"""Response shapes for `services/whoop/router.py`. Python stays snake_case
throughout the service; these models translate to camelCase only at the
JSON boundary, via `alias_generator` — the conventional split between an
idiomatic Python backend and a JS-conventional API surface.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for every response model below: fields are declared and set in
    snake_case from Python, serialized in camelCase over the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class RecordResponse(CamelModel):
    id: uuid.UUID
    whoop_record_id: str
    score: int | float | None  # recovery/sleep %, or strain 0-21 for cycles and workouts
    recorded_at: datetime
    score_state: str | None = None


class CycleResponse(RecordResponse):
    start: datetime | None
    end: datetime | None
    kilojoule: float | None
    average_heart_rate: int | None
    max_heart_rate: int | None


class RecoveryResponse(RecordResponse):
    sleep_id: str | None
    user_calibrating: bool | None
    resting_heart_rate: float | None
    hrv_rmssd_milli: float | None
    spo2_percentage: float | None
    skin_temp_celsius: float | None


class SleepResponse(RecordResponse):
    cycle_id: str | None
    start: datetime | None
    end: datetime | None
    nap: bool | None
    in_bed_milli: int | None
    awake_milli: int | None
    light_sleep_milli: int | None
    slow_wave_sleep_milli: int | None
    rem_sleep_milli: int | None
    sleep_cycle_count: int | None
    disturbance_count: int | None
    sleep_needed_milli: int | None
    respiratory_rate: float | None
    sleep_consistency_percentage: int | None
    sleep_efficiency_percentage: float | None


class WorkoutResponse(RecordResponse):
    start: datetime | None
    end: datetime | None
    sport_name: str | None
    average_heart_rate: int | None
    max_heart_rate: int | None
    kilojoule: float | None
    percent_recorded: float | None
    distance_meter: float | None
    altitude_gain_meter: float | None
    zone_durations_milli: list[int | None] | None


class ProfileResponse(CamelModel):
    first_name: str | None
    last_name: str | None
    height_meter: float | None
    weight_kilogram: float | None
    max_heart_rate: int | None


class SyncBatchResponse(CamelModel):
    queued: int


class AuthCallbackResponse(CamelModel):
    connected: bool
    user_id: uuid.UUID
    read_token: str | None  # shown once — scopes read access to this user only


class ExchangeCodeRequest(CamelModel):
    code: str


class SyncTriggerResponse(CamelModel):
    queued: bool


class ActivityLogResponse(CamelModel):
    route: str
    created_at: datetime


class SyncLogResponse(CamelModel):
    status: str
    trigger_source: str
    recoveries_synced: int
    sleep_synced: int
    workouts_synced: int
    cycles_synced: int
    duration_ms: float
    error_message: str | None
    created_at: datetime
