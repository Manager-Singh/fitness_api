"""Admin progress bars must render (format_html cannot use {:.2f} placeholders)."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils.html import format_html

from users.admin_ui import _segment_bars_from_diagnostics


class AdminProgressBarsTest(SimpleTestCase):
    def test_format_html_rejects_float_format_spec(self):
        with self.assertRaises(ValueError):
            format_html("{} {:.2f} cm", "loss", 1.5)

    def test_segment_bars_render_four_rows(self):
        class FakeState:
            spinal_current_loss_um = 15000
            collapse_current_loss_um = 12000
            pelvic_current_loss_um = 8000
            legs_current_loss_um = 5000

        user = MagicMock(pk=1, id=1)
        with patch("users.admin_ui.PostureState") as ps, patch(
            "users.admin_ui._today_engine1_segment_shares",
            return_value=(0, {}),
        ):
            ps.objects.filter.return_value.first.return_value = FakeState()
            html = str(_segment_bars_from_diagnostics(user))

        self.assertEqual(html.count("hm-seg-row"), 4)
        self.assertIn("hm-seg-fill-base", html)
