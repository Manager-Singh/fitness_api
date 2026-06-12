# HEIGHT APP — FRIDAY WORK ORDER (Complete Build Spec)
### For the dev team's Cursor + Claude worker. Work top to bottom, in order. Tick each box.
**Date issued:** Fri, Jun 12, 2026

---

## ⛔ READ THIS FIRST — THE GOLDEN FENCE (applies to every task below)

You are doing **UI, display, content, and points-config work.** You are **NOT** re-architecting the height engine. Do not touch any of the following unless a task *explicitly* says so:

- The point-to-cm conversion (1 pt = 0.001 cm Engine 1; teen Engine 2 = 0.00005 cm).
- Engine 1 / Engine 2 routing logic.
- The HeightLedger (μm storage, append-only rule, `rebuildLedgerFromDate()`).
- Workout logging, `reps_done`, the streak engine, the rank engine.
- The 20 original exercise-catalog columns (you may read `seconds_per_rep`, the 21st).
- The Ultimate Height Predictor engine math (`HeightPredictorEngine` in `optimized_height_predictor.dart`) — it is a **sealed box**.

**Three of these tasks change POINT CAPS and POINT VALUES.** That is allowed and intended — but a cap is a config number, not engine surgery. Change the constant; never rewrite the engine that reads it. If a change starts touching ledger writes or cm-conversion, **stop and flag it.**

**Definition of "done" for every task:** the change is visible on a real device in the new Play Store build AND the listed acceptance test passes. "It compiles" is not done. "I wrote the code" is not done. **Shown working on device = done.**

---

## WORK ORDER AT A GLANCE

| # | Task | Type | Risk | Why it's in this slot |
|---|---|---|---|---|
| 1 | Fix the % optimization math (one 68-pt pool) | **Bug — logic** | 🔴 High | It's a wrong number users see every day. Foundational. Do it first. |
| 2 | Audit & verify the 20-point assessment plumbing | **Bug — verify** | 🔴 High | The predictor is the paid hero feature; confirm every input reaches the engine. |
| 2A | Assessment "Data Confirmed" animated intro screen | **New build** | 🟡 Med | Reveals known data points with green checks before questions — makes it feel high-end. |
| 3 | Adult Nutrition page — full redesign | **New build** | 🟡 Med | Replaces the confusing food-chip page with the simple protein+fluids model. |
| 4 | Nutrition food rows bigger / readable | **Bug — UI** | 🟢 Low | Folds into #3 for adults; still needed for teens. |
| 5 | Habit instructions — tap-down "How to" | **New content** | 🟢 Low | Drop-in detail panel. Self-contained. |
| 6 | Height-Loss box (teens + adults) | **New build** | 🟡 Med | Reads existing posture data; must update live on every log. |
| 7 | Make the habits/lifestyle screen full-screen | **Bug — UI** | 🟢 Low | Same screen family as #5. Batch them. |
| 8 | Remove fake social-proof onboarding screens | **Deletion** | 🟢 Low | Pure removal. Fast. Do last. |
| 9 | Add segment up-sell icons to growth-trend screen | **New content** | 🟢 Low | Onboarding asset wiring. |

Items 4+5+7 all live on the same two screens (Nutrition, Habits/Lifestyle) — batch them in one pass so you only touch those files once. Items 2 + 2A are both in `optimized_height_predictor.dart` — do them together.

---

# ✅ TASK 1 — FIX THE OPTIMIZATION % MATH (Nutrition + Lifestyle + Habits)

**Friday sheet item #2. This is a real bug, highest priority.**

### The bug
User tapped sleep + hydration + sunlight + both meditations and the home screen showed **50% optimized**. That is wrong. The % is being computed off a count of items or a hardcoded fraction, **not off the total point pool.**

### The rule (this is the canonical formula — implement EXACTLY)
The optimization % runs off **one shared pool of all trackable points across the three sections.** Every single trackable point is worth the **same** percentage.

**TEENS — total pool = 68 points** (Nutrition 35 + Lifestyle 21 + Habits 12):

