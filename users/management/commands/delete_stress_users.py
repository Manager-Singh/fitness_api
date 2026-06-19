from __future__ import annotations

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = "Delete dummy stress-test users and their related data via cascades."

    def add_arguments(self, parser):
        parser.add_argument("--prefix", default="stress", help="Stress user prefix.")
        parser.add_argument("--domain", default="stress.local", help="Stress user email domain.")
        parser.add_argument("--dry-run", action="store_true", help="Only show how many users would be deleted.")
        parser.add_argument("--keep-fixtures", action="store_true", help="Keep shared stress-test fixture rows.")

    def handle(self, *args, **options):
        prefix = str(options["prefix"]).strip()
        domain = str(options["domain"]).strip()
        dry_run = bool(options["dry_run"])

        User = get_user_model()
        qs = User.objects.filter(
            Q(email__startswith=f"{prefix}_")
            | Q(email__startswith=f"{prefix}_teen_")
            | Q(email__startswith=f"{prefix}_adult_"),
            email__endswith=f"@{domain}",
            is_staff=False,
            is_superuser=False,
        )
        count = qs.count()
        if dry_run:
            self.stdout.write(f"Stress users matched: {count}")
            return

        user_ids = list(qs.values_list("id", flat=True))
        deleted_breakdown = self._delete_user_related_data(user_ids)
        deleted_count, user_delete_breakdown = qs.delete()
        for key, value in user_delete_breakdown.items():
            deleted_breakdown[key] = deleted_breakdown.get(key, 0) + value
        fixture_breakdown = {}
        if not bool(options["keep_fixtures"]):
            fixture_breakdown = self._delete_fixtures()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted stress users/data: users={count}, total_deleted_rows={deleted_count}"
            )
        )
        for model_name, model_count in sorted(deleted_breakdown.items()):
            self.stdout.write(f"  {model_name}: {model_count}")
        for model_name, model_count in sorted(fixture_breakdown.items()):
            self.stdout.write(f"  {model_name}: {model_count}")

    def _delete_user_related_data(self, user_ids):
        from chatbot.models import ChatMessage
        from height_analysis.models import GeneticHeightEstimate, HeightGrowthProjection
        from height_predictor.models import UltimateHeightPrediction
        from nutration.models_log import NutraEntry, NutraSession
        from posture.models import PostureReport
        from posture_analysis.models import PosturalRecommendation, UserPosturalOptimizationData
        from user_profile.models import Payment
        from workouts.models import WorkoutEntry, WorkoutSession, UserRoutine, UserRoutineExercise
        from users.models import DailyLog, FriendInvite, Friendship, HeightLedger, NotificationEventLog, OTP, PostureState

        breakdown = {}

        def add(name, deleted_tuple):
            deleted, details = deleted_tuple
            breakdown[name] = breakdown.get(name, 0) + deleted
            for key, value in details.items():
                breakdown[key] = breakdown.get(key, 0) + value

        with transaction.atomic():
            add("users.OTP(pre)", OTP.objects.filter(user_id__in=user_ids).delete())
            add("users.NotificationEventLog(pre)", NotificationEventLog.objects.filter(user_id__in=user_ids).delete())
            add("users.Friendship(a)", Friendship.objects.filter(user_id_a_id__in=user_ids).delete())
            add("users.Friendship(b)", Friendship.objects.filter(user_id_b_id__in=user_ids).delete())
            add("users.FriendInvite(inviter)", FriendInvite.objects.filter(inviter_id__in=user_ids).delete())
            add("users.FriendInvite(accepted)", FriendInvite.objects.filter(accepted_by_id__in=user_ids).delete())
            add("chatbot.ChatMessage(pre)", ChatMessage.objects.filter(user_id__in=user_ids).delete())
            add("users.DailyLog(pre)", DailyLog.objects.filter(user_id__in=user_ids).delete())
            add("users.HeightLedger(pre)", HeightLedger.objects.filter(user_id__in=user_ids).delete())
            add("users.PostureState(pre)", PostureState.objects.filter(user_id__in=user_ids).delete())
            add("height_predictor.UltimateHeightPrediction(pre)", UltimateHeightPrediction.objects.filter(user_id__in=user_ids).delete())

            routines = UserRoutine.objects.filter(user_id__in=user_ids)
            routine_ids = list(routines.values_list("id", flat=True))
            add("workouts.WorkoutEntry(user)", WorkoutEntry.objects.filter(session__user_id__in=user_ids).delete())
            if routine_ids:
                add("workouts.WorkoutEntry(routine)", WorkoutEntry.objects.filter(session__user_routine_id__in=routine_ids).delete())
            add("workouts.WorkoutSession(user)", WorkoutSession.objects.filter(user_id__in=user_ids).delete())
            if routine_ids:
                add("workouts.WorkoutSession(routine)", WorkoutSession.objects.filter(user_routine_id__in=routine_ids).delete())
            add("workouts.UserRoutineExercise(pre)", UserRoutineExercise.objects.filter(routine_id__in=routine_ids).delete())
            add("workouts.UserRoutine(pre)", routines.delete())

            add("nutration.NutraEntry(pre)", NutraEntry.objects.filter(session__user_id__in=user_ids).delete())
            add("nutration.NutraSession(pre)", NutraSession.objects.filter(user_id__in=user_ids).delete())
            add("posture.PostureReport(pre)", PostureReport.objects.filter(user_id__in=user_ids).delete())
            add("height_analysis.HeightGrowthProjection(pre)", HeightGrowthProjection.objects.filter(genetic_estimate__user_id__in=user_ids).delete())
            add("height_analysis.GeneticHeightEstimate(pre)", GeneticHeightEstimate.objects.filter(user_id__in=user_ids).delete())
            add("posture_analysis.PosturalRecommendation(pre)", PosturalRecommendation.objects.filter(user_data__user_id__in=user_ids).delete())
            add("posture_analysis.UserPosturalOptimizationData(pre)", UserPosturalOptimizationData.objects.filter(user_id__in=user_ids).delete())
            self._maybe_delete_model(breakdown, "wellness_tracker", "WellnessSubmission", user_id__in=user_ids)
            self._maybe_delete_model(breakdown, "exercise", "ExerciseSubmission", user_id__in=user_ids)
            add("user_profile.Payment(pre)", Payment.objects.filter(user_id__in=user_ids).delete())

        return breakdown

    def _maybe_delete_model(self, breakdown, app_label: str, model_name: str, **filters):
        if not django_apps.is_installed(app_label):
            return
        Model = django_apps.get_model(app_label, model_name)
        if Model is None:
            return
        deleted, details = Model.objects.filter(**filters).delete()
        breakdown[f"{app_label}.{model_name}(pre)"] = breakdown.get(f"{app_label}.{model_name}(pre)", 0) + deleted
        for key, value in details.items():
            breakdown[key] = breakdown.get(key, 0) + value

    def _delete_fixtures(self):
        from habits.models import MicroHabit
        from nutration.models import AgeGroup, Food, Module
        from payment_packages.models import PaymentPackage
        from workouts.models import Exercise

        out = {}
        deleted, _ = MicroHabit.objects.filter(code="stress-test-breathing").delete()
        out["habits.MicroHabit(stress)"] = deleted
        deleted, _ = Exercise.objects.filter(name="Stress Test Wall Angels").delete()
        out["workouts.Exercise(stress)"] = deleted
        deleted, _ = Food.objects.filter(name="Stress Test Food").delete()
        out["nutration.Food(stress)"] = deleted
        deleted, _ = Module.objects.filter(name="Stress Test Nutrition").delete()
        out["nutration.Module(stress)"] = deleted
        deleted, _ = AgeGroup.objects.filter(name="Stress Test All Ages").delete()
        out["nutration.AgeGroup(stress)"] = deleted
        deleted, _ = PaymentPackage.objects.filter(name="Stress Test Paid").delete()
        out["payment_packages.PaymentPackage(stress)"] = deleted
        return out
