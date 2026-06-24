# Wednesday Frontend Handoff

This backend repo does not contain the mobile screens referenced by Wednesday Tasks 9-12. The Django API changes provide the data contract; the visual fixes below need to be applied in the mobile/frontend codebase.

## Task 9 - Teen True Optimized Report Section

- Recolor the True Optimized section blue, not yellow.
- Replace the fake "Reveal My Prediction" control with the real reveal action.
- Use a small lock icon at the end of the row instead of a large "LOCKED" tag.
- Subtitle: "Your genetic height prediction (how tall will you be?)"
- Backend fields to consume from `/api/dashboard-new`: `target_metrics.true_optimized_green_cm`, `top_graph.teen_lines_cm.true_optimized_green`, `true_optimized_locked`, and subscription/trial state.

## Task 10 - "Everything You Need" Icons

- Restore icon size, spacing, and centering inside the circular containers.
- Keep all five icons, including HGH Boost, fitting cleanly on one row.
- Avoid shrinking individual icons until they look cramped.

## Task 11 - Pre-Assessment Lander

- Fit headline, subhead, three instruction boxes, "#1 rule" callout, and CTA on one standard phone screen.
- Reduce vertical margins, internal box padding, and gaps.
- CTA must be fully visible without scrolling.

## Task 12 - Questionnaire Image Grid

- Ensure all six answer panels are visible with no bottom clipping.
- Preserve the Tuesday minimal-text/bigger-image behavior while sizing the grid to the viewport.
- Slightly reduce panel size if needed; never allow the bottom row to clip.

## Related Backend Contract

- Reassessment availability is exposed under `/api/dashboard-new` -> `scan`: `can_reassess`, `workouts_logged_today`, and `reassess_message`.
- If `can_reassess` is false, disable the Re-Assess control and show `reassess_message`.
- Exercise cards should use backend `category_label`; labels now match the Wednesday pillar names.
