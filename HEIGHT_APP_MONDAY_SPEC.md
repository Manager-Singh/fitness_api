# THE HEIGHT APP — MONDAY SPEC SHEET

> **READ FIRST:** This is a **new** list, **separate from the items you did not finish on Friday** — those Friday items still need to be completed too. Everything below is on top of that.

**Screenshots referenced (already sent):** the **Posture Exercise** screen, the **Teen Dashboard**, the **Adult Dashboard**, the **Lifestyle** cards, and the **new Nutrition page** (two-tier hydration) with its image asset sheet.

**Reminder:** 1 point = 0.001 cm. Don't change that or the engine routing — these are sync, gating, display, copy, and the nutrition-page build.

**Sections:** A Paywall · B Live engine · C Exercise player · D Dashboard popups · E Lifestyle popups · **F Nutrition page rebuild (NEW)**

> **Implementation guide (API + mobile map):** [`docs/MONDAY_SPEC_FRONTEND_GUIDE.md`](docs/MONDAY_SPEC_FRONTEND_GUIDE.md) — maps each section/point (A1, A2, B1…F7) to backend endpoints and Flutter tasks.

### Implementation status (by spec point)

| Point | Backend | Mobile | Primary API / notes |
|-------|---------|--------|---------------------|
| **A1** | ✅ Done | 🔲 Build results screen | `POST /api/posture-questions` → `onboarding_results` |
| **A2** | ✅ Done | 🔲 Lock all log CTAs + handle 403 | All log POSTs → `paywall_required: true` |
| **B1** | ✅ Done | 🔲 Apply `dashboard_new` on log success | `POST` workout/nutra/habit logs |
| **B2** | ✅ Done | 🔲 No client double-count | Same embed as B1 |
| **B3** | ✅ Done | 🔲 Display `height_loss_box.remaining_cm` at 3 dp | `GET /api/dashboard-new` |
| **C1** | — | 🔲 Remove rest countdown UI | — |
| **C2** | ✅ Done | 🔲 Show `category_label` pill | `GET /api/my-routine` |
| **C3** | ✅ Done | 🔲 40s timer when `unit: "secs"` | `GET /api/my-routine` |
| **D1** | — | 🔲 Rename label string | Teen dashboard |
| **D2** | — | 🔲 Tap → modal (copy in §D2 below) | Static strings in app |
| **E1** | ✅ Done | 🔲 ℹ️ + modal from API | `GET /api/my-nutrition-plan?type=lifestyle` → `info_popup` |
| **F1** | ✅ Done | 🔲 Display server totals only | `GET/POST /api/adult-nutrition` |
| **F2** | ✅ Done | 🔲 Tap/long-press tiles + badges | `add_tier1`, `undo_tier1`, `add_tier2`, `undo_tier2` |
| **F3** | — | 🔲 Full screen layout rebuild | See §F3 + frontend guide |
| **F4** | — | 🔲 Bundle assets per table | Local `images adult foods` |
| **F5** | — | 🔲 Exact copy strings | See §F5 below |
| **F6** | ✅ Done | 🔲 Wire tier keys to POST actions | `tier1_log` / `tier2_log` on server |
| **F7** | ✅ Done | 🔲 QA all 7 cases on device | Acceptance table §F7 |
| **F8** | — | 🔲 Product rules (milk, coffee) | No API change |

---

# SECTION A — Paywall gating + the missing results screen

