from __future__ import annotations

from datetime import date
from typing import Any

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

    logger.info("aws_get_cost_and_usage start=%s end=%s granularity=%s", start_date, end_date, granularity)
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
def aws_get_cost_forecast(
    start_date: str = "",
    end_date: str = "",
    granularity: str = "MONTHLY",
    metric: str = "UNBLENDED_COST",
) -> str:
    """
    Get a Cost Explorer forecast for future AWS spend.

    Args:
        start_date:  Forecast start date YYYY-MM-DD (default: tomorrow).
        end_date:    Forecast end date YYYY-MM-DD (default: last day of current month).
        granularity: 'DAILY' or 'MONTHLY' (default 'MONTHLY').
        metric:      'UNBLENDED_COST', 'BLENDED_COST', or 'NET_UNBLENDED_COST'.

    Returns:
        JSON: total_forecast, unit, forecast_by_period.
    """
    today = date.today()
    import calendar
    if not start_date:
        import datetime
        start_date = (today + datetime.timedelta(days=1)).isoformat()
    if not end_date:
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = today.replace(day=last_day).isoformat()

    logger.info("aws_get_cost_forecast start=%s end=%s", start_date, end_date)
    try:
        client = boto3.client("ce", region_name="us-east-1")
        resp = client.get_cost_forecast(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity=granularity,
            Metric=metric,
        )
        total = resp.get("Total", {})
        by_period = [
            {
                "period": r["TimePeriod"],
                "mean_value": round(float(r.get("MeanValue", 0)), 4),
                "prediction_interval_lower": round(float(r.get("PredictionIntervalLowerBound", 0)), 4),
                "prediction_interval_upper": round(float(r.get("PredictionIntervalUpperBound", 0)), 4),
            }
            for r in resp.get("ForecastResultsByTime", [])
        ]
        return _ok({
            "total_forecast": round(float(total.get("Amount", 0)), 4),
            "unit": total.get("Unit", "USD"),
            "forecast_by_period": by_period,
        })
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")


@mcp.tool()
def aws_list_budgets(
    account_id: str = "",
) -> str:
    """
    List AWS Budgets for the account.

    Args:
        account_id: AWS account ID (default: auto-detected from STS).

    Returns:
        JSON: budget_count, budgets — each with name, type, limit, actual spend,
              forecasted spend, and alert thresholds.
    """
    logger.info("aws_list_budgets account_id=%s", account_id or "auto")
    try:
        if not account_id:
            account_id = boto3.client("sts").get_caller_identity()["Account"]
        client = boto3.client("budgets", region_name="us-east-1")
        paginator = client.get_paginator("describe_budgets")
        budgets: list[dict[str, Any]] = []
        for page in paginator.paginate(AccountId=account_id):
            for b in page.get("Budgets", []):
                limit = b.get("BudgetLimit", {})
                actual = b.get("CalculatedSpend", {}).get("ActualSpend", {})
                forecast = b.get("CalculatedSpend", {}).get("ForecastedSpend", {})
                budgets.append({
                    "name": b.get("BudgetName"),
                    "type": b.get("BudgetType"),
                    "time_unit": b.get("TimeUnit"),
                    "limit_amount": limit.get("Amount"),
                    "limit_unit": limit.get("Unit"),
                    "actual_spend": actual.get("Amount"),
                    "forecasted_spend": forecast.get("Amount"),
                    "last_updated": b.get("LastUpdatedTime"),
                })
        return _ok({"budget_count": len(budgets), "budgets": budgets})
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
        items: list[dict[str, Any]] = []
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
