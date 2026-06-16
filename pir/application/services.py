from pir.domain.entities import PirEvent
from pir.domain.services import PirClassificationService
from pir.infrastructure.repositories import PirEventRepository
from pir.infrastructure.mqtt_publisher import PirEventMqttPublisher
from iam.infrastructure.repositories import DeviceRepository


class PirEventApplicationService:
    """Orchestrates: auth → classify → persist locally → publish to MQTT."""

    def __init__(self):
        self.classification_service = PirClassificationService()
        self.event_repository       = PirEventRepository()
        self.publisher              = PirEventMqttPublisher()
        self.device_repository      = DeviceRepository()

    def record_event(
        self,
        device_id: int,
        farm_id: int,
        zone_id: int | None,
        pulse_duration_ms: float,
        triggers_per_minute: int,
        recorded_at: str | None,
        api_key: str,
    ) -> PirEvent:
        """Validate device, classify PIR signal, save locally, publish to MQTT.

        Raises:
            ValueError: If device credentials are invalid or signal values are out of range.
        """
        if not self.device_repository.find_by_id_and_api_key(device_id, api_key):
            raise ValueError("Device not found or invalid API key")

        event = self.classification_service.create_event(
            device_id, farm_id, zone_id,
            pulse_duration_ms, triggers_per_minute, recorded_at,
        )
        saved = self.event_repository.save(event)
        self.publisher.publish(saved)
        return saved