# Ultimate Height Predictor — Frontend Integration Guide

**Audience:** App / frontend developers
**Feature:** Ultimate Height Predictor (Model v2) — produces the **"True Optimized Height"** number.
**Status:** Backend live. Self-contained ("sealed box") — it does not change daily points, engines, the ledger, streaks, or any other dashboard number.

---

## 1. Overview

The predictor turns a short assessment (onboarding values + a few maturity/tape questions) into one number: **`true_optimized_cm`** — the user's true optimized adult height.

- The app submits the assessment once → the backend computes and **stores** the result.
- The stored value automatically appears as the **green "True Optimized Height" line** on `dashboard-new`.
- If the user later edits their profile (height / parent heights / DOB / sex), the backend **auto-recomputes** the stored value — the app does **not** need to re-submit for those edits.

---

## 2. Endpoints

Base prefix: **`/api/predictor/`**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/predictor/ultimate-height` | Run the assessment, store + return the result |
| `GET`  | `/api/predictor/ultimate-height` | Read the latest stored result + completion state |
| `GET`  | `/api/predictor/assessment-prefill` | Known profile data for Task 2A "Data Confirmed" intro screen |

**Auth:** required (same bearer token / auth header used for every other authenticated API).

---

## 3. `GET /api/predictor/ultimate-height`

Call this when opening the predictor screen to decide whether to show a stored result or prompt the user to take the assessment.

**Never run yet:**

```json
{ "completed": false, "result": null }
```

**Already completed:**

```json
{
  "completed": true,
  "result": {
    "id": 12,
    "completed": true,
    "band": "A",
    "model_version": "v2",
    "true_optimized_cm": 181.3,
    "genetic_potential_cm": 179.0,
    "posture_recovery_cm": 1.2,
    "breakdown": { "...": "see §6" },
    "computed_at": "2026-06-10T14:05:00Z"
  }
}
```

---

## 4. `POST /api/predictor/ultimate-height`

Submit the answers from the assessment screens. **All fields are optional** — the backend fills the 5 core fields from the user's profile if you omit them, and any client-supplied value wins over the profile default.

### Request body

```json
{
  "sex": "male",
  "age_years": 14.5,
  "current_height_cm": 165,
  "father_height_cm": 178,
  "mother_height_cm": 164,

  "voice_depth": 1,
  "facial_hair": 1,
  "body_hair": 1,
  "adams_apple": 0,

  "menarche_status": 0,
  "growth_spurt_status": 0,

  "recent_growth_cm": 4.0,
  "wingspan_cm": 167,
  "wrist_circumference_cm": 16,
  "weight_kg": 55,
  "shoe_size": 9
}
```

### Field reference

| Field | Type | Range | Notes |
|-------|------|-------|-------|
| `sex` | string | `"male"` / `"female"` | Core. Auto-filled from profile if omitted. |
| `age_years` | number | 0–120 | Core. Auto-filled from DOB/age. |
| `current_height_cm` | number | 50–260 | Core. Auto-filled from profile. |
| `father_height_cm` | number | 120–260 | Core. Auto-filled from profile. |
| `mother_height_cm` | number | 120–260 | Core. Auto-filled from profile. |
| `voice_depth` | int | 0–2 | **Male** maturity (Band A). |
| `facial_hair` | int | 0–2 | **Male** maturity (Band A). |
| `body_hair` | int | 0–2 | **Male** maturity (Band A). |
| `adams_apple` | int | 0–1 | **Male** maturity (Band A). |
| `menarche_status` | int | 0–3 | **Female** maturity (Band A). |
| `growth_spurt_status` | int | 0–2 | **Female** maturity (Band A). |
| `recent_growth_cm` | number (nullable) | 0–40 | Both sexes. Optional velocity refinement. |
| `wingspan_cm` | number (nullable) | 50–280 | Optional tape measure (no penalty if skipped). |
| `wrist_circumference_cm` | number (nullable) | 8–30 | Optional tape measure (no penalty if skipped). |
| `weight_kg` | number (nullable) | 20–250 | Optional, analytics only. |
| `shoe_size` | number (nullable) | 1–20 | Optional, analytics only. |

**Which maturity questions to show** (depends on age band → see §7):
- **Band A male:** `voice_depth`, `facial_hair`, `body_hair`, `adams_apple`.
- **Band A female:** `menarche_status`, `growth_spurt_status`.
- **Band B / 20+:** skip the maturity questionnaire (the model ignores it).

### Success response — `201 Created`

Same shape as the `GET` `result` object (see §3 and §6).

```json
{ "completed": true, "result": { "...": "..." } }
```

### Error — missing core values — `422 Unprocessable Entity`

Returned only if a core field is neither in the profile nor in the request:

```json
{
  "error": "Missing required values for the prediction.",
  "missing": ["father_height_cm"],
  "hint": "These are normally collected at onboarding; send them in the request if absent."
}
```

→ Re-prompt for the listed `missing` fields and resubmit.

### Error — validation — `400 Bad Request`

Standard DRF field validation (e.g. out-of-range value). Body is a per-field error map, e.g.:

```json
{ "age_years": ["Ensure this value is less than or equal to 120."] }
```

---

## 5. Result object fields

| Field | Meaning |
|-------|---------|
| `id` | Prediction row id. |
| `completed` | Always `true` for a stored result. |
| `band` | `"A"` (13.0–17.49), `"B"` (17.5–20), or `"20+"` (posture-only). See §7. |
| `model_version` | Algorithm version (`"v2"`). |
| `true_optimized_cm` | **The headline number** — true optimized adult height (cm, 1 decimal). |
| `genetic_potential_cm` | Genetic potential component (before posture). |
| `posture_recovery_cm` | Posture recovery added on top (read from the user's existing posture state). |
| `breakdown` | Full step-by-step trace (see §6) — for debugging/QA, not required for UI. |
| `computed_at` | ISO timestamp the result was computed. |

---

## 6. `breakdown` object (optional, for QA/debug)

Full transparency trace. Not needed to render the UI — display `true_optimized_cm`. Keys:

```json
{
  "model_version": "v2",
  "band": "A",
  "mph_cm": 177.5,
  "maturity": 0.62,
  "biological_age": 14.71,
  "fraction_attained": 0.9123,
  "height_est_maturity_cm": 180.9,
  "w_maturity": 0.65,
  "genetic_potential_cm": 179.0,
  "frame_adj_cm": 0.4,
  "wing_adj_cm": 0.6,
  "posture_recovery_cm": 1.2,
  "true_optimized_cm": 181.3,
  "floor_applied": false
}
```

(For Band `20+`, the maturity-related keys are `null` and `genetic_potential_cm == current_height_cm`, since genetic growth is finished and only posture is added.)

---

## 7. Age bands (which screens to show)

| Age | Band | Maturity questionnaire | Model |
|-----|------|------------------------|-------|
| 13.0 – 17.49 | `A` | **Yes** (sex-specific, see §4) | Full maturity + genetic + posture |
| 17.5 – 20.0 | `B` | **No** (skipped) | Lite — **`recent_growth_cm` required** on POST |
| 20.0+ | `20+` | **No** | Posture-only (`current + posture_recovery`) |

Band A: `recent_growth_cm` optional. Band B: omitting `recent_growth_cm` returns **422**.

---

## 8. Where the value appears in `dashboard-new`

After **`GET /api/predictor/ultimate-height` returns `completed: true`**, `GET /api/posture/dashboard-new` surfaces the value at:

- **`dashboard.predictor_completed`** — `true` only after a completed assessment
- **`target_metrics.true_optimized_green_cm`**
- **`top_graph.teen_lines_cm.true_optimized_green`** (the green chart line)
- **`top_graph.teen_lines_cm.true_optimized_locked`** (boolean lock flag)

**There is no legacy fallback.** Until the predictor assessment is completed, the green slot stays **`null`** and **`true_optimized_locked`** is **`true`** (for paid teens). The predictor API is the single source of truth.

### Gating (important)

The green True Optimized value is only populated when the user is **teen track AND paid AND `predictor_completed: true`**. Otherwise:

- `true_optimized_green` → `null`
- `true_optimized_locked` → `true`

UI rule: show the green line/number only when it is non-null; show the locked state when `true_optimized_locked` is `true`. (Adults use `target_height_cm` instead — they don't get this green line.)

---

## 8b. `GET /api/predictor/assessment-prefill`

Use for the animated "Data Confirmed" intro (Task 2A) before question screens:

```json
{
  "sex": "Male",
  "exact_age": { "years": 14, "months": 2, "days": 11 },
  "current_height_cm": 165.0,
  "father_height_cm": 180.0,
  "mother_height_cm": 166.0,
  "father_height_is_estimate": false,
  "mother_height_is_estimate": false,
  "posture_recovery_cm": 4.2,
  "predictor_completed": false,
  "band": null
}
```

When parent height was "I don't know" in onboarding, `*_is_estimate` is `true` and heights use regional averages.

---

## 8c. Other Friday dashboard keys (mobile handoff)

**Full Friday batch (Tasks 1–9):** see [`FRIDAY_WORK_ORDER_FRONTEND_GUIDE.md`](FRIDAY_WORK_ORDER_FRONTEND_GUIDE.md).

| Key | Purpose |
|-----|---------|
| `dashboard.routine_progress.completion_percent` | Home **"% optimized today"** — teen pool 68, adult pool 27 |
| `dashboard.routine_progress.completion_breakdown` | Per-section earned/max for the bar |
| `dashboard.height_loss_box.remaining_cm` | Height lost to posture (live, ≥2 decimals) |
| `dashboard.height_loss_box.recovered` | `true` when remaining ≤ 0 |
| `GET/POST /api/adult-nutrition` | Adult protein + fluids (max 15 pts) — replaces chip grid |
| `GET /api/habits` → `items[].instruction_steps` | Tap-down "How to" ordered steps (fallback: `how_to_detail`) |

**Mobile-only (no API change):** teen nutrition row sizing, habits full-screen layout, remove fake onboarding testimonials, growth-trend segment icons.

---

## 9. Recommended app flow

1. **On opening the predictor screen** → `GET /api/predictor/ultimate-height`.
   - `completed: true` → show the stored `result.true_optimized_cm` (don't force a re-run).
   - `completed: false` → show the assessment intro.
2. **User completes the questions** → `POST` the answers → show `result.true_optimized_cm` in the success/reveal UI.
3. **Dashboard** → the value flows into `dashboard-new` automatically (read the keys in §8).
4. **Profile edits** (current height / parent heights / DOB / sex) → **no re-POST needed**; the backend auto-recomputes the stored prediction, and `dashboard-new` reflects it on next load.
5. **User re-takes the maturity questions / re-measures tape** → `POST` again to refresh (maturity/tape answers are not stored on the profile, so a fresh POST is the only way to update them).

---

## 10. Examples

### cURL

```bash
# Read latest
curl -X GET "https://<host>/api/predictor/ultimate-height" \
  -H "Authorization: Bearer <TOKEN>"

