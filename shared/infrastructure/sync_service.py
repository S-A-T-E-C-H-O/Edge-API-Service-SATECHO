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


def _sync_pir_once() -> None:
    """Synchronize classified PIR events to the cloud individually (no batching).

    Unlike soil telemetry, a failed PIR sync is not enqueued on the retry queue —
    the event simply stays `synced=False` and is retried on the next periodic cycle.
    """
    from pir.infrastructure.repositories import PirEventRepository

    repo = PirEventRepository()
    db.connect(reuse_if_open=True)
    try:
        rows = repo.find_unsynced(limit=50)
        if not rows:
            return
        synced_ids = []
        for row in rows:
            ok = cloud_client.post_security_event(
                row.device_id, row.farm_id, row.zone_id, row.classification,
                row.triggers_per_minute, row.pulse_duration_ms,
                # UTC "...Z" sin offset — isoformat() en un datetime tz-aware
                # produciría "+00:00Z" (Instant inválido para Jackson en el back).
                row.recorded_at.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            )
            if ok:
                synced_ids.append(row.id)
            else:
                logger.warning("PIR event sync failed (id=%s) — will retry next cycle", row.id)
        if synced_ids:
            repo.mark_synced(synced_ids)
            logger.info("Synced %d PIR events to cloud", len(synced_ids))
    except Exception as exc:
        logger.error("PIR sync error: %s", exc)
    finally:
        db.close()


async def _run_loop() -> None:
    """Async periodic sync loop — soil and PIR sync run concurrently via asyncio.gather()."""
    delay = _SYNC_INTERVAL
    while True:
        await asyncio.sleep(delay)
        try:
            await asyncio.gather(
                asyncio.to_thread(_sync_once),
                asyncio.to_thread(_sync_pir_once),
            )
            delay = _SYNC_INTERVAL
        except Exception as exc:
            logger.error("Unexpected sync error: %s", exc)
            delay = min(delay * 2, 300)


def start() -> None:
    """Start retry queue and register sync loop with the shared async runner."""
    get_retry_queue().start()
    _get_bg_runner().add_task(_run_loop())
    logger.info("Sync service registered — interval=%ds", _SYNC_INTERVAL)