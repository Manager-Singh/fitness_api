"""Apply EXERCISE_SPEC_SHEET.md copy to Exercise rows (description, instructions, safety)."""
from __future__ import annotations

from workouts.exercise_assignment_data import REAL_CATALOG_SPEC_KEYS, spec_key_for_name
from workouts.exercise_spec_sheet_data import EXERCISE_SPEC_SHEET_ROWS


def _method_title(name: str, dosage: str) -> str:
    return f"{name.upper()} — {dosage}"


def exercise_fields_from_spec_row(row: dict) -> dict:
    """Build Exercise model fields from a spec sheet row."""
    name = row["name"]
    dosage = row["dosage"]
    steps = list(row["steps"])
    raw_methods = row.get("methods")
    if isinstance(raw_methods, list) and raw_methods:
        instruction_methods = [
            {
                "title": str(m.get("title") or "").strip(),
                "steps": [str(s).strip() for s in (m.get("steps") or []) if str(s).strip()],
            }
            for m in raw_methods
            if isinstance(m, dict)
        ]
    else:
        instruction_methods = [
            {
                "title": _method_title(name, dosage),
                "steps": steps,
            }
        ]
    return {
        "description": row["description"],
        "instruction_content": "",
        "instruction_steps": steps,
        "instruction_methods": instruction_methods,
        "safety_note": row.get("safety_note") or "",
    }


def run_sync(*, stdout=None, exercise_model=None, dry_run: bool = False) -> dict:
    if exercise_model is None:
        from workouts.models import Exercise as exercise_model

    Exercise = exercise_model
    updated = 0
    unmatched_db: list[str] = []
    missing_spec = set(REAL_CATALOG_SPEC_KEYS) - set(EXERCISE_SPEC_SHEET_ROWS)

    if missing_spec and stdout:
        stdout.write(f"Warning: spec sheet missing keys: {sorted(missing_spec)}")

    for ex in Exercise.objects.all():
        key = spec_key_for_name(ex.name)
        if not key or key not in EXERCISE_SPEC_SHEET_ROWS:
            if key in REAL_CATALOG_SPEC_KEYS:
                unmatched_db.append(ex.name)
            continue

        fields = exercise_fields_from_spec_row(EXERCISE_SPEC_SHEET_ROWS[key])
        if dry_run:
            updated += 1
            continue

        for field, value in fields.items():
            setattr(ex, field, value)
        ex.save(update_fields=list(fields.keys()))
        updated += 1

    result = {
        "updated": updated,
        "unmatched_db": unmatched_db,
        "missing_spec_keys": sorted(missing_spec),
    }

    if stdout:
        stdout.write(f"Updated instruction copy on {updated} exercise(s).")
        if unmatched_db:
            stdout.write(f"Catalog exercises not updated: {unmatched_db}")
        if dry_run:
            stdout.write("Dry run — no changes written.")

    return result
