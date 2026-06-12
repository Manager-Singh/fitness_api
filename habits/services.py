"""Micro-habit logging and Engine 1 point totals (Issue #13)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from habits.models import MicroHabit, MicroHabitLog
from utils.user_time import user_localize_dt, user_today

# Part 3: habits cap raised 6 -> 12. The math: Puppet 6 (3pt x2 slots) + Desk 2 + Doorway 2
# + Tech-Neck 2 = 12. Routes to Engine 1 / posture recovery for both teens and adults.
DAILY_HABIT_CAP = 12
ENGINE_CM_PER_POINT = 0.001


def resolve_habit_log_date(user, request_data=None):
    """Same midnight grace as nutra-logs (optional client_timestamp)."""
    request_data = request_data or {}
    now_utc = timezone.now()
    now_local = user_localize_dt(user, now_utc)
    log_date = now_local.date()
    grace_minutes = 5
    if now_local.hour == 0 and now_local.minute < grace_minutes:
        client_ts = request_data.get("client_timestamp")
        if client_ts:
            try:
                parsed = datetime.fromisoformat(str(client_ts).replace("Z", "+00:00"))
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.utc)
                client_local = user_localize_dt(user, parsed.astimezone(timezone.utc))
                if client_local.date() == (log_date - timedelta(days=1)):
                    return log_date - timedelta(days=1)
            except Exception:
                pass
    return log_date


def total_raw_habit_points(user, log_date: date) -> int:
    return int(
        MicroHabitLog.objects.filter(user=user, log_date=log_date).aggregate(
            total=Sum("points")
        )["total"]
        or 0
    )


def capped_habit_points_for_engine(user, log_date: date) -> int:
    return min(DAILY_HABIT_CAP, total_raw_habit_points(user, log_date))


def _validate_slot(habit: MicroHabit, slot: str) -> str:
    slot = str(slot or "").strip().lower()
    if habit.logging_mode == MicroHabit.AM_PM:
        if slot not in (MicroHabitLog.SLOT_AM, MicroHabitLog.SLOT_PM):
            raise ValidationError("slot must be 'am' or 'pm' for this habit.")
    elif slot != MicroHabitLog.SLOT_ONCE:
        raise ValidationError("slot must be 'once' for this habit.")
    return slot


def _habit_points_for_habit_on_date(user, log_date: date, habit: MicroHabit) -> int:
    """Points already logged for a single habit on a date (for per-habit cap checks)."""
    return int(
        MicroHabitLog.objects.filter(user=user, log_date=log_date, habit=habit).aggregate(
            total=Sum("points")
        )["total"]
        or 0
    )


def log_habit(user, log_date: date, habit_code: str, slot: str):
    """
    Toggle one log row per (user, date, habit, slot).

    - If no row exists: create it and return ``(log, "created")``.
    - If a row already exists: delete it and return ``(None, "removed")``.

    Part 7.4 — server-side enforcement at POST time (not just at scoring time):
    - reject a new log that would push this habit past its ``daily_max_points``;
    - reject a new log that would push the day past the global ``DAILY_HABIT_CAP``;
    - tolerate a concurrent duplicate create (unique constraint) as an idempotent toggle.
    """
    habit = MicroHabit.objects.filter(code=habit_code, is_active=True).first()
    if not habit:
        raise ValidationError(f"Unknown habit: {habit_code}")

    slot = _validate_slot(habit, slot)
    pts = int(habit.points_per_log or 1)

    existing = MicroHabitLog.objects.filter(
        user=user,
        log_date=log_date,
        habit=habit,
        slot=slot,
    ).first()
    if existing:
        existing.delete()
        return None, "removed"

    # Per-habit daily cap (e.g. Puppet max 6 = 3pts x 2 slots).
    habit_max = int(habit.daily_max_points or 0)
    if habit_max > 0 and (_habit_points_for_habit_on_date(user, log_date, habit) + pts) > habit_max:
        raise ValidationError(
            f"Daily limit reached for '{habit.name}' ({habit_max} pts)."
        )

    # Global daily habits cap.
    if (total_raw_habit_points(user, log_date) + pts) > DAILY_HABIT_CAP:
        raise ValidationError(
            f"Daily habit points limit reached ({DAILY_HABIT_CAP} pts)."
        )

    try:
        with transaction.atomic():
            log = MicroHabitLog.objects.create(
                user=user,
                log_date=log_date,
                habit=habit,
                slot=slot,
                points=pts,
            )
        return log, "created"
    except IntegrityError:
        # Concurrent duplicate create for the same (user, date, habit, slot): treat the
        # already-present row as the result of this toggle rather than 500-ing.
        log = MicroHabitLog.objects.filter(
            user=user, log_date=log_date, habit=habit, slot=slot
        ).first()
        return log, "created"


def build_habits_plan_payload(user, log_date: date | None = None) -> dict:
    """Catalog + today's slot state for Lifestyle tab Habits section."""
    log_date = log_date or user_today(user)
    logs = {
        (row.habit_id, row.slot): row
        for row in MicroHabitLog.objects.filter(user=user, log_date=log_date).select_related("habit")
    }
    raw_pts = total_raw_habit_points(user, log_date)
    capped_pts = min(DAILY_HABIT_CAP, raw_pts)

    items = []
    for habit in MicroHabit.objects.filter(is_active=True).order_by("sort_order", "name"):
        if habit.logging_mode == MicroHabit.AM_PM:
            slots = {}
            for slot_key in (MicroHabitLog.SLOT_AM, MicroHabitLog.SLOT_PM):
                row = logs.get((habit.id, slot_key))
                slots[slot_key] = {
                    "logged": row is not None,
                    "points": int(row.points) if row else 0,
                    "logged_at": row.logged_at.isoformat() if row else None,
                }
        else:
            row = logs.get((habit.id, MicroHabitLog.SLOT_ONCE))
            slots = {
                "once": {
                    "logged": row is not None,
                    "points": int(row.points) if row else 0,
                    "logged_at": row.logged_at.isoformat() if row else None,
                }
            }

        items.append(
            {
                "code": habit.code,
                "name": habit.name,
                "ui_prompt": habit.ui_prompt,
                "how_to_detail": habit.how_to_detail or habit.ui_prompt,
                "instruction_steps": habit.get_instruction_steps(),
                "instruction_lines": habit.get_instruction_lines(),
                "image_url": habit.image.url if habit.image else None,
                "daily_max": int(habit.daily_max_points),
                "logging_mode": habit.logging_mode,
                "points_per_log": int(habit.points_per_log),
                "slots": slots,
            }
        )

    return {
        "section_title": "Habits",
        "engine": "engine1",
        "cm_per_point": ENGINE_CM_PER_POINT,
        "points_today": raw_pts,
        "points_capped_for_engine": capped_pts,
        "daily_cap": DAILY_HABIT_CAP,
        "log_date": str(log_date),
        "items": items,
    }
