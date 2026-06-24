"""Recompute stored questionnaire assessments under the posture targeting scoring.

The Monday work order changed the questionnaire math to A-F answer fractions,
height-scaled pillar caps, and targeted posture deficiencies. This command re-runs
the current scoring on already-stored answers and re-saves the assessment.

It reuses the exact same extraction + scoring + persistence path as the live
submit view, so there is no logic drift.

Usage:
    python manage.py recompute_issue9_questionnaire_scoring --dry-run
    python manage.py recompute_issue9_questionnaire_scoring --user qqqq@yopmail.com
    python manage.py recompute_issue9_questionnaire_scoring          # all eligible users
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from posture_questions.models import PostureQuestion
from utils.posture.assessment_service import save_questionnaire_assessment
from utils.posture.issue9_visual_scoring import compute_issue9_visual_results
from utils.posture.section3_manual_scoring import _pick_single_with_options


def _extract_issue9_letters(posture_q):
    """Same field/option mapping the submit view uses to build A-F answers."""
    return {
        "q1": _pick_single_with_options(posture_q.forward_head_posture_answer, posture_q.forward_head_posture_options),
        "q2": _pick_single_with_options(posture_q.gap_between_your_lower_back_answer, posture_q.gap_between_your_lower_back_options),
        "q3": _pick_single_with_options(posture_q.tightness_or_discomfort_answer, posture_q.tightness_or_discomfort_options),
        "q4": _pick_single_with_options(posture_q.slouch_when_standing_or_sitting_answer, posture_q.slouch_when_standing_or_sitting_options),
        "q5": _pick_single_with_options(posture_q.feel_noticeably_shorter_end_of_day_compare_to_morning_answer, posture_q.feel_noticeably_shorter_end_of_day_compare_to_morning_options),
        "q6": _pick_single_with_options(posture_q.perfectly_aligned_and_decompressed_answer, posture_q.perfectly_aligned_and_decompressed_options),
        "q7": _pick_single_with_options(posture_q.flexible_in_your_hamstrings_and_hips_answer, posture_q.flexible_in_your_hamstrings_and_hips_options),
        "q8": _pick_single_with_options(posture_q.active_your_core_during_daily_task_answer, posture_q.active_your_core_during_daily_task_options),
    }


def _breakdown_from_segments(segs):
    """Map issue9 segment payload -> the optimization_breakdown the assessment expects."""
    return {
        "spinal_compression": {
            "current_loss_cm": float(segs["spinal"]["loss_cm"]),
            "max_loss_cm": float(segs["spinal"]["max_loss"]),
            "percent_optimized": float(segs["spinal"]["opt_pct"]),
        },
        "posture_collapse": {
            "current_loss_cm": float(segs["collapse"]["loss_cm"]),
            "max_loss_cm": float(segs["collapse"]["max_loss"]),
            "percent_optimized": float(segs["collapse"]["opt_pct"]),
        },
        "pelvic_tilt_back": {
            "current_loss_cm": float(segs["pelvic"]["loss_cm"]),
            "max_loss_cm": float(segs["pelvic"]["max_loss"]),
            "percent_optimized": float(segs["pelvic"]["opt_pct"]),
        },
        "leg_hamstring": {
            "current_loss_cm": float(segs["legs"]["loss_cm"]),
            "max_loss_cm": float(segs["legs"]["max_loss"]),
            "percent_optimized": float(segs["legs"]["opt_pct"]),
        },
    }


class Command(BaseCommand):
    help = "Recompute stored questionnaire assessments under posture targeting scoring."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )
        parser.add_argument(
            "--user",
            default=None,
            help="Limit to a single user by id, email, or username.",
        )

    def _resolve_users(self, user_arg):
        User = get_user_model()
        if not user_arg:
            return None
        qs = User.objects.filter(
            Q(email__iexact=user_arg) | Q(username__iexact=user_arg)
        )
        if str(user_arg).isdigit():
            qs = User.objects.filter(
                Q(pk=int(user_arg)) | Q(email__iexact=user_arg) | Q(username__iexact=user_arg)
            )
        return set(qs.values_list("id", flat=True))

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        user_ids = self._resolve_users(options.get("user"))

        pq_qs = PostureQuestion.objects.select_related("user")
        if user_ids is not None:
            if not user_ids:
                self.stdout.write(self.style.WARNING("No matching user found."))
                return
            pq_qs = pq_qs.filter(user_id__in=user_ids)

        from users.models import PostureState

        updated = 0
        skipped_non_issue9 = 0
        processed = 0

        for posture_q in pq_qs.iterator():
            processed += 1
            letters = _extract_issue9_letters(posture_q)
            if not all(v in ("A", "B", "C", "D", "E", "F") for v in letters.values()):
                skipped_non_issue9 += 1
                continue

            profile = getattr(posture_q.user, "profile", None)
            height_cm = getattr(profile, "current_height_cm", None) or getattr(profile, "base_height_cm", None)
            result = compute_issue9_visual_results(letters, height_cm=height_cm, clamp_min_cm=0.0)
            new_total = float(result["total_recoverable_loss_cm"])

            state = PostureState.objects.filter(user_id=posture_q.user_id).first()
            old_total_um = int(getattr(state, "total_recoverable_loss_um", 0) or 0) if state else 0
            old_total_cm = round(old_total_um / 10000.0, 2)

            label = getattr(posture_q.user, "email", None) or getattr(posture_q.user, "username", posture_q.user_id)
            self.stdout.write(
                f"user={label} answers={''.join(letters[f'q{i}'] for i in range(1, 9))} "
                f"old={old_total_cm}cm -> new={round(new_total, 2)}cm"
            )

            if dry_run:
                continue

            breakdown = _breakdown_from_segments(result["segments"])
            save_questionnaire_assessment(
                posture_q.user,
                breakdown,
                raw_data={
                    "mode": "posture_targeting_v1",
                    "answers": letters,
                    "recomputed_by": "recompute_issue9_questionnaire_scoring",
                    "scoring_meta": result.get("meta", {}),
                },
            )
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. processed={processed}, recomputed={updated}, "
                f"skipped_non_issue9={skipped_non_issue9}, dry_run={dry_run}"
            )
        )
