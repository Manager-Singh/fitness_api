"""Admin UI helpers — badges, progress dashboard HTML."""
from __future__ import annotations

from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from django.middleware.csrf import get_token

from users.models import DailyLog, HeightLedger, PostureState
from users.spec_runtime import (
    LEDGER_ENTRY_DAILY_COMPUTE,
    compute_engine1_gain_shares,
    get_user_runtime_state_snapshot,
)
from utils.posture.diagnostics_contract import build_posture_optimization_diagnostics
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct_precise
from utils.user_time import user_today


def um_to_cm(um) -> float:
    try:
        return int(um or 0) / 10000.0
    except (TypeError, ValueError):
        return 0.0


def fmt_cm(um) -> str:
    return f"{um_to_cm(um):.3f}"


def fmt_um_line(um: int | float | None, *, decimals_cm: int = 4) -> str:
    try:
        u = int(um or 0)
    except (TypeError, ValueError):
        u = 0
    cm = u / 10000.0
    return f"{u:,} μm ({cm:.{decimals_cm}f} cm)"


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


_SEGMENT_BAR_DEFS = (
    ("spinal_compression", "Spinal", "spinal_current_loss_um"),
    ("posture_collapse", "Collapse", "collapse_current_loss_um"),
    ("pelvic_tilt_back", "Pelvic", "pelvic_current_loss_um"),
    ("leg_hamstring", "Legs", "legs_current_loss_um"),
)


def _today_engine1_segment_shares(user) -> tuple[int, dict[str, int]]:
    """Today's Engine-1 μm total and per-field share from ledger metadata or recompute."""
    if not user or not user.pk:
        return 0, {}
    today = user_today(user)
    ledger = (
        HeightLedger.objects.filter(
            user=user,
            log_date=today,
            entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
        )
        .order_by("-created_at")
        .first()
    )
    engine1_um = int(getattr(ledger, "engine1_delta_um", 0) or 0) if ledger else 0
    if engine1_um <= 0:
        return 0, {}

    meta = (ledger.metadata or {}).get("engine1_segment_shares_um") if ledger else None
    if isinstance(meta, dict) and meta:
        return engine1_um, {k: int(v or 0) for k, v in meta.items()}

    state = PostureState.objects.filter(user=user).first()
    if not state:
        return engine1_um, {}

    # Reconstruct pre-gain losses: current + today's share (one refinement pass).
    class _Snap:
        pass

    snap = _Snap()
    for _, _, field in _SEGMENT_BAR_DEFS:
        setattr(snap, field, int(getattr(state, field, 0) or 0))
    shares = compute_engine1_gain_shares(snap, engine1_um)
    for field, share in shares.items():
        setattr(snap, field, int(getattr(snap, field, 0) or 0) + int(share or 0))
    shares = compute_engine1_gain_shares(snap, engine1_um)
    return engine1_um, shares


def _opt_pct_from_loss_um(loss_um: int, seg_key: str) -> float:
    max_cm = float(POSTURE_SEGMENT_MAX_LOSS_CM.get(seg_key, 0))
    loss_cm = int(loss_um or 0) / 10000.0
    return float(posture_segment_opt_pct_precise(loss_cm, max_cm, decimals=2))


def _segment_bars_from_diagnostics(user) -> str:
    """Segment bars: green = prior opt %, amber = today's Engine-1 gain split."""
    if not user or not user.pk:
        return ""
    engine1_today_um, shares_by_field = _today_engine1_segment_shares(user)
    state = PostureState.objects.filter(user=user).first()

    rows = []
    for seg_key, label, field in _SEGMENT_BAR_DEFS:
        loss_after_um = int(getattr(state, field, 0) or 0) if state else 0
        share_um = int(shares_by_field.get(field, 0) or 0)
        loss_before_um = loss_after_um + share_um

        pct_after = _opt_pct_from_loss_um(loss_after_um, seg_key)
        pct_before = _opt_pct_from_loss_um(loss_before_um, seg_key)
        pct_today = max(0.0, pct_after - pct_before)
        loss_cm = f"{loss_after_um / 10000.0:.2f}"
        pct_today_str = f"{pct_today:.2f}" if pct_today else "0"
        share_line = fmt_um_line(share_um) if share_um else "0 μm"

        w_before = max(0, min(100, int(round(pct_before))))
        w_today = max(0, min(100 - w_before, int(round(pct_today))))

        rows.append(
            format_html(
                '<div class="hm-seg-row">'
                '<span class="hm-seg-name">{}</span>'
                '<div class="hm-seg-track hm-seg-track-split">'
                '<div class="hm-seg-fill-base" style="width:{}%;"></div>'
                '<div class="hm-seg-fill-today" style="width:{}%;"></div>'
                "</div>"
                '<span class="hm-seg-pct">{}%'
                '<span class="hm-seg-pct-today">+{}%</span></span>'
                '<span class="hm-seg-loss">{} · {} cm'
                '<span class="hm-seg-today-gain"> · today <strong>+{}</strong></span></span>'
                "</div>",
                label,
                w_before,
                w_today,
                int(round(pct_after)),
                pct_today_str,
                fmt_um_line(loss_after_um),
                loss_cm,
                share_line,
            )
        )

    legend = ""
    if engine1_today_um > 0:
        legend = format_html(
            '<p class="hm-seg-legend">'
            '<span class="hm-legend-swatch hm-legend-base"></span> Prior optimization '
            '<span class="hm-legend-swatch hm-legend-today"></span> '
            "Today Engine-1 gain split ({} total)</p>",
            fmt_um_line(engine1_today_um),
        )

    return format_html(
        '<div class="hm-segments">{}{}</div>',
        legend,
        mark_safe("".join(str(r) for r in rows)),
    )


