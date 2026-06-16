# Monday Spec — Frontend Implementation Guide

**Audience:** Mobile / Flutter team  
**Source spec:** [`HEIGHT_APP_MONDAY_SPEC.md`](../HEIGHT_APP_MONDAY_SPEC.md)  
**Backend status:** Live (Jun 2026) — paywall gates, live dashboard embed, height-loss 3 dp, adult nutrition tiers, exercise labels, lifestyle info popups, onboarding results payload.

This guide maps **every Monday spec section and bullet** to **what you build in the app**, **which API to call**, and **how to accept it**.

> **Friday work is still required.** This Monday list is **on top of** unfinished Friday items. See [`FRIDAY_WORK_ORDER_FRONTEND_GUIDE.md`](FRIDAY_WORK_ORDER_FRONTEND_GUIDE.md).

---

## Global

| Item | Value |
|------|-------|
| Base URL | `https://api.height.fit/api` |
| Auth | `Authorization: Bearer <access_token>` |
| Trailing slash | **No** — `/api/dashboard-new`, not `/api/dashboard-new/` |
| Primary dashboard | `GET /api/dashboard-new` |
| Subscription / paywall state | `GET /api/dashboard-new` → `dashboard.subscription`, `dashboard.trial_data`, `dashboard.meta` |

**Definition of done:** visible on a real device build **and** the spec acceptance test passes.

---

## Master map (spec → work)

| Spec | Title | Backend | Mobile | Primary APIs |
|------|--------|---------|--------|----------------|
| **A1** | Results screen after 8 questions | ✅ `onboarding_results` on questionnaire POST | **Build screen** + navigation | `POST /api/posture-questions` |
| **A2** | Paywall lock on all logging | ✅ `403` + `paywall_required` on all log POSTs | **Lock UI** + intercept 403 | All log endpoints below |
| **B1** | Instant stat updates per point | ✅ `dashboard_new` on log POSTs | **Bind embed**; no stale cache | Log POSTs + `GET /api/dashboard-new` |
| **B2** | No Genetic+/Posture+ flicker | ✅ Fixed teen embed math | **Use POST embed**; drop client double-count | `dashboard_new` in log responses |
| **B3** | Height Loss mirrors Posture+ (3 dp) | ✅ `height_loss_box` | **Display API values**; don't recompute | `GET /api/dashboard-new` |
| **C1** | Remove rest countdown | — | **Remove UI** | — |
| **C2** | Exercise card category pill | ✅ `category_label` on routine exercises | **Bind pill** | `GET /api/my-routine` |
| **C3** | Mountain Climber 40s timer | ✅ `unit: "secs"`, `qty_min: 40` | **Timer player** | `GET /api/my-routine` |
| **D1** | Rename Genetic Height → Genetic Average | — (label only) | **Rename string** | `genetic_average_cm` on dashboard |
| **D2** | Dashboard stat popups | — (static copy in spec) | **Tap → modal** | Dashboard display fields |
| **E1** | Lifestyle ℹ️ popups | ✅ `info_popup` on lifestyle modules | **ℹ️ icon + modal** | `GET /api/my-nutrition-plan?type=lifestyle` |
| **F1–F8** | Adult nutrition page rebuild | ✅ Tier1/Tier2 API | **Full screen rebuild** | `GET/POST /api/adult-nutrition` |

---

# SECTION A — Paywall + results screen

## A1 — Results / reveal screen after 8 posture questions

**Spec problem:** App jumps straight to paywall; user never sees their computed numbers.

**Flow (teen & adult):**

```
Question 8 submit → Results screen → Paywall → Dashboard (if declined)
```

**API — submit questionnaire**

```http
POST /api/posture-questions
Authorization: Bearer <token>
```

When all 8 answers are complete, response includes:

```json
{
  "success": true,
  "onboarding_results": {
    "total_posture_loss_cm": 3.3,
    "genetic_average_cm": 172.4,
    "genetic_mid_parental_cm": 175.2,
    "current_height_cm": 165.0,
    "true_optimized_cm": null,
    "true_optimized_locked": true
  },
  "user": {
    "section3_contract": { "...": "..." },
    "estimated_genetic_height_cm": 175.2
  }
}
```

