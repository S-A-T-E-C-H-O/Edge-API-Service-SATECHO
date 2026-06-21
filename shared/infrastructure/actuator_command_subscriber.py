"""Actuator command subscriber.

Intercepts backend→device actuator commands published to:
    agrosafe/{farm}/devices/{device}/actuator/command

For each command the edge:
1. Logs the command to the cloud via post_actuator_log().
2. Republishes to the embedded raw topic so the ESP32 receives it.
   If the device is offline (no data seen in the last 60 s), the command
   is buffered in memory and replayed when the device comes back online.
"""

import json
import logging

import paho.mqtt.client as mqtt

from shared.infrastructure import cloud_client
from shared.infrastructure.device_tracker import buffer_command, is_online
from shared.infrastructure.mqtt_client import get_mqtt_client, register_handler

logger = logging.getLogger(__name__)

# Backend publishes commands here; edge intercepts
_TOPIC_ACTUATOR_CMD = "agrosafe/+/devices/+/actuator/command"


def _extract_ids(topic: str) -> tuple[str, str]:
    """Return (farm_id, device_id) from agrosafe/{farm}/devices/{device}/actuator/command."""
    parts = topic.split("/")
    return parts[1], parts[3]


def _republish(topic: str, payload: str) -> None:
    """Republish an actuator command to the same topic (device picks it up from broker)."""
    client = get_mqtt_client()
    info = client.publish(topic, payload, qos=1)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error("Actuator relay publish failed (topic=%s): %s", topic, mqtt.error_string(info.rc))
    else:
        logger.debug("Actuator command relayed: %s", topic)


def _handle_actuator_command(topic: str, payload: str) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON on actuator command topic %s", topic)
        return

    farm_id, device_id_str = _extract_ids(topic)
    try:
        device_id = int(device_id_str)
    except ValueError:
        logger.error("Non-integer device_id in topic %s", topic)
        return

    actuator_type  = data.get("actuatorType", "VALVE")
    action         = data.get("action", "UNKNOWN")
    zone_id        = data.get("zoneId")
    command_source = data.get("commandSource", "BACKEND")

    cloud_client.post_actuator_log(
        device_id=device_id,
        zone_id=zone_id,
        actuator_type=actuator_type,
        action=action,
        command_source=command_source,
        success=True,
        response_message="relayed by edge",
    )

    if is_online(device_id):
        _republish(topic, payload)
    else:
        buffer_command(device_id, topic, payload)


def start() -> None:
    """Subscribe to actuator command topics and wire up the drain callback."""
    from shared.infrastructure.device_tracker import set_drain_callback
    set_drain_callback(_republish)

    register_handler(_TOPIC_ACTUATOR_CMD, _handle_actuator_command)
    logger.info("Actuator command subscriber started — topic=%s", _TOPIC_ACTUATOR_CMD)
