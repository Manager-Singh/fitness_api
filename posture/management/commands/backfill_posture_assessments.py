"""One-time backfill: create PostureAssessment rows from existing PostureState."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from posture.models import PostureAssessment
from users.models import PostureState
from utils.posture.state_recalculator import recalculate_posture_state


class Command(BaseCommand):
    help = "Backfill posture_assessments from existing PostureState rows"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        created = 0
        skipped = 0

        for state in PostureState.objects.select_related("user").iterator():
            if not state.scan_completed and not state.questionnaire_completed:
                skipped += 1
                continue

            if PostureAssessment.objects.filter(user_id=state.user_id).exists():
                skipped += 1
                continue

            if state.scan_completed and state.last_scan_at:
                source = PostureAssessment.SOURCE_SCAN
                completed_at = state.last_scan_at
            elif state.questionnaire_completed:
                source = PostureAssessment.SOURCE_QUESTIONNAIRE
                completed_at = (
                    state.questionnaire_completed_at
                    or state.last_recalculated_at
                    or state.updated_at
                )
            else:
                skipped += 1
                continue

            if dry_run:
                created += 1
                continue

            PostureAssessment.objects.create(
                user_id=state.user_id,
                source=source,
                spinal_loss_um=int(state.spinal_current_loss_um or 0),
                collapse_loss_um=int(state.collapse_current_loss_um or 0),
                pelvic_loss_um=int(state.pelvic_current_loss_um or 0),
                legs_loss_um=int(state.legs_current_loss_um or 0),
                total_loss_um=int(state.total_recoverable_loss_um or 0),
                confidence_score=1.00,
                is_active=True,
                completed_at=completed_at or timezone.now(),
                raw_data={"backfilled": True},
            )
            recalculate_posture_state(state.user)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete: created={created}, skipped={skipped}, dry_run={dry_run}"
            )
        )
