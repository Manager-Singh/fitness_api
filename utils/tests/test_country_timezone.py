from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from utils.country import default_timezone_for_country


class CountryTimezoneTests(SimpleTestCase):
    def test_canada_defaults_central(self):
        self.assertEqual(default_timezone_for_country("CA"), "America/Winnipeg")

    def test_unknown_country_utc(self):
        # Multi-zone country left unmapped -> UTC fallback (US spans many zones).
        self.assertEqual(default_timezone_for_country("US"), "UTC")

    def test_belgium_resolves_to_brussels(self):
        """Bug 7a: Belgium must map to Europe/Brussels, not bare UTC."""
        self.assertEqual(default_timezone_for_country("BE"), "Europe/Brussels")
        self.assertEqual(default_timezone_for_country("be"), "Europe/Brussels")

    def test_belgium_dst_offsets(self):
        """Europe/Brussels gives CET (+1) in winter and CEST (+2) in summer."""
        tz = ZoneInfo(default_timezone_for_country("BE"))
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        summer = datetime(2026, 7, 15, 12, 0, tzinfo=tz)
        self.assertEqual(winter.utcoffset().total_seconds(), 3600)  # UTC+1
        self.assertEqual(summer.utcoffset().total_seconds(), 7200)  # UTC+2

    def test_other_eu_countries_mapped(self):
        self.assertEqual(default_timezone_for_country("FR"), "Europe/Paris")
        self.assertEqual(default_timezone_for_country("DE"), "Europe/Berlin")
        self.assertEqual(default_timezone_for_country("GB"), "Europe/London")
