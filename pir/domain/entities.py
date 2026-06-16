from datetime import datetime
from enum import Enum


class PirClassification(str, Enum):
    WIND   = "WIND"
    ANIMAL = "ANIMAL"
    PERSON = "PERSON"


class PirEvent:
    """Aggregate root representing a single PIR sensor detection event."""

    def __init__(
        self,
        device_id: int,
        farm_id: int,
        zone_id: int | None,
        pulse_duration_ms: float,
        triggers_per_minute: int,
        classification: PirClassification,
        recorded_at: datetime,
        id: int = None,
    ):
        self.id = id
        self.device_id = device_id
        self.farm_id = farm_id
        self.zone_id = zone_id
        self.pulse_duration_ms = pulse_duration_ms
        self.triggers_per_minute = triggers_per_minute
        self.classification = classification
        self.recorded_at = recorded_at