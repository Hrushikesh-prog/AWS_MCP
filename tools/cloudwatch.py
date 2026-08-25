from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ms_to_iso, _ok


@mcp.tool()
def aws_list_cloudwatch_alarms(
    region: str = "us-east-1",
    state: str = "all",
) -> str:
    """
    List CloudWatch metric alarms with their state, metric, dimensions, and actions.

    Args:
        region: AWS region (default 'us-east-1').
        state:  'OK', 'ALARM', 'INSUFFICIENT_DATA', or 'all' (default).

    Returns:
        JSON: region, alarm_count, alarms — each with name, state, description,
              metric_name, namespace, dimensions, actions_enabled,
              alarm_actions, ok_actions, last_updated.
    """
    _VALID = {"OK", "ALARM", "INSUFFICIENT_DATA", "all"}
    if state not in _VALID:
        return _err(f"state must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")

    logger.info("aws_list_cloudwatch_alarms region=%s state=%s", region, state)
    try:
        client = boto3.client("cloudwatch", region_name=region)
        kwargs: dict[str, Any] = {}
        if state != "all":
            kwargs["StateValue"] = state

        paginator = client.get_paginator("describe_alarms")
        alarms = []
        for page in paginator.paginate(AlarmTypes=["MetricAlarm"], **kwargs):
            for alarm in page.get("MetricAlarms", []):
                alarms.append({
                    "name": alarm.get("AlarmName"),
                    "state": alarm.get("StateValue"),
                    "description": alarm.get("AlarmDescription") or "",
                    "metric_name": alarm.get("MetricName"),
                    "namespace": alarm.get("Namespace"),
                    "dimensions": [
                        {"name": d["Name"], "value": d["Value"]}
                        for d in alarm.get("Dimensions", [])
                    ],
                    "actions_enabled": alarm.get("ActionsEnabled"),
                    "alarm_actions": alarm.get("AlarmActions", []),
                    "ok_actions": alarm.get("OKActions", []),
                    "last_updated": alarm.get("StateUpdatedTimestamp"),
                })
        return _ok({"region": region, "alarm_count": len(alarms), "alarms": alarms})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_delete_cloudwatch_alarm(
    alarm_name: str,
    region: str = "us-east-1",
) -> str:
    """
    Delete a CloudWatch alarm by name.

    Args:
        alarm_name: Exact name of the alarm to delete. (required)
        region:     AWS region (default 'us-east-1').

    Returns:
        JSON: alarm_name, region, deleted (bool).
    """
    if not alarm_name or not alarm_name.strip():
        return _err("alarm_name must be a non-empty string.", "VALIDATION_ERROR")

    logger.info("aws_delete_cloudwatch_alarm name=%s region=%s", alarm_name, region)
    try:
        boto3.client("cloudwatch", region_name=region).delete_alarms(AlarmNames=[alarm_name])
        return _ok({"alarm_name": alarm_name, "region": region, "deleted": True})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


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
