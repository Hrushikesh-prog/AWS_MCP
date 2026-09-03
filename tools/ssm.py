from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


def _ssm(region: str):
    return boto3.client("ssm", region_name=region)


@mcp.tool()
def aws_get_ssm_parameter(
    name: str,
    with_decryption: bool = True,
    region: str = "us-east-1",
) -> str:
    """
    Get a single SSM Parameter Store parameter by name.

    Args:
        name:            Parameter name or full path (e.g. '/app/db/password'). (required)
        with_decryption: Decrypt SecureString values; default True.
        region:          AWS region (default 'us-east-1').

    Returns:
        JSON: name, type, value, version, last_modified, arn.
    """
    if not name:
        return _err("name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_ssm_parameter name=%s region=%s", name, region)
    try:
        r = _ssm(region).get_parameter(Name=name, WithDecryption=with_decryption)
        p = r["Parameter"]
        return _ok({
            "name": p.get("Name"),
            "type": p.get("Type"),
            "value": p.get("Value"),
            "version": p.get("Version"),
            "last_modified": p.get("LastModifiedDate"),
            "arn": p.get("ARN"),
            "data_type": p.get("DataType", "text"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_ssm_parameters_by_path(
    path: str,
    recursive: bool = True,
    with_decryption: bool = True,
    region: str = "us-east-1",
) -> str:
    """
    Get all SSM parameters under a path prefix.

    Args:
        path:            Parameter path prefix, e.g. '/myapp/prod/'. (required)
        recursive:       Include sub-paths; default True.
        with_decryption: Decrypt SecureString values; default True.
        region:          AWS region (default 'us-east-1').

    Returns:
        JSON: path, parameter_count, parameters (name, type, value, version).
    """
    if not path:
        return _err("path is required.", "VALIDATION_ERROR")
    logger.info("aws_get_ssm_parameters_by_path path=%s region=%s", path, region)
    try:
        paginator = _ssm(region).get_paginator("get_parameters_by_path")
        params: list[dict[str, Any]] = []
        for page in paginator.paginate(
            Path=path, Recursive=recursive, WithDecryption=with_decryption
        ):
            for p in page.get("Parameters", []):
                params.append({
                    "name": p.get("Name"),
                    "type": p.get("Type"),
                    "value": p.get("Value"),
                    "version": p.get("Version"),
                    "last_modified": p.get("LastModifiedDate"),
                })
        return _ok({"path": path, "parameter_count": len(params), "parameters": params})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_put_ssm_parameter(
    name: str,
    value: str,
    param_type: str = "String",
    description: str = "",
    overwrite: bool = False,
    region: str = "us-east-1",
) -> str:
    """
    Create or update an SSM Parameter Store parameter.

    Args:
        name:        Parameter name/path (e.g. '/app/api_key'). (required)
        value:       Parameter value. (required)
        param_type:  'String', 'StringList', or 'SecureString'; default 'String'.
        description: Human-readable description. (optional)
        overwrite:   Overwrite if the parameter already exists; default False.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: name, version, tier.
    """
    if not name or not value:
        return _err("name and value are required.", "VALIDATION_ERROR")
    valid_types = {"String", "StringList", "SecureString"}
    if param_type not in valid_types:
        return _err(f"param_type must be one of {valid_types}.", "VALIDATION_ERROR")
    logger.info("aws_put_ssm_parameter name=%s type=%s region=%s", name, param_type, region)
    try:
        kwargs: dict[str, Any] = {
            "Name": name, "Value": value, "Type": param_type, "Overwrite": overwrite,
        }
        if description:
            kwargs["Description"] = description
        r = _ssm(region).put_parameter(**kwargs)
        return _ok({"name": name, "version": r.get("Version"), "tier": r.get("Tier")})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_ssm_parameter(name: str, region: str = "us-east-1") -> str:
    """
    Delete an SSM Parameter Store parameter.

    Args:
        name:   Parameter name or path. (required)
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: status message.
    """
    if not name:
        return _err("name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_ssm_parameter name=%s region=%s", name, region)
    try:
        _ssm(region).delete_parameter(Name=name)
        return _ok({"message": f"Parameter '{name}' deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_ssm_parameters(
    filter_name: str = "",
    max_results: int = 50,
    region: str = "us-east-1",
) -> str:
    """
    List and describe SSM parameters, optionally filtered by name prefix.

    Args:
        filter_name: Name prefix to filter on (e.g. '/myapp/'). (optional)
        max_results: Max results per page; default 50, capped at 50.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: parameter_count, parameters (name, type, description, last_modified, version).
    """
    max_results = max(1, min(int(max_results), 50))
    logger.info("aws_describe_ssm_parameters filter=%r region=%s", filter_name, region)
    try:
        kwargs: dict[str, Any] = {"MaxResults": max_results}
        if filter_name:
            kwargs["Filters"] = [{"Key": "Name", "Option": "BeginsWith", "Values": [filter_name]}]
        paginator = _ssm(region).get_paginator("describe_parameters")
        params: list[dict[str, Any]] = []
        for page in paginator.paginate(**kwargs):
            for p in page.get("Parameters", []):
                params.append({
                    "name": p.get("Name"),
                    "type": p.get("Type"),
                    "description": p.get("Description", ""),
                    "last_modified": p.get("LastModifiedDate"),
                    "version": p.get("Version"),
                    "tier": p.get("Tier"),
                    "data_type": p.get("DataType", "text"),
                })
        return _ok({"parameter_count": len(params), "parameters": params})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_send_ssm_command(
    instance_ids: list[str],
    commands: list[str],
    comment: str = "",
    timeout_seconds: int = 60,
    region: str = "us-east-1",
) -> str:
    """
    Run shell commands on one or more EC2 instances via SSM Run Command.

    Args:
        instance_ids:     List of EC2 instance IDs (e.g. ['i-0abc123']). (required)
        commands:         List of shell commands to execute. (required)
        comment:          Human-readable comment for this command invocation. (optional)
        timeout_seconds:  Command timeout in seconds; default 60.
        region:           AWS region (default 'us-east-1').

    Returns:
        JSON: command_id, status, instance_ids, requested_at.
    """
    if not instance_ids or not commands:
        return _err("instance_ids and commands are required.", "VALIDATION_ERROR")
    logger.info("aws_send_ssm_command instances=%s region=%s", instance_ids, region)
    try:
        kwargs: dict[str, Any] = {
            "InstanceIds": instance_ids,
            "DocumentName": "AWS-RunShellScript",
            "Parameters": {"commands": commands},
            "TimeoutSeconds": timeout_seconds,
        }
        if comment:
            kwargs["Comment"] = comment
        r = _ssm(region).send_command(**kwargs)
        cmd = r["Command"]
        return _ok({
            "command_id": cmd.get("CommandId"),
            "status": cmd.get("Status"),
            "instance_ids": cmd.get("InstanceIds"),
            "requested_at": cmd.get("RequestedDateTime"),
            "comment": cmd.get("Comment", ""),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_ssm_command_invocation(
    command_id: str,
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Get the output and status of an SSM Run Command invocation.

    Args:
        command_id:  Command ID returned by aws_send_ssm_command. (required)
        instance_id: EC2 instance ID the command ran on. (required)
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: status, stdout, stderr, exit_code, execution_elapsed_ms.
    """
    if not command_id or not instance_id:
        return _err("command_id and instance_id are required.", "VALIDATION_ERROR")
    logger.info("aws_get_ssm_command_invocation cmd=%s instance=%s region=%s", command_id, instance_id, region)
    try:
        r = _ssm(region).get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        return _ok({
            "command_id": r.get("CommandId"),
            "instance_id": r.get("InstanceId"),
            "status": r.get("Status"),
            "status_detail": r.get("StatusDetails"),
            "stdout": r.get("StandardOutputContent", ""),
            "stderr": r.get("StandardErrorContent", ""),
            "exit_code": r.get("ResponseCode"),
            "execution_start": r.get("ExecutionStartDateTime"),
            "execution_end": r.get("ExecutionEndDateTime"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_ssm_commands(
    instance_id: str = "",
    max_results: int = 20,
    region: str = "us-east-1",
) -> str:
    """
    List recent SSM Run Command invocations.

    Args:
        instance_id: Filter to commands run on this instance (optional).
        max_results: Max results; default 20, capped at 50.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: command_count, commands (command_id, status, instance_ids, requested_at, comment).
    """
    max_results = max(1, min(int(max_results), 50))
    logger.info("aws_list_ssm_commands instance=%r region=%s", instance_id, region)
    try:
        kwargs: dict[str, Any] = {"MaxResults": max_results}
        if instance_id:
            kwargs["Filters"] = [{"key": "InstanceId", "value": instance_id}]
        r = _ssm(region).list_commands(**kwargs)
        commands = [
            {
                "command_id": c.get("CommandId"),
                "document_name": c.get("DocumentName"),
                "status": c.get("Status"),
                "instance_ids": c.get("InstanceIds", []),
                "requested_at": c.get("RequestedDateTime"),
                "comment": c.get("Comment", ""),
            }
            for c in r.get("Commands", [])
        ]
        return _ok({"command_count": len(commands), "commands": commands})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_ssm_managed_instances(
    region: str = "us-east-1",
    max_results: int = 50,
) -> str:
    """
    List EC2 instances and on-premises servers registered with SSM.

    Args:
        region:      AWS region (default 'us-east-1').
        max_results: Max results; default 50, capped at 50.

    Returns:
        JSON: instance_count, instances (id, name, ping_status, platform, agent_version, ip).
    """
    max_results = max(1, min(int(max_results), 50))
    logger.info("aws_list_ssm_managed_instances region=%s", region)
    try:
        paginator = _ssm(region).get_paginator("describe_instance_information")
        instances: list[dict[str, Any]] = []
        for page in paginator.paginate(MaxResults=max_results):
            for i in page.get("InstanceInformationList", []):
                instances.append({
                    "instance_id": i.get("InstanceId"),
                    "ping_status": i.get("PingStatus"),
                    "last_ping": i.get("LastPingDateTime"),
                    "agent_version": i.get("AgentVersion"),
                    "platform_type": i.get("PlatformType"),
                    "platform_name": i.get("PlatformName"),
                    "ip_address": i.get("IPAddress"),
                    "computer_name": i.get("ComputerName"),
                    "resource_type": i.get("ResourceType"),
                })
        return _ok({"instance_count": len(instances), "instances": instances})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
