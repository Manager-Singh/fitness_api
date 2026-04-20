from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Q, Sum, Count
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nutration.models_log import NutraEntry, NutraSession
from posture.models import PostureReport
from user_profile.models import UserProfile
from users.models import DailyLog, HeightLedger, PostureState
from utils.age import get_user_age, get_user_age_exact
from users.spec_runtime import compute_daily_height_for_user
from utils.check_payment import check_subscription_or_response
from utils.monetization_gate import compute_monetization_flags
from utils.engine_routing import apply_engine_routing
from utils.user_time import user_localize_dt, user_today
from workouts.models import Exercise, UserRoutine, WorkoutEntry, WorkoutSession
from workouts.serializers_log import WorkoutEntryReadSerializer
from nutration.serializers_log import NutraEntryReadSerializer


def _adult_free_logging_locked(user) -> bool:
    """Section 7.1 — unpaid adults cannot log exercises or nutrition/lifestyle."""
    try:
        age = int(get_user_age(user) or 0)
    except Exception:
        age = 0
    if age < 21:
        return False
    sub = check_subscription_or_response(user).data
    return not bool(sub.get("is_paid", False))


def _to_local_date(request, fallback):
    """
    Section 14.3: default log_date is the user's local calendar day.
    During the first ``grace_minutes`` after local midnight, ``client_timestamp`` may
    pin logs to *yesterday* only (same rule as DRF workout/nutra logs).
    Outside that window, client timestamps must not backdate.
    """
    now_local = user_localize_dt(request.user, timezone.now())
    local_date = now_local.date()
    grace_minutes = 5
    stamp = request.data.get("client_timestamp")
    if not stamp:
        return local_date if fallback is None else fallback
    in_grace = now_local.hour == 0 and now_local.minute < grace_minutes
    if in_grace:
        try:
            parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.utc)
            parsed_local = user_localize_dt(request.user, parsed.astimezone(timezone.utc))
            if parsed_local.date() == (local_date - timedelta(days=1)):
                return local_date - timedelta(days=1)
        except Exception:
            pass
    return local_date


def _adult_food_points_for_engine(user, log_date):
    """
    Spec Section 11.3/11.6 (adults):
    - only 4 qualifying foods count: top 2 from Disc + top 2 from Muscle
    - cap at 12 points/day
    """
    entries = NutraEntry.objects.filter(
        session__user=user,
        session__date=log_date,
        food__isnull=False,
    ).select_related("module")
    disc = []
    muscle = []
    for e in entries:
        module = getattr(e, "module", None)
        module_name = str(getattr(module, "name", "") or "").lower()
        module_cat = str(getattr(module, "nutrition_category", "") or "").lower()
        score = float(e.score or 0)
        if module_cat == "disc" or any(t in module_name for t in ("disc", "lubric", "spine")):
            disc.append(score)
        elif module_cat == "muscle" or any(t in module_name for t in ("muscle", "repair", "fuel")):
            muscle.append(score)
    selected = sorted(disc, reverse=True)[:2] + sorted(muscle, reverse=True)[:2]
    return float(sum(selected))


