from __future__ import annotations

from dataclasses import dataclass


TEEN_TRACEABLE_NUTRITION_CAP_POINTS = 35.0
TEEN_CAP_EVENT_KEY = "teen_nutrition_cap_35"
TEEN_CAP_MESSAGE_EXACT = (
    "You've hit today's nutrition target. Your body has what it needs to grow. "
    "Logging more won't add points or height — come back tomorrow!"
)


@dataclass(frozen=True)
class TeenCapResult:
    cap_limit: float
    cap_reached: bool
    crossed_today: bool
    modal_required: bool
    message: str | None


def teen_cap_result(*, raw_before: float, raw_after: float, modal_required: bool) -> TeenCapResult:
    """
    Spec Issue 13: show exact message the moment a teen crosses the 35-pt cap,
    and only require the modal once per day.
    """
    before = float(raw_before or 0.0)
    after = float(raw_after or 0.0)
    cap = float(TEEN_TRACEABLE_NUTRITION_CAP_POINTS)
    cap_reached = bool(after >= cap)
    crossed = bool(before < cap <= after)
    msg = TEEN_CAP_MESSAGE_EXACT if cap_reached else None
    return TeenCapResult(
        cap_limit=cap,
        cap_reached=cap_reached,
        crossed_today=crossed,
        modal_required=bool(modal_required and crossed),
        message=msg,
    )

