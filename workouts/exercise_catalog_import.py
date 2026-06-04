"""Apply client exercise catalog CSV rows to Exercise + VariantExercise."""
from __future__ import annotations

import csv
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from workouts.exercise_timer_display import parse_primary_timer_dosage
from workouts.models import AgeBracket, Exercise, RoutineTemplate, RoutineVariant, Unit, VariantExercise

logger = logging.getLogger(__name__)

VARIANT_PRESCRIPTION_SEP = " ;; "


def ensure_seconds_per_rep_column() -> bool:
    """Add ``seconds_per_rep`` when DB was migrated outside repo migration chain."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'workouts_exercise'
              AND COLUMN_NAME = 'seconds_per_rep'
            """
        )
        if cursor.fetchone()[0]:
            return False
        cursor.execute(
            "ALTER TABLE workouts_exercise "
            "ADD COLUMN seconds_per_rep DECIMAL(4,2) NULL"
        )
        logger.info("Added workouts_exercise.seconds_per_rep column")
        return True


def _csv_bool(val: str) -> bool:
    return str(val or "").strip().lower() in ("true", "1", "yes")


def _optional_int(val: str) -> int | None:
    s = str(val or "").strip()
    if not s:
        return None
    return int(float(s))


def _optional_decimal(val: str) -> Decimal | None:
    s = str(val or "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_instruction_methods(raw: str) -> list:
    if not (raw or "").strip():
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        logger.warning("Invalid instruction_methods JSON: %s", raw[:80])
        return []


def _normalize_bracket_key(bracket: str) -> str:
    return re.sub(r"\s+", "", (bracket or "").lower().replace("–", "-"))


def _find_age_bracket(bracket_str: str) -> AgeBracket | None:
    key = _normalize_bracket_key(bracket_str)
    for ab in AgeBracket.objects.all():
        if _normalize_bracket_key(ab.title) == key:
            return ab
        if _normalize_bracket_key(str(ab)) == key:
            return ab
    m = re.match(r"(\d+)-(\d+)", key.replace("+", ""))
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return AgeBracket.objects.filter(min_age=lo, max_age=hi).first()
    if key.endswith("+"):
        lo = int(re.sub(r"[^0-9]", "", key) or "0")
        return AgeBracket.objects.filter(min_age=lo, max_age__isnull=True).first()
    return None


def _find_variant(template_name: str, bracket_str: str, track: str) -> RoutineVariant | None:
    tmpl = RoutineTemplate.objects.filter(name__iexact=template_name.strip()).first()
    if not tmpl:
        tmpl = RoutineTemplate.objects.filter(name__icontains=template_name.strip()[:25]).first()
    if not tmpl:
        return None
    ab = _find_age_bracket(bracket_str)
    if not ab:
        return None
    track = (track or "").strip().lower()
    return RoutineVariant.objects.filter(template=tmpl, age_bracket=ab, track=track).first()


def _parse_variant_prescription_chunk(chunk: str) -> tuple[str, str, str, str, str] | None:
    parts = [p.strip() for p in chunk.split("|")]
    if len(parts) < 5:
        return None
    return parts[0], parts[1], parts[2], parts[3], "|".join(parts[4:])


def apply_catalog_row(row: dict, *, dry_run: bool = False) -> dict:
    """
    Update one Exercise (by id) and its VariantExercise rows from a CSV dict.
    Returns stats dict for logging.
    """
    stats = {"exercise_updated": False, "variants_updated": 0, "warnings": []}

    try:
        ex_id = int(row.get("id") or 0)
    except (TypeError, ValueError):
        stats["warnings"].append(f"invalid id: {row.get('id')}")
        return stats

    exercise = Exercise.objects.filter(pk=ex_id).first()
    if not exercise:
        stats["warnings"].append(f"exercise id={ex_id} not found")
        return stats

    methods = _parse_instruction_methods(row.get("instructions_methods_json") or "")
    spr = _optional_decimal(row.get("seconds_per_rep"))
    spinal = _optional_int(row.get("spinal_pct"))
    collapse = _optional_int(row.get("collapse_pct"))
    pelvic = _optional_int(row.get("pelvic_pct"))
    legs = _optional_int(row.get("legs_pct"))

    if not dry_run:
        exercise.description = (row.get("description") or "").strip()
        exercise.safety_note = (row.get("safety_note") or "").strip()
        exercise.instruction_methods = methods
        if (row.get("short_name") or "").strip():
            exercise.short_name = row["short_name"].strip()
        cat = (row.get("category") or "").strip()
        if cat:
            exercise.category = cat
        exercise.seconds_per_rep = spr
        if all(v is not None for v in (spinal, collapse, pelvic, legs)):
            exercise.spinal_pct = spinal
            exercise.collapse_pct = collapse
            exercise.pelvic_pct = pelvic
            exercise.legs_pct = legs
        potency = _optional_int(row.get("potency"))
        hgh = _optional_int(row.get("hgh_score"))
        if potency is not None:
            exercise.potency = potency
        if hgh is not None:
            exercise.hgh_score = hgh
        beast = _optional_int(row.get("beast_bonus"))
        if beast is not None:
            exercise.beast_bonus = beast
        if (row.get("teen_only") or "").strip():
            exercise.teen_only = _csv_bool(row.get("teen_only"))
        if (row.get("adult_only") or "").strip():
            exercise.adult_only = _csv_bool(row.get("adult_only"))
        exercise.save()
        stats["exercise_updated"] = True

    # Variant prescriptions from CSV column
    vp_raw = (row.get("variant_prescriptions") or "").strip()
    if not vp_raw:
        stats["warnings"].append(f"{exercise.name}: no variant_prescriptions in CSV")
        return stats

    for chunk in vp_raw.split(VARIANT_PRESCRIPTION_SEP):
        chunk = chunk.strip()
        if not chunk:
            continue
        parsed = _parse_variant_prescription_chunk(chunk)
        if not parsed:
            stats["warnings"].append(f"{exercise.name}: bad variant chunk: {chunk[:60]}")
            continue
        tmpl_name, bracket, track, tier, dosage_str = parsed
        dosage = parse_primary_timer_dosage(dosage_str)
        if not dosage:
            stats["warnings"].append(f"{exercise.name}: unparseable dosage: {dosage_str}")
            continue

        variant = _find_variant(tmpl_name, bracket, track)
        if not variant:
            stats["warnings"].append(
                f"{exercise.name}: variant not found: {tmpl_name}|{bracket}|{track}"
            )
            continue

        ve = VariantExercise.objects.filter(variant=variant, exercise=exercise, tier=tier).first()
        if not ve:
            ve = VariantExercise.objects.filter(variant=variant, exercise=exercise).first()
        if not ve:
            stats["warnings"].append(
                f"{exercise.name}: no VariantExercise on {variant} tier={tier}"
            )
            continue

        if not dry_run:
            ve.sets = dosage.sets
            ve.quantity_min = dosage.quantity_min
            ve.quantity_max = dosage.quantity_max
            ve.unit = dosage.unit
            note = dosage.per_side_note
            if note and note not in (ve.notes or ""):
                ve.notes = note
            ve.save(update_fields=["sets", "quantity_min", "quantity_max", "unit", "notes"])
        stats["variants_updated"] += 1

    return stats


def import_catalog_csv(path: Path, *, dry_run: bool = False) -> dict:
    """Import all rows from client-fixed catalog CSV."""
    summary = {
        "rows": 0,
        "exercises_updated": 0,
        "variants_updated": 0,
        "warnings": [],
    }
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with transaction.atomic():
        for row in rows:
            summary["rows"] += 1
            stats = apply_catalog_row(row, dry_run=dry_run)
            if stats.get("exercise_updated"):
                summary["exercises_updated"] += 1
            summary["variants_updated"] += stats.get("variants_updated", 0)
            summary["warnings"].extend(stats.get("warnings", []))
        if dry_run:
            transaction.set_rollback(True)

    return summary
