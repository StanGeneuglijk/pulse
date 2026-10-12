"""ORM schema for the WHOOP product. Data tables are written only through
crud.py's upserts, keyed on the `(user_id, whoop_record_id)` unique constraints.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import utcnow
from core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # The WHOOP account id: reconnecting the same account updates this row.
    # Nullable only for rows created before it was recorded.
    whoop_user_id: Mapped[str | None] = mapped_column(default=None, unique=True)
    first_name: Mapped[str | None] = mapped_column(default=None)
    last_name: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    encrypted_access_token: Mapped[str | None] = mapped_column(default=None)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(default=None)
    token_expires_at: Mapped[datetime | None] = mapped_column(default=None)
    whoop_connected: Mapped[bool] = mapped_column(default=False)
    read_token: Mapped[str | None] = mapped_column(default=None, unique=True)  # per-user read scope


class BodyMeasurement(Base):
    """The user's latest WHOOP body measurement — one row per user, replaced
    on every sync."""

    __tablename__ = "body_measurements"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    height_meter: Mapped[float | None]
    weight_kilogram: Mapped[float | None]
    max_heart_rate: Mapped[int | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


# Every WHOOP record table shares these: `score` and `recorded_at` are the
# headline value and timestamp (read by whoop-insight-service), typed
# columns hold the metrics worth querying, and `raw` keeps the full record.


class Cycle(Base):
    """One physiological day: day strain, energy, heart rate."""

    __tablename__ = "cycles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    whoop_record_id: Mapped[str]
    score: Mapped[float | None]  # day strain, 0-21
    recorded_at: Mapped[datetime]
    start: Mapped[datetime | None]
    end: Mapped[datetime | None]
    score_state: Mapped[str | None]
    kilojoule: Mapped[float | None]
    average_heart_rate: Mapped[int | None]
    max_heart_rate: Mapped[int | None]
    raw: Mapped[dict | None] = mapped_column(JSONB)
    content_hash: Mapped[str]

    __table_args__ = (
        UniqueConstraint("user_id", "whoop_record_id", name="uq_user_cycle_record"),
        Index("ix_cycle_user_id", "user_id"),
    )


class Recovery(Base):
    __tablename__ = "recoveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    whoop_record_id: Mapped[str]  # the cycle id — a recovery is 1:1 with its cycle
    score: Mapped[int | None]  # recovery %, 0-100
    recorded_at: Mapped[datetime]
    sleep_id: Mapped[str | None]
    score_state: Mapped[str | None]
    user_calibrating: Mapped[bool | None]
    resting_heart_rate: Mapped[float | None]
    hrv_rmssd_milli: Mapped[float | None]
    spo2_percentage: Mapped[float | None]
    skin_temp_celsius: Mapped[float | None]
    raw: Mapped[dict | None] = mapped_column(JSONB)
    content_hash: Mapped[str]

    __table_args__ = (
        UniqueConstraint("user_id", "whoop_record_id", name="uq_user_recovery_record"),
        Index("ix_recovery_user_id", "user_id"),
    )


class Sleep(Base):
    __tablename__ = "sleeps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    whoop_record_id: Mapped[str]
    score: Mapped[int | None]  # sleep performance %, 0-100
    recorded_at: Mapped[datetime]
    cycle_id: Mapped[str | None]
    start: Mapped[datetime | None]
    end: Mapped[datetime | None]
    nap: Mapped[bool | None]
    score_state: Mapped[str | None]
    in_bed_milli: Mapped[int | None]
    awake_milli: Mapped[int | None]
    light_sleep_milli: Mapped[int | None]
    slow_wave_sleep_milli: Mapped[int | None]
    rem_sleep_milli: Mapped[int | None]
    sleep_cycle_count: Mapped[int | None]
    disturbance_count: Mapped[int | None]
    sleep_needed_milli: Mapped[int | None]  # baseline + debt + strain - naps
    respiratory_rate: Mapped[float | None]
    sleep_consistency_percentage: Mapped[int | None]
    sleep_efficiency_percentage: Mapped[float | None]
    raw: Mapped[dict | None] = mapped_column(JSONB)
    content_hash: Mapped[str]

    __table_args__ = (
        UniqueConstraint("user_id", "whoop_record_id", name="uq_user_sleep_record"),
        Index("ix_sleep_user_id", "user_id"),
    )


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    whoop_record_id: Mapped[str]
    score: Mapped[float | None]  # strain — WHOOP's real 0-21 decimal scale, not an integer
    recorded_at: Mapped[datetime]
    start: Mapped[datetime | None]
    end: Mapped[datetime | None]
    sport_name: Mapped[str | None]
    score_state: Mapped[str | None]
    average_heart_rate: Mapped[int | None]
    max_heart_rate: Mapped[int | None]
    kilojoule: Mapped[float | None]
    percent_recorded: Mapped[float | None]
    distance_meter: Mapped[float | None]
    altitude_gain_meter: Mapped[float | None]
    zone_durations_milli: Mapped[list | None] = mapped_column(JSONB)  # zones 0-5
    raw: Mapped[dict | None] = mapped_column(JSONB)
    content_hash: Mapped[str]

    __table_args__ = (
        UniqueConstraint("user_id", "whoop_record_id", name="uq_user_workout_record"),
        Index("ix_workout_user_id", "user_id"),
    )


class SyncJobLog(Base):
    """One row per sync attempt, written when it finishes. `user_id` has no
    foreign key so an attempt for a missing user can still be logged.
    """

    __tablename__ = "sync_job_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        index=True
    )  # X-Request-ID of the request that triggered this
    job_id: Mapped[str | None]  # RQ job id — same value across every attempt of one job
    attempt_number: Mapped[int]  # 1 on the first attempt, incrementing per retry
    trigger_source: Mapped[str]  # login | cron | manual
    status: Mapped[str]  # success | failed
    retries_left: Mapped[int | None]  # RQ's own count at write time; None outside a worker
    recoveries_synced: Mapped[int]
    sleep_synced: Mapped[int]
    workouts_synced: Mapped[int]
    cycles_synced: Mapped[int] = mapped_column(default=0, server_default="0")
    duration_ms: Mapped[float]
    error_message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (Index("ix_sync_job_logs_user_id", "user_id"),)


class UserActivityLog(Base):
    """One row per read-route hit — how people use the API, as opposed to
    SyncJobLog's pipeline record.
    """

    __tablename__ = "user_activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    route: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (Index("ix_user_activity_logs_user_id", "user_id"),)
