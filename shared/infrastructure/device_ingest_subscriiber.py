import json
import logging
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from shared.infrastructure import device_tracker
from shared.infrastructure.mqtt_client import get_mqtt_client, register_handler


def _mark_seen_and_drain(device_id: int) -> None:
    device_tracker.mark_seen(device_id)
    from shared.infrastructure.actuator_command_subscriber import drain_pending
    drain_pending(device_id)


logger = logging.getLogger(__name__)

_EDGE_API_KEY = os.getenv("MQTT_EDGE_API_KEY", "edge-shared-secret-change-me")

# Raw topics published by ESP32 devices. The zone may be omitted, embedded in
# each payload, or included in the topic with /zones/{zoneId}/.
_TOPIC_RAW_SOIL = "agrosafe/raw/+/+/soil/reading"
_TOPIC_RAW_SECURITY = "agrosafe/raw/+/+/security/event"
_TOPIC_RAW_ZONE_SOIL = "agrosafe/raw/+/+/zones/+/soil/reading"
_TOPIC_RAW_ZONE_SECURITY = "agrosafe/raw/+/+/zones/+/security/event"

# Fallback only. Prefer zone_id/zoneId from payload or /zones/{zoneId}/ topic.
_DEFAULT_ZONE_ID = int(os.getenv("EDGE_ZONE_ID", "1"))