> **Each point = 100 ÷ 68 = 1.47%**

```
optimization_pct = min(100, round( (total_points_earned / 68) * 100 ))
```
where `total_points_earned = nutrition_pts + lifestyle_pts + habit_pts` (each already capped at its own max: 35 / 21 / 12).

So:
- 1 point logged → 1.47%
- 10 points → 14.7%
- All 68 → 100%

**ADULTS — total pool = 27 points** (Nutrition 15 + Habits 12; adults have **no Lifestyle tab**):

> **Each point = 100 ÷ 27 = 3.70%**

```
optimization_pct = min(100, round( (total_points_earned / 27) * 100 ))
```
where `total_points_earned = adult_nutrition_pts + habit_pts` (capped 15 / 12).

> **Adult nutrition cap timing:** the 15 assumes Task 3 (the nutrition redesign) is in this build. If Task 3 ships in the same build, adult pool = 27. If Task 3 is NOT in this build yet, use the OLD adult nutrition cap to set the adult pool — confirm the old cap before hardcoding.

### Why one pool, not per-section
The whole "optimized today" number is a **single daily score** built from everything the user logged across nutrition, lifestyle, and habits combined. One pool, every point equal weight. This is the model the client wants and it's what the screen should reflect. (Each section still has its own internal cap so no one section can run away — but the headline % divides by the combined pool.)

### Implementation notes
- Clamp to 100 (never show 103%).
- `*_pts` feeding the sum must be the **post-cap** value. If the engine hands you a raw uncapped number, cap it at the section max (35/21/12 teen, 15/12 adult) before summing, or the % overshoots.
- Round for display, but compute from the real points so a single logged item always nudges the bar (same principle as the posture-bar decimal fix — never round the input to zero).
- **The 50%-bug root cause:** the old code was almost certainly dividing by a count of tapped items, or scoring one section in isolation, instead of summing all points and dividing by the fixed pool (68 teen / 27 adult). Replace whatever it's doing with the single formula above.

### Files (Cursor: grep for these)
- The home-screen optimization widget (search where the "% optimized" headline renders on `dashboard-new`).
- `utils/scores_summary.py` / `today_score_breakdown()` — confirm it returns `food/lifestyle/habit` point totals so the UI can sum them and divide by the pool.

### ✅ Acceptance test
1. Fresh day, teen account. Log **one** lifestyle item worth 1 pt → headline shows **~1.47%** (1 point), NOT 50%, NOT 0%.
2. Tap sleep + hydration + sunlight + both meditations (the bug-report combo) → % equals (those points ÷ 68) × 100, NOT a flat 50%.
3. Log points across all three sections until 68 total → reads **100%**.
4. Adult account: log to 27 total pts → 100%; ~13–14 pts → ~50%.
5. Each individual point added moves the headline by ~1.47% (teen) / ~3.70% (adult).

---

# ✅ TASK 2 — AUDIT & COMPLETE THE 20-POINT ASSESSMENT

**Friday sheet item #4. The predictor is the paid flagship — it must run on its full input set.**

### What you reported collecting
> voice / facial hair · underarm hair · Adam's apple · growth in 12 months · wingspan & wrist

### What the engine ACTUALLY supports (read `optimized_height_predictor.dart`, `HeightPredictorEngine.predict()`)
The sealed engine already accepts and uses **all** of these inputs. Nothing about the math is missing — the question is whether the **flow is feeding the engine every input on both age bands.** Here is the complete required input matrix. Verify each one is collected and passed:

