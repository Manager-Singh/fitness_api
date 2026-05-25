"""Section 4.3 — Engine-1 daily gain redistributed by current loss share (active segments)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from users.models import PostureState
from users.spec_runtime import _redistribute_engine1_gain_across_segments
from utils.posture.height_constants import (
    POSTURE_SEGMENT_MAX_LOSS_CM,
    posture_segment_opt_pct_precise,
)


class SegmentGainRedistributionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="seg_redist_user",
            email="seg_redist@example.com",
            password="testpass123",
        )
        self.state, _ = PostureState.objects.get_or_create(user=self.user)
        self.state.spinal_current_loss_um = int(0.67 * 10000)
        self.state.collapse_current_loss_um = int(1.61 * 10000)
        self.state.pelvic_current_loss_um = int(1.59 * 10000)
        self.state.legs_current_loss_um = int(0.98 * 10000)
        self.state.total_recoverable_loss_um = int(5.03 * 10000)
        self.state.save()

    def _pct(self, loss_um: int, key: str) -> float:
        max_cm = POSTURE_SEGMENT_MAX_LOSS_CM[key]
        loss_cm = loss_um / 10000.0
        return posture_segment_opt_pct_precise(loss_cm, max_cm, decimals=2)

    def test_79_points_079cm_loss_proportional_not_full_gain_per_segment(self):
        """79 pts → 790 μm; spinal ~15% of gain (~119 μm), not 30% (~237 μm) or full 790 μm."""
        before = {
            "spinal": self.state.spinal_current_loss_um,
            "collapse": self.state.collapse_current_loss_um,
            "pelvic": self.state.pelvic_current_loss_um,
            "legs": self.state.legs_current_loss_um,
        }
        pct_before = {
            "spinal_compression": self._pct(before["spinal"], "spinal_compression"),
            "posture_collapse": self._pct(before["collapse"], "posture_collapse"),
            "pelvic_tilt_back": self._pct(before["pelvic"], "pelvic_tilt_back"),
            "leg_hamstring": self._pct(before["legs"], "leg_hamstring"),
        }

        gain_um = 790
        _redistribute_engine1_gain_across_segments(self.state, gain_um)
        self.state.refresh_from_db()

        after = {
            "spinal": self.state.spinal_current_loss_um,
            "collapse": self.state.collapse_current_loss_um,
            "pelvic": self.state.pelvic_current_loss_um,
            "legs": self.state.legs_current_loss_um,
        }
        total_reduced = sum(before[k] - after[k] for k in before)
        self.assertEqual(total_reduced, gain_um)

        spinal_share = before["spinal"] - after["spinal"]
        self.assertGreater(spinal_share, 80)
        self.assertLess(spinal_share, 160)
        self.assertLess(spinal_share, 200, "fixed 30% would give ~237 μm to spinal")

        pct_after_spinal = self._pct(after["spinal"], "spinal_compression")
        delta_spinal = pct_after_spinal - pct_before["spinal_compression"]
        self.assertLess(delta_spinal, 2.0, "spinal bar should move ~0.4%, not ~13%")
        self.assertGreater(delta_spinal, 0.1)

    def test_spinal_inactive_renormalizes_over_remaining_loss(self):
        """When spinal loss = 0, gain splits only across collapse/pelvic/legs by their losses."""
        self.state.spinal_current_loss_um = 0
        self.state.collapse_current_loss_um = 35000
        self.state.pelvic_current_loss_um = 25000
        self.state.legs_current_loss_um = 10000
        self.state.save()

        gain_um = 7000
        _redistribute_engine1_gain_across_segments(self.state, gain_um)
        self.state.refresh_from_db()

        self.assertEqual(self.state.spinal_current_loss_um, 0)
        self.assertEqual(self.state.collapse_current_loss_um, 35000 - int(round(7000 * 35000 / 70000)))

    def test_single_active_segment_gets_full_gain(self):
        self.state.collapse_current_loss_um = 0
        self.state.pelvic_current_loss_um = 0
        self.state.legs_current_loss_um = 0
        self.state.spinal_current_loss_um = 20000
        self.state.save()

        _redistribute_engine1_gain_across_segments(self.state, 500)
        self.state.refresh_from_db()
        self.assertEqual(self.state.spinal_current_loss_um, 19500)
