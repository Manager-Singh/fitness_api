"""Log embed dashboard metrics (Monday B2)."""
from django.test import SimpleTestCase

from utils.log_embed_metrics import teen_top_cards_from_metrics


class TeenTopCardsEmbedTests(SimpleTestCase):
    def test_genetic_and_posture_cards_differ_when_only_posture_logged(self):
        metrics = {
            "genetic_plus_today_cm": 0.0,
            "posture_plus_today_cm": 0.007,
            "daily_gains_cm": 0.007,
            "height_cm": 165.007,
        }
        cards = {c["key"]: c["value_cm"] for c in teen_top_cards_from_metrics(metrics)}
        self.assertEqual(cards["posture_plus"], 0.007)
        self.assertEqual(cards["genetic_plus"], 0.0)
        self.assertNotEqual(cards["genetic_plus"], cards["posture_plus"])
