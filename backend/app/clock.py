"""Time helpers. Services never read the clock; routers pass ``now`` in.

Datetimes are stored as naive UTC because SQLite drops tzinfo. "Today" for
streaks and the daily goal is the calendar date in ``APP_TIMEZONE``.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_date(now: datetime, tz_name: str | None = None) -> date:
    """Calendar date in the app timezone for a naive-UTC ``now``."""
    tz = ZoneInfo(tz_name or settings.APP_TIMEZONE)
    return now.replace(tzinfo=timezone.utc).astimezone(tz).date()
