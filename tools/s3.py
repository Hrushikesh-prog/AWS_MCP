from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


def _s3():
    return boto3.client("s3")


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


@mcp.tool()
def aws_create_s3_bucket(
    bucket_name: str,
    region: str = "us-east-1",
    enable_versioning: bool = False,
) -> str:
    """
    Create a new S3 bucket.

    Args:
        bucket_name:       Globally unique bucket name. (required)
        region:            AWS region for the bucket; default 'us-east-1'.
        enable_versioning: Enable versioning on creation; default False.

    Returns:
        JSON: bucket_name, location, versioning.
    """
    if not bucket_name:
        return _err("bucket_name is required.", "VALIDATION_ERROR")
    logger.info("aws_create_s3_bucket bucket=%s region=%s", bucket_name, region)
    try:
        client = boto3.client("s3", region_name=region)
        kwargs: dict[str, Any] = {"Bucket": bucket_name}
        if region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        client.create_bucket(**kwargs)
        if enable_versioning:
            client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"},
            )
        return _ok({
            "bucket_name": bucket_name,
            "region": region,
            "versioning": "Enabled" if enable_versioning else "Suspended",
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_s3_bucket(bucket_name: str, force: bool = False) -> str:
    """
    Delete an S3 bucket. The bucket must be empty unless force=True.

    Args:
        bucket_name: Bucket name to delete. (required)
        force:       If True, delete all objects and versions first. Default False.

    Returns:
        JSON: status message.
    """
    if not bucket_name:
        return _err("bucket_name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_s3_bucket bucket=%s force=%s", bucket_name, force)
    try:
        client = boto3.client("s3")
        if force:
            paginator = client.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=bucket_name):
                objects_to_delete = [
                    {"Key": obj["Key"], "VersionId": obj["VersionId"]}
                    for obj in page.get("Versions", []) + page.get("DeleteMarkers", [])
                ]
                if objects_to_delete:
                    client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects_to_delete})
        client.delete_bucket(Bucket=bucket_name)
        return _ok({"message": f"Bucket '{bucket_name}' deleted successfully."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_upload_s3_object(
    bucket_name: str,
    key: str,
    content: str,
    content_type: str = "text/plain",
) -> str:
    """
    Upload a text or JSON string as an S3 object.

    Args:
        bucket_name:  Destination bucket name. (required)
        key:          Object key (path), e.g. 'data/config.json'. (required)
        content:      Text content to upload. (required)
        content_type: MIME type, e.g. 'application/json'; default 'text/plain'.

    Returns:
        JSON: bucket, key, etag, size_bytes.
    """
    if not bucket_name or not key or content is None:
        return _err("bucket_name, key, and content are required.", "VALIDATION_ERROR")
    logger.info("aws_upload_s3_object bucket=%s key=%s", bucket_name, key)
    try:
        body = content.encode("utf-8")
        r = boto3.client("s3").put_object(
            Bucket=bucket_name, Key=key, Body=body, ContentType=content_type,
        )
        return _ok({
            "bucket": bucket_name,
            "key": key,
            "etag": r.get("ETag", "").strip('"'),
            "size_bytes": len(body),
            "content_type": content_type,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_download_s3_object(bucket_name: str, key: str) -> str:
    """
    Download the content of an S3 object as a UTF-8 string.

    Args:
        bucket_name: Bucket name. (required)
        key:         Object key. (required)

    Returns:
        JSON: bucket, key, content, content_type, size_bytes, last_modified.
    """
    if not bucket_name or not key:
        return _err("bucket_name and key are required.", "VALIDATION_ERROR")
    logger.info("aws_download_s3_object bucket=%s key=%s", bucket_name, key)
    try:
        r = boto3.client("s3").get_object(Bucket=bucket_name, Key=key)
        body = r["Body"].read()
        try:
            content = body.decode("utf-8")
        except UnicodeDecodeError:
            import base64
            content = f"[binary data, base64]\n{base64.b64encode(body).decode()}"
        return _ok({
            "bucket": bucket_name,
            "key": key,
            "content": content,
            "content_type": r.get("ContentType", ""),
            "size_bytes": r.get("ContentLength"),
            "last_modified": r.get("LastModified"),
            "etag": r.get("ETag", "").strip('"'),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_s3_object(bucket_name: str, key: str, version_id: str = "") -> str:
    """
    Delete an object from an S3 bucket.

    Args:
        bucket_name: Bucket name. (required)
        key:         Object key to delete. (required)
        version_id:  Specific version to delete (versioned buckets). (optional)

    Returns:
        JSON: status message.
    """
    if not bucket_name or not key:
        return _err("bucket_name and key are required.", "VALIDATION_ERROR")
    logger.info("aws_delete_s3_object bucket=%s key=%s", bucket_name, key)
    try:
        kwargs: dict[str, Any] = {"Bucket": bucket_name, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id
        r = boto3.client("s3").delete_object(**kwargs)
        return _ok({
            "message": f"Object '{key}' deleted from '{bucket_name}'.",
            "version_id": r.get("VersionId", ""),
            "delete_marker": r.get("DeleteMarker", False),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_copy_s3_object(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
) -> str:
    """
    Copy an S3 object from one location to another (within or across buckets).

    Args:
        source_bucket: Source bucket name. (required)
        source_key:    Source object key. (required)
        dest_bucket:   Destination bucket name. (required)
        dest_key:      Destination object key. (required)

    Returns:
        JSON: source, destination, etag.
    """
    if not all([source_bucket, source_key, dest_bucket, dest_key]):
        return _err("All four arguments are required.", "VALIDATION_ERROR")
    logger.info("aws_copy_s3_object %s/%s -> %s/%s", source_bucket, source_key, dest_bucket, dest_key)
    try:
        r = boto3.client("s3").copy_object(
            Bucket=dest_bucket,
            Key=dest_key,
            CopySource={"Bucket": source_bucket, "Key": source_key},
        )
        return _ok({
            "source": f"s3://{source_bucket}/{source_key}",
            "destination": f"s3://{dest_bucket}/{dest_key}",
            "etag": r.get("CopyObjectResult", {}).get("ETag", "").strip('"'),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_s3_object_metadata(bucket_name: str, key: str) -> str:
    """
    Get metadata for an S3 object without downloading its content.

    Args:
        bucket_name: Bucket name. (required)
        key:         Object key. (required)

    Returns:
        JSON: key, size_bytes, last_modified, etag, content_type, metadata.
    """
    if not bucket_name or not key:
        return _err("bucket_name and key are required.", "VALIDATION_ERROR")
    logger.info("aws_get_s3_object_metadata bucket=%s key=%s", bucket_name, key)
    try:
        r = boto3.client("s3").head_object(Bucket=bucket_name, Key=key)
        return _ok({
            "bucket": bucket_name,
            "key": key,
            "size_bytes": r.get("ContentLength"),
            "last_modified": r.get("LastModified"),
            "etag": r.get("ETag", "").strip('"'),
            "content_type": r.get("ContentType", ""),
            "storage_class": r.get("StorageClass", "STANDARD"),
            "version_id": r.get("VersionId", ""),
            "metadata": r.get("Metadata", {}),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_s3_bucket_versioning(bucket_name: str) -> str:
    """
    Get the versioning configuration of an S3 bucket.

    Args:
        bucket_name: Bucket name. (required)

    Returns:
        JSON: bucket, versioning_status.
    """
    if not bucket_name:
        return _err("bucket_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_s3_bucket_versioning bucket=%s", bucket_name)
    try:
        r = boto3.client("s3").get_bucket_versioning(Bucket=bucket_name)
        return _ok({"bucket": bucket_name, "versioning_status": r.get("Status", "Not set")})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_put_s3_bucket_versioning(bucket_name: str, status: str = "Enabled") -> str:
    """
    Enable or suspend versioning on an S3 bucket.

    Args:
        bucket_name: Bucket name. (required)
        status:      'Enabled' or 'Suspended'; default 'Enabled'.

    Returns:
        JSON: bucket, versioning_status.
    """
    if not bucket_name:
        return _err("bucket_name is required.", "VALIDATION_ERROR")
    if status not in {"Enabled", "Suspended"}:
        return _err("status must be 'Enabled' or 'Suspended'.", "VALIDATION_ERROR")
    logger.info("aws_put_s3_bucket_versioning bucket=%s status=%s", bucket_name, status)
    try:
        boto3.client("s3").put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": status},
        )
        return _ok({"bucket": bucket_name, "versioning_status": status})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_generate_s3_presigned_url(
    bucket_name: str,
    key: str,
    operation: str = "get_object",
    expiry_seconds: int = 3600,
) -> str:
    """
    Generate a pre-signed URL for temporary access to an S3 object.

    Args:
        bucket_name:    Bucket name. (required)
        key:            Object key. (required)
        operation:      'get_object' (download) or 'put_object' (upload); default 'get_object'.
        expiry_seconds: URL validity in seconds; default 3600 (1h), max 604800 (7d).

    Returns:
        JSON: presigned_url, operation, expires_in_seconds.
    """
    if not bucket_name or not key:
        return _err("bucket_name and key are required.", "VALIDATION_ERROR")
    if operation not in {"get_object", "put_object"}:
        return _err("operation must be 'get_object' or 'put_object'.", "VALIDATION_ERROR")
    expiry_seconds = max(1, min(int(expiry_seconds), 604800))
    logger.info("aws_generate_s3_presigned_url bucket=%s key=%s op=%s", bucket_name, key, operation)
    try:
        url = boto3.client("s3").generate_presigned_url(
            ClientMethod=operation,
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=expiry_seconds,
        )
        return _ok({"presigned_url": url, "operation": operation, "expires_in_seconds": expiry_seconds})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_s3_bucket_location(bucket_name: str) -> str:
    """
    Get the AWS region where an S3 bucket is located.

    Args:
        bucket_name: Bucket name. (required)

    Returns:
        JSON: bucket, region.
    """
    if not bucket_name:
        return _err("bucket_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_s3_bucket_location bucket=%s", bucket_name)
    try:
        r = boto3.client("s3").get_bucket_location(Bucket=bucket_name)
        region = r.get("LocationConstraint") or "us-east-1"
        return _ok({"bucket": bucket_name, "region": region})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_s3_bucket_tags(bucket_name: str) -> str:
    """
    Get tags applied to an S3 bucket.

    Args:
        bucket_name: Bucket name. (required)

    Returns:
        JSON: bucket, tags (dict).
    """
    if not bucket_name:
        return _err("bucket_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_s3_bucket_tags bucket=%s", bucket_name)
    try:
        r = boto3.client("s3").get_bucket_tagging(Bucket=bucket_name)
        tags = {t["Key"]: t["Value"] for t in r.get("TagSet", [])}
        return _ok({"bucket": bucket_name, "tags": tags})
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchTagSet":
            return _ok({"bucket": bucket_name, "tags": {}})
        return _err(str(e), code)
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_put_s3_bucket_tags(bucket_name: str, tags: dict[str, str]) -> str:
    """
    Set (replace) all tags on an S3 bucket.

    Args:
        bucket_name: Bucket name. (required)
        tags:        Dict of tag key-value pairs, e.g. {"env": "prod"}. (required)

    Returns:
        JSON: bucket, tags applied.
    """
    if not bucket_name or tags is None:
        return _err("bucket_name and tags are required.", "VALIDATION_ERROR")
    logger.info("aws_put_s3_bucket_tags bucket=%s", bucket_name)
    try:
        boto3.client("s3").put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]},
        )
        return _ok({"bucket": bucket_name, "tags": tags, "message": "Tags updated successfully."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
