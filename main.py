#!/usr/bin/env python3
"""
AWS MCP Server — entry point.

Imports all tools, resources, and prompts (registration via decorators),
then starts the FastMCP server on stdio or SSE transport.

  MCP_TRANSPORT=stdio  (default) — local Claude Desktop / CLI
  MCP_TRANSPORT=sse              — Cloud Run / HTTP host (set PORT too)
"""
from __future__ import annotations

import os

import prompts
import resources
import tools
from server import logger, mcp

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    port = int(os.environ.get("PORT", "8080"))

    logger.info(
        "AWS MCP Server starting — transport=%s port=%s | tools=100 resources=5 prompts=5",
        transport, port if transport == "sse" else "n/a",
    )

    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
