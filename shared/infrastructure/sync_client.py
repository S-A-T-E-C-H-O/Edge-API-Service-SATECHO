import logging
import os
import threading
import time

from shared.infrastructure import cloud_client
from shared.infrastructure.database import db

logger = logging.getLogger(__name__)

_SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))


def _build_batch_items(rows) -> list[dict]:
    """Expand each soil reading row into per-metric BatchIngestResource items.

    Uses a list comprehension with a nested generator for the 4 metric types.
    """
    METRICS = [
        ("SOIL_MOISTURE",          "moisture"),
        ("ELECTRICAL_CONDUCTIVITY", "ec"),
        ("SOIL_PH",                 "ph"),
        ("SOIL_TEMPERATURE",        "temperature"),
    ]
    return [
        {
            "deviceId": r.device_id,
            "zoneId": r.zone_id,
            "timestamp": ts,
            "metricType": mt,
            "value": getattr(r, attr),
        }
        for r in rows
        for mt, attr in METRICS
        for ts in [r.recorded_at.strftime("%Y-%m-%dT%H:%M:%S") + "Z"]
    ]


def _sync_once() -> None:
    from soil.infrastructure.repositories import SoilReadingRepository

    repo = SoilReadingRepository()
    db.connect(reuse_if_open=True)
    try:
        rows = repo.find_unsynced(limit=50)
        if not rows:
            return
        items = _build_batch_items(rows)
        ok = cloud_client.post_batch_telemetry(items)
        if ok:
            repo.mark_synced([r.id for r in rows])
            logger.info("Synced %d soil readings to cloud", len(rows))
        else:
            logger.warning("Cloud sync failed — will retry in %ds", _SYNC_INTERVAL)
    except Exception as exc:
        logger.error("Sync error: %s", exc)
    finally:
        db.close()


def _run_loop() -> None:
    delay = _SYNC_INTERVAL
    while True:
        time.sleep(delay)
        try:
            _sync_once()
            delay = _SYNC_INTERVAL
        except Exception as exc:
            logger.error("Unexpected sync error: %s", exc)
            delay = min(delay * 2, 300)


def start() -> None:
    """Start the background sync thread (call once at app startup)."""
    t = threading.Thread(target=_run_loop, name="sync-service", daemon=True)
    t.start()
    logger.info("Sync service started — interval=%ds", _SYNC_INTERVAL)