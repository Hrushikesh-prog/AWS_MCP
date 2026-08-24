from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ms_to_iso, _ok


@mcp.tool()
def aws_get_cloudwatch_logs(
    log_group_name: str,
    region: str = "us-east-1",
    limit: int = 25,
    filter_pattern: str = "",
) -> str:
    """
    Fetch recent log events from an AWS CloudWatch Logs group.

    Args:
        log_group_name: Full name of the CloudWatch log group. (required)
        region:         AWS region (default 'us-east-1').
        limit:          Max events to return; default 25, capped at 200.
        filter_pattern: CloudWatch filter syntax, e.g. 'ERROR'. (optional)

    Returns:
        JSON: log_group, region, event_count, events
              (each: timestamp (ISO-8601 UTC), message, log_stream_name).
    """
    if not log_group_name or not log_group_name.strip():
        return _err("log_group_name must be a non-empty string.", "VALIDATION_ERROR")
    limit = max(1, min(int(limit), 200))
    logger.info("aws_get_cloudwatch_logs group=%s region=%s limit=%d filter=%r",
                log_group_name, region, limit, filter_pattern)
    try:
        kwargs: dict[str, Any] = {"logGroupName": log_group_name, "limit": limit}
        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern
        resp = boto3.client("logs", region_name=region).filter_log_events(**kwargs)
        events = [
            {
                "timestamp": _ms_to_iso(e["timestamp"]),
                "message": e.get("message", ""),
                "log_stream_name": e.get("logStreamName", ""),
            }
            for e in resp.get("events", [])
        ]
        return _ok({"log_group": log_group_name, "region": region,
                    "event_count": len(events), "events": events})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
