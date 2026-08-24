from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

# CRITICAL: stream=sys.stderr — any write to stdout corrupts MCP JSON-RPC framing.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("aws-mcp-server")

mcp = FastMCP(
    name="AWS MCP Server",
    instructions=(
        "Read-only access to AWS: S3, EC2, DynamoDB, CloudWatch Logs, "
        "Lambda, RDS, SNS, SQS, and IAM identity. "
        "Credentials resolved via the standard AWS credential chain. "
        "Use resources to load bulk context and tools for targeted queries."
    ),
)
