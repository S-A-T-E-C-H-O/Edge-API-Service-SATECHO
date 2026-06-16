"""Sync service: orchestrates cloud sync with retry-queue fallback.

When cloud sync fails, telemetry is already stored locally (SQLite, synced=False).
The retry queue stores lightweight replay tasks that re-attempt batch sync
with exponential backoff, ensuring no data loss during cloud outages.

Both the periodic sync loop and heartbeat run concurrently via asyncio.gather()
in a shared background event-loop thread.
"""

import asyncio
import logging
import os

from shared.infrastructure import cloud_client
from shared.infrastructure.database import db
from shared.infrastructure.heartbeat_service import _get_bg_runner
from shared.infrastructure.retry_queue import get_retry_queue

logger = logging.getLogger(__name__)

_SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))


def _sync_batch(reading_ids: list[int]) -> None:
    """Replay a single batch sync for given reading IDs.

    If the cloud call fails, items remain unsynced in SQLite and will be
    picked up by the next periodic sync cycle.
    """
    from soil.infrastructure.models import SoilReading as SoilReadingModel

    db.connect(reuse_if_open=True)
    try:
        rows = list(SoilReadingModel.select().where(SoilReadingModel.id.in_(reading_ids)))
        if not rows:
            return
        from shared.infrastructure.sync_client import _build_batch_items
        items = _build_batch_items(rows)
        ok = cloud_client.post_batch_telemetry(items)
        if ok:
            SoilReadingModel.update(synced=True).where(SoilReadingModel.id.in_(reading_ids)).execute()
            logger.info("Retry sync OK — %d readings", len(rows))
        else:
            raise RuntimeError("Cloud sync returned non-2xx")
    finally:
        db.close()


def _sync_once() -> None:
    from soil.infrastructure.repositories import SoilReadingRepository

    repo = SoilReadingRepository()
    db.connect(reuse_if_open=True)
    try:
        rows = repo.find_unsynced(limit=50)
        if not rows:
            return
        from shared.infrastructure.sync_client import _build_batch_items
        items = _build_batch_items(rows)
        ok = cloud_client.post_batch_telemetry(items)
        if ok:
            repo.mark_synced([r.id for r in rows])
            logger.info("Synced %d soil readings to cloud", len(rows))
        else:
            logger.warning("Cloud sync failed — enqueuing %d items for retry", len(rows))
            rq = get_retry_queue()
            rq.enqueue(_sync_batch, [r.id for r in rows])
    except Exception as exc:
        logger.error("Sync error: %s", exc)
        try:
            rq = get_retry_queue()
            rq.enqueue(_sync_batch, [r.id for r in rows])
        except Exception:
            pass
    finally:
        db.close()


async def _run_loop() -> None:
    """Async periodic sync loop — runs via asyncio.gather() for concurrency."""
    delay = _SYNC_INTERVAL
    while True:
        await asyncio.sleep(delay)
        try:
            await asyncio.to_thread(_sync_once)
            delay = _SYNC_INTERVAL
        except Exception as exc:
            logger.error("Unexpected sync error: %s", exc)
            delay = min(delay * 2, 300)


def start() -> None:
    """Start retry queue and register sync loop with the shared async runner."""
    get_retry_queue().start()
    _get_bg_runner().add_task(_run_loop())
    logger.info("Sync service registered — interval=%ds", _SYNC_INTERVAL)