| UI field | API key | Notes |
|----------|---------|--------|
| Total posture loss | `onboarding_results.total_posture_loss_cm` | From 8-question scoring |
| Genetic Average (teen) | `onboarding_results.genetic_average_cm` | Teen only |
| Genetic mid-parental | `onboarding_results.genetic_mid_parental_cm` | MPH-style estimate |
| Current height | `onboarding_results.current_height_cm` | |
| True Optimized teaser | `onboarding_results.true_optimized_cm` | `null` when locked |
| Lock state | `onboarding_results.true_optimized_locked` | Show 🔒 teaser when `true` |

`onboarding_results` is `null` until questionnaire is fully complete.

**Mobile tasks**

1. New **Results** route after Q8 — do **not** open paywall first.
2. Bind all fields from `onboarding_results` (fallback: `user.section3_contract` only if needed).
3. CTA: **Continue** → paywall screen.

**Acceptance:** Finish 8 questions → results screen with all numbers → then paywall.

---

## A2 — Enforce paywall (declined user cannot log)

**Spec rule:** Declined unpaid user **sees** dashboard but **every action button** opens paywall.

**Backend:** Strict gate — unpaid teen **and** adult get **403** on all logging POSTs (no trial logging exception on API).

**403 body (all log endpoints):**

```json
{
  "detail": "Logging is locked. Subscribe to unlock full access.",
  "paywall_required": true,
  "gate": "subscription_required"
}
```

**Gated endpoints (POST only — GET stays open):**

| Action | Endpoint |
|--------|----------|
| Log workout | `POST /api/workout-logs` |
| Log food / lifestyle (teen) | `POST /api/nutra-logs` |
| Adult nutrition | `POST /api/adult-nutrition` |
| Log habit | `POST /api/habit-logs` |
| Legacy spec logs | `POST /api/log-exercise`, `POST /api/log-food`, lifestyle spec views |

**Mobile tasks**

1. Read `subscription.is_paid` (or equivalent) from dashboard/subscription API.
2. If unpaid: wrap **every** log CTA (workout, habit, nutrition, lifestyle) → show paywall **before** API call.
3. **Also** handle `403` + `paywall_required: true` as safety net (never silently fail).
4. Do **not** block `GET` dashboard, routines, nutrition plan, or adult-nutrition **read**.

**Acceptance:** New unpaid teen declines paywall → dashboard visible → tap any log action → paywall (no successful log).

---

# SECTION B — Live height engine (display)

## B1 — Update on every single point instantly

**Spec rule:** 1 posture point → Posture+ +0.001, Height Loss −0.001, Height +0.001 immediately.

**Do not** wait for a second dashboard fetch if the log response already includes fresh data.

**After any successful log POST**, response includes:

```json
{
  "logged": true,
  "dashboard_new": {
    "message": "Dashboard retrieved successfully",
    "dashboard": {
      "variant": "teen",
      "live_metrics": { "...": "..." },
      "top_graph": {
        "cards": [
          { "key": "genetic_plus", "label": "Genetic +", "value_cm": 0.006 },
          { "key": "posture_plus", "label": "Posture+", "value_cm": 0.007 },
          { "key": "daily_gains", "label": "Daily Gains", "value_cm": 0.013 },
          { "key": "height", "label": "Height", "value_cm": 165.013 }
        ]
      },
      "height_loss_box": { "remaining_cm": 3.272, "...": "..." },
      "posture_optimization": { "...": "..." }
    }
  }
}
```

**Endpoints that return `dashboard_new`:**

- `POST /api/workout-logs`
- `POST /api/nutra-logs`
- `POST /api/habit-logs` (on create, not remove)

**Mobile tasks**

1. On log success → merge `dashboard_new.dashboard` into home/dashboard state **immediately**.
2. Update Height Loss, Posture+, Genetic+, Daily Gains, Height from embed (teen: `top_graph.cards` + `height_loss_box`).
3. Optional full refresh: `GET /api/dashboard-new` on pull-to-refresh only.

**Acceptance:** Log **one** workout point → dashboard numbers move before leaving the screen.

---

## B2 — Fix Genetic+/Posture+ spike-then-drop flicker

**Spec problem:** Both cards show ~+0.77 cm then snap down.

**Cause (fixed server-side):** Fast embed used wrong math. **Client fix:** use POST `dashboard_new` embed; **do not** add log points on top of dashboard totals client-side.

**Mobile tasks**

1. Remove any client logic that does `dashboard + today_log_delta` double counting.
2. Replace dashboard stats from embed **atomically** (single setState), not field-by-field with delays.
3. Genetic+ and Posture+ must come from **different** card keys (`genetic_plus` vs `posture_plus`).

