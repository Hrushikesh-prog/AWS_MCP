from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_list_sns_topics(
    region: str = "us-east-1",
) -> str:
    """
    List all SNS topics in an AWS region.

    Args:
        region: AWS region to query (default 'us-east-1').

    Returns:
        JSON: region, topic_count, topic_arns (list of ARN strings).
    """
    logger.info("aws_list_sns_topics region=%s", region)
    try:
        paginator = boto3.client("sns", region_name=region).get_paginator("list_topics")
        arns = [t["TopicArn"] for page in paginator.paginate() for t in page.get("Topics", [])]
        return _ok({"region": region, "topic_count": len(arns), "topic_arns": arns})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
