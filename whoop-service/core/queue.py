"""The Redis connection RQ runs on, and the only place `rq` is imported —
products use `Queue`, `Retry` and `get_current_job` from here.
"""

from redis import Redis
from rq import Queue, Retry, get_current_job

from core.config import settings

redis_conn = Redis.from_url(settings.redis_url, protocol=2)

__all__ = ["redis_conn", "Queue", "Retry", "get_current_job"]
