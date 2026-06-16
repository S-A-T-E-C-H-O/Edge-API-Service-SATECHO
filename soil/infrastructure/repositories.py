from typing import List

from soil.domain.entities import SoilReading
from soil.infrastructure.models import SoilReading as SoilReadingModel


class SoilReadingRepository:

    @staticmethod
    def save(reading: SoilReading) -> SoilReading:
        row = SoilReadingModel.create(
            device_id=reading.device_id,
            farm_id=reading.farm_id,
            zone_id=reading.zone_id,
            moisture=reading.moisture,
            ec=reading.ec,
            ph=reading.ph,
            temperature=reading.temperature,
            recorded_at=reading.recorded_at,
            is_valid=reading.is_valid,
            synced=False,
            ambient_temperature=reading.ambient_temperature,
            security_pir_status=reading.security_pir_status,
        )
        reading.id = row.id
        return reading

    @staticmethod
    def find_unsynced(limit: int = 50) -> List[SoilReadingModel]:
        return list(
            SoilReadingModel.select()
            .where((SoilReadingModel.synced == False) & (SoilReadingModel.is_valid == True))
            .order_by(SoilReadingModel.recorded_at)
            .limit(limit)
        )

    @staticmethod
    def mark_synced(ids: List[int]) -> None:
        if not ids:
            return
        SoilReadingModel.update(synced=True).where(SoilReadingModel.id.in_(ids)).execute()