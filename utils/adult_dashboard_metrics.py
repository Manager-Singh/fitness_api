"""Shared adult dashboard height / habit metrics (ledger-backed)."""

from django.db.models import Sum

from habits.models import MicroHabitLog
from user_profile.models import UserProfile
from users.models import DailyLog, HeightLedger
from users.spec_runtime import LEDGER_ENTRY_DAILY_COMPUTE, get_user_runtime_state_snapshot
from utils.posture.height_constants import POINTS_TO_CM_ENGINE1
from utils.user_time import user_today


def adult_base_height_cm(user) -> float:
    try:
        prof = UserProfile.objects.filter(user=user).only("base_height_cm", "current_height_cm").first()
        if prof and prof.base_height_cm not in (None, ""):
            return float(prof.base_height_cm)
        if prof and prof.current_height_cm not in (None, ""):
            return float(prof.current_height_cm)
    except Exception:
        pass
    return 0.0


def live_cumulative_gain_cm(user) -> float:
    """Engine cumulative gain in cm (not absolute height)."""
    runtime = get_user_runtime_state_snapshot(user) or {}
    cum = runtime.get("current_height_um")
    if cum is not None:
        return round(max(0, int(cum)) / 10000.0, 4)
    row = (
        HeightLedger.objects.filter(user=user, entry_type=LEDGER_ENTRY_DAILY_COMPUTE)
        .order_by("-log_date", "-created_at")
        .only("cumulative_um")
        .first()
    )
    if row:
        return round(max(0, int(row.cumulative_um or 0)) / 10000.0, 4)
    return 0.0


def live_height_cm(user) -> float:
    return round(adult_base_height_cm(user) + live_cumulative_gain_cm(user), 4)


def count_habits_logged(user, log_date=None) -> int:
    log_date = log_date or user_today(user)
    return MicroHabitLog.objects.filter(user=user, log_date=log_date).count()


def adult_engine1_points_today(user, log_date=None) -> int:
    log_date = log_date or user_today(user)
    daily = DailyLog.objects.filter(user=user, log_date=log_date).only("engine1_points").first()
    return int((daily.engine1_points if daily else 0) or 0)


def adult_daily_gains_cm_today(user, log_date=None, *, conversion_enabled: bool = True) -> float:
    if not conversion_enabled:
        return 0.0
    return round(adult_engine1_points_today(user, log_date) * POINTS_TO_CM_ENGINE1, 4)


def adult_chart_series(user, target_height_cm: float, days_window: int = 90) -> list:
    """Days-based chart: absolute height = base + ledger cumulative gain per day."""
    base_cm = adult_base_height_cm(user)
    rows = list(
        HeightLedger.objects.filter(user=user, entry_type=LEDGER_ENTRY_DAILY_COMPUTE)
        .order_by("-log_date", "-created_at")[:days_window]
    )
    rows = list(reversed(rows))
    if not rows:
        h = live_height_cm(user)
        return [
            {
                "day": 0,
                "date": str(user_today(user)),
                "current_height_cm": round(h, 4),
                "target_height_cm": round(float(target_height_cm), 4),
            }
        ]
    series = []
    for idx, r in enumerate(rows):
        gain_cm = float(r.cumulative_um or 0) / 10000.0
        series.append(
            {
                "day": idx,
                "date": str(r.log_date),
                "current_height_cm": round(base_cm + gain_cm, 4),
                "target_height_cm": round(float(target_height_cm), 4),
            }
        )
    return series
