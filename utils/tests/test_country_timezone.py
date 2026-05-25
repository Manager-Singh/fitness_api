from django.test import SimpleTestCase

from utils.country import default_timezone_for_country


class CountryTimezoneTests(SimpleTestCase):
    def test_canada_defaults_central(self):
        self.assertEqual(default_timezone_for_country("CA"), "America/Winnipeg")

    def test_unknown_country_utc(self):
        self.assertEqual(default_timezone_for_country("US"), "UTC")
