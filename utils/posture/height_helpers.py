import logging

logger = logging.getLogger(__name__)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        logger.exception("safe_float failed", extra={"value": repr(v)})
        return default


def safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        logger.exception("safe_int failed", extra={"value": repr(v)})
        return default