**Acceptance:** Return from workout → correct values on first paint, no jump-then-drop.

---

## B3 — Height Loss accuracy (3 decimal places)

**Spec rule:** `height_loss = starting − cumulative_posture_plus` to **3 dp** (e.g. 3.3 − 0.028 = **3.272**).

**API — `GET /api/dashboard-new`**

```json
"height_loss_box": {
  "label": "Height Lost to Posture",
  "remaining_cm": 3.272,
  "initial_recoverable_cm": 3.3,
  "posture_plus_cumulative_cm": 0.028,
  "recovered": false,
  "sub_label": "Recoverable — shrinks as you train."
}
```

**Mobile tasks**

1. Display `remaining_cm` with **3 decimal places** (format `%.3f`).
2. **Do not** recompute height loss from segment bars client-side.
3. After logs, read `height_loss_box` from `dashboard_new` embed or full dashboard GET.

**Acceptance:** 3.3 start, +0.028 Posture+ cumulative → shows **3.272**.

---

# SECTION C — Exercise player & cards

## C1 — Remove rest countdown

**Spec:** Remove 5-4-3-2-1 between exercises.

| | |
|--|--|
| Backend | None |
| Mobile | Delete inter-exercise rest timer UI; on exercise complete → return to exercise list |

---

## C2 — Category label on exercise cards

**Spec:** Empty pill → show category (HGH, Spinal Decompression, etc.).

**API — `GET /api/my-routine`**

Each exercise in the routine payload includes:

```json
{
  "name": "Cobra Stretch",
  "category": "posture",
  "category_label": "Spinal Decompression",
  "primary_timer_dosage": "2 set(s) × 30 seconds (timer)"
}
```

| `category_label` examples |
|---------------------------|
| `HGH` |
| `Spinal Decompression` |
| `Postural Correction` |
| `Pelvic` |
| `Legs & Hamstrings` |

**Mobile:** Bind the pill to `category_label` (not raw `category` code).

---

## C3 — Mountain Climber = 40 second timer

**Spec:** Timed 40s, not reps.

**API:** Mountain Climbers prescription:

```json
{
  "name": "Mountain Climbers",
  "unit": "secs",
  "qty_min": 40,
  "sets": 1,
  "primary_timer_dosage": "1 set(s) × 40 seconds (timer)"
}
```

**Mobile tasks**

1. If `unit == "secs"` → **timer/hold player**, not rep counter.
2. Mountain Climber: **40 seconds** continuous motion.

---

# SECTION D — Dashboard tappable popups

## D1 — Rename

**Spec:** Teen top-left **"Genetic Height" → "Genetic Average"**.

| | |
|--|--|
| Backend | Field is `dashboard.genetic_average_cm` on teen dashboard |
| Mobile | Change label string only |

---

## D2 — Popup copy (static in app)

**Spec rule:** Every stat and segment tappable on **free and paid**. Tap → small modal; tap outside → dismiss. Title + one line body.

**Backend:** No popup API — copy is **hardcoded** from spec table below.

### Shared (teen + adult)

| Tap target | Popup body |
|------------|------------|
| Height Loss | How much height posture and compression have stolen — what's left to recover. This drops as you log workouts. |
| Spinal | Compression in your spinal discs that shortens your height — and one of the most recoverable areas. |
| Posture | Height lost to slouching and forward-head posture. Correcting it stands you taller. |
| Pelvic | Tilt in your hips that shortens your stance. Realigning it restores length. |
| Legs | Tightness and imbalance in your legs and hamstrings that pulls your posture down. |
| Height | Your current height right now, updated live as you log. |

### Teen-only top stats

| Tap target | Popup body |
|------------|------------|
| Genetic Average | Where you should be right now according to your genetics. |
| Genetic mid-parental | The height your genes point to, based on your mom's and dad's heights. |
| True Optimized 🔒 | Your personalized predicted height if you fully optimize posture, sleep, and nutrition. |
| Genetic + | Height gained today from your natural growth curve plus optimization. |
| Posture + | Height recovered today by correcting your posture and decompressing your spine. |
| Daily Gains | How much height you added today from all your activity combined. |

### Adult-only top stats

| Tap target | Popup body |
|------------|------------|
| Optimized Height 🔒 | Your full height once you've recovered everything posture and aging have cost you. This is the target. |
| Base Height | Your starting height when you began — before any recovery. |
| Total Recovered | The height you've gained back so far since you started. |
| Daily Gains | How much height you've recovered today. |

