# Frontend Posture Targeting Implementation Guide

**Audience:** Mobile / Flutter team  
**Date:** Jun 22, 2026  
**Backend status:** Implemented and covered by focused backend tests  
**Source spec:** [`MONDAY_WORK_ORDER_MASTER 22-06-26.md`](../MONDAY_WORK_ORDER_MASTER%2022-06-26.md)

This guide explains how the mobile app should integrate the new posture questionnaire, targeted workout assignment, and dashboard behavior.

**Base URL:** `https://api.height.fit/api`  
**Auth:** `Authorization: Bearer <access_token>` on every request  
**Trailing slash:** URLs have no trailing slash, e.g. `/api/update-posture-questions`

---

## 1. What Changed

The posture system is now deficiency-targeted:

- The posture quiz is 8 questions, each answered A-F.
- Answers feed 4 posture pillars: `spinal`, `collapse`, `pelvic`, `legs`.
- Taller users can recover more absolute centimeters for the same posture severity.
- Max reference recovery at 175cm is 8.0cm: collapse 3.0, spinal 2.5, pelvic 1.5, legs 1.0.
- Core 6 is fixed and covers all 4 pillars every day, including legs.
- Recommended and Beast slots are display labels only; the backend fills them from the user's worst remaining pillars.
- A workout only grows the pillar it targets. Example: a spinal-primary exercise credits spinal plus its secondary pillar, not all 4 pillars.
- Nutrition and habits show full dashboard points, but actual posture recovery shares only count for pillars trained that day.
- Teens also get Genetic+ from biological growth and Engine 2 inputs; teen nutrition/lifestyle/HGH do not recover posture pillars.

Do not recompute posture math on the client. Submit the answers and render the backend response.

---

## 2. Main APIs

| Screen / action | API | Notes |
|---|---|---|
| Submit posture quiz | `POST /api/update-posture-questions` | Sends all 8 answers and options |
| Dashboard | `GET /api/dashboard-new` | Read posture bars, height-loss box, daily gains |
| Personalized routine | `GET /api/my-routine` | Returns Core, Recommended, Beast exercises |
| Log workout | `POST /api/workout-logs` | Rebuilds ledger and returns dashboard embed |
| Food/lifestyle logs | `POST /api/nutra-logs` | Visible points remain full |
| Habits | `GET /api/habits`, habit logging endpoint | Habit points are visible; posture recovery is gated by trained pillars |

---

## 3. Posture Quiz UI

### 3.1 Question Flow

Show 8 required questions in this order:

| Question | UI type | Backend field group | Pillar |
|---|---|---|---|
| Q1 Head / neck | Image grid A-F | `forward_head_posture_*` | Collapse |
| Q2 Upper-back rounding | Image grid A-F | `gap_between_your_lower_back_*` | Collapse |
| Q3 Shoulder rotation | Image grid A-F | `tightness_or_discomfort_*` | Collapse |
| Q4 Upper back vs wall | Image grid A-F | `slouch_when_standing_or_sitting_*` | Collapse |
| Q5 Pelvic tilt | Image grid A-F | `feel_noticeably_shorter_end_of_day_compare_to_morning_*` | Pelvic |
| Q6 Knee bend | Image grid A-F | `perfectly_aligned_and_decompressed_*` | Legs |
| Q7 Spinal compression | Text cards 1-6 | `flexible_in_your_hamstrings_and_hips_*` | Spinal |
| Q8 Front-view symmetry | Text cards 1-6 | `active_your_core_during_daily_task_*` | Spinal/Pelvic |

Keep the existing backend field names even though the labels are changing. They are the current API contract.

### 3.2 Answer Mapping

Every question must send one answer letter:

```text
A = 0.0
B = 0.2
C = 0.4
D = 0.6
E = 0.8
F = 1.0
```

For Q7 and Q8, the UI displays numbered cards 1-6 but still submits letters:

```text
1 -> A
2 -> B
3 -> C
4 -> D
5 -> E
6 -> F
```

### 3.3 Image Questions Q1-Q6

Render a 6-panel tappable grid:

- 2 columns x 3 rows on mobile.
- Panels labeled A-F, best to worst.
- Selected state: teal glowing border.
- Use image filenames `q1` through `q6`.
- Do not rely on labels baked into image files. The app controls the A-F mapping.

### 3.4 Text Questions Q7-Q8

