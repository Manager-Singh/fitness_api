from django.test import TestCase

from utils.country import (
    DEFAULT_COUNTRY_CODE,
    country_flag_emoji,
    normalize_country_code,
    resolve_country_code,
)


class CountryCodeUtilTests(TestCase):
    def test_normalize_accepts_lowercase(self):
        self.assertEqual(normalize_country_code("ca"), "CA")

    def test_normalize_rejects_invalid(self):
        self.assertIsNone(normalize_country_code("CAN"))
        self.assertIsNone(normalize_country_code(""))

    def test_resolve_applies_default(self):
        self.assertEqual(resolve_country_code(None, default=DEFAULT_COUNTRY_CODE), "CA")

    def test_flag_emoji_for_known_code(self):
        self.assertEqual(country_flag_emoji("US"), "🇺🇸")

    def test_flag_emoji_unknown_is_none(self):
        self.assertIsNone(country_flag_emoji(None))