**Mobile:** Implement one reusable `StatInfoModal(title, body)`. Wire tap on segments that were previously non-interactive (four bars + Height Loss + Height).

---

# SECTION E — Lifestyle card info popups

## E1 — ℹ️ on each lifestyle card

**API — `GET /api/my-nutrition-plan?type=lifestyle`**

Each lifestyle module:

```json
{
  "id": 12,
  "name": "Sleep",
  "short_name": "Sleep",
  "tag_line": "...",
  "info_popup": {
    "title": "SLEEP 🌙",
    "body": "Your body releases its biggest surge of growth hormone during deep sleep..."
  },
  "habits": [ "..."]
}
```

`info_popup` is `null` when admin has not set copy (fallback: hide ℹ️).

**Mobile tasks**

1. Show ℹ️ when `info_popup != null`.
2. Tap → modal with `title` + `body`.
3. Copy is editable in Django admin (`info_popup_title`, `info_popup_body`) — prefer API over hardcoding.

**Default seeded copy** matches Monday spec §E1 (Sleep, Hydration, Sunlight, Morning/Evening Meditation).

---

# SECTION F — Adult nutrition page rebuild

**Applies to:** Adult accounts only (`is_adult: true`). Teens keep existing food-list nutrition.

**Replaces:** Old grey hydration layout, protein chips, 500 ml water icons.

---

## F1 — Points logic (display only — server authoritative)

```
nutrition_points = min(15, protein_points + fluid_points)
protein_points   = min(9, floor(grams / 10))
fluid_points     = min(6, tier1_total×2 + tier2_total×1)
```

**Never** compute totals client-side for dashboard/engine — display API numbers only.

---

## F2 — Multiple logging (tiles + badges)

| Gesture | API action |
|---------|------------|
| Tap tier tile (+1) | `add_tier1` / `add_tier2` |
| Long-press or − (−1) | `undo_tier1` / `undo_tier2` |
| Protein +10g | `add_protein` `{ "grams": 10 }` |
| Protein undo | `undo_protein` `{ "grams": 10 }` |
| Custom protein | `add_protein` or `set_protein` |
| Reset day | `reset` |

**Badge:** show `×{count}` from `tier1.items[].count` / `tier2.items[].count` when `count > 1`.

**Past fluid cap:** counts still increase; `fluids.points` stays at 6; `fluids.points_raw` can exceed 6.

---

## F3 — Screen layout (mobile)

Build to Gemini mock + spec structure:

1. Header + tabs (`Nutrition` | `Habits`)
2. Ring: `nutrition_points / nutrition_points_cap` (X / 15)
3. **PROTEIN** card — decorative food strip (local assets F4), gram buttons only
4. **SPINAL HYDRATION TIER 1** — 6 drink tiles
5. **Fluids X / 6 pts** meter (shared pool)
6. **SPINAL HYDRATION TIER 2** — 6 liquid tiles

---

## F4 — Asset mapping (local bundle)

Folder: **`images adult foods`** (transparent PNG ~512×512).

| UI | Asset filename |
|----|----------------|
| Protein strip: Chicken | `chicken2` |
| Salmon | `salmon2` |
| Beef | `beef2` |
| Milk (display only) | `milk2` |
| Beans | `beans2` |
| Eggs | `eggs2` |
| Tier1: Bone Broth | `broth2` |
| Watermelon | `watermelon2` |
| Coconut | `coconut2` |
| Cucumber | `cucumber2` |
| Celery | `celery2` |
| Beet | `beet2` |
| Tier2: Water | `water bottom` |
| Milk (loggable) | `milk bottom` |
| Tea | `tea bottom` |
| Coffee | `coffee bottom` |
| Juice | `juice bottom` |
| Carbonated | `carbonated bottom` |

Map tile `key` from API to asset name in client config.

---

## F5 — Exact copy strings

Use verbatim from [`HEIGHT_APP_MONDAY_SPEC.md`](../HEIGHT_APP_MONDAY_SPEC.md) §F5 (protein desc, tier headers, fluids label).

---

## F6 — API contract

### Load

```http
GET /api/adult-nutrition
```

