from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_list_ec2_instances(
    region: str = "us-east-1",
    state: str = "all",
) -> str:
    """
    List EC2 instances in an AWS region, optionally filtered by state.

    Args:
        region: AWS region (default 'us-east-1').
        state:  'running', 'stopped', or 'all' (default).

    Returns:
        JSON: region, instance_count, instances
              (each: instance_id, instance_type, state, name, public_ip,
               private_ip, launch_time).
    """
    _VALID = {"running", "stopped", "all"}
    if state not in _VALID:
        return _err(f"state must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")
    logger.info("aws_list_ec2_instances region=%s state=%s", region, state)
    try:
        client = boto3.client("ec2", region_name=region)
        filters = [{"Name": "instance-state-name", "Values": [state]}] if state != "all" else []
        paginator = client.get_paginator("describe_instances")
        pages = paginator.paginate(Filters=filters) if filters else paginator.paginate()
        instances: list[dict[str, Any]] = []
        for page in pages:
            for rsv in page.get("Reservations", []):
                for inst in rsv.get("Instances", []):
                    name = next(
                        (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), None
                    )
                    instances.append({
                        "instance_id": inst.get("InstanceId"),
                        "instance_type": inst.get("InstanceType"),
                        "state": inst.get("State", {}).get("Name"),
                        "name": name,
                        "public_ip": inst.get("PublicIpAddress"),
                        "private_ip": inst.get("PrivateIpAddress"),
                        "launch_time": inst.get("LaunchTime"),
                    })
        return _ok({"region": region, "instance_count": len(instances), "instances": instances})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
