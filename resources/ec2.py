from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp


@mcp.resource("aws://ec2/{region}/instances")
def resource_ec2_instances(region: str) -> str:
    """
    All EC2 instances in the specified region with state and IP addresses.
    Attach this resource for a region-level compute inventory.
    URI pattern: aws://ec2/<region>/instances  (e.g. aws://ec2/us-east-1/instances)
    """
    logger.info("resource: aws://ec2/%s/instances", region)
    try:
        client = boto3.client("ec2", region_name=region)
        paginator = client.get_paginator("describe_instances")
        rows: list[str] = []
        for page in paginator.paginate():
            for rsv in page.get("Reservations", []):
                for inst in rsv.get("Instances", []):
                    name = next(
                        (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), "-"
                    )
                    rows.append(
                        f"- `{inst.get('InstanceId')}` | {inst.get('InstanceType')} | "
                        f"{inst.get('State', {}).get('Name')} | {name} | "
                        f"pub:{inst.get('PublicIpAddress', '-')} "
                        f"priv:{inst.get('PrivateIpAddress', '-')}"
                    )
        lines = [f"# EC2 Instances — {region}", f"Total: {len(rows)}", ""]
        lines += rows if rows else ["No instances found."]
        return "\n".join(lines)
    except (ClientError, BotoCoreError) as e:
        return f"Error fetching EC2 instances in {region}: {e}"