_METRIC_MAP = {
    "humidity_fc28": "moisture",
    "salinity_hr202l": "ec",
    "ambient_temp_dht11": "ambient_temperature",
    "soil_temp_ds18b20": "temperature",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_ids(topic: str) -> tuple[str, str]:
    """Return (farm_id, device_id) from agrosafe/raw/{farm}/{device}/..."""
    parts = topic.split("/")
    return parts[2], parts[3]


def _zone_from_topic(topic: str) -> int | None:
    """Return zone_id from agrosafe/raw/{farm}/{device}/zones/{zone}/... if present."""
    parts = topic.split("/")
    try:
        zone_idx = parts.index("zones") + 1
        return int(parts[zone_idx])
    except (ValueError, IndexError, TypeError):
        return None


def _coerce_zone_id(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_zone_id(topic: str, payload_zone=None) -> int:
    """Prefer payload zone metadata, then topic zone, then EDGE_ZONE_ID fallback."""
    return _coerce_zone_id(payload_zone) or _zone_from_topic(topic) or _DEFAULT_ZONE_ID


def _handle_soil(topic: str, payload: str) -> None:
    try:
        readings = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON on raw soil topic %s", topic)
        return

    if not isinstance(readings, list):
        logger.error("Expected array on raw soil topic %s, got %s", topic, type(readings).__name__)
        return

    farm_id, device_id = _extract_ids(topic)
    _mark_seen_and_drain(int(device_id))
    metrics: dict = {}
    timestamp = _now_iso()
    zone_id = _resolve_zone_id(topic)

    for reading in readings:
        metric_type = reading.get("metricType", "")
        field = _METRIC_MAP.get(metric_type)
        if field:
            metrics[field] = reading.get("value")
        if reading.get("timestamp"):
            timestamp = reading["timestamp"]
        zone_id = _resolve_zone_id(
            topic,
            reading.get("zone_id") or reading.get("zoneId") or zone_id,
        )

    out_payload = json.dumps({
        "api_key": _EDGE_API_KEY,
        "zone_id": zone_id,
        "moisture": metrics.get("moisture"),
        "ec": metrics.get("ec"),
        "ph": None,
        "temperature": metrics.get("temperature"),
        "ambient_temperature": metrics.get("ambient_temperature"),
        "created_at": timestamp,
    })

    out_topic = f"agrosafe/{farm_id}/devices/{device_id}/soil/reading"
    client = get_mqtt_client()

    if not client.is_connected():
        _persist_soil_fallback(int(device_id), int(farm_id), zone_id, metrics, timestamp)
        logger.warning("MQTT not connected - soil reading buffered locally (topic=%s)", out_topic)
        return

    info = client.publish(out_topic, out_payload, qos=1)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error(
            "Soil relay publish failed (topic=%s): %s - buffering locally",
            out_topic,
            mqtt.error_string(info.rc),
        )
        _persist_soil_fallback(int(device_id), int(farm_id), zone_id, metrics, timestamp)
    else:
        logger.debug("Soil reading relayed raw-to-back: %s", out_topic)


def _persist_soil_fallback(device_id: int, farm_id: int, zone_id: int, metrics: dict, timestamp: str) -> None:
    from dateutil.parser import parse
    from soil.domain.entities import SoilReading
    from soil.infrastructure.repositories import SoilReadingRepository
    from shared.infrastructure.database import db

    try:
        recorded_at = parse(timestamp)
    except (ValueError, TypeError):
        recorded_at = datetime.now(timezone.utc)

    db.connect(reuse_if_open=True)
    try:
        reading = SoilReading(
            device_id, farm_id, zone_id,
            metrics.get("moisture") or 0.0, metrics.get("ec") or 0.0, 7.0,
            metrics.get("temperature") or 0.0, recorded_at,
            ambient_temperature=metrics.get("ambient_temperature"),
        )
        SoilReadingRepository.save(reading)
    finally:
        db.close()


def _handle_security(topic: str, payload: str) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON on raw security topic %s", topic)
        return

    farm_id, device_id = _extract_ids(topic)
    _mark_seen_and_drain(int(device_id))

    from pir.domain.services import PirClassificationService

    pulse_duration_ms = data.get("pulse_duration_ms", 0)
    triggers_per_minute = data.get("triggers_per_minute", 1)
    classification = PirClassificationService.classify(pulse_duration_ms, triggers_per_minute)
    recorded_at = data.get("detectedAt", _now_iso())
    zone_id = _resolve_zone_id(topic, data.get("zone_id") or data.get("zoneId"))

    out_payload = json.dumps({
        "api_key": _EDGE_API_KEY,
        "zone_id": zone_id,
        "pulse_duration_ms": pulse_duration_ms,
        "triggers_per_minute": triggers_per_minute,
        "classification": classification.value,
        "recorded_at": recorded_at,
    })

    out_topic = f"agrosafe/{farm_id}/devices/{device_id}/security/event"
    client = get_mqtt_client()

    if not client.is_connected():
        _persist_security_fallback(
            int(device_id), int(farm_id), zone_id, pulse_duration_ms,
            triggers_per_minute, classification, recorded_at,
        )
        logger.warning("MQTT not connected - security event buffered locally (topic=%s)", out_topic)
        return

    info = client.publish(out_topic, out_payload, qos=1)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error(
            "Security relay publish failed (topic=%s): %s - buffering locally",
            out_topic,
            mqtt.error_string(info.rc),
        )
        _persist_security_fallback(
            int(device_id), int(farm_id), zone_id, pulse_duration_ms,
            triggers_per_minute, classification, recorded_at,
        )
    else:
        logger.debug("Security event relayed raw-to-back: %s - classification=%s", out_topic, classification.value)


def _persist_security_fallback(device_id: int, farm_id: int, zone_id: int, pulse_duration_ms,
                               triggers_per_minute, classification, recorded_at: str) -> None:
    from dateutil.parser import parse
    from pir.domain.entities import PirEvent
    from pir.infrastructure.repositories import PirEventRepository
    from shared.infrastructure.database import db

    try:
        ts = parse(recorded_at)
    except (ValueError, TypeError):
        ts = datetime.now(timezone.utc)

    db.connect(reuse_if_open=True)
    try:
        event = PirEvent(
            device_id, farm_id, zone_id, float(pulse_duration_ms),
            int(triggers_per_minute), classification, ts,
        )
        PirEventRepository.save(event)
    finally:
        db.close()


def start() -> None:
    """Subscribe to raw ESP32 topics. Call once at app startup."""
    register_handler(_TOPIC_RAW_SOIL, _handle_soil)
    register_handler(_TOPIC_RAW_SECURITY, _handle_security)
    register_handler(_TOPIC_RAW_ZONE_SOIL, _handle_soil)
    register_handler(_TOPIC_RAW_ZONE_SECURITY, _handle_security)
    logger.info(
        "Device ingest subscriber started - topics=%s, %s, %s, %s",
        _TOPIC_RAW_SOIL, _TOPIC_RAW_SECURITY, _TOPIC_RAW_ZONE_SOIL, _TOPIC_RAW_ZONE_SECURITY,
    )