```json
{
  "log_date": "2026-06-16",
  "protein": {
    "grams": 30,
    "points": 3,
    "grams_cap": 90,
    "points_cap": 9,
    "gram_buttons": [10, 20, 30]
  },
  "tier1": {
    "items": [
      { "key": "bone_broth", "label": "Bone Broth", "count": 1, "points_each": 2 }
    ],
    "log": { "bone_broth": 1 },
    "points_each": 2
  },
  "tier2": {
    "items": [
      { "key": "water", "label": "Water", "count": 2, "points_each": 1 }
    ],
    "log": { "water": 2 },
    "points_each": 1
  },
  "fluids": {
    "points": 4,
    "points_cap": 6,
    "points_raw": 4,
    "label": "Fluids 4 / 6 pts"
  },
  "nutrition_points": 7,
  "nutrition_points_cap": 15
}
```

### Tier keys (POST `item` field)

**Tier 1:** `bone_broth`, `watermelon`, `coconut`, `cucumber`, `celery`, `beet`

**Tier 2:** `water`, `milk`, `tea`, `coffee`, `juice`, `carbonated`

### POST examples

```http
POST /api/adult-nutrition
{ "action": "add_tier1", "item": "bone_broth" }

POST /api/adult-nutrition
{ "action": "undo_tier2", "item": "water" }

POST /api/adult-nutrition
{ "action": "add_protein", "grams": 30 }
```

**Legacy aliases still work:** `add_spine_drink` + `drink_type`, `add_water` / `undo_water`.

Response = full updated state (same shape as GET).

---

## F7 — Acceptance tests (QA on device)

| # | Log | Ring | Fluids pts |
|---|-----|------|------------|
| 1 | 30g + Bone Broth + Watermelon + Coconut | **9 / 15** | 6 |
| 2 | 90g + 3 tier1 drinks | **15 / 15** | 6 |
| 3 | 6× Water (tier2 only) | **6 / 15** | 6 |
| 4 | 2 tier1 + 2 tier2 waters | — | **6** |
| 5 | Bone Broth ×4 | — | pts **6**, badge **×4** |
| 6 | Protein via grams only | caps 9 pts / 90g | — |
| 7 | Any combo | never **> 15** | — |

---

## F8 — Product flags (do not “fix”)

- Protein card **milk image** = display only; Tier 2 **milk** = loggable fluid.
- Tier 2 coffee/carbonated = baseline hydration tracking, not spine claims.

---

# Definition of done — full QA checklist

| # | Spec | Test |
|---|------|------|
| 1 | A1 | 8 questions → **results** → paywall |
| 2 | A2 | Declined unpaid → dashboard visible, **every** log action → paywall |
| 3 | B1 | One point → instant Posture+/Genetic+, Height Loss, Height |
| 4 | B2 | No spike-then-drop on Genetic+/Posture+ |
| 5 | B3 | 3.3 − 0.028 → Height Loss **3.272** |
| 6 | C1 | No rest countdown |
| 7 | C2 | Every exercise card shows `category_label` |
| 8 | C3 | Mountain Climber 40s timer |
| 9 | D1+D2 | All stats/segments tappable; teen label "Genetic Average" |
| 10 | E1 | Lifestyle ℹ️ popups from `info_popup` |
| 11 | F | Adult nutrition page: protein + tier1 + tier2, ring X/15, F7 tests pass |

---

# Quick API reference

| Screen / action | Method | Path |
|-----------------|--------|------|
| Dashboard | GET | `/api/dashboard-new` |
| Questionnaire submit | POST | `/api/posture-questions` |
| My routine / exercises | GET | `/api/my-routine` |
| Log workout | POST | `/api/workout-logs` |
| Teen nutrition / lifestyle plan | GET | `/api/my-nutrition-plan` |
| Lifestyle only | GET | `/api/my-nutrition-plan?type=lifestyle` |
| Log teen food / lifestyle | POST | `/api/nutra-logs` |
| Adult nutrition | GET/POST | `/api/adult-nutrition` |
| Log habit | POST | `/api/habit-logs` |

---

# Related docs

| Topic | Doc |
|-------|-----|
| Friday items (still required) | [`FRIDAY_WORK_ORDER_FRONTEND_GUIDE.md`](FRIDAY_WORK_ORDER_FRONTEND_GUIDE.md) |
| Height predictor | [`HEIGHT_PREDICTOR_FRONTEND_GUIDE.md`](HEIGHT_PREDICTOR_FRONTEND_GUIDE.md) |
| Legacy nutrition notes | [`FRONTEND_NUTRITION_API_GUIDE.md`](FRONTEND_NUTRITION_API_GUIDE.md) — **§F supersedes adult hydration/chips section** |
