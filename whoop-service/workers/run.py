"""Entrypoint for `python -m workers.run`. Import every service module here —
RQ resolves job dotted-paths by importing them fresh in this process."""

import os
import uuid

from rq import Worker

import services.whoop.sync  # noqa: F401 — import needed so RQ can resolve the job path
from core.logging import configure_logging, get_logger
from core.queue import redis_conn
from services.whoop.config import sync_queue

configure_logging()
logger = get_logger(__name__)

if __name__ == "__main__":
    worker_name = f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    logger.info("worker_starting", worker_name=worker_name)
    worker = Worker([sync_queue], connection=redis_conn, name=worker_name)
    # No RQ scheduler: it polls Redis every second, which exhausts Upstash's free
    # command quota (Oct 2026 outage). Sync retries are immediate, so nothing needs scheduling.
    worker.work()
