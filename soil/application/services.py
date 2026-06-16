import logging
from datetime import datetime, timezone

from soil.domain.entities import SoilReading
from soil.domain.services import SoilReadingService
from soil.infrastructure.repositories import SoilReadingRepository
from soil.infrastructure.mqtt_publisher import SoilReadingMqttPublisher
from iam.infrastructure.repositories import DeviceRepository

logger = logging.getLogger(__name__)

# consecutive invalid count per device_id; module-level survives across requests
_consecutive_invalid_counts: dict[int, int] = {}
_DEGRADATION_THRESHOLD = 3


class SoilReadingApplicationService:
    """Orchestrates: auth → validate → persist locally → publish to MQTT."""

    def __init__(self):
        self.reading_service = SoilReadingService()
        self.reading_repository = SoilReadingRepository()
        self.publisher = SoilReadingMqttPublisher()
        self.device_repository = DeviceRepository()

    def record_reading(
        self,
        device_id: int,
        farm_id: int,
        zone_id: int | None,
        moisture: float,
        ec: float,
        ph: float,
        temperature: float,
        recorded_at: str | None,
        api_key: str,
        ambient_temperature: float | None = None,
        security_pir_status: str | None = None,
    ) -> SoilReading:
        """Validate device, create reading, save locally, publish to MQTT.

        Raises:
            ValueError: If device credentials are invalid or sensor data is out of range.
        """
        if not self.device_repository.find_by_id_and_api_key(device_id, api_key):
            raise ValueError("Device not found or invalid API key")

        try:
            reading = self.reading_service.create_reading(
                device_id, farm_id, zone_id, moisture, ec, ph, temperature, recorded_at,
                ambient_temperature=ambient_temperature,
                security_pir_status=security_pir_status,
            )
            saved = self.reading_repository.save(reading)
            _consecutive_invalid_counts[device_id] = 0
            self.publisher.publish(saved)
            return saved

        except ValueError as exc:
            count = _consecutive_invalid_counts.get(device_id, 0) + 1
            _consecutive_invalid_counts[device_id] = count
            logger.warning(
                "Invalid reading from device %s (consecutive=%d): %s",
                device_id, count, exc,
            )
            if count >= _DEGRADATION_THRESHOLD:
                logger.error(
                    "SENSOR DEGRADATION: device %s has %d consecutive invalid readings — check sensor",
                    device_id, count,
                )

            # persist raw values for audit (is_valid=False, not synced to cloud)
            try:
                m = float(moisture) if moisture is not None else 0.0
                e = float(ec) if ec is not None else 0.0
                p = float(ph) if ph is not None else 0.0
                t = float(temperature) if temperature is not None else 0.0
                at = float(ambient_temperature) if ambient_temperature is not None else None
            except (TypeError, ValueError):
                m = e = p = t = 0.0
                at = None
            raw = SoilReading(
                device_id, farm_id, zone_id, m, e, p, t,
                datetime.now(timezone.utc), is_valid=False,
                ambient_temperature=at,
                security_pir_status=security_pir_status,
            )
            self.reading_repository.save(raw)
            raise