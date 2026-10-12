"""Typed shapes of WHOOP's v2 API responses, parsed in client.py (the trust
boundary) so a shape change fails loudly there, not downstream.

Only the fields the platform reads are typed; unknown fields are ignored
here and kept verbatim in each row's `raw` column.
"""

from pydantic import BaseModel


class Profile(BaseModel):
    user_id: int
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class BodyMeasurement(BaseModel):
    height_meter: float | None = None
    weight_kilogram: float | None = None
    max_heart_rate: int | None = None


class CycleScore(BaseModel):
    strain: float | None = None
    kilojoule: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None


class CycleRecord(BaseModel):
    id: int
    created_at: str
    start: str
    end: str | None = None  # None while the cycle is still in progress
    timezone_offset: str | None = None
    score_state: str | None = None
    score: CycleScore | None = None


class RecoveryScore(BaseModel):
    user_calibrating: bool | None = None
    recovery_score: int | None = None
    resting_heart_rate: float | None = None
    hrv_rmssd_milli: float | None = None
    spo2_percentage: float | None = None
    skin_temp_celsius: float | None = None


class RecoveryRecord(BaseModel):
    cycle_id: int
    sleep_id: str | None = None
    created_at: str
    score_state: str | None = None
    score: RecoveryScore | None = None


class SleepStageSummary(BaseModel):
    total_in_bed_time_milli: int | None = None
    total_awake_time_milli: int | None = None
    total_no_data_time_milli: int | None = None
    total_light_sleep_time_milli: int | None = None
    total_slow_wave_sleep_time_milli: int | None = None
    total_rem_sleep_time_milli: int | None = None
    sleep_cycle_count: int | None = None
    disturbance_count: int | None = None


class SleepNeeded(BaseModel):
    baseline_milli: int | None = None
    need_from_sleep_debt_milli: int | None = None
    need_from_recent_strain_milli: int | None = None
    need_from_recent_nap_milli: int | None = None


class SleepScore(BaseModel):
    stage_summary: SleepStageSummary | None = None
    sleep_needed: SleepNeeded | None = None
    respiratory_rate: float | None = None
    sleep_performance_percentage: int | None = None
    sleep_consistency_percentage: int | None = None
    sleep_efficiency_percentage: float | None = None


class SleepRecord(BaseModel):
    id: str
    cycle_id: int | None = None
    created_at: str
    start: str | None = None
    end: str | None = None
    timezone_offset: str | None = None
    nap: bool | None = None
    score_state: str | None = None
    score: SleepScore | None = None


class ZoneDurations(BaseModel):
    zone_zero_milli: int | None = None
    zone_one_milli: int | None = None
    zone_two_milli: int | None = None
    zone_three_milli: int | None = None
    zone_four_milli: int | None = None
    zone_five_milli: int | None = None


class WorkoutScore(BaseModel):
    strain: float | None = None  # 0-21, decimal
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    kilojoule: float | None = None
    percent_recorded: float | None = None
    distance_meter: float | None = None
    altitude_gain_meter: float | None = None
    altitude_change_meter: float | None = None
    zone_durations: ZoneDurations | None = None


class WorkoutRecord(BaseModel):
    id: str
    created_at: str
    start: str | None = None
    end: str | None = None
    timezone_offset: str | None = None
    sport_name: str | None = None
    score_state: str | None = None
    score: WorkoutScore | None = None
