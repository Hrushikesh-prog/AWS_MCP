from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_list_lambda_functions(
    region: str = "us-east-1",
) -> str:
    """
    List all Lambda functions in an AWS region.

    Args:
        region: AWS region to query (default 'us-east-1').

    Returns:
        JSON: region, function_count, functions
              (each: name, runtime, handler, memory_mb, timeout_secs,
               last_modified, description).
    """
    logger.info("aws_list_lambda_functions region=%s", region)
    try:
        paginator = boto3.client("lambda", region_name=region).get_paginator("list_functions")
        functions: list[dict[str, Any]] = []
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                functions.append({
                    "name": fn.get("FunctionName"),
                    "runtime": fn.get("Runtime"),
                    "handler": fn.get("Handler"),
                    "memory_mb": fn.get("MemorySize"),
                    "timeout_secs": fn.get("Timeout"),
                    "last_modified": fn.get("LastModified"),
                    "description": fn.get("Description", ""),
                })
        return _ok({"region": region, "function_count": len(functions), "functions": functions})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_lambda_function(function_name: str, region: str = "us-east-1") -> str:
    """
    Get detailed configuration and code location for a Lambda function.

    Args:
        function_name: Function name or ARN. (required)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: name, arn, runtime, handler, memory_mb, timeout_secs, env_vars,
              role, vpc_config, last_modified, code_size, code_location.
    """
    if not function_name:
        return _err("function_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_lambda_function name=%s region=%s", function_name, region)
    try:
        r = boto3.client("lambda", region_name=region).get_function(FunctionName=function_name)
        c = r.get("Configuration", {})
        return _ok({
            "name": c.get("FunctionName"),
            "arn": c.get("FunctionArn"),
            "runtime": c.get("Runtime"),
            "handler": c.get("Handler"),
            "description": c.get("Description", ""),
            "memory_mb": c.get("MemorySize"),
            "timeout_secs": c.get("Timeout"),
            "role": c.get("Role"),
            "last_modified": c.get("LastModified"),
            "code_size": c.get("CodeSize"),
            "env_vars": c.get("Environment", {}).get("Variables", {}),
            "vpc_config": c.get("VpcConfig"),
            "architectures": c.get("Architectures", []),
            "state": c.get("State"),
            "state_reason": c.get("StateReason", ""),
            "code_location": r.get("Code", {}).get("Location"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_invoke_lambda(
    function_name: str,
    payload: str = "{}",
    invocation_type: str = "RequestResponse",
    region: str = "us-east-1",
) -> str:
    """
    Invoke a Lambda function and return its response.

    Args:
        function_name:    Function name or ARN. (required)
        payload:          JSON string payload; default '{}'.
        invocation_type:  'RequestResponse' (sync), 'Event' (async), or 'DryRun'.
                          Default 'RequestResponse'.
        region:           AWS region (default 'us-east-1').

    Returns:
        JSON: status_code, response_payload, executed_version, log_tail.
    """
    if not function_name:
        return _err("function_name is required.", "VALIDATION_ERROR")
    import json as _json
    logger.info("aws_invoke_lambda name=%s type=%s region=%s", function_name, invocation_type, region)
    try:
        r = boto3.client("lambda", region_name=region).invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            Payload=payload.encode("utf-8"),
            LogType="Tail" if invocation_type == "RequestResponse" else "None",
        )
        response_payload = ""
        if "Payload" in r:
            response_payload = r["Payload"].read().decode("utf-8")
        log_tail = ""
        if "LogResult" in r:
            import base64
            log_tail = base64.b64decode(r["LogResult"]).decode("utf-8")
        return _ok({
            "status_code": r.get("StatusCode"),
            "executed_version": r.get("ExecutedVersion"),
            "function_error": r.get("FunctionError", ""),
            "response_payload": response_payload,
            "log_tail": log_tail,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_lambda_function(function_name: str, region: str = "us-east-1") -> str:
    """
    Delete a Lambda function and all its versions and aliases.

    Args:
        function_name: Function name or ARN. (required)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: status message.
    """
    if not function_name:
        return _err("function_name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_lambda_function name=%s region=%s", function_name, region)
    try:
        boto3.client("lambda", region_name=region).delete_function(FunctionName=function_name)
        return _ok({"message": f"Lambda function '{function_name}' deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_update_lambda_env_vars(
    function_name: str,
    variables: dict[str, str],
    region: str = "us-east-1",
) -> str:
    """
    Update (replace) the environment variables on a Lambda function.

    Args:
        function_name: Function name or ARN. (required)
        variables:     Dict of environment variable key-value pairs. (required)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: name, env_vars, last_modified.
    """
    if not function_name or variables is None:
        return _err("function_name and variables are required.", "VALIDATION_ERROR")
    logger.info("aws_update_lambda_env_vars name=%s region=%s", function_name, region)
    try:
        r = boto3.client("lambda", region_name=region).update_function_configuration(
            FunctionName=function_name,
            Environment={"Variables": variables},
        )
        return _ok({
            "name": r.get("FunctionName"),
            "env_vars": r.get("Environment", {}).get("Variables", {}),
            "last_modified": r.get("LastModified"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_update_lambda_config(
    function_name: str,
    memory_mb: int | None = None,
    timeout_secs: int | None = None,
    description: str = "",
    handler: str = "",
    region: str = "us-east-1",
) -> str:
    """
    Update the configuration of a Lambda function (memory, timeout, description, handler).

    Args:
        function_name: Function name or ARN. (required)
        memory_mb:     New memory allocation in MB (128–10240). (optional)
        timeout_secs:  New timeout in seconds (1–900). (optional)
        description:   New description string. (optional)
        handler:       New handler string, e.g. 'index.handler'. (optional)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: name, memory_mb, timeout_secs, description, handler, last_modified.
    """
    if not function_name:
        return _err("function_name is required.", "VALIDATION_ERROR")
    logger.info("aws_update_lambda_config name=%s region=%s", function_name, region)
    try:
        kwargs: dict = {"FunctionName": function_name}
        if memory_mb is not None:
            kwargs["MemorySize"] = max(128, min(int(memory_mb), 10240))
        if timeout_secs is not None:
            kwargs["Timeout"] = max(1, min(int(timeout_secs), 900))
        if description:
            kwargs["Description"] = description
        if handler:
            kwargs["Handler"] = handler
        if len(kwargs) == 1:
            return _err("Provide at least one parameter to update.", "VALIDATION_ERROR")
        r = boto3.client("lambda", region_name=region).update_function_configuration(**kwargs)
        return _ok({
            "name": r.get("FunctionName"),
            "memory_mb": r.get("MemorySize"),
            "timeout_secs": r.get("Timeout"),
            "description": r.get("Description", ""),
            "handler": r.get("Handler"),
            "last_modified": r.get("LastModified"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_lambda_aliases(function_name: str, region: str = "us-east-1") -> str:
    """
    List all aliases for a Lambda function.

    Args:
        function_name: Function name or ARN. (required)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: function_name, alias_count, aliases (name, arn, function_version, description).
    """
    if not function_name:
        return _err("function_name is required.", "VALIDATION_ERROR")
    logger.info("aws_list_lambda_aliases name=%s region=%s", function_name, region)
    try:
        paginator = boto3.client("lambda", region_name=region).get_paginator("list_aliases")
        aliases = []
        for page in paginator.paginate(FunctionName=function_name):
            for a in page.get("Aliases", []):
                aliases.append({
                    "name": a.get("Name"),
                    "arn": a.get("AliasArn"),
                    "function_version": a.get("FunctionVersion"),
                    "description": a.get("Description", ""),
                })
        return _ok({"function_name": function_name, "alias_count": len(aliases), "aliases": aliases})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_lambda_policy(function_name: str, region: str = "us-east-1") -> str:
    """
    Get the resource-based policy (permissions) attached to a Lambda function.

    Args:
        function_name: Function name or ARN. (required)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: function_name, policy (raw JSON string).
    """
    if not function_name:
        return _err("function_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_lambda_policy name=%s region=%s", function_name, region)
    try:
        r = boto3.client("lambda", region_name=region).get_policy(FunctionName=function_name)
        return _ok({"function_name": function_name, "policy": r.get("Policy"), "revision_id": r.get("RevisionId")})
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ResourceNotFoundException":
            return _ok({"function_name": function_name, "policy": None, "message": "No resource policy attached."})
        return _err(str(e), code)
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_lambda_event_source_mappings(
    function_name: str,
    region: str = "us-east-1",
) -> str:
    """
    List event source mappings (SQS, DynamoDB Streams, Kinesis) for a Lambda function.

    Args:
        function_name: Function name or ARN. (required)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: function_name, mapping_count, mappings (uuid, source_arn, state, batch_size).
    """
    if not function_name:
        return _err("function_name is required.", "VALIDATION_ERROR")
    logger.info("aws_list_lambda_event_source_mappings name=%s region=%s", function_name, region)
    try:
        paginator = boto3.client("lambda", region_name=region).get_paginator("list_event_source_mappings")
        mappings = []
        for page in paginator.paginate(FunctionName=function_name):
            for m in page.get("EventSourceMappings", []):
                mappings.append({
                    "uuid": m.get("UUID"),
                    "source_arn": m.get("EventSourceArn"),
                    "state": m.get("State"),
                    "batch_size": m.get("BatchSize"),
                    "last_modified": m.get("LastModified"),
                    "function_arn": m.get("FunctionArn"),
                })
        return _ok({"function_name": function_name, "mapping_count": len(mappings), "mappings": mappings})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_lambda_layers(region: str = "us-east-1") -> str:
    """
    List all Lambda layers available in a region.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: layer_count, layers (name, arn, latest_version, description, runtimes).
    """
    logger.info("aws_list_lambda_layers region=%s", region)
    try:
        paginator = boto3.client("lambda", region_name=region).get_paginator("list_layers")
        layers = []
        for page in paginator.paginate():
            for l in page.get("Layers", []):
                lv = l.get("LatestMatchingVersion", {})
                layers.append({
                    "name": l.get("LayerName"),
                    "arn": l.get("LayerArn"),
                    "latest_version": lv.get("Version"),
                    "latest_arn": lv.get("LayerVersionArn"),
                    "description": lv.get("Description", ""),
                    "compatible_runtimes": lv.get("CompatibleRuntimes", []),
                })
        return _ok({"region": region, "layer_count": len(layers), "layers": layers})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
