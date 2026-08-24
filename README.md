# AWS MCP Server

A production-ready, read-only [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that gives Claude direct access to your AWS account. Built with [FastMCP](https://github.com/jlowin/fastmcp) and [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html).

## What it does

This server acts as a bridge between Claude and your AWS account. Once connected, Claude can query your AWS resources in plain English — no AWS Console or CLI needed. All operations are **read-only**; nothing is created, modified, or deleted.

## Features

### Tools (9)
Direct, targeted queries against AWS services:

| Tool | Description |
|---|---|
| `aws_list_s3_buckets` | List all S3 buckets in the account |
| `aws_get_s3_objects` | List objects in a bucket (with prefix filter) |
| `aws_list_ec2_instances` | List EC2 instances with state, IPs, and Name tags |
| `aws_execute_read_query_dynamodb` | Scan a DynamoDB table (read-only) |
| `aws_get_cloudwatch_logs` | Fetch and filter CloudWatch log events |
| `aws_list_lambda_functions` | List Lambda functions and their runtimes |
| `aws_describe_rds_instances` | Describe RDS database instances |
| `aws_list_sns_topics` | List SNS topics |
| `aws_list_sqs_queues` | List SQS queues |

### Resources (5)
Bulk context loaders — Claude reads these to get a broad picture before diving into specifics:

- **account** — caller identity and account summary
- **s3** — bucket inventory
- **ec2** — instance inventory
- **lambda** — function inventory
- **cloudwatch** — log group inventory

### Prompts (5)
Pre-built analysis workflows Claude can run on demand:

- **infrastructure_overview** — full account inventory summary
- **ec2_troubleshoot** — EC2 connectivity and health diagnostics
- **incident_analysis** — CloudWatch log triage for incidents
- **cost_optimization** — spot idle/oversized resources
- **s3_security_audit** — flag public or misconfigured buckets

## Project structure

```
AWS_MCP/
├── main.py                    # Entry point — selects stdio or SSE transport
├── server.py                  # FastMCP app instance and logger
├── requirements.txt           # Pinned dependencies
├── Dockerfile                 # Multi-stage image for Cloud Run
├── claude_desktop_config.json # Example config for Claude Desktop
├── tools/                     # One module per AWS service
│   ├── s3.py
│   ├── ec2.py
│   ├── dynamodb.py
│   ├── cloudwatch.py
│   ├── lambda_.py
│   ├── rds.py
│   ├── iam.py
│   ├── sns.py
│   └── sqs.py
├── resources/                 # Bulk context loaders
├── prompts/                   # Pre-built analysis workflows
└── utils/
    └── serializers.py         # DynamoDB TypeDeserializer helpers
```

## Prerequisites

- Python 3.11+
- AWS credentials configured (IAM user or role) with **read-only** permissions
- [Claude Desktop](https://claude.ai/download) or any MCP-compatible client

## Local setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd AWS_MCP

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure AWS credentials (choose one)
#    Option A — AWS credentials file (~/.aws/credentials)
#    Option B — environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

## Connect to Claude Desktop

Add the following to your `claude_desktop_config.json`:

**Windows** — `%APPDATA%\Claude\claude_desktop_config.json`  
**macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Linux** — `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aws": {
      "command": "C:\\path\\to\\AWS_MCP\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\AWS_MCP\\main.py"],
      "env": {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "your_key",
        "AWS_SECRET_ACCESS_KEY": "your_secret"
      }
    }
  }
}
```

Restart Claude Desktop. You should see the AWS tools available in the tools panel.

## Deploy to GCP Cloud Run

The server supports HTTP/SSE transport for hosted deployments.

```bash
# Build and push the image
docker build -t gcr.io/YOUR_PROJECT/aws-mcp-server .
docker push gcr.io/YOUR_PROJECT/aws-mcp-server

# Deploy — pass AWS credentials as secrets, never bake them into the image
gcloud run deploy aws-mcp-server \
  --image gcr.io/YOUR_PROJECT/aws-mcp-server \
  --region us-central1 \
  --set-env-vars MCP_TRANSPORT=sse,AWS_DEFAULT_REGION=us-east-1 \
  --set-secrets AWS_ACCESS_KEY_ID=aws-access-key:latest,AWS_SECRET_ACCESS_KEY=aws-secret-key:latest \
  --allow-unauthenticated
```

The `MCP_TRANSPORT=sse` env var switches the server from STDIO to HTTP/SSE mode automatically. `PORT` is injected by Cloud Run and defaults to `8080`.

## Transport modes

| Mode | When to use | How to activate |
|---|---|---|
| `stdio` | Local Claude Desktop / CLI | Default (no env var needed) |
| `sse` | Cloud Run / remote HTTP host | `MCP_TRANSPORT=sse` |

## Security notes

- All tools are **read-only** — no write or delete operations are exposed.
- Use an IAM user or role with the minimum required read permissions (`ReadOnlyAccess` policy or a custom policy).
- Never commit AWS credentials to source control. Use environment variables, `~/.aws/credentials`, or Secret Manager for Cloud Run.
- The Docker image runs as a non-root user (`appuser`) for container security.

## Dependencies

| Package | Purpose |
|---|---|
| `mcp[cli] >=1.9` | MCP framework (FastMCP, transport layer) |
| `boto3 >=1.38` | AWS SDK |
| `botocore >=1.38` | Low-level AWS client |
| `pydantic >=2.10` | Data validation |
