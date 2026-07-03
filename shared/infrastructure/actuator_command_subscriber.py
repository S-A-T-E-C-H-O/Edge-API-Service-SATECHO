"""Actuator command subscriber with an offline buffer (EP-005-TS007).

ESP32 devices are already subscribed directly to the shared MQTT broker on the
same actuator command topic, so under normal conditions delivery does not
depend on the Edge. What the Edge adds is resilience: if a device has not been
seen recently (device_tracker.is_online() is False), the command cannot be
guaranteed to reach it, so it is buffered here and re-published the moment the
device is observed online again (see drain_pending(), called from
device_ingest_subscriiber after every mark_seen()).
"""

import json
import logging
import threading

import paho.mqtt.client as mqtt

from shared.infrastructure import cloud_client, device_tracker
from shared.infrastructure.mqtt_client import get_mqtt_client, register_handler

logger = logging.getLogger(__name__)

_TOPIC_ACTUATOR_COMMAND = "agrosafe/+/devices/+/actuator/command"

_pending_commands: dict[int, list[tuple[str, str, object, str, str]]] = {}
_lock = threading.Lock()


def _extract_device_id(topic: str) -> int:
    """Return device_id from agrosafe/{farmId}/devices/{deviceId}/actuator/command."""
    return int(topic.split("/")[3])


def _handle_actuator_command(topic: str, payload: str) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON on actuator command topic %s", topic)
        return

    try:
        device_id = _extract_device_id(topic)
    except (IndexError, ValueError):
        logger.error("Cannot parse device_id from actuator topic %s", topic)
        return

    zone_id = data.get("zone_id")
    action = data.get("action", "UNKNOWN")
    source = data.get("source", "manual")

    if device_tracker.is_online(device_id):
        _deliver(topic, payload, device_id, zone_id, action, source)
    else:
        with _lock:
            _pending_commands.setdefault(device_id, []).append((topic, payload, zone_id, action, source))
        logger.info("Device %s offline — buffered actuator command action=%s", device_id, action)


def _deliver(topic: str, payload: str, device_id: int, zone_id, action: str, source: str) -> None:
    client = get_mqtt_client()
    info = client.publish(topic, payload, qos=1)
    success = info.rc == mqtt.MQTT_ERR_SUCCESS
    if not success:
        logger.error("Actuator command republish failed (topic=%s): %s", topic, mqtt.error_string(info.rc))
    cloud_client.post_actuator_log(
        device_id, zone_id, "VALVE", action, source, success,
        "" if success else mqtt.error_string(info.rc),
    )


def drain_pending(device_id: int) -> None:
    """Flush any buffered actuator commands for a device that just came back online."""
    with _lock:
        pending = _pending_commands.pop(device_id, [])
    for topic, payload, zone_id, action, source in pending:
        logger.info("Draining buffered actuator command for device %s: action=%s", device_id, action)
        _deliver(topic, payload, device_id, zone_id, action, source)


def start() -> None:
    """Subscribe to actuator command topics. Call once at app startup."""
    register_handler(_TOPIC_ACTUATOR_COMMAND, _handle_actuator_command)
    logger.info("Actuator command subscriber started — topic=%s", _TOPIC_ACTUATOR_COMMAND)