def compact_today_height_block(user) -> str:
    """One compact block: ledger formula + per-segment today E1 share (μm)."""
    if not user or not user.pk:
        return ""
    today = user_today(user)
    ledger = (
        HeightLedger.objects.filter(
            user=user,
            log_date=today,
            entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
        )
        .order_by("-created_at")
        .first()
    )
    daily = DailyLog.objects.filter(user=user, log_date=today).first()
    _e1_um, shares = _today_engine1_segment_shares(user)

    if not ledger and not daily:
        return format_html('<p class="hm-formula-muted">No daily compute for {} yet.</p>', today)

    from users.spec_runtime import _um_from_dm

    e1_um = int(getattr(ledger, "engine1_delta_um", 0) or 0) if ledger else 0
    e2_um = _um_from_dm(getattr(ledger, "engine2_delta_dm", 0) or 0) if ledger else 0
    bio_um = int(getattr(ledger, "bio_delta_um", 0) or 0) if ledger else 0
    delta_um = int(getattr(ledger, "delta_um", 0) or 0) if ledger else 0

    share_rows = []
    for seg_key, label, field in _SEGMENT_BAR_DEFS:
        share_um = int(shares.get(field, 0) or 0)
        if share_um <= 0 and e1_um <= 0:
            continue
        share_rows.append(
            f"<tr><td>{label}</td><td>{fmt_um_line(share_um)}</td></tr>"
        )

    share_table = ""
    if share_rows and e1_um > 0:
        share_table = mark_safe(
            '<table class="hm-compact-table"><thead><tr>'
            "<th>Segment</th><th>Today E1 share</th></tr></thead><tbody>"
            + "".join(share_rows)
            + "</tbody></table>"
        )

    pts_line = ""
    if daily:
        pts_line = format_html(
            "<p class=\"hm-compact-line\">E1 points today: <strong>{}</strong> "
            "(exercise {} · food {} · lifestyle {} · habits {})</p>",
            daily.engine1_points,
            daily.exercise_points,
            daily.food_points,
            daily.lifestyle_points,
            daily.habit_points,
        )

    return format_html(
        '<div class="hm-compact-today">'
        "<p class=\"hm-compact-line\"><code>Δ_um = E1_um + E2_um + Bio_um</code></p>"
        "<p class=\"hm-compact-line\">"
        "{} + {} + {} = <strong>{}</strong></p>"
        "{}"
        "{}"
        "</div>",
        fmt_um_line(e1_um),
        fmt_um_line(e2_um),
        fmt_um_line(bio_um),
        fmt_um_line(delta_um),
        pts_line,
        share_table,
    )


_TIER_STYLES = {
    "core": ("#1e40af", "#dbeafe", "Core"),
    "rec": ("#6b21a8", "#f3e8ff", "Rec"),
    "beast": ("#9a3412", "#ffedd5", "Beast"),
}


def _tier_badge(tier: str | None) -> str:
    key = (tier or "").lower()
    color, bg, label = _TIER_STYLES.get(key, ("#64748b", "#f1f5f9", tier or "—"))
    return badge(label, color=color, bg=bg)


def _qty_label(ure) -> str:
    unit = (ure.unit or "reps").lower()
    lo = ure.qty_min
    hi = ure.qty_max
    if hi and hi != lo:
        qty = f"{lo}–{hi}"
    else:
        qty = str(lo)
    if unit == "reps":
        return f"{ure.sets}×{qty} reps"
    if unit == "sec":
        return f"{ure.sets}×{qty}s"
    return f"{ure.sets}×{qty} {unit}"