| Input | Engine param | Band A (under 17.5) | Band B (17.5–20) | Source |
|---|---|---|---|---|
| Sex | `sex` | auto | auto | profile |
| Exact age (decimal yr) | `ageYears` | auto from DOB | auto from DOB | profile |
| Current height | `currentHeightCm` | auto | auto | profile |
| Father height | `fatherHeightCm` | auto | auto | onboarding |
| Mother height | `motherHeightCm` | auto | auto | onboarding |
| Posture recovery cm | `postureRecoveryCm` | auto (READ — never recompute) | auto | posture assessment |
| **Voice depth** (M) | `maleMaturity.voiceDepth` | ✅ ask | ❌ skip (puberty done) | in-flow |
| **Facial hair** (M) | `maleMaturity.facialHair` | ✅ ask | ❌ skip | in-flow |
| **Body/underarm hair** (M) | `maleMaturity.bodyHair` | ✅ ask | ❌ skip | in-flow |
| **Adam's apple** (M) | `maleMaturity.adamsApple` | ✅ ask | ❌ skip | in-flow |
| **Menarche status** (F) | `femaleMaturity.menarcheStatus` | ✅ ask | ❌ skip | in-flow |
| **Body hair** (F) | `femaleMaturity.bodyHair` | ✅ ask | ❌ skip | in-flow |
| **Recent growth (cm/12mo)** | `recentGrowthCm` | ✅ ask (skippable) | ✅ ask — this is the MAIN Band B question | in-flow |
| **Wingspan** | `wingspanCm` | optional/skippable | optional/skippable | in-flow (tape) |
| **Wrist circumference** | `wristCircumferenceCm` | optional/skippable | optional/skippable | in-flow (tape) |

### The actual finding (tell the worker this plainly)
The list the client tested — *"voice, facial hair, underarm, Adam's apple, growth, wingspan & wrist"* — **is the complete and correct Band A male set.** Nothing is missing for a Band A male. It only *looks* thin because:

1. **The 6 auto-filled inputs are invisible.** Sex, age, current height, both parent heights, and posture-recovery cm are pulled from profile/onboarding and never shown as questions — but they ARE fed to the engine. The user sees 5–6 questions and assumes that's all the model uses. It isn't. **This is correct behavior, not a bug — but we ARE going to SHOW it to the user.** That's the new build in **Task 2A below**: an animated data-confirmation screen that reveals each known data point with a green check before the questions start, so the assessment visibly feels like a full 20-point engine.
2. **Band B (17.5–20) correctly shows fewer questions** — maturity questions are skipped because puberty is done. Also correct.
3. **Females get a different set** (menarche + body hair instead of the 4 male markers). Also correct.