# Submit assessment
curl -X POST "https://<host>/api/predictor/ultimate-height" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"sex":"male","age_years":14.5,"voice_depth":1,"facial_hair":1,"body_hair":1,"adams_apple":0,"recent_growth_cm":4.0}'
```

### JavaScript (fetch)

```javascript
const BASE = "https://<host>/api/predictor/ultimate-height";
const headers = {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json",
};

// 1) Read latest on screen open
async function getPrediction() {
  const res = await fetch(BASE, { headers });
  return res.json(); // { completed, result }
}

// 2) Submit the assessment
async function submitPrediction(answers) {
  const res = await fetch(BASE, {
    method: "POST",
    headers,
    body: JSON.stringify(answers),
  });
  if (res.status === 422) {
    const { missing } = await res.json();
    // re-prompt for `missing` fields, then resubmit
    return { needsMore: missing };
  }
  const data = await res.json(); // { completed: true, result: {...} }
  return { result: data.result };
}
```

---

## 11. FAQ

**Q: Does updating the profile change the predicted height?**
Yes — if a completed prediction already exists, editing height / parent heights / DOB / sex triggers an automatic recompute on the backend. No app action needed. (It never creates a prediction from scratch on a profile edit — the user must take the assessment at least once first.)

**Q: Do I need to send the core fields (sex, age, heights)?**
No, if they're already in the user's profile. Send them only to override, or when the `422` response says they're `missing`.

**Q: What if the user is an adult (20+)?**
The assessment still works; the result is `current_height_cm + posture_recovery_cm` (posture-only). Skip the maturity questions. Note the green dashboard line is teen-only.

**Q: Is the number client-computed?**
No. The number is **server-authoritative** — always read `true_optimized_cm` from the API response; never compute it on the client.
