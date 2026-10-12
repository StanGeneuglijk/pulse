"""Persistence for the WHOOP product: scoped reads and the idempotent,
content-hash-gated upserts every sync lands on.
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.clock import utcnow
from core.exceptions import UserNotFoundError
from services.whoop.models import (
    BodyMeasurement,
    Cycle,
    Recovery,
    Sleep,
    SyncJobLog,
    User,
    UserActivityLog,
    Workout,
)
from services.whoop.whoop_types import (
    BodyMeasurement as BodyMeasurementRecord,
)
from services.whoop.whoop_types import (
    CycleRecord,
    Profile,
    RecoveryRecord,
    SleepRecord,
    WorkoutRecord,
)

_LOG_PAGE_SIZE = 50

RecordModel = type[Cycle] | type[Recovery] | type[Sleep] | type[Workout]


def _parse_whoop_datetime(value: str | None) -> datetime | None:
    """WHOOP's `...Z` timestamp as the naive UTC datetime the schema stores."""
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _raw_and_hash(record: BaseModel) -> tuple[dict, str]:
    """The record as stored JSON, and its fingerprint — an unchanged hash lets
    the upsert skip the write."""
    raw = record.model_dump(mode="json", exclude_none=True)
    return raw, hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


async def get_user(db: AsyncSession, user_id: str) -> User:
    """Raises:
    UserNotFoundError: If no such user exists.
    """
    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        raise UserNotFoundError(user_id)
    return user


async def list_connected_user_ids(db: AsyncSession) -> list[uuid.UUID]:
    """Every connected user — the set `/sync/batch` fans out to."""
    result = await db.execute(select(User.id).where(User.whoop_connected.is_(True)))
    return list(result.scalars().all())


async def _list_records(db: AsyncSession, model: RecordModel, user_id: str) -> list:
    result = await db.execute(
        select(model).where(model.user_id == uuid.UUID(user_id)).order_by(model.recorded_at.desc())
    )
    return list(result.scalars().all())


async def list_recovery(db: AsyncSession, user_id: str) -> list[Recovery]:
    """All recovery rows for one user, newest first."""
    return await _list_records(db, Recovery, user_id)


async def list_sleep(db: AsyncSession, user_id: str) -> list[Sleep]:
    """All sleep rows for one user, newest first."""
    return await _list_records(db, Sleep, user_id)


async def list_workout(db: AsyncSession, user_id: str) -> list[Workout]:
    """All workout rows for one user, newest first."""
    return await _list_records(db, Workout, user_id)


async def list_cycles(db: AsyncSession, user_id: str) -> list[Cycle]:
    """All cycles (physiological days) for one user, newest first."""
    return await _list_records(db, Cycle, user_id)


async def get_body_measurement(db: AsyncSession, user_id: str) -> BodyMeasurement | None:
    return await db.get(BodyMeasurement, uuid.UUID(user_id))


async def list_activity(db: AsyncSession, user_id: str) -> list[UserActivityLog]:
    """A user's recent API activity, newest first."""
    result = await db.execute(
        select(UserActivityLog)
        .where(UserActivityLog.user_id == uuid.UUID(user_id))
        .order_by(UserActivityLog.created_at.desc())
        .limit(_LOG_PAGE_SIZE)
    )
    return list(result.scalars().all())


async def list_syncs(db: AsyncSession, user_id: str) -> list[SyncJobLog]:
    """A user's recent sync attempts, newest first."""
    result = await db.execute(
        select(SyncJobLog)
        .where(SyncJobLog.user_id == uuid.UUID(user_id))
        .order_by(SyncJobLog.created_at.desc())
        .limit(_LOG_PAGE_SIZE)
    )
    return list(result.scalars().all())


async def last_successful_sync_at(db: AsyncSession, user_id: str) -> datetime | None:
    """When this user's last successful sync finished — the start point for an
    incremental fetch.
    """
    result = await db.execute(
        select(func.max(SyncJobLog.created_at)).where(
            SyncJobLog.user_id == uuid.UUID(user_id), SyncJobLog.status == "success"
        )
    )
    return result.scalar_one()


