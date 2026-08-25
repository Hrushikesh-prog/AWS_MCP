from __future__ import annotations

from datetime import date

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_get_cost_and_usage(
    start_date: str = "",
    end_date: str = "",
    granularity: str = "MONTHLY",
) -> str:
    """
    Get AWS cost and usage for a date range using Cost Explorer.

    Args:
        start_date:  Start date YYYY-MM-DD (default: first day of current month).
        end_date:    End date YYYY-MM-DD (default: today).
        granularity: 'DAILY' or 'MONTHLY' (default 'MONTHLY').

    Returns:
        JSON: granularity, results — each with period, total_cost, currency,
              and service_breakdown sorted by cost descending.
    """
    today = date.today()
    if not start_date:
        start_date = today.replace(day=1).isoformat()
    if not end_date:
        end_date = today.isoformat()

    _VALID = {"DAILY", "MONTHLY"}
    if granularity not in _VALID:
        return _err(f"granularity must be one of {sorted(_VALID)}.", "VALIDATION_ERROR")

    logger.info(
        "aws_get_cost_and_usage start=%s end=%s granularity=%s",
        start_date, end_date, granularity,
    )
    try:
        client = boto3.client("ce", region_name="us-east-1")
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity=granularity,
            Metrics=["BlendedCost", "UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        results = []
        for result in response.get("ResultsByTime", []):
            groups = []
            for group in result.get("Groups", []):
                cost = group["Metrics"].get("UnblendedCost", {})
                amount = float(cost.get("Amount", 0))
                if amount > 0:
                    groups.append({
                        "service": group["Keys"][0],
                        "cost": round(amount, 4),
                        "currency": cost.get("Unit", "USD"),
                    })
            groups.sort(key=lambda x: x["cost"], reverse=True)
            total = result.get("Total", {}).get("BlendedCost", {})
            results.append({
                "period": result["TimePeriod"],
                "total_cost": round(float(total.get("Amount", 0)), 4),
                "currency": total.get("Unit", "USD"),
                "service_breakdown": groups,
            })
        return _ok({"granularity": granularity, "results": results})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_get_free_tier_usage() -> str:
    """
    Get AWS Free Tier usage for the current month.

    Returns:
        JSON: count, free_tier_usage — each entry has service, operation,
              actual_usage, forecasted_usage, limit, and unit.
    """
    logger.info("aws_get_free_tier_usage")
    try:
        client = boto3.client("freetier", region_name="us-east-1")
        paginator = client.get_paginator("get_free_tier_usage")
        items = []
        for page in paginator.paginate():
            for item in page.get("freeTierUsages", []):
                items.append({
                    "service": item.get("serviceName"),
                    "operation": item.get("operationName"),
                    "usage_type": item.get("usageType"),
                    "actual_usage": item.get("actualUsageAmount"),
                    "forecasted_usage": item.get("forecastedUsageAmount"),
                    "limit": item.get("limit"),
                    "unit": item.get("unit"),
                    "description": item.get("description"),
                })
        items.sort(key=lambda x: (x.get("actual_usage") or 0), reverse=True)
        return _ok({"count": len(items), "free_tier_usage": items})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
