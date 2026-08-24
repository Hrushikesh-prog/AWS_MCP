from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from server import logger


def _serialize(obj: Any) -> Any:
    """Recursively convert AWS SDK types to JSON-serializable Python types."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    return obj


def _ok(data: Any) -> str:
    return json.dumps({"status": "success", "data": _serialize(data)}, indent=2)


def _err(message: str, code: str = "AWS_ERROR") -> str:
    logger.error("[%s] %s", code, message)
    return json.dumps(
        {"status": "error", "error": {"code": code, "message": message}},
        indent=2,
    )


def _ms_to_iso(epoch_ms: int) -> str:
    """Convert epoch-milliseconds to an ISO-8601 UTC string."""
    return datetime.utcfromtimestamp(epoch_ms / 1000).isoformat() + "Z"
