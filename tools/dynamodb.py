from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_execute_read_query_dynamodb(
    table_name: str,
    region: str = "us-east-1",
    limit: int = 10,
) -> str:
    """
    Perform a safe, read-only Scan on a DynamoDB table and return a sample.

    Decimal and datetime values are automatically serialized to JSON types.

    Args:
        table_name: Name of the DynamoDB table. (required)
        region:     AWS region (default 'us-east-1').
        limit:      Max items to return; default 10, capped at 50.

    Returns:
        JSON: table_name, count, scanned_count, items (deserialized documents).
    """
    if not table_name or not table_name.strip():
        return _err("table_name must be a non-empty string.", "VALIDATION_ERROR")
    limit = max(1, min(int(limit), 50))
    logger.info("aws_execute_read_query_dynamodb table=%s region=%s limit=%d", table_name, region, limit)
    try:
        from boto3.dynamodb.types import TypeDeserializer  # noqa: PLC0415
        client = boto3.client("dynamodb", region_name=region)
        td = TypeDeserializer()
        resp = client.scan(TableName=table_name, Limit=limit)
        items = [{k: td.deserialize(v) for k, v in raw.items()} for raw in resp.get("Items", [])]
        return _ok({
            "table_name": table_name,
            "count": resp.get("Count", len(items)),
            "scanned_count": resp.get("ScannedCount", len(items)),
            "items": items,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_update_dynamodb_billing_mode(
    table_name: str,
    billing_mode: str = "PAY_PER_REQUEST",
    region: str = "us-east-1",
) -> str:
    """
    Update the billing mode of a DynamoDB table.

    Switching to PAY_PER_REQUEST (On-Demand) removes provisioned capacity
    and auto-scaling policies, which cascade-deletes associated CloudWatch alarms.

    Args:
        table_name:   Name of the DynamoDB table. (required)
        billing_mode: 'PAY_PER_REQUEST' (On-Demand) or 'PROVISIONED' (default: PAY_PER_REQUEST).
        region:       AWS region (default 'us-east-1').

    Returns:
        JSON: table_name, billing_mode, table_status.
    """
    if not table_name or not table_name.strip():
        return _err("table_name must be a non-empty string.", "VALIDATION_ERROR")
    _VALID = {"PAY_PER_REQUEST", "PROVISIONED"}
    if billing_mode not in _VALID:
        return _err(f"billing_mode must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")

    logger.info("aws_update_dynamodb_billing_mode table=%s mode=%s region=%s", table_name, billing_mode, region)
    try:
        client = boto3.client("dynamodb", region_name=region)
        resp = client.update_table(TableName=table_name, BillingMode=billing_mode)
        table = resp.get("TableDescription", {})
        return _ok({
            "table_name": table.get("TableName"),
            "billing_mode": billing_mode,
            "table_status": table.get("TableStatus"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
