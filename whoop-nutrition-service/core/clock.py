"""`utcnow()` as a naive UTC datetime — the schema is naive-UTC throughout,
since every upstream timestamp is UTC.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """The current time, UTC, naive — matches every column and
    comparison in this schema, which are all naive-UTC by design."""
    return datetime.now(UTC).replace(tzinfo=None)
