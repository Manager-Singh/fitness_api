"""
Canonical copy + instructions from EXERCISE_SPEC_SHEET.md (29 unique exercises).
Keys match exercise_assignment_data spec keys.
"""

EXERCISE_SPEC_SHEET_ROWS: dict[str, dict] = {
    "bird-dog": {
        "name": "Bird-Dog",
        "description": "Builds the core and spinal stability that keeps your back straight and balanced under daily load.",
        "dosage": "2 set(s) × 12 reps per side",
        "steps": [
            "Start on your hands and knees in a tabletop position.",
            "Extend your opposite arm and leg straight out, level with your body.",
            "Return with control and alternate for 12 reps each side.",
        ],
    },
    "butterfly stretch": {
        "name": "Butterfly Stretch",
        "description": "Opens tight hips and groin so your pelvis can sit in a taller, neutral position.",
        "dosage": "2 set(s) × 30 seconds (timer)",
        "steps": [
            "Sit tall with the soles of your feet pressed together.",
            "Hold your feet and gently press your knees toward the floor.",
            "Keep your back straight and hold for the full 30 seconds.",
        ],
    },
    "cat-cow stretch": {
        "name": "Cat-Cow Stretch",
        "description": "Mobilizes every segment of the spine, restoring the natural curves that keep you upright and tall.",
        "dosage": "2 set(s) × 12 reps",
        "steps": [
            "Start on your hands and knees in a tabletop position.",
            "Inhale and drop your belly, lifting your chest and tailbone (Cow).",
            "Exhale and round your spine, tucking your chin (Cat) — flow for 12 reps.",
        ],
    },
    "child's pose": {
        "name": "Child's Pose",
        "description": "Gently decompresses the lower spine and releases back tension built up from sitting.",
        "dosage": "2 set(s) × 40 seconds (timer)",
        "steps": [
            "Kneel and sit back on your heels.",
            "Fold forward and stretch both arms out along the floor.",
            "Relax your back and hold for the full 40 seconds.",
        ],
    },
    "child's pose with arm walks": {
        "name": "child's Pose with Arm Walks",
        "description": "Decompresses the lower back and stretches the lats, undoing the compression that rounds your spine.",
        "dosage": "2 set(s) × 40 seconds (timer)",
        "steps": [
            "Kneel and sit back on your heels with both arms stretched forward.",
            "Walk your hands forward to lengthen your spine, then walk them left and right.",
            "Breathe deeply and hold the stretch for the full 40 seconds.",
        ],
    },
    "chin tucks": {
        "name": "Chin Tucks",
        "description": "Pulls your head back over the shoulders, reversing the forward-head slump that shortens you.",
        "dosage": "2 set(s) × 15 reps",
        "steps": [
            "Sit or stand tall with your shoulders relaxed.",
            "Pull your chin straight back to make a 'double chin' and hold 2 seconds.",
            "Release and repeat for 15 consecutive reps.",
        ],
    },
    "cobra stretch": {
        "name": "Cobra Stretch",
        "description": "Extends your spine the opposite way it slumps all day, restoring its natural upright curve.",
        "dosage": "2 set(s) × 30 seconds (timer)",
        "steps": [
            "Lie face down with your hands flat under your shoulders.",
            "Press your upper body up while keeping your hips on the floor.",
            "Breathe deeply and hold for the full 30 seconds.",
        ],
    },
    "decompression hang": {
        "name": "Decompression Hang",
        "description": "Decompresses the spine and rehydrates the discs that compress all day — the fastest way to reclaim lost height.",
        "dosage": "2 set(s) × 45 seconds (timer)",
        "steps": [
            "Grip a pull-up bar shoulder-width apart with palms facing away.",
            "Hang fully relaxed and let your spine decompress under your bodyweight.",
            "Stay still — don't swing or kick.",
        ],
        "methods": [
            {
                "title": "Bar",
                "steps": [
                    "Grip a pull-up bar shoulder-width apart with palms facing away.",
                    "Hang fully relaxed and let your spine decompress under your bodyweight.",
                    "Stay still — don't swing or kick.",
                ],
            },
            {
                "title": "Door Frame",
                "steps": [
                    "Find the sturdiest door in your home, open it 90° and place a towel over the top edge to protect the door.",
                    "Place one hand near the top corner closest to the hinges (strongest side), other hand about 14 inches next to it along the top edge.",
                    "Bend your knees to take all weight off your feet — hang and feel your spine decompress.",
                ],
            },
        ],
        "safety_note": (
            "Use only a solid wood or solid-core door. Stop if the door creaks, "
            "shifts, or shows any sign of stress."
        ),
    },
    "deep squat hold": {
        "name": "Deep Squat Hold",
        "description": "Resets tight hips, ankles, and lower back into full range — the foundation for standing taller.",
        "dosage": "2 set(s) × 45 seconds (timer)",
        "steps": [
            "Squat down as low as you can with your feet flat on the floor.",
            "Place your elbows inside your knees and gently push them apart.",
            "Keep your chest tall and hold for the full 45 seconds.",
        ],
    },
    "doorway chest stretch": {
        "name": "Doorway Chest Stretch",
        "description": "Opens tight chest muscles that pull the shoulders forward, letting them settle back and tall.",
        "dosage": "2 set(s) × 30 seconds (timer)",
        "steps": [
            "Stand in a doorway and place your forearms on the frame, elbows at shoulder height.",
            "Step one foot forward and lean gently through the doorway.",
            "Feel the stretch across your chest and hold for the full 30 seconds.",
        ],
    },
    "foam roller thoracic extension": {
        "name": "Foam Roller Thoracic Extension",
        "description": "Reverses upper-back rounding (kyphosis), unlocking height trapped in a hunched thoracic spine.",
        "dosage": "2 set(s) × 12 reps",
        "steps": [
            "Lie with a foam roller across your upper back, knees bent.",
            "Support your head with your hands and gently arch back over the roller.",
            "Return to start and repeat for 12 slow, controlled reps.",
        ],
    },
    "glute bridges": {
        "name": "Glute Bridges",
        "description": "Activates the glutes to correct pelvic tilt and stabilize the spine into a taller alignment.",
        "dosage": "2 set(s) × 20 reps",
        "steps": [
            "Lie on your back with knees bent and feet flat.",
            "Squeeze your glutes and lift your hips until your body forms a straight line.",
            "Lower slowly with control and repeat for 20 consecutive reps.",
        ],
    },
    "hamstring stretch": {
        "name": "Hamstring Stretch",
        "description": "Loosens tight hamstrings that pull the pelvis out of line — freeing it to sit tall and neutral.",
        "dosage": "2 set(s) × 30 seconds per leg (timer)",
        "steps": [
            "Sit with one leg straight and the other bent inward.",
            "Reach gently toward the toes of your straight leg.",
            "Hold for the full 30 seconds, then switch legs.",
        ],
    },
    "hip flexor stretch": {
        "name": "Hip Flexor Stretch",
        "description": "Releases the tight hip flexors that pull your pelvis forward — a top hidden cause of lost height.",
        "dosage": "2 set(s) × 30 seconds per side (timer)",
        "steps": [
            "Kneel on one knee with the other foot forward, front knee at 90°.",
            "Push your hips gently forward until you feel a stretch at the front of the hip.",
            "Hold for the full 30 seconds, then switch sides.",
        ],
    },
    "pelvic tilts": {
        "name": "Pelvic Tilts",
        "description": "Strengthens the deep core and corrects pelvic tilt — the sway that hides height and pushes the belly forward.",
        "dosage": "2 set(s) × 20 reps",
        "steps": [
            "Lie on your back with knees bent and feet flat on the floor.",
            "Gently flatten your lower back into the floor by tilting your pelvis up.",
            "Release and repeat for 20 consecutive reps.",
        ],
    },
    "plank": {
        "name": "Plank",
        "description": "Builds the deep-core endurance that holds your spine tall and stable all day long.",
        "dosage": "2 set(s) × 45 seconds (timer)",
        "steps": [
            "Rest on your forearms with elbows directly under your shoulders.",
            "Extend your legs back so your body forms one straight line.",
            "Brace your core and hold for the full 45 seconds — don't let your hips sag.",
        ],
    },
    "seated forward fold": {
        "name": "Seated Forward Fold",
        "description": "Lengthens the whole back chain — hamstrings, lower back, spine — that compresses from sitting.",
        "dosage": "2 set(s) × 30 seconds (timer)",
        "steps": [
            "Sit with both legs extended straight in front of you.",
            "Hinge at your hips and reach toward your toes.",
            "Relax into the stretch and hold for the full 30 seconds.",
        ],
    },
    "spinal twist stretch": {
        "name": "Spinal Twist Stretch",
        "description": "Mobilizes and realigns the spine's rotation, releasing tension that pulls your posture out of line.",
        "dosage": "2 set(s) × 30 seconds per side (timer)",
        "steps": [
            "Lie on your back with both arms out wide in a 'T'.",
            "Drop one bent knee across your body toward the floor, keeping both shoulders flat.",
            "Hold for the full 30 seconds, then switch sides.",
        ],
    },
    "superman hold": {
        "name": "Superman Hold",
        "description": "Strengthens the entire back chain that fights slouching and keeps the spine extended and tall.",
        "dosage": "2 set(s) × 30 seconds (timer)",
        "steps": [
            "Lie on your stomach with both arms extended forward.",
            "Lift your chest, arms, and legs off the floor at the same time.",
            "Keep your gaze down and hold for the full 30 seconds.",
        ],
    },
    "tadasana (mountain pose)": {
        "name": "Tadasana (Mountain Pose)",
        "description": "Trains your body's tallest neutral posture so standing upright becomes your default.",
        "dosage": "2 set(s) × 30 seconds (timer)",
        "steps": [
            "Stand with your feet together, weight spread evenly.",
            "Engage your thighs, tuck your tailbone, and lift your chest.",
            "Reach the crown of your head upward and hold for the full 30 seconds.",
        ],
    },
    "wall angels": {
        "name": "Wall Angels",
        "description": "Opens the chest and pulls the shoulders back, directly reversing the rounded-shoulder slump.",
        "dosage": "2 set(s) × 15 reps",
        "steps": [
            "Stand with your back flat against a wall, feet 6 inches forward.",
            "Press your arms to the wall in a 'W' shape.",
            "Slide your arms up to a 'Y' and back down for 15 reps, keeping contact with the wall.",
        ],
    },
    "bodyweight squats": {
        "name": "Bodyweight Squats",
        "description": "High-rep leg loading triggers a strong growth-hormone response during your growth years.",
        "dosage": "2 set(s) × 25 reps",
        "steps": [
            "Stand with your feet shoulder-width apart, chest tall.",
            "Lower your hips back and down like sitting into a chair.",
            "Drive back up tall and repeat for 25 reps.",
        ],
    },
    "box jumps / jump squats": {
        "name": "Box Jumps / Jump Squats",
        "description": "Explosive impact stimulates growth hormone and loads the bones — powerful growth signals while young.",
        "dosage": "2 set(s) × 12 reps",
        "steps": [
            "Stand in front of a sturdy box or step.",
            "Bend slightly, then jump explosively onto it.",
            "Step down (don't jump down) and repeat for 12 reps.",
        ],
    },
    "hgh boost (sprint & burpees)": {
        "name": "HGH Boost (Sprint & Burpees)",
        "description": "Short max-effort bursts spike natural growth hormone — the key driver of growth while you're developing.",
        "dosage": "2 set(s) × 30 seconds (timer)",
        "steps": [
            "Sprint in place as hard as you can for 30 seconds.",
            "Immediately drop into 10 fast burpees.",
            "Rest briefly, then complete your second round.",
        ],
    },
    "high knees": {
        "name": "High Knees",
        "description": "A fast-impact burst that stimulates growth hormone and gets the whole body firing.",
        "dosage": "2 set(s) × 40 seconds (timer)",
        "steps": [
            "Stand tall and run in place, driving your knees toward your chest.",
            "Pump your arms and stay light on your feet.",
            "Keep the pace up for the full 40 seconds.",
        ],
    },
    "jump rope": {
        "name": "Jump Rope",
        "description": "Rhythmic impact triggers growth hormone and strengthens bone — prime signals while you're still growing.",
        "dosage": "2 set(s) × 60 seconds (timer)",
        "steps": [
            "Hold the rope handles at hip height (or mime it without a rope).",
            "Jump with both feet, keeping the jumps low and quick.",
            "Land softly on the balls of your feet for the full 60 seconds.",
        ],
    },
    "lunges": {
        "name": "Lunges",
        "description": "Builds leg strength and opens the hip flexors, supporting a taller, balanced stance.",
        "dosage": "2 set(s) × 12 reps per leg",
        "steps": [
            "Step one foot forward and lower your back knee toward the floor.",
            "Keep your front knee stacked directly over your ankle.",
            "Push back to standing and alternate for 12 reps each leg.",
        ],
    },
    "mountain climbers": {
        "name": "Mountain Climbers",
        "description": "A high-intensity burst that spikes growth hormone while training core and shoulder stability.",
        "dosage": "2 set(s) × 40 seconds (timer)",
        "steps": [
            "Start in a high plank with your hands under your shoulders.",
            "Drive one knee toward your chest, then quickly switch legs.",
            "Keep your hips low and the pace fast for the full 40 seconds.",
        ],
    },
    "squats": {
        "name": "Squats",
        "description": "Loads the legs and spine to trigger growth hormone and build the strength that holds you upright.",
        "dosage": "2 set(s) × 20 reps",
        "steps": [
            "Stand with your feet shoulder-width apart.",
            "Lower your hips back and down like sitting into a chair.",
            "Drive back up tall and repeat for 20 reps.",
        ],
    },
}
