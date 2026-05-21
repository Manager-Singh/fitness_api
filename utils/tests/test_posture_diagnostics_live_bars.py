"""Posture optimization bars use live PostureState after unlock, not frozen scan breakdown."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from users.models import PostureState
from utils.posture.diagnostics_contract import build_posture_optimization_diagnostics
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM


class PostureDiagnosticsLiveBarsTests(TestCase):
    def test_unlocked_user_prefers_runtime_over_stale_breakdown(self):
        user = get_user_model().objects.create_user(
            username="live_bars_user",
            email="live_bars@example.com",
            password="testpass123",
        )
        state, _ = PostureState.objects.get_or_create(user=user)
        state.scan_completed = True
        state.questionnaire_completed = True
        state.total_recoverable_loss_um = int(2.6 * 10000)
        state.spinal_current_loss_um = int(0.10 * 10000)
        state.collapse_current_loss_um = int(0.96 * 10000)
        state.pelvic_current_loss_um = int(0.53 * 10000)
        state.legs_current_loss_um = int(0.52 * 10000)
        state.save()

        stale_breakdown = {}
        for seg, max_loss in POSTURE_SEGMENT_MAX_LOSS_CM.items():
            stale_breakdown[seg] = {
                "current_loss_cm": max_loss * 0.4,
                "max_loss_cm": max_loss,
                "percent_optimized": 60,
            }

        diag = build_posture_optimization_diagnostics(
            user=user,
            optimization_breakdown=stale_breakdown,
            source="ai_scan",
        )
        spinal = diag["segments"]["spinal_compression"]
        self.assertAlmostEqual(spinal["current_loss_cm"], 0.10, places=2)
        self.assertGreater(spinal["percent_optimized_precise"], 90.0)