### So what to actually DO
The engine is fine. Verify the **plumbing**:
- [ ] Confirm `_computeResult()` passes `recentGrowthCm`, `wingspanCm`, `wristCm` through to `predict()` (it does in the file — confirm it survived any edits).
- [ ] Confirm the 6 auto inputs are non-null at call time. **If `fatherHeightCm`/`motherHeightCm` are null** (user picked "I don't know" in onboarding), pass the regional-average fallback — same value the dashboard already uses. A null parent height will skew or crash the genetic anchor. This is the one real risk.
- [ ] Confirm Band B still asks `recentGrowthCm` as a **required** question (it's the primary signal when maturity is done) — not skippable on Band B, even though it's skippable on Band A.
- [ ] Confirm the reveal writes to the existing True Optimized field and the dashboard reads `true_optimized_green_cm` from the predictor, gated on `completed: true` (your team already documented this gating — verify it holds).

### ⚠️ Known live discrepancy to close (from your 11 Jun report)
Dashboard projects a green value (e.g. 204.6) while the predictor API still returns `completed: false`. **The predictor API is the single source of truth.** The green True Optimized number must NOT display until `GET /api/predictor/ultimate-height` returns `completed: true`. Until then the pill stays LOCKED. Fix the dashboard to stop showing a projected green value pre-completion.

### ✅ Acceptance test
1. Band A male (e.g. age 14): all 4 maturity Qs + recent growth + tape appear; reveal produces a number; dashboard green pill unlocks only after `completed: true`.
2. Band A female (age 14): menarche + body hair + still-growing + recent growth + tape; reveal works.
3. Band B (age 19): NO maturity Qs; recent growth is required; tape optional; reveal works.
4. Parent height = "I don't know": prediction still runs using regional fallback, no crash.
5. Pre-assessment: dashboard green value is hidden/locked, never a stray projected number.

---

# ✅ TASK 2A — ASSESSMENT "DATA CONFIRMED" INTRO SCREEN (NEW BUILD)

**This is the new screen the client wants. It is the FIRST screen after the user taps the True Optimized pill / "Take the 20-point assessment," shown BEFORE any questions.** It replaces the current plain `_IntroScreen` in `optimized_height_predictor.dart`.

### The goal
Make the assessment feel like a high-end, data-rich engine. Before asking anything, the screen **reveals the data points the app already knows** one by one, each landing with a green checkmark. The user watches their profile data populate and thinks "this thing already knows a ton about me" — then the question screens feel like the final layer of a serious system, not a thin 5-question quiz.

### The animation (sequential reveal, top to bottom)
A vertical list builds itself row by row. Each row animates in on a stagger (~500–700 ms apart), and as each label appears, its **value pops in on the right** and a **green checkmark lands at the far right.** Order:

| Step | Left label (fades in) | Right value (pops in after a beat) | Far right |
|---|---|---|---|
| 1 | **Gender** | the user's actual sex — e.g. `Male` | ✅ green check |
| 2 | **Exact Age** | exact age to the day — e.g. `14 yrs, 2 mo, 11 days` | ✅ |
| 3 | **Your Height** | current height — e.g. `165.0 cm` | ✅ |
| 4 | **Father's Height** | e.g. `180.0 cm` | ✅ |
| 5 | **Mother's Height** | e.g. `166.0 cm` | ✅ |
| 6 | **Posture Recovery** | the recoverable cm — e.g. `+4.2 cm` | ✅ |

- Each label appears first (left-aligned, white). After a short beat (~250 ms) its value slides/fades in from the right (cyan/teal, bold). Then the green checkmark scale-pops at the far right edge of the row.
- Subtle row styling: thin divider or a faint dark rounded row behind each, so the checks line up in a clean column on the far right.
- Optional: a soft tick/confirm sound per check if the player audio is on (respect the existing sound toggle — never required).

### After all 6 rows are checked
- A short pause, then a header/subhead settles in and the **primary button** appears:
  - **Header:** `We already know this much.`
  - **Subhead:** `Just confirm a few growth signals and we'll calculate your True Optimized Height.`
  - **Button:** `CONTINUE →` (teal pill) — advances to the FIRST question screen (the existing maturity / recent-growth flow).

### Values to bind (all already passed into `OptimizedHeightPredictorFlow`)
- Gender ← `widget.sex` ("male"/"female" → display "Male"/"Female")
- Exact Age ← computed from `widget.dob` (`DateTime.now().difference(dob)`) → format as years/months/days (the engine already computes `_ageYears`; for display, break it into Y/M/D)
- Your Height ← `widget.currentHeightCm`
- Father's Height ← `widget.fatherHeightCm` (if null → show `Using regional average`, still checked — don't show a blank)
- Mother's Height ← `widget.motherHeightCm` (same null handling)
- Posture Recovery ← `widget.postureRecoveryCm` (display as `+X.X cm`)

### Band handling
- Show **all 6 rows on both Band A and Band B** — the known data is the same regardless of age. Only the *question* screens after this differ by band.
- Keep the existing intro copy variants out — this animated screen IS the new intro for both bands.

### Build notes / fences
- This is **display only.** It reads the values already handed to the flow; it computes nothing new and writes nothing. Pure presentation.
- It must not block: if any value is briefly unavailable, show the regional-average/"—" gracefully and still check the row — never hang on a missing field.
- Implement as a replacement for `_IntroScreen` (or a new `_DataConfirmScreen` inserted as page 0). Use staggered `AnimatedOpacity`/`AnimatedSlide` + a scale transition on the check icon. Match `_Style` (teal `#00BFB3`, bright `#4EE6E6`, bg `#0A0A0A`, card `#1C1C1E`).

