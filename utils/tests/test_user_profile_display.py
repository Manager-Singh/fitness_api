from types import SimpleNamespace

from django.test import SimpleTestCase

from utils.country import should_apply_country_default_timezone
from utils.user_profile_display import apply_display_name_to_user, resolved_display_name


class UserProfileDisplayTests(SimpleTestCase):
    def test_resolved_display_name_prefers_display_name(self):
        user = SimpleNamespace(display_name="denniss", name="Other", username="x@y.com")
        self.assertEqual(resolved_display_name(user), "denniss")

    def test_apply_name_syncs_both_fields(self):
        user = SimpleNamespace(display_name=None, name=None)
        apply_display_name_to_user(user, "denniss")
        self.assertEqual(user.display_name, "denniss")
        self.assertEqual(user.name, "denniss")

    def test_should_apply_tz_when_utc(self):
        user = SimpleNamespace(timezone="UTC")
        self.assertTrue(should_apply_country_default_timezone(user))