def routine_section_html(user, request) -> str:
    """Active posture/HGH routines + generate button (admin change page)."""
    if not user or not user.pk:
        return ""

    from django.db.models import Prefetch
    from django.urls import reverse

    from workouts.models import UserRoutine, UserRoutineExercise

    generate_url = reverse("admin:users_user_generate_routine", args=[user.pk])
    routines_url = (
        reverse("admin:workouts_userroutine_changelist") + f"?user__id__exact={user.pk}"
    )
    csrf = get_token(request)

    routines = list(
        UserRoutine.objects.filter(user=user, is_active=True)
        .prefetch_related(
            Prefetch(
                "exercises",
                queryset=UserRoutineExercise.objects.select_related("exercise")
                .order_by("order"),
            )
        )
        .order_by("routine_type", "-created_at")
    )

    routine_blocks = []
    if not routines:
        routine_blocks.append(
            format_html(
                '<div class="hm-routine-empty">'
                "<p>No active routine yet.</p>"
                '<p class="hm-routine-empty-hint">'
                "Generate a personalized POSTURE routine (10 exercises) from this user’s posture state."
                "</p></div>"
            )
        )
    else:
        for routine in routines:
            exercises = list(routine.exercises.all())
            cards = []
            for ure in exercises:
                ex = ure.exercise
                name = ex.short_name or ex.name
                cards.append(
                    format_html(
                        '<div class="hm-ex-card">'
                        '<span class="hm-ex-order">#{}</span>'
                        '<div class="hm-ex-body">'
                        '<div class="hm-ex-title">{}</div>'
                        '<div class="hm-ex-meta">{} {}</div>'
                        "</div></div>",
                        ure.order,
                        name,
                        _tier_badge(ure.tier),
                        badge(_qty_label(ure), color="#334155", bg="#e2e8f0"),
                    )
                )
            routine_blocks.append(
                format_html(
                    '<div class="hm-routine-block">'
                    '<div class="hm-routine-head">'
                    '{} {} <span class="hm-routine-date">{}</span>'
                    '<span class="hm-routine-count">{} exercises</span>'
                    "</div>"
                    '<div class="hm-ex-grid">{}</div>'
                    "</div>",
                    badge(
                        routine.get_routine_type_display(),
                        color="#0f766e",
                        bg="#ccfbf1",
                    ),
                    badge_bool(routine.is_active, "Active", "Inactive"),
                    routine.created_at.strftime("%Y-%m-%d %H:%M"),
                    len(exercises),
                    format_html("".join(cards)) if cards else "—",
                )
            )

    actions = format_html(
        '<div class="hm-routine-actions">'
        '<form method="post" action="{}" class="hm-generate-form" '
        'onsubmit="return confirm(\'Generate a new POSTURE routine? The current active routine will be deactivated.\');">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
        '<button type="submit" class="hm-btn-generate">'
        '<span class="hm-btn-icon">↻</span> Generate routine</button>'
        "</form>"
        '<a class="hm-link-btn hm-link-btn-secondary" href="{}">All routines</a>'
        "</div>",
        generate_url,
        csrf,
        routines_url,
    )

    return format_html(
        '<div class="hm-routine-panel">'
        '<div class="hm-routine-panel-head">'
        '<h3 class="hm-routine-panel-title">Exercise routine</h3>'
        '<p class="hm-routine-panel-sub">Active assignments from <code>generate_user_routines</code></p>'
        "</div>"
        "{}"
        "{}"
        "</div>",
        format_html("".join(routine_blocks)),
        actions,
    )


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

    has_assessment = bool(str(snap.get("assessment_sources_used") or "").strip())
    q_done = bool(snap.get("questionnaire_completed")) or has_assessment
    unlock_row = format_html(
        '<div class="hm-meta-row">{} {} <span class="hm-meta-gap"></span> Sources: <code>{}</code></div>',
        badge_bool(snap.get("scan_completed"), "Scan done", "No scan"),
        badge_bool(q_done, "Questionnaire", "No questionnaire"),
        snap.get("assessment_sources_used") or "—",
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

    links = format_html(
        '<div class="hm-links">'
        '<a class="hm-link-btn" href="{}">Daily logs</a>'
        '<a class="hm-link-btn" href="{}">Height ledger</a>'
        "</div>",
        daily_logs_url,
        ledger_url,
    )

    footnote = format_html(
        '<p class="hm-footnote">Updated by cron <code>run_daily_height_pipeline</code>. '
        "Daily logs and height ledger tables below (last 30 days).</p>"
    )

    return format_html(
        '<div class="hm-progress-dashboard">'
        "{}{}{}{}{}{}{}"
        "</div>",
        cards,
        unlock_row,
        format_html('<div class="hm-section-title">Posture optimization bars</div>'),
        _segment_bars_from_diagnostics(user),
        format_html('<div class="hm-section-title">Today height &amp; E1 split</div>'),
        compact_today_height_block(user),
        format_html('<div class="hm-section-title">Today points</div>{}', today_detail or "—"),
        links,
        footnote,
    )
