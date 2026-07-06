import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("CLOUD_API_URL", "http://localhost:8080")
_EDGE_API_KEY = (
    os.getenv("MQTT_EDGE_API_KEY")
    or os.getenv("EDGE_API_KEY")
    or os.getenv("CLOUD_API_TOKEN")
    or "edge-shared-secret-change-me"
)
_TIMEOUT = 10  # seconds


def _headers() -> dict:
    return {"X-Device-Api-Key": _EDGE_API_KEY, "Content-Type": "application/json"}


def _enabled() -> bool:
    if not _EDGE_API_KEY:
        logger.debug("Edge API key not set - cloud sync disabled")
        return False
    return True


def _post_json(url: str, body: dict) -> bool:
    body = {**body, "api_key": _EDGE_API_KEY}
    try:
        resp = requests.post(url, json=body, headers=_headers(), timeout=_TIMEOUT)
        if resp.status_code in (200, 201):
            return True
        logger.warning("Cloud POST failed - HTTP %s: %s", resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as exc:
        logger.warning("Cloud POST error: %s", exc)
        return False


def post_batch_telemetry(items: list[dict]) -> bool:
    """POST grouped soil readings to /api/v1/edge/devices/{deviceId}/soil-readings."""
    if not _enabled() or not items:
        return False

    metric_fields = {
        "SOIL_MOISTURE": "moisture",
        "ELECTRICAL_CONDUCTIVITY": "ec",
        "SOIL_PH": "ph",
        "SOIL_TEMPERATURE": "temperature",
    }
    grouped: dict[tuple[int, int | None, str], dict] = {}
    for item in items:
        field = metric_fields.get(str(item.get("metricType")))
        if not field:
            logger.warning("Skipping unsupported metric type: %s", item.get("metricType"))
            continue
        key = (int(item["deviceId"]), item.get("zoneId"), item["timestamp"])
        body = grouped.setdefault(
            key,
            {"zone_id": item.get("zoneId"), "created_at": item["timestamp"]},
        )
        body[field] = item.get("value")

    all_ok = True
    for (device_id, _zone_id, _timestamp), body in grouped.items():
        url = f"{_BASE_URL}/api/v1/edge/devices/{device_id}/soil-readings"
        all_ok = _post_json(url, body) and all_ok
    if all_ok:
        logger.debug("Batch telemetry sync OK - %d grouped readings", len(grouped))
    return all_ok


def post_heartbeat(device_id: int, battery_level: float | None = None) -> bool:
    """POST heartbeat to /api/v1/edge/devices/{deviceId}/heartbeat."""
    if not _enabled():
        return False
    url = f"{_BASE_URL}/api/v1/edge/devices/{device_id}/heartbeat"
    body: dict[str, Any] = {"battery_level": battery_level}
    ok = _post_json(url, body)
    if ok:
        logger.debug("Heartbeat OK - device %s", device_id)
    return ok


_CONFIDENCE_BY_CLASSIFICATION = {"PERSON": 95.0, "ANIMAL": 70.0, "WIND": 40.0}


def post_security_event(
    device_id: int,
    farm_id: int,
    zone_id: int | None,
    classification: str,
    triggers_per_minute: int,
    pulse_duration_ms: float,
    detected_at: str,
) -> bool:
    """POST a classified PIR event to /api/v1/edge/farms/{farmId}/devices/{deviceId}/security-events."""
    if not _enabled():
        return False
    url = f"{_BASE_URL}/api/v1/edge/farms/{farm_id}/devices/{device_id}/security-events"
    body = {
        "zone_id": zone_id,
        "classification": classification,
        "confidence_level": _CONFIDENCE_BY_CLASSIFICATION.get(classification, 50.0),
        "recorded_at": detected_at,
        "location_description": f"Zone {zone_id}" if zone_id is not None else None,
        "triggers_per_minute": triggers_per_minute,
        "pulse_duration_ms": pulse_duration_ms,
    }
    ok = _post_json(url, body)
    if ok:
        logger.debug("Security event sync OK - device %s classification=%s", device_id, classification)
    return ok


def post_actuator_log(
    device_id: int,
    zone_id: int | None,
    actuator_type: str,
    action: str,
    command_source: str,
    success: bool,
    response_message: str,
) -> bool:
    """POST actuator command log to /api/v1/edge/devices/{deviceId}/actuator-logs."""
    if not _enabled():
        return False
    url = f"{_BASE_URL}/api/v1/edge/devices/{device_id}/actuator-logs"
    body = {
        "zone_id": zone_id,
        "actuator_type": actuator_type,
        "action": action,
        "command_source": command_source,
        "success": success,
        "response_message": response_message,
    }
    ok = _post_json(url, body)
    if ok:
        logger.debug("Actuator log posted - device %s %s %s", device_id, actuator_type, action)
    return ok
