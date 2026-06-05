# THE HEIGHT APP — Fix Checklist (Exercise Player / Rep Counter)

**For:** the dev team's Claude Code (Sonnet).
**How to use:** Work through these **in order, one number at a time.** Check each off only when its "Done when" test passes. Items 1 and 2 fix ~80% of what looks broken in the screenshots.

---

## Read this first — the one idea that explains most of the bugs

Every exercise is **either a REP exercise or a HOLD exercise**:

- **HOLD** = show a **countdown timer** (e.g. 30 → 0 seconds). ✅ *Cobra Stretch already does this correctly.*
- **REP** = show a counter that **counts UP from 0 to the target** (e.g. 0 → 20), advancing one rep automatically every `seconds_per_rep` seconds. ❌ *This is broken right now.*

**The core bug:** Pelvic Tilts is a REP exercise (target = 20 reps). The app is showing it as a **20-second countdown timer** ("00:20"). It is mistaking the rep target "20" for "20 seconds." See screenshots 4 and 5.

Here is the correct data straight from the catalog (`EXERCISE_CATALOG_DATABASE_EXPORT.csv`), so you can verify against it:

| Exercise | What the screen must show | How the app should detect it |
|---|---|---|
| Pelvic Tilts | REP counter 0 → 20, +1 every **3.4s** | `seconds_per_rep` = 3.4, no "(timer)" in dosage |
| Glute Bridges | REP counter 0 → 20, +1 every **4.0s** | `seconds_per_rep` = 4.0, no "(timer)" in dosage |
| Cobra Stretch | HOLD countdown **30 → 0** | dosage contains "(timer)" |

**Detection rule (use everywhere):**
```
if primary_timer_dosage contains "(timer)"   → HOLD mode (countdown)
else                                         → REP mode (count up 0→target, step every seconds_per_rep)
```

---

## 1. Regenerate every existing user's routine  ← do this FIRST

**What's wrong:** Existing users still have a saved routine built from the OLD catalog. That's why Glute Bridges shows the new "20 Reps" badge but the old "3 sets x 15 reps" text underneath (screenshot 3, circled) — the badge reads the live catalog, the text reads the stale saved routine. New sign-ups are fine; existing users are stuck on old data.

**Why it matters:** Until routines are regenerated, the player loads stale exercise data with no `seconds_per_rep` and no rep/hold flag, so it falls back to timer mode. This is the hidden reason Pelvic Tilts shows a timer.

**Fix (pick one):**
- **Quick:** run a one-time job that regenerates all active user routines from the current `Exercise` table (you already have `import_exercise_catalog_from_csv` and the regeneration path — trigger it for all users).
- **Robust (better long-term):** make the routine serializer read `sets`, `target`, `primary_timer_dosage`, and `seconds_per_rep` **live from the linked `Exercise` row at serialization time**, instead of from a frozen snapshot. Then catalog edits always show up with no regeneration needed.

**Done when:** A pre-existing test user opens Routine and every card shows the new numbers (Glute Bridges = "2 sets x 20 reps"). No "3 sets x 15 reps" anywhere.

---

## 2. Make REP exercises show the rep counter (not a timer)

**What's wrong:** Pelvic Tilts shows "00:20" (a 20-second clock) and counts down. It must show a counter going **0 → 20**, one rep about every 3.4 seconds. Screenshots 4 and 5.

**Where to look:** `exercise_player_dosage.dart` (parser), `ExercisesController._mapExerciseData` (field mapping), `ExerciseDialog` (the player UI), and `PostureExercisePhase`.

**Fix:**
1. Confirm `_mapExerciseData` actually copies `primary_timer_dosage` and `seconds_per_rep` onto the routine item the player uses. If those fields are null at the player, mode detection can't work (this links back to item 1).
2. Apply the detection rule from the top of this doc. REP exercises must enter the auto-paced counter phase; only "(timer)" exercises get the countdown.
3. Safety fallback: if an exercise is NOT a timer but `seconds_per_rep` is missing, default the interval to **3.5s** — never fall back to a countdown timer for a rep exercise.

**Done when:** Pelvic Tilts shows a counter climbing 0 → 20 (≈ every 3.4s), Glute Bridges 0 → 20 (≈ every 4.0s), and Cobra Stretch still counts **down** from 30. No rep exercise ever shows a clock.

---

## 3. Make each exercise card show ONE consistent dosage

**What's wrong:** On the Glute Bridges card the badge says "20 Reps" but the line under the title says "3 sets x 15 reps" (screenshot 3). They come from two different data sources.

**Fix:** Make the badge and the description text read from the **same** source (the regenerated routine item, or the live catalog). After item 1, both should say "2 sets x 20 reps".

