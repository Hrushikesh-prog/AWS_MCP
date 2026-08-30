# AWS MCP — Hybrid Server

A hybrid [Model Context Protocol (MCP)](https://modelcontextprotocol.io) setup that combines a custom FastMCP server for EC2/S3/Lambda/RDS with official [AWS Labs MCP servers](https://github.com/awslabs/mcp) for everything else.

## Architecture

| Server | Source | Covers |
|--------|--------|--------|
| `custom-aws` | This project (FastMCP + boto3) | EC2 (50 tools), S3, Lambda, RDS, Resources, Prompts |
| `awslabs.aws-documentation-mcp-server` | Official AWS Labs | AWS docs & API reference search |
| `awslabs.cloudwatch-mcp-server` | Official AWS Labs | CloudWatch metrics, alarms, logs analysis |
| `awslabs.dynamodb-mcp-server` | Official AWS Labs | DynamoDB design guidance & operations |
| `awslabs.iam-mcp-server` | Official AWS Labs | IAM users, roles, policies, groups |
| `awslabs.amazon-sns-sqs-mcp-server` | Official AWS Labs | SNS topics & SQS queue management |
| `awslabs.billing-cost-management-mcp-server` | Official AWS Labs | AWS billing & cost management |

**Why custom for EC2?** No official AWS Labs MCP server exists for general EC2 management. The custom server fills that gap with 50 read-only EC2 tools.

## Custom Server — What It Does

### Tools (54)
| Tool | Description |
|------|-------------|
| `aws_list_s3_buckets` | List all S3 buckets |
| `aws_get_s3_objects` | List objects in a bucket (with prefix filter) |
| `aws_list_ec2_instances` | List instances with state, IPs, Name tags |
| *(+ 47 more EC2 tools)* | Describe, filter, and inspect EC2 resources |
| `aws_list_lambda_functions` | List Lambda functions and runtimes |
| `aws_describe_rds_instances` | Describe RDS database instances |

### Resources (5)
Bulk context loaders — read once for a broad account picture:
- **account** — caller identity and account summary
- **s3** — bucket inventory
- **ec2** — instance inventory
- **lambda** — function inventory
- **cloudwatch** — log group inventory

### Prompts (5)
Pre-built analysis workflows:
- **infrastructure_overview** — full account inventory summary
- **ec2_troubleshoot** — EC2 connectivity and health diagnostics
- **incident_analysis** — CloudWatch log triage for incidents
- **cost_optimization** — spot idle/oversized resources
- **s3_security_audit** — flag public or misconfigured buckets

## Project Structure

```
AWS_MCP/
├── main.py                    # Entry point — stdio or SSE transport
├── server.py                  # FastMCP app instance and logger
├── requirements.txt           # Pinned dependencies
├── Dockerfile                 # Multi-stage image for Cloud Run
├── claude_desktop_config.json # Hybrid config for Claude Desktop
├── .mcp.json                  # Hybrid config for Claude Code CLI
├── tools/                     # Custom tools (EC2, S3, Lambda, RDS)
│   ├── ec2.py
│   ├── s3.py
│   ├── lambda_.py
│   └── rds.py
├── resources/                 # Bulk context loaders
├── prompts/                   # Pre-built analysis workflows
└── utils/
    └── serializers.py
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — required to run official AWS Labs servers
- AWS credentials configured (`~/.aws/credentials` or env vars)

### Install uv (if not already installed)
```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Local Setup (Custom Server)

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

## Connect to Claude Desktop

Copy `claude_desktop_config.json` content into:
- **Windows** — `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`

Update the `custom-aws` path to match your actual install location, and set your `AWS_PROFILE` (or replace with explicit key/secret). Restart Claude Desktop.

## Connect to Claude Code CLI

The `.mcp.json` in this directory is automatically picked up by Claude Code when you open this folder. Update `AWS_DEFAULT_REGION` as needed. AWS credentials are read from `~/.aws/credentials` by default.

## Transport Modes (Custom Server)

| Mode | When to use | How to activate |
|------|-------------|-----------------|
| `stdio` | Local Claude Desktop / CLI | Default |
| `sse` | Cloud Run / remote HTTP host | `MCP_TRANSPORT=sse` |

## Security Notes

- Custom server tools are **read-only** — no write or delete operations.
- Official AWS Labs servers may support write operations (e.g., IAM, SNS/SQS). Use a scoped IAM role.
- Never commit AWS credentials to source control.
- The Docker image runs as a non-root user (`appuser`).

## Dependencies

| Package | Purpose |
|---------|---------|
| `mcp[cli] >=1.9` | FastMCP framework |
| `boto3 >=1.38` | AWS SDK for the custom server |
| `pydantic >=2.10` | Data validation |
| `uv` | Runs official AWS Labs MCP servers |