### ✅ Acceptance test
1. Tap the assessment entry → the 6 rows animate in one by one, each value pops on the right, each ends with a green check in a clean far-right column.
2. After the 6th check, the header + `CONTINUE →` appear; tapping advances to the first real question.
3. Real profile values show (correct sex, exact age to the day, real heights, real +cm posture).
4. Null parent height → row shows "Using regional average" and still checks; no blank, no crash.
5. Works on both a Band A (14yo) and Band B (19yo) account; only the subsequent questions differ.

> A live design reference for this screen (the animated reveal) is included in the chat alongside this doc — the team can mirror the layout, stagger, and check-pop in Flutter.

---

# ✅ TASK 3 — ADULT NUTRITION PAGE: FULL REDESIGN

**Friday sheet item #7 (and #1 for adults). The current chip-grid page is confusing, cramped, off-spec. Replace it.**

### Kill
- The "quick foods to click" chip grid. Gone. It's the source of the confusion.
- The old 13-food / category-slot system for adults.

### Build — three simple controls, ONE screen, NO scrolling
The whole adult nutrition tab becomes three sections. Tap-driven, almost no typing.

#### Section 1 — Protein (the main engine)
- **One horizontal progress bar:** `Protein  40 / 90 g  ·  +4 pts`
- **Scoring:** 1 point per 10 g. **Max 9 points** (caps at 90 g).
- **Input:** a single "+ Add protein (g)" stepper/field. User types grams or taps +/–. That's it. No food chips.
  - (If you want one convenience affordance, a tiny "+10 / +20 / +30 g" quick-add row is allowed — but the underlying value is always **grams**, never a named food. Keep it dead simple.)
- **Formula:** `protein_pts = min(9, floor(protein_grams / 10))`

#### Section 2 — Spinal Hydration (the spine drinks)
- **Three glass icons** the user taps to fill. Tapping logs **500 ml** of a spine drink.
- **Scoring:** 2 points per 500 ml drink. These share the fluids cap with water (below).
- **The 6 drinks** (any combination — 3 bone broths is as valid as one of each): **Bone Broth · Watermelon Juice · Cucumber Juice · Celery Juice · Coconut Water · Beet Juice.**
- Tap a glass → pick a drink → it fills, +2 pts.

#### Section 3 — Water
- **A row of bottle icons,** each = 500 ml.
- **Scoring:** 1 point per 500 ml (i.e. 2 pts per litre).

#### The shared FLUIDS cap
Spinal Hydration + Water share **one fluids bucket, max 6 points.**
- Any spine drink = 2 pts / 500 ml.
- Water = 1 pt / 500 ml.
- So a user caps fluids at 6 with three spine drinks (1.5 L), or with 3 L of water, or any mix.

```
fluids_pts = min(6, (spine_drinks_count * 2) + floor(water_ml / 500) * 1)
```

#### Section total
**Adult Nutrition cap = 9 (protein) + 6 (fluids) = 15 points.** This is the number Task 1 divides by for the adult nutrition %.

