# Section 5.10 — Teen nutrition dots + lifestyle dots for combined bar.


def teen_nutrition_dots_from_food_points(food_points: float) -> int:
    """1–10=1, 11–20=2, 21–30=3, 31+=4 dots."""
    fp = float(food_points or 0)
    if fp <= 0:
        return 0
    if fp <= 10:
        return 1
    if fp <= 20:
        return 2
    if fp <= 30:
        return 3
    return 4


def teen_lifestyle_dots_for_day(user, log_date) -> int:
    """
    Section 5.10 — up to four lifestyle dots (one each channel when threshold met):
    - Sleep: any logged tier 7–8h (5pts), 8–9h (8pts), or 9+h (10pts) → dot if score >= 5.
    - Sunlight: spec awards 6 pts for 10–20 min outdoor → dot when sun score >= 6
      (full tier; partial credit below 6 does not earn the dot).
    - Meditation: morning/afternoon sessions (1 pt each in spec) → dot if any med score >= 1.
    - Hydration: 2 L daily (1 pt) → dot if hydration score >= 1.
    Uses NutraEntry module name routing consistent with spec_runtime / scores_summary.
    """
    from nutration.models_log import NutraEntry

    sleep = sun = med = hyd = 0.0
    qs = NutraEntry.objects.filter(session__user=user, session__date=log_date).select_related(
        "module"
    )
    for e in qs:
        if e.food_id:
            continue
        name = str(getattr(e.module, "name", "") or "").lower()
        sc = float(e.score or 0)
        if "sleep" in name:
            sleep = max(sleep, sc)
        elif "sun" in name:
            sun = max(sun, sc)
        elif "meditat" in name:
            med = max(med, sc)
        elif "hydrat" in name or "water" in name:
            hyd = max(hyd, sc)
    dots = 0
    if sleep >= 5.0:
        dots += 1
    if sun >= 6.0:
        dots += 1
    if med >= 1.0:
        dots += 1
    if hyd >= 1.0:
        dots += 1
    return min(4, dots)


def teen_lifestyle_nutrition_combined_percent(nutrition_dots: int, lifestyle_dots: int) -> int:
    """Up to 4 nutrition + 4 lifestyle dots → 100% bar (12.5% per dot)."""
    total = min(8, int(nutrition_dots) + int(lifestyle_dots))
    return min(100, int(round(total * 12.5)))
