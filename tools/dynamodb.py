from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


def _deserialize_items(raw_items: list[dict]) -> list[dict]:
    from boto3.dynamodb.types import TypeDeserializer
    td = TypeDeserializer()
    return [{k: td.deserialize(v) for k, v in item.items()} for item in raw_items]


@mcp.tool()
def aws_list_dynamodb_tables(
    region: str = "us-east-1",
) -> str:
    """
    List all DynamoDB tables in an AWS region.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: region, table_count, table_names (list of strings).
    """
    logger.info("aws_list_dynamodb_tables region=%s", region)
    try:
        client = boto3.client("dynamodb", region_name=region)
        paginator = client.get_paginator("list_tables")
        tables: list[str] = []
        for page in paginator.paginate():
            tables.extend(page.get("TableNames", []))
        return _ok({"region": region, "table_count": len(tables), "table_names": tables})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_dynamodb_table(
    table_name: str,
    region: str = "us-east-1",
) -> str:
    """
    Get detailed metadata about a DynamoDB table.

    Args:
        table_name: Name of the DynamoDB table. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: table_name, status, item_count, size_bytes, billing_mode,
              key_schema, attribute_definitions, global_secondary_indexes,
              creation_date_time, provisioned_throughput.
    """
    if not table_name or not table_name.strip():
        return _err("table_name must be a non-empty string.", "VALIDATION_ERROR")
    logger.info("aws_describe_dynamodb_table table=%s region=%s", table_name, region)
    try:
        resp = boto3.client("dynamodb", region_name=region).describe_table(TableName=table_name)
        t = resp.get("Table", {})
        return _ok({
            "table_name": t.get("TableName"),
            "status": t.get("TableStatus"),
            "item_count": t.get("ItemCount"),
            "size_bytes": t.get("TableSizeBytes"),
            "billing_mode": t.get("BillingModeSummary", {}).get("BillingMode"),
            "key_schema": t.get("KeySchema", []),
            "attribute_definitions": t.get("AttributeDefinitions", []),
            "global_secondary_indexes": [
                {
                    "name": gsi.get("IndexName"),
                    "status": gsi.get("IndexStatus"),
                    "item_count": gsi.get("ItemCount"),
                    "key_schema": gsi.get("KeySchema", []),
                }
                for gsi in t.get("GlobalSecondaryIndexes", [])
            ],
            "local_secondary_indexes": [
                {"name": lsi.get("IndexName"), "key_schema": lsi.get("KeySchema", [])}
                for lsi in t.get("LocalSecondaryIndexes", [])
            ],
            "provisioned_throughput": t.get("ProvisionedThroughput", {}),
            "creation_date_time": t.get("CreationDateTime"),
            "arn": t.get("TableArn"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


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
        client = boto3.client("dynamodb", region_name=region)
        resp = client.scan(TableName=table_name, Limit=limit)
        items = _deserialize_items(resp.get("Items", []))
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
def aws_query_dynamodb_table(
    table_name: str,
    key_condition_expression: str,
    expression_attribute_names: dict[str, str] | None = None,
    expression_attribute_values: dict[str, Any] | None = None,
    index_name: str = "",
    limit: int = 25,
    scan_index_forward: bool = True,
    region: str = "us-east-1",
) -> str:
    """
    Query a DynamoDB table or index using a KeyConditionExpression.

    Args:
        table_name:                  DynamoDB table name. (required)
        key_condition_expression:    DynamoDB key condition, e.g. 'pk = :pk_val'. (required)
        expression_attribute_names:  Dict mapping placeholders to attribute names.
        expression_attribute_values: Dict mapping value placeholders to DynamoDB-typed values,
                                     e.g. {":pk_val": {"S": "user#123"}}.
        index_name:                  Global or local secondary index name (optional).
        limit:                       Max items; default 25, capped at 100.
        scan_index_forward:          True = ascending (default), False = descending.
        region:                      AWS region (default 'us-east-1').

    Returns:
        JSON: table_name, count, items (deserialized).
    """
    if not table_name.strip() or not key_condition_expression.strip():
        return _err("table_name and key_condition_expression are required.", "VALIDATION_ERROR")
    limit = max(1, min(int(limit), 100))
    logger.info("aws_query_dynamodb_table table=%s region=%s", table_name, region)
    try:
        kwargs: dict[str, Any] = {
            "TableName": table_name,
            "KeyConditionExpression": key_condition_expression,
            "Limit": limit,
            "ScanIndexForward": scan_index_forward,
        }
        if index_name:
            kwargs["IndexName"] = index_name
        if expression_attribute_names:
            kwargs["ExpressionAttributeNames"] = expression_attribute_names
        if expression_attribute_values:
            kwargs["ExpressionAttributeValues"] = expression_attribute_values

        resp = boto3.client("dynamodb", region_name=region).query(**kwargs)
        items = _deserialize_items(resp.get("Items", []))
        return _ok({"table_name": table_name, "count": resp.get("Count", len(items)), "items": items})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_dynamodb_item(
    table_name: str,
    key: dict[str, Any],
    region: str = "us-east-1",
) -> str:
    """
    Get a single item from DynamoDB by its primary key.

    Args:
        table_name: DynamoDB table name. (required)
        key:        Primary key as DynamoDB-typed dict,
                    e.g. {"pk": {"S": "user#123"}, "sk": {"S": "profile"}}.
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: table_name, found (bool), item (deserialized if found).
    """
    if not table_name.strip():
        return _err("table_name is required.", "VALIDATION_ERROR")
    if not key:
        return _err("key must be a non-empty dict.", "VALIDATION_ERROR")
    logger.info("aws_get_dynamodb_item table=%s region=%s", table_name, region)
    try:
        resp = boto3.client("dynamodb", region_name=region).get_item(
            TableName=table_name,
            Key=key,
        )
        raw = resp.get("Item")
        if raw is None:
            return _ok({"table_name": table_name, "found": False, "item": None})
        item = _deserialize_items([raw])[0]
        return _ok({"table_name": table_name, "found": True, "item": item})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_put_dynamodb_item(
    table_name: str,
    item: dict[str, Any],
    region: str = "us-east-1",
) -> str:
    """
    Put (create or replace) a single item in a DynamoDB table.

    Args:
        table_name: DynamoDB table name. (required)
        item:       Item as a DynamoDB-typed dict,
                    e.g. {"pk": {"S": "user#123"}, "name": {"S": "Alice"}}.
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: table_name, message.
    """
    if not table_name.strip():
        return _err("table_name is required.", "VALIDATION_ERROR")
    if not item:
        return _err("item must be a non-empty dict.", "VALIDATION_ERROR")
    logger.info("aws_put_dynamodb_item table=%s region=%s", table_name, region)
    try:
        boto3.client("dynamodb", region_name=region).put_item(TableName=table_name, Item=item)
        return _ok({"table_name": table_name, "message": "Item written successfully."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_dynamodb_item(
    table_name: str,
    key: dict[str, Any],
    region: str = "us-east-1",
) -> str:
    """
    Delete a single item from a DynamoDB table by its primary key.

    Args:
        table_name: DynamoDB table name. (required)
        key:        Primary key as DynamoDB-typed dict,
                    e.g. {"pk": {"S": "user#123"}}.
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: table_name, message.
    """
    if not table_name.strip():
        return _err("table_name is required.", "VALIDATION_ERROR")
    if not key:
        return _err("key must be a non-empty dict.", "VALIDATION_ERROR")
    logger.info("aws_delete_dynamodb_item table=%s region=%s", table_name, region)
    try:
        boto3.client("dynamodb", region_name=region).delete_item(TableName=table_name, Key=key)
        return _ok({"table_name": table_name, "message": "Item deleted successfully."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_dynamodb_table(
    table_name: str,
    key_schema: list[dict[str, str]],
    attribute_definitions: list[dict[str, str]],
    billing_mode: str = "PAY_PER_REQUEST",
    region: str = "us-east-1",
    read_capacity: int = 5,
    write_capacity: int = 5,
) -> str:
    """
    Create a new DynamoDB table.

    Args:
        table_name:            Name for the new table. (required)
        key_schema:            List of {"AttributeName": "...", "KeyType": "HASH"|"RANGE"}.
        attribute_definitions: List of {"AttributeName": "...", "AttributeType": "S"|"N"|"B"}.
        billing_mode:          'PAY_PER_REQUEST' (default) or 'PROVISIONED'.
        region:                AWS region (default 'us-east-1').
        read_capacity:         Read capacity units (only for PROVISIONED; default 5).
        write_capacity:        Write capacity units (only for PROVISIONED; default 5).

    Returns:
        JSON: table_name, status, arn.
    """
    if not table_name.strip():
        return _err("table_name is required.", "VALIDATION_ERROR")
    logger.info("aws_create_dynamodb_table table=%s region=%s", table_name, region)
    try:
        kwargs: dict[str, Any] = {
            "TableName": table_name,
            "KeySchema": key_schema,
            "AttributeDefinitions": attribute_definitions,
            "BillingMode": billing_mode,
        }
        if billing_mode == "PROVISIONED":
            kwargs["ProvisionedThroughput"] = {
                "ReadCapacityUnits": read_capacity,
                "WriteCapacityUnits": write_capacity,
            }
        resp = boto3.client("dynamodb", region_name=region).create_table(**kwargs)
        t = resp.get("TableDescription", {})
        return _ok({
            "table_name": t.get("TableName"),
            "status": t.get("TableStatus"),
            "arn": t.get("TableArn"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_dynamodb_table(
    table_name: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete a DynamoDB table and all its data (irreversible).

    Args:
        table_name: Name of the table to delete. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: table_name, status.
    """
    if not table_name.strip():
        return _err("table_name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_dynamodb_table table=%s region=%s", table_name, region)
    try:
        resp = boto3.client("dynamodb", region_name=region).delete_table(TableName=table_name)
        t = resp.get("TableDescription", {})
        return _ok({"table_name": t.get("TableName"), "status": t.get("TableStatus")})
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

    Switching to PAY_PER_REQUEST removes provisioned capacity and auto-scaling policies.

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
        resp = boto3.client("dynamodb", region_name=region).update_table(
            TableName=table_name, BillingMode=billing_mode,
        )
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
