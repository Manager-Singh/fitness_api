from collections import defaultdict
from datetime import date
from django.db.models import Prefetch
from nutration.models_log import NutraSession
from workouts.models import WorkoutSession, UserRoutineExercise, ExerciseCategory, Tier
from utils.age import get_user_age


def calculate_green_dots(user, target_date=None):
    target_date = target_date or date.today()
    green_dots = defaultdict(int)

    # ───── NUTRITION + LIFESTYLE ─────
    session = (
        NutraSession.objects
        .filter(user=user, date=target_date)
        .prefetch_related("entries__food", "entries__activity", "entries__module")
        .first()
    )

    nutrition_score = 0
    lifestyle_activities = set()

    if session:
        for entry in session.entries.all():
            if entry.food:
                try:
                    nutrition_score += int(entry.score or 0)
                except (ValueError, TypeError):
                    continue
            elif entry.activity and entry.module and entry.module.type == "LIFE":
                lifestyle_activities.add(entry.activity.name)

    green_dots["lifestyle"] = min(len(lifestyle_activities), 4)

    if nutrition_score >= 31:
        green_dots["nutrition"] = 4
    elif nutrition_score >= 21:
        green_dots["nutrition"] = 3
    elif nutrition_score >= 11:
        green_dots["nutrition"] = 2
    elif nutrition_score >= 1:
        green_dots["nutrition"] = 1

    # ───── WORKOUT (all sessions) ─────
    w_sessions = (
        WorkoutSession.objects
        .filter(user=user, date=target_date)
        .select_related("user_routine")
        .prefetch_related(
            "entries__exercise",
            Prefetch(
                "user_routine__exercises",
                queryset=UserRoutineExercise.objects.select_related("exercise"),
                to_attr="prefetched_exercises",
            ),
        )
    )

    posture_dots = 0
    hgh_dots = 0

    try:
        age = get_user_age(user)
    except Exception:
        age = 0

    for wsession in w_sessions:
        if not wsession.user_routine:
            continue

        # prescriptions now come from UserRoutineExercise
        prescriptions = {
            ure.exercise_id: ure.tier
            for ure in getattr(wsession.user_routine, "prefetched_exercises", [])
        }

        for entry in wsession.entries.all():
            ex = entry.exercise
            tier = prescriptions.get(ex.id)

            # POSTURE exercises
            # if ex.category in [
            #     ExerciseCategory.POSTURE,
            #     ExerciseCategory.ENVIRONMENT,
            #     ExerciseCategory.GENERAL,
            # ]:
            if (wsession.user_routine.routine_type == "POSTURE"
            and tier in [Tier.CORE, Tier.RECOMMENDED,Tier.BEAST]):
                posture_dots += 1

            # HGH exercises (only if user_routine is HGH)
            if (
                wsession.user_routine.routine_type == "HGH"
                and tier in [Tier.CORE, Tier.RECOMMENDED,Tier.BEAST]
            ):
                hgh_dots += 1

    #  Final posture dot (limit by age)
    max_posture = 8 if age >= 21 else 6
    green_dots["posture"] = min(posture_dots, max_posture)

    #  Final HGH dot (max 2)
    green_dots["hgh_boost"] = min(hgh_dots, 2)
    t_lifestyle_dots = 0 if age >= 21 else 4    
    l_nutrition_dots = 4 if age >= 21 else 4    
    # Debug
    print(f" posture_ex = {posture_dots}, hgh_ex = {hgh_dots}, age = {age}")
    print(f" Final green_dots: {dict(green_dots)}")

    lifestyle_dots = green_dots["lifestyle"]
    nutrition_dots = green_dots["nutrition"]
    posture_dots = green_dots["posture"]

    total_ln_dots = lifestyle_dots + nutrition_dots  # max = 8
    max_ln_dot = t_lifestyle_dots + l_nutrition_dots  # max = 8


    lifestyle_nutrition_percent = float((total_ln_dots / max_ln_dot) * 100)
    lifestyle_percent = float((lifestyle_dots / 4) * 100)
    nutrition_percent = float((nutrition_dots / 4) * 100)
    posture_percent = float((posture_dots / max_posture) * 100)
    
    return {
        "lifestyle": green_dots["lifestyle"],
        "nutrition": green_dots["nutrition"],
        "posture": green_dots["posture"],
        "hgh_boost": green_dots["hgh_boost"],
        "lifestyle_nutrition": lifestyle_nutrition_percent,
        "posture_percent": posture_percent,
        "posture_count":max_posture,
        "max_ln_dot":max_ln_dot,
        "lifestyle_percent":lifestyle_percent,
        "nutrition_percent":nutrition_percent
    }
