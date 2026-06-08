"""Admin HTML panels: segment loss + daily height formulas (points, μm, cm)."""
from __future__ import annotations

from django.utils.html import format_html
from django.utils.safestring import mark_safe

from users.models import DailyLog, HeightLedger, PostureState
from users.spec_runtime import LEDGER_ENTRY_DAILY_COMPUTE, _daily_engine_points, _um_from_dm
from utils.age import get_user_age_on_date
from utils.check_payment import check_subscription_or_response
from utils.posture.diagnostics_contract import build_posture_optimization_diagnostics
from utils.posture.height_constants import (
    POINTS_TO_CM_ENGINE1,
    POINTS_TO_CM_ENGINE2,
    POSTURE_SEGMENT_DISTRIBUTION_RATIO,
    POSTURE_SEGMENT_MAX_LOSS_CM,
    posture_segment_opt_pct_precise,
)
from utils.user_time import user_today


def fmt_um_line(um: int | float | None, *, decimals_cm: int = 4) -> str:
    try:
        u = int(um or 0)
    except (TypeError, ValueError):
        u = 0
    cm = u / 10000.0
    return f"{u:,} μm ({cm:.{decimals_cm}f} cm)"


def _formula_table(headers: list[str], rows: list, *, caption: str = "") -> str:
    head_html = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        body_rows.append(f"<tr>{cells}</tr>")
    cap = f'<caption class="hm-formula-cap">{caption}</caption>' if caption else ""
    return mark_safe(
        f'<table class="hm-formula-table">{cap}'
        f"<thead><tr>{head_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )


def _today_engine1_segment_shares_from_panel(user):
    from users.admin_ui import _today_engine1_segment_shares

    return _today_engine1_segment_shares(user)


def posture_segment_formula_html(user) -> str:
    """Segment losses from PostureState (μm) with spec formulas."""
    if not user or not user.pk:
        return "—"
    state = PostureState.objects.filter(user=user).first()
    if not state:
        return format_html('<p class="hm-formula-muted">No PostureState yet.</p>')

    seg_defs = [
        ("spinal_compression", "Spinal", "spinal_current_loss_um"),
        ("posture_collapse", "Collapse", "collapse_current_loss_um"),
        ("pelvic_tilt_back", "Pelvic", "pelvic_current_loss_um"),
        ("leg_hamstring", "Legs", "legs_current_loss_um"),
    ]
    _, shares_by_field = _today_engine1_segment_shares_from_panel(user)
    rows = []
    sum_loss_um = 0
    for seg_key, label, field in seg_defs:
        loss_um = int(getattr(state, field, 0) or 0)
        share_um = int(shares_by_field.get(field, 0) or 0)
        sum_loss_um += loss_um
        max_cm = float(POSTURE_SEGMENT_MAX_LOSS_CM.get(seg_key, 0))
        max_um = int(round(max_cm * 10000))
        cur_cm = loss_um / 10000.0
        pct = posture_segment_opt_pct_precise(cur_cm, max_cm, decimals=2)
        ratio = POSTURE_SEGMENT_DISTRIBUTION_RATIO.get(seg_key, 0)
        rows.append([
            label,
            f"{ratio * 100:.0f}%",
            fmt_um_line(max_um),
            fmt_um_line(loss_um),
            fmt_um_line(share_um) if share_um else "—",
            mark_safe(
                f'<code>(1 − {cur_cm:.4f}/{max_cm:.2f})×100</code> → <strong>{pct}%</strong>'
            ),
        ])

    total_um = int(state.total_recoverable_loss_um or 0) or sum_loss_um
    bars = _segment_bars_html(user)

    return format_html(
        '<div class="hm-formula-panel">'
        '<div class="hm-formula-title">Segment loss &amp; optimization (PostureState)</div>'
        '<p class="hm-formula-note">'
        "<strong>Stored in μm</strong> (1 cm = 10,000 μm). "
        "Bar % = <code>(1 − Current_Loss / Max_Loss) × 100</code>. "
        "Initial split from questionnaire uses "
        "<code>Total × segment ratio</code> "
        "(Spinal 30% · Collapse 35% · Pelvic 25% · Legs 10%)."
        "</p>"
        "{}"
        '<p class="hm-formula-total">'
        "<strong>Total recoverable:</strong> {} "
        '<span class="hm-formula-muted">(sum segments {} μm if total unset)</span>'
        "</p>"
        '<div class="hm-formula-subtitle">Visual bars (same as dashboard API)</div>'
        "{}"
        '<div class="hm-formula-subtitle">Engine-1 daily redistribution (§4.3)</div>'
        '<p class="hm-formula-note">'
        "<strong>Initial</strong> losses use fixed 30/35/25/10 of total recoverable. "
        "<strong>Daily gain</strong> (e.g. 79 pts → 790 μm) is split only across active segments, "
        "weighted by each segment&apos;s <code>Current_Loss_um</code>: "
        "<code>share = round(gain_um × loss_um / sum_active_loss_um)</code>. "
        "This avoids bars rising too fast on segments that already have little loss left."
        "</p>"
        "</div>",
        _formula_table(
            ["Segment", "Init ratio", "Max loss", "Current loss", "Today E1 share", "Opt % formula"],
            rows,
            caption="Per-segment μm storage",
        ),
        fmt_um_line(total_um),
        sum_loss_um,
        bars,
    )


def _segment_bars_html(user) -> str:
    from users.admin_ui import _segment_bars_from_diagnostics

    return _segment_bars_from_diagnostics(user)


def daily_points_formula_html(user, log_date=None) -> str:
    """Point-wise daily engine breakdown + μm height conversion."""
    if not user or not user.pk:
        return "—"
    log_date = log_date or user_today(user)
    daily = DailyLog.objects.filter(user=user, log_date=log_date).first()
    ledger = (
        HeightLedger.objects.filter(
            user=user,
            log_date=log_date,
            entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
        )
        .order_by("-created_at")
        .first()
    )

    try:
        age = int(get_user_age_on_date(user, log_date) or 0)
    except (TypeError, ValueError):
        age = 0
    is_teen = 13 <= age <= 20
    is_adult = age >= 21

    try:
        sub = check_subscription_or_response(user).data
        e1, e2, ex_pts, food_pts, life_pts, habit_pts = _daily_engine_points(
            user, log_date, age, sub
        )
    except Exception:
        e1 = e2 = ex_pts = food_pts = life_pts = habit_pts = 0

    e1_i = int(daily.engine1_points) if daily else int(round(e1))
    e2_i = int(daily.engine2_points) if daily else int(round(e2))
    ex_i = int(daily.exercise_points) if daily else int(ex_pts)
    food_i = int(daily.food_points) if daily else int(food_pts)
    life_i = int(daily.lifestyle_points) if daily else int(life_pts)
    habit_i = int(daily.habit_points) if daily else int(habit_pts)

    if is_adult:
        posture_approx = max(0, ex_i)
        nutrition_approx = max(0, e1_i - posture_approx - habit_i)
        e1_formula = format_html(
            "<code>E1 = posture_work + adult_food_gate + habits</code><br>"
            "= {} + {} + {} = <strong>{} pts</strong>",
            posture_approx,
            nutrition_approx,
            habit_i,
            e1_i,
        )
        e2_formula = "<code>E2 = 0</code> (adults — Engine 2 disabled)"
    elif is_teen:
        e1_formula = format_html(
            "<code>E1 = posture_work + habits</code> (capped by habits max 12/day)<br>"
            "= posture + {} habits → <strong>{} pts</strong>",
            habit_i,
            e1_i,
        )
        e2_formula = format_html(
            "<code>E2 = min(HGH,30) + min(food,35) + min(sleep,10) + min(sun,6) "
            "+ min(meditation,2) + min(hydration,1)</code><br>"
            "Lifestyle bucket today: <strong>{} pts</strong> (sleep/sun/med/hyd) · "
            "Food: <strong>{}</strong> → <strong>{} pts E2</strong>",
            life_i,
            food_i,
            e2_i,
        )
    else:
        e1_formula = format_html("E1 recomputed: <strong>{}</strong>", e1_i)
        e2_formula = format_html("E2 recomputed: <strong>{}</strong>", e2_i)

    e1_um = int(round(e1_i * POINTS_TO_CM_ENGINE1 * 10000))
    e2_dm = int(round(e2_i * 5))
    e2_um = _um_from_dm(e2_dm)

    point_rows = [
        ["Exercise (posture+HGH logs)", str(ex_i), "—", "Feeds posture_pts / hgh_pts"],
        ["Food", str(food_i), "—", "Teen → E2 cap; adult → E1 gate"],
        ["Lifestyle", str(life_i), "—", "Teen → E2 components"],
        ["Habits (micro)", str(habit_i), "—", "Engine 1, max 12/day"],
        ["Engine 1 total", str(e1_i), fmt_um_line(e1_um), f"× {POINTS_TO_CM_ENGINE1} cm/pt"],
        ["Engine 2 total", str(e2_i), fmt_um_line(e2_um), f"× {POINTS_TO_CM_ENGINE2} cm/pt (via dμm÷10)"],
    ]

    ledger_block = ""
    if ledger:
        bio_um = int(ledger.bio_delta_um or 0)
        delta_um = int(ledger.delta_um or 0)
        ledger_block = format_html(
            '<div class="hm-formula-subtitle">Height ledger row (daily_compute)</div>'
            '<p class="hm-formula-note">'
            "<code>Δ_um = E1_um + E2_um + Bio_um</code> (teen caps / pre-scan pending may zero E1/E2)<br>"
            "<strong>{}</strong> = {} + {} + {} → <strong>{}</strong><br>"
            "Cumulative: <strong>{}</strong>"
            "</p>",
            log_date,
            fmt_um_line(ledger.engine1_delta_um),
            fmt_um_line(_um_from_dm(ledger.engine2_delta_dm)),
            fmt_um_line(bio_um),
            fmt_um_line(delta_um),
            fmt_um_line(ledger.cumulative_um),
        )

    validated = badge_bool_inline(daily.validated) if daily else "—"

    return format_html(
        '<div class="hm-formula-panel">'
        '<div class="hm-formula-title">Daily calculation — {}</div>'
        '<p class="hm-formula-note">Age {} · {} · Validated: {}</p>'
        '<div class="hm-formula-subtitle">Engine points (Section 11)</div>'
        "<p>{}</p><p>{}</p>"
        "{}"
        '<div class="hm-formula-subtitle">Points → height (μm)</div>'
        '<p class="hm-formula-note">'
        "<code>E1_um = round(E1_pts × {:.4f} × 10,000)</code> · "
        "<code>E2_dm = round(E2_pts × 5)</code> (0.5 μm steps) · "
        "<code>E2_um = round(E2_dm / 10)</code>"
        "</p>"
        "{}"
        "{}"
        "</div>",
        log_date,
        age,
        "Teen" if is_teen else ("Adult" if is_adult else "Unknown tier"),
        validated,
        e1_formula,
        e2_formula,
        _formula_table(
            ["Source", "Points", "Height (μm)", "Formula"],
            point_rows,
        ),
        ledger_block,
    )


def badge_bool_inline(value: bool) -> str:
    if value:
        return '<span style="color:#166534;font-weight:600">✓ Yes</span>'
    return '<span style="color:#991b1b;font-weight:600">✗ No</span>'
