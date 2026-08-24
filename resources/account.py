from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp


@mcp.resource("aws://account/identity")
def resource_account_identity() -> str:
    """
    Current AWS caller identity: account ID, ARN, and user/role ID.
    Attach this resource to verify which AWS account is active.
    """
    logger.info("resource: aws://account/identity")
    try:
        resp = boto3.client("sts").get_caller_identity()
        lines = [
            "# AWS Caller Identity",
            f"- **Account ID:** {resp.get('Account')}",
            f"- **ARN:**        {resp.get('Arn')}",
            f"- **User ID:**    {resp.get('UserId')}",
        ]
        return "\n".join(lines)
    except (ClientError, BotoCoreError) as e:
        return f"Error fetching identity: {e}"
