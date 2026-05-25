"""Section 4.3 — Engine-1 daily gain redistributed proportional to segment current loss."""
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
        # Client scenario: total current loss ~4.43 cm
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

    def test_79_points_079cm_proportional_shares_not_full_gain_per_segment(self):
        """79 pts → 0.079 cm (790 um); each segment gets loss-proportional share only."""
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

        gain_um = 790  # 0.079 cm
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

        # Spinal ~15.1% of gain → ~119 um, not 790 um
        spinal_share = before["spinal"] - after["spinal"]
        self.assertGreater(spinal_share, 80)
        self.assertLess(spinal_share, 160)

        pct_after_spinal = self._pct(after["spinal"], "spinal_compression")
        delta_spinal = pct_after_spinal - pct_before["spinal_compression"]
        self.assertLess(delta_spinal, 2.0, "spinal bar should move ~0.4%, not ~13%")
        self.assertGreater(delta_spinal, 0.1)

        for key, um_key in [
            ("posture_collapse", "collapse"),
            ("pelvic_tilt_back", "pelvic"),
            ("leg_hamstring", "legs"),
        ]:
            delta = self._pct(after[um_key], key) - pct_before[key]
            self.assertLess(delta, 3.0, f"{key} bar jump too large")

    def test_single_active_segment_gets_full_gain(self):
        self.state.collapse_current_loss_um = 0
        self.state.pelvic_current_loss_um = 0
        self.state.legs_current_loss_um = 0
        self.state.spinal_current_loss_um = 20000
        self.state.save()

        _redistribute_engine1_gain_across_segments(self.state, 500)
        self.state.refresh_from_db()
        self.assertEqual(self.state.spinal_current_loss_um, 19500)
        self.assertEqual(self.state.collapse_current_loss_um, 0)
