"""
MCP-to-MCP proxy manager.

At server startup the lifespan function:
  1. Spawns each child MCP server as a subprocess via stdio transport.
  2. Connects a ClientSession and performs the MCP handshake.
  3. Calls list_tools() to discover every tool the child exposes.
  4. Wraps each child tool in a thin async proxy and dynamically registers it
     on the FastMCP app so Claude sees them as native tools.

On server shutdown all child sessions and subprocesses are cleaned up.

Tool schema forwarding:
  The child's inputSchema is passed directly as the 'parameters' on the proxy
  Tool object, so Claude receives the exact same JSON Schema (parameter names,
  types, defaults, descriptions) as if it were talking directly to the child.

Arg routing:
  FastMCP validates incoming args with a permissive Pydantic model
  (extra='allow') then unpacks them as **kwargs into the proxy function.
  The proxy function forwards the raw kwargs dict straight to
  ClientSession.call_tool(), which serialises them for the child server.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools.base import Tool, FuncMetadata
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
from pydantic import ConfigDict

from proxy.config import CHILD_SERVERS

logger = logging.getLogger("aws-mcp-server.proxy")


# ---------------------------------------------------------------------------
# Permissive arg model — captures any kwargs without a fixed schema
# ---------------------------------------------------------------------------

class _AnyArgsModel(ArgModelBase):
    """Accepts arbitrary keyword arguments for proxy forwarding."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def model_dump_one_level(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name, field_info in self.__class__.model_fields.items():
            output_name = field_info.alias if field_info.alias else field_name
            result[output_name] = getattr(self, field_name)
        result.update(self.model_extra or {})
        return result


_PROXY_FUNC_METADATA = FuncMetadata(
    arg_model=_AnyArgsModel,
    output_schema=None,
    output_model=None,
    wrap_output=False,
)


# ---------------------------------------------------------------------------
# Proxy tool factory
# ---------------------------------------------------------------------------

def _make_proxy_tool(session: ClientSession, child_tool: Any) -> Tool:
    """Return a FastMCP Tool that delegates calls to a child server tool."""
    tool_name = child_tool.name

    async def _proxy(**kwargs: Any) -> str:
        result = await session.call_tool(tool_name, kwargs)
        parts: list[str] = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        return "\n".join(parts)

    _proxy.__name__ = tool_name

    return Tool(
        fn=_proxy,
        name=tool_name,
        title=None,
        description=child_tool.description or "",
        parameters=child_tool.inputSchema,
        fn_metadata=_PROXY_FUNC_METADATA,
        is_async=True,
        context_kwarg=None,
        annotations=None,
        icons=[],
        meta=None,
    )


# ---------------------------------------------------------------------------
# Lifespan — connect / disconnect all child servers
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastMCP):
    """FastMCP lifespan that starts child MCP servers and registers proxy tools."""
    _open_contexts: list[Any] = []
    _open_sessions: list[ClientSession] = []
    total_proxied = 0

    for cfg in CHILD_SERVERS:
        server_name = cfg["name"]
        try:
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )
            ctx = stdio_client(params)
            read, write = await ctx.__aenter__()
            _open_contexts.append(ctx)

            session = ClientSession(read, write)
            await session.__aenter__()
            _open_sessions.append(session)

            await session.initialize()
            logger.info("[proxy] Connected to child server: %s", server_name)

            tools_resp = await session.list_tools()
            for child_tool in tools_resp.tools:
                proxy_tool = _make_proxy_tool(session, child_tool)
                app._tool_manager._tools[child_tool.name] = proxy_tool
                logger.info("[proxy]   + %s", child_tool.name)
                total_proxied += 1

        except Exception as exc:
            logger.warning(
                "[proxy] Could not connect to %s (%s %s): %s — skipping.",
                server_name, cfg["command"], " ".join(cfg.get("args", [])), exc,
            )

    logger.info("[proxy] Proxy ready — %d tools registered from child servers.", total_proxied)
    yield

    # Graceful shutdown
    for session in reversed(_open_sessions):
        try:
            await session.__aexit__(None, None, None)
        except Exception:
            pass
    for ctx in reversed(_open_contexts):
        try:
            await ctx.__aexit__(None, None, None)
        except Exception:
            pass
    logger.info("[proxy] All child server connections closed.")
