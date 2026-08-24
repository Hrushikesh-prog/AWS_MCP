from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _serialize


@mcp.resource("aws://s3/buckets")
def resource_s3_buckets() -> str:
    """
    All S3 buckets in the account with their creation dates.
    Attach this resource to get a quick bucket inventory.
    """
    logger.info("resource: aws://s3/buckets")
    try:
        resp = boto3.client("s3").list_buckets()
        buckets = resp.get("Buckets", [])
        if not buckets:
            return "# S3 Buckets\nNo buckets found."
        lines = ["# S3 Buckets", f"Total: {len(buckets)}", ""]
        for b in buckets:
            created = _serialize(b["CreationDate"])
            lines.append(f"- `{b['Name']}` (created {created})")
        return "\n".join(lines)
    except (ClientError, BotoCoreError) as e:
        return f"Error fetching buckets: {e}"
