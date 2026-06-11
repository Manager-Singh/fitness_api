"""Admin UI for Ultimate Height Predictor on the User change page."""
from __future__ import annotations

from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.html import format_html

from height_predictor.services import get_latest_prediction


def _badge(text: str, *, color: str = "#64748b", bg: str = "#f1f5f9") -> str:
    return format_html(
        '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        'font-size:11px;font-weight:600;color:{};background:{};white-space:nowrap;">{}</span>',
        color,
        bg,
        text,
    )


def ultimate_height_section_html(user, request) -> str:
    """Latest prediction summary + generate button (admin user change page)."""
    if not user or not user.pk:
        return ""

    generate_url = reverse("admin:users_user_generate_ultimate_height", args=[user.pk])
    list_url = (
        reverse("admin:height_predictor_ultimateheightprediction_changelist")
        + f"?user__id__exact={user.pk}"
    )
    csrf = get_token(request)
    latest = get_latest_prediction(user)

    if latest:
        detail_url = reverse(
            "admin:height_predictor_ultimateheightprediction_change",
            args=[latest.pk],
        )
        summary = format_html(
            '<div class="hm-ultpred-summary">'
            '<div class="hm-stat-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:12px;">'
            '<div><div class="hm-stat-label">True Optimized</div>'
            '<div class="hm-stat-value"><strong>{} cm</strong></div></div>'
            '<div><div class="hm-stat-label">Genetic potential</div>'
            '<div class="hm-stat-value">{} cm</div></div>'
            '<div><div class="hm-stat-label">Posture recovery</div>'
            '<div class="hm-stat-value">{} cm</div></div>'
            '<div><div class="hm-stat-label">Band</div>'
            '<div class="hm-stat-value">{} {}</div></div>'
            '<div><div class="hm-stat-label">Computed</div>'
            '<div class="hm-stat-value" style="font-size:12px;">{}</div></div>'
            "</div>"
            '<p class="help">'
            'Model <code>{}</code> · prediction #{} · '
            '<a href="{}">Open full record</a>'
            "</p>"
            "</div>",
            latest.true_optimized_cm,
            latest.genetic_potential_cm,
            latest.posture_recovery_cm,
            _badge(str(latest.band or "—"), color="#1e40af", bg="#dbeafe"),
            _badge("Completed", color="#166534", bg="#dcfce7") if latest.completed else _badge("Incomplete"),
            latest.computed_at.strftime("%Y-%m-%d %H:%M UTC") if latest.computed_at else "—",
            latest.model_version or "v2",
            latest.pk,
            detail_url,
        )
    else:
        summary = format_html(
            '<div class="hm-ultpred-empty">'
            "<p><strong>No completed prediction yet.</strong></p>"
            "<p class=\"help\">Generate from the user's profile (sex, age, heights, parent heights). "
            "If a prior assessment exists, maturity/tape answers are reused automatically.</p>"
            "</div>"
        )

    actions = format_html(
        '<div class="hm-routine-actions" style="margin-top:12px;">'
        '<form method="post" action="{}" class="hm-generate-form" '
        "onsubmit=\"return confirm('Run Ultimate Height Predictor for this user? A new row will be stored.');\">"
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
        '<button type="submit" class="hm-btn-generate">'
        '<span class="hm-btn-icon">↻</span> Generate / re-run predictor</button>'
        "</form>"
        '<a class="hm-link-btn hm-link-btn-secondary" href="{}">All predictions</a>'
        "</div>",
        generate_url,
        csrf,
        list_url,
    )

    return format_html(
        '<div class="hm-routine-panel hm-ultpred-panel">'
        '<div class="hm-routine-panel-head">'
        '<h3 class="hm-routine-panel-title">Ultimate Height Predictor (Model v2)</h3>'
        '<p class="hm-routine-panel-sub">True Optimized Height — feeds dashboard green line when completed (teen + paid)</p>'
        "</div>"
        "{}"
        "{}"
        "</div>",
        summary,
        actions,
    )
