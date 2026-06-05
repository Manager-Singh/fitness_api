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
    per_side_word: str = "side"  # "side" or "leg" (the client catalog distinguishes both)

    @property
    def per_side_note(self) -> str:
        if self.per_side:
            return f"per {self.per_side_word or 'side'}"
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
    side_word = (m.group(4) or "").lower()
    per_side = bool(side_word)
    is_timer = "second" in unit_word or "(timer)" in text.lower()
    unit = Unit.SECS if is_timer else Unit.REPS
    return ParsedDosage(
        sets=sets,
        quantity_min=qty_min,
        quantity_max=qty_max,
        unit=unit,
        per_side=per_side,
        is_timer=is_timer,
        per_side_word=side_word or "side",
    )


def format_primary_timer_dosage(
    *,
    sets: int,
    quantity_min: int,
    quantity_max: int | None,
    unit: str,
    per_side: bool = False,
    per_side_word: str | None = None,
) -> str:
    """Human-readable dosage matching the client catalog format.

    ``per_side_word`` lets callers preserve the catalog's "per side" vs
    "per leg" distinction; defaults to "side" when only the boolean is given.
    """
    suffix = ""
    if per_side:
        word = (per_side_word or "side").strip().lower() or "side"
        suffix = f" per {word}"
    if unit == Unit.SECS:
        if quantity_max and quantity_max != quantity_min:
            qty = f"{quantity_min}–{quantity_max}"
        else:
            qty = str(quantity_min)
        return f"{sets} set(s) × {qty} seconds{suffix} (timer)"
    if quantity_max and quantity_max != quantity_min:
        qty = f"{quantity_min}–{quantity_max}"
    else:
        qty = str(quantity_min)
    return f"{sets} set(s) × {qty} reps{suffix}"
