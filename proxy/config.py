"""
Child MCP server definitions.

Each entry is a dict with:
  name    — human label used in log messages
  command — executable to run (e.g. "uvx" or "npx")
  args    — argument list passed to command
  env     — optional dict of extra env vars to merge into the child process env
            (None → inherit the parent process environment)

Add, remove, or comment-out entries to control which servers are proxied.
"""
from __future__ import annotations

CHILD_SERVERS: list[dict] = [
    {
        "name": "SNS/SQS",
        "command": "uvx",
        "args": ["awslabs.amazon-sns-sqs-mcp-server@latest"],
        "env": None,
    },
    {
        "name": "Billing",
        "command": "uvx",
        "args": ["awslabs.billing-cost-management-mcp-server@latest"],
        "env": None,
    },
    {
        "name": "DynamoDB",
        "command": "uvx",
        "args": ["awslabs.dynamodb-mcp-server@latest"],
        "env": None,
    },
    {
        "name": "IAM",
        "command": "uvx",
        "args": ["awslabs.iam-mcp-server@latest"],
        "env": None,
    },
]
