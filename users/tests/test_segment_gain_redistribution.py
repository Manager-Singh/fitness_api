"""Section 4.3 — Engine-1 daily gain redistributed by FIXED segment ratios (30/35/25/10).

Per spec v34 §4.3 / §9 the daily gain is split across active segments by the fixed
segment ratios, renormalized over the active set — NOT by each segment's current loss.
"""
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

    def test_all_active_uses_fixed_30_35_25_10_ratios(self):
        """All four active → gain split by fixed ratios: spinal 30%, collapse 35%, pelvic 25%, legs 10%."""
        before = {
            "spinal": self.state.spinal_current_loss_um,
            "collapse": self.state.collapse_current_loss_um,
            "pelvic": self.state.pelvic_current_loss_um,
            "legs": self.state.legs_current_loss_um,
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
        deltas = {seg: before[seg] - after[seg] for seg in before}
        # Largest-remainder (Hamilton) apportionment: shares sum to exactly the gain
        # (no over/under allocation from independent rounding) and Legs always gets its
        # fixed 10% slice. spinal=237.0 and legs=79.0 are exact; the leftover unit from
        # the collapse/pelvic .5 remainders goes to collapse (stable tie order).
        self.assertEqual(sum(deltas.values()), gain_um)
        self.assertEqual(deltas["spinal"], 237)
        self.assertEqual(deltas["collapse"], 277)
        self.assertEqual(deltas["pelvic"], 197)
        self.assertEqual(deltas["legs"], 79)

    def test_spinal_inactive_renormalizes_over_active_ratios(self):
        """Spec worked example: spinal at 0 → collapse 35/70=50%, pelvic 25/70≈36%, legs 10/70≈14%."""
        self.state.spinal_current_loss_um = 0
        self.state.collapse_current_loss_um = 35000
        self.state.pelvic_current_loss_um = 25000
        self.state.legs_current_loss_um = 10000
        self.state.save()

        gain_um = 7000
        _redistribute_engine1_gain_across_segments(self.state, gain_um)
        self.state.refresh_from_db()

        self.assertEqual(self.state.spinal_current_loss_um, 0)
        # Active ratios renormalize over 0.35 + 0.25 + 0.10 = 0.70.
        self.assertEqual(
            self.state.collapse_current_loss_um, 35000 - round(gain_um * 0.35 / 0.70)
        )
        self.assertEqual(
            self.state.pelvic_current_loss_um, 25000 - round(gain_um * 0.25 / 0.70)
        )
        self.assertEqual(
            self.state.legs_current_loss_um, 10000 - round(gain_um * 0.10 / 0.70)
        )

    def test_single_active_segment_gets_full_gain(self):
        self.state.collapse_current_loss_um = 0
        self.state.pelvic_current_loss_um = 0
        self.state.legs_current_loss_um = 0
        self.state.spinal_current_loss_um = 20000
        self.state.save()

        _redistribute_engine1_gain_across_segments(self.state, 500)
        self.state.refresh_from_db()
        self.assertEqual(self.state.spinal_current_loss_um, 19500)

    def test_legs_gets_its_share_and_total_is_fully_allocated(self):
        """
        Bug 3 regression: Legs & Hamstring (ratio 0.10) must receive its fixed slice of
        the daily Engine-1 gain like every other active segment, and the per-segment
        shares must sum to exactly the gain (largest-remainder apportionment never loses
        or over-allocates units the way independent rounding could).
        """
        self.state.spinal_current_loss_um = 10000
        self.state.collapse_current_loss_um = 10000
        self.state.pelvic_current_loss_um = 10000
        self.state.legs_current_loss_um = 10000
        self.state.save()
        before = {
            "spinal": self.state.spinal_current_loss_um,
            "collapse": self.state.collapse_current_loss_um,
            "pelvic": self.state.pelvic_current_loss_um,
            "legs": self.state.legs_current_loss_um,
        }

        gain_um = 500  # a realistic single-day gain (0.05 cm)
        _redistribute_engine1_gain_across_segments(self.state, gain_um)
        self.state.refresh_from_db()
        deltas = {
            "spinal": before["spinal"] - self.state.spinal_current_loss_um,
            "collapse": before["collapse"] - self.state.collapse_current_loss_um,
            "pelvic": before["pelvic"] - self.state.pelvic_current_loss_um,
            "legs": before["legs"] - self.state.legs_current_loss_um,
        }
        self.assertEqual(sum(deltas.values()), gain_um)
        self.assertEqual(deltas["legs"], 50)  # 500 * 0.10
        self.assertGreater(deltas["legs"], 0, "Legs must not be frozen at 0.")
