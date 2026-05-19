"""
Embed full GET /api/dashboard-new payload in log POST responses (workout-logs, nutra-logs).
"""
import logging

from django.test import RequestFactory
from rest_framework import status
from rest_framework.request import Request

logger = logging.getLogger(__name__)

_SEGMENT_LONG_KEYS = {
    "spinal": "spinal_compression",
    "collapse": "posture_collapse",
    "pelvic": "pelvic_tilt_back",
    "legs": "leg_hamstring",
}


def _patch_adult_live_dashboard(dashboard: dict, user, log_date) -> None:
    """Overlay ledger-backed adult metrics after a same-day log + rebuild."""
    from utils.adult_dashboard_live import build_adult_dashboard_live_payload

    live = build_adult_dashboard_live_payload(user, log_date)
    if not live or dashboard.get("variant") != "adult":
        return

    dashboard["live_metrics"] = {
        **(dashboard.get("live_metrics") or {}),
        "height_cm": live["current_height_cm"],
        "total_recovered_cm": live["total_recovered_cm"],
        "daily_gains_cm": live["today_total_gain_cm"],
    }

    rp = dict(dashboard.get("routine_progress") or {})
    rp["daily_points"] = live["today_daily_points"]
    dashboard["routine_progress"] = rp

    top_graph = dict(dashboard.get("top_graph") or {})
    cards = list(top_graph.get("cards") or [])
    for card in cards:
        key = card.get("key")
        if key == "height":
            card["value_cm"] = round(live["current_height_cm"], 3)
        elif key == "total_recovered":
            card["value_cm"] = round(live["total_recovered_cm"], 3)
        elif key == "daily_gains":
            card["value_cm"] = round(live["today_total_gain_cm"], 3)
    top_graph["cards"] = cards
    dashboard["top_graph"] = top_graph

    bars_percent = {}
    bars_percent_precise = {}
    raw_segments = dict((dashboard.get("posture_optimization") or {}).get("raw_segments") or {})
    for short, seg in (live.get("segments") or {}).items():
        long_key = _SEGMENT_LONG_KEYS.get(short, short)
        opt = float(seg.get("opt_pct", 0))
        loss = float(seg.get("loss_cm", 0))
        bars_percent[long_key] = int(opt)
        bars_percent_precise[long_key] = opt
        prev = raw_segments.get(long_key) or {}
        raw_segments[long_key] = {
            **prev,
            "current_loss_cm": loss,
            "percent_optimized": int(opt),
            "percent_optimized_precise": opt,
        }

    po = dict(dashboard.get("posture_optimization") or {})
    po["bars_percent"] = bars_percent
    po["bars_percent_precise"] = bars_percent_precise
    po["raw_segments"] = raw_segments
    po["total_current_loss_cm"] = round(sum(float(s.get("loss_cm", 0)) for s in live["segments"].values()), 2)
    dashboard["posture_optimization"] = po

    imp = dict(dashboard.get("important_data") or {})
    growth = dict(imp.get("growth_projection") or {})
    growth["current_height_cm"] = live["current_height_cm"]
    imp["growth_projection"] = growth
    rd = dict(imp.get("response_data") or {})
    rd["current_height_cm"] = live["current_height_cm"]
    rd["height_reclaimed_cm"] = live["total_recovered_cm"]
    target = float(rd.get("target_height_cm") or live["current_height_cm"])
    rd["remaining_cm"] = round(max(0.0, target - live["current_height_cm"]), 4)
    imp["response_data"] = rd
    dashboard["important_data"] = imp

    chart = dashboard.get("chart_breakdown")
    if isinstance(chart, dict) and chart.get("series"):
        series = list(chart["series"])
        if series:
            series[-1] = {
                **series[-1],
                "current_height_cm": round(live["total_recovered_cm"], 4),
            }
            chart["series"] = series
            dashboard["chart_breakdown"] = chart


def build_dashboard_new_embed(user, log_date=None, include_debug=False):
    """
    Return the same dict shape as GET /api/dashboard-new (message + dashboard).

    Returns None if the dashboard cannot be built (e.g. subscription expired).
    """
    from utils.user_time import user_today

    log_date = log_date or user_today(user)

    try:
        from posture_questions.views import get_dashboard_new
    except Exception:
        logger.exception("dashboard_new_embed: import get_dashboard_new failed")
        return None

    query = {}
    if include_debug:
        query["include_debug"] = "1"
    http_request = RequestFactory().get("/api/dashboard-new", query)
    http_request.user = user
    drf_request = Request(http_request)

    try:
        response = get_dashboard_new(drf_request)
    except Exception:
        logger.exception("dashboard_new_embed: get_dashboard_new failed", extra={"user_id": getattr(user, "id", None)})
        return None

    if int(getattr(response, "status_code", 500)) != status.HTTP_200_OK:
        return None

    data = dict(response.data or {})
    dashboard = data.get("dashboard")
    if isinstance(dashboard, dict):
        _patch_adult_live_dashboard(dashboard, user, log_date)
    return data