async def needs_full_sync(db: AsyncSession, user_id: str) -> bool:
    """True when some stored record predates full-detail storage (`raw` is
    empty), so the next sync must re-fetch history rather than only recent days."""
    uid = uuid.UUID(user_id)
    stale = or_(
        *(
            exists().where(model.user_id == uid, model.raw.is_(None))
            for model in (Recovery, Sleep, Workout)
        )
    )
    return bool((await db.execute(select(stale))).scalar())


async def connect_user(
    db: AsyncSession,
    *,
    profile: Profile,
    encrypted_access_token: str,
    encrypted_refresh_token: str,
    expires_in: int,
) -> User:
    """Store a freshly exchanged token pair for a WHOOP account: updates the
    existing user when this account connected before (keeping its id and
    `read_token`), creates one otherwise."""
    whoop_user_id = str(profile.user_id)
    result = await db.execute(select(User).where(User.whoop_user_id == whoop_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(whoop_user_id=whoop_user_id, read_token=secrets.token_urlsafe(32))
        db.add(user)
    user.first_name = profile.first_name
    user.last_name = profile.last_name
    user.email = profile.email
    user.encrypted_access_token = encrypted_access_token
    user.encrypted_refresh_token = encrypted_refresh_token
    user.token_expires_at = utcnow() + timedelta(seconds=expires_in)
    user.whoop_connected = True
    await db.commit()
    await db.refresh(user)
    return user


async def mark_disconnected(db: AsyncSession, user_id: str) -> None:
    """Stop scheduling syncs for a user whose WHOOP grant is dead, until they
    reconnect."""
    user = await get_user(db, user_id)
    user.whoop_connected = False
    await db.commit()


async def update_tokens(
    db: AsyncSession,
    user_id: uuid.UUID | str,
    encrypted_access_token: str,
    encrypted_refresh_token: str,
    *,
    expires_in: int,
) -> None:
    """Persist a refreshed token pair.

    Raises:
        UserNotFoundError: If `user_id` doesn't exist.
    """
    user = await get_user(db, str(user_id))
    user.encrypted_access_token = encrypted_access_token
    user.encrypted_refresh_token = encrypted_refresh_token
    user.token_expires_at = utcnow() + timedelta(seconds=expires_in)
    await db.commit()


async def _upsert(
    db: AsyncSession,
    model: RecordModel,
    constraint: str,
    user_id: str,
    whoop_record_id: str,
    record: BaseModel,
    values: dict[str, Any],
) -> None:
    """Upsert one WHOOP record keyed on (user_id, whoop_record_id); skipped
    when its content hash is unchanged.

    Doesn't commit — sync_one_user commits once per batch, not once per record.
    """
    raw, content_hash = _raw_and_hash(record)
    row = {**values, "raw": raw, "content_hash": content_hash}
    stmt = insert(model).values(user_id=uuid.UUID(user_id), whoop_record_id=whoop_record_id, **row)
    stmt = stmt.on_conflict_do_update(
        constraint=constraint,
        set_={key: stmt.excluded[key] for key in row},
        where=model.content_hash != stmt.excluded.content_hash,
    )
    await db.execute(stmt)


async def upsert_cycle(db: AsyncSession, user_id: str, record: CycleRecord) -> None:
    score = record.score
    await _upsert(
        db,
        Cycle,
        "uq_user_cycle_record",
        user_id,
        str(record.id),
        record,
        {
            "score": score.strain if score else None,
            "recorded_at": _parse_whoop_datetime(record.created_at),
            "start": _parse_whoop_datetime(record.start),
            "end": _parse_whoop_datetime(record.end),
            "score_state": record.score_state,
            "kilojoule": score.kilojoule if score else None,
            "average_heart_rate": score.average_heart_rate if score else None,
            "max_heart_rate": score.max_heart_rate if score else None,
        },
    )


async def upsert_recovery(db: AsyncSession, user_id: str, record: RecoveryRecord) -> None:
    score = record.score
    await _upsert(
        db,
        Recovery,
        "uq_user_recovery_record",
        user_id,
        str(record.cycle_id),
        record,
        {
            "score": score.recovery_score if score else None,
            "recorded_at": _parse_whoop_datetime(record.created_at),
            "sleep_id": record.sleep_id,
            "score_state": record.score_state,
            "user_calibrating": score.user_calibrating if score else None,
            "resting_heart_rate": score.resting_heart_rate if score else None,
            "hrv_rmssd_milli": score.hrv_rmssd_milli if score else None,
            "spo2_percentage": score.spo2_percentage if score else None,
            "skin_temp_celsius": score.skin_temp_celsius if score else None,
        },
    )


def _sleep_needed_milli(record: SleepRecord) -> int | None:
    need = record.score.sleep_needed if record.score else None
    if need is None or need.baseline_milli is None:
        return None
    return (
        need.baseline_milli
        + (need.need_from_sleep_debt_milli or 0)
        + (need.need_from_recent_strain_milli or 0)
        + (need.need_from_recent_nap_milli or 0)  # negative: a nap reduces need
    )


async def upsert_sleep(db: AsyncSession, user_id: str, record: SleepRecord) -> None:
    score = record.score
    stages = score.stage_summary if score else None
    await _upsert(
        db,
        Sleep,
        "uq_user_sleep_record",
        user_id,
        record.id,
        record,
        {
            "score": score.sleep_performance_percentage if score else None,
            "recorded_at": _parse_whoop_datetime(record.created_at),
            "cycle_id": str(record.cycle_id) if record.cycle_id is not None else None,
            "start": _parse_whoop_datetime(record.start),
            "end": _parse_whoop_datetime(record.end),
            "nap": record.nap,
            "score_state": record.score_state,
            "in_bed_milli": stages.total_in_bed_time_milli if stages else None,
            "awake_milli": stages.total_awake_time_milli if stages else None,
            "light_sleep_milli": stages.total_light_sleep_time_milli if stages else None,
            "slow_wave_sleep_milli": stages.total_slow_wave_sleep_time_milli if stages else None,
            "rem_sleep_milli": stages.total_rem_sleep_time_milli if stages else None,
            "sleep_cycle_count": stages.sleep_cycle_count if stages else None,
            "disturbance_count": stages.disturbance_count if stages else None,
            "sleep_needed_milli": _sleep_needed_milli(record),
            "respiratory_rate": score.respiratory_rate if score else None,
            "sleep_consistency_percentage": score.sleep_consistency_percentage if score else None,
            "sleep_efficiency_percentage": score.sleep_efficiency_percentage if score else None,
        },
    )


async def upsert_workout(db: AsyncSession, user_id: str, record: WorkoutRecord) -> None:
    score = record.score
    zones = score.zone_durations if score else None
    await _upsert(
        db,
        Workout,
        "uq_user_workout_record",
        user_id,
        record.id,
        record,
        {
            "score": score.strain if score else None,
            "recorded_at": _parse_whoop_datetime(record.created_at),
            "start": _parse_whoop_datetime(record.start),
            "end": _parse_whoop_datetime(record.end),
            "sport_name": record.sport_name,
            "score_state": record.score_state,
            "average_heart_rate": score.average_heart_rate if score else None,
            "max_heart_rate": score.max_heart_rate if score else None,
            "kilojoule": score.kilojoule if score else None,
            "percent_recorded": score.percent_recorded if score else None,
            "distance_meter": score.distance_meter if score else None,
            "altitude_gain_meter": score.altitude_gain_meter if score else None,
            "zone_durations_milli": [
                zones.zone_zero_milli,
                zones.zone_one_milli,
                zones.zone_two_milli,
                zones.zone_three_milli,
                zones.zone_four_milli,
                zones.zone_five_milli,
            ]
            if zones
            else None,
        },
    )


async def upsert_body_measurement(
    db: AsyncSession, user_id: str, record: BodyMeasurementRecord
) -> None:
    """Replace the user's body measurement. Doesn't commit."""
    values = record.model_dump()
    stmt = insert(BodyMeasurement).values(user_id=uuid.UUID(user_id), **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[BodyMeasurement.user_id], set_={**values, "updated_at": utcnow()}
    )
    await db.execute(stmt)
