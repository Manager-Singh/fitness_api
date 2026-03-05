from typing import Optional


def height_str(ft: int | None, inch: int | None) -> str:
    """Return `5'11"` or 'unknown' if both parts missing."""
    if ft is None and inch is None:
        return "unknown"
    ft = ft or 0
    inch = inch or 0
    return f"{ft}'{inch}\""


def ft_in_to_cm(ft: int | str | None, inch: int | str | None) -> float | None:
    """Feet+inches → centimetres (None- and str-safe)."""
    if ft is None and inch is None:
        return None
    try:
        ft = float(ft or 0)
        inch = float(inch or 0)
        return ft * 30.48 + inch * 2.54
    except (ValueError, TypeError):
        return None  # gracefully handle invalid input


def fmt_cm(val: float | None) -> str:
    """Return '175.4 cm' or 'unknown'."""
    return f"{val:.1f} cm" if val is not None else "unknown"
