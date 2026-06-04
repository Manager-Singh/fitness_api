"""Encode/decode PaymentPackage.duration (2 chars, no DB migration)."""
from __future__ import annotations

# 1–12 → single stored character (fits max_length=2 with unit letter)
_COUNT_CHARS = "123456789abc"
_COUNT_TO_CHAR = {i + 1: c for i, c in enumerate(_COUNT_CHARS)}
_CHAR_TO_COUNT = {c: i + 1 for i, c in enumerate(_COUNT_CHARS)}

DURATION_UNIT_CHOICES = [
    ("d", "Day"),
    ("w", "Week"),
    ("m", "Month"),
    ("y", "Year"),
]

DURATION_COUNT_CHOICES = [(i, str(i)) for i in range(1, 13)]

_UNIT_LABELS = {
    "d": ("Day", "Days"),
    "w": ("Week", "Weeks"),
    "m": ("Month", "Months"),
    "y": ("Year", "Years"),
}


def _char_to_count(ch: str) -> int:
    return _CHAR_TO_COUNT.get(ch, 1)


def _count_to_char(count: int) -> str:
    count = max(1, min(12, int(count)))
    return _COUNT_TO_CHAR[count]


def decode_duration(duration: str | None) -> tuple[int, str]:
    """
    Split stored code into (count 1–12, unit d/w/m/y).

    Legacy: ``3``, ``6``, ``9``, ``12`` = that many months.
    Encoded: ``{count_char}{unit}`` e.g. ``7d``, ``3m``, ``1y``, ``cw`` = 12 weeks.
    """
    d = str(duration or "3").strip().lower()
    if len(d) == 2 and d[1] in "dwmy":
        return _char_to_count(d[0]), d[1]
    if d.isdigit():
        n = int(d)
        return max(1, min(12, n)), "m"
    return 3, "m"


def encode_duration(count: int, unit: str) -> str:
    """Persist count + unit in the existing ``duration`` column (max 2 chars)."""
    unit = (unit or "m").strip().lower()[:1]
    if unit not in "dwmy":
        unit = "m"
    return f"{_count_to_char(int(count))}{unit}"


def format_duration_label(duration: str | None) -> str:
    count, unit = decode_duration(duration)
    singular, plural = _UNIT_LABELS.get(unit, ("Month", "Months"))
    label = singular if count == 1 else plural
    return f"{count} {label}"


def package_duration_days(duration: str | None) -> int:
    count, unit = decode_duration(duration)
    if unit == "d":
        return count
    if unit == "w":
        return count * 7
    if unit == "m":
        return count * 30
    if unit == "y":
        return count * 365
    return count * 30