Render 6 full-width selectable cards:

- Left badge: number 1-6.
- Right side: option text.
- Selected background: dark teal.
- Selected border: teal glow.
- Minimum row height: 56px.
- Show progress: `Q n of 8`.

Style tokens:

```text
Background: #0A0A0A
Card unselected: #141416 fill, #262629 border, #E8E8EA text
Card selected: #0E2E2C fill, #00BFB3 border
Badge unselected: #1C1C1F circle, #00BFB3 number
Badge selected: #00BFB3 circle, #04342C number
Subtext: #9AA
```

---

## 4. Submit Payload

Use the same endpoint as before:

```http
POST /api/update-posture-questions
Authorization: Bearer <token>
Content-Type: application/json
```

Example:

```json
{
  "forward_head_posture_question": "When you stand relaxed, how far forward does your head sit?",
  "forward_head_posture_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "forward_head_posture_answer": "C",

  "gap_between_your_lower_back_question": "Looking from the side, how rounded is your upper back?",
  "gap_between_your_lower_back_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "gap_between_your_lower_back_answer": "D",

  "tightness_or_discomfort_question": "Let your arms hang completely dead at your sides. Which way do your thumbs/palms naturally point?",
  "tightness_or_discomfort_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "tightness_or_discomfort_answer": "B",

  "slouch_when_standing_or_sitting_question": "Stand with your back to a wall, heels and hips touching it. How does your upper back and head meet the wall?",
  "slouch_when_standing_or_sitting_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "slouch_when_standing_or_sitting_answer": "D",

  "feel_noticeably_shorter_end_of_day_compare_to_morning_question": "From the side, how is your pelvis (hips) tilted?",
  "feel_noticeably_shorter_end_of_day_compare_to_morning_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "feel_noticeably_shorter_end_of_day_compare_to_morning_answer": "C",

  "perfectly_aligned_and_decompressed_question": "Standing relaxed, how bent are your knees?",
  "perfectly_aligned_and_decompressed_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "perfectly_aligned_and_decompressed_answer": "B",

  "flexible_in_your_hamstrings_and_hips_question": "Be honest about your spine right now. Through a normal day, what do you actually notice?",
  "flexible_in_your_hamstrings_and_hips_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "flexible_in_your_hamstrings_and_hips_answer": "C",

  "active_your_core_during_daily_task_question": "Stand in front of a mirror, feet together, and relax. Looking at your shoulders and hips, how level are they?",
  "active_your_core_during_daily_task_options": "[\"A\",\"B\",\"C\",\"D\",\"E\",\"F\"]",
  "active_your_core_during_daily_task_answer": "B"
}
```

All 8 answers are required before the backend marks `questionnaire_completed: true`.

---

## 5. Submit Response Fields To Use

After submit, read:

```json
{
  "user": {
    "questionnaire_completed": true,
    "section3_contract": {
      "mode": "posture_targeting_v1",
      "answers": {"q1": "C", "q2": "D"},
      "total_recoverable_loss_cm": 3.2,
      "target_height_cm": 178.2,
      "ranked_segments": ["collapse", "spinal", "pelvic", "legs"],
      "optimization_breakdown": {
        "spinal_compression": {
          "current_loss_cm": 0.7,
          "max_loss_cm": 2.5,
          "percent_optimized": 72
        }
      },
      "scoring_meta": {
        "height_factor": 1.0,
        "reference_height_cm": 175.0
      }
    },
    "onboarding_results": {
      "total_posture_loss_cm": 3.2,
      "current_height_cm": 175.0
    }
  }
}
```

Important rules:

- `mode` should be `posture_targeting_v1`.
- Use `total_recoverable_loss_cm` for posture recovery potential.
- Use `optimization_breakdown` for the 4 posture bars.
- Use `ranked_segments` for summary messaging if needed.
- Do not show raw `scoring_meta` to users unless building a debug screen.

---

## 6. Dashboard UI Rules

Read dashboard from:

```http
GET /api/dashboard-new
```

The backend now updates posture bars from actual targeted pillar recovery.

Frontend rules:

- Do not split height gain equally across all pillars on the client.
- Do not assume nutrition/habits always create full posture recovery.
- If a user only logs a spinal workout, only spinal primary plus secondary credit should move.
- Full dashboard points still display normally for workouts, nutrition, lifestyle, and habits.
- Height-loss/posture bars should always come from the backend response.

