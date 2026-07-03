from typing import List

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
            synced=False,
        )
        event.id = row.id
        return event

    @staticmethod
    def find_unsynced(limit: int = 50) -> List[PirEventModel]:
        return list(
            PirEventModel.select()
            .where(PirEventModel.synced == False)
            .order_by(PirEventModel.recorded_at)
            .limit(limit)
        )

    @staticmethod
    def mark_synced(ids: List[int]) -> None:
        if not ids:
            return
        PirEventModel.update(synced=True).where(PirEventModel.id.in_(ids)).execute()