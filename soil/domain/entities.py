from datetime import datetime


class SoilReading:
    """Aggregate root representing a single soil-sensor reading."""

    def __init__(
        self,
        device_id: int,
        farm_id: int,
        zone_id: int | None,
        moisture: float,
        ec: float,
        ph: float,
        temperature: float,
        recorded_at: datetime,
        is_valid: bool = True,
        ambient_temperature: float | None = None,
        security_pir_status: str | None = None,
        id: int = None,
    ):
        self.id = id
        self.device_id = device_id
        self.farm_id = farm_id
        self.zone_id = zone_id
        self.moisture = moisture
        self.ec = ec
        self.ph = ph
        self.temperature = temperature
        self.recorded_at = recorded_at
        self.is_valid = is_valid
        self.ambient_temperature = ambient_temperature
        self.security_pir_status = security_pir_status