from django.test import SimpleTestCase

from posture_questions.serializers_dashboard import DashboardNewResponseSerializer


class DashboardNewSerializerSmokeTests(SimpleTestCase):
    def test_minimal_payload_validates(self):
        payload = {
            "message": "Dashboard retrieved successfully",
            "dashboard": {
                "variant": "teen",
                "scan": {
                    "scan_completed": False,
                    "can_scan": True,
                    "scan_message": "x",
                    "rescan_timer_days": None,
                    "teen_scan_required": True,
                },
                "top_graph": {
                    "cards": [
                        {"key": "genetic_plus", "label": "Genetic +", "value_cm": 0.0},
                        {"key": "posture_plus", "label": "Posture+", "value_cm": 0.0},
                        {"key": "daily_gains", "label": "Daily Gains", "value_cm": 0.0},
                        {"key": "height", "label": "Height", "value_cm": 170.0},
                    ],
                    "teen_lines_cm": None,
                    "adult_target_height_cm": None,
                },
                "routine_progress": {
                    "cta": "Start",
                    "posture_exercises_fraction": "0/6",
                    "posture_exercises_done": 0,
                    "posture_exercises_total": 6,
                    "posture_exercises_percent": 0,
                    "nutrition_percent": 0,
                    "teen_nutrition_dots": 0,
                    "teen_lifestyle_dots": 0,
                    "streak_days": 0,
                    "daily_points": 0,
                    "rank": None,
                },
                "posture_optimization": {
                    "total_recoverable_loss_cm": 0.0,
                    "total_current_loss_cm": 0.0,
                    "bars_percent": {},
                    "raw_segments": {},
                },
            },
        }
        ser = DashboardNewResponseSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)
