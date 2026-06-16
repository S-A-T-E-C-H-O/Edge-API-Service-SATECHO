from typing import Optional

import peewee

from iam.domain.entities import Device
from iam.infrastructure.models import Device as DeviceModel


class DeviceRepository:

    @staticmethod
    def find_by_id_and_api_key(device_id: int, api_key: str) -> Optional[Device]:
        try:
            row = DeviceModel.get(
                (DeviceModel.device_id == device_id) & (DeviceModel.api_key == api_key)
            )
            return Device(row.device_id, row.farm_id, row.api_key, row.created_at)
        except peewee.DoesNotExist:
            return None

    @staticmethod
    def get_or_create_test_device() -> Device:
        row, _ = DeviceModel.get_or_create(
            device_id=5,
            defaults={
                "farm_id": 1,
                "api_key": "test-sensor-key-123",
                "created_at": "2026-06-15T00:00:00Z",
            },
        )
        return Device(row.device_id, row.farm_id, row.api_key, row.created_at)