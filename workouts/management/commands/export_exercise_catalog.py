"""
Export every Exercise row from the database with descriptions, instructions,
safety notes, segment matrix, and timer/dosage (sets × quantity × unit).

Outputs Markdown + CSV under docs/ for client copy-editing.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from utils.exercise_prescriptions import prescription_for_exercise_name
from workouts.models import Exercise, Unit, VariantExercise


def _format_dosage(sets, qty_min, qty_max, unit) -> str:
    unit_label = "seconds (timer)" if unit == Unit.SECS else "reps"
    if qty_max and qty_max != qty_min:
        qty = f"{qty_min}–{qty_max}"
    else:
        qty = str(qty_min)
    return f"{sets} set(s) × {qty} {unit_label}"


def _timer_summary(exercise) -> str:
    """Primary timer: first variant prescription, else code fallback."""
    ve = (
        VariantExercise.objects.filter(exercise=exercise)
        .order_by("variant__template__name", "order")
        .first()
    )
    if ve:
        return _format_dosage(ve.sets, ve.quantity_min, ve.quantity_max, ve.unit)
    pres = prescription_for_exercise_name(exercise.name)
    return _format_dosage(
        pres["sets"],
        pres["quantity_min"],
        pres.get("quantity_max"),
        pres["unit"],
    ) + " (code default — no VariantExercise row)"


def _instructions_text(exercise) -> str:
    lines = exercise.get_instruction_lines()
    if lines:
        return "\n".join(f"  {i + 1}. {line}" for i, line in enumerate(lines))
    if (exercise.instruction_content or "").strip():
        return exercise.instruction_content.strip()
    if (exercise.description or "").strip():
        return f"(description field only) {exercise.description.strip()}"
    return "(no instructions in database)"


def _methods_text(exercise) -> str:
    methods = exercise.get_instruction_methods()
    if not methods:
        return ""
    parts = []
    for m in methods:
        title = (m.get("title") or "Method").strip()
        steps = m.get("steps") or []
        parts.append(f"**{title}**")
        for i, step in enumerate(steps, 1):
            parts.append(f"  {i}. {step}")
    return "\n".join(parts)


class Command(BaseCommand):
    help = "Export exercise catalog (descriptions, instructions, timers) to docs/*.md and *.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="docs",
            help="Directory for EXERCISE_CATALOG_DATABASE_EXPORT.{md,csv}",
        )

    def handle(self, *args, **options):
        out_dir = Path(options["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        exercises = list(Exercise.objects.all().order_by("name"))

        md_path = out_dir / "EXERCISE_CATALOG_DATABASE_EXPORT.md"
        csv_path = out_dir / "EXERCISE_CATALOG_DATABASE_EXPORT.csv"

        self._write_markdown(md_path, exercises, stamp)
        self._write_csv(csv_path, exercises, stamp)

        self.stdout.write(self.style.SUCCESS(f"Wrote {md_path}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {csv_path}"))
        self.stdout.write(f"Exported {len(exercises)} exercises.")

    def _write_markdown(self, path: Path, exercises: list, stamp: str) -> None:
        lines = [
            "# Exercise catalog (from database)",
            "",
            f"Generated: {stamp}",
            "",
            "This document is pulled from live `Exercise` and `VariantExercise` rows.",
            "Use it to review and tweak copy, instructions, and timers before updating admin/DB.",
            "",
            "**Timer fields:** `sets` × `quantity_min`/`quantity_max` × `unit` (`secs` = countdown timer in seconds, `reps` = rep counter).",
            "",
            "---",
            "",
        ]

        for ex in exercises:
            ve_rows = list(
                VariantExercise.objects.filter(exercise=ex)
                .select_related("variant__template", "variant__age_bracket")
                .order_by("variant__template__name", "order")
            )
            lines.append(f"## {ex.name}")
            lines.append("")
            lines.append(f"| Field | Value |")
            lines.append(f"|-------|-------|")
            lines.append(f"| Database ID | {ex.id} |")
            lines.append(f"| Short name | {ex.short_name or '—'} |")
            lines.append(f"| Category | {ex.category} |")
            lines.append(f"| Points | {ex.points} |")
            lines.append(f"| Teen only | {ex.teen_only} |")
            lines.append(f"| Adult only | {ex.adult_only} |")
            if ex.assignment_matrix_ready:
                lines.append(
                    f"| Segment % (spinal/collapse/pelvic/legs) | "
                    f"{ex.spinal_pct}/{ex.collapse_pct}/{ex.pelvic_pct}/{ex.legs_pct} |"
                )
                lines.append(f"| Potency / HGH score / Beast bonus | {ex.potency}/{ex.hgh_score}/{ex.beast_bonus} |")
            else:
                lines.append("| Segment matrix | not fully configured |")
            spr = ex.seconds_per_rep
            spr_display = str(spr) if spr is not None else "(empty — hold/timer)"
            lines.append(f"| **seconds_per_rep** | {spr_display} |")
            lines.append(f"| **Primary timer/dosage** | **{_timer_summary(ex)}** |")
            lines.append("")

            if (ex.description or "").strip():
                lines.append("### Description (DB field)")
                lines.append("")
                lines.append(ex.description.strip())
                lines.append("")

            if (ex.safety_note or "").strip():
                lines.append("### Safety note")
                lines.append("")
                lines.append(ex.safety_note.strip())
                lines.append("")

            methods = _methods_text(ex)
            if methods:
                lines.append("### Instructions (methods JSON — shown in app when set)")
                lines.append("")
                lines.append(methods)
                lines.append("")

            lines.append("### Instructions (as shown in API — merged)")
            lines.append("")
            lines.append(_instructions_text(ex))
            lines.append("")

            if ve_rows:
                lines.append("### Timers / dosage by routine variant (VariantExercise)")
                lines.append("")
                lines.append("| Routine template | Age bracket | Track | Tier | Sets × Qty | Unit | Notes |")
                lines.append("|------------------|-------------|-------|------|------------|------|-------|")
                for ve in ve_rows:
                    v = ve.variant
                    tmpl = getattr(v.template, "name", str(v.template_id))
                    bracket = str(v.age_bracket)
                    dosage = _format_dosage(ve.sets, ve.quantity_min, ve.quantity_max, ve.unit)
                    lines.append(
                        f"| {tmpl} | {bracket} | {v.track} | {ve.tier} | {dosage} | {ve.unit} | {ve.notes or '—'} |"
                    )
                lines.append("")
            else:
                pres = prescription_for_exercise_name(ex.name)
                lines.append("### Timers / dosage (code fallback only)")
                lines.append("")
                lines.append(_format_dosage(
                    pres["sets"], pres["quantity_min"], pres.get("quantity_max"), pres["unit"]
                ))
                lines.append("")
                lines.append("_No VariantExercise rows in DB for this exercise._")
                lines.append("")

            lines.append("---")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_csv(self, path: Path, exercises: list, stamp: str) -> None:
        fieldnames = [
            "id",
            "name",
            "short_name",
            "category",
            "points",
            "teen_only",
            "adult_only",
            "spinal_pct",
            "collapse_pct",
            "pelvic_pct",
            "legs_pct",
            "potency",
            "hgh_score",
            "beast_bonus",
            "primary_timer_dosage",
            "seconds_per_rep",
            "description",
            "safety_note",
            "instructions_merged",
            "instructions_methods_json",
            "variant_prescriptions",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for ex in exercises:
                ve_rows = VariantExercise.objects.filter(exercise=ex).select_related(
                    "variant__template", "variant__age_bracket"
                ).order_by("variant__template__name", "order")
                var_parts = []
                for ve in ve_rows:
                    v = ve.variant
                    var_parts.append(
                        f"{v.template.name}|{v.age_bracket}|{v.track}|{ve.tier}|"
                        f"{_format_dosage(ve.sets, ve.quantity_min, ve.quantity_max, ve.unit)}"
                    )
                import json

                w.writerow({
                    "id": ex.id,
                    "name": ex.name,
                    "short_name": ex.short_name or "",
                    "category": ex.category,
                    "points": ex.points,
                    "teen_only": ex.teen_only,
                    "adult_only": ex.adult_only,
                    "spinal_pct": ex.spinal_pct if ex.spinal_pct is not None else "",
                    "collapse_pct": ex.collapse_pct if ex.collapse_pct is not None else "",
                    "pelvic_pct": ex.pelvic_pct if ex.pelvic_pct is not None else "",
                    "legs_pct": ex.legs_pct if ex.legs_pct is not None else "",
                    "potency": ex.potency if ex.potency is not None else "",
                    "hgh_score": ex.hgh_score if ex.hgh_score is not None else "",
                    "beast_bonus": ex.beast_bonus,
                    "primary_timer_dosage": _timer_summary(ex),
                    "seconds_per_rep": str(ex.seconds_per_rep) if ex.seconds_per_rep is not None else "",
                    "description": (ex.description or "").replace("\n", " ").strip(),
                    "safety_note": (ex.safety_note or "").replace("\n", " ").strip(),
                    "instructions_merged": " | ".join(ex.get_instruction_lines()).replace("\n", " "),
                    "instructions_methods_json": json.dumps(ex.instruction_methods or [], ensure_ascii=False),
                    "variant_prescriptions": " ;; ".join(var_parts),
                })
