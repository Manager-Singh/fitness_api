"""Ledger-backed today metrics for log-response dashboard embed (matches /dashboard-new section5)."""
from __future__ import annotations

from users.models import DailyLog, HeightLedger
from users.spec_runtime import LEDGER_ENTRY_DAILY_COMPUTE
from utils.adult_dashboard_metrics import (
    adult_base_height_cm,
    live_cumulative_gain_cm,
    live_height_cm,
)
from utils.posture.height_constants import POINTS_TO_CM_ENGINE1, POINTS_TO_CM_ENGINE2


def _ledger_today_deltas_cm(user, log_date) -> tuple[float, float, float]:
    """Return (engine1_cm, engine2_cm, bio_cm) for log_date from HeightLedger rows."""
    e1_um = bio_um = e2_dm = 0
    for row in HeightLedger.objects.filter(
        user=user,
        log_date=log_date,
        entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
    ).only("engine1_delta_um", "bio_delta_um", "engine2_delta_dm"):
        e1_um += int(row.engine1_delta_um or 0)
        bio_um += int(row.bio_delta_um or 0)
        e2_dm += int(row.engine2_delta_dm or 0)
    return (
        e1_um / 10000.0,
        float(e2_dm) / 100000.0,
        bio_um / 10000.0,
    )


def _dailylog_today_fallback_cm(user, log_date) -> tuple[float, float, float]:
    """Fallback when ledger row not yet visible (should be rare after rebuild_ledger)."""
    daily = DailyLog.objects.filter(user=user, log_date=log_date).only(
        "engine1_points", "engine2_points", "daily_genetic_average_gain_cm"
    ).first()
    if not daily:
        return 0.0, 0.0, 0.0
    e1 = float(int(daily.engine1_points or 0)) * POINTS_TO_CM_ENGINE1
    e2 = float(int(daily.engine2_points or 0)) * POINTS_TO_CM_ENGINE2
    bio = float(daily.daily_genetic_average_gain_cm or 0)
    return e1, e2, bio


def teen_today_dashboard_metrics(user, log_date) -> dict:
    """
    Today's Genetic+, Posture+, Daily Gains, and live height for teen log embed.
    Mirrors section5_contract in build_dashboard_base_payload.
    """
    e1, e2, bio = _ledger_today_deltas_cm(user, log_date)
    if e1 == 0.0 and e2 == 0.0 and bio == 0.0:
        e1, e2, bio = _dailylog_today_fallback_cm(user, log_date)

    posture_plus = round(e1, 4)
    genetic_plus = round(e2 + bio, 4)
    daily_gains = round(e1 + e2 + bio, 4)
    base_cm = adult_base_height_cm(user)
    height_cm = live_height_cm(user)
    cum_cm = live_cumulative_gain_cm(user)

    return {
        "posture_plus_today_cm": posture_plus,
        "genetic_plus_today_cm": genetic_plus,
        "daily_gains_cm": daily_gains,
        "height_cm": height_cm,
        "base_height_cm": round(base_cm, 4),
        "genetic_cumulative_cm": round(cum_cm * 0.5, 4),  # display helper; cards use today only
        "postureplus_cumulative_cm": round(cum_cm, 4),
        "genetic_blue_cm": round(base_cm + cum_cm * 0.5, 4),
        "us_optimized_red_cm": height_cm,
    }


def teen_top_cards_from_metrics(metrics: dict) -> list:
    return [
        {
            "key": "genetic_plus",
            "label": "Genetic +",
            "value_cm": round(metrics["genetic_plus_today_cm"], 3),
        },
        {
            "key": "posture_plus",
            "label": "Posture+",
            "value_cm": round(metrics["posture_plus_today_cm"], 3),
        },
        {
            "key": "daily_gains",
            "label": "Daily Gains",
            "value_cm": round(metrics["daily_gains_cm"], 3),
        },
        {
            "key": "height",
            "label": "Height",
            "value_cm": round(metrics["height_cm"], 3),
        },
    ]
