from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


def _sm(region: str):
    return boto3.client("secretsmanager", region_name=region)


@mcp.tool()
def aws_list_secrets(region: str = "us-east-1", max_results: int = 50) -> str:
    """
    List all secrets in AWS Secrets Manager.

    Args:
        region:      AWS region (default 'us-east-1').
        max_results: Max secrets to return; default 50, capped at 100.

    Returns:
        JSON: region, secret_count, secrets (name, arn, last_changed, description).
    """
    max_results = max(1, min(int(max_results), 100))
    logger.info("aws_list_secrets region=%s", region)
    try:
        paginator = _sm(region).get_paginator("list_secrets")
        secrets: list[dict[str, Any]] = []
        for page in paginator.paginate(MaxResults=max_results):
            for s in page.get("SecretList", []):
                secrets.append({
                    "name": s.get("Name"),
                    "arn": s.get("ARN"),
                    "description": s.get("Description", ""),
                    "last_changed": s.get("LastChangedDate"),
                    "last_accessed": s.get("LastAccessedDate"),
                    "rotation_enabled": s.get("RotationEnabled", False),
                    "tags": {t["Key"]: t["Value"] for t in s.get("Tags", [])},
                })
        return _ok({"region": region, "secret_count": len(secrets), "secrets": secrets})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_secret(secret_id: str, region: str = "us-east-1") -> str:
    """
    Describe a secret's metadata (no value returned).

    Args:
        secret_id: Secret name or ARN. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: name, arn, description, rotation info, tags, versions.
    """
    if not secret_id:
        return _err("secret_id is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_secret secret=%s region=%s", secret_id, region)
    try:
        r = _sm(region).describe_secret(SecretId=secret_id)
        return _ok({
            "name": r.get("Name"),
            "arn": r.get("ARN"),
            "description": r.get("Description", ""),
            "rotation_enabled": r.get("RotationEnabled", False),
            "rotation_lambda_arn": r.get("RotationLambdaARN"),
            "last_rotated": r.get("LastRotatedDate"),
            "last_changed": r.get("LastChangedDate"),
            "last_accessed": r.get("LastAccessedDate"),
            "tags": {t["Key"]: t["Value"] for t in r.get("Tags", [])},
            "version_ids": list(r.get("VersionIdsToStages", {}).keys()),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_secret_value(secret_id: str, region: str = "us-east-1") -> str:
    """
    Retrieve the current value of a secret.

    Args:
        secret_id: Secret name or ARN. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: name, arn, secret_string (or secret_binary as base64), version_id.
    """
    if not secret_id:
        return _err("secret_id is required.", "VALIDATION_ERROR")
    logger.info("aws_get_secret_value secret=%s region=%s", secret_id, region)
    try:
        r = _sm(region).get_secret_value(SecretId=secret_id)
        return _ok({
            "name": r.get("Name"),
            "arn": r.get("ARN"),
            "version_id": r.get("VersionId"),
            "secret_string": r.get("SecretString"),
            "created_date": r.get("CreatedDate"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_secret(
    name: str,
    secret_string: str,
    description: str = "",
    region: str = "us-east-1",
) -> str:
    """
    Create a new secret in AWS Secrets Manager.

    Args:
        name:          Unique secret name. (required)
        secret_string: Secret value as a string or JSON string. (required)
        description:   Human-readable description. (optional)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: name, arn, version_id.
    """
    if not name or not secret_string:
        return _err("name and secret_string are required.", "VALIDATION_ERROR")
    logger.info("aws_create_secret name=%s region=%s", name, region)
    try:
        kwargs: dict[str, Any] = {"Name": name, "SecretString": secret_string}
        if description:
            kwargs["Description"] = description
        r = _sm(region).create_secret(**kwargs)
        return _ok({"name": r.get("Name"), "arn": r.get("ARN"), "version_id": r.get("VersionId")})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_update_secret(
    secret_id: str,
    secret_string: str,
    description: str = "",
    region: str = "us-east-1",
) -> str:
    """
    Update the value (and optionally description) of an existing secret.

    Args:
        secret_id:     Secret name or ARN. (required)
        secret_string: New secret value. (required)
        description:   New description (omit to leave unchanged). (optional)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: name, arn, version_id.
    """
    if not secret_id or not secret_string:
        return _err("secret_id and secret_string are required.", "VALIDATION_ERROR")
    logger.info("aws_update_secret secret=%s region=%s", secret_id, region)
    try:
        kwargs: dict[str, Any] = {"SecretId": secret_id, "SecretString": secret_string}
        if description:
            kwargs["Description"] = description
        r = _sm(region).update_secret(**kwargs)
        return _ok({"name": r.get("Name"), "arn": r.get("ARN"), "version_id": r.get("VersionId")})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_secret(
    secret_id: str,
    recovery_window_days: int = 30,
    force_delete: bool = False,
    region: str = "us-east-1",
) -> str:
    """
    Schedule a secret for deletion.

    Args:
        secret_id:             Secret name or ARN. (required)
        recovery_window_days:  Days before permanent deletion (7–30); default 30.
                               Ignored when force_delete is True.
        force_delete:          If True, delete immediately with no recovery window.
        region:                AWS region (default 'us-east-1').

    Returns:
        JSON: name, arn, deletion_date.
    """
    if not secret_id:
        return _err("secret_id is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_secret secret=%s force=%s region=%s", secret_id, force_delete, region)
    try:
        kwargs: dict[str, Any] = {"SecretId": secret_id}
        if force_delete:
            kwargs["ForceDeleteWithoutRecovery"] = True
        else:
            kwargs["RecoveryWindowInDays"] = max(7, min(int(recovery_window_days), 30))
        r = _sm(region).delete_secret(**kwargs)
        return _ok({"name": r.get("Name"), "arn": r.get("ARN"), "deletion_date": r.get("DeletionDate")})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_restore_secret(secret_id: str, region: str = "us-east-1") -> str:
    """
    Restore a secret that was scheduled for deletion.

    Args:
        secret_id: Secret name or ARN. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: name, arn.
    """
    if not secret_id:
        return _err("secret_id is required.", "VALIDATION_ERROR")
    logger.info("aws_restore_secret secret=%s region=%s", secret_id, region)
    try:
        r = _sm(region).restore_secret(SecretId=secret_id)
        return _ok({"name": r.get("Name"), "arn": r.get("ARN")})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_secret_versions(secret_id: str, region: str = "us-east-1") -> str:
    """
    List all versions of a secret.

    Args:
        secret_id: Secret name or ARN. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: secret_id, versions (version_id, stages, created_date).
    """
    if not secret_id:
        return _err("secret_id is required.", "VALIDATION_ERROR")
    logger.info("aws_list_secret_versions secret=%s region=%s", secret_id, region)
    try:
        paginator = _sm(region).get_paginator("list_secret_version_ids")
        versions: list[dict[str, Any]] = []
        for page in paginator.paginate(SecretId=secret_id):
            for v in page.get("Versions", []):
                versions.append({
                    "version_id": v.get("VersionId"),
                    "stages": v.get("VersionStages", []),
                    "created_date": v.get("CreatedDate"),
                    "last_accessed": v.get("LastAccessedDate"),
                })
        return _ok({"secret_id": secret_id, "version_count": len(versions), "versions": versions})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_tag_secret(
    secret_id: str,
    tags: dict[str, str],
    region: str = "us-east-1",
) -> str:
    """
    Add or update tags on a secret.

    Args:
        secret_id: Secret name or ARN. (required)
        tags:      Dict of tag key-value pairs, e.g. {"env": "prod"}. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: status message.
    """
    if not secret_id or not tags:
        return _err("secret_id and tags are required.", "VALIDATION_ERROR")
    logger.info("aws_tag_secret secret=%s region=%s", secret_id, region)
    try:
        _sm(region).tag_resource(
            SecretId=secret_id,
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )
        return _ok({"message": f"Tags applied to secret '{secret_id}'.", "tags": tags})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
