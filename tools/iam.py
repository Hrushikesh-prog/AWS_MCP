from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_get_caller_identity() -> str:
    """
    Return the AWS identity (account, ARN, user ID) for the active credentials.

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


@mcp.tool()
def aws_get_account_summary() -> str:
    """
    Get a summary of IAM resource counts and limits for the account.

    Returns:
        JSON: account summary map (e.g., Users, Groups, Roles, Policies, etc.)
    """
    logger.info("aws_get_account_summary")
    try:
        resp = boto3.client("iam").get_account_summary()
        return _ok({"summary_map": resp.get("SummaryMap", {})})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_iam_users(
    max_results: int = 50,
) -> str:
    """
    List IAM users in the account.

    Args:
        max_results: Max users to return; default 50, capped at 200.

    Returns:
        JSON: user_count, users — each with user_name, user_id, arn,
              path, create_date, password_last_used.
    """
    max_results = max(1, min(int(max_results), 200))
    logger.info("aws_list_iam_users max=%d", max_results)
    try:
        paginator = boto3.client("iam").get_paginator("list_users")
        users: list[dict[str, Any]] = []
        for page in paginator.paginate():
            for u in page.get("Users", []):
                users.append({
                    "user_name": u.get("UserName"),
                    "user_id": u.get("UserId"),
                    "arn": u.get("Arn"),
                    "path": u.get("Path"),
                    "create_date": u.get("CreateDate"),
                    "password_last_used": u.get("PasswordLastUsed"),
                })
            if len(users) >= max_results:
                users = users[:max_results]
                break
        return _ok({"user_count": len(users), "users": users})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_iam_user(
    user_name: str,
) -> str:
    """
    Get details about a specific IAM user.

    Args:
        user_name: IAM user name. (required)

    Returns:
        JSON: user_name, user_id, arn, path, create_date, tags.
    """
    if not user_name.strip():
        return _err("user_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_iam_user user=%s", user_name)
    try:
        resp = boto3.client("iam").get_user(UserName=user_name)
        u = resp.get("User", {})
        return _ok({
            "user_name": u.get("UserName"),
            "user_id": u.get("UserId"),
            "arn": u.get("Arn"),
            "path": u.get("Path"),
            "create_date": u.get("CreateDate"),
            "password_last_used": u.get("PasswordLastUsed"),
            "tags": u.get("Tags", []),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_iam_user(
    user_name: str,
    path: str = "/",
    tags: dict[str, str] | None = None,
) -> str:
    """
    Create a new IAM user.

    Args:
        user_name: Name for the new IAM user. (required)
        path:      IAM path (default '/').
        tags:      Dict of tag key-value pairs (optional).

    Returns:
        JSON: user_name, user_id, arn, create_date.
    """
    if not user_name.strip():
        return _err("user_name is required.", "VALIDATION_ERROR")
    logger.info("aws_create_iam_user user=%s", user_name)
    try:
        kwargs: dict[str, Any] = {"UserName": user_name, "Path": path}
        if tags:
            kwargs["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]
        resp = boto3.client("iam").create_user(**kwargs)
        u = resp.get("User", {})
        return _ok({
            "user_name": u.get("UserName"),
            "user_id": u.get("UserId"),
            "arn": u.get("Arn"),
            "create_date": u.get("CreateDate"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_iam_user(
    user_name: str,
) -> str:
    """
    Delete an IAM user. The user must have no attached policies, access keys,
    or group memberships before deletion.

    Args:
        user_name: IAM user name to delete. (required)

    Returns:
        JSON: user_name, message.
    """
    if not user_name.strip():
        return _err("user_name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_iam_user user=%s", user_name)
    try:
        boto3.client("iam").delete_user(UserName=user_name)
        return _ok({"user_name": user_name, "message": "IAM user deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_iam_roles(
    max_results: int = 50,
    path_prefix: str = "/",
) -> str:
    """
    List IAM roles in the account.

    Args:
        max_results: Max roles to return; default 50, capped at 200.
        path_prefix: Filter by path prefix (default '/').

    Returns:
        JSON: role_count, roles — each with role_name, role_id, arn,
              path, description, create_date.
    """
    max_results = max(1, min(int(max_results), 200))
    logger.info("aws_list_iam_roles max=%d", max_results)
    try:
        paginator = boto3.client("iam").get_paginator("list_roles")
        roles: list[dict[str, Any]] = []
        for page in paginator.paginate(PathPrefix=path_prefix):
            for r in page.get("Roles", []):
                roles.append({
                    "role_name": r.get("RoleName"),
                    "role_id": r.get("RoleId"),
                    "arn": r.get("Arn"),
                    "path": r.get("Path"),
                    "description": r.get("Description", ""),
                    "create_date": r.get("CreateDate"),
                    "max_session_duration": r.get("MaxSessionDuration"),
                })
            if len(roles) >= max_results:
                roles = roles[:max_results]
                break
        return _ok({"role_count": len(roles), "roles": roles})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_iam_policies(
    scope: str = "Local",
    max_results: int = 50,
) -> str:
    """
    List IAM managed policies.

    Args:
        scope:       'Local' (customer-managed, default), 'AWS' (managed), or 'All'.
        max_results: Max policies to return; default 50, capped at 200.

    Returns:
        JSON: policy_count, policies — each with policy_name, arn,
              attachment_count, create_date, update_date.
    """
    max_results = max(1, min(int(max_results), 200))
    _VALID = {"Local", "AWS", "All"}
    if scope not in _VALID:
        return _err(f"scope must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")
    logger.info("aws_list_iam_policies scope=%s max=%d", scope, max_results)
    try:
        paginator = boto3.client("iam").get_paginator("list_policies")
        policies: list[dict[str, Any]] = []
        for page in paginator.paginate(Scope=scope):
            for p in page.get("Policies", []):
                policies.append({
                    "policy_name": p.get("PolicyName"),
                    "arn": p.get("Arn"),
                    "attachment_count": p.get("AttachmentCount", 0),
                    "create_date": p.get("CreateDate"),
                    "update_date": p.get("UpdateDate"),
                    "description": p.get("Description", ""),
                })
            if len(policies) >= max_results:
                policies = policies[:max_results]
                break
        return _ok({"policy_count": len(policies), "policies": policies})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_attached_role_policies(
    role_name: str,
) -> str:
    """
    List managed policies attached to an IAM role.

    Args:
        role_name: IAM role name. (required)

    Returns:
        JSON: role_name, policy_count, policies — each with policy_name, arn.
    """
    if not role_name.strip():
        return _err("role_name is required.", "VALIDATION_ERROR")
    logger.info("aws_list_attached_role_policies role=%s", role_name)
    try:
        paginator = boto3.client("iam").get_paginator("list_attached_role_policies")
        policies: list[dict[str, Any]] = []
        for page in paginator.paginate(RoleName=role_name):
            for p in page.get("AttachedPolicies", []):
                policies.append({"policy_name": p.get("PolicyName"), "arn": p.get("PolicyArn")})
        return _ok({"role_name": role_name, "policy_count": len(policies), "policies": policies})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_attach_role_policy(
    role_name: str,
    policy_arn: str,
) -> str:
    """
    Attach a managed IAM policy to a role.

    Args:
        role_name:  IAM role name. (required)
        policy_arn: ARN of the managed policy to attach. (required)

    Returns:
        JSON: role_name, policy_arn, message.
    """
    if not role_name.strip() or not policy_arn.strip():
        return _err("role_name and policy_arn are required.", "VALIDATION_ERROR")
    logger.info("aws_attach_role_policy role=%s policy=%s", role_name, policy_arn)
    try:
        boto3.client("iam").attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        return _ok({"role_name": role_name, "policy_arn": policy_arn, "message": "Policy attached."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_detach_role_policy(
    role_name: str,
    policy_arn: str,
) -> str:
    """
    Detach a managed IAM policy from a role.

    Args:
        role_name:  IAM role name. (required)
        policy_arn: ARN of the managed policy to detach. (required)

    Returns:
        JSON: role_name, policy_arn, message.
    """
    if not role_name.strip() or not policy_arn.strip():
        return _err("role_name and policy_arn are required.", "VALIDATION_ERROR")
    logger.info("aws_detach_role_policy role=%s policy=%s", role_name, policy_arn)
    try:
        boto3.client("iam").detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        return _ok({"role_name": role_name, "policy_arn": policy_arn, "message": "Policy detached."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_iam_access_keys(
    user_name: str,
) -> str:
    """
    List IAM access keys for a user.

    Args:
        user_name: IAM user name. (required)

    Returns:
        JSON: user_name, access_keys — each with access_key_id, status, create_date.
    """
    if not user_name.strip():
        return _err("user_name is required.", "VALIDATION_ERROR")
    logger.info("aws_list_iam_access_keys user=%s", user_name)
    try:
        resp = boto3.client("iam").list_access_keys(UserName=user_name)
        keys = [
            {
                "access_key_id": k.get("AccessKeyId"),
                "status": k.get("Status"),
                "create_date": k.get("CreateDate"),
            }
            for k in resp.get("AccessKeyMetadata", [])
        ]
        return _ok({"user_name": user_name, "access_keys": keys})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_iam_access_key(
    user_name: str,
) -> str:
    """
    Create a new IAM access key for a user.

    IMPORTANT: Save the returned secret access key — AWS does not store it.

    Args:
        user_name: IAM user name. (required)

    Returns:
        JSON: access_key_id, secret_access_key, status, create_date.
    """
    if not user_name.strip():
        return _err("user_name is required.", "VALIDATION_ERROR")
    logger.info("aws_create_iam_access_key user=%s", user_name)
    try:
        resp = boto3.client("iam").create_access_key(UserName=user_name)
        k = resp.get("AccessKey", {})
        return _ok({
            "user_name": user_name,
            "access_key_id": k.get("AccessKeyId"),
            "secret_access_key": k.get("SecretAccessKey"),
            "status": k.get("Status"),
            "create_date": k.get("CreateDate"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_iam_access_key(
    user_name: str,
    access_key_id: str,
) -> str:
    """
    Delete an IAM access key for a user.

    Args:
        user_name:     IAM user name. (required)
        access_key_id: Access key ID to delete. (required)

    Returns:
        JSON: user_name, access_key_id, message.
    """
    if not user_name.strip() or not access_key_id.strip():
        return _err("user_name and access_key_id are required.", "VALIDATION_ERROR")
    logger.info("aws_delete_iam_access_key user=%s key=%s", user_name, access_key_id)
    try:
        boto3.client("iam").delete_access_key(UserName=user_name, AccessKeyId=access_key_id)
        return _ok({"user_name": user_name, "access_key_id": access_key_id, "message": "Access key deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
