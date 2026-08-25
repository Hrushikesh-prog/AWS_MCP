from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ec2(region: str):
    return boto3.client("ec2", region_name=region)


def _tag_name(tags: list[dict]) -> str | None:
    return next((t["Value"] for t in (tags or []) if t["Key"] == "Name"), None)


# ===========================================================================
# INSTANCE MANAGEMENT
# ===========================================================================

@mcp.tool()
def aws_list_ec2_instances(
    region: str = "us-east-1",
    state: str = "all",
) -> str:
    """
    List EC2 instances in a region, optionally filtered by state.

    Args:
        region: AWS region (default 'us-east-1').
        state:  'running', 'stopped', 'pending', 'terminated', or 'all'.

    Returns:
        JSON: region, instance_count, instances
              (each: instance_id, instance_type, state, name, public_ip,
               private_ip, launch_time, availability_zone, vpc_id, subnet_id).
    """
    _VALID = {"running", "stopped", "pending", "terminated", "shutting-down", "all"}
    if state not in _VALID:
        return _err(f"state must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")
    logger.info("aws_list_ec2_instances region=%s state=%s", region, state)
    try:
        client = _ec2(region)
        filters = [{"Name": "instance-state-name", "Values": [state]}] if state != "all" else []
        paginator = client.get_paginator("describe_instances")
        pages = paginator.paginate(Filters=filters) if filters else paginator.paginate()
        instances: list[dict[str, Any]] = []
        for page in pages:
            for rsv in page.get("Reservations", []):
                for inst in rsv.get("Instances", []):
                    instances.append({
                        "instance_id": inst.get("InstanceId"),
                        "instance_type": inst.get("InstanceType"),
                        "state": inst.get("State", {}).get("Name"),
                        "name": _tag_name(inst.get("Tags", [])),
                        "public_ip": inst.get("PublicIpAddress"),
                        "private_ip": inst.get("PrivateIpAddress"),
                        "launch_time": inst.get("LaunchTime"),
                        "availability_zone": inst.get("Placement", {}).get("AvailabilityZone"),
                        "vpc_id": inst.get("VpcId"),
                        "subnet_id": inst.get("SubnetId"),
                        "image_id": inst.get("ImageId"),
                        "key_name": inst.get("KeyName"),
                        "security_groups": [
                            {"id": sg["GroupId"], "name": sg["GroupName"]}
                            for sg in inst.get("SecurityGroups", [])
                        ],
                    })
        return _ok({"region": region, "instance_count": len(instances), "instances": instances})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_ec2_instance(
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Get detailed attributes of a single EC2 instance.

    Args:
        instance_id: EC2 instance ID (e.g. 'i-0abc123').
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: full instance attributes including network interfaces,
              block device mappings, IAM profile, monitoring, and tags.
    """
    if not instance_id.strip():
        return _err("instance_id is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_ec2_instance instance_id=%s region=%s", instance_id, region)
    try:
        resp = _ec2(region).describe_instances(InstanceIds=[instance_id])
        reservations = resp.get("Reservations", [])
        if not reservations:
            return _err(f"Instance {instance_id} not found.", "NOT_FOUND")
        inst = reservations[0]["Instances"][0]
        return _ok({
            "instance_id": inst.get("InstanceId"),
            "instance_type": inst.get("InstanceType"),
            "state": inst.get("State", {}).get("Name"),
            "name": _tag_name(inst.get("Tags", [])),
            "tags": inst.get("Tags", []),
            "image_id": inst.get("ImageId"),
            "key_name": inst.get("KeyName"),
            "public_ip": inst.get("PublicIpAddress"),
            "public_dns": inst.get("PublicDnsName"),
            "private_ip": inst.get("PrivateIpAddress"),
            "private_dns": inst.get("PrivateDnsName"),
            "launch_time": inst.get("LaunchTime"),
            "availability_zone": inst.get("Placement", {}).get("AvailabilityZone"),
            "tenancy": inst.get("Placement", {}).get("Tenancy"),
            "vpc_id": inst.get("VpcId"),
            "subnet_id": inst.get("SubnetId"),
            "architecture": inst.get("Architecture"),
            "platform": inst.get("Platform"),
            "hypervisor": inst.get("Hypervisor"),
            "virtualization_type": inst.get("VirtualizationType"),
            "root_device_type": inst.get("RootDeviceType"),
            "root_device_name": inst.get("RootDeviceName"),
            "monitoring_state": inst.get("Monitoring", {}).get("State"),
            "ebs_optimized": inst.get("EbsOptimized"),
            "ena_support": inst.get("EnaSupport"),
            "iam_instance_profile": inst.get("IamInstanceProfile", {}).get("Arn"),
            "security_groups": inst.get("SecurityGroups", []),
            "network_interfaces": [
                {
                    "interface_id": ni.get("NetworkInterfaceId"),
                    "private_ip": ni.get("PrivateIpAddress"),
                    "subnet_id": ni.get("SubnetId"),
                    "vpc_id": ni.get("VpcId"),
                    "mac_address": ni.get("MacAddress"),
                    "attachment_status": ni.get("Attachment", {}).get("Status"),
                }
                for ni in inst.get("NetworkInterfaces", [])
            ],
            "block_devices": [
                {
                    "device_name": bd.get("DeviceName"),
                    "volume_id": bd.get("Ebs", {}).get("VolumeId"),
                    "status": bd.get("Ebs", {}).get("Status"),
                    "delete_on_termination": bd.get("Ebs", {}).get("DeleteOnTermination"),
                }
                for bd in inst.get("BlockDeviceMappings", [])
            ],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_start_ec2_instance(
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Start a stopped EC2 instance.

    Args:
        instance_id: EC2 instance ID to start.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: instance_id, previous_state, current_state.
    """
    if not instance_id.strip():
        return _err("instance_id is required.", "VALIDATION_ERROR")
    logger.info("aws_start_ec2_instance instance_id=%s region=%s", instance_id, region)
    try:
        resp = _ec2(region).start_instances(InstanceIds=[instance_id])
        change = resp["StartingInstances"][0]
        return _ok({
            "instance_id": change["InstanceId"],
            "previous_state": change["PreviousState"]["Name"],
            "current_state": change["CurrentState"]["Name"],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_stop_ec2_instance(
    instance_id: str,
    region: str = "us-east-1",
    force: bool = False,
) -> str:
    """
    Stop a running EC2 instance.

    Args:
        instance_id: EC2 instance ID to stop.
        region:      AWS region (default 'us-east-1').
        force:       Force stop without graceful shutdown (default False).

    Returns:
        JSON: instance_id, previous_state, current_state.
    """
    if not instance_id.strip():
        return _err("instance_id is required.", "VALIDATION_ERROR")
    logger.info("aws_stop_ec2_instance instance_id=%s force=%s region=%s", instance_id, force, region)
    try:
        resp = _ec2(region).stop_instances(InstanceIds=[instance_id], Force=force)
        change = resp["StoppingInstances"][0]
        return _ok({
            "instance_id": change["InstanceId"],
            "previous_state": change["PreviousState"]["Name"],
            "current_state": change["CurrentState"]["Name"],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_reboot_ec2_instance(
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Reboot a running EC2 instance.

    Args:
        instance_id: EC2 instance ID to reboot.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: instance_id, message.
    """
    if not instance_id.strip():
        return _err("instance_id is required.", "VALIDATION_ERROR")
    logger.info("aws_reboot_ec2_instance instance_id=%s region=%s", instance_id, region)
    try:
        _ec2(region).reboot_instances(InstanceIds=[instance_id])
        return _ok({"instance_id": instance_id, "message": "Reboot request accepted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_terminate_ec2_instance(
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Terminate (permanently delete) an EC2 instance.

    Args:
        instance_id: EC2 instance ID to terminate.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: instance_id, previous_state, current_state.
    """
    if not instance_id.strip():
        return _err("instance_id is required.", "VALIDATION_ERROR")
    logger.info("aws_terminate_ec2_instance instance_id=%s region=%s", instance_id, region)
    try:
        resp = _ec2(region).terminate_instances(InstanceIds=[instance_id])
        change = resp["TerminatingInstances"][0]
        return _ok({
            "instance_id": change["InstanceId"],
            "previous_state": change["PreviousState"]["Name"],
            "current_state": change["CurrentState"]["Name"],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_launch_ec2_instance(
    image_id: str,
    instance_type: str,
    region: str = "us-east-1",
    key_name: str = "",
    security_group_ids: list[str] | None = None,
    subnet_id: str = "",
    min_count: int = 1,
    max_count: int = 1,
    user_data: str = "",
    name_tag: str = "",
    iam_instance_profile_arn: str = "",
) -> str:
    """
    Launch one or more new EC2 instances.

    Args:
        image_id:                  AMI ID (required, e.g. 'ami-0abcdef1234567890').
        instance_type:             Instance type (required, e.g. 't3.micro').
        region:                    AWS region (default 'us-east-1').
        key_name:                  Key pair name for SSH access.
        security_group_ids:        List of security group IDs.
        subnet_id:                 Subnet ID to launch into.
        min_count:                 Minimum instances to launch (default 1).
        max_count:                 Maximum instances to launch (default 1).
        user_data:                 User data script (plain text, not base64).
        name_tag:                  Value for the 'Name' tag.
        iam_instance_profile_arn:  ARN of IAM instance profile to attach.

    Returns:
        JSON: instances list with instance_id, state, private_ip.
    """
    if not image_id.strip():
        return _err("image_id is required.", "VALIDATION_ERROR")
    if not instance_type.strip():
        return _err("instance_type is required.", "VALIDATION_ERROR")
    logger.info(
        "aws_launch_ec2_instance image_id=%s type=%s region=%s count=%d",
        image_id, instance_type, region, max_count,
    )
    try:
        kwargs: dict[str, Any] = {
            "ImageId": image_id,
            "InstanceType": instance_type,
            "MinCount": max(1, min_count),
            "MaxCount": max(1, max_count),
        }
        if key_name:
            kwargs["KeyName"] = key_name
        if security_group_ids:
            kwargs["SecurityGroupIds"] = security_group_ids
        if subnet_id:
            kwargs["SubnetId"] = subnet_id
        if user_data:
            kwargs["UserData"] = user_data
        if name_tag:
            kwargs["TagSpecifications"] = [{
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": name_tag}],
            }]
        if iam_instance_profile_arn:
            kwargs["IamInstanceProfile"] = {"Arn": iam_instance_profile_arn}

        resp = _ec2(region).run_instances(**kwargs)
        launched = [
            {
                "instance_id": inst["InstanceId"],
                "state": inst["State"]["Name"],
                "private_ip": inst.get("PrivateIpAddress"),
                "instance_type": inst["InstanceType"],
                "availability_zone": inst.get("Placement", {}).get("AvailabilityZone"),
            }
            for inst in resp.get("Instances", [])
        ]
        return _ok({"region": region, "launched_count": len(launched), "instances": launched})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_ec2_instance_status(
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Get system and instance status checks for an EC2 instance.

    Args:
        instance_id: EC2 instance ID.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: instance_id, instance_state, system_status, instance_status,
              events (scheduled maintenance/retirement).
    """
    if not instance_id.strip():
        return _err("instance_id is required.", "VALIDATION_ERROR")
    logger.info("aws_get_ec2_instance_status instance_id=%s region=%s", instance_id, region)
    try:
        resp = _ec2(region).describe_instance_status(
            InstanceIds=[instance_id],
            IncludeAllInstances=True,
        )
        statuses = resp.get("InstanceStatuses", [])
        if not statuses:
            return _err(f"Instance {instance_id} not found.", "NOT_FOUND")
        s = statuses[0]
        return _ok({
            "instance_id": s["InstanceId"],
            "availability_zone": s.get("AvailabilityZone"),
            "instance_state": s.get("InstanceState", {}).get("Name"),
            "system_status": {
                "status": s.get("SystemStatus", {}).get("Status"),
                "details": s.get("SystemStatus", {}).get("Details", []),
            },
            "instance_status": {
                "status": s.get("InstanceStatus", {}).get("Status"),
                "details": s.get("InstanceStatus", {}).get("Details", []),
            },
            "events": s.get("Events", []),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_ec2_console_output(
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Retrieve the console (serial port) output of an EC2 instance for debugging.

    Args:
        instance_id: EC2 instance ID.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: instance_id, timestamp, output (decoded text).
    """
    if not instance_id.strip():
        return _err("instance_id is required.", "VALIDATION_ERROR")
    logger.info("aws_get_ec2_console_output instance_id=%s region=%s", instance_id, region)
    try:
        resp = _ec2(region).get_console_output(InstanceId=instance_id)
        import base64
        raw = resp.get("Output", "")
        try:
            decoded = base64.b64decode(raw).decode("utf-8", errors="replace")
        except Exception:
            decoded = raw
        return _ok({
            "instance_id": resp.get("InstanceId"),
            "timestamp": resp.get("Timestamp"),
            "output": decoded,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_modify_ec2_instance_type(
    instance_id: str,
    new_instance_type: str,
    region: str = "us-east-1",
) -> str:
    """
    Change the instance type of a stopped EC2 instance.

    Args:
        instance_id:       EC2 instance ID (must be stopped first).
        new_instance_type: Target instance type (e.g. 't3.large').
        region:            AWS region (default 'us-east-1').

    Returns:
        JSON: instance_id, new_instance_type, message.
    """
    if not instance_id.strip() or not new_instance_type.strip():
        return _err("instance_id and new_instance_type are required.", "VALIDATION_ERROR")
    logger.info(
        "aws_modify_ec2_instance_type instance_id=%s type=%s region=%s",
        instance_id, new_instance_type, region,
    )
    try:
        _ec2(region).modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={"Value": new_instance_type},
        )
        return _ok({
            "instance_id": instance_id,
            "new_instance_type": new_instance_type,
            "message": "Instance type updated. Start the instance to apply.",
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_add_ec2_tags(
    resource_id: str,
    tags: dict[str, str],
    region: str = "us-east-1",
) -> str:
    """
    Add or overwrite tags on any EC2 resource (instances, volumes, AMIs, etc.).

    Args:
        resource_id: EC2 resource ID (instance, volume, snapshot, AMI, etc.).
        tags:        Dict of tag key-value pairs (e.g. {"Env": "prod"}).
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: resource_id, tags_applied.
    """
    if not resource_id.strip():
        return _err("resource_id is required.", "VALIDATION_ERROR")
    if not tags:
        return _err("tags dict must not be empty.", "VALIDATION_ERROR")
    logger.info("aws_add_ec2_tags resource_id=%s tags=%s region=%s", resource_id, tags, region)
    try:
        _ec2(region).create_tags(
            Resources=[resource_id],
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )
        return _ok({"resource_id": resource_id, "tags_applied": tags})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_remove_ec2_tags(
    resource_id: str,
    tag_keys: list[str],
    region: str = "us-east-1",
) -> str:
    """
    Remove specific tags from an EC2 resource.

    Args:
        resource_id: EC2 resource ID.
        tag_keys:    List of tag keys to remove.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: resource_id, tags_removed.
    """
    if not resource_id.strip():
        return _err("resource_id is required.", "VALIDATION_ERROR")
    if not tag_keys:
        return _err("tag_keys must not be empty.", "VALIDATION_ERROR")
    logger.info("aws_remove_ec2_tags resource_id=%s keys=%s region=%s", resource_id, tag_keys, region)
    try:
        _ec2(region).delete_tags(
            Resources=[resource_id],
            Tags=[{"Key": k} for k in tag_keys],
        )
        return _ok({"resource_id": resource_id, "tags_removed": tag_keys})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_ec2_instance_types(
    region: str = "us-east-1",
    architecture: str = "x86_64",
    max_results: int = 50,
) -> str:
    """
    List available EC2 instance types in a region, optionally filtered by architecture.

    Args:
        region:       AWS region (default 'us-east-1').
        architecture: 'x86_64', 'arm64', or 'i386' (default 'x86_64').
        max_results:  Max results to return, capped at 100.

    Returns:
        JSON: instance_types list with vcpus, memory_mib, storage, network_performance.
    """
    max_results = max(1, min(int(max_results), 100))
    logger.info(
        "aws_list_ec2_instance_types region=%s arch=%s", region, architecture,
    )
    try:
        resp = _ec2(region).describe_instance_types(
            Filters=[{"Name": "processor-info.supported-architecture", "Values": [architecture]}],
            MaxResults=max_results,
        )
        types = [
            {
                "instance_type": it["InstanceType"],
                "vcpus": it.get("VCpuInfo", {}).get("DefaultVCpus"),
                "memory_mib": it.get("MemoryInfo", {}).get("SizeInMiB"),
                "network_performance": it.get("NetworkInfo", {}).get("NetworkPerformance"),
                "ebs_optimized_support": it.get("EbsInfo", {}).get("EbsOptimizedSupport"),
                "free_tier_eligible": it.get("FreeTierEligible", False),
                "current_generation": it.get("CurrentGeneration", False),
            }
            for it in resp.get("InstanceTypes", [])
        ]
        return _ok({
            "region": region,
            "architecture": architecture,
            "instance_type_count": len(types),
            "instance_types": types,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# AMI (AMAZON MACHINE IMAGES)
# ===========================================================================

@mcp.tool()
def aws_list_ec2_amis(
    region: str = "us-east-1",
    owner: str = "self",
    name_filter: str = "",
    max_results: int = 20,
) -> str:
    """
    List AMIs available to your account.

    Args:
        region:      AWS region (default 'us-east-1').
        owner:       'self', 'amazon', 'aws-marketplace', or an account ID.
        name_filter: Wildcard pattern to filter by AMI name (e.g. 'ubuntu-*').
        max_results: Max results (default 20, capped at 100).

    Returns:
        JSON: ami_count, amis (each: image_id, name, state, architecture,
              creation_date, root_device_type, virtualization_type).
    """
    max_results = max(1, min(int(max_results), 100))
    logger.info("aws_list_ec2_amis region=%s owner=%s filter=%r", region, owner, name_filter)
    try:
        kwargs: dict[str, Any] = {"Owners": [owner]}
        if name_filter:
            kwargs["Filters"] = [{"Name": "name", "Values": [name_filter]}]
        resp = _ec2(region).describe_images(**kwargs)
        images = sorted(
            resp.get("Images", []),
            key=lambda x: x.get("CreationDate", ""),
            reverse=True,
        )[:max_results]
        return _ok({
            "region": region,
            "ami_count": len(images),
            "amis": [
                {
                    "image_id": img["ImageId"],
                    "name": img.get("Name"),
                    "description": img.get("Description"),
                    "state": img.get("State"),
                    "architecture": img.get("Architecture"),
                    "creation_date": img.get("CreationDate"),
                    "root_device_type": img.get("RootDeviceType"),
                    "virtualization_type": img.get("VirtualizationType"),
                    "public": img.get("Public", False),
                    "owner_id": img.get("OwnerId"),
                    "platform": img.get("Platform"),
                }
                for img in images
            ],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_ec2_ami(
    image_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Get detailed information about a specific AMI.

    Args:
        image_id: AMI ID (e.g. 'ami-0abc123').
        region:   AWS region (default 'us-east-1').

    Returns:
        JSON: full AMI attributes including block device mappings and tags.
    """
    if not image_id.strip():
        return _err("image_id is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_ec2_ami image_id=%s region=%s", image_id, region)
    try:
        resp = _ec2(region).describe_images(ImageIds=[image_id])
        images = resp.get("Images", [])
        if not images:
            return _err(f"AMI {image_id} not found.", "NOT_FOUND")
        img = images[0]
        return _ok({
            "image_id": img["ImageId"],
            "name": img.get("Name"),
            "description": img.get("Description"),
            "state": img.get("State"),
            "architecture": img.get("Architecture"),
            "creation_date": img.get("CreationDate"),
            "root_device_type": img.get("RootDeviceType"),
            "root_device_name": img.get("RootDeviceName"),
            "virtualization_type": img.get("VirtualizationType"),
            "hypervisor": img.get("Hypervisor"),
            "public": img.get("Public", False),
            "owner_id": img.get("OwnerId"),
            "platform": img.get("Platform"),
            "tags": img.get("Tags", []),
            "block_device_mappings": img.get("BlockDeviceMappings", []),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_ec2_ami(
    instance_id: str,
    name: str,
    description: str = "",
    region: str = "us-east-1",
    no_reboot: bool = True,
) -> str:
    """
    Create an AMI from an existing EC2 instance.

    Args:
        instance_id: Source EC2 instance ID.
        name:        Name for the new AMI.
        description: Optional description.
        region:      AWS region (default 'us-east-1').
        no_reboot:   If True, instance is not rebooted before image creation (default True).

    Returns:
        JSON: image_id, name, message.
    """
    if not instance_id.strip() or not name.strip():
        return _err("instance_id and name are required.", "VALIDATION_ERROR")
    logger.info(
        "aws_create_ec2_ami instance_id=%s name=%r region=%s", instance_id, name, region,
    )
    try:
        resp = _ec2(region).create_image(
            InstanceId=instance_id,
            Name=name,
            Description=description,
            NoReboot=no_reboot,
        )
        return _ok({
            "image_id": resp["ImageId"],
            "name": name,
            "message": "AMI creation initiated. Use aws_describe_ec2_ami to check status.",
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_deregister_ec2_ami(
    image_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Deregister (delete) an AMI. Does not delete associated snapshots.

    Args:
        image_id: AMI ID to deregister.
        region:   AWS region (default 'us-east-1').

    Returns:
        JSON: image_id, message.
    """
    if not image_id.strip():
        return _err("image_id is required.", "VALIDATION_ERROR")
    logger.info("aws_deregister_ec2_ami image_id=%s region=%s", image_id, region)
    try:
        _ec2(region).deregister_image(ImageId=image_id)
        return _ok({"image_id": image_id, "message": "AMI deregistered successfully."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# SECURITY GROUPS
# ===========================================================================

@mcp.tool()
def aws_list_security_groups(
    region: str = "us-east-1",
    vpc_id: str = "",
) -> str:
    """
    List EC2 security groups in a region, optionally filtered by VPC.

    Args:
        region: AWS region (default 'us-east-1').
        vpc_id: Filter by VPC ID (optional).

    Returns:
        JSON: security_group_count, security_groups
              (each: group_id, name, description, vpc_id, inbound_rule_count, outbound_rule_count).
    """
    logger.info("aws_list_security_groups region=%s vpc_id=%s", region, vpc_id)
    try:
        kwargs: dict[str, Any] = {}
        if vpc_id:
            kwargs["Filters"] = [{"Name": "vpc-id", "Values": [vpc_id]}]
        paginator = _ec2(region).get_paginator("describe_security_groups")
        pages = paginator.paginate(**kwargs)
        groups = []
        for page in pages:
            for sg in page.get("SecurityGroups", []):
                groups.append({
                    "group_id": sg["GroupId"],
                    "name": sg["GroupName"],
                    "description": sg.get("Description"),
                    "vpc_id": sg.get("VpcId"),
                    "owner_id": sg.get("OwnerId"),
                    "inbound_rule_count": len(sg.get("IpPermissions", [])),
                    "outbound_rule_count": len(sg.get("IpPermissionsEgress", [])),
                    "tags": sg.get("Tags", []),
                })
        return _ok({"region": region, "security_group_count": len(groups), "security_groups": groups})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_describe_security_group(
    group_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Get full details of a security group including all inbound and outbound rules.

    Args:
        group_id: Security group ID (e.g. 'sg-0abc123').
        region:   AWS region (default 'us-east-1').

    Returns:
        JSON: group_id, name, description, vpc_id, inbound_rules, outbound_rules.
    """
    if not group_id.strip():
        return _err("group_id is required.", "VALIDATION_ERROR")
    logger.info("aws_describe_security_group group_id=%s region=%s", group_id, region)
    try:
        resp = _ec2(region).describe_security_groups(GroupIds=[group_id])
        sgs = resp.get("SecurityGroups", [])
        if not sgs:
            return _err(f"Security group {group_id} not found.", "NOT_FOUND")
        sg = sgs[0]
        return _ok({
            "group_id": sg["GroupId"],
            "name": sg["GroupName"],
            "description": sg.get("Description"),
            "vpc_id": sg.get("VpcId"),
            "owner_id": sg.get("OwnerId"),
            "tags": sg.get("Tags", []),
            "inbound_rules": sg.get("IpPermissions", []),
            "outbound_rules": sg.get("IpPermissionsEgress", []),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_security_group(
    name: str,
    description: str,
    vpc_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Create a new EC2 security group in a VPC.

    Args:
        name:        Security group name.
        description: Security group description.
        vpc_id:      VPC ID to create the group in.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: group_id, name, vpc_id.
    """
    if not name.strip() or not description.strip() or not vpc_id.strip():
        return _err("name, description, and vpc_id are all required.", "VALIDATION_ERROR")
    logger.info("aws_create_security_group name=%r vpc_id=%s region=%s", name, vpc_id, region)
    try:
        resp = _ec2(region).create_security_group(
            GroupName=name,
            Description=description,
            VpcId=vpc_id,
        )
        return _ok({"group_id": resp["GroupId"], "name": name, "vpc_id": vpc_id})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_security_group(
    group_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete an EC2 security group.

    Args:
        group_id: Security group ID to delete.
        region:   AWS region (default 'us-east-1').

    Returns:
        JSON: group_id, message.
    """
    if not group_id.strip():
        return _err("group_id is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_security_group group_id=%s region=%s", group_id, region)
    try:
        _ec2(region).delete_security_group(GroupId=group_id)
        return _ok({"group_id": group_id, "message": "Security group deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_add_security_group_ingress_rule(
    group_id: str,
    protocol: str,
    from_port: int,
    to_port: int,
    cidr: str = "",
    source_group_id: str = "",
    region: str = "us-east-1",
    description: str = "",
) -> str:
    """
    Add an inbound (ingress) rule to a security group.

    Args:
        group_id:        Security group ID.
        protocol:        IP protocol: 'tcp', 'udp', 'icmp', or '-1' (all traffic).
        from_port:       Start of port range (use -1 for ICMP/all).
        to_port:         End of port range (use -1 for ICMP/all).
        cidr:            IPv4 CIDR block (e.g. '0.0.0.0/0'). One of cidr or source_group_id required.
        source_group_id: Alternate to cidr — allow traffic from another security group.
        region:          AWS region (default 'us-east-1').
        description:     Rule description.

    Returns:
        JSON: group_id, rule added summary.
    """
    if not group_id.strip():
        return _err("group_id is required.", "VALIDATION_ERROR")
    if not cidr and not source_group_id:
        return _err("Either cidr or source_group_id must be provided.", "VALIDATION_ERROR")
    logger.info(
        "aws_add_security_group_ingress_rule group_id=%s proto=%s ports=%d-%d",
        group_id, protocol, from_port, to_port,
    )
    try:
        ip_permission: dict[str, Any] = {
            "IpProtocol": protocol,
            "FromPort": from_port,
            "ToPort": to_port,
        }
        if cidr:
            ip_permission["IpRanges"] = [{"CidrIp": cidr, "Description": description}]
        elif source_group_id:
            ip_permission["UserIdGroupPairs"] = [{"GroupId": source_group_id, "Description": description}]

        _ec2(region).authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[ip_permission],
        )
        return _ok({
            "group_id": group_id,
            "direction": "ingress",
            "protocol": protocol,
            "port_range": f"{from_port}-{to_port}",
            "source": cidr or source_group_id,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_add_security_group_egress_rule(
    group_id: str,
    protocol: str,
    from_port: int,
    to_port: int,
    cidr: str = "0.0.0.0/0",
    region: str = "us-east-1",
    description: str = "",
) -> str:
    """
    Add an outbound (egress) rule to a security group.

    Args:
        group_id:    Security group ID.
        protocol:    IP protocol: 'tcp', 'udp', 'icmp', or '-1' (all traffic).
        from_port:   Start of port range (use -1 for ICMP/all).
        to_port:     End of port range (use -1 for ICMP/all).
        cidr:        Destination IPv4 CIDR (default '0.0.0.0/0').
        region:      AWS region (default 'us-east-1').
        description: Rule description.

    Returns:
        JSON: group_id, rule added summary.
    """
    if not group_id.strip():
        return _err("group_id is required.", "VALIDATION_ERROR")
    logger.info(
        "aws_add_security_group_egress_rule group_id=%s proto=%s ports=%d-%d",
        group_id, protocol, from_port, to_port,
    )
    try:
        _ec2(region).authorize_security_group_egress(
            GroupId=group_id,
            IpPermissions=[{
                "IpProtocol": protocol,
                "FromPort": from_port,
                "ToPort": to_port,
                "IpRanges": [{"CidrIp": cidr, "Description": description}],
            }],
        )
        return _ok({
            "group_id": group_id,
            "direction": "egress",
            "protocol": protocol,
            "port_range": f"{from_port}-{to_port}",
            "destination": cidr,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_revoke_security_group_ingress_rule(
    group_id: str,
    protocol: str,
    from_port: int,
    to_port: int,
    cidr: str = "",
    source_group_id: str = "",
    region: str = "us-east-1",
) -> str:
    """
    Remove an inbound rule from a security group.

    Args:
        group_id:        Security group ID.
        protocol:        IP protocol: 'tcp', 'udp', 'icmp', or '-1'.
        from_port:       Start of port range.
        to_port:         End of port range.
        cidr:            IPv4 CIDR of the rule to remove.
        source_group_id: Source group of the rule to remove (alternative to cidr).
        region:          AWS region (default 'us-east-1').

    Returns:
        JSON: group_id, removed rule summary.
    """
    if not group_id.strip():
        return _err("group_id is required.", "VALIDATION_ERROR")
    if not cidr and not source_group_id:
        return _err("Either cidr or source_group_id must be provided.", "VALIDATION_ERROR")
    logger.info(
        "aws_revoke_security_group_ingress_rule group_id=%s proto=%s ports=%d-%d",
        group_id, protocol, from_port, to_port,
    )
    try:
        ip_permission: dict[str, Any] = {
            "IpProtocol": protocol,
            "FromPort": from_port,
            "ToPort": to_port,
        }
        if cidr:
            ip_permission["IpRanges"] = [{"CidrIp": cidr}]
        elif source_group_id:
            ip_permission["UserIdGroupPairs"] = [{"GroupId": source_group_id}]

        _ec2(region).revoke_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[ip_permission],
        )
        return _ok({
            "group_id": group_id,
            "direction": "ingress",
            "protocol": protocol,
            "port_range": f"{from_port}-{to_port}",
            "source": cidr or source_group_id,
            "message": "Rule revoked.",
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# KEY PAIRS
# ===========================================================================

@mcp.tool()
def aws_list_key_pairs(
    region: str = "us-east-1",
) -> str:
    """
    List all EC2 key pairs in a region.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: key_pair_count, key_pairs (each: name, fingerprint, id, type, create_time).
    """
    logger.info("aws_list_key_pairs region=%s", region)
    try:
        resp = _ec2(region).describe_key_pairs()
        pairs = [
            {
                "name": kp["KeyName"],
                "key_pair_id": kp.get("KeyPairId"),
                "fingerprint": kp.get("KeyFingerprint"),
                "type": kp.get("KeyType"),
                "create_time": kp.get("CreateTime"),
                "tags": kp.get("Tags", []),
            }
            for kp in resp.get("KeyPairs", [])
        ]
        return _ok({"region": region, "key_pair_count": len(pairs), "key_pairs": pairs})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_key_pair(
    key_name: str,
    key_type: str = "rsa",
    region: str = "us-east-1",
) -> str:
    """
    Create a new EC2 key pair and return the private key material.

    IMPORTANT: Save the returned private key immediately — AWS does not store it.

    Args:
        key_name: Name for the new key pair.
        key_type: 'rsa' (default) or 'ed25519'.
        region:   AWS region (default 'us-east-1').

    Returns:
        JSON: key_name, key_pair_id, key_type, private_key_material.
    """
    if not key_name.strip():
        return _err("key_name is required.", "VALIDATION_ERROR")
    if key_type not in ("rsa", "ed25519"):
        return _err("key_type must be 'rsa' or 'ed25519'.", "VALIDATION_ERROR")
    logger.info("aws_create_key_pair key_name=%r key_type=%s region=%s", key_name, key_type, region)
    try:
        resp = _ec2(region).create_key_pair(KeyName=key_name, KeyType=key_type)
        return _ok({
            "key_name": resp["KeyName"],
            "key_pair_id": resp.get("KeyPairId"),
            "key_type": key_type,
            "private_key_material": resp["KeyMaterial"],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_key_pair(
    key_name: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete an EC2 key pair.

    Args:
        key_name: Key pair name to delete.
        region:   AWS region (default 'us-east-1').

    Returns:
        JSON: key_name, message.
    """
    if not key_name.strip():
        return _err("key_name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_key_pair key_name=%r region=%s", key_name, region)
    try:
        _ec2(region).delete_key_pair(KeyName=key_name)
        return _ok({"key_name": key_name, "message": "Key pair deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# ELASTIC IPs
# ===========================================================================

@mcp.tool()
def aws_list_elastic_ips(
    region: str = "us-east-1",
) -> str:
    """
    List all allocated Elastic IP addresses in a region.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: elastic_ip_count, elastic_ips
              (each: allocation_id, public_ip, instance_id, association_id, domain).
    """
    logger.info("aws_list_elastic_ips region=%s", region)
    try:
        resp = _ec2(region).describe_addresses()
        eips = [
            {
                "allocation_id": addr.get("AllocationId"),
                "public_ip": addr.get("PublicIp"),
                "private_ip": addr.get("PrivateIpAddress"),
                "instance_id": addr.get("InstanceId"),
                "association_id": addr.get("AssociationId"),
                "network_interface_id": addr.get("NetworkInterfaceId"),
                "domain": addr.get("Domain"),
                "tags": addr.get("Tags", []),
            }
            for addr in resp.get("Addresses", [])
        ]
        return _ok({"region": region, "elastic_ip_count": len(eips), "elastic_ips": eips})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_allocate_elastic_ip(
    region: str = "us-east-1",
) -> str:
    """
    Allocate a new Elastic IP address.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: allocation_id, public_ip.
    """
    logger.info("aws_allocate_elastic_ip region=%s", region)
    try:
        resp = _ec2(region).allocate_address(Domain="vpc")
        return _ok({
            "allocation_id": resp["AllocationId"],
            "public_ip": resp["PublicIp"],
            "domain": resp.get("Domain"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_release_elastic_ip(
    allocation_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Release an Elastic IP address back to AWS. It must not be associated.

    Args:
        allocation_id: Elastic IP allocation ID.
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: allocation_id, message.
    """
    if not allocation_id.strip():
        return _err("allocation_id is required.", "VALIDATION_ERROR")
    logger.info("aws_release_elastic_ip allocation_id=%s region=%s", allocation_id, region)
    try:
        _ec2(region).release_address(AllocationId=allocation_id)
        return _ok({"allocation_id": allocation_id, "message": "Elastic IP released."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_associate_elastic_ip(
    allocation_id: str,
    instance_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Associate an Elastic IP with a running EC2 instance.

    Args:
        allocation_id: Elastic IP allocation ID.
        instance_id:   Target EC2 instance ID.
        region:        AWS region (default 'us-east-1').

    Returns:
        JSON: association_id, allocation_id, instance_id.
    """
    if not allocation_id.strip() or not instance_id.strip():
        return _err("allocation_id and instance_id are required.", "VALIDATION_ERROR")
    logger.info(
        "aws_associate_elastic_ip allocation_id=%s instance_id=%s region=%s",
        allocation_id, instance_id, region,
    )
    try:
        resp = _ec2(region).associate_address(
            AllocationId=allocation_id,
            InstanceId=instance_id,
        )
        return _ok({
            "association_id": resp["AssociationId"],
            "allocation_id": allocation_id,
            "instance_id": instance_id,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_disassociate_elastic_ip(
    association_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Disassociate an Elastic IP from an EC2 instance (keeps the allocation).

    Args:
        association_id: Elastic IP association ID.
        region:         AWS region (default 'us-east-1').

    Returns:
        JSON: association_id, message.
    """
    if not association_id.strip():
        return _err("association_id is required.", "VALIDATION_ERROR")
    logger.info(
        "aws_disassociate_elastic_ip association_id=%s region=%s", association_id, region,
    )
    try:
        _ec2(region).disassociate_address(AssociationId=association_id)
        return _ok({"association_id": association_id, "message": "Elastic IP disassociated."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# VPC & NETWORKING
# ===========================================================================

@mcp.tool()
def aws_list_vpcs(
    region: str = "us-east-1",
) -> str:
    """
    List all VPCs in a region.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: vpc_count, vpcs
              (each: vpc_id, name, cidr_block, state, is_default, dhcp_options_id).
    """
    logger.info("aws_list_vpcs region=%s", region)
    try:
        resp = _ec2(region).describe_vpcs()
        vpcs = [
            {
                "vpc_id": v["VpcId"],
                "name": _tag_name(v.get("Tags", [])),
                "cidr_block": v.get("CidrBlock"),
                "state": v.get("State"),
                "is_default": v.get("IsDefault", False),
                "dhcp_options_id": v.get("DhcpOptionsId"),
                "instance_tenancy": v.get("InstanceTenancy"),
                "tags": v.get("Tags", []),
            }
            for v in resp.get("Vpcs", [])
        ]
        return _ok({"region": region, "vpc_count": len(vpcs), "vpcs": vpcs})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_subnets(
    region: str = "us-east-1",
    vpc_id: str = "",
) -> str:
    """
    List subnets in a region, optionally filtered by VPC.

    Args:
        region: AWS region (default 'us-east-1').
        vpc_id: Filter by VPC ID (optional).

    Returns:
        JSON: subnet_count, subnets
              (each: subnet_id, name, vpc_id, cidr_block, availability_zone,
               available_ips, map_public_ip_on_launch).
    """
    logger.info("aws_list_subnets region=%s vpc_id=%s", region, vpc_id)
    try:
        kwargs: dict[str, Any] = {}
        if vpc_id:
            kwargs["Filters"] = [{"Name": "vpc-id", "Values": [vpc_id]}]
        resp = _ec2(region).describe_subnets(**kwargs)
        subnets = [
            {
                "subnet_id": s["SubnetId"],
                "name": _tag_name(s.get("Tags", [])),
                "vpc_id": s.get("VpcId"),
                "cidr_block": s.get("CidrBlock"),
                "availability_zone": s.get("AvailabilityZone"),
                "available_ip_count": s.get("AvailableIpAddressCount"),
                "map_public_ip_on_launch": s.get("MapPublicIpOnLaunch", False),
                "state": s.get("State"),
                "default_for_az": s.get("DefaultForAz", False),
                "tags": s.get("Tags", []),
            }
            for s in resp.get("Subnets", [])
        ]
        return _ok({"region": region, "subnet_count": len(subnets), "subnets": subnets})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_internet_gateways(
    region: str = "us-east-1",
    vpc_id: str = "",
) -> str:
    """
    List internet gateways in a region, optionally filtered by attached VPC.

    Args:
        region: AWS region (default 'us-east-1').
        vpc_id: Filter by attached VPC ID (optional).

    Returns:
        JSON: igw_count, internet_gateways (each: igw_id, name, attachments).
    """
    logger.info("aws_list_internet_gateways region=%s vpc_id=%s", region, vpc_id)
    try:
        kwargs: dict[str, Any] = {}
        if vpc_id:
            kwargs["Filters"] = [{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
        resp = _ec2(region).describe_internet_gateways(**kwargs)
        igws = [
            {
                "igw_id": igw["InternetGatewayId"],
                "name": _tag_name(igw.get("Tags", [])),
                "attachments": igw.get("Attachments", []),
                "tags": igw.get("Tags", []),
            }
            for igw in resp.get("InternetGateways", [])
        ]
        return _ok({"region": region, "igw_count": len(igws), "internet_gateways": igws})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_route_tables(
    region: str = "us-east-1",
    vpc_id: str = "",
) -> str:
    """
    List route tables in a region, optionally filtered by VPC.

    Args:
        region: AWS region (default 'us-east-1').
        vpc_id: Filter by VPC ID (optional).

    Returns:
        JSON: route_table_count, route_tables
              (each: route_table_id, name, vpc_id, routes, associations).
    """
    logger.info("aws_list_route_tables region=%s vpc_id=%s", region, vpc_id)
    try:
        kwargs: dict[str, Any] = {}
        if vpc_id:
            kwargs["Filters"] = [{"Name": "vpc-id", "Values": [vpc_id]}]
        resp = _ec2(region).describe_route_tables(**kwargs)
        rts = [
            {
                "route_table_id": rt["RouteTableId"],
                "name": _tag_name(rt.get("Tags", [])),
                "vpc_id": rt.get("VpcId"),
                "routes": [
                    {
                        "destination": r.get("DestinationCidrBlock") or r.get("DestinationIpv6CidrBlock"),
                        "target": (
                            r.get("GatewayId") or r.get("NatGatewayId") or
                            r.get("InstanceId") or r.get("NetworkInterfaceId") or
                            r.get("VpcPeeringConnectionId") or r.get("TransitGatewayId")
                        ),
                        "state": r.get("State"),
                    }
                    for r in rt.get("Routes", [])
                ],
                "associations": [
                    {
                        "subnet_id": a.get("SubnetId"),
                        "main": a.get("Main", False),
                    }
                    for a in rt.get("Associations", [])
                ],
            }
            for rt in resp.get("RouteTables", [])
        ]
        return _ok({"region": region, "route_table_count": len(rts), "route_tables": rts})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_network_interfaces(
    region: str = "us-east-1",
    instance_id: str = "",
    vpc_id: str = "",
) -> str:
    """
    List Elastic Network Interfaces (ENIs) in a region.

    Args:
        region:      AWS region (default 'us-east-1').
        instance_id: Filter by attached instance ID (optional).
        vpc_id:      Filter by VPC ID (optional).

    Returns:
        JSON: eni_count, network_interfaces (each: eni_id, status, private_ip,
              attachment, subnet_id, vpc_id, security_groups).
    """
    logger.info(
        "aws_list_network_interfaces region=%s instance_id=%s vpc_id=%s",
        region, instance_id, vpc_id,
    )
    try:
        filters = []
        if instance_id:
            filters.append({"Name": "attachment.instance-id", "Values": [instance_id]})
        if vpc_id:
            filters.append({"Name": "vpc-id", "Values": [vpc_id]})
        kwargs: dict[str, Any] = {"Filters": filters} if filters else {}
        resp = _ec2(region).describe_network_interfaces(**kwargs)
        enis = [
            {
                "eni_id": ni["NetworkInterfaceId"],
                "description": ni.get("Description"),
                "status": ni.get("Status"),
                "private_ip": ni.get("PrivateIpAddress"),
                "mac_address": ni.get("MacAddress"),
                "subnet_id": ni.get("SubnetId"),
                "vpc_id": ni.get("VpcId"),
                "availability_zone": ni.get("AvailabilityZone"),
                "attachment": {
                    "instance_id": ni.get("Attachment", {}).get("InstanceId"),
                    "device_index": ni.get("Attachment", {}).get("DeviceIndex"),
                    "status": ni.get("Attachment", {}).get("Status"),
                } if ni.get("Attachment") else None,
                "security_groups": [
                    {"id": sg["GroupId"], "name": sg["GroupName"]}
                    for sg in ni.get("Groups", [])
                ],
            }
            for ni in resp.get("NetworkInterfaces", [])
        ]
        return _ok({"region": region, "eni_count": len(enis), "network_interfaces": enis})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# EBS VOLUMES
# ===========================================================================

@mcp.tool()
def aws_list_ebs_volumes(
    region: str = "us-east-1",
    state: str = "all",
) -> str:
    """
    List EBS volumes in a region.

    Args:
        region: AWS region (default 'us-east-1').
        state:  'available', 'in-use', 'error', or 'all' (default).

    Returns:
        JSON: volume_count, volumes
              (each: volume_id, name, size_gib, state, volume_type,
               availability_zone, encrypted, iops, attachments).
    """
    _VALID = {"available", "in-use", "error", "all"}
    if state not in _VALID:
        return _err(f"state must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")
    logger.info("aws_list_ebs_volumes region=%s state=%s", region, state)
    try:
        kwargs: dict[str, Any] = {}
        if state != "all":
            kwargs["Filters"] = [{"Name": "status", "Values": [state]}]
        paginator = _ec2(region).get_paginator("describe_volumes")
        pages = paginator.paginate(**kwargs)
        volumes = []
        for page in pages:
            for v in page.get("Volumes", []):
                volumes.append({
                    "volume_id": v["VolumeId"],
                    "name": _tag_name(v.get("Tags", [])),
                    "size_gib": v.get("Size"),
                    "state": v.get("State"),
                    "volume_type": v.get("VolumeType"),
                    "availability_zone": v.get("AvailabilityZone"),
                    "encrypted": v.get("Encrypted", False),
                    "iops": v.get("Iops"),
                    "throughput": v.get("Throughput"),
                    "create_time": v.get("CreateTime"),
                    "kms_key_id": v.get("KmsKeyId"),
                    "attachments": [
                        {
                            "instance_id": a.get("InstanceId"),
                            "device": a.get("Device"),
                            "state": a.get("State"),
                            "delete_on_termination": a.get("DeleteOnTermination"),
                        }
                        for a in v.get("Attachments", [])
                    ],
                })
        return _ok({"region": region, "volume_count": len(volumes), "volumes": volumes})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_ebs_volume(
    availability_zone: str,
    size_gib: int,
    volume_type: str = "gp3",
    region: str = "us-east-1",
    encrypted: bool = False,
    iops: int = 0,
    throughput: int = 0,
    snapshot_id: str = "",
    name_tag: str = "",
) -> str:
    """
    Create a new EBS volume.

    Args:
        availability_zone: AZ for the volume (e.g. 'us-east-1a').
        size_gib:          Size in GiB.
        volume_type:       'gp3' (default), 'gp2', 'io1', 'io2', 'st1', 'sc1', 'standard'.
        region:            AWS region (default 'us-east-1').
        encrypted:         Encrypt the volume (default False).
        iops:              Provisioned IOPS (for io1/io2/gp3; 0 = use default).
        throughput:        Throughput in MiB/s for gp3 (0 = use default).
        snapshot_id:       Create from snapshot (optional).
        name_tag:          Value for the 'Name' tag.

    Returns:
        JSON: volume_id, size_gib, state, availability_zone.
    """
    if not availability_zone.strip():
        return _err("availability_zone is required.", "VALIDATION_ERROR")
    if size_gib <= 0:
        return _err("size_gib must be a positive integer.", "VALIDATION_ERROR")
    logger.info(
        "aws_create_ebs_volume az=%s size=%dGiB type=%s region=%s",
        availability_zone, size_gib, volume_type, region,
    )
    try:
        kwargs: dict[str, Any] = {
            "AvailabilityZone": availability_zone,
            "Size": size_gib,
            "VolumeType": volume_type,
            "Encrypted": encrypted,
        }
        if iops > 0:
            kwargs["Iops"] = iops
        if throughput > 0:
            kwargs["Throughput"] = throughput
        if snapshot_id:
            kwargs["SnapshotId"] = snapshot_id
        if name_tag:
            kwargs["TagSpecifications"] = [{
                "ResourceType": "volume",
                "Tags": [{"Key": "Name", "Value": name_tag}],
            }]

        resp = _ec2(region).create_volume(**kwargs)
        return _ok({
            "volume_id": resp["VolumeId"],
            "size_gib": resp["Size"],
            "volume_type": resp["VolumeType"],
            "state": resp["State"],
            "availability_zone": resp["AvailabilityZone"],
            "encrypted": resp["Encrypted"],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_ebs_volume(
    volume_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete an EBS volume. The volume must be in 'available' state (not attached).

    Args:
        volume_id: EBS volume ID to delete.
        region:    AWS region (default 'us-east-1').

    Returns:
        JSON: volume_id, message.
    """
    if not volume_id.strip():
        return _err("volume_id is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_ebs_volume volume_id=%s region=%s", volume_id, region)
    try:
        _ec2(region).delete_volume(VolumeId=volume_id)
        return _ok({"volume_id": volume_id, "message": "Volume deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_attach_ebs_volume(
    volume_id: str,
    instance_id: str,
    device_name: str,
    region: str = "us-east-1",
) -> str:
    """
    Attach an EBS volume to an EC2 instance.

    Args:
        volume_id:   EBS volume ID to attach.
        instance_id: Target EC2 instance ID.
        device_name: Device name on the instance (e.g. '/dev/xvdf').
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: volume_id, instance_id, device_name, state.
    """
    if not volume_id.strip() or not instance_id.strip() or not device_name.strip():
        return _err("volume_id, instance_id, and device_name are required.", "VALIDATION_ERROR")
    logger.info(
        "aws_attach_ebs_volume volume_id=%s instance_id=%s device=%s region=%s",
        volume_id, instance_id, device_name, region,
    )
    try:
        resp = _ec2(region).attach_volume(
            VolumeId=volume_id,
            InstanceId=instance_id,
            Device=device_name,
        )
        return _ok({
            "volume_id": resp["VolumeId"],
            "instance_id": resp["InstanceId"],
            "device_name": resp["Device"],
            "state": resp["State"],
            "attach_time": resp.get("AttachTime"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_detach_ebs_volume(
    volume_id: str,
    region: str = "us-east-1",
    force: bool = False,
) -> str:
    """
    Detach an EBS volume from its EC2 instance.

    Args:
        volume_id: EBS volume ID to detach.
        region:    AWS region (default 'us-east-1').
        force:     Force detach (risk of data corruption; default False).

    Returns:
        JSON: volume_id, state.
    """
    if not volume_id.strip():
        return _err("volume_id is required.", "VALIDATION_ERROR")
    logger.info(
        "aws_detach_ebs_volume volume_id=%s force=%s region=%s", volume_id, force, region,
    )
    try:
        resp = _ec2(region).detach_volume(VolumeId=volume_id, Force=force)
        return _ok({
            "volume_id": resp["VolumeId"],
            "instance_id": resp.get("InstanceId"),
            "device_name": resp.get("Device"),
            "state": resp["State"],
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_modify_ebs_volume(
    volume_id: str,
    region: str = "us-east-1",
    size_gib: int = 0,
    volume_type: str = "",
    iops: int = 0,
    throughput: int = 0,
) -> str:
    """
    Modify an EBS volume (resize, change type, adjust IOPS/throughput). Can be done live.

    Args:
        volume_id:   EBS volume ID to modify.
        region:      AWS region (default 'us-east-1').
        size_gib:    New size in GiB (0 = no change). Can only increase.
        volume_type: New volume type (empty = no change).
        iops:        New provisioned IOPS (0 = no change).
        throughput:  New throughput in MiB/s for gp3 (0 = no change).

    Returns:
        JSON: volume_modification details.
    """
    if not volume_id.strip():
        return _err("volume_id is required.", "VALIDATION_ERROR")
    if not any([size_gib, volume_type, iops, throughput]):
        return _err("Specify at least one of: size_gib, volume_type, iops, throughput.", "VALIDATION_ERROR")
    logger.info("aws_modify_ebs_volume volume_id=%s region=%s", volume_id, region)
    try:
        kwargs: dict[str, Any] = {"VolumeId": volume_id}
        if size_gib > 0:
            kwargs["Size"] = size_gib
        if volume_type:
            kwargs["VolumeType"] = volume_type
        if iops > 0:
            kwargs["Iops"] = iops
        if throughput > 0:
            kwargs["Throughput"] = throughput

        resp = _ec2(region).modify_volume(**kwargs)
        mod = resp.get("VolumeModification", {})
        return _ok({
            "volume_id": mod.get("VolumeId"),
            "modification_state": mod.get("ModificationState"),
            "target_size_gib": mod.get("TargetSize"),
            "target_volume_type": mod.get("TargetVolumeType"),
            "target_iops": mod.get("TargetIops"),
            "target_throughput": mod.get("TargetThroughput"),
            "start_time": mod.get("StartTime"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# EBS SNAPSHOTS
# ===========================================================================

@mcp.tool()
def aws_list_ebs_snapshots(
    region: str = "us-east-1",
    owner: str = "self",
    volume_id: str = "",
    max_results: int = 20,
) -> str:
    """
    List EBS snapshots.

    Args:
        region:      AWS region (default 'us-east-1').
        owner:       'self' (default) or an AWS account ID.
        volume_id:   Filter by source volume ID (optional).
        max_results: Max results (default 20, capped at 100).

    Returns:
        JSON: snapshot_count, snapshots
              (each: snapshot_id, volume_id, state, size_gib, start_time,
               progress, description, encrypted).
    """
    max_results = max(1, min(int(max_results), 100))
    logger.info(
        "aws_list_ebs_snapshots region=%s owner=%s volume_id=%s", region, owner, volume_id,
    )
    try:
        filters = []
        if volume_id:
            filters.append({"Name": "volume-id", "Values": [volume_id]})
        resp = _ec2(region).describe_snapshots(
            OwnerIds=[owner],
            Filters=filters,
            MaxResults=max_results,
        )
        snaps = [
            {
                "snapshot_id": s["SnapshotId"],
                "volume_id": s.get("VolumeId"),
                "state": s.get("State"),
                "size_gib": s.get("VolumeSize"),
                "start_time": s.get("StartTime"),
                "progress": s.get("Progress"),
                "description": s.get("Description"),
                "encrypted": s.get("Encrypted", False),
                "kms_key_id": s.get("KmsKeyId"),
                "owner_id": s.get("OwnerId"),
                "tags": s.get("Tags", []),
            }
            for s in resp.get("Snapshots", [])
        ]
        return _ok({"region": region, "snapshot_count": len(snaps), "snapshots": snaps})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_ebs_snapshot(
    volume_id: str,
    description: str = "",
    region: str = "us-east-1",
    name_tag: str = "",
) -> str:
    """
    Create a snapshot of an EBS volume.

    Args:
        volume_id:   EBS volume ID to snapshot.
        description: Snapshot description.
        region:      AWS region (default 'us-east-1').
        name_tag:    Value for the 'Name' tag.

    Returns:
        JSON: snapshot_id, volume_id, state, start_time.
    """
    if not volume_id.strip():
        return _err("volume_id is required.", "VALIDATION_ERROR")
    logger.info("aws_create_ebs_snapshot volume_id=%s region=%s", volume_id, region)
    try:
        kwargs: dict[str, Any] = {"VolumeId": volume_id, "Description": description}
        if name_tag:
            kwargs["TagSpecifications"] = [{
                "ResourceType": "snapshot",
                "Tags": [{"Key": "Name", "Value": name_tag}],
            }]
        resp = _ec2(region).create_snapshot(**kwargs)
        return _ok({
            "snapshot_id": resp["SnapshotId"],
            "volume_id": resp["VolumeId"],
            "state": resp["State"],
            "start_time": resp.get("StartTime"),
            "description": resp.get("Description"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_ebs_snapshot(
    snapshot_id: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete an EBS snapshot.

    Args:
        snapshot_id: Snapshot ID to delete.
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: snapshot_id, message.
    """
    if not snapshot_id.strip():
        return _err("snapshot_id is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_ebs_snapshot snapshot_id=%s region=%s", snapshot_id, region)
    try:
        _ec2(region).delete_snapshot(SnapshotId=snapshot_id)
        return _ok({"snapshot_id": snapshot_id, "message": "Snapshot deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_copy_ebs_snapshot(
    snapshot_id: str,
    source_region: str,
    destination_region: str,
    description: str = "",
    encrypted: bool = False,
) -> str:
    """
    Copy an EBS snapshot to another region.

    Args:
        snapshot_id:         Source snapshot ID.
        source_region:       Region where the snapshot currently lives.
        destination_region:  Target region for the copy.
        description:         Description for the copied snapshot.
        encrypted:           Encrypt the copy (default False).

    Returns:
        JSON: new_snapshot_id in the destination region.
    """
    if not snapshot_id.strip() or not source_region.strip() or not destination_region.strip():
        return _err("snapshot_id, source_region, and destination_region are required.", "VALIDATION_ERROR")
    logger.info(
        "aws_copy_ebs_snapshot snapshot_id=%s %s -> %s", snapshot_id, source_region, destination_region,
    )
    try:
        resp = boto3.client("ec2", region_name=destination_region).copy_snapshot(
            SourceRegion=source_region,
            SourceSnapshotId=snapshot_id,
            Description=description,
            Encrypted=encrypted,
        )
        return _ok({
            "new_snapshot_id": resp["SnapshotId"],
            "source_snapshot_id": snapshot_id,
            "source_region": source_region,
            "destination_region": destination_region,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


# ===========================================================================
# PLACEMENT GROUPS
# ===========================================================================

@mcp.tool()
def aws_list_placement_groups(
    region: str = "us-east-1",
) -> str:
    """
    List EC2 placement groups in a region.

    Args:
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: placement_group_count, placement_groups
              (each: name, strategy, state, partition_count).
    """
    logger.info("aws_list_placement_groups region=%s", region)
    try:
        resp = _ec2(region).describe_placement_groups()
        groups = [
            {
                "name": pg["GroupName"],
                "group_id": pg.get("GroupId"),
                "strategy": pg.get("Strategy"),
                "state": pg.get("State"),
                "partition_count": pg.get("PartitionCount"),
                "tags": pg.get("Tags", []),
            }
            for pg in resp.get("PlacementGroups", [])
        ]
        return _ok({
            "region": region,
            "placement_group_count": len(groups),
            "placement_groups": groups,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_create_placement_group(
    name: str,
    strategy: str = "cluster",
    region: str = "us-east-1",
    partition_count: int = 0,
) -> str:
    """
    Create an EC2 placement group.

    Args:
        name:            Placement group name.
        strategy:        'cluster', 'spread', or 'partition' (default 'cluster').
        region:          AWS region (default 'us-east-1').
        partition_count: Number of partitions (only for 'partition' strategy; 0 = use default).

    Returns:
        JSON: name, strategy, state.
    """
    _VALID = {"cluster", "spread", "partition"}
    if strategy not in _VALID:
        return _err(f"strategy must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")
    if not name.strip():
        return _err("name is required.", "VALIDATION_ERROR")
    logger.info(
        "aws_create_placement_group name=%r strategy=%s region=%s", name, strategy, region,
    )
    try:
        kwargs: dict[str, Any] = {"GroupName": name, "Strategy": strategy}
        if strategy == "partition" and partition_count > 0:
            kwargs["PartitionCount"] = partition_count
        resp = _ec2(region).create_placement_group(**kwargs)
        pg = resp.get("PlacementGroup", {})
        return _ok({
            "name": pg.get("GroupName"),
            "strategy": pg.get("Strategy"),
            "state": pg.get("State"),
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_placement_group(
    name: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete an EC2 placement group (must have no instances).

    Args:
        name:   Placement group name.
        region: AWS region (default 'us-east-1').

    Returns:
        JSON: name, message.
    """
    if not name.strip():
        return _err("name is required.", "VALIDATION_ERROR")
    logger.info("aws_delete_placement_group name=%r region=%s", name, region)
    try:
        _ec2(region).delete_placement_group(GroupName=name)
        return _ok({"name": name, "message": "Placement group deleted."})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
