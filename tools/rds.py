from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_describe_rds_instances(
    region: str = "us-east-1",
) -> str:
    """
    List all RDS database instances in an AWS region.

    Args:
        region: AWS region to query (default 'us-east-1').

    Returns:
        JSON: region, instance_count, instances
              (each: db_instance_identifier, db_instance_class, engine,
               engine_version, status, endpoint, multi_az, storage_gb,
               publicly_accessible).
    """
    logger.info("aws_describe_rds_instances region=%s", region)
    try:
        paginator = boto3.client("rds", region_name=region).get_paginator(
            "describe_db_instances"
        )
        instances: list[dict[str, Any]] = []
        for page in paginator.paginate():
            for db in page.get("DBInstances", []):
                endpoint = db.get("Endpoint", {})
                instances.append({
                    "db_instance_identifier": db.get("DBInstanceIdentifier"),
                    "db_instance_class": db.get("DBInstanceClass"),
                    "engine": db.get("Engine"),
                    "engine_version": db.get("EngineVersion"),
                    "status": db.get("DBInstanceStatus"),
                    "endpoint": f"{endpoint.get('Address', '')}:{endpoint.get('Port', '')}",
                    "multi_az": db.get("MultiAZ", False),
                    "storage_gb": db.get("AllocatedStorage"),
                    "publicly_accessible": db.get("PubliclyAccessible", False),
                })
        return _ok({"region": region, "instance_count": len(instances), "instances": instances})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
