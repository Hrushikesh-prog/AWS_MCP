from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_list_s3_buckets() -> str:
    """
    List all S3 buckets in the AWS account.

    Returns:
        JSON: bucket_count (int), buckets (list with name + creation_date).
    """
    logger.info("aws_list_s3_buckets")
    try:
        response = boto3.client("s3").list_buckets()
        buckets = [
            {"name": b["Name"], "creation_date": b["CreationDate"]}
            for b in response.get("Buckets", [])
        ]
        return _ok({"bucket_count": len(buckets), "buckets": buckets})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_s3_objects(
    bucket_name: str,
    prefix: str = "",
    max_keys: int = 20,
) -> str:
    """
    List objects inside an S3 bucket, optionally filtered by a key prefix.

    Args:
        bucket_name: Name of the S3 bucket. (required)
        prefix:      Key prefix filter, e.g. 'logs/2024/'. (optional)
        max_keys:    Max objects to return; default 20, capped at 100.

    Returns:
        JSON: bucket, prefix, object_count, truncated, objects
              (each: key, size_bytes, last_modified, storage_class).
    """
    if not bucket_name or not bucket_name.strip():
        return _err("bucket_name must be a non-empty string.", "VALIDATION_ERROR")
    max_keys = max(1, min(int(max_keys), 100))
    logger.info("aws_get_s3_objects bucket=%s prefix=%r max_keys=%d", bucket_name, prefix, max_keys)
    try:
        kwargs: dict[str, Any] = {"Bucket": bucket_name, "MaxKeys": max_keys}
        if prefix:
            kwargs["Prefix"] = prefix
        response = boto3.client("s3").list_objects_v2(**kwargs)
        objects = [
            {
                "key": o["Key"],
                "size_bytes": o["Size"],
                "last_modified": o["LastModified"],
                "storage_class": o.get("StorageClass", "STANDARD"),
            }
            for o in response.get("Contents", [])
        ]
        return _ok({
            "bucket": bucket_name, "prefix": prefix,
            "object_count": len(objects),
            "truncated": response.get("IsTruncated", False),
            "objects": objects,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
