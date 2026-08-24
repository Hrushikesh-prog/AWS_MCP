from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp


@mcp.resource("aws://lambda/{region}/functions")
def resource_lambda_functions(region: str) -> str:
    """
    All Lambda functions in the specified region with runtime and memory info.
    URI pattern: aws://lambda/<region>/functions
    """
    logger.info("resource: aws://lambda/%s/functions", region)
    try:
        paginator = boto3.client("lambda", region_name=region).get_paginator("list_functions")
        rows: list[str] = []
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                rows.append(
                    f"- `{fn.get('FunctionName')}` | {fn.get('Runtime')} | "
                    f"{fn.get('MemorySize')} MB | timeout {fn.get('Timeout')}s"
                )
        lines = [f"# Lambda Functions — {region}", f"Total: {len(rows)}", ""]
        lines += rows if rows else ["No functions found."]
        return "\n".join(lines)
    except (ClientError, BotoCoreError) as e:
        return f"Error fetching Lambda functions in {region}: {e}"
