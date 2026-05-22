"""Tests for posture assessment reconciliation and routine regen threshold."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from posture.models import PostureAssessment
from users.models import PostureState, User
from utils.posture.state_recalculator import recalculate_posture_state
from utils.posture.state_to_breakdown import (
    breakdown_to_segment_um,
    posture_state_to_optimization_breakdown,
)
from utils.routine_regeneration_check import _max_segment_opt_delta_pct


class PostureReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="recon_user",
            email="recon@example.com",
            password="testpass123",
        )

    def _make_assessment(self, source, spinal_um, completed_at, **kwargs):
        defaults = {
            "collapse_loss_um": 0,
            "pelvic_loss_um": 0,
            "legs_loss_um": 0,
            "total_loss_um": spinal_um,
            "confidence_score": Decimal("1.00"),
            "is_active": True,
            "completed_at": completed_at,
        }
        defaults.update(kwargs)
        return PostureAssessment.objects.create(
            user=self.user,
            source=source,
            spinal_loss_um=spinal_um,
            **defaults,
        )

    def test_questionnaire_only_copies_to_state(self):
        self._make_assessment(
            PostureAssessment.SOURCE_QUESTIONNAIRE,
            24000,
            timezone.now(),
            collapse_loss_um=10000,
            pelvic_loss_um=5000,
            legs_loss_um=3000,
            total_loss_um=42000,
        )
        state = recalculate_posture_state(self.user)
        self.assertEqual(state.assessment_sources_used, PostureState.ASSESSMENT_SOURCES_QUESTIONNAIRE_ONLY)
        self.assertEqual(state.spinal_current_loss_um, 24000)

    def test_blend_scan_primary_70_30(self):
        t0 = timezone.now()
        t1 = t0 + timedelta(hours=1)
        self._make_assessment(
            PostureAssessment.SOURCE_QUESTIONNAIRE,
            10000,
            t0,
            total_loss_um=10000,
        )
        self._make_assessment(
            PostureAssessment.SOURCE_SCAN,
            20000,
            t1,
            total_loss_um=20000,
        )
        state = recalculate_posture_state(self.user)
        self.assertEqual(state.assessment_sources_used, PostureState.ASSESSMENT_SOURCES_BOTH_SCAN_PRIMARY)
        # 70% scan (20000) + 30% questionnaire (10000) = 17000
        self.assertEqual(state.spinal_current_loss_um, 17000)

    def test_state_to_breakdown_keys(self):
        state, _ = PostureState.objects.get_or_create(user=self.user)
        state.spinal_current_loss_um = 15000
        state.collapse_current_loss_um = 10000
        state.pelvic_current_loss_um = 5000
        state.legs_current_loss_um = 2000
        state.save()
        bd = posture_state_to_optimization_breakdown(state)
        self.assertIn("spinal_compression", bd)
        self.assertAlmostEqual(bd["spinal_compression"]["current_loss_cm"], 1.5)

    def test_breakdown_to_segment_um(self):
        bd = {
            "spinal_compression": {"current_loss_cm": 1.2},
            "posture_collapse": {"current_loss_cm": 0.5},
            "pelvic_tilt_back": {"current_loss_cm": 0.3},
            "leg_hamstring": {"current_loss_cm": 0.1},
        }
        um = breakdown_to_segment_um(bd)
        self.assertEqual(um["spinal"], 12000)
        self.assertEqual(um["total"], 12000 + 5000 + 3000 + 1000)

    def test_delta_pct_triggers_at_15(self):
        state = PostureState(
            spinal_current_loss_um=5000,
            collapse_current_loss_um=0,
            pelvic_current_loss_um=0,
            legs_current_loss_um=0,
        )
        snapshot = {"spinal_loss_um": 25000}
        delta = _max_segment_opt_delta_pct(snapshot, state)
        self.assertGreaterEqual(delta, 15.0)