Use existing dashboard fields for:

- Current height / cumulative gain.
- `height_loss_box`.
- Posture bars / optimization breakdown.
- Teen Genetic+ line and adult Posture+ line.

---

## 7. Routine Screen Rules

Load routine:

```http
GET /api/my-routine
```

Expected structure remains Core, Recommended, Beast, but semantics changed:

- Core 6 is fixed and covers all 4 posture pillars.
- Adults: Core 6 + 2 Recommended + 2 Beast = 10 exercises.
- Teens: 1 HGH core slot + 4 posture pillar core slots + 1 worst-pillar extra + 2 Recommended + 2 Beast = 10 exercises.
- Recommended and Beast are labels. Do not hardcode a Beast exercise list.
- Backend chooses extra slots based on remaining deficiencies.
- Exercise order and assignment should be rendered as returned.

Frontend should not locally reshuffle rec/beast exercises.

---

## 8. Workout Logging

Log a completed exercise:

```http
POST /api/workout-logs
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "user_routine": 123,
  "exercise_id": 45,
  "points": 7,
  "sets_done": 2,
  "reps_done": 12,
  "duration_s": 60
}
```

After a successful log:

- Use returned `dashboard_new` if present to refresh the UI immediately.
- Otherwise call `GET /api/dashboard-new`.
- Do not animate all 4 posture bars for one workout.
- Let the backend response determine which bars moved.

HGH rule for teens:

- HGH exercises feed Genetic+ / Engine 2.
- HGH exercises do not move posture bars.
- There is no HGH daily Engine 2 cap in the new spec.

---

## 9. Nutrition, Habits, And Recovery

Visible points and actual posture recovery are intentionally decoupled.

Frontend display:

- Show full nutrition points when logged.
- Show full habit points when logged.
- Keep morale/points UI unchanged.

Actual height recovery:

- If no workout was completed that day, food/habits create no posture recovery.
- If only one pillar was trained, only that pillar collects its strict share.
- If full Core 6 is completed, all 4 pillars are trained and all shares are collected.
- Teen nutrition/lifestyle feeds Genetic+ Engine 2, not posture bars.
- Teen posture habits feed posture pillars using the strict trained-pillar rule.

Do not display forfeiture as a penalty unless product explicitly asks. The normal user-facing message should be positive: "Complete your Core 6 to unlock full recovery credit across all posture areas."

---

## 10. Teen Vs Adult Display

Adults:

- Daily gains = Posture+ only.
- Posture+ is posture exercise recovery plus eligible nutrition/habit shares.
- No Genetic+ / Engine 2 display for adults.

Teens:

- Daily gains = Genetic+ + Posture+.
- Genetic+ includes biological daily gain plus Engine 2 boost.
- Engine 2 boost comes from HGH, nutrition, sleep, sunlight, meditation, hydration.
- Teen nutrition/lifestyle does not move posture bars.
- Female teen biological gain stops at exact age 17.0.

---

## 11. Acceptance Tests For Mobile

Quiz:

- Q1-Q6 render A-F image grid with one required selection.
- Q7-Q8 render numbered 1-6 cards and submit A-F letters.
- Progress shows `Q n of 8`.
- Submit all 8 answers and receive `section3_contract.mode = posture_targeting_v1`.
- All-F at 175cm produces 8cm total recovery in backend response.

Routine:

- Adult routine shows 10 exercises.
- Teen routine shows 10 exercises.
- Core includes at least one spinal, collapse, pelvic, and legs posture exercise.
- Teen core includes one HGH exercise.
- Recommended/Beast render exactly as returned by backend.

Dashboard / logging:

- Log a spinal-primary exercise and confirm only relevant posture bars move after refresh.
- Log nutrition/habits with no workout and confirm visible points update but height recovery does not move.
- Complete Core 6 and confirm all posture areas are eligible for daily recovery.
- Log teen HGH and confirm Genetic+ can move but posture bars do not.

---

## 12. Do Not Do This On Frontend

- Do not calculate centimeters from A-F answers in Flutter.
- Do not split workout gain across all 4 pillars.
- Do not hardcode Beast/Recommended exercise pools.
- Do not cap teen HGH points on the client.
- Do not assume teen nutrition/lifestyle moves posture bars.
- Do not rely on image text baked into `q1`-`q8` assets.