**Done when:** Badge and description agree on every card.

---

## 4. Fix the caption text on rep exercises

**What's wrong:** The player still says *"The GIF shows the motion — follow the time and sets shown below, not the GIF's pace."* (screenshot 5). Rep exercises have no "time" to follow.

**Fix:** For REP exercises, show something like: *"Follow the motion — each tick is one rep, paced for you."* Keep the time-based wording only for HOLD exercises (or use the rep-friendly wording for both). This is the `Mode-specific helper text` in `ExerciseDialog`.

**Done when:** Pelvic Tilts no longer says "follow the time."

---

## 5. Fix the "Exercise Complete" screen

**What's wrong:** On completion, Pelvic Tilts still shows "00:20" (leftover timer) AND the green "Log Exercise" + "Redo" buttons sit on top of the instruction text behind them — it looks broken (screenshot 4).

**Fix:**
- Replace the leftover timer with the final rep count or a checkmark.
- Give the completion overlay a **solid background panel** so the buttons don't overlap the step text behind them.
- Keep the "Log Exercise" action firing the **same** logging event as before — do not change logging.

**Done when:** The complete screen is clean: no stray timer, no overlapping text, logging still works.

---

## 6. Remove the empty black corners at the top of the player

**What's wrong:** Empty black rectangles in the top-left and top-right of the exercise screen (screenshot 5, circled). The clip/media area isn't filling the space.

**Fix:** Make the media (GIF/video) container fill the available width, or center it on a matching background, so there are no stray black gaps. This is a sizing / aspect-ratio issue on the media widget.

**Done when:** No empty black boxes around the clip on any screen size.

---

## 7. Verify the Lifestyle tab is hidden for ADULT users

**What to check:** The Wellness screen shows the **Lifestyle** tab (screenshot 2). Adults should see **only Nutrition + Habits**; only teens should see Lifestyle.

**Why:** Lifestyle factors feed the teen-only growth engine. Adults don't use that engine, so the tab shouldn't appear for them.

**Fix/verify:** If the screenshot account is a **teen**, this is correct — no change. If it's an **adult**, hide the Lifestyle tab (the report says this was done — confirm it actually works on a real adult account, including the deep-link index mapping Habits → UI index 1).

**Done when:** Adult account = Nutrition + Habits only. Teen account = all three tabs.

---

## 8. Sanity-check the daily height-gain math

**What to check:** Dashboard shows Daily Points = 86 and Daily Gains = +0.086 cm (screenshot 1). That equals 86 × 0.001, which is the posture formula (**height gain = eligible points × 0.001 cm**). That's internally consistent, so this is a verification, not a confirmed bug.

**Confirm only this:** the points being multiplied are the ones that *should* raise an adult's height.
- Adults: **posture + nutrition** points count toward height. **Lifestyle should NOT** (adults don't have that engine).
- Make sure no teen-only / lifestyle points are leaking into an adult's daily gain.

**Done when:** For an adult, daily gain = (posture + nutrition points) × 0.001, nothing else mixed in.

---

## 9. (Polish) Un-truncate the posture labels

The Posture Optimization labels are cut off: "Spinal Com…", "Postural C…", "Legs & Ha…" (screenshot 1). Widen the label column or use short names: **Spinal, Posture, Pelvic, Legs**.

---

## 10. (Polish) Check the double logo on the splash screen

The first splash screen shows the logo twice — a cyan wordmark and the metallic wordmark (screenshot 6, left). Confirm that's intentional; if not, show one.

---

## DO NOT touch these — they are correct and were built right

- **Workout logging, `reps_done`, points calculation, the height ledger.** Leave them exactly as-is. This whole job is a **display/player-layer fix** — if a change of yours alters logging, points, or the ledger, you've gone too far; back it out.
- **The catalog values** (2 sets, the rep counts, `seconds_per_rep`). They are final and correct. Don't "fix" them.
- **Hold exercises** (Cobra, Plank, Hang, etc.) already work — just keep their countdown and the 3-2-1 lead-in.

---

## Fast self-test before you say it's done

1. Open Routine as a **pre-existing** user → all cards show 2 sets + new reps (item 1, 3).
2. Start **Pelvic Tilts** → 3-2-1 → counter climbs 0→20, no clock (item 2, 4).
3. Start **Cobra Stretch** → 3-2-1 → countdown 30→0 (item 2 didn't break holds).
4. Finish an exercise → clean complete screen, logging works (item 5).
5. Look at the player edges → no black corner gaps (item 6).
6. Open Wellness on an **adult** account → no Lifestyle tab (item 7).
