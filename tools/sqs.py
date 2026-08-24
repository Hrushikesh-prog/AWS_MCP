from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_list_sqs_queues(
    region: str = "us-east-1",
    prefix: str = "",
) -> str:
    """
    List SQS queues in an AWS region, optionally filtered by a name prefix.

    Args:
        region: AWS region to query (default 'us-east-1').
        prefix: Optional queue name prefix for filtering. (optional)

    Returns:
        JSON: region, queue_count, queue_urls (list of URL strings).
    """
    logger.info("aws_list_sqs_queues region=%s prefix=%r", region, prefix)
    try:
        kwargs: dict[str, Any] = {}
        if prefix:
            kwargs["QueueNamePrefix"] = prefix
        resp = boto3.client("sqs", region_name=region).list_queues(**kwargs)
        urls = resp.get("QueueUrls", [])
        return _ok({"region": region, "queue_count": len(urls), "queue_urls": urls})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