### A1 — Add the results/reveal screen after the 8 posture questions (MISSING)
**→ Backend:** ✅ `onboarding_results` on questionnaire POST · **Mobile:** 🔲 build screen · **Guide:** [§A1](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#section-a--paywall--results-screen)
**Problem:** After a teen finishes the 8 posture questions, the app jumps straight toward the paywall. The **results screen is missing** — the one that shows all their calculated data on one screen *before* the paywall.
**Fix:** After the last posture question, show a **results screen** that displays their computed numbers in one place:
- **Total posture loss** (the cm they've lost, from the 8 answers)
- **Genetic Average** (where they should be now)
- **Genetic mid-parental** (parent-based target)
- **Current height**
- (and their optimized potential / "True Optimized" teaser)

This is the payoff that motivates the purchase — it must appear **before** the paywall. (Adults get the analogous screen with their relevant numbers.)
**Done when:** Finishing the 8 questions opens a data/results screen, then the paywall.

### A2 — Enforce the paywall (currently everything is free if you decline) 🔴
**→ Backend:** ✅ 403 on all log POSTs when unpaid · **Mobile:** 🔲 lock every action button · **Guide:** [§A2](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#a2--enforce-paywall-declined-user-cannot-log)
**Problem:** Registered as a new 13-year-old. Declining the paywall **both times** drops you on the dashboard — and you can do **exercises, habits, nutrition, everything** as if it's all free. That's a giant hole.
**Fix:** We are doing the paywall now. After declining, the user **can still see the dashboard**, but **every action button is locked** and tapping any of them **opens the paywall** instead of performing the action. Locked surfaces: starting/logging any workout, logging any habit, logging any nutrition, logging any lifestyle item — all of it routes back to the paywall.
**Done when:** A declined free user sees the dashboard but cannot log a single thing — every action button leads to the paywall.

---

# SECTION B — Real-time height engine (numbers must be live, accurate, stable)

### B1 — Update on EVERY single point, instantly (too much delay now) 🔴
**→ Backend:** ✅ `dashboard_new` embed on log POSTs · **Mobile:** 🔲 merge embed immediately · **Guide:** [§B1](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#b1--update-on-every-single-point-instantly)
**Problem:** Doing workouts, the **"Height Loss" number doesn't go down** right away. It eventually worked — but only **after logging all habits and several workouts**. That's too much delay.
**Fix:** Every point, the **instant** it's earned from **any** source (workout, habit, nutrition, lifestyle), must immediately update — on the fly, no batching:
- **Posture+ points** (posture exercises, habits, adult nutrition) → `posture_plus += 0.001` · `height_loss −= 0.001` · `total_height += 0.001`
- **Genetic+ points** (teen growth / HGH / lifestyle) → `genetic_plus += 0.001` · `total_height += 0.001` (does **not** reduce Height Loss)

**Even 1 point** must move Posture+ (or Genetic+), Height Loss, and Total Height immediately. No waiting for multiple logs.
**Done when:** Logging a single point visibly updates the right stat, Height Loss, and Total Height on the dashboard right away.

### B2 — Fix the Genetic+/Posture+ spike-then-recalibrate flicker
**→ Backend:** ✅ fixed teen embed math · **Mobile:** 🔲 drop client optimistic double-count · **Guide:** [§B2](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#b2--fix-geneticposture-spike-then-drop-flicker)
**Problem:** Right after logging a workout and returning to the dashboard, **Genetic+ and Posture+ both jump big** (showing ~**+0.77 cm each at the same time**), then **recalibrate back down** to the correct numbers. Looks sloppy.
**Fix:** The dashboard must render the **correct** values on first paint — no inflated spike that then settles. Find the double-count / pre-recalc render and make the numbers land correct immediately. (Likely the same root cause as B3 — something is summed twice before it recalcs.)
**Done when:** Returning to the dashboard shows the right Genetic+/Posture+ values instantly, with no jump-then-drop.

### B3 — Fix Height-Loss tracking accuracy (must exactly mirror Posture+)
**→ Backend:** ✅ `height_loss_box.remaining_cm` at 3 dp · **Mobile:** 🔲 bind from API, don't recompute · **Guide:** [§B3](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#b3--height-loss-accuracy-3-decimal-places)
**Problem:** Currently **+0.028 Posture+** but **Height Loss shows 3.270**, when it started at **3.3**. 3.3 − 0.028 should be **3.272**, not 3.270 — it's drifting, so it isn't tracked 100% correctly.
**Fix:** Lock the relationship: `height_loss = starting_posture_loss − cumulative_posture_plus`, exact to 3 decimals. Height Loss must move down by **exactly** the Posture+ amount, every time.
**Done when:** With +0.028 Posture+ from a 3.3 start, Height Loss reads exactly **3.272** (and stays in sync for any value).

---

# SECTION C — Exercise player & cards

### C1 — Remove the rest counter (5-4-3-2-1 between exercises)
**→ Backend:** — · **Mobile:** 🔲 remove UI · **Guide:** [§C1](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#c1--remove-rest-countdown)
**Problem:** The inter-exercise resting countdown isn't needed anymore — when a workout's done the user just goes back to the exercise dashboard.
**Fix:** Remove the 5-4-3-2-1 rest countdown entirely.
**Done when:** No rest countdown appears; finishing an exercise returns to the exercise list.

### C2 — Add the category label to each exercise card
**→ Backend:** ✅ `category_label` on routine exercises · **Mobile:** 🔲 bind pill · **Guide:** [§C2](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#c2--category-label-on-exercise-cards)
**Problem:** On the **Posture Exercise** cards there's an empty pill (circled in the screenshot) with no category. Users can't tell what each exercise targets.
**Fix:** Show the exercise's **category** in that label — e.g. **HGH**, **Spinal Decompression**, **Legs & Hamstrings**, **Postural Correction** (use the correct category per exercise from the catalog).
**Done when:** Every exercise card shows its category in the previously-empty label.

### C3 — Fix Mountain Climber (timed, not reps)
**→ Backend:** ✅ `unit: "secs"`, `qty_min: 40` · **Mobile:** 🔲 timer player · **Guide:** [§C3](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#c3--mountain-climber--40-second-timer)
**Problem:** Mountain Climber is set up as reps.
**Fix:** Mountain Climber is a **timed** exercise — **40 seconds of the motion**, not reps. Use the timer/hold mode, not the rep counter.
**Done when:** Mountain Climber runs a 40-second timer, no rep count.

---

# SECTION D — Dashboard buttons → tappable popups (free + paid, BOTH tiers)

**→ Backend:** — (static copy) · **Mobile:** 🔲 D1 rename + D2 modals · **Guide:** [§D](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#section-d--dashboard-tappable-popups)

**Rule for all of them:** every stat and segment on the dashboard is **tappable on both free and paid**. Tap → small popup. Tap outside → dismiss. Each popup = the title + the one line below it. Several of these (the four segments + Height Loss + Height) are **currently just display labels — make them tappable too.**

### D1 — Rename
The teen top-left button **"Genetic Height" → "Genetic Average."**

### D2 — Popup copy

**SHARED — identical on BOTH the teen and adult dashboards:**

| Button | Popup text |
|---|---|
| **Height Loss** | How much height posture and compression have stolen — what's left to recover. This drops as you log workouts. |
| **Spinal** | Compression in your spinal discs that shortens your height — and one of the most recoverable areas. |
| **Posture** | Height lost to slouching and forward-head posture. Correcting it stands you taller. |
| **Pelvic** | Tilt in your hips that shortens your stance. Realigning it restores length. |
| **Legs** | Tightness and imbalance in your legs and hamstrings that pulls your posture down. |
| **Height** | Your current height right now, updated live as you log. |

**TEEN dashboard — top stats:**

| Button | Popup text |
|---|---|
| **Genetic Average** | Where you should be right now according to your genetics. |
| **Genetic mid-parental** | The height your genes point to, based on your mom's and dad's heights. |
| **True Optimized** 🔒 | Your personalized predicted height if you fully optimize posture, sleep, and nutrition. |
| **Genetic +** | Height gained today from your natural growth curve plus optimization. |
| **Posture +** | Height recovered today by correcting your posture and decompressing your spine. |
| **Daily Gains** | How much height you added today from all your activity combined. |

**ADULT dashboard — top stats:**

| Button | Popup text |
|---|---|
| **Optimized Height** 🔒 | Your full height once you've recovered everything posture and aging have cost you. This is the target. |
| **Base Height** | Your starting height when you began — before any recovery. |
| **Total Recovered** | The height you've gained back so far since you started. |
| **Daily Gains** | How much height you've recovered today. |

**Done when:** Every stat and segment above is tappable on free + paid and opens the correct popup; teen top-left reads "Genetic Average"; the four segments + Height Loss + Height (which were plain labels) are now tappable.

---

# SECTION E — Lifestyle card info popups

### E1 — Add an info icon + popup to each Lifestyle card
**→ Backend:** ✅ `info_popup` on lifestyle modules API · **Mobile:** 🔲 ℹ️ icon + modal · **Guide:** [§E1](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#e1--ℹ️-on-each-lifestyle-card)
**Problem:** The Lifestyle cards (Sleep / Hydration / Sunlight / Meditation) don't explain why they matter.
**Fix:** Add a small **ℹ️ info icon** to each card. Tap → popup. Tap outside → dismiss. Each popup = the title + the line below.

**SLEEP 🌙** — Your body releases its biggest surge of growth hormone during deep sleep — and the longer you sleep, the more surges you get. 8–10 hours gives your body the full window it needs to grow. Short sleep cuts that window short.

**HYDRATION 💧** — Your spinal discs are nearly 80% water, and they're what give you height between your bones. Stay hydrated and they stay full and tall — let them dry out and your spine compresses and you shrink. 2 litres keeps them plumped to full height.

**SUNLIGHT ☀️** — Sunlight is how your body makes vitamin D — the key that lets your bones actually absorb calcium and grow. No D, and the calcium you eat goes to waste. 20–30 minutes a day flips that switch on and keeps your growth plates fed.

**MORNING MEDITATION 🧘** — Stress floods your body with cortisol — a hormone that directly blocks growth hormone from doing its job. 10 calm minutes drops your cortisol, clears the path, and lets your growth hormone work. Less stress, more height.

**EVENING MEDITATION 🧘** — Winding down at night drops the stress hormone cortisol — the one that blocks growth hormone from working. A calm 10 minutes before bed clears the path so your body can grow while you sleep. It also helps you fall into deep sleep faster, where the real growth happens.

**Done when:** Each Lifestyle card has an info icon that opens the correct popup.

---

# SECTION F — NUTRITION PAGE REBUILD (the new two-tier design)

**→ Backend:** ✅ tier1/tier2 API + scoring · **Mobile:** 🔲 full page rebuild · **Guide:** [§F](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#section-f--adult-nutrition-page-rebuild)

**Applies to:** the **Adult** nutrition page (asset folder = "images adult foods"; tabs = Nutrition + Habits). *Confirm if teens should get the same page or keep their current nutrition.*
**This replaces** the old grey "tap to fill" hydration layout. Build it to match the new design: a Protein card, then **Spinal Hydration Tier 1**, then **Spinal Hydration Tier 2**, all with real food/drink images on every tile.

## F1 — Points logic (this is the whole math — it must add up to 15)
**→ Backend:** ✅ server scoring · **Mobile:** 🔲 display API values only · **Guide:** [§F1](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f1--points-logic-display-only--server-authoritative)

```
NUTRITION TOTAL = 15 pts  (shown as the X / 15 ring at the top)
├─ PROTEIN          = max 9     1 pt per 10 g  (caps at 90 g)
└─ FLUIDS POOL      = max 6     ← ONE shared pool, filled by BOTH tiers
   ├─ Tier 1 (spine drinks)   +2 pts per drink logged
   └─ Tier 2 (baseline liquids) +1 pt per item logged
```

Formulas (server-authoritative — never trust a client total):
```
protein_points   = min(9, floor(protein_grams / 10))
fluid_points     = min(6, (tier1_total_logs * 2) + (tier2_total_logs * 1))
nutrition_points = protein_points + fluid_points        // max 15
```

**The fluids pool is ONE shared 6-pt bucket.** Tier 1 and Tier 2 both pour into it. That's why 3 spine drinks alone (3×2) max it at 6, and 6 waters alone (6×1) also max it at 6. Tier-1 drinks are worth double because they add collagen, electrolytes, and silica that plain liquids don't.

**Worked examples (all verified):**
| Logged | Protein | Fluids | Total |
|---|---|---|---|
| 30 g protein + Bone Broth + Watermelon + Coconut | 3 | 6 | **9 / 15** ← matches the screenshot |
| 90 g protein + 3 spine drinks | 9 | 6 | 15 / 15 (max) |
| 0 protein + 6 waters | 0 | 6 | 6 / 15 |
| 50 g protein + 1 spine drink + 2 waters | 5 | 4 | 9 / 15 |

Routes to **Engine 1** (adult nutrition → Engine 1, 1 pt = 0.001 cm). No engine change.

## F2 — Multiple logging (NEW — important)
**→ Backend:** ✅ `add_tier1` / `undo_tier1` / `add_tier2` / `undo_tier2` · **Mobile:** 🔲 tap/long-press + badges · **Guide:** [§F2](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f2--multiple-logging-tiles--badges)
A user can log **the same drink more than once** — twice, three times, four times — so the page captures whatever they actually drink that day.
- Each tap on a tile = **+1 serving** of that drink/item and adds its points (Tier 1 +2, Tier 2 +1) **up to the 6-pt fluid cap**.
- Each tile shows a **count badge** when logged more than once (e.g. `×2`, `×3`). A tap adds one; a **long-press (or a − control)** removes one.
- **Beyond the cap:** logging past 6 fluid points is still **allowed and recorded** (so the user's real intake is tracked), but it **adds no points past 6**. Example: Bone Broth ×4 = 8 raw → fluid points cap at **6**, consumption still stored as 4.
- Protein is entered in **grams only** via the gram buttons; it caps at 9 pts / 90 g. (The protein food images are not loggable — see F3.)

## F3 — Screen design & layout (build reference)
**→ Backend:** — · **Mobile:** 🔲 full layout · **Guide:** [§F3](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f3--screen-layout-mobile)
*(Your Gemini screenshot is the visual mock; this is the structure to build. I can't hand over a literal .fig file, but this spec + that screenshot fully define it.)*

**Header:** back arrow · "HEIGHT / MAXIMIZE YOUR HEIGHT" lockup · settings gear.
**Tabs:** `Nutrition` (active, cyan underline) · `Habits`.
**Tracker row:** "Nutrition tracker" + "June 14 · daily points" on the left; a **circular progress ring showing `X / 15`** on the right (cyan arc on dark track).

**Card 1 — PROTEIN**
- Title `PROTEIN` with a small strip of the 6 protein food images beside it — these are **decorative only** (they show the user what counts as protein). They are **NOT** tappable.
- Description: *Rebuilds the back, core, and glute muscles that hold your spine tall. 1 pt per 10 g — aim for 90 g.*
- Progress line: `30 / 90 g · +3 pts` (left) and `3 / 9 pts` (right) above a cyan progress bar.
- **Logging row (the only way to add protein):** `+10g` `+20g` `+30g` `+ Add` (custom grams) and an **undo** ↺. The user enters grams — the app can't know how many eggs or how much chicken they ate, so grams is the input. No per-food quick-adds.

**Card 2 — SPINAL HYDRATION TIER 1** · right-aligned `+2 pts per drink`
- Description: *Your discs are 80% water and compress through the day. Pick any 3 spine-friendly drinks to refill them.*
- **6 drink tiles**, 2 rows × 3: Bone Broth · Watermelon · Coconut · Cucumber · Celery · Beet. Each tile = the drink **image** + name; logged tiles get a cyan border + count badge.
- **`Fluids X / 6 pts` meter** sits under this card — it is the **shared pool** (Tier 1 + Tier 2 both feed it).

**Card 3 — SPINAL HYDRATION TIER 2** · right-aligned `+1 pt per item`
- Description: *Essential baseline systemic hydration for overall body health. Log other key daily liquids here.*
- **6 tiles**, row(s) of 3: Water · Milk · Tea · Coffee · Juice · Carbonated. Same tile pattern (image + name + count badge). These feed the **same** fluids pool above.

**Tile states (all tiles, both tiers):** empty = thin teal outline; logged = filled + cyan border + `×N` badge; tap = +1; long-press / − = −1.

## F4 — Asset mapping (your Gemini image files → tiles)
**→ Backend:** — · **Mobile:** 🔲 bundle PNGs · **Guide:** [§F4](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f4--asset-mapping-local-bundle)

**Protein food images (DISPLAY ONLY — decorative strip in the Protein card header, not tappable, no point values):**
| Shows | Asset |
|---|---|
| Chicken | `chicken2` |
| Salmon | `salmon2` |
| Beef / Steak | `beef2` |
| Milk | `milk2` |
| Beans | `beans2` |
| Eggs | `eggs2` |

**Tier 1 — spine drinks (+2 pts each):**
| Tile | Asset |
|---|---|
| Bone Broth | `broth2` |
| Watermelon | `watermelon2` |
| Coconut | `coconut2` |
| Cucumber | `cucumber2` |
| Celery | `celery2` |
| Beet | `beet2` |

**Tier 2 — baseline liquids (+1 pt each):**
| Tile | Asset |
|---|---|
| Water | `water bottom` |
| Milk | `milk bottom` |
| Tea | `tea bottom` |
| Coffee | `coffee bottom` |
| Juice | `juice bottom` |
| Carbonated | `carbonated bottom` |

All images live in the **"images adult foods"** folder. Export each as a transparent PNG, ~512×512, centered. (Milk appears in both Protein and Tier 2 — that's intentional, see flag below.)

## F5 — Copy (exact strings)
**→ Backend:** — · **Mobile:** 🔲 verbatim strings · **Guide:** [§F5](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f5--exact-copy-strings)
- Protein desc: "Rebuilds the back, core, and glute muscles that hold your spine tall. 1 pt per 10 g — aim for 90 g."
- Tier 1 header: "SPINAL HYDRATION TIER 1" · "+2 pts per drink" · desc "Your discs are 80% water and compress through the day. Pick any 3 spine-friendly drinks to refill them."
- Tier 2 header: "SPINAL HYDRATION TIER 2" · "+1 pt per item" · desc "Essential baseline systemic hydration for overall body health. Log other key daily liquids here."
- Fluids meter label: "Fluids X / 6 pts" (sub-note optional: "spine drinks + baseline liquids share one pool").

## F6 — Data model
**→ Backend:** ✅ `tier1_log` / `tier2_log` + `GET/POST /api/adult-nutrition` · **Mobile:** 🔲 wire actions · **Guide:** [§F6](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f6--api-contract)
- `protein_grams` (int).
- `tier1_log`: per-drink counts, e.g. `{bone_broth, watermelon, coconut, cucumber, celery, beet}` (each an int ≥ 0).
- `tier2_log`: per-item counts, e.g. `{water, milk, tea, coffee, juice, carbonated}` (each an int ≥ 0).
- Derived/served: `protein_points`, `fluid_points`, `nutrition_points` via F1 (server-authoritative).
- Store full per-drink counts so real intake is tracked even past the cap.

## F7 — Acceptance tests
**→ Backend:** ✅ unit tests · **Mobile:** 🔲 device QA · **Guide:** [§F7](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f7--acceptance-tests-qa-on-device)
1. 30 g protein + Bone Broth + Watermelon + Coconut → ring reads **9 / 15** (3 + 6).
2. 90 g protein + 3 spine drinks → **15 / 15**.
3. 6 waters (Tier 2) only → fluids **6**, total **6 / 15**.
4. 2 spine drinks + 2 waters → fluids **6** (4 + 2).
5. Bone Broth ×4 → fluid points cap at **6**, count stored as **4**.
6. Protein logged via gram buttons only; caps at 9 / 90 g (no per-food tapping).
7. Nutrition never exceeds **15**; points flow to Engine 1.

## F8 — Flags (decide before final build)
**→ Backend:** — · **Mobile:** 🔲 product rules (milk display vs loggable) · **Guide:** [§F8](docs/MONDAY_SPEC_FRONTEND_GUIDE.md#f8--product-flags-do-not-fix)
- **Milk appears as a Protein image (display only) and as a tappable Tier 2 liquid.** Only the Tier 2 milk is loggable (adds a fluid point). The Protein milk is just illustration. No double-count.
- **Tier 2 is hydration tracking, not a spine claim.** Coffee/carbonated count toward *baseline hydration* (general health), not disc benefit — keep that framing honest; the spine benefit lives in Tier 1. (Coffee is mildly dehydrating, so it's the weakest item, but it's included to catch real intake.)

---

# DEFINITION OF DONE (quick QA)
1. 8 questions → **results screen** → paywall (A1). 2. Declined free user: dashboard visible, **every** action locked to paywall (A2). 3. **One** point instantly moves Posture+/Genetic+, Height Loss, Total Height (B1). 4. No spike-then-drop on Genetic+/Posture+ (B2). 5. 3.3 start − 0.028 Posture+ = exactly **3.272** Height Loss (B3). 6. No rest countdown (C1). 7. Every exercise card shows its category (C2). 8. Mountain Climber = 40-sec timer (C3). 9. Every dashboard stat + segment tappable on free + paid with the correct popup, both tiers; teen top-left = "Genetic Average" (D1, D2). 10. Lifestyle cards have info-icon popups (E1). 11. **Nutrition page:** Protein + Tier 1 + Tier 2 built with images; ring = X/15; fluids share one 6-pt pool; multiple logging works; math matches F1/F7 (F).
