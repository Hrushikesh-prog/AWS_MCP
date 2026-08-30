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


@mcp.tool()
def aws_create_sqs_queue(
    queue_name: str,
    region: str = "us-east-1",
    fifo: bool = False,
    delay_seconds: int = 0,
    visibility_timeout: int = 30,
    message_retention_seconds: int = 345600,
    tags: dict[str, str] | None = None,
) -> str:
    """
    Create an SQS queue.

    Args:
        queue_name:                 Queue name (FIFO queues must end with '.fifo'). (required)
        region:                     AWS region (default 'us-east-1').
        fifo:                       Create a FIFO queue (default False).
        delay_seconds:              Delivery delay in seconds 0-900 (default 0).
        visibility_timeout:         Visibility timeout in seconds 0-43200 (default 30).
        message_retention_seconds:  Retention period in seconds 60-1209600 (default 345600 = 4 days).
        tags:                       Dict of tag key-value pairs (optional).

    Returns:
        JSON: queue_url, queue_name.
    """
    if not queue_name.strip():
        return _err("queue_name is required.", "VALIDATION_ERROR")
    logger.info("aws_create_sqs_queue name=%s region=%s fifo=%s", queue_name, region, fifo)
    try:
        attrs: dict[str, str] = {
            "DelaySeconds": str(delay_seconds),
            "VisibilityTimeout": str(visibility_timeout),
            "MessageRetentionPeriod": str(message_retention_seconds),
        }
        if fifo:
            attrs["FifoQueue"] = "true"
            attrs["ContentBasedDeduplication"] = "true"
        kwargs: dict[str, Any] = {"QueueName": queue_name, "Attributes": attrs}
        if tags:
            kwargs["tags"] = tags
        resp = boto3.client("sqs", region_name=region).create_queue(**kwargs)
        return _ok({"queue_url": resp.get("QueueUrl"), "queue_name": queue_name})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_sqs_queue(
    queue_url: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete an SQS queue and all its messages.

    Args:
        queue_url: SQS queue URL to delete. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: queue_url, message.
    """
    if not queue_url.strip():
        return _err("queue_url is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_sqs_queue url=%s region=%s", queue_url, region)
    try:
        boto3.client("sqs", region_name=region).delete_queue(QueueUrl=queue_url)
        return _ok({"queue_url": queue_url, "message": "Queue deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_sqs_queue_attributes(
    queue_url: str,
    region: str = "us-east-1",
) -> str:
    """
    Get attributes of an SQS queue (message counts, visibility timeout, etc.).

    Args:
        queue_url: SQS queue URL. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: queue_url, attributes dict including ApproximateNumberOfMessages,
              VisibilityTimeout, MessageRetentionPeriod, QueueArn, etc.
    """
    if not queue_url.strip():
        return _err("queue_url is required.", "VALIDATION_ERROR")
    logger.info("aws_get_sqs_queue_attributes url=%s region=%s", queue_url, region)
    try:
        resp = boto3.client("sqs", region_name=region).get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["All"],
        )
        return _ok({"queue_url": queue_url, "attributes": resp.get("Attributes", {})})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_send_sqs_message(
    queue_url: str,
    message_body: str,
    delay_seconds: int = 0,
    message_group_id: str = "",
    message_deduplication_id: str = "",
    message_attributes: dict[str, Any] | None = None,
    region: str = "us-east-1",
) -> str:
    """
    Send a message to an SQS queue.

    Args:
        queue_url:                 SQS queue URL. (required)
        message_body:              Message body string. (required)
        delay_seconds:             Per-message delay 0-900 (default 0; not valid for FIFO).
        message_group_id:          Required for FIFO queues.
        message_deduplication_id:  Required for FIFO queues without content-based deduplication.
        message_attributes:        Dict of message attribute objects (optional).
        region:                    AWS region (default 'us-east-1').

    Returns:
        JSON: message_id, md5_of_body.
    """
    if not queue_url.strip() or not message_body.strip():
        return _err("queue_url and message_body are required.", "VALIDATION_ERROR")
    logger.info("aws_send_sqs_message url=%s region=%s", queue_url, region)
    try:
        kwargs: dict[str, Any] = {"QueueUrl": queue_url, "MessageBody": message_body}
        if delay_seconds > 0:
            kwargs["DelaySeconds"] = delay_seconds
        if message_group_id:
            kwargs["MessageGroupId"] = message_group_id
        if message_deduplication_id:
            kwargs["MessageDeduplicationId"] = message_deduplication_id
        if message_attributes:
            kwargs["MessageAttributes"] = message_attributes
        resp = boto3.client("sqs", region_name=region).send_message(**kwargs)
        return _ok({
            "message_id": resp.get("MessageId"),
            "md5_of_body": resp.get("MD5OfMessageBody"),
            "sequence_number": resp.get("SequenceNumber"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_receive_sqs_messages(
    queue_url: str,
    max_messages: int = 1,
    visibility_timeout: int = 30,
    wait_time_seconds: int = 0,
    region: str = "us-east-1",
) -> str:
    """
    Receive messages from an SQS queue. Messages remain in the queue until deleted.

    Args:
        queue_url:          SQS queue URL. (required)
        max_messages:       Max messages to receive 1-10 (default 1).
        visibility_timeout: Seconds messages stay invisible after receipt (default 30).
        wait_time_seconds:  Long-polling wait time 0-20 seconds (default 0 = short poll).
        region:             AWS region (default 'us-east-1').

    Returns:
        JSON: message_count, messages — each with message_id, receipt_handle,
              body, md5_of_body, attributes, message_attributes.
    """
    max_messages = max(1, min(int(max_messages), 10))
    if not queue_url.strip():
        return _err("queue_url is required.", "VALIDATION_ERROR")
    logger.info("aws_receive_sqs_messages url=%s max=%d region=%s", queue_url, max_messages, region)
    try:
        resp = boto3.client("sqs", region_name=region).receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            VisibilityTimeout=visibility_timeout,
            WaitTimeSeconds=wait_time_seconds,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
        messages = [
            {
                "message_id": m.get("MessageId"),
                "receipt_handle": m.get("ReceiptHandle"),
                "body": m.get("Body"),
                "md5_of_body": m.get("MD5OfBody"),
                "attributes": m.get("Attributes", {}),
                "message_attributes": m.get("MessageAttributes", {}),
            }
            for m in resp.get("Messages", [])
        ]
        return _ok({"queue_url": queue_url, "message_count": len(messages), "messages": messages})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_sqs_message(
    queue_url: str,
    receipt_handle: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete a specific message from an SQS queue using its receipt handle.

    Args:
        queue_url:      SQS queue URL. (required)
        receipt_handle: Receipt handle from aws_receive_sqs_messages. (required)
        region:         AWS region (default 'us-east-1').

    Returns:
        JSON: queue_url, message.
    """
    if not queue_url.strip() or not receipt_handle.strip():
        return _err("queue_url and receipt_handle are required.", "VALIDATION_ERROR")
    logger.info("aws_delete_sqs_message url=%s region=%s", queue_url, region)
    try:
        boto3.client("sqs", region_name=region).delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )
        return _ok({"queue_url": queue_url, "message": "Message deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_purge_sqs_queue(
    queue_url: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete all messages in an SQS queue (irreversible; once per 60 seconds max).

    Args:
        queue_url: SQS queue URL. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: queue_url, message.
    """
    if not queue_url.strip():
        return _err("queue_url is required.", "VALIDATION_ERROR")
    logger.info("aws_purge_sqs_queue url=%s region=%s", queue_url, region)
    try:
        boto3.client("sqs", region_name=region).purge_queue(QueueUrl=queue_url)
        return _ok({"queue_url": queue_url, "message": "Queue purge initiated (may take up to 60 seconds)."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
