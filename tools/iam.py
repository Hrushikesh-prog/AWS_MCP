from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_get_caller_identity() -> str:
    """
    Return the AWS identity (account, ARN, user ID) for the active credentials.

    Useful for verifying which account and principal the server is operating as
    before performing any other queries.

    Returns:
        JSON: account_id, arn, user_id.
    """
    logger.info("aws_get_caller_identity")
    try:
        resp = boto3.client("sts").get_caller_identity()
        return _ok({
            "account_id": resp.get("Account"),
            "arn": resp.get("Arn"),
            "user_id": resp.get("UserId"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
