from datetime import date

from django.test import SimpleTestCase

from utils.age import age_years_days_since_last_birthday, format_age_exact_years_days


class AgeExactTests(SimpleTestCase):
    def test_birthday_alignment_zero_days(self):
        dob = date(2010, 6, 10)
        ref = date(2024, 6, 10)
        self.assertEqual(age_years_days_since_last_birthday(dob, ref), (14, 0))
        self.assertEqual(format_age_exact_years_days(dob, ref), "14 years 0 days old")

    def test_days_since_last_birthday(self):
        dob = date(2010, 6, 10)
        ref = date(2024, 8, 20)
        years, days = age_years_days_since_last_birthday(dob, ref)
        self.assertEqual(years, 14)
        self.assertEqual(days, (ref - date(2024, 6, 10)).days)

    def test_feb_29_on_non_leap_year(self):
        dob = date(2020, 2, 29)
        ref = date(2023, 3, 1)
        years, days = age_years_days_since_last_birthday(dob, ref)
        self.assertEqual(years, 3)
        self.assertEqual(days, (ref - date(2023, 2, 28)).days)
