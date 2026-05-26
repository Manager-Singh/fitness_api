import unittest
from types import SimpleNamespace

from utils.account_tier import auth_track_fields, desired_account_tier
from utils.paywall_flags import account_age_bounds, is_adult_age, is_teen_age
from utils.profile_completeness import is_teen_for_profile_requirements


class GenderAccountTierTests(unittest.TestCase):
    def test_female_18_is_adult(self):
        self.assertEqual(desired_account_tier(age_exact=18.94, gender="female"), "adult")
        self.assertFalse(is_teen_age(18.94, gender="female"))
        self.assertTrue(is_adult_age(18.94, gender="female"))

    def test_male_18_is_teen(self):
        self.assertEqual(desired_account_tier(age_exact=18.5, gender="male"), "teen")
        self.assertTrue(is_teen_age(18.5, gender="male"))
        self.assertFalse(is_adult_age(18.5, gender="male"))

    def test_male_21_is_adult(self):
        self.assertEqual(desired_account_tier(age_exact=21.0, gender="male"), "adult")
        self.assertTrue(is_adult_age(21.0, gender="male"))

    def test_female_16_is_teen(self):
        self.assertEqual(desired_account_tier(age_exact=16.5, gender="female"), "teen")
        self.assertTrue(is_teen_age(16.5, gender="female"))

    def test_bounds_by_sex(self):
        f = account_age_bounds(gender="female")
        m = account_age_bounds(gender="male")
        self.assertEqual(f["teen_max"], 17.0)
        self.assertEqual(f["adult_min"], 18.0)
        self.assertEqual(m["teen_max"], 20.0)
        self.assertEqual(m["adult_min"], 21.0)


class ProfileRequirementsBySexTests(unittest.TestCase):
    def test_female_18_skips_parent_heights(self):
        user = SimpleNamespace(account_tier="teen")
        user.profile = SimpleNamespace(gender="female")

        import utils.profile_completeness as pc

        orig = pc.get_user_age_exact
        try:
            pc.get_user_age_exact = lambda _u: 18.9
            self.assertFalse(is_teen_for_profile_requirements(user))
        finally:
            pc.get_user_age_exact = orig

    def test_male_18_requires_parent_heights(self):
        user = SimpleNamespace(account_tier="adult")
        user.profile = SimpleNamespace(gender="male")

        import utils.profile_completeness as pc

        orig = pc.get_user_age_exact
        try:
            pc.get_user_age_exact = lambda _u: 18.5
            self.assertTrue(is_teen_for_profile_requirements(user))
        finally:
            pc.get_user_age_exact = orig


class AuthTrackFieldsBySexTests(unittest.TestCase):
    def test_female_18_login_fields(self):
        user = SimpleNamespace(account_tier="teen", id=1)
        user.save = lambda update_fields=None: None
        profile = SimpleNamespace(gender="female")

        import utils.account_tier as at

        orig_exact = at.get_user_age_exact
        orig_age = at.get_user_age
        orig_sex = at.user_profile_sex
        try:
            at.get_user_age_exact = lambda _u: 18.9
            at.get_user_age = lambda _u, default="currently": 18
            at.user_profile_sex = lambda _u: "female"
            fields = auth_track_fields(user, age_years=18)
        finally:
            at.get_user_age_exact = orig_exact
            at.get_user_age = orig_age
            at.user_profile_sex = orig_sex

        self.assertEqual(fields["account_tier"], "adult")
        self.assertEqual(fields["gender"], "female")
        self.assertFalse(fields["is_teen_track"])
        self.assertEqual(fields["dashboard_variant"], "adult")

    def test_male_18_login_fields(self):
        user = SimpleNamespace(account_tier="adult", id=1)
        user.save = lambda update_fields=None: None

        import utils.account_tier as at

        orig_exact = at.get_user_age_exact
        orig_age = at.get_user_age
        orig_sex = at.user_profile_sex
        try:
            at.get_user_age_exact = lambda _u: 18.5
            at.get_user_age = lambda _u, default="currently": 18
            at.user_profile_sex = lambda _u: "male"
            fields = auth_track_fields(user, age_years=18)
        finally:
            at.get_user_age_exact = orig_exact
            at.get_user_age = orig_age
            at.user_profile_sex = orig_sex

        self.assertEqual(fields["account_tier"], "teen")
        self.assertEqual(fields["gender"], "male")
        self.assertTrue(fields["is_teen_track"])
        self.assertEqual(fields["dashboard_variant"], "teen")