> **Why water is worth half of a spine drink (put this rationale in the UI, don't hide it):** the point gap is intentional and scientifically grounded — spine drinks add collagen/glycine (bone broth), electrolytes (watermelon/coconut/celery), and silica (cucumber) that plain water can't. The 2:1 ratio quietly rewards the better choice without punishing water. Don't "fix" it to be equal.

### Exact copy for the Spinal Hydration section
> **Spinal Hydration**
> Your spinal discs are nearly 80% water and compress as they lose fluid through the day — it's why you're shorter at night. Refill them with 3 spine-friendly drinks daily, any mix from the list. The goal is simply keeping your discs hydrated and your connective tissue fed.
> **+2 pts each · 3 per day**

### Design requirements
- Match the **high-end look of the Lifestyle & Habits cards** (rounded dark cards, cyan borders, soft glow). The client specifically wants it to feel as polished as those.
- **Must fit on one screen, no scroll**, on a Samsung S23-class device (393×851 dp). Use responsive scaling (you already added `AdultNutritionMetrics` for this — use it).
- Protein bar at top, three hydration glasses middle, water bottles bottom. Clean vertical rhythm.

### ⚠️ Double-count guard
Adults no longer have a Lifestyle tab, and water now lives in Nutrition. **Make sure nothing in the old Lifestyle/water code still awards adults water or sleep points** — otherwise fluids get counted twice. Check this when wiring in.

### Data model
- `AdultNutritionDay { user_id, date, protein_grams, spine_drinks: [drink_id…], water_ml }`
- Derive points at read time from the formulas above. Do not store points; store the raw grams/ml/drink list.
- This routes to **Engine 1** (adult nutrition → Engine 1, never Engine 2). Unchanged from spec.

### ✅ Acceptance test
1. Log 90 g protein → bar full, +9 pts, section can't exceed 9 from protein.
2. Tap 3 spine drinks → +6 fluids pts → fluids capped; a 4th drink adds 0.
3. 3 L water only → fluids = 6 (capped). 1 spine drink (2) + 4 water (4) = 6.
4. Full section = 15 pts. Adult nutrition % (Task 1) reads 100%.
5. Screen shows fully on one S23 screen, no scroll, matches Lifestyle/Habits styling.
6. No water/sleep points leak to adults from the old Lifestyle code.

---

# ✅ TASK 4 — NUTRITION FOOD ROWS: BIGGER & READABLE

**Friday sheet item #1.**

- **Adults:** resolved by Task 3 (the chip grid is gone). No separate work.
- **Teens:** the teen food log rows are too small/cramped after the responsive shrink. Bump them back up closer to the previous size — larger row height, larger font, more tap target. Keep it readable on small devices but do not over-shrink.
- Apply the same readability pass to the header progress ring number if it's still tiny (you already bumped the adult ring to ~42% of ring diameter — match that generosity on teen).

### ✅ Acceptance test
Teen nutrition rows are comfortably readable and tappable on a small device; nothing clipped; ring number legible.

---

# ✅ TASK 5 — HABIT "HOW TO" TAP-DOWN PANELS

**Friday sheet item #3 (the instruction text). Self-contained content addition.**

Each habit card gets a tappable **"How to" / info** affordance. Tapping expands a detail panel with the exact text below. Collapse on second tap. No other behavior change.

#### 5.1 — Puppet String Walk
> Imagine an invisible string attached to the crown of your head, gently pulling you straight up toward the ceiling. Keep your chin level, let your shoulders drop, and walk as tall as possible.
> **Duration:** Focus on this active posture for at least 3 to 5 minutes of continuous walking. Perform once during your morning (AM) routine, and once in the evening (PM).

#### 5.2 — 60-Sec Desk Un-Slouch
> Slide your hips all the way to the back of your chair and plant your feet flat. Engage your core, drop your shoulders away from your ears, and actively lengthen your spine.
> **Duration:** Hold this rigid, perfect alignment for exactly 60 seconds. Check this off once in the AM and once in the PM.

#### 5.3 — Tech-Neck Lift
> Stop bending your neck forward. Raise your arms and hold your phone directly at eye level to eliminate cervical spine compression while you scroll, read, or watch.
> **Duration:** Maintain this elevated hold for at least 15 continuous minutes of screen time to earn your daily log.

#### 5.4 — Doorway Posture Reset
> Use doorways as a physical trigger. Right before you walk through a frame, pause, roll your shoulders back and down, tuck your chin slightly, and actively lengthen your spine to your maximum height.
> **Duration:** Perform this quick alignment check 3 separate times throughout your day before checking off the log.

### ⚠️ Points & frequency reconciliation (IMPORTANT — these define the Habits cap of 12)
The habit **point values and frequencies** must match what Task 1's 12-point cap assumes. Lock them as:

| Habit | Points each | Times/day | Daily total |
|---|---|---|---|
| Puppet String Walk | 3 | 2 (AM + PM) | 6 |
| 60-Sec Desk Un-Slouch | 1 | 2 (AM + PM) | 2 |
| Tech-Neck Lift | 2 | 1 | 2 |
| Doorway Posture Reset | 1 | 2 | 2 |
| **TOTAL** | | | **12** |

> ⚠️ **Note the conflict to resolve:** the *instruction text above* for Doorway says "3 separate times" and Tech-Neck says "15 minutes," but the *points table* the cap is built on uses Doorway ×2 and Tech-Neck at one log. **The points table is canonical for scoring** (it produces the 12 cap). The instruction text is coaching guidance. If the client wants the log frequency to literally match the text (Doorway ×3), that changes the cap to 13 and Task 1's divisor — **flag it and wait for confirmation before changing the cap.** For now: build to the 12-point table, display the text as written.

This Habits section applies **identically to adults and teens** — do not fork them.

### ✅ Acceptance test
Tap "How to" on each of the 4 cards → correct detail text expands → collapses on second tap. Points per habit and the 12 cap match the table. No engine change.

---

# ✅ TASK 6 — HEIGHT-LOSS BOX (TEENS + ADULTS)

**Friday sheet item #5. New build. Reads existing posture data — must update live, no lag.**

### What it is
A box on the dashboard showing the user's **current posture height loss** in cm — the recoverable deficit from their posture questionnaire/scan — and it **shrinks dynamically as they recover.**

### Where the number comes from (do NOT invent a new formula)
- Initial value = `Total_Recoverable_Loss` from the posture questionnaire/scan (the value the posture engine already produces — same one Task 2 reads as `postureRecoveryCm`).
- **Current displayed loss = `Total_Recoverable_Loss − PosturePlus_Cumulative`** (the remaining deficit). This is already a derived value in the engine — read it, don't recompute it.
- As `PosturePlus_Cumulative` grows from logged workouts, the remaining loss shrinks. When fully recovered, it reads 0.0 (or "Recovered ✓").

### Behavior requirements
- **Updates on every logged workout / point added — no lag, no end-of-day batch.** Log a posture exercise → the box ticks down immediately. This is the same live-update requirement as the posture recovery bars; reuse that update path.
- **Re-assessment changes it.** When the user re-takes the posture assessment, the initial loss is overwritten per the existing re-scan rule (re-scan updates `Current_Loss`; first scan after questionnaire sets `Total_Recoverable_Loss`). The box reflects the new baseline.
- **Decimals:** show enough precision that a single workout visibly moves it (≥2 decimals, same fix as the bars). Never round the per-workout nudge to zero.

### Display
- Use the design the client attached for this box (matching dark/teal card).
- Suggested copy: headline "Height Lost to Posture", big number e.g. `4.20 cm`, sub-label "Recoverable — shrinks as you train."
- Applies to **both** teen and adult dashboards.

### ⚠️ Fence
This box is a **read-only display** of existing engine state. It must not write to the ledger, must not change recovery rate, must not affect points. Display only.

### ✅ Acceptance test
1. New user post-questionnaire: box shows their `Total_Recoverable_Loss` (e.g. worst-case 6.0).
2. Log one posture workout → box decreases immediately (visible at 2 decimals), no refresh needed.
3. Log several → it keeps shrinking each time, never frozen.
4. Re-take assessment with different answers → box resets to the new baseline.
5. Fully recovered → reads 0.00 / "Recovered ✓". Confirmed on both a teen and an adult account.

---

# ✅ TASK 7 — MAKE HABITS / LIFESTYLE SCREEN FULL-SCREEN

**Friday sheet item #3 (the layout half). Batch with Task 5 — same screen.**

- Kill the **gap at the bottom** of the habits screen. It must fill the viewport (full-screen, responsive, no dead space, no scroll on standard devices).
- With the reclaimed space, make the **images and habit cards bigger** — more breathing room, larger illustrations, larger tap targets.
- Keep it dynamic/responsive so it fits every device (you already moved to `ListView.separated` and compact card mode — ensure the full-screen layout still adapts on small devices without overflow).

### ✅ Acceptance test
Habits screen fills the screen on S23-class and a small device, no bottom gap, no scroll, cards/images visibly larger, AM/PM selectors don't overflow.

---

# ✅ TASK 8 — REMOVE FAKE SOCIAL-PROOF ONBOARDING SCREENS

**Friday sheet item #6. Pure deletion. Do last (it can't break anything downstream once routing is patched).**

- Remove the fabricated testimonial / social-proof screens from **both** the teen and adult onboarding flows. Specifically the "Join 30,000+ teens" screen and any "Jake/Priya/Marcus +Xcm" testimonial cards, and the equivalent adult social-proof screen if present.
- **Patch the onboarding router** so the flow skips cleanly from the screen before to the screen after — no dead step, no blank page, no broken "Step X of Y" counter.
- After removal, re-verify the onboarding step order and the progress bar count so it still reads correctly.

> Why: these are fabricated numbers/testimonials. On a public, paid, health-adjacent app aimed partly at minors, fake testimonials are an FTC and app-store-review liability and a screenshot-on-Reddit risk. Removing them is the safe call. (If real testimonials exist later, they can be added back with "individual results vary.")

### ✅ Acceptance test
Walk both onboarding flows start to finish: the testimonial/social-proof screens are gone, the flow is continuous with no blank or dead screen, and the progress counter is correct.

---

# ✅ TASK 9 — ADD SEGMENT UP-SELL ICONS TO THE GROWTH-TREND SCREEN

**Friday sheet item #8.**

- On the onboarding screen with the **growth-trend chart**, the row of **per-segment icons** beneath the chart (the four posture segments we up-sell: Spinal Compression, Postural Collapse, Pelvic Tilt & Back, Legs & Hamstring) is missing.
- Add the four segment icons below the chart, matching the existing onboarding visual style. These are the assets that visually communicate the four areas the app fixes.
- If the icon assets don't exist yet, this is blocked on art — flag which of the four are missing so they can be generated (transparent PNG, 512×512, consistent teal-glow style).

### ✅ Acceptance test
The growth-trend onboarding screen shows the four labeled segment icons beneath the chart, styled consistently, no missing/placeholder boxes.

---

# 📋 FINAL DEFINITION OF DONE (the whole Friday batch)

Send back **one screen recording** on the new Play Store build demonstrating, in order:
1. Teen dashboard: log one item → the "% optimized" headline moves by ~1.47% (1 point of 68), NOT 50% (Task 1).
2. Assessment entry: the new "Data Confirmed" screen animating the 6 known data points in with green checks, then CONTINUE → into the questions (Task 2A).
3. Adult Nutrition: the new protein-bar + 3 spine glasses + water bottles screen, full-screen no scroll, log to 15 pts (Task 3).
4. A habit card "How to" expanding with the correct text (Task 5).
5. Height-Loss box ticking down immediately after logging a posture workout (Task 6).
6. Habits screen full-screen, no bottom gap, bigger cards (Task 7).
7. Both onboarding flows with the fake testimonial screens gone, flow continuous (Task 8).
8. The 20-point assessment: Band A male, Band B (19yo), and the dashboard green pill staying locked until `completed: true` (Task 2).

Plus confirm in writing:
- The optimization pools used by Task 1: **teen = 68** (35+21+12), **adult = 27** (15+12), each point = 1.47% / 3.70%, single shared pool.
- That adult fluids don't double-count against old Lifestyle water code.
- The Doorway/Tech-Neck frequency decision (build to the 12-pt table unless told otherwise).

---

# ⚠️ OPEN QUESTIONS FOR THE CLIENT (answer these to remove the last guesses)

1. **Doorway Posture Reset frequency** — instruction text says 3×/day, points table says 2×/day (which gives the clean 12 cap that Task 1's 68-pool depends on). Which wins for scoring? (Default: 2× / cap 12.)
2. **Adult nutrition cap timing** — if Task 3 ships this build, adult nutrition cap = 15 → adult pool = 27. Confirm Task 3 is in this build (it should be).
3. **Height-Loss box copy** — confirm the exact label/wording you want on the attached box design ("Height Lost to Posture" vs other).
4. **Task 9 icons** — do the four segment icon assets exist, or do they need to be generated?
