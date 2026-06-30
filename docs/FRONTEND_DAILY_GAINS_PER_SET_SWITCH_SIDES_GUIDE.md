# Frontend Guide: Daily Gains, Per-Set Crediting, And Switch-Side Timer

**Audience:** Mobile / Flutter team  
**Date:** Jun 30, 2026  
**Backend status:** Implemented and covered by focused backend tests  
**Primary APIs:** `GET /api/my-routine`, `POST /api/workout-logs`, `GET /api/dashboard-new`

This guide covers the frontend work needed for the backend changes around strict Daily Gains, per-set crediting, partial workout progress, and unilateral "switch sides" exercises.

---

## 1. What Changed

Daily Gains is now ledger-backed. The app should display the value from the dashboard API and must not recompute it from points.

Workout credit is now per completed set. A user who completes set 1 of 2 gets immediate partial points and height credit. Completing set 2 later adds the remaining credit. Repeating the same set does not add credit again.

Some exercises are unilateral. For these, one set means both sides are completed. The app must run side 1, show a switch prompt, run side 2, then log that set once.

Daily workout dots are now separate from gains:

- Points and height move after each completed set.
- The exercise dot fills only when all sets are completed.
- Partial progress should show as partial, such as `1/2 sets` or a half-filled ring.

---

## 2. Routine API Fields

Use `GET /api/my-routine`.

Each exercise can now include these fields:

```json
{
  "id": 123,
  "exercise_id": 45,
  "name": "Hamstring Stretch",
  "points": 6,
  "sets": 2,
  "unit": "secs",
  "qty_min": 30,
  "qty_max": null,
  "completed": false,
  "completed_sets": 1,
  "total_sets": 2,
  "progress_fraction": 0.5,
  "partially_completed": true,
  "is_unilateral": true,
  "unilateral_label": "leg",
  "switch_prompt_text": "SWITCH LEGS",
  "switch_prompt_subtext": "Get into position on your other leg",
  "switch_countdown_seconds": 3,
  "credit_unit": "set"
}
```

Important frontend rules:

- Use `completed` only for full exercise completion.
- Use `completed_sets`, `total_sets`, and `partially_completed` for partial UI.
- Use `is_unilateral` to decide whether to run side 1 plus side 2 before logging a set.
- Use `switch_prompt_text` and `switch_prompt_subtext` from the API instead of hardcoding labels.
- `credit_unit` is currently `set`; log only when a full set is complete.

---

## 3. Logging A Completed Set

Use `POST /api/workout-logs`.

For the new per-set flow, send `set_index` when one set is genuinely complete.

```http
POST /api/workout-logs
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "user_routine": 10,
  "exercise_id": 45,
  "set_index": 1,
  "duration_s": 30,
  "client_timestamp": "2026-06-30T05:30:00.000Z"
}
```

For rep exercises:

```json
{
  "user_routine": 10,
  "exercise_id": 46,
  "set_index": 1,
  "reps_done": 12,
  "client_timestamp": "2026-06-30T05:30:00.000Z"
}
```

Expected response includes progress and an updated dashboard embed:

```json
{
  "logged": true,
  "duplicate": false,
  "counts_toward_engine": true,
  "credited_set_index": 1,
  "points_credited": 3.5,
  "completed_sets": 1,
  "total_sets": 2,
  "progress_fraction": 0.5,
  "partially_completed": true,
  "exercise_completed": false,
  "dashboard_new": {}
}
```

Duplicate set response:

```json
{
  "logged": true,
  "duplicate": true,
  "counts_toward_engine": false,
  "points_credited": 0.0,
  "message": "This workout set is already completed for today."
}
```

Frontend behavior:

- Treat duplicate response as success for UI state, but do not animate new points.
- Bind `dashboard_new` after every successful non-duplicate log to avoid stale dashboard values.
- Do not send a log for abandoned/incomplete sets.
- If the user exits 20s into a 30s hold, do not call `POST /api/workout-logs`.

