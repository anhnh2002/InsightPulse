"""Day-window helpers: target-day math, ISO checks, relative-date parsing."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def yesterday_utc() -> date:
    return today_utc() - timedelta(days=1)


def parse_day(s: str) -> date:
    """Strict YYYY-MM-DD; raises ValueError."""
    return date.fromisoformat(s)


def iso_to_date(iso_ts: str) -> date | None:
    """UTC date of an ISO timestamp (offset-aware or naive=UTC); None if unparseable."""
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def in_day(iso_ts: str, day: date) -> bool:
    """True if an ISO timestamp falls on `day` (UTC)."""
    return iso_to_date(iso_ts) == day


# Relative post ages as shown by LinkedIn/X UIs, Vietnamese and English locales.
# Alternation order matters: "min" and "mo(nth)" must be tried before bare "m",
# "y(ea)r" before bare "y", so "5mo" is 5 months, not 5 minutes.
_REL = re.compile(
    r"(\d+)\s*"
    r"(phút|giờ|ngày|tuần|tháng|năm"
    r"|min(?:ute)?s?|h(?:ou)?rs?|h"
    r"|d(?:ay)?s?|w(?:eek)?s?"
    r"|mo(?:nth)?s?|y(?:ea)?rs?|y|m)\b",
    re.IGNORECASE,
)

_MIN_UNITS = {"phút", "m", "min", "mins", "minute", "minutes"}
_HOUR_UNITS = {"giờ", "h", "hr", "hrs", "hour", "hours"}
_DAY_MULT = {
    "ngày": 1, "d": 1, "day": 1, "days": 1,
    "tuần": 7, "w": 7, "week": 7, "weeks": 7,
    "tháng": 30, "mo": 30, "mos": 30, "month": 30, "months": 30,
    "năm": 365, "y": 365, "yr": 365, "yrs": 365, "year": 365, "years": 365,
}


# How far a resolved approx_date may actually sit from the true post day, given
# the precision of the relative age it came from ("2w" → ±3d, "1mo" → ±15d).
PRECISION_TOLERANCE_DAYS = {"day": 0, "week": 3, "month": 15, "unknown": 0}


def overlaps_window(approx: date, precision: str, start: date, end: date) -> bool:
    """True if a post's date-uncertainty band intersects [start, end]."""
    tol = timedelta(days=PRECISION_TOLERANCE_DAYS.get(precision, 0))
    return approx + tol >= start and approx - tol <= end


def parse_post_date(s: str, ref: datetime) -> date | None:
    """Resolve an absolute ("2026-07-28") or relative ("16 giờ", "2w") post date.

    Relative ages resolve against `ref` (the fetch time, UTC). Returns None when
    nothing parseable is found.
    """
    s = (s or "").strip().lower()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    m = _REL.search(s)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit in _MIN_UNITS:
        return ref.date()
    if unit in _HOUR_UNITS:
        return (ref - timedelta(hours=n)).date()
    mult = _DAY_MULT.get(unit) or _DAY_MULT.get(unit.rstrip("s"))
    if mult is None:
        return None
    return (ref - timedelta(days=n * mult)).date()
