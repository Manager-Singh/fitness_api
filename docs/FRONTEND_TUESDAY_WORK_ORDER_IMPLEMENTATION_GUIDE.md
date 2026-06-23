# Frontend Tuesday Work Order Implementation Guide

Audience: Mobile / Flutter team  
Date: Jun 23, 2026  
Source: `TUESDAY_WORK_ORDER (1).md`  
Backend status: Backend fixes and regression tests are implemented in this repo.

This guide is frontend-ready. Implement the UI/copy changes below in the mobile app, and use the backend fields exactly as described. Do not recompute posture or height math on the client.

## 1. API Fields Frontend Must Use

### Questionnaire Submit

Endpoint:

```http
POST /api/update-posture-questions
Authorization: Bearer <access_token>
Content-Type: application/json
```

Required frontend behavior:

- Submit all 8 posture answers.
- Q1-Q6 submit answer letters `A` through `F`.
- Q7-Q8 display numbered choices `1` through `6`, but submit mapped letters:

```text
1 -> A
2 -> B
3 -> C
4 -> D
5 -> E
6 -> F
```

Fields to read from response:

```text
user.section3_contract.mode
user.section3_contract.total_recoverable_loss_cm
user.section3_contract.target_height_cm
user.section3_contract.optimization_breakdown
user.onboarding_results.current_height_cm
user.onboarding_results.total_posture_loss_cm
```

Rules:

- `mode` must be `posture_targeting_v1`.
- Use `target_height_cm` for optimized height when present.
- If `target_height_cm` is missing, compute display fallback as `current_height_cm + total_recoverable_loss_cm`.
- Never show `You should be 0.0 cm` when current height and recoverable loss exist.

### Routine

Endpoint:

```http
GET /api/my-routine
```

Render exactly what backend returns:

- Core
- Recommended
- Beast

Do not hardcode Core 6, Recommended, or Beast pools in the app. Backend assignment now targets worst posture pillars.

### Dashboard

Endpoint:

```http
GET /api/dashboard-new
```

Frontend display rules:

- Show visible nutrition/habit points as returned by dashboard.
- Do not assume food/habit points always move posture bars.
- Posture bars move only when backend returns updated posture state.
- Teen HGH affects Genetic+ / Engine 2, not posture bars.

## 2. Task 3 - Adult Nutrition Copy

Replace adult nutrition text with the approved copy below.

### Protein

Header:

```text
PROTEIN
```

Rate label:

```text
+1 pt per 10g
```

Body:

```text
Rebuilds the back, core, and glute muscles that hold your spine tall. Aim for 90g a day.
```

Keep existing quantity buttons:

```text
+10g
+20g
+30g
+Add
```

### Basic Hydration

Header:

```text
BASIC HYDRATION
```

Rate label:

```text
+1 pt per 500ml
```

Body:

```text
Everyday hydration keeps your discs full and your spine working at full height. Staying hydrated through the day is one of the simplest ways to support your height.
```

Examples/chips:

```text
Water
Milk
Tea
Coffee
Juice
Carbonated
```

### Premium Hydration

Header:

```text
PREMIUM HYDRATION
```

Rate label:

```text
+2 pts per 500ml
```

Body:

```text
The most powerful drinks for spinal health. Your discs are nearly 80% water - these spine-friendly drinks deliver the deepest hydration and nutrients for disc lubrication and nourishment. Worth twice the points of basic drinks.
```

Examples/chips:

```text
Bone Broth
Watermelon
Coconut
Cucumber
Celery
Beet
```

Shared pool line between Basic and Premium:

```text
Fluids X / 6 pts - Premium + Basic drinks share one pool
```

Acceptance:

- Remove all `drink 3 a day` copy.
- Basic and Premium should complement each other.
- Premium explains why it is worth 2x points.

## 3. Task 4 And 12 - Paywall Copy

Applies to both adult and teen paywalls.

Remove:

```text
12,000+ members
join 12,000 teens
```

