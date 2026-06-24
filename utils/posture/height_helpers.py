import logging

logger = logging.getLogger(__name__)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safe_float(v, default=0.0):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def safe_int(v, default=0):
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
