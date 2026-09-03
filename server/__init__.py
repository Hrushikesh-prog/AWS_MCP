from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from proxy.manager import lifespan

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
        "Unified AWS MCP server: native boto3 tools for S3, EC2, DynamoDB, "
        "CloudWatch, Lambda, RDS, SNS, SQS, IAM, and Billing — plus proxied "
        "tools from any configured child MCP servers (awslabs and others). "
        "Credentials resolved via the standard AWS credential chain."
    ),
    lifespan=lifespan,
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8080")),
)
