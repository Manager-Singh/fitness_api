from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nutration.models import AgeGroup, Food, Module
from nutration.models_log import NutraEntry, NutraSession
from posture.models import PostureReport
from user_profile.models import UserProfile
from users.spec_runtime import rebuild_ledger_from_date
from workouts.models import (
    Exercise,
    ExerciseCategory,
    RoutineType,
    Tier,
    UserRoutine,
    UserRoutineExercise,
    WorkoutEntry,
    WorkoutSession,
)


def _parse_date(value: str):
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _ensure_min_nutrition_fixtures():
    """
    Create minimal Module/Food rows if the DB is empty.
    This is only for test seeding and runs under staff-only endpoint.
    """
    ag, _ = AgeGroup.objects.get_or_create(name="All Ages", defaults={"min_age": 0, "max_age": None})

    disc, _ = Module.objects.get_or_create(
        name="Disc Lubrication",
        age_group=ag,
        defaults={"type": Module.NUTRITION, "short_name": "Disc", "action_btn": "Log", "tag_line": ""},
    )
    muscle, _ = Module.objects.get_or_create(
        name="Posture Muscle Repair",
        age_group=ag,
        defaults={"type": Module.NUTRITION, "short_name": "Muscle", "action_btn": "Log", "tag_line": ""},
    )
    sleep, _ = Module.objects.get_or_create(
        name="Sleep",
        age_group=ag,
        defaults={"type": Module.LIFESTYLE, "short_name": "Sleep", "action_btn": "Log", "tag_line": ""},
    )
    sun, _ = Module.objects.get_or_create(
        name="Sunlight",
        age_group=ag,
        defaults={"type": Module.LIFESTYLE, "short_name": "Sun", "action_btn": "Log", "tag_line": ""},
    )
    med, _ = Module.objects.get_or_create(
        name="Meditation",
        age_group=ag,
        defaults={"type": Module.LIFESTYLE, "short_name": "Meditation", "action_btn": "Log", "tag_line": ""},
    )
    hyd, _ = Module.objects.get_or_create(
        name="Hydration",
        age_group=ag,
        defaults={"type": Module.LIFESTYLE, "short_name": "Hydration", "action_btn": "Log", "tag_line": ""},
    )

    f1, _ = Food.objects.get_or_create(name="Salmon", defaults={"short_name": "Salmon"})
    f2, _ = Food.objects.get_or_create(name="Collagen", defaults={"short_name": "Collagen"})
    return {
        "modules": {"disc": disc, "muscle": muscle, "sleep": sleep, "sun": sun, "med": med, "hyd": hyd},
        "foods": {"salmon": f1, "collagen": f2},
    }


def _ensure_min_exercise_fixtures():
    """
    Create minimal Exercise rows if missing (posture + hgh).
    """
    posture, _ = Exercise.objects.get_or_create(
        name="Wall Angels",
        defaults={"short_name": "Wall Angels", "points": 5, "category": ExerciseCategory.POSTURE},
    )
    hgh, _ = Exercise.objects.get_or_create(
        name="HGH Sprint",
        defaults={"short_name": "Sprint", "points": 10, "category": ExerciseCategory.HGH},
    )
    return {"posture": posture, "hgh": hgh}


def _seed_scan(user, on_date):
    """
    Create a deterministic PostureReport + set profile.last_scan for scan_completed flows.
    """
    profile = UserProfile.objects.filter(user=user).first()
    if profile:
        profile.last_scan = timezone.make_aware(datetime.combine(on_date, datetime.min.time()), dt_timezone.utc)
        profile.save(update_fields=["last_scan"])

    optimization_breakdown = {
        "spinal_compression": {"current_loss_cm": 1.8, "max_loss_cm": 3.0, "percent_optimized": 40},
        "posture_collapse": {"current_loss_cm": 1.75, "max_loss_cm": 2.5, "percent_optimized": 30},
        "pelvic_tilt_back": {"current_loss_cm": 0.9, "max_loss_cm": 1.5, "percent_optimized": 40},
        "leg_hamstring": {"current_loss_cm": 0.3, "max_loss_cm": 1.0, "percent_optimized": 70},
    }
    PostureReport.objects.create(
        user=user,
        data={"optimization_breakdown": optimization_breakdown, "total_recoverable_loss_cm": 4.75},
        raw_request_data={"seeded": True, "seed_date": str(on_date)},
    )


