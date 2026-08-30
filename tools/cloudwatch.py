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
        JSON: region, alarm_count, alarms — each with name, state, metric_name,
              namespace, dimensions, alarm_actions, ok_actions, last_updated.
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
    Fetch recent log events from a CloudWatch Logs group.

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
    logger.info(
        "aws_get_cloudwatch_logs group=%s region=%s limit=%d filter=%r",
        log_group_name, region, limit, filter_pattern,
    )
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


@mcp.tool()
def aws_list_cloudwatch_log_groups(
    region: str = "us-east-1",
    prefix: str = "",
    max_results: int = 50,
) -> str:
    """
    List CloudWatch Logs log groups in a region.

    Args:
        region:      AWS region (default 'us-east-1').
        prefix:      Filter groups by name prefix (optional).
        max_results: Max groups to return; default 50, capped at 200.

    Returns:
        JSON: region, log_group_count, log_groups
              (each: name, retained_days, stored_bytes, creation_time).
    """
    max_results = max(1, min(int(max_results), 200))
    logger.info("aws_list_cloudwatch_log_groups region=%s prefix=%r", region, prefix)
    try:
        client = boto3.client("logs", region_name=region)
        kwargs: dict[str, Any] = {}
        if prefix:
            kwargs["logGroupNamePrefix"] = prefix
        paginator = client.get_paginator("describe_log_groups")
        groups: list[dict[str, Any]] = []
        for page in paginator.paginate(**kwargs):
            for lg in page.get("logGroups", []):
                groups.append({
                    "name": lg.get("logGroupName"),
                    "retained_days": lg.get("retentionInDays"),
                    "stored_bytes": lg.get("storedBytes"),
                    "creation_time": _ms_to_iso(lg["creationTime"]) if lg.get("creationTime") else None,
                    "metric_filter_count": lg.get("metricFilterCount", 0),
                    "kms_key_id": lg.get("kmsKeyId"),
                })
            if len(groups) >= max_results:
                groups = groups[:max_results]
                break
        return _ok({"region": region, "log_group_count": len(groups), "log_groups": groups})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_cloudwatch_log_streams(
    log_group_name: str,
    region: str = "us-east-1",
    max_results: int = 20,
    order_by: str = "LastEventTime",
) -> str:
    """
    List log streams within a CloudWatch Logs group.

    Args:
        log_group_name: Name of the log group. (required)
        region:         AWS region (default 'us-east-1').
        max_results:    Max streams to return; default 20, capped at 50.
        order_by:       'LastEventTime' (newest first, default) or 'LogStreamName'.

    Returns:
        JSON: log_group, stream_count, log_streams
              (each: name, last_event_time, creation_time, stored_bytes).
    """
    if not log_group_name or not log_group_name.strip():
        return _err("log_group_name must be a non-empty string.", "VALIDATION_ERROR")
    max_results = max(1, min(int(max_results), 50))
    logger.info("aws_list_cloudwatch_log_streams group=%s region=%s", log_group_name, region)
    try:
        resp = boto3.client("logs", region_name=region).describe_log_streams(
            logGroupName=log_group_name,
            orderBy=order_by,
            descending=True,
            limit=max_results,
        )
        streams = [
            {
                "name": s.get("logStreamName"),
                "last_event_time": _ms_to_iso(s["lastEventTimestamp"]) if s.get("lastEventTimestamp") else None,
                "creation_time": _ms_to_iso(s["creationTime"]) if s.get("creationTime") else None,
                "stored_bytes": s.get("storedBytes"),
                "first_event_time": _ms_to_iso(s["firstEventTimestamp"]) if s.get("firstEventTimestamp") else None,
            }
            for s in resp.get("logStreams", [])
        ]
        return _ok({"log_group": log_group_name, "stream_count": len(streams), "log_streams": streams})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_cloudwatch_metric_statistics(
    namespace: str,
    metric_name: str,
    dimensions: list[dict] | None = None,
    start_time: str = "",
    end_time: str = "",
    period: int = 3600,
    statistics: list[str] | None = None,
    region: str = "us-east-1",
) -> str:
    """
    Retrieve CloudWatch metric statistics for a given metric.

    Args:
        namespace:   Metric namespace (e.g. 'AWS/EC2'). (required)
        metric_name: Metric name (e.g. 'CPUUtilization'). (required)
        dimensions:  List of {"Name": "...", "Value": "..."} dicts. (optional)
        start_time:  ISO-8601 start time (default: 1 hour ago).
        end_time:    ISO-8601 end time (default: now).
        period:      Aggregation period in seconds (default 3600).
        statistics:  List of stats: 'Average','Sum','Minimum','Maximum','SampleCount'.
                     Default: ['Average'].
        region:      AWS region (default 'us-east-1').

    Returns:
        JSON: namespace, metric_name, datapoints sorted by timestamp ascending.
    """
    from datetime import datetime, timezone, timedelta
    if not namespace.strip() or not metric_name.strip():
        return _err("namespace and metric_name are required.", "VALIDATION_ERROR")
    now = datetime.now(timezone.utc)
    start_dt = datetime.fromisoformat(start_time) if start_time else now - timedelta(hours=1)
    end_dt = datetime.fromisoformat(end_time) if end_time else now
    stats = statistics or ["Average"]
    dims = dimensions or []
    logger.info(
        "aws_get_cloudwatch_metric_statistics ns=%s metric=%s region=%s",
        namespace, metric_name, region,
    )
    try:
        resp = boto3.client("cloudwatch", region_name=region).get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dims,
            StartTime=start_dt,
            EndTime=end_dt,
            Period=period,
            Statistics=stats,
        )
        datapoints = sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"])
        return _ok({
            "namespace": namespace,
            "metric_name": metric_name,
            "period_seconds": period,
            "datapoint_count": len(datapoints),
            "datapoints": datapoints,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
