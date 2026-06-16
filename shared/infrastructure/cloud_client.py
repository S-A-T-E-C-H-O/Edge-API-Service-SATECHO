import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("CLOUD_API_URL", "http://localhost:8080")
_TOKEN = os.getenv("CLOUD_API_TOKEN", "")
_TIMEOUT = 10  # seconds


def _headers() -> dict:
    return {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}


def _enabled() -> bool:
    if not _TOKEN:
        logger.debug("CLOUD_API_TOKEN not set — cloud sync disabled")
        return False
    return True


def post_batch_telemetry(items: list[dict]) -> bool:
    """POST list of BatchIngestResource items to /api/v1/telemetry/batch.
    Returns True on success (HTTP 2xx).
    """
    if not _enabled() or not items:
        return False
    url = f"{_BASE_URL}/api/v1/telemetry/batch"
    try:
        resp = requests.post(url, json=items, headers=_headers(), timeout=_TIMEOUT)
        if resp.status_code in (200, 201):
            logger.debug("Batch telemetry sync OK — %d items", len(items))
            return True
        logger.warning("Batch telemetry sync failed — HTTP %s: %s", resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as exc:
        logger.warning("Batch telemetry sync error: %s", exc)
        return False


def post_heartbeat(device_id: int, battery_level: float | None = None) -> bool:
    """POST heartbeat to /api/v1/devices/{deviceId}/heartbeat.
    Returns True on success.
    """
    if not _enabled():
        return False
    url = f"{_BASE_URL}/api/v1/devices/{device_id}/heartbeat"
    body: dict[str, Any] = {"batteryLevel": battery_level}
    try:
        resp = requests.post(url, json=body, headers=_headers(), timeout=_TIMEOUT)
        if resp.status_code in (200, 201):
            logger.debug("Heartbeat OK — device %s", device_id)
            return True
        logger.warning("Heartbeat failed — HTTP %s", resp.status_code)
        return False
    except requests.RequestException as exc:
        logger.warning("Heartbeat error: %s", exc)
        return False


def post_actuator_log(
    device_id: int,
    zone_id: int | None,
    actuator_type: str,
    action: str,
    command_source: str,
    success: bool,
    response_message: str,
) -> bool:
    """POST actuator command log to /api/v1/actuators/{deviceId}/command.
    Returns True on success.
    """
    if not _enabled():
        return False
    url = f"{_BASE_URL}/api/v1/actuators/{device_id}/command"
    body = {
        "zoneId": zone_id,
        "actuatorType": actuator_type,
        "action": action,
        "commandSource": command_source,
        "success": success,
        "responseMessage": response_message,
    }
    try:
        resp = requests.post(url, json=body, headers=_headers(), timeout=_TIMEOUT)
        if resp.status_code in (200, 201):
            logger.debug("Actuator log posted — device %s %s %s", device_id, actuator_type, action)
            return True
        logger.warning("Actuator log failed — HTTP %s", resp.status_code)
        return False
    except requests.RequestException as exc:
        logger.warning("Actuator log error: %s", exc)
        return False