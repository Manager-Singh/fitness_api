"""Monday E1 — Module lifestyle info popup API."""
from django.test import TestCase

from nutration.models import AgeGroup, Module
from nutration.serializers_plan import ModulePlanSerializer


class ModuleInfoPopupSerializerTests(TestCase):
    def test_info_popup_null_when_empty(self):
        ag = AgeGroup.objects.create(name="T13", min_age=13, max_age=20)
        mod = Module.objects.create(
            name="Sleep",
            type=Module.LIFESTYLE,
            age_group=ag,
            info_popup_title="",
            info_popup_body="",
        )
        data = ModulePlanSerializer(mod).data
        self.assertIsNone(data["info_popup"])

    def test_info_popup_object_when_set(self):
        ag = AgeGroup.objects.create(name="T14", min_age=13, max_age=20)
        mod = Module.objects.create(
            name="Hydration",
            type=Module.LIFESTYLE,
            age_group=ag,
            info_popup_title="HYDRATION 💧",
            info_popup_body="Stay hydrated.",
        )
        data = ModulePlanSerializer(mod).data
        self.assertEqual(data["info_popup"]["title"], "HYDRATION 💧")
        self.assertEqual(data["info_popup"]["body"], "Stay hydrated.")
