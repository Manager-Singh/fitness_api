# Tuesday Work Order QA Signoff

Date: Jun 23, 2026

## Backend Status

Implemented and verified:

- Strict nutrition/habit posture recovery now credits only pillars primary-trained by completed posture exercises.
- Zero-workout days keep visible nutrition/habit points but produce zero posture recovery from those points.
- Adult Core 6 generation now uses the rebalanced spec lists instead of stale DB variant core order.
- Teen Core 6 includes HGH + one of each posture pillar + dynamic worst-pillar extra.
- Teen/adult extra slots use net-gap largest-remainder allocation.
- Adult results payload includes `current_height_cm`, `total_recoverable_loss_cm`, and `target_height_cm`.
- Questionnaire edge cases return clean `400` responses for invalid profile data, invalid completed answers, and missing teen parent heights.
- Existing users can receive a full refreshed Core + Recommended + Beast plan through `regenerate_posture_routines`.

## Commands Run

```bash
python manage.py test utils.tests.test_posture_targeting_scoring utils.tests.test_posture_targeting_allocation users.tests.test_targeted_engine1_recovery users.tests.test_daily_points_breakdown workouts.tests.test_exercise_assignment_spec posture_questions.tests.test_questionnaire_submit --verbosity 1 --keepdb
```

Result: 51 tests passed.

```bash
python manage.py regenerate_posture_routines --dry-run --user 0
```

Result: command completed successfully with zero processed users for the smoke-check filter.

## Deployment Notes

Run in order:

1. Apply migrations already pending for the branch.
2. Sync exercise assignment data if the environment has stale variant prescriptions:

```bash
python manage.py sync_routine_variant_prescriptions --backfill-first
```

3. Regenerate active posture routines after deploy:

```bash
python manage.py regenerate_posture_routines
```

4. Restart app workers.
5. Recheck staging APIs: `/api/update-posture-questions`, `/api/my-routine`, `/api/dashboard-new`, workout logging, and nutrition logging.

## Frontend/Mobile Status

Mobile-only Tuesday items are documented in `docs/FRONTEND_POSTURE_TARGETING_IMPLEMENTATION_GUIDE.md` section 13:

- Adult nutrition copy.
- Adult/teen paywall trust row and fake member-count removal.
- Adult optimized-height display binding.
- Pre-assessment lander.
- Minimal questionnaire pages.
- Teen HGH icon, feature-card images, and True Optimized reveal button.

These require mobile repo implementation and device QA.
