"""
One-time data heal for corrupted PostureState segment losses.

Background: a non-idempotent recompute path used to re-apply the Engine-1 segment
redistribution to PostureState on every force_recompute/rebuild without restoring the
baseline, so the optimization bars drifted far past the real, ledger-tracked recovery
(e.g. bars showing ~2.2 cm recovered while the ledger only earned ~0.1 cm).

This command re-derives the spec-correct value for every user:

    Current_Loss[segment] = assessment_baseline[segment] − cumulative Engine-1 recovery

It is safe to re-run (idempotent) and only touches users who have posture assessments.
"""
from django.core.management.base import BaseCommand

from users.models import PostureState
from utils.posture.state_recalculator import (
    _cumulative_engine1_recovery_um,
    _derive_assessment_baseline_um,
    _distribute_recovery_over_baseline,
    resync_segment_losses_from_baseline,
)

_SEG_ATTRS = (
    "spinal_current_loss_um",
    "collapse_current_loss_um",
    "pelvic_current_loss_um",
    "legs_current_loss_um",
)


class Command(BaseCommand):
    help = "Heal corrupted PostureState segment losses (Current_Loss = baseline − cumulative recovery)."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Heal a single user by email.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without saving.",
        )

    def handle(self, *args, **options):
        qs = PostureState.objects.select_related("user").all()
        if options.get("email"):
            qs = qs.filter(user__email=options["email"])

        healed = 0
        skipped = 0
        for state in qs:
            user = state.user
            before = tuple(int(getattr(state, a) or 0) for a in _SEG_ATTRS)

            if options.get("dry_run"):
                baseline_um = _derive_assessment_baseline_um(user, state)
                if baseline_um is None:
                    skipped += 1
                    continue
                recovered = _cumulative_engine1_recovery_um(user)
                shares = (
                    _distribute_recovery_over_baseline(baseline_um, recovered)
                    if recovered > 0
                    else {}
                )
                target = tuple(
                    max(0, baseline_um[a] - shares.get(a, 0)) for a in _SEG_ATTRS
                )
                if target != before:
                    healed += 1
                    self.stdout.write(f"{user.email}: {before} -> {target}")
                continue

            new_state = resync_segment_losses_from_baseline(user)
            if new_state is None:
                skipped += 1
                continue
            after = tuple(int(getattr(new_state, a) or 0) for a in _SEG_ATTRS)
            if after != before:
                healed += 1
                self.stdout.write(f"{user.email}: {before} -> {after}")

        verb = "Would heal" if options.get("dry_run") else "Healed"
        self.stdout.write(
            self.style.SUCCESS(f"{verb} {healed} user(s); skipped {skipped} (no assessments).")
        )
