from django.test import SimpleTestCase

from workouts.exercise_display_labels import exercise_category_label


class _Exercise:
    def __init__(self, name, category="posture", **pcts):
        self.name = name
        self.category = category
        self.spinal_pct = pcts.get("spinal_pct", 0)
        self.collapse_pct = pcts.get("collapse_pct", 0)
        self.pelvic_pct = pcts.get("pelvic_pct", 0)
        self.legs_pct = pcts.get("legs_pct", 0)


class ExerciseDisplayLabelTests(SimpleTestCase):
    def test_tadasana_and_chin_tucks_use_canonical_collapse_label(self):
        tadasana = _Exercise(
            "Tadasana (Mountain Pose)",
            spinal_pct=40,
            collapse_pct=40,
            pelvic_pct=15,
            legs_pct=5,
        )
        chin_tucks = _Exercise(
            "Chin Tucks",
            spinal_pct=65,
            collapse_pct=30,
            pelvic_pct=5,
            legs_pct=0,
        )

        self.assertEqual(exercise_category_label(tadasana), "Postural Collapse")
        self.assertEqual(exercise_category_label(chin_tucks), "Postural Collapse")

    def test_hgh_label_matches_wednesday_spec(self):
        self.assertEqual(exercise_category_label(_Exercise("Jump Rope", category="hgh")), "HGH Activation")

    def test_full_wednesday_exercise_list_uses_correct_pillar_labels(self):
        expected = {
            "Hanging from Bar": "Spinal Compression",
            "Cobra Stretch": "Spinal Compression",
            "Knees-to-Chest Rock": "Spinal Compression",
            "Cat-Cow Stretch": "Spinal Compression",
            "Child's Pose w/ Arm Walks": "Spinal Compression",
            "Spinal Twist Stretch": "Spinal Compression",
            "Child's Pose": "Spinal Compression",
            "Wall Angels": "Postural Collapse",
            "Standing Posture Reset": "Postural Collapse",
            "Tadasana (Mountain Pose)": "Postural Collapse",
            "Doorway Chest Stretch": "Postural Collapse",
            "Chin Tucks": "Postural Collapse",
            "Wall Chin Tuck": "Postural Collapse",
            "Superman Hold": "Postural Collapse",
            "Glute Bridges": "Pelvic Tilt & Back",
            "Hip Flexor Stretch": "Pelvic Tilt & Back",
            "Posterior Pelvic Tilt (Pelvic Tilts)": "Pelvic Tilt & Back",
            "Bird Dog": "Pelvic Tilt & Back",
            "Dead Bug": "Pelvic Tilt & Back",
            "McGill Curl-Up": "Pelvic Tilt & Back",
            "Pigeon Pose": "Pelvic Tilt & Back",
            "Side Plank": "Pelvic Tilt & Back",
            "Plank": "Pelvic Tilt & Back",
            "Hamstring Stretch": "Leg & Hamstring",
            "Hamstring Hinge": "Leg & Hamstring",
            "Butterfly Stretch": "Leg & Hamstring",
            "Wall Calf Stretch": "Leg & Hamstring",
            "Ankle Mobility": "Leg & Hamstring",
            "Box Jumps": "HGH Activation",
            "Burpees": "HGH Activation",
            "Deep Squat Hold": "HGH Activation",
            "High Knees": "HGH Activation",
            "Jump Rope": "HGH Activation",
            "Jump Squats": "HGH Activation",
            "Lunges": "HGH Activation",
            "Mountain Climbers": "HGH Activation",
            "Sprints": "HGH Activation",
            "Squats": "HGH Activation",
        }

        self.assertEqual(len(expected), 38)
        for name, label in expected.items():
            with self.subTest(name=name):
                self.assertEqual(exercise_category_label(_Exercise(name)), label)
