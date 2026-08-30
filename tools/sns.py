from __future__ import annotations

from typing import Any

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


@mcp.tool()
def aws_create_sns_topic(
    name: str,
    region: str = "us-east-1",
    fifo: bool = False,
    tags: dict[str, str] | None = None,
) -> str:
    """
    Create an SNS topic.

    Args:
        name:   Topic name. For FIFO topics must end with '.fifo'. (required)
        region: AWS region (default 'us-east-1').
        fifo:   Create a FIFO topic (default False).
        tags:   Dict of tag key-value pairs (optional).

    Returns:
        JSON: topic_arn.
    """
    if not name.strip():
        return _err("name is required.", "VALIDATION_ERROR")
    logger.info("aws_create_sns_topic name=%s region=%s fifo=%s", name, region, fifo)
    try:
        kwargs: dict[str, Any] = {"Name": name}
        if fifo:
            kwargs["Attributes"] = {"FifoTopic": "true"}
        if tags:
            kwargs["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]
        resp = boto3.client("sns", region_name=region).create_topic(**kwargs)
        return _ok({"topic_arn": resp.get("TopicArn"), "name": name})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_sns_topic(
    topic_arn: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete an SNS topic and all its subscriptions.

    Args:
        topic_arn: SNS topic ARN to delete. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: topic_arn, message.
    """
    if not topic_arn.strip():
        return _err("topic_arn is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_sns_topic arn=%s region=%s", topic_arn, region)
    try:
        boto3.client("sns", region_name=region).delete_topic(TopicArn=topic_arn)
        return _ok({"topic_arn": topic_arn, "message": "Topic deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_sns_topic_attributes(
    topic_arn: str,
    region: str = "us-east-1",
) -> str:
    """
    Get attributes of an SNS topic (subscriptions count, policy, etc.).

    Args:
        topic_arn: SNS topic ARN. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: topic_arn, attributes dict.
    """
    if not topic_arn.strip():
        return _err("topic_arn is required.", "VALIDATION_ERROR")
    logger.info("aws_get_sns_topic_attributes arn=%s region=%s", topic_arn, region)
    try:
        resp = boto3.client("sns", region_name=region).get_topic_attributes(TopicArn=topic_arn)
        return _ok({"topic_arn": topic_arn, "attributes": resp.get("Attributes", {})})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_publish_sns_message(
    topic_arn: str,
    message: str,
    subject: str = "",
    message_group_id: str = "",
    message_deduplication_id: str = "",
    region: str = "us-east-1",
) -> str:
    """
    Publish a message to an SNS topic.

    Args:
        topic_arn:                 SNS topic ARN. (required)
        message:                   Message body. (required)
        subject:                   Email subject line (optional, used in email subscriptions).
        message_group_id:          Required for FIFO topics — groups messages into ordered sequences.
        message_deduplication_id:  Required for FIFO topics without content-based deduplication.
        region:                    AWS region (default 'us-east-1').

    Returns:
        JSON: message_id.
    """
    if not topic_arn.strip() or not message.strip():
        return _err("topic_arn and message are required.", "VALIDATION_ERROR")
    logger.info("aws_publish_sns_message arn=%s region=%s", topic_arn, region)
    try:
        kwargs: dict[str, Any] = {"TopicArn": topic_arn, "Message": message}
        if subject:
            kwargs["Subject"] = subject
        if message_group_id:
            kwargs["MessageGroupId"] = message_group_id
        if message_deduplication_id:
            kwargs["MessageDeduplicationId"] = message_deduplication_id
        resp = boto3.client("sns", region_name=region).publish(**kwargs)
        return _ok({"message_id": resp.get("MessageId"), "topic_arn": topic_arn})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_sns_subscriptions(
    region: str = "us-east-1",
    topic_arn: str = "",
) -> str:
    """
    List SNS subscriptions, optionally filtered by topic.

    Args:
        region:    AWS region (default 'us-east-1').
        topic_arn: Filter to subscriptions of this topic (optional).

    Returns:
        JSON: subscription_count, subscriptions — each with subscription_arn,
              topic_arn, protocol, endpoint, owner.
    """
    logger.info("aws_list_sns_subscriptions region=%s topic=%s", region, topic_arn or "all")
    try:
        client = boto3.client("sns", region_name=region)
        subs: list[dict[str, Any]] = []
        if topic_arn:
            paginator = client.get_paginator("list_subscriptions_by_topic")
            pages = paginator.paginate(TopicArn=topic_arn)
        else:
            paginator = client.get_paginator("list_subscriptions")
            pages = paginator.paginate()
        for page in pages:
            for s in page.get("Subscriptions", []):
                subs.append({
                    "subscription_arn": s.get("SubscriptionArn"),
                    "topic_arn": s.get("TopicArn"),
                    "protocol": s.get("Protocol"),
                    "endpoint": s.get("Endpoint"),
                    "owner": s.get("Owner"),
                })
        return _ok({"subscription_count": len(subs), "subscriptions": subs})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_subscribe_sns_topic(
    topic_arn: str,
    protocol: str,
    endpoint: str,
    region: str = "us-east-1",
) -> str:
    """
    Subscribe an endpoint to an SNS topic.

    Args:
        topic_arn: SNS topic ARN. (required)
        protocol:  Delivery protocol: 'email', 'email-json', 'sqs', 'lambda',
                   'https', 'http', 'sms', 'application', 'firehose'. (required)
        endpoint:  Endpoint to receive notifications (email address, SQS ARN, etc.). (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: subscription_arn (or 'PendingConfirmation' for email).
    """
    if not topic_arn.strip() or not protocol.strip() or not endpoint.strip():
        return _err("topic_arn, protocol, and endpoint are required.", "VALIDATION_ERROR")
    logger.info("aws_subscribe_sns_topic arn=%s proto=%s region=%s", topic_arn, protocol, region)
    try:
        resp = boto3.client("sns", region_name=region).subscribe(
            TopicArn=topic_arn,
            Protocol=protocol,
            Endpoint=endpoint,
            ReturnSubscriptionArn=True,
        )
        return _ok({
            "subscription_arn": resp.get("SubscriptionArn"),
            "topic_arn": topic_arn,
            "protocol": protocol,
            "endpoint": endpoint,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_unsubscribe_sns(
    subscription_arn: str,
    region: str = "us-east-1",
) -> str:
    """
    Remove a subscription from an SNS topic.

    Args:
        subscription_arn: The subscription ARN to remove. (required)
        region:           AWS region (default 'us-east-1').

    Returns:
        JSON: subscription_arn, message.
    """
    if not subscription_arn.strip():
        return _err("subscription_arn is required.", "VALIDATION_ERROR")
    logger.info("aws_unsubscribe_sns arn=%s region=%s", subscription_arn, region)
    try:
        boto3.client("sns", region_name=region).unsubscribe(SubscriptionArn=subscription_arn)
        return _ok({"subscription_arn": subscription_arn, "message": "Unsubscribed successfully."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
