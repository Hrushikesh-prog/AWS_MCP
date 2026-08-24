from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp


@mcp.resource("aws://cloudwatch/{region}/log-groups")
def resource_cloudwatch_log_groups(region: str) -> str:
    """
    All CloudWatch log groups in the specified region with retention settings.
    Attach this resource to discover available log groups before querying logs.
    URI pattern: aws://cloudwatch/<region>/log-groups
    """
    logger.info("resource: aws://cloudwatch/%s/log-groups", region)
    try:
        paginator = boto3.client("logs", region_name=region).get_paginator(
            "describe_log_groups"
        )
        groups: list[str] = []
        for page in paginator.paginate():
            for g in page.get("logGroups", []):
                retention = g.get("retentionInDays", "Never expires")
                stored_mb = round(g.get("storedBytes", 0) / 1_048_576, 2)
                groups.append(
                    f"- `{g['logGroupName']}` | retention: {retention} days | "
                    f"stored: {stored_mb} MB"
                )
        lines = [f"# CloudWatch Log Groups — {region}", f"Total: {len(groups)}", ""]
        lines += groups if groups else ["No log groups found."]
        return "\n".join(lines)
    except (ClientError, BotoCoreError) as e:
        return f"Error fetching log groups in {region}: {e}"
