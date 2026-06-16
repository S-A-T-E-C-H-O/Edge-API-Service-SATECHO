import json
import logging
import os

import paho.mqtt.client as mqtt

from pir.domain.entities import PirEvent
from shared.infrastructure.mqtt_client import get_mqtt_client

logger = logging.getLogger(__name__)

_EDGE_API_KEY = os.getenv("MQTT_EDGE_API_KEY", "edge-shared-secret-change-me")


class PirEventMqttPublisher:
    """Publishes a classified PirEvent to agrosafe/{farmId}/devices/{deviceId}/security/event."""

    @staticmethod
    def publish(event: PirEvent) -> None:
        # Topic matches backend mqtt.topics.security = "agrosafe/+/devices/+/security/event"
        topic = f"agrosafe/{event.farm_id}/devices/{event.device_id}/security/event"
        payload = json.dumps({
            "api_key": _EDGE_API_KEY,
            "zone_id": event.zone_id,
            "pulse_duration_ms": event.pulse_duration_ms,
            "triggers_per_minute": event.triggers_per_minute,
            "classification": event.classification.value,
            "recorded_at": event.recorded_at.isoformat(),
        })
        client = get_mqtt_client()
        info = client.publish(topic, payload, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(
                "PIR MQTT publish failed (topic=%s): %s",
                topic, mqtt.error_string(info.rc),
            )
        else:
            logger.debug("PIR event published to %s — classification=%s", topic, event.classification.value)