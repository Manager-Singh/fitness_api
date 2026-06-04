"""Parse/format exercise dosage strings (catalog CSV + rep-counter player spec)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from workouts.models import Unit

DOSAGE_RE = re.compile(
    r"(\d+)\s*set\(s\)\s*×\s*([\d–\-]+)\s*(reps|seconds)"
    r"(?:\s*per\s*(side|leg))?(?:\s*\(timer\))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedDosage:
    sets: int
    quantity_min: int
    quantity_max: int | None
    unit: str  # Unit.REPS or Unit.SECS
    per_side: bool
    is_timer: bool

    @property
    def per_side_note(self) -> str:
        if self.per_side:
            return "per side"
        return ""


def _parse_quantity(raw: str) -> tuple[int, int | None]:
    raw = (raw or "").strip().replace("–", "-")
    if "-" in raw:
        parts = raw.split("-", 1)
        return int(parts[0]), int(parts[1])
    return int(raw), None


def parse_primary_timer_dosage(text: str) -> ParsedDosage | None:
    """Parse client catalog ``primary_timer_dosage`` strings."""
    if not (text or "").strip():
        return None
    m = DOSAGE_RE.search(text.strip())
    if not m:
        return None
    sets = int(m.group(1))
    qty_min, qty_max = _parse_quantity(m.group(2))
    unit_word = m.group(3).lower()
    per_side = bool(m.group(4))
    is_timer = "second" in unit_word or "(timer)" in text.lower()
    unit = Unit.SECS if is_timer else Unit.REPS
    return ParsedDosage(
        sets=sets,
        quantity_min=qty_min,
        quantity_max=qty_max,
        unit=unit,
        per_side=per_side,
        is_timer=is_timer,
    )


def format_primary_timer_dosage(
    *,
    sets: int,
    quantity_min: int,
    quantity_max: int | None,
    unit: str,
    per_side: bool = False,
) -> str:
    """Human-readable dosage matching the client catalog format."""
    if quantity_max and quantity_max != quantity_min:
        qty = f"{quantity_min}–{quantity_max}"
    else:
        qty = str(quantity_min)
    if unit == Unit.SECS:
        base = f"{sets} set(s) × {qty} seconds"
        if per_side:
            base += " per side"
        return f"{base} (timer)"
    base = f"{sets} set(s) × {qty} reps"
    if per_side:
        base += " per side"
    return base
