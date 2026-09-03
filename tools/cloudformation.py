from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


def _cf(region: str):
    return boto3.client("cloudformation", region_name=region)


@mcp.tool()
def aws_list_cf_stacks(
    status_filter: list[str] | None = None,
    region: str = "us-east-1",
) -> str:
    """
    List CloudFormation stacks, optionally filtered by status.

    Args:
        status_filter: List of stack statuses to include, e.g.
                       ['CREATE_COMPLETE', 'UPDATE_COMPLETE'].
                       Defaults to all active stacks (excludes DELETE_COMPLETE).
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: stack_count, stacks (name, id, status, description, created, updated).
    """
    default_statuses = [
        "CREATE_IN_PROGRESS", "CREATE_FAILED", "CREATE_COMPLETE",
        "ROLLBACK_IN_PROGRESS", "ROLLBACK_FAILED", "ROLLBACK_COMPLETE",
        "UPDATE_IN_PROGRESS", "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS", "UPDATE_COMPLETE",
        "UPDATE_FAILED", "UPDATE_ROLLBACK_IN_PROGRESS", "UPDATE_ROLLBACK_FAILED",
        "UPDATE_ROLLBACK_COMPLETE", "REVIEW_IN_PROGRESS", "IMPORT_IN_PROGRESS",
        "IMPORT_COMPLETE", "IMPORT_ROLLBACK_IN_PROGRESS", "IMPORT_ROLLBACK_FAILED",
        "IMPORT_ROLLBACK_COMPLETE",
    ]
    statuses = status_filter if status_filter else default_statuses
    logger.info("aws_list_cf_stacks statuses=%s region=%s", statuses, region)
    try:
        paginator = _cf(region).get_paginator("list_stacks")
        stacks: list[dict[str, Any]] = []
        for page in paginator.paginate(StackStatusFilter=statuses):
            for s in page.get("StackSummaries", []):
                stacks.append({
                    "name": s.get("StackName"),
                    "id": s.get("StackId"),
                    "status": s.get("StackStatus"),
                    "status_reason": s.get("StackStatusReason", ""),
                    "description": s.get("TemplateDescription", ""),
                    "created": s.get("CreationTime"),
                    "updated": s.get("LastUpdatedTime"),
                })
        return _ok({"stack_count": len(stacks), "stacks": stacks})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_cf_stack(stack_name: str, region: str = "us-east-1") -> str:
    """
    Describe a CloudFormation stack including outputs and parameters.

    Args:
        stack_name: Stack name or ARN. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: name, status, description, parameters, outputs, capabilities, tags.
    """
    if not stack_name:
        return _err("stack_name is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_cf_stack stack=%s region=%s", stack_name, region)
    try:
        r = _cf(region).describe_stacks(StackName=stack_name)
        s = r["Stacks"][0]
        return _ok({
            "name": s.get("StackName"),
            "id": s.get("StackId"),
            "status": s.get("StackStatus"),
            "status_reason": s.get("StackStatusReason", ""),
            "description": s.get("Description", ""),
            "created": s.get("CreationTime"),
            "updated": s.get("LastUpdatedTime"),
            "capabilities": s.get("Capabilities", []),
            "parameters": [
                {"key": p["ParameterKey"], "value": p.get("ParameterValue", "")}
                for p in s.get("Parameters", [])
            ],
            "outputs": [
                {"key": o["OutputKey"], "value": o.get("OutputValue", ""), "description": o.get("Description", "")}
                for o in s.get("Outputs", [])
            ],
            "tags": {t["Key"]: t["Value"] for t in s.get("Tags", [])},
            "role_arn": s.get("RoleARN"),
            "notification_arns": s.get("NotificationARNs", []),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_cf_stack_events(
    stack_name: str,
    max_events: int = 20,
    region: str = "us-east-1",
) -> str:
    """
    Get recent events for a CloudFormation stack (useful for debugging).

    Args:
        stack_name: Stack name or ARN. (required)
        max_events: Max events to return; default 20.
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: stack_name, event_count, events (timestamp, resource, status, reason).
    """
    if not stack_name:
        return _err("stack_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_cf_stack_events stack=%s region=%s", stack_name, region)
    try:
        paginator = _cf(region).get_paginator("describe_stack_events")
        events: list[dict[str, Any]] = []
        for page in paginator.paginate(StackName=stack_name):
            for e in page.get("StackEvents", []):
                events.append({
                    "timestamp": e.get("Timestamp"),
                    "resource_id": e.get("LogicalResourceId"),
                    "resource_type": e.get("ResourceType"),
                    "status": e.get("ResourceStatus"),
                    "reason": e.get("ResourceStatusReason", ""),
                })
            if len(events) >= max_events:
                events = events[:max_events]
                break
        return _ok({"stack_name": stack_name, "event_count": len(events), "events": events})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_cf_stack_resources(stack_name: str, region: str = "us-east-1") -> str:
    """
    List all resources in a CloudFormation stack.

    Args:
        stack_name: Stack name or ARN. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: stack_name, resource_count, resources (logical_id, physical_id, type, status).
    """
    if not stack_name:
        return _err("stack_name is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_cf_stack_resources stack=%s region=%s", stack_name, region)
    try:
        paginator = _cf(region).get_paginator("list_stack_resources")
        resources: list[dict[str, Any]] = []
        for page in paginator.paginate(StackName=stack_name):
            for r in page.get("StackResourceSummaries", []):
                resources.append({
                    "logical_id": r.get("LogicalResourceId"),
                    "physical_id": r.get("PhysicalResourceId", ""),
                    "type": r.get("ResourceType"),
                    "status": r.get("ResourceStatus"),
                    "status_reason": r.get("ResourceStatusReason", ""),
                    "last_updated": r.get("LastUpdatedTimestamp"),
                })
        return _ok({"stack_name": stack_name, "resource_count": len(resources), "resources": resources})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_cf_stack(
    stack_name: str,
    template_body: str,
    parameters: list[dict[str, str]] | None = None,
    capabilities: list[str] | None = None,
    region: str = "us-east-1",
) -> str:
    """
    Create a new CloudFormation stack.

    Args:
        stack_name:   Unique stack name. (required)
        template_body: CloudFormation template as a YAML or JSON string. (required)
        parameters:   List of {'ParameterKey': ..., 'ParameterValue': ...} dicts. (optional)
        capabilities: List of required capabilities, e.g. ['CAPABILITY_IAM',
                      'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND']. (optional)
        region:       AWS region (default 'us-east-1').

    Returns:
        JSON: stack_id.
    """
    if not stack_name or not template_body:
        return _err("stack_name and template_body are required.", "VALIDATION_ERROR")
    logger.info("aws_create_cf_stack stack=%s region=%s", stack_name, region)
    try:
        kwargs: dict[str, Any] = {"StackName": stack_name, "TemplateBody": template_body}
        if parameters:
            kwargs["Parameters"] = parameters
        if capabilities:
            kwargs["Capabilities"] = capabilities
        r = _cf(region).create_stack(**kwargs)
        return _ok({"stack_id": r.get("StackId"), "stack_name": stack_name, "status": "CREATE_IN_PROGRESS"})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_update_cf_stack(
    stack_name: str,
    template_body: str,
    parameters: list[dict[str, str]] | None = None,
    capabilities: list[str] | None = None,
    region: str = "us-east-1",
) -> str:
    """
    Update an existing CloudFormation stack with a new template.

    Args:
        stack_name:    Stack name or ARN. (required)
        template_body: Updated CloudFormation template (YAML or JSON). (required)
        parameters:    List of {'ParameterKey': ..., 'ParameterValue': ...}. (optional)
        capabilities:  e.g. ['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']. (optional)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: stack_id.
    """
    if not stack_name or not template_body:
        return _err("stack_name and template_body are required.", "VALIDATION_ERROR")
    logger.info("aws_update_cf_stack stack=%s region=%s", stack_name, region)
    try:
        kwargs: dict[str, Any] = {"StackName": stack_name, "TemplateBody": template_body}
        if parameters:
            kwargs["Parameters"] = parameters
        if capabilities:
            kwargs["Capabilities"] = capabilities
        r = _cf(region).update_stack(**kwargs)
        return _ok({"stack_id": r.get("StackId"), "stack_name": stack_name, "status": "UPDATE_IN_PROGRESS"})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_cf_stack(stack_name: str, region: str = "us-east-1") -> str:
    """
    Delete a CloudFormation stack and all its resources.

    Args:
        stack_name: Stack name or ARN. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: status message.
    """
    if not stack_name:
        return _err("stack_name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_cf_stack stack=%s region=%s", stack_name, region)
    try:
        _cf(region).delete_stack(StackName=stack_name)
        return _ok({"message": f"Stack '{stack_name}' deletion initiated.", "status": "DELETE_IN_PROGRESS"})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_validate_cf_template(template_body: str, region: str = "us-east-1") -> str:
    """
    Validate a CloudFormation template for syntax errors before deploying.

    Args:
        template_body: YAML or JSON CloudFormation template. (required)
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: parameters, capabilities, description (if valid).
    """
    if not template_body:
        return _err("template_body is required.", "VALIDATION_ERROR")
    logger.info("aws_validate_cf_template region=%s", region)
    try:
        r = _cf(region).validate_template(TemplateBody=template_body)
        return _ok({
            "valid": True,
            "description": r.get("Description", ""),
            "parameters": [
                {
                    "key": p.get("ParameterKey"),
                    "default": p.get("DefaultValue", ""),
                    "no_echo": p.get("NoEcho", False),
                    "description": p.get("Description", ""),
                }
                for p in r.get("Parameters", [])
            ],
            "capabilities": r.get("Capabilities", []),
            "capabilities_reason": r.get("CapabilitiesReason", ""),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_cf_stack_template(stack_name: str, region: str = "us-east-1") -> str:
    """
    Retrieve the current template body of a deployed CloudFormation stack.

    Args:
        stack_name: Stack name or ARN. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: stack_name, template_body.
    """
    if not stack_name:
        return _err("stack_name is required.", "VALIDATION_ERROR")
    logger.info("aws_get_cf_stack_template stack=%s region=%s", stack_name, region)
    try:
        r = _cf(region).get_template(StackName=stack_name)
        return _ok({"stack_name": stack_name, "template_body": r.get("TemplateBody", "")})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_detect_cf_stack_drift(stack_name: str, region: str = "us-east-1") -> str:
    """
    Initiate a drift detection operation on a CloudFormation stack.

    Args:
        stack_name: Stack name or ARN. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: drift_detection_id, stack_name.
    """
    if not stack_name:
        return _err("stack_name is required.", "VALIDATION_ERROR")
    logger.info("aws_detect_cf_stack_drift stack=%s region=%s", stack_name, region)
    try:
        r = _cf(region).detect_stack_drift(StackName=stack_name)
        return _ok({
            "drift_detection_id": r.get("StackDriftDetectionId"),
            "stack_name": stack_name,
            "message": "Drift detection started. Poll aws_describe_cf_stack for DriftInformation.",
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