Do not show any invented member count anywhere.

Trust row:

```text
Secure payment
30-day money-back guarantee
No hidden fees
```

Risk-free line near CTA:

```text
Try it risk-free - if you don't see results, get a full refund within 30 days.
```

Teen shorter alternate if space is tight:

```text
Try it risk-free - full refund within 30 days if you don't see results.
```

Acceptance:

- No fake member numbers remain on adult or teen paywalls.
- Trust row appears near purchase CTA.
- Do not ship guarantee copy unless refund policy page supports it.

## 4. Task 5 - Adult Results Page 0.0 cm Fix

Bug to fix:

```text
You should be 0.0 cm. You are currently 160.0 cm.
```

Display logic:

```text
recoverable_cm = total_recoverable_loss_cm
current_height = current_height_cm
optimized_height = target_height_cm or current_height_cm + total_recoverable_loss_cm
```

Primary result number:

```text
+{recoverable_cm} cm
```

Body copy:

```text
You're currently {current_height} cm. Your optimized height is {optimized_height} cm - most of this gap is recoverable, locked away by spinal compression, muscle imbalance, and years of bad posture.
```

Example:

```text
current_height_cm = 160.0
total_recoverable_loss_cm = 4.1
target_height_cm = 164.1
```

Expected display:

```text
+4.1 cm
You're currently 160.0 cm. Your optimized height is 164.1 cm - most of this gap is recoverable, locked away by spinal compression, muscle imbalance, and years of bad posture.
```

Acceptance:

- Never display optimized/should-be height as `0.0 cm` when data exists.
- If values are still loading, hide the sentence until values are ready.
- Keep existing good copy about posture stealing height and the plan targeting worst areas.

## 5. Task 6 - Pre-Assessment Lander

Add this screen before Q1.

Flow:

```text
Assessment entry -> Pre-assessment lander -> START MY ASSESSMENT -> Q1
```

Top eyebrow:

```text
FREE ASSESSMENT
```

Headline:

```text
Your Free Height Loss Assessment
```

Subhead:

```text
Find out exactly how much height your posture has stolen - in 2 minutes.
```

Intro:

```text
8 quick questions. To get your most accurate result, set yourself up right:
```

Three icon cards:

```text
Take a photo or use a mirror
Best results: a side-on photo of yourself, or stand in front of a mirror.
```

```text
Stand totally relaxed
Don't pose, don't straighten up. We need your natural, everyday posture.
```

```text
Or have someone check you
A friend looking at you from the side works just as well.
```

Key callout:

```text
The #1 rule: don't correct your posture. Your relaxed, natural stance is your true starting point - that's what we measure.
```

CTA:

```text
START MY ASSESSMENT ->
```

Trust line:

```text
Free - No account needed - Takes 2 minutes
```

Design:

- Dark app background: `#0A0A0A`.
- Teal accent: `#00BFB3`.
- Cards: `#141416` fill, subtle teal border, rounded corners.
- Use large icons, 64px or larger where possible.
- Keep page skimmable in 5 seconds.

Acceptance:

- Lander appears once before the quiz.
- Full measurement instructions live here, not on each question page.

## 6. Task 7 - Questionnaire Page UI Fix

Remove the long instruction block from Q1-Q8 pages.

Each question page should show only:

- Progress bar and `Q n of 8`.
- Question prompt.
- One short reminder line.
- Choices.

Q1-Q6 layout:

- 2 columns x 3 rows.
- Image panels should fill most of the available screen.
- Each image card is tappable.
- Selected state uses teal glow/border.

Q7-Q8 layout:

- Six stacked numbered cards.
- Left badge: number `1` through `6`.
- Right side: option text.
- Submit mapped `A` through `F` value.

Per-question prompts:

