from django.test import SimpleTestCase

from utils.posture.height_helpers import safe_float, safe_int
from utils.teen_optimized_height import safe_float as teen_safe_float


class HeightHelperTests(SimpleTestCase):
    def test_none_and_blank_return_defaults_without_exception_logs(self):
        with self.assertNoLogs("utils.posture.height_helpers", level="ERROR"):
            self.assertEqual(safe_float(None), 0.0)
            self.assertEqual(safe_float("", default=1.25), 1.25)
            self.assertEqual(safe_int(None), 0)
            self.assertEqual(safe_int("", default=7), 7)

    def test_invalid_strings_still_return_defaults(self):
        self.assertEqual(safe_float("not-a-number", default=2.5), 2.5)
        self.assertEqual(safe_int("not-a-number", default=3), 3)

    def test_teen_safe_float_handles_none_quietly(self):
        with self.assertNoLogs("utils.teen_optimized_height", level="ERROR"):
            self.assertEqual(teen_safe_float(None), 0.0)
            self.assertEqual(teen_safe_float("", default=4.5), 4.5)