def _seed_day_logs(user, on_date, variant, fixtures):
    """
    Seed workout + nutrition/lifestyle logs for a single date.
    """
    # Clear existing day logs (idempotent).
    WorkoutEntry.objects.filter(session__user=user, session__date=on_date).delete()
    WorkoutSession.objects.filter(user=user, date=on_date).delete()
    NutraEntry.objects.filter(session__user=user, session__date=on_date).delete()
    NutraSession.objects.filter(user=user, date=on_date).delete()

    ex = fixtures["exercises"]

    posture_routine = UserRoutine.objects.filter(user=user, is_active=True, routine_type=RoutineType.POSTURE).first()
    if posture_routine is None:
        posture_routine = UserRoutine.objects.create(user=user, routine_type=RoutineType.POSTURE, is_active=True)
        UserRoutineExercise.objects.get_or_create(
            routine=posture_routine, exercise=ex["posture"], defaults={"tier": Tier.CORE, "order": 1}
        )

    session = WorkoutSession.objects.create(user=user, user_routine=posture_routine, date=on_date)

    posture_exercises = list(posture_routine.exercises.all().order_by("order")[:2])
    if not posture_exercises:
        posture_exercises = [
            UserRoutineExercise.objects.create(routine=posture_routine, exercise=ex["posture"], tier=Tier.CORE, order=1)
        ]
    for ure in posture_exercises:
        pts = int(getattr(ure.exercise, "points", 0) or 0)
        WorkoutEntry.objects.create(
            session=session,
            user_routine_exercise=ure,
            exercise=ure.exercise,
            points=pts,
            sets_done=getattr(ure, "sets", None),
            reps_done=getattr(ure, "qty_min", None),
        )

    # HGH only for teen variant (seed into an HGH routine + session)
    if variant == "teen":
        hgh_routine = UserRoutine.objects.filter(user=user, is_active=True, routine_type=RoutineType.HGH).first()
        if hgh_routine is None:
            hgh_routine = UserRoutine.objects.create(user=user, routine_type=RoutineType.HGH, is_active=True)
            UserRoutineExercise.objects.get_or_create(
                routine=hgh_routine, exercise=ex["hgh"], defaults={"tier": Tier.CORE, "order": 1}
            )
        hgh_session = WorkoutSession.objects.create(user=user, user_routine=hgh_routine, date=on_date)
        hgh_ure = hgh_routine.exercises.all().order_by("order").first()
        if hgh_ure:
            WorkoutEntry.objects.create(
                session=hgh_session,
                user_routine_exercise=hgh_ure,
                exercise=hgh_ure.exercise,
                points=int(getattr(hgh_ure.exercise, "points", 0) or 0),
                sets_done=getattr(hgh_ure, "sets", None),
                reps_done=getattr(hgh_ure, "qty_min", None),
            )

    # Nutrition and lifestyle
    nsession = NutraSession.objects.create(user=user, date=on_date)
    mods = fixtures["nutrition"]["modules"]
    foods = fixtures["nutrition"]["foods"]

    # Adult: log two disc + two muscle to reach 100% nutrition bar potential.
    # Teen: log food points for dots; lifestyle points for dots.
    NutraEntry.objects.create(session=nsession, module=mods["disc"], food=foods["salmon"], score=3, servings="1")
    NutraEntry.objects.create(session=nsession, module=mods["muscle"], food=foods["collagen"], score=3, servings="1")

    if variant == "teen":
        NutraEntry.objects.create(session=nsession, module=mods["sleep"], activity_id=1, score=10)
        NutraEntry.objects.create(session=nsession, module=mods["sun"], activity_id=1, score=6)
        NutraEntry.objects.create(session=nsession, module=mods["med"], activity_id=1, score=1)
        NutraEntry.objects.create(session=nsession, module=mods["hyd"], activity_id=1, score=1)


class SeedDayDataAPIView(APIView):
    """
    Test endpoint to seed deterministic data and recompute ledger.
    Access rules:
      - allowed for staff users, OR
      - allowed when request includes header `X-Test-Seed-Token` matching `settings.TEST_SEED_TOKEN`

    POST /api/test/seed-day
    Body:
      - date: YYYY-MM-DD (required)
      - variant: adult|teen (optional; inferred from profile age if missing)
      - days: int (optional, default 0) -> also seed N previous days
      - include_scan: bool (optional, default true)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        is_staff = bool(getattr(request.user, "is_staff", False))
        seed_token = str(request.headers.get("X-Test-Seed-Token") or "").strip()
        expected = str(getattr(settings, "TEST_SEED_TOKEN", "") or "").strip()
        has_seed_token = bool(expected) and seed_token == expected
        if not (is_staff or has_seed_token):
            return Response({"error": "seed_token_required"}, status=status.HTTP_403_FORBIDDEN)

        try:
            on_date = _parse_date(request.data.get("date"))
        except Exception:
            return Response({"error": "invalid_date", "message": "date must be YYYY-MM-DD"}, status=422)

        days = int(request.data.get("days") or 0)
        include_scan = bool(request.data.get("include_scan", True))
        variant = str(request.data.get("variant") or "").strip().lower()

        profile = UserProfile.objects.filter(user=request.user).first()
        if not variant:
            try:
                age = int(float(getattr(profile, "age", 0) or 0))
            except Exception:
                age = 0
            variant = "adult" if age >= 21 else "teen"
        if variant not in {"adult", "teen"}:
            return Response({"error": "invalid_variant", "message": "variant must be adult|teen"}, status=422)

        fixtures = {
            "nutrition": _ensure_min_nutrition_fixtures(),
            "exercises": _ensure_min_exercise_fixtures(),
        }

        if include_scan:
            _seed_scan(request.user, on_date)

        start_date = on_date - timedelta(days=max(0, days))
        d = start_date
        while d <= on_date:
            _seed_day_logs(request.user, d, variant, fixtures)
            d += timedelta(days=1)

        try:
            rebuild_ledger_from_date(request.user, start_date)
        except Exception as e:
            return Response({"error": "rebuild_failed", "detail": str(e)}, status=500)

        return Response(
            {
                "ok": True,
                "user_id": request.user.id,
                "variant": variant,
                "seeded_from": str(start_date),
                "seeded_to": str(on_date),
                "include_scan": include_scan,
                "note": "Now call /api/dashboard-new to verify outputs for today.",
            },
            status=status.HTTP_200_OK,
        )

