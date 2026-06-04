from django.test import SimpleTestCase

from payment_packages.duration_utils import (
    decode_duration,
    encode_duration,
    format_duration_label,
    package_duration_days,
)


class PackageDurationUtilsTests(SimpleTestCase):
    def test_encode_decode_roundtrip(self):
        for count in range(1, 13):
            for unit in "dwmy":
                code = encode_duration(count, unit)
                self.assertEqual(len(code), 2)
                self.assertEqual(decode_duration(code), (count, unit))

    def test_legacy_month_codes(self):
        self.assertEqual(decode_duration("3"), (3, "m"))
        self.assertEqual(decode_duration("12"), (12, "m"))
        self.assertEqual(package_duration_days("12"), 360)

    def test_short_plans(self):
        self.assertEqual(package_duration_days(encode_duration(7, "d")), 7)
        self.assertEqual(package_duration_days(encode_duration(1, "w")), 7)
        self.assertEqual(package_duration_days(encode_duration(1, "m")), 30)
        self.assertEqual(package_duration_days(encode_duration(1, "y")), 365)

    def test_labels(self):
        self.assertEqual(format_duration_label(encode_duration(7, "d")), "7 Days")
        self.assertEqual(format_duration_label(encode_duration(1, "w")), "1 Week")
        self.assertEqual(format_duration_label("3"), "3 Months")
