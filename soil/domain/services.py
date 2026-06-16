from datetime import datetime, timezone

from dateutil.parser import parse

from soil.domain.entities import SoilReading


class SoilReadingService:
    """Domain service: validates raw sensor values and constructs a SoilReading entity."""

    @staticmethod
    def create_reading(
        device_id: int,
        farm_id: int,
        zone_id: int | None,
        moisture: float,
        ec: float,
        ph: float,
        temperature: float,
        recorded_at: str | None,
        ambient_temperature: float | None = None,
        security_pir_status: str | None = None,
    ) -> SoilReading:
        """Validate sensor data and return a transient SoilReading.

        Raises:
            ValueError: If any sensor value is outside its physical range,
                or if recorded_at is not a valid ISO 8601 string.
        """
        try:
            moisture = float(moisture)
            ec = float(ec)
            ph = float(ph)
            temperature = float(temperature)
            if ambient_temperature is not None:
                ambient_temperature = float(ambient_temperature)
        except (TypeError, ValueError):
            raise ValueError("Sensor values must be numeric")

        if not (0 <= moisture <= 100):
            raise ValueError(f"moisture {moisture} out of range [0, 100]")
        if not (0 <= ec <= 20):
            raise ValueError(f"ec {ec} out of range [0, 20]")
        if not (0 <= ph <= 14):
            raise ValueError(f"ph {ph} out of range [0, 14]")
        if not (-10 <= temperature <= 60):
            raise ValueError(f"temperature {temperature} out of range [-10, 60]")

        if recorded_at:
            try:
                ts = parse(recorded_at).astimezone(timezone.utc)
            except (ValueError, TypeError):
                raise ValueError("recorded_at must be a valid ISO 8601 timestamp")
        else:
            ts = datetime.now(timezone.utc)

        return SoilReading(
            device_id, farm_id, zone_id, moisture, ec, ph, temperature, ts,
            ambient_temperature=ambient_temperature,
            security_pir_status=security_pir_status,
        )