def _daily_totals_payload(user, log_date, *, age_exact):
    """
    Produce Section-17-style daily totals and gate/cap flags.
    """
    age = 0
    try:
        age = int(get_user_age(user) or 0)
    except Exception:
        age = 0
    exercise_logged_today = WorkoutEntry.objects.filter(
        session__user=user,
        session__date=log_date,
    ).exists()
    daily = DailyLog.objects.filter(user=user, log_date=log_date).first()

    daily_posture_pts_today = int((daily.engine1_points if daily else 0) or 0)
    daily_hgh_pts_today = int((daily.engine2_points if daily else 0) or 0)
    daily_lifestyle_pts_today = int((daily.lifestyle_points if daily else 0) or 0)

    # Nutrition: spec math has an exercise-validation gate.
    raw_food_points = (
        NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            food__isnull=False,
        ).aggregate(total=Sum("score"))["total"]
        or 0
    )
    raw_food_points = float(raw_food_points or 0)
    if age >= 21:
        effective_food_points = min(_adult_food_points_for_engine(user, log_date), 12.0) if exercise_logged_today else 0.0
        cap_limit = 12.0
        # "Cap reached" in adult mode means logged beyond what the engine can count.
        food_entry_count = NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            food__isnull=False,
        ).count()
        cap_reached = bool(food_entry_count > 4 or raw_food_points > effective_food_points or effective_food_points >= cap_limit)
    else:
        effective_food_points = min(raw_food_points, 35.0) if exercise_logged_today else 0.0
        cap_limit = 35.0
        cap_reached = bool(raw_food_points >= cap_limit)

    counts_toward_engine_nutrition = bool(exercise_logged_today and effective_food_points > 0)
    diary_note = "Daily nutrition cap reached. Recorded in diary only." if cap_reached else None

    daily_nutrition_pts_today = int(round(effective_food_points if age >= 21 else ((daily.food_points if daily else 0) or 0)))

    return {
        "daily_posture_pts_today": daily_posture_pts_today,
        "daily_hgh_pts_today": daily_hgh_pts_today,
        "daily_nutrition_pts_today": daily_nutrition_pts_today,
        "daily_lifestyle_pts_today": daily_lifestyle_pts_today,
        "exercises_done": bool(exercise_logged_today),
        "nutrition_counts_toward_engine": counts_toward_engine_nutrition,
        "cap_reached": bool(cap_reached),
        "diary_note": diary_note,
    }


class LogExerciseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _adult_free_logging_locked(request.user):
            return Response(
                {
                    "error": "paywall_required",
                    "detail": "Exercise logging is locked for free adult accounts.",
                    "gate": "adult_diagnosis_gate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        exercise_id = request.data.get("exercise_id")
        points = int(request.data.get("points", 0))
        if not exercise_id:
            return Response({"error": "exercise_id is required."}, status=422)
        try:
            exercise = Exercise.objects.get(id=exercise_id)
        except Exercise.DoesNotExist:
            return Response({"error": "invalid_exercise"}, status=422)

        user_routine = None
        user_routine_id = request.data.get("user_routine")
        if user_routine_id:
            try:
                user_routine = UserRoutine.objects.get(id=user_routine_id, user=request.user)
            except UserRoutine.DoesNotExist:
                return Response({"error": "invalid_user_routine"}, status=422)

        local_date = _to_local_date(request, user_today(request.user))
        before = DailyLog.objects.filter(user=request.user, log_date=local_date).first()
        before_engine1 = int((before.engine1_points if before else 0) or 0)
        before_engine2 = int((before.engine2_points if before else 0) or 0)
        last_entry = (
            WorkoutEntry.objects.filter(
                session__user=request.user,
                session__date=local_date,
                exercise=exercise,
            )
            .order_by("-created_at")
            .first()
        )
        if last_entry and (timezone.now() - last_entry.created_at).total_seconds() < 60:
            return Response(
                {
                    "error": "duplicate_log",
                    "message": "This exercise was already logged within 60 seconds.",
                    "cooldown_s": 60,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        session, _ = WorkoutSession.objects.get_or_create(
            user=request.user,
            user_routine=user_routine,
            date=local_date,
        )
        entry = WorkoutEntry.objects.create(
            session=session,
            exercise=exercise,
            points=max(0, points),
            sets_done=request.data.get("sets_done") or None,
            reps_done=request.data.get("reps_done") or None,
            duration_s=request.data.get("duration_s") or None,
        )
        age_exact = get_user_age_exact(request.user)
        apply_engine_routing(
            user=request.user,
            log_date=local_date,
            age_exact=age_exact,
            points=entry.points,
            routine_type=(user_routine.routine_type if user_routine else None),
            entry_kind="exercise",
        )
        daily = DailyLog.objects.filter(user=request.user, log_date=local_date).first()
        after_engine1 = int((daily.engine1_points if daily else 0) or 0)
        after_engine2 = int((daily.engine2_points if daily else 0) or 0)
        totals = _daily_totals_payload(request.user, local_date, age_exact=age_exact)
        return Response(
            {
                "logged": True,
                "log_date": str(local_date),
                "counts_toward_engine": True,
                "daily_posture_pts_today": totals["daily_posture_pts_today"],
                "daily_hgh_pts_today": totals["daily_hgh_pts_today"],
                "daily_nutrition_pts_today": totals["daily_nutrition_pts_today"],
                "daily_lifestyle_pts_today": totals["daily_lifestyle_pts_today"],
                "exercises_done": totals["exercises_done"],
                "engine1_points_delta": max(0, after_engine1 - before_engine1),
                "engine2_points_delta": max(0, after_engine2 - before_engine2),
                "entry": WorkoutEntryReadSerializer(entry).data,
            },
            status=status.HTTP_200_OK,
        )


class LogFoodAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _adult_free_logging_locked(request.user):
            return Response(
                {
                    "error": "paywall_required",
                    "detail": "Nutrition/lifestyle logging is locked for free adult accounts.",
                    "gate": "adult_diagnosis_gate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        module_id = request.data.get("module_id")
        food_id = request.data.get("food_id")
        if not module_id or not food_id:
            return Response({"error": "module_id and food_id are required."}, status=422)
        local_date = _to_local_date(request, user_today(request.user))
        before = DailyLog.objects.filter(user=request.user, log_date=local_date).first()
        before_engine1 = int((before.engine1_points if before else 0) or 0)
        before_engine2 = int((before.engine2_points if before else 0) or 0)
        session, _ = NutraSession.objects.get_or_create(user=request.user, date=local_date)
        entry = NutraEntry.objects.create(
            session=session,
            module_id=module_id,
            food_id=food_id,
            servings=request.data.get("servings", ""),
            score=request.data.get("score"),
        )
        age_exact = get_user_age_exact(request.user)
        apply_engine_routing(
            user=request.user,
            log_date=local_date,
            age_exact=age_exact,
            points=(entry.score or 0),
            entry_kind="food",
        )
        daily = DailyLog.objects.filter(user=request.user, log_date=local_date).first()
        after_engine1 = int((daily.engine1_points if daily else 0) or 0)
        after_engine2 = int((daily.engine2_points if daily else 0) or 0)
        totals = _daily_totals_payload(request.user, local_date, age_exact=age_exact)
        counts_toward_engine = bool(totals["nutrition_counts_toward_engine"])
        return Response(
            {
                "logged": True,
                "log_date": str(local_date),
                "counts_toward_engine": counts_toward_engine,
                "daily_posture_pts_today": totals["daily_posture_pts_today"],
                "daily_hgh_pts_today": totals["daily_hgh_pts_today"],
                "daily_nutrition_pts_today": totals["daily_nutrition_pts_today"],
                "daily_lifestyle_pts_today": totals["daily_lifestyle_pts_today"],
                "exercises_done": totals["exercises_done"],
                "cap_reached": totals["cap_reached"],
                "diary_note": totals["diary_note"],
                "engine1_points_delta": max(0, after_engine1 - before_engine1),
                "engine2_points_delta": max(0, after_engine2 - before_engine2),
                "entry": NutraEntryReadSerializer(entry).data,
            },
            status=status.HTTP_200_OK,
        )


class LogLifestyleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _adult_free_logging_locked(request.user):
            return Response(
                {
                    "error": "paywall_required",
                    "detail": "Nutrition/lifestyle logging is locked for free adult accounts.",
                    "gate": "adult_diagnosis_gate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        module_id = request.data.get("module_id")
        activity_id = request.data.get("activity_id")
        if not module_id or not activity_id:
            return Response({"error": "module_id and activity_id are required."}, status=422)
        local_date = _to_local_date(request, user_today(request.user))
        before = DailyLog.objects.filter(user=request.user, log_date=local_date).first()
        before_engine1 = int((before.engine1_points if before else 0) or 0)
        before_engine2 = int((before.engine2_points if before else 0) or 0)
        before_lifestyle = int((before.lifestyle_points if before else 0) or 0)
        session, _ = NutraSession.objects.get_or_create(user=request.user, date=local_date)
        entry = NutraEntry.objects.create(
            session=session,
            module_id=module_id,
            activity_id=activity_id,
            score=request.data.get("score"),
        )
        age_exact = get_user_age_exact(request.user)
        apply_engine_routing(
            user=request.user,
            log_date=local_date,
            age_exact=age_exact,
            points=(entry.score or 0),
            entry_kind="lifestyle",
        )
        daily = DailyLog.objects.filter(user=request.user, log_date=local_date).first()
        after_engine1 = int((daily.engine1_points if daily else 0) or 0)
        after_engine2 = int((daily.engine2_points if daily else 0) or 0)
        after_lifestyle = int((daily.lifestyle_points if daily else 0) or 0)
        totals = _daily_totals_payload(request.user, local_date, age_exact=age_exact)

        # Spec-style: lifestyle is teens-only for engine credit.
        pts_awarded = max(0, after_engine2 - before_engine2) if (age_exact is not None and float(age_exact) < 21.0) else 0
        counts_toward_engine = bool(pts_awarded > 0)
        return Response(
            {
                "logged": True,
                "log_date": str(local_date),
                "pts_awarded": int(pts_awarded),
                "counts_toward_engine": counts_toward_engine,
                "daily_posture_pts_today": totals["daily_posture_pts_today"],
                "daily_hgh_pts_today": totals["daily_hgh_pts_today"],
                "daily_nutrition_pts_today": totals["daily_nutrition_pts_today"],
                "daily_lifestyle_pts_today": totals["daily_lifestyle_pts_today"],
                "exercises_done": totals["exercises_done"],
                "engine1_points_delta": max(0, after_engine1 - before_engine1),
                "engine2_points_delta": max(0, after_engine2 - before_engine2),
                "lifestyle_points_delta": max(0, after_lifestyle - before_lifestyle),
                "entry": NutraEntryReadSerializer(entry).data,
            },
            status=status.HTTP_200_OK,
        )


class UserStateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Spec Section 14.1: reads should not mutate HeightLedger.
        # Runtime compute is handled by the daily pipeline/cron.
        #
        # Optional debug escape hatch: staff can force recompute explicitly.
        if str(request.query_params.get("recompute") or "").strip() in {"1", "true", "yes"} and bool(
            getattr(user, "is_staff", False)
        ):
            compute_daily_height_for_user(user, force_recompute=True)
        profile = UserProfile.objects.filter(user=user).first()
        posture_state, _ = PostureState.objects.get_or_create(user=user)
        has_scan = PostureReport.objects.filter(user=user).exists()
        if has_scan and not posture_state.scan_completed:
            posture_state.scan_completed = True
            posture_state.last_scan_at = profile.last_scan if profile else None
            posture_state.save(update_fields=["scan_completed", "last_scan_at", "updated_at"])

        today = user_today(user)
        daily = DailyLog.objects.filter(user=user, log_date=today).first()
        latest_ledger = (
            HeightLedger.objects.filter(user=user, entry_type="daily_compute")
            .order_by("-log_date", "-created_at")
            .first()
        )
        age_exact = get_user_age_exact(user)
        subscription = check_subscription_or_response(user).data
        monetization = compute_monetization_flags(int(age_exact or 0), subscription)
        points_today = 0
        if daily:
            points_today = (daily.exercise_points + daily.food_points + daily.lifestyle_points)
        return Response(
            {
                "user_id": user.id,
                "tier": user.account_tier,
                "age_exact": age_exact,
                "scan_completed": posture_state.scan_completed,
                "questionnaire_completed": posture_state.questionnaire_completed,
                "total_recoverable_loss_um": posture_state.total_recoverable_loss_um,
                "points_today": points_today,
                "engine1_points_today": daily.engine1_points if daily else 0,
                "engine2_points_today": daily.engine2_points if daily else 0,
                "conversion_enabled": monetization["conversion_enabled"],
                "full_access_trial_active": bool(monetization["is_teen"] and monetization["is_trial"] and not monetization["full_access_trial_expired"]),
                "full_access_trial_expired": monetization["full_access_trial_expired"],
                "current_height_um": latest_ledger.cumulative_um if latest_ledger else None,
                "last_scan_at": posture_state.last_scan_at,
            },
            status=status.HTTP_200_OK,
        )
