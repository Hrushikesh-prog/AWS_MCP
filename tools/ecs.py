from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


def _ecs(region: str):
    return boto3.client("ecs", region_name=region)


@mcp.tool()
def aws_list_ecs_clusters(region: str = "us-east-1") -> str:
    """
    List all ECS clusters in a region.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: cluster_count, cluster_arns.
    """
    logger.info("aws_list_ecs_clusters region=%s", region)
    try:
        paginator = _ecs(region).get_paginator("list_clusters")
        arns: list[str] = []
        for page in paginator.paginate():
            arns.extend(page.get("clusterArns", []))
        return _ok({"cluster_count": len(arns), "cluster_arns": arns})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_ecs_cluster(cluster: str, region: str = "us-east-1") -> str:
    """
    Describe an ECS cluster in detail.

    Args:
        cluster: Cluster name or ARN. (required)
        region:  AWS region (default 'us-east-1').

    Returns:
        JSON: name, status, running_tasks, pending_tasks, active_services,
              registered_instances, capacity_providers.
    """
    if not cluster:
        return _err("cluster is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_ecs_cluster cluster=%s region=%s", cluster, region)
    try:
        r = _ecs(region).describe_clusters(clusters=[cluster], include=["STATISTICS", "TAGS"])
        if not r.get("clusters"):
            return _err(f"Cluster '{cluster}' not found.", "NOT_FOUND")
        c = r["clusters"][0]
        return _ok({
            "name": c.get("clusterName"),
            "arn": c.get("clusterArn"),
            "status": c.get("status"),
            "running_tasks": c.get("runningTasksCount"),
            "pending_tasks": c.get("pendingTasksCount"),
            "active_services": c.get("activeServicesCount"),
            "registered_instances": c.get("registeredContainerInstancesCount"),
            "capacity_providers": c.get("capacityProviders", []),
            "tags": {t["key"]: t["value"] for t in c.get("tags", [])},
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_ecs_services(cluster: str, region: str = "us-east-1") -> str:
    """
    List all services in an ECS cluster.

    Args:
        cluster: Cluster name or ARN. (required)
        region:  AWS region (default 'us-east-1').

    Returns:
        JSON: cluster, service_count, service_arns.
    """
    if not cluster:
        return _err("cluster is required.", "VALIDATION_ERROR")
    logger.info("aws_list_ecs_services cluster=%s region=%s", cluster, region)
    try:
        paginator = _ecs(region).get_paginator("list_services")
        arns: list[str] = []
        for page in paginator.paginate(cluster=cluster):
            arns.extend(page.get("serviceArns", []))
        return _ok({"cluster": cluster, "service_count": len(arns), "service_arns": arns})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_ecs_service(
    cluster: str,
    service: str,
    region: str = "us-east-1",
) -> str:
    """
    Describe an ECS service including its deployments and health.

    Args:
        cluster: Cluster name or ARN. (required)
        service: Service name or ARN. (required)
        region:  AWS region (default 'us-east-1').

    Returns:
        JSON: name, status, desired/running/pending counts, task_definition,
              load_balancers, deployment info.
    """
    if not cluster or not service:
        return _err("cluster and service are required.", "VALIDATION_ERROR")
    logger.info("aws_describe_ecs_service cluster=%s service=%s region=%s", cluster, service, region)
    try:
        r = _ecs(region).describe_services(cluster=cluster, services=[service])
        if not r.get("services"):
            return _err(f"Service '{service}' not found in cluster '{cluster}'.", "NOT_FOUND")
        s = r["services"][0]
        return _ok({
            "name": s.get("serviceName"),
            "arn": s.get("serviceArn"),
            "cluster": s.get("clusterArn"),
            "status": s.get("status"),
            "desired_count": s.get("desiredCount"),
            "running_count": s.get("runningCount"),
            "pending_count": s.get("pendingCount"),
            "task_definition": s.get("taskDefinition"),
            "launch_type": s.get("launchType"),
            "platform_version": s.get("platformVersion"),
            "load_balancers": s.get("loadBalancers", []),
            "deployments": [
                {
                    "id": d.get("id"),
                    "status": d.get("status"),
                    "task_definition": d.get("taskDefinition"),
                    "desired": d.get("desiredCount"),
                    "running": d.get("runningCount"),
                    "pending": d.get("pendingCount"),
                    "created": d.get("createdAt"),
                    "updated": d.get("updatedAt"),
                }
                for d in s.get("deployments", [])
            ],
            "created_at": s.get("createdAt"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_ecs_tasks(
    cluster: str,
    service: str = "",
    desired_status: str = "RUNNING",
    region: str = "us-east-1",
) -> str:
    """
    List tasks in an ECS cluster, optionally scoped to a service.

    Args:
        cluster:        Cluster name or ARN. (required)
        service:        Filter by service name or ARN. (optional)
        desired_status: 'RUNNING', 'PENDING', or 'STOPPED'; default 'RUNNING'.
        region:         AWS region (default 'us-east-1').

    Returns:
        JSON: cluster, service, task_count, task_arns.
    """
    if not cluster:
        return _err("cluster is required.", "VALIDATION_ERROR")
    valid_statuses = {"RUNNING", "PENDING", "STOPPED"}
    if desired_status not in valid_statuses:
        return _err(f"desired_status must be one of {valid_statuses}.", "VALIDATION_ERROR")
    logger.info("aws_list_ecs_tasks cluster=%s service=%r status=%s region=%s", cluster, service, desired_status, region)
    try:
        kwargs: dict[str, Any] = {"cluster": cluster, "desiredStatus": desired_status}
        if service:
            kwargs["serviceName"] = service
        paginator = _ecs(region).get_paginator("list_tasks")
        arns: list[str] = []
        for page in paginator.paginate(**kwargs):
            arns.extend(page.get("taskArns", []))
        return _ok({"cluster": cluster, "service": service, "task_count": len(arns), "task_arns": arns})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_ecs_tasks(
    cluster: str,
    task_arns: list[str],
    region: str = "us-east-1",
) -> str:
    """
    Describe ECS tasks in detail (up to 100 at once).

    Args:
        cluster:   Cluster name or ARN. (required)
        task_arns: List of task ARNs or IDs to describe. (required)
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: task_count, tasks (id, status, task_definition, containers, started_at, cpu, memory).
    """
    if not cluster or not task_arns:
        return _err("cluster and task_arns are required.", "VALIDATION_ERROR")
    task_arns = task_arns[:100]
    logger.info("aws_describe_ecs_tasks cluster=%s tasks=%d region=%s", cluster, len(task_arns), region)
    try:
        r = _ecs(region).describe_tasks(cluster=cluster, tasks=task_arns)
        tasks = [
            {
                "task_arn": t.get("taskArn"),
                "task_definition": t.get("taskDefinitionArn"),
                "last_status": t.get("lastStatus"),
                "desired_status": t.get("desiredStatus"),
                "cpu": t.get("cpu"),
                "memory": t.get("memory"),
                "launch_type": t.get("launchType"),
                "started_at": t.get("startedAt"),
                "stopped_at": t.get("stoppedAt"),
                "stopped_reason": t.get("stoppedReason", ""),
                "containers": [
                    {
                        "name": c.get("name"),
                        "image": c.get("image"),
                        "last_status": c.get("lastStatus"),
                        "exit_code": c.get("exitCode"),
                        "reason": c.get("reason", ""),
                    }
                    for c in t.get("containers", [])
                ],
            }
            for t in r.get("tasks", [])
        ]
        return _ok({"task_count": len(tasks), "tasks": tasks})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_run_ecs_task(
    cluster: str,
    task_definition: str,
    count: int = 1,
    launch_type: str = "FARGATE",
    subnet_ids: list[str] | None = None,
    security_group_ids: list[str] | None = None,
    assign_public_ip: bool = True,
    region: str = "us-east-1",
) -> str:
    """
    Run (launch) a new ECS task.

    Args:
        cluster:           Cluster name or ARN. (required)
        task_definition:   Task definition name:revision or ARN. (required)
        count:             Number of task instances to launch; default 1.
        launch_type:       'FARGATE' or 'EC2'; default 'FARGATE'.
        subnet_ids:        List of subnet IDs for Fargate networking. (optional)
        security_group_ids: List of security group IDs. (optional)
        assign_public_ip:  Assign a public IP for Fargate tasks; default True.
        region:            AWS region (default 'us-east-1').

    Returns:
        JSON: task_arns, failures.
    """
    if not cluster or not task_definition:
        return _err("cluster and task_definition are required.", "VALIDATION_ERROR")
    logger.info("aws_run_ecs_task cluster=%s taskdef=%s count=%d region=%s", cluster, task_definition, count, region)
    try:
        kwargs: dict[str, Any] = {
            "cluster": cluster,
            "taskDefinition": task_definition,
            "count": max(1, count),
            "launchType": launch_type,
        }
        if launch_type == "FARGATE" and (subnet_ids or security_group_ids):
            network_config: dict[str, Any] = {"awsvpcConfiguration": {
                "assignPublicIp": "ENABLED" if assign_public_ip else "DISABLED",
            }}
            if subnet_ids:
                network_config["awsvpcConfiguration"]["subnets"] = subnet_ids
            if security_group_ids:
                network_config["awsvpcConfiguration"]["securityGroups"] = security_group_ids
            kwargs["networkConfiguration"] = network_config
        r = _ecs(region).run_task(**kwargs)
        return _ok({
            "task_arns": [t.get("taskArn") for t in r.get("tasks", [])],
            "failures": r.get("failures", []),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_stop_ecs_task(
    cluster: str,
    task: str,
    reason: str = "Stopped by AWS MCP",
    region: str = "us-east-1",
) -> str:
    """
    Stop a running ECS task.

    Args:
        cluster: Cluster name or ARN. (required)
        task:    Task ARN or ID. (required)
        reason:  Human-readable reason for stopping. (optional)
        region:  AWS region (default 'us-east-1').

    Returns:
        JSON: task_arn, last_status, desired_status.
    """
    if not cluster or not task:
        return _err("cluster and task are required.", "VALIDATION_ERROR")
    logger.info("aws_stop_ecs_task cluster=%s task=%s region=%s", cluster, task, region)
    try:
        r = _ecs(region).stop_task(cluster=cluster, task=task, reason=reason)
        t = r.get("task", {})
        return _ok({
            "task_arn": t.get("taskArn"),
            "last_status": t.get("lastStatus"),
            "desired_status": t.get("desiredStatus"),
            "stopped_reason": t.get("stoppedReason", ""),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_update_ecs_service(
    cluster: str,
    service: str,
    desired_count: int | None = None,
    task_definition: str = "",
    force_new_deployment: bool = False,
    region: str = "us-east-1",
) -> str:
    """
    Update an ECS service (scale tasks, deploy new task definition, or force redeployment).

    Args:
        cluster:             Cluster name or ARN. (required)
        service:             Service name or ARN. (required)
        desired_count:       New desired task count (omit to leave unchanged). (optional)
        task_definition:     New task definition name:revision or ARN (omit to leave unchanged). (optional)
        force_new_deployment: Force a redeployment even if nothing changed; default False.
        region:              AWS region (default 'us-east-1').

    Returns:
        JSON: service name, status, desired_count, deployments.
    """
    if not cluster or not service:
        return _err("cluster and service are required.", "VALIDATION_ERROR")
    logger.info("aws_update_ecs_service cluster=%s service=%s region=%s", cluster, service, region)
    try:
        kwargs: dict[str, Any] = {
            "cluster": cluster,
            "service": service,
            "forceNewDeployment": force_new_deployment,
        }
        if desired_count is not None:
            kwargs["desiredCount"] = desired_count
        if task_definition:
            kwargs["taskDefinition"] = task_definition
        r = _ecs(region).update_service(**kwargs)
        s = r.get("service", {})
        return _ok({
            "name": s.get("serviceName"),
            "status": s.get("status"),
            "desired_count": s.get("desiredCount"),
            "running_count": s.get("runningCount"),
            "pending_count": s.get("pendingCount"),
            "task_definition": s.get("taskDefinition"),
            "deployments": len(s.get("deployments", [])),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_ecs_task_definitions(
    family_prefix: str = "",
    status: str = "ACTIVE",
    region: str = "us-east-1",
) -> str:
    """
    List ECS task definitions, optionally filtered by family prefix.

    Args:
        family_prefix: Filter by task definition family prefix. (optional)
        status:        'ACTIVE' or 'INACTIVE'; default 'ACTIVE'.
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: task_definition_count, task_definition_arns.
    """
    logger.info("aws_list_ecs_task_definitions family=%r status=%s region=%s", family_prefix, status, region)
    try:
        kwargs: dict[str, Any] = {"status": status}
        if family_prefix:
            kwargs["familyPrefix"] = family_prefix
        paginator = _ecs(region).get_paginator("list_task_definitions")
        arns: list[str] = []
        for page in paginator.paginate(**kwargs):
            arns.extend(page.get("taskDefinitionArns", []))
        return _ok({"task_definition_count": len(arns), "task_definition_arns": arns})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_ecs_task_definition(
    task_definition: str,
    region: str = "us-east-1",
) -> str:
    """
    Describe an ECS task definition including containers, volumes, and CPU/memory.

    Args:
        task_definition: Task definition family:revision or ARN. (required)
        region:          AWS region (default 'us-east-1').

    Returns:
        JSON: family, revision, status, cpu, memory, network_mode, containers, volumes.
    """
    if not task_definition:
        return _err("task_definition is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_ecs_task_definition taskdef=%s region=%s", task_definition, region)
    try:
        r = _ecs(region).describe_task_definition(taskDefinition=task_definition)
        td = r.get("taskDefinition", {})
        return _ok({
            "family": td.get("family"),
            "revision": td.get("revision"),
            "arn": td.get("taskDefinitionArn"),
            "status": td.get("status"),
            "cpu": td.get("cpu"),
            "memory": td.get("memory"),
            "network_mode": td.get("networkMode"),
            "requires_compatibilities": td.get("requiresCompatibilities", []),
            "execution_role_arn": td.get("executionRoleArn"),
            "task_role_arn": td.get("taskRoleArn"),
            "containers": [
                {
                    "name": c.get("name"),
                    "image": c.get("image"),
                    "cpu": c.get("cpu"),
                    "memory": c.get("memory"),
                    "memory_reservation": c.get("memoryReservation"),
                    "port_mappings": c.get("portMappings", []),
                    "environment": [
                        {"name": e["name"], "value": e["value"]}
                        for e in c.get("environment", [])
                    ],
                    "essential": c.get("essential", True),
                    "log_configuration": c.get("logConfiguration"),
                }
                for c in td.get("containerDefinitions", [])
            ],
            "volumes": td.get("volumes", []),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_ecs_container_instances(
    cluster: str,
    region: str = "us-east-1",
) -> str:
    """
    List EC2 container instances registered with an ECS cluster.

    Args:
        cluster: Cluster name or ARN. (required)
        region:  AWS region (default 'us-east-1').

    Returns:
        JSON: cluster, instance_count, instance_arns.
    """
    if not cluster:
        return _err("cluster is required.", "VALIDATION_ERROR")
    logger.info("aws_list_ecs_container_instances cluster=%s region=%s", cluster, region)
    try:
        paginator = _ecs(region).get_paginator("list_container_instances")
        arns: list[str] = []
        for page in paginator.paginate(cluster=cluster):
            arns.extend(page.get("containerInstanceArns", []))
        return _ok({"cluster": cluster, "instance_count": len(arns), "instance_arns": arns})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
