SECTION6_DISPLAY_COPY = {
    "Hanging from Bar": "2 sets x 30-60 sec hold",
    "HGH Boost (Sprint & Burpees)": "3 rounds: 30 sec sprint + 10 burpees",
    "Jump Rope": "2-3 rounds x 1 minute",
    "Box Jumps / Jump Squats": "3 sets x 8-10 reps",
    "Cobra Stretch": "2 sets x 30 sec hold",
    "Hip Flexor Stretch": "2 sets x 30 sec per leg",
    "Glute Bridges": "3 sets x 15 reps",
    "Squats / Bodyweight Squats": "2-3 sets x 15-20 reps",
    "High Knees": "2 rounds x 30 sec",
    "Wall Angels": "2 sets x 12 reps",
    "Mountain Climbers": "3 rounds x 20 sec on / 10 sec rest",
    "Deep Squat Hold": "2 sets x 45 sec hold",
    "Cat-Cow Stretch": "2 sets x 10 reps",
    "Hamstring Stretch": "2 sets x 30 sec per leg",
    "Lunges": "2 sets x 12 reps per leg",
    "Plank": "2 sets x 45-60 sec hold",
    "Superman Hold": "2 sets x 20-30 sec hold",
    "Tadasana (Mountain Pose)": "2 sets x 30 sec",
    "Doorway Chest Stretch": "2 sets x 30 sec per side",
    "Child's Pose with Arm Walks": "2 sets x 30 sec hold + walk forward",
    "Spinal Twist Stretch": "2 sets x 30 sec per side",
    "Bird-Dog": "2 sets x 10 reps per side",
    "Butterfly Stretch": "2 sets x 30 sec",
    "Chin Tucks": "3 sets x 10 reps (5 sec hold each)",
    "Pelvic Tilts": "2 sets x 15 reps",
    "Foam Roller Thoracic Extension": "2 sets x 10 gentle reps",
    "Child's Pose": "2 sets x 30 sec hold",
    "Seated Forward Fold": "2 sets x 30 sec",
}


def section6_display_copy_for_exercise(name):
    return SECTION6_DISPLAY_COPY.get(str(name or "").strip(), None)
