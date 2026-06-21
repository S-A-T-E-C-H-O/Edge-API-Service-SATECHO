import json
import logging
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from iam.infrastructure.repositories import DeviceRepository
from shared.infrastructure.device_tracker import mark_seen
from shared.infrastructure.mqtt_client import get_mqtt_client, register_handler

logger = logging.getLogger(__name__)

# Raw topics published by ESP32 (no zone_id, embedded format)
_TOPIC_RAW_SOIL     = "agrosafe/raw/+/+/soil/reading"
_TOPIC_RAW_SECURITY = "agrosafe/raw/+/+/security/event"

# Default zone_id — ESP32-SATECHO-001 is installed in zone 1
_DEFAULT_ZONE_ID = 1

_METRIC_MAP = {
    "humidity_fc28":      "moisture",
    "salinity_hr202l":    "ec",
    "ambient_temp_dht11": "ambient_temperature",
    "soil_temp_ds18b20":  "temperature",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_device(device_id: int, farm_id: int, mac: str) -> None:
    """Zero-touch provisioning: register device on first contact if unknown."""
    DeviceRepository.find_or_create_by_mac(device_id, farm_id, mac)


def _extract_ids(topic: str) -> tuple[str, str]:
    """Return (farm_id, device_id) from agrosafe/raw/{farm}/{device}/..."""
    parts = topic.split("/")
    return parts[2], parts[3]


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
    metrics: dict = {}
    timestamp = _now_iso()
    mac = ""

    for r in readings:
        metric_type = r.get("metricType", "")
        field = _METRIC_MAP.get(metric_type)
        if field:
            metrics[field] = r.get("value")
        if r.get("timestamp"):
            timestamp = r["timestamp"]
        if not mac and r.get("mac_address"):
            mac = r["mac_address"]

    if not mac:
        logger.warning("Soil payload from device %s has no mac_address — dropping", device_id)
        return

    _ensure_device(int(device_id), int(farm_id), mac)
    mark_seen(int(device_id))

    out_payload = json.dumps({
        "api_key":             mac,
        "zone_id":             _DEFAULT_ZONE_ID,
        "moisture":            metrics.get("moisture"),
        "ec":                  metrics.get("ec"),
        "ph":                  None,
        "temperature":         metrics.get("temperature"),
        "ambient_temperature": metrics.get("ambient_temperature"),
        "created_at":          timestamp,
    })

    out_topic = f"agrosafe/{farm_id}/devices/{device_id}/soil/reading"
    client = get_mqtt_client()
    info = client.publish(out_topic, out_payload, qos=1)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error("Soil relay publish failed (topic=%s): %s", out_topic, mqtt.error_string(info.rc))
    else:
        logger.debug("Soil reading relayed raw→back: %s", out_topic)


def _handle_security(topic: str, payload: str) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON on raw security topic %s", topic)
        return

    farm_id, device_id = _extract_ids(topic)
    mac = data.get("mac_address", "")
    classification = data.get("classification", "UNKNOWN")

    if not mac:
        logger.warning("Security payload from device %s has no mac_address — dropping", device_id)
        return

    _ensure_device(int(device_id), int(farm_id), mac)
    mark_seen(int(device_id))

    out_payload = json.dumps({
        "api_key":              mac,
        "zone_id":              _DEFAULT_ZONE_ID,
        "pulse_duration_ms":    0,
        "triggers_per_minute":  1 if data.get("security_pir_status") == "DETECTED" else 0,
        "classification":       classification,
        "recorded_at":          data.get("detectedAt", _now_iso()),
    })

    out_topic = f"agrosafe/{farm_id}/devices/{device_id}/security/event"
    client = get_mqtt_client()
    info = client.publish(out_topic, out_payload, qos=1)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error("Security relay publish failed (topic=%s): %s", out_topic, mqtt.error_string(info.rc))
    else:
        logger.debug("Security event relayed raw→back: %s — classification=%s", out_topic, classification)


def start() -> None:
    """Subscribe to raw ESP32 topics. Call once at app startup."""
    register_handler(_TOPIC_RAW_SOIL, _handle_soil)
    register_handler(_TOPIC_RAW_SECURITY, _handle_security)
    logger.info(
        "Device ingest subscriber started — topics=%s, %s",
        _TOPIC_RAW_SOIL, _TOPIC_RAW_SECURITY,
    )