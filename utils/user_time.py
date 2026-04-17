from datetime import datetime, date
from zoneinfo import ZoneInfo

from django.utils import timezone


def get_user_tz(user):
    tz_name = str(getattr(user, "timezone", "") or "UTC")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def user_now(user) -> datetime:
    return timezone.now().astimezone(get_user_tz(user))


def user_today(user) -> date:
    return user_now(user).date()


def user_localize_dt(user, dt_utc: datetime) -> datetime:
    return dt_utc.astimezone(get_user_tz(user))
