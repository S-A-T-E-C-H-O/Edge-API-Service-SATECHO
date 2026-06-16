from pir.domain.entities import PirEvent
from pir.infrastructure.models import PirEvent as PirEventModel


class PirEventRepository:

    @staticmethod
    def save(event: PirEvent) -> PirEvent:
        row = PirEventModel.create(
            device_id=event.device_id,
            farm_id=event.farm_id,
            zone_id=event.zone_id,
            pulse_duration_ms=event.pulse_duration_ms,
            triggers_per_minute=event.triggers_per_minute,
            classification=event.classification.value,
            recorded_at=event.recorded_at,
        )
        event.id = row.id
        return event