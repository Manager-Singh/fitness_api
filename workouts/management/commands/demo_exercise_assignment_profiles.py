from django.core.management.base import BaseCommand

from utils.exercise_assignment import (
    ranked_segments_from_losses,
    select_adult_recommended_beast,
    select_teen_recommended_beast,
)
from workouts.exercise_assignment_data import TEEN_CORE_6_NAMES
from workouts.models import Exercise


PROFILES = [
    {
        "label": "Adult A — balanced low",
        "age": 25,
        "losses": {"spinal": 0.1, "collapse": 0.1, "pelvic": 0.1, "legs": 0.1},
    },
    {
        "label": "Adult B — collapse worst",
        "age": 28,
        "losses": {"spinal": 0.2, "collapse": 1.5, "pelvic": 0.3, "legs": 0.1},
    },
    {
        "label": "Adult C — pelvic + legs",
        "age": 35,
        "losses": {"spinal": 0.2, "collapse": 0.4, "pelvic": 1.2, "legs": 0.9},
    },
    {
        "label": "Teen D — age 14 collapse",
        "age": 14,
        "losses": {"spinal": 0.2, "collapse": 1.5, "pelvic": 0.3, "legs": 0.1},
    },
    {
        "label": "Teen E — age 19 same losses",
        "age": 19,
        "losses": {"spinal": 0.2, "collapse": 1.5, "pelvic": 0.3, "legs": 0.1},
    },
]


class Command(BaseCommand):
    help = "Print Recommended + Beast picks for 5 spec test profiles (in-memory scorer)."

    def handle(self, *args, **options):
        from utils.exercise_assignment import adult_scoring_pool_queryset, teen_scoring_pool_queryset

        adult_pool = list(adult_scoring_pool_queryset(Exercise))
        teen_pool = list(teen_scoring_pool_queryset(Exercise))
        if not adult_pool:
            self.stderr.write("No backfilled adult exercises — run migrations first.")
            return

        core_names = TEEN_CORE_6_NAMES
        core_ex = [Exercise.objects.filter(name__iexact=n).first() for n in core_names]
        core_ex = [e for e in core_ex if e]

        for p in PROFILES:
            losses = p["losses"]
            ranked = ranked_segments_from_losses(losses)
            self.stdout.write(f"\n=== {p['label']} (age {p['age']}) ===")
            self.stdout.write(f"Ranked segments: {ranked}")
            if p["age"] >= 21:
                rec, beast = select_adult_recommended_beast(adult_pool, losses, core_ex[:1])
                self.stdout.write(f"Core 6: (from AgeBracket variant in app — not simulated here)")
            else:
                rec, beast = select_teen_recommended_beast(teen_pool, losses, p["age"], core_ex[:4])
                self.stdout.write(f"Teen fixed core: {', '.join(core_names)}")
            self.stdout.write(f"Recommended: {', '.join(e.name for e in rec)}")
            self.stdout.write(f"Beast Mode:  {', '.join(e.name for e in beast)}")
            teen_in = [e.name for e in rec + beast if e.teen_only]
            if p["age"] >= 21 and teen_in:
                self.stdout.write(self.style.ERROR(f"TC-N FAIL teen exercises: {teen_in}"))
