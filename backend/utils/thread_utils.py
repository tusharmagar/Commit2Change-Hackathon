from __future__ import annotations

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo


def _safe_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def phone_hash(phone_number: str) -> str:
    digest = hashlib.sha256(phone_number.encode("utf-8")).hexdigest()
    return digest[:12]


def thread_id_for_day(phone_number: str, timezone_name: str) -> str:
    tz = _safe_timezone(timezone_name)
    local_date = datetime.now(tz).date().isoformat()
    return f"whatsapp:{phone_hash(phone_number)}:{local_date}"
