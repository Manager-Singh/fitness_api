from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from posture_questions.services.routine_service import RoutineService
from users.models import PostureState
from utils.posture.state_to_breakdown import posture_state_to_optimization_breakdown
from utils.routine_genrate import generate_user_routines
from workouts.models import RoutineType, UserRoutine


class Command(BaseCommand):
    help = "Fully regenerate active posture routines so users receive the latest Core 6 and targeted extra slots."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report affected users without changing routines.",
        )
        parser.add_argument(
            "--user",
            default=None,
            help="Limit to one user by id, email, or username.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Regenerate users without active routines too. Default only targets active posture routines.",
        )

    def _user_ids_from_arg(self, user_arg):
        if not user_arg:
            return None
        User = get_user_model()
        qs = User.objects.filter(Q(email__iexact=user_arg) | Q(username__iexact=user_arg))
        if str(user_arg).isdigit():
            qs = User.objects.filter(
                Q(pk=int(user_arg)) | Q(email__iexact=user_arg) | Q(username__iexact=user_arg)
            )
        return set(qs.values_list("id", flat=True))

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        include_without_active = bool(options["all"])
        user_ids = self._user_ids_from_arg(options.get("user"))

        User = get_user_model()
        users = User.objects.filter(is_active=True)
        if user_ids is not None:
            users = users.filter(id__in=user_ids)
        if not include_without_active:
            users = users.filter(
                custom_routines__is_active=True,
                custom_routines__routine_type=RoutineType.POSTURE,
            )
        users = users.distinct().order_by("id")

        processed = 0
        regenerated = 0
        skipped = 0
        for user in users.iterator(chunk_size=200):
            processed += 1
            state = PostureState.objects.filter(user=user).first()
            active = (
                UserRoutine.objects.filter(
                    user=user,
                    is_active=True,
                    routine_type=RoutineType.POSTURE,
                )
                .order_by("-created_at")
                .first()
            )
            fallback = getattr(active, "optimization_breakdown", None) if active else None
            breakdown = (
                posture_state_to_optimization_breakdown(state)
                if state
                else RoutineService.reconciled_optimization_breakdown(user, fallback)
            )
            if not breakdown:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"skip user={user.id}: no posture breakdown")
                )
                continue
            if dry_run:
                self.stdout.write(
                    f"would regenerate user={user.id} active_routine={getattr(active, 'id', None)}"
                )
                continue
            generate_user_routines(user, breakdown)
            regenerated += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"regenerated user={user.id} old_active={getattr(active, 'id', None)}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. processed={processed}, regenerated={regenerated}, skipped={skipped}, dry_run={dry_run}"
            )
        )
