"""Timestamps in UTC.

Every timestamp written to evidence files is UTC in the form 2026-11-18T08:15:00Z.
Git commit dates are read in strict ISO 8601 with an offset (%cI) and converted here.
Naive datetimes (no offset) are rejected, because their zone cannot be known.
"""
from datetime import datetime, timezone


def to_utc_iso(value):
    """Convert an ISO 8601 string with offset (or a timezone-aware datetime) to UTC 'Z' form."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z") or text.endswith("z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"timestamp without UTC offset: {value!r}")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_id_from(iso_utc):
    """Directory-safe run identifier from a UTC timestamp."""
    return iso_utc.replace(":", "").replace("-", "")
