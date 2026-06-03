"""Regen rec/beast path must still persist the full spec routine (10 exercises).

Regression: the partial-regen path (regen_rec_beast_only=True, used by daily /
dashboard recompute) had no backfill, so a short or name-colliding rec/beast
selection silently persisted only 9 exercises. It now backfills to 10.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase

from user_profile.models import UserProfile
from users.models import User
from utils.routine_genrate import generate_user_routines
from workouts.models import (
    AgeBracket,
    Exercise,
    ExerciseCategory,
    RoutineTemplate,
    RoutineType,
    RoutineVariant,
    Tier,
    Track,
    Unit,
    UserRoutine,
    UserRoutineExercise,
)


class RegenRoutineCountTests(TestCase):
    def _exercise(self, name, **kw):
        defaults = dict(
            points=5,
            category=ExerciseCategory.POSTURE,
            spinal_pct=25,
            collapse_pct=25,
            pelvic_pct=25,
            legs_pct=25,
            potency=5,
            teen_only=False,
        )
        defaults.update(kw)
        return Exercise.objects.create(name=name, **defaults)

    def setUp(self):
        self.bracket = AgeBracket.objects.create(title="21+", min_age=21, max_age=None)
        tmpl = RoutineTemplate.objects.create(name="Adult Posture")
        self.variant = RoutineVariant.objects.create(
            template=tmpl, age_bracket=self.bracket, track=Track.POSTURE
        )

        self.core_exs = [self._exercise(f"Core Move {i}") for i in range(6)]
        # Spare scorable pool for rec/beast + backfill headroom.
        self.pool_exs = [self._exercise(f"Pool Move {i}", potency=9 - i) for i in range(6)]

        u = User.objects.create_user(
            username="regenadult",
            email="regenadult@test.example",
            password="secret123",
        )
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.gender = "male"
        prof.birth_date = date.today() - timedelta(days=int(365.2425 * 25))
        prof.save()
        u.account_tier = "adult"
        u.save(update_fields=["account_tier"])
        # Re-fetch to avoid the stale reverse-OneToOne profile cache for age lookup.
        self.user = User.objects.get(pk=u.pk)

        self.routine = UserRoutine.objects.create(
            user=self.user, routine_type=RoutineType.POSTURE, is_active=True
        )
        for i, ex in enumerate(self.core_exs):
            UserRoutineExercise.objects.create(
                routine=self.routine,
                exercise=ex,
                tier=Tier.CORE,
                order=i + 1,
                sets=1,
                qty_min=10,
                unit=Unit.REPS,
            )

    def test_regen_backfills_to_10_when_selection_short(self):
        # Force a short selection: 2 recommended + only 1 beast (= 9 with Core 6).
        rec = self.pool_exs[:2]
        beast = self.pool_exs[2:3]
        with patch(
            "utils.routine_genrate.select_adult_recommended_beast",
            return_value=(rec, beast),
        ):
            generate_user_routines(
                self.user, {}, regen_rec_beast_only=True, existing_routine=self.routine
            )

        total = UserRoutineExercise.objects.filter(routine=self.routine).count()
        self.assertEqual(total, 10, "Regen must backfill rec/beast to the spec 10 exercises")
        self.assertEqual(
            UserRoutineExercise.objects.filter(routine=self.routine, tier=Tier.CORE).count(),
            6,
            "Core 6 must be preserved on partial regen",
        )
