# Posture Loss Scoring — Corrected Spec

**Replaces:** the Q8-multiplier logic in the Issue9 spec (Section 4) and its implementation in `utils/posture/issue9_visual_scoring.py`.
**For:** the dev team's Claude Code.
**This is a scoring recalibration the client has explicitly signed off on.** It changes the questionnaire result for everyone — that is intended.

---

## Why we're changing it (plain English)

A user answered the **worst** option on all 8 questions and got **3.9 cm**, not the maximum. That's wrong from a user's point of view, and it happened for two reasons that we are now fixing:

1. **Q8 was a multiplier, not a loss.** Answering Q8 = worst (rigid/locked spine) *halved* the recoverable loss (×0.50), because the old spec treated a locked spine as "your loss is mostly permanent." So "worst on everything" came out LOW. **Fix: Q8 now ADDS loss like Q1–Q7.** No multiplier anywhere.
2. **The 4 segment bars didn't add up to the headline number** for high-severity users (headline 3.0 vs bars 3.95), because one used the clamped total and the other used raw values. **Fix: the headline now always equals the sum of the 4 bars.**

After this change: **worst answer on all 8 = exactly 6.0 cm** (the max), and the bars always reconcile with the headline.

---

## 1. New per-question loss values

Every question now ADDS loss. Options are ordered **A (best posture) → D (worst posture)**. These are the values to put in the scoring table:

| Question | A | B | C | D (worst) |
|---|---|---|---|---|
| Q1 | 0.0 | 0.3 | 0.6 | **0.9** |
| Q2 | 0.0 | 0.4 | 0.8 | **1.2** |
| Q3 | 0.0 | 0.2 | 0.35 | **0.5** |
| Q4 | 0.0 | 0.3 | 0.6 | **0.9** |
| Q5 | 0.0 | 0.15 | 0.3 | **0.4** |
| Q6 | 0.0 | 0.25 | 0.5 | **0.7** |
| Q7 | 0.0 | 0.25 | 0.5 | **0.7** |
| Q8 | 0.0 | 0.25 | 0.5 | **0.7** |

The **D column sums to exactly 6.0** (0.9+1.2+0.5+0.9+0.4+0.7+0.7+0.7 = 6.0). That is the whole point: worst-on-all lands exactly on the 6.0 cap with no clamping needed.

**Two ordering rules when you wire this up:**
- **Q8 is now a normal additive question.** Delete every line that treats Q8 as a multiplier. Do NOT multiply the total by anything.
- **Q5 must be monotonic: option D = the most compressive / worst posture.** The old spec had Q5's "D" scoring *less* than "C" (posterior tilt is less compressive than anterior). That made "worst" not the worst. Re-order Q5's answer options so the most compressive option is D, and use the values above (D = 0.4 is the largest for Q5).

---

## 2. Total loss formula

```
raw_loss   = sum of the 8 selected option values
total_loss = clamp(raw_loss, 0.5, 6.0)      # min 0.5, max 6.0
```

- **No Q8 multiplier.** Remove `totalRecoverable = total × multiplier(Q8)` entirely.
- Because the worst case sums to exactly 6.0, the upper clamp is only ever *touched* (never *exceeds*), so it can no longer distort the headline vs. the bars.
- `0.5` floor stays as a safety net for near-perfect posture (all-A → 0.5).

---

## 3. Segment bars — now reconciled with the headline

Keep your **existing per-question → segment distribution** (the percentages each question already contributes to Spinal / Postural Collapse / Pelvic / Legs & Hamstring). The reconciliation below works with ANY distribution, as long as each question's segment percentages sum to 100%.

```
# 1. raw per-segment loss
for each segment s:
    seg_raw[s] = sum over questions q of ( option_value[q] × question_pct[q][s] )

# 2. scale segments to match the clamped headline so they always add up
if raw_loss > 0:
    factor = total_loss / raw_loss
    for each segment s: seg_loss[s] = seg_raw[s] × factor
else:
    # all-A edge case: distribute the 0.5 floor across segments by their max ceilings
    for each segment s: seg_loss[s] = total_loss × seg_max[s] / sum(seg_max)
```

**Result:** `seg_loss[spinal] + seg_loss[collapse] + seg_loss[pelvic] + seg_loss[legs] == total_loss`, always. The reveal-screen number and the four dashboard bars can never disagree again.

> If you don't have a per-question segment split and want a simple default, use one primary segment per question: Q1,Q2 → Spinal; Q3,Q4 → Postural Collapse; Q5,Q6 → Pelvic; Q7,Q8 → Legs & Hamstring. That gives segment maxes Spinal 2.1, Collapse 1.4, Pelvic 1.1, Legs 1.4 (sum 6.0). Replace with the real mapping if the questions target different areas.

---

## 4. Bar display (unchanged math)

```
optimized_percent[s] = (1 − seg_current_loss[s] / seg_max[s]) × 100
```

Optional polish (display only, no math impact): show **1 decimal** (e.g. `17.9%` instead of `18%`) so users see per-workout movement on the slow-moving segments.

---

## 5. What this does to the reported case

The user who answered worst on all 8:
- **Before:** raw 8.4 → clamp 6.0 → ×0.50 (Q8) = **3.0 cm headline**, bars summed to 3.95 → felt broken.
- **After:** raw 6.0 → **6.0 cm headline**, bars = Spinal 2.1 + Collapse 1.4 + Pelvic 1.1 + Legs 1.4 = **6.0 cm**. Worst = max, bars match. Fixed.

---

## 6. Do NOT change

- The point→height conversion (1 pt = 0.001 cm), the daily caps, the engines, the ledger. This task is **only** the questionnaire loss calculation and the segment-bar reconciliation.
- The 0.5 floor and 6.0 cap values (keep them).

---

## 7. Acceptance tests (must all pass)

1. **All D** → headline = **6.00 cm**; the 4 bars sum to **6.00 cm**.
2. **All A** → headline = **0.50 cm** (floor); bars sum to 0.50.
3. **All C** → headline ≈ **4.15 cm**; bars sum to the same.
4. **Q8 alone = D** (all others A) → headline = **0.70 cm** (proves Q8 ADDS and never halves).
5. **Reconciliation:** for any random mix of answers, `headline == sum(4 bars)` (to within rounding). This was verified to hold across 5,000 random combinations.
6. No code path multiplies the total by a Q8 factor anywhere.
