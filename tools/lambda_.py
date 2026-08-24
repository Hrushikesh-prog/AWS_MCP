from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from server import logger, mcp
from utils.serializers import _err, _ok


@mcp.tool()
def aws_list_lambda_functions(
    region: str = "us-east-1",
) -> str:
    """
    List all Lambda functions in an AWS region.

    Args:
        region: AWS region to query (default 'us-east-1').

    Returns:
        JSON: region, function_count, functions
              (each: name, runtime, handler, memory_mb, timeout_secs,
               last_modified, description).
    """
    logger.info("aws_list_lambda_functions region=%s", region)
    try:
        paginator = boto3.client("lambda", region_name=region).get_paginator("list_functions")
        functions: list[dict[str, Any]] = []
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                functions.append({
                    "name": fn.get("FunctionName"),
                    "runtime": fn.get("Runtime"),
                    "handler": fn.get("Handler"),
                    "memory_mb": fn.get("MemorySize"),
                    "timeout_secs": fn.get("Timeout"),
                    "last_modified": fn.get("LastModified"),
                    "description": fn.get("Description", ""),
                })
        return _ok({"region": region, "function_count": len(functions), "functions": functions})
    except ClientError as e:
        return _err(str(e), e.response["Error"]["Code"])
    except BotoCoreError as e:
        return _err(str(e), "BOTOCORE_ERROR")
