from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from typing import Any

TSR_REPEAT_TERM_MONTHS: dict[str, int] = {
    "8-01-01": 3, "8-01-02": 3, "8-06-04": 3,
    "8-06-03": 12, "8-08-05": 12, "8-08-06": 12, "8-08-07": 12,
    "8-01-03": 24, "8-01-04": 24, "8-02-01": 24, "8-02-02": 24,
    "8-02-03": 24, "8-03-01": 24, "8-03-02": 24, "8-03-03": 24,
    "8-07-01": 24, "8-07-09": 24, "8-07-10": 24, "8-07-11": 24,
    "8-04-01": 24, "8-07-12": 24, "8-07-13": 24, "8-07-14": 24,
    "8-07-04": 36, "8-07-05": 36, "8-04-02": 36, "8-04-03": 36,
    "8-05-01": 36,
}


def normalize_tsr_code(value: Any) -> str:
    raw = str(value or "").strip().replace("–", "-").replace("—", "-")
    match = re.match(r"^\s*(8(?:\(1\)|\.1)?-\d{2}(?:-\d{2})?)", raw, flags=re.I)
    if not match:
        return ""
    return re.sub(r"^8(?:\(1\)|\.1)-", "8-", match.group(1), flags=re.I)


def get_repeat_term_months(value: Any) -> int | None:
    return TSR_REPEAT_TERM_MONTHS.get(normalize_tsr_code(value))


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def calculate_repeat_visit_date(tsr_code: Any, check_date: Any) -> date | None:
    months = get_repeat_term_months(tsr_code)
    source = _as_date(check_date)
    if months is None or source is None:
        return None
    month_index = source.month - 1 + months
    target_year = source.year + month_index // 12
    target_month = month_index % 12 + 1
    target_day = min(source.day, calendar.monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day)
