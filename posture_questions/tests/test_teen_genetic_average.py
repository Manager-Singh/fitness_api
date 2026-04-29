"""Section 5.1b — Genetic_Average from MPH anchor + growth_table."""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from user_profile.models import UserProfile
from utils.posture.teen_genetic_average import (
    compute_daily_genetic_average_gain_cm,
    compute_genetic_average_cm,
    teen_growth_interp_rate_percent,
)

User = get_user_model()


class TeenGeneticAverageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ga_teen@test.com",
            username="ga_teen",
            password="x",
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.gender = "male"
        self.profile.father_height_cm = "180"
        self.profile.mother_height_cm = "160"
        self.profile.birth_date = date(2010, 6, 15)
        self.profile.base_height_cm = "165"
        self.profile.current_height_cm = "165"
        self.profile.save()

    def test_male_anchor_at_13(self):
        # MPH = (180+160+13)/2 = 176.5; anchor = 176.5 * 0.88
        with patch(
            "utils.posture.teen_genetic_average.get_user_age_exact_on_date",
            return_value=13.0,
        ):
            ga = compute_genetic_average_cm(self.user, date.today())
        self.assertAlmostEqual(ga, 176.5 * 0.88, places=2)

    def test_interp_rate_matches_spec_example(self):
        # Male 16.42: interp = 1.55 + 0.42*(1.10-1.55) = 1.361
        ir = teen_growth_interp_rate_percent("male", 16.42)
        self.assertAlmostEqual(ir, 1.361, places=3)

    def test_female_stops_at_17(self):
        self.profile.gender = "female"
        self.profile.father_height_cm = "175"
        self.profile.mother_height_cm = "165"
        self.profile.save()
        on = date.today()
        with patch(
            "utils.posture.teen_genetic_average.get_user_age_exact_on_date",
            return_value=18.0,
        ):
            self.assertEqual(compute_daily_genetic_average_gain_cm(self.user, on), 0.0)
        ir = teen_growth_interp_rate_percent("female", 17.5)
        self.assertEqual(ir, 0.0)

    def test_daily_gain_positive_teen_male(self):
        on = date.today()
        with patch(
            "utils.posture.teen_genetic_average.get_user_age_exact_on_date",
            return_value=16.42,
        ):
            ga = compute_genetic_average_cm(self.user, on)
            dg = compute_daily_genetic_average_gain_cm(self.user, on)
        self.assertGreater(ga, 150.0)
        self.assertGreater(dg, 0.0)
        ir = teen_growth_interp_rate_percent("male", 16.42)
        self.assertAlmostEqual(dg, round(ga * (ir / 100.0) / 365.0, 6), places=5)
