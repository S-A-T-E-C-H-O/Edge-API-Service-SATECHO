"""Actuator command subscriber with an offline buffer (EP-005-TS007).

ESP32 devices are already subscribed directly to the shared MQTT broker on the
same actuator command topic, so under normal conditions delivery does not
depend on the Edge. What the Edge adds is resilience: if a device has not been
seen recently (device_tracker.is_online() is False), the command cannot be
guaranteed to reach it, so it is buffered here and re-published the moment the
device is observed online again (see drain_pending(), called from
device_ingest_subscriiber after every mark_seen()).

Anti-echo design: the Edge subscribes to the same topic the backend publishes
on, and the broker echoes every publish back to all subscribers — including
this one. Re-publishing a live command verbatim therefore created an infinite
command storm (subscriber → publish → broker echo → subscriber → ...).
The fix is twofold:
  * When the device is ONLINE the Edge does NOT re-publish at all — the device
    already received the broker's original delivery. The Edge only records the
    command (cloud actuator log).
  * When draining the offline buffer the Edge must publish (the device missed
    the original), so the payload is tagged with ``edge_relayed: true`` and the
    handler discards any message carrying that marker. The ESP32 firmware reads
    only the fields it knows (action / duration_minutes), so the extra marker
    is harmless on the device side.
"""

import json
import logging
import threading

import paho.mqtt.client as mqtt

from shared.infrastructure import cloud_client, device_tracker
from shared.infrastructure.mqtt_client import get_mqtt_client, register_handler

logger = logging.getLogger(__name__)

_TOPIC_ACTUATOR_COMMAND = "agrosafe/+/devices/+/actuator/command"

# Marker injected into payloads re-published by this module. Messages carrying
# it are our own broker echoes and must never be processed again.
_RELAY_MARKER = "edge_relayed"

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

    if isinstance(data, dict) and data.get(_RELAY_MARKER):
        logger.debug("Ignoring own relayed actuator command echo (topic=%s)", topic)
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
        # The device is subscribed to this same topic and already received the
        # broker's original delivery — re-publishing would only echo back to
        # this subscriber. Observe and record, nothing else.
        _log_command(device_id, zone_id, action, source, True, "")
        logger.debug(
            "Actuator command observed for online device %s: action=%s", device_id, action
        )
    else:
        with _lock:
            _pending_commands.setdefault(device_id, []).append(
                (topic, payload, zone_id, action, source)
            )
        logger.info("Device %s offline — buffered actuator command action=%s", device_id, action)


def _log_command(device_id: int, zone_id, action: str, source: str,
                 success: bool, message: str) -> None:
    cloud_client.post_actuator_log(
        device_id, zone_id, "VALVE", action, source, success, message,
    )


def _republish_relayed(topic: str, payload: str, device_id: int, zone_id,
                       action: str, source: str) -> None:
    """Publish a buffered command back to the device, tagged so our own
    subscription discards the broker echo."""
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            data = {"action": action}
    except json.JSONDecodeError:
        data = {"action": action}
    data[_RELAY_MARKER] = True

    client = get_mqtt_client()
    info = client.publish(topic, json.dumps(data), qos=1)
    success = info.rc == mqtt.MQTT_ERR_SUCCESS
    if not success:
        logger.error(
            "Actuator command republish failed (topic=%s): %s",
            topic, mqtt.error_string(info.rc),
        )
    _log_command(
        device_id, zone_id, action, source, success,
        "" if success else mqtt.error_string(info.rc),
    )


def drain_pending(device_id: int) -> None:
    """Flush any buffered actuator commands for a device that just came back online."""
    with _lock:
        pending = _pending_commands.pop(device_id, [])
    for topic, payload, zone_id, action, source in pending:
        logger.info("Draining buffered actuator command for device %s: action=%s", device_id, action)
        _republish_relayed(topic, payload, device_id, zone_id, action, source)


def start() -> None:
    """Subscribe to actuator command topics. Call once at app startup."""
    register_handler(_TOPIC_ACTUATOR_COMMAND, _handle_actuator_command)
    logger.info("Actuator command subscriber started — topic=%s", _TOPIC_ACTUATOR_COMMAND)
