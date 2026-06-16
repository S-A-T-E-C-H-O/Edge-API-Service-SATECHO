import json
import logging
import os

import paho.mqtt.client as mqtt

from soil.domain.entities import SoilReading
from shared.infrastructure.mqtt_client import get_mqtt_client

logger = logging.getLogger(__name__)

_EDGE_API_KEY = os.getenv("MQTT_EDGE_API_KEY", "edge-shared-secret-change-me")


class SoilReadingMqttPublisher:
    """Publishes a validated SoilReading to agrosafe/{farmId}/devices/{deviceId}/soil/reading."""

    @staticmethod
    def publish(reading: SoilReading) -> None:
        topic = f"agrosafe/{reading.farm_id}/devices/{reading.device_id}/soil/reading"
        payload = json.dumps({
            "api_key": _EDGE_API_KEY,
            "zone_id": reading.zone_id,
            "moisture": reading.moisture,
            "ec": reading.ec,
            "ph": reading.ph,
            "temperature": reading.temperature,
            "ambient_temperature": reading.ambient_temperature,
            "security_pir_status": reading.security_pir_status,
            "created_at": reading.recorded_at.isoformat(),
        })
        client = get_mqtt_client()
        info = client.publish(topic, payload, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(
                "Soil MQTT publish failed (topic=%s): %s",
                topic, mqtt.error_string(info.rc),
            )
        else:
            logger.debug("Soil reading published to %s", topic)