```text
Q1: When you stand relaxed, how far forward does your head sit?
Reminder: Relaxed, looking straight ahead - pick the closest.

Q2: Looking from the side, how rounded is your upper back?
Reminder: Stand relaxed - don't straighten. Pick the closest.

Q3: Let your arms hang dead. Which way do your thumbs point?
Reminder: Arms totally limp - don't adjust. Pick the closest.

Q4: Back to a wall - how do your head and upper back meet it?
Reminder: Relax against the wall - don't push back. Pick the closest.

Q5: From the side, how is your pelvis tilted?
Reminder: Stand natural - don't tuck or arch. Pick the closest.

Q6: Standing relaxed, how bent are your knees?
Reminder: Stand how you always do. Pick the closest.

Q7: Through a normal day, what do you notice about your spine?
Reminder: Think morning-to-night. Pick what matches.

Q8: In a mirror, how level are your shoulders and hips?
Reminder: Stand natural, feet together. Pick the closest.
```

Acceptance:

- Images occupy the majority of Q1-Q6 screens.
- Only prompt plus one reminder line appears above choices.
- Full 3-method instructions appear only on the pre-assessment lander.

## 7. Task 8 - Teen Report HGH Boost Icon

Keep existing 4 teen pillar icons blue. Do not restyle them to teal.

Add fifth matching blue icon:

```text
HGH Boost
```

Placement:

```text
Spinal Compression -> Postural Collapse -> Pelvic Tilt & Back -> Legs & Hamstring -> HGH Boost
```

Use the provided HGH icon asset when available.

Acceptance:

- 5 icons fit in one row or an approved responsive layout.
- Styling matches the existing blue teen report icons.

## 8. Task 9 - Teen Everything You Need Images

Add images to feature cards without replacing existing text.

Image mapping:

```text
Posture Correction -> posture3
Daily Growth Routine -> growth3
Sleep & HGH Coaching -> sleep3
Nutrition for Growth -> nutrition3
HGH feature / HGH Boost -> hgh3
Tracking / progress -> track3
```

Acceptance:

- Every mapped card gets the correct image.
- Existing blue headings and grey descriptions remain.
- Keep the existing CTA at the bottom.

## 9. Task 10 - Teen True Optimized Height Button

Remove broken placeholder cluster:

```text
? ? ?
triple-checkmark cluster
```

Replace `LOCKED` with a friendly reveal button.

Button:

```text
Reveal My Prediction
```

Include lock icon inside the button.

Subtitle:

```text
Your genetic height prediction
(how tall will you be?)
```

Acceptance:

- Button uses existing True Optimized card accent palette.
- No broken placeholder cluster remains.
- `LOCKED` label is replaced by the reveal CTA.

## 10. Frontend QA Checklist

Adult:

- Nutrition copy matches this guide exactly.
- No `drink 3 a day` text remains.
- Paywall has no fake member count.
- Results page shows `optimized_height = current + recoverable`.
- Results page never shows `You should be 0.0 cm` when backend values exist.
- Adult routine renders backend Core, Recommended, and Beast exactly as returned.

Teen:

- Teen paywall has no `join 12,000 teens`.
- Teen report shows 5 icons including `HGH Boost`.
- Teen feature cards show `posture3`, `growth3`, `sleep3`, `nutrition3`, `hgh3`, and `track3`.
- True Optimized card shows `Reveal My Prediction`.
- Teen HGH logging shows Genetic+ behavior, not posture bar movement unless posture exercises are also completed.

Assessment:

- Pre-assessment lander appears before Q1.
- Q1-Q6 images dominate the screen.
- Q7-Q8 show six numbered cards.
- Q7-Q8 submit `A` through `F`, not raw numbers.
- All 8 answers submit successfully and response has `section3_contract.mode = posture_targeting_v1`.

## 11. Do Not Implement On Frontend

- Do not calculate posture centimeters from answers.
- Do not split workout gains across all 4 pillars locally.
- Do not hardcode exercise assignment logic.
- Do not cap teen HGH points on the client.
- Do not show fake member counts.
- Do not render guarantee copy unless policy supports it.

