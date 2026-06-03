from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from nutration.lifestyle_log import upsert_lifestyle_nutra_entry
from nutration.models import Activity, AgeGroup, Module, ModuleActivity
from nutration.models_log import NutraEntry, NutraSession

User = get_user_model()


class LifestyleUpsertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teen_life", password="x", email="t@e.com")
        self.ag = AgeGroup.objects.create(name="13-20", min_age=13, max_age=20)
        self.mod = Module.objects.create(
            name="Sleep",
            type=Module.LIFESTYLE,
            age_group=self.ag,
            wheel_type=True,
        )
        self.act_a = Activity.objects.create(name="Sleep Log A")
        self.act_b = Activity.objects.create(name="Sleep Log B")
        ModuleActivity.objects.create(module=self.mod, activity=self.act_a, score=5)
        ModuleActivity.objects.create(module=self.mod, activity=self.act_b, score=8)
        self.session = NutraSession.objects.create(user=self.user, date=date(2026, 5, 19))

    def test_second_log_same_module_updates_not_duplicates(self):
        upsert_lifestyle_nutra_entry(
            self.session, module=self.mod, activity=self.act_a, score=5
        )
        entry, created = upsert_lifestyle_nutra_entry(
            self.session, module=self.mod, activity=self.act_b, score=8
        )
        self.assertFalse(created)
        self.assertEqual(entry.score, 8)
        self.assertEqual(entry.activity_id, self.act_b.id)
        self.assertEqual(
            NutraEntry.objects.filter(
                session=self.session, module=self.mod, food__isnull=True
            ).count(),
            1,
        )
