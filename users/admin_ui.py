"""Admin UI helpers — badges, progress dashboard HTML."""
from __future__ import annotations

from django.urls import reverse
from django.utils.html import format_html

from users.models import DailyLog, HeightLedger
from users.spec_runtime import get_user_runtime_state_snapshot
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct
from utils.user_time import user_today


def um_to_cm(um) -> float:
    try:
        return int(um or 0) / 10000.0
    except (TypeError, ValueError):
        return 0.0


def fmt_cm(um) -> str:
    return f"{um_to_cm(um):.3f}"


def badge(text: str, *, color: str = "#64748b", bg: str = "#f1f5f9") -> str:
    return format_html(
        '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        'font-size:11px;font-weight:600;color:{};background:{};white-space:nowrap;">{}</span>',
        color,
        bg,
        text,
    )


def badge_bool(value: bool, yes: str = "Yes", no: str = "No") -> str:
    if value:
        return badge(yes, color="#166534", bg="#dcfce7")
    return badge(no, color="#991b1b", bg="#fee2e2")


def badge_tier(tier: str | None) -> str:
    t = (tier or "").lower()
    if t == "teen":
        return badge("Teen", color="#1e40af", bg="#dbeafe")
    if t == "adult":
        return badge("Adult", color="#6b21a8", bg="#f3e8ff")
    return badge("—", color="#64748b", bg="#f1f5f9")


def badge_points(value, *, highlight: bool = False) -> str:
    if value in (None, "—"):
        return badge("—")
    if highlight:
        return badge(str(value), color="#0f766e", bg="#ccfbf1")
    return badge(str(value), color="#334155", bg="#e2e8f0")


def _stat_card(title: str, value: str, subtitle: str = "", *, accent: str = "#0ea5e9") -> str:
    return format_html(
        '<div class="hm-stat-card" style="border-left:4px solid {};">'
        '<div class="hm-stat-label">{}</div>'
        '<div class="hm-stat-value">{}</div>'
        '<div class="hm-stat-sub">{}</div></div>',
        accent,
        title,
        value,
        subtitle,
    )


def _segment_bars(state) -> str:
    if not state:
        return ""
    mapping = [
        ("Spinal", "spinal_current_loss_um", "spinal_compression"),
        ("Collapse", "collapse_current_loss_um", "posture_collapse"),
        ("Pelvic", "pelvic_current_loss_um", "pelvic_tilt_back"),
        ("Legs", "legs_current_loss_um", "leg_hamstring"),
    ]
    rows = []
    for label, attr, key in mapping:
        max_cm = float(POSTURE_SEGMENT_MAX_LOSS_CM.get(key, 1))
        loss_cm = um_to_cm(getattr(state, attr, 0))
        pct = posture_segment_opt_pct(loss_cm, max_cm)
        width = max(4, min(100, int(pct)))
        rows.append(
            format_html(
                '<div class="hm-seg-row">'
                '<span class="hm-seg-name">{}</span>'
                '<div class="hm-seg-track"><div class="hm-seg-fill" style="width:{}%;"></div></div>'
                '<span class="hm-seg-pct">{}%</span>'
                '<span class="hm-seg-loss">{} cm loss</span></div>',
                label,
                width,
                pct,
                f"{loss_cm:.2f}",
            )
        )
    return format_html('<div class="hm-segments">{}</div>', format_html("".join(rows)))


def progress_dashboard_html(user) -> str:
    if not user or not user.pk:
        return "—"

    snap = get_user_runtime_state_snapshot(user)
    today = user_today(user)
    daily = DailyLog.objects.filter(user=user, log_date=today).first()
    ledger = (
        HeightLedger.objects.filter(user=user, entry_type="daily_compute")
        .order_by("-log_date", "-created_at")
        .first()
    )
    state = getattr(user, "posture_state", None)
    if state is None:
        from users.models import PostureState

        state = PostureState.objects.filter(user=user).first()

    daily_logs_url = reverse("admin:users_dailylog_changelist") + f"?user__id__exact={user.id}"
    ledger_url = reverse("admin:users_heightledger_changelist") + f"?user__id__exact={user.id}&entry_type=daily_compute"

    pipeline_ok = user.last_reset_date == today
    pipeline_sub = format_html(
        "TZ: {} · {}",
        user.timezone or "UTC",
        badge_bool(pipeline_ok, "Pipeline up to date", "Pipeline pending today"),
    )

    cards = format_html(
        '<div class="hm-stat-grid">{}{}{}{}</div>',
        _stat_card("Cumulative height", f"{fmt_cm(snap.get('current_height_um'))} cm", "From height ledger", accent="#0ea5e9"),
        _stat_card("Engine 1 today", str(daily.engine1_points if daily else "—"), "Posture + habits (+ adult food gate)", accent="#10b981"),
        _stat_card("Engine 2 today", str(daily.engine2_points if daily else "—"), "Teen HGH + lifestyle caps", accent="#8b5cf6"),
        _stat_card("Local today", str(today), pipeline_sub, accent="#f59e0b"),
    )

    unlock_row = format_html(
        '<div class="hm-meta-row">{} {} <span class="hm-meta-gap"></span> Sources: <code>{}</code></div>',
        badge_bool(snap.get("scan_completed"), "Scan done", "No scan"),
        badge_bool(snap.get("questionnaire_completed"), "Questionnaire", "No questionnaire"),
        state.assessment_sources_used if state and state.assessment_sources_used else "—",
    )

    today_detail = ""
    if daily:
        today_detail = format_html(
            '<table class="hm-mini-table"><thead><tr>'
            "<th>Exercise</th><th>Food</th><th>Lifestyle</th><th>Habits</th><th>Validated</th>"
            "</tr></thead><tbody><tr>"
            "<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
            "</tr></tbody></table>",
            daily.exercise_points,
            daily.food_points,
            daily.lifestyle_points,
            daily.habit_points,
            badge_bool(daily.validated, "Yes", "No"),
        )

    ledger_detail = ""
    if ledger:
        from users.spec_runtime import _um_from_dm

        ledger_detail = format_html(
            '<p class="hm-ledger-line">Latest ledger <strong>{}</strong>: '
            "Δ <strong>{} cm</strong> · cumulative <strong>{} cm</strong> · "
            "E1 Δ {} cm · E2 Δ {} cm</p>",
            ledger.log_date,
            fmt_cm(ledger.delta_um),
            fmt_cm(ledger.cumulative_um),
            fmt_cm(ledger.engine1_delta_um),
            fmt_cm(_um_from_dm(ledger.engine2_delta_dm)),
        )

    links = format_html(
        '<div class="hm-links">'
        '<a class="hm-link-btn" href="{}">Daily logs</a>'
        '<a class="hm-link-btn" href="{}">Height ledger</a>'
        "</div>",
        daily_logs_url,
        ledger_url,
    )

    footnote = format_html(
        '<p class="hm-footnote">Progress is computed by cron '
        "<code>run_daily_height_pipeline</code> (every 5 min) → "
        "<code>compute_daily_height_for_user</code>. "
        "Scroll down for the last 30 days in the inlines below.</p>"
    )

    return format_html(
        '<div class="hm-progress-dashboard">'
        "{}{}{}{}{}{}{}"
        "</div>",
        cards,
        unlock_row,
        _segment_bars(state),
        format_html('<div class="hm-section-title">Today breakdown</div>{}', today_detail or "—"),
        ledger_detail,
        links,
        footnote,
    )
