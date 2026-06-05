# DIRECTIVE: Posture Bars Must Move On Every Logged Workout

**Status: the current behavior is NOT accepted.**

The explanation that "the recovery is happening but it's under 1% so the bar can't show it" is rejected. If a user completes a workout, the posture bars must visibly change. A user logging effort and seeing the numbers sit frozen looks broken — and it doesn't matter that the value is technically stored in the background. **What is tracked must be shown.**

---

## The requirement (non-negotiable)

> **Every logged workout — and every point added — must produce a visible change in the posture recovery bars, immediately, at the moment it is logged.**

No batching to end-of-day. No waiting for a screen refresh or app restart. Log → bars move, on the spot.

---

## Why the current setup fails (using your own numbers)

You said a full day is 86 points = 0.086 cm, Legs gets 10%, Legs max = 1.0 cm. Here's what that means per workout on the Legs bar:

| Action | Legs bar moves | Whole-number display shows |
|---|---|---|
| 1 point | +0.01% | nothing (0%) |
| ~half a workout | +0.05% | nothing (0%) |
| one full workout | +0.09% | nothing (0%) |
| a full day (10 workouts) | +0.86% | rounds to 1% |

So with whole-number display, a user can do **all ten workouts and watch the Legs bar not move at all**. The recovery is real; you are **rounding it away before you draw it**. That is the bug.

---

## The fix (two parts, both required)

### 1. Display the bars with decimals
Show **at least 2 decimal places** on every posture bar (e.g. `18.00%` → `18.09%` → `18.18%`…). With 2 decimals, every action in the table above becomes visible — even a single point moves the bar by `+0.01%`. This is a display change only; it does not touch the recovery math, the caps, or the ledger.

### 2. Update the bars live on every log event
The bars must recompute and re-render the instant a workout is logged or a point is added — not on a timer, not on next app open. Wire the bar widget to the same event that records the workout so the UI reflects the new cumulative recovery immediately.

---

## Acceptance tests (must all pass)

1. Log **one** workout → at least one posture bar's displayed number changes on the spot (e.g. Legs `18.00%` → `18.09%`).
2. Log workouts one at a time → the bars tick up **every single time**, never frozen.
3. After all 10 workouts in a day → each bar has visibly increased from where it started that day.
4. The bar numbers always reconcile with the stored recovery (display ≠ a separate fake value).
5. No rounding step anywhere hides a real, non-zero recovery from the user.

---

## Note on scope

This does **not** change the recovery rate, the point→cm conversion, the daily caps, or the segment split — those stay as signed off. This is purely: **show the movement that is already happening, with enough precision, the moment it happens.** If, separately, you want each workout to move the bars by a *larger* amount, that's a different decision about the recovery rate — raise it explicitly; it is not part of this fix.