---

## 4. Unilateral Switch-Side Flow

When `is_unilateral` is `true`, each set has two side phases.

Timed example: Hamstring Stretch, `2 sets x 30 sec per leg`

1. Show `Set 1 of 2 - Left leg`.
2. Run 30s timer.
3. At zero, show `switch_prompt_text`, usually `SWITCH LEGS`.
4. Show `switch_prompt_subtext`.
5. Run a 3 second countdown from `switch_countdown_seconds`.
6. Auto-start side 2. Allow optional "Start now" to skip countdown.
7. Run 30s timer for right leg.
8. Only now call `POST /api/workout-logs` with `set_index: 1`.

Rep example: Bird-Dog, `2 sets x 12 reps per side`

1. Count 12 reps side 1.
2. Show switch prompt and countdown.
3. Count 12 reps side 2.
4. Log the set once.

Do not credit per side. Credit only after both sides are completed.

---

## 5. Exercises With Switch Prompt

Backend marks the definitive current catalog exercises:

- Hamstring Stretch: `is_unilateral=true`, `unilateral_label=leg`
- Hip Flexor Stretch: `is_unilateral=true`, `unilateral_label=side`
- Spinal Twist Stretch: `is_unilateral=true`, `unilateral_label=side`
- Bird-Dog: `is_unilateral=true`, `unilateral_label=side`
- Lunges: `is_unilateral=true`, `unilateral_label=leg`

Mountain Climbers / Mountain Climber should remain a single continuous timer. Do not show a switch prompt when `is_unilateral=false`.

Future filmed exercises may also return `is_unilateral=true`. The frontend should trust the API field rather than maintaining a separate hardcoded list.

---

## 6. Partial Progress UI

Use these states:

```text
0/2 sets: empty dot, no completed state
1/2 sets: partial dot or "1/2 sets"
2/2 sets: filled dot, completed=true
```

Recommended exercise-card bindings:

- Main completion: `completed`
- Partial visual: `partially_completed`
- Text: `"${completed_sets}/${total_sets} sets"`
- Progress ring: `progress_fraction`

The dashboard "X of 10 done" should follow the backend dashboard value. Do not increment it locally after only one set unless the backend returns the exercise as fully complete.

---

## 7. Daily Gains And Dashboard

Daily Gains now follows strict backend crediting:

- Nutrition and habits can show full points for morale.
- Height gain only includes lifestyle shares for primary-trained pillars.
- A primary pillar counts as trained after at least one credited set.
- Daily Gains and Total Recovered should agree for a single-day fresh user because both are ledger-backed.

Frontend rules:

- Display `Daily_Gains_cm`, `daily_gains_cm`, or the relevant dashboard `daily_gains.value_cm` from the API.
- Do not compute Daily Gains as `points * 0.001`.
- Do not add nutrition/habit points to height locally.
- Refresh dashboard from `dashboard_new` in log responses or refetch `GET /api/dashboard-new` on focus/navigation.

---

## 8. Acceptance Checklist

- Completing 1 set of a 2-set exercise shows partial progress and immediate points/height movement.
- Completing set 2 fills the exercise dot and totals equal the original full-exercise credit.
- Repeating the same set does not animate or add points again.
- Exiting mid-set does not call the log endpoint.
- Hamstring Stretch runs left 30s, switch legs, right 30s, then logs one set.
- Bird-Dog and Lunges run reps on both sides before logging the set.
- Mountain Climbers remains a single continuous 40s timer with no switch prompt.
- Dashboard Daily Gains is rendered from backend response only.
- Navigating back to dashboard after logging a set shows updated Daily Points, Daily Gains, Total Recovered, and bars.

---

## 9. Backward Compatibility Note

The backend still accepts older full-exercise logging payloads and converts them into all expected set completions once. New app builds should use `set_index` so partial progress works correctly.
