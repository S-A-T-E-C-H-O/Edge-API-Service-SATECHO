from datetime import datetime, timezone
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
    def find_or_create_by_mac(device_id: int, farm_id: int, mac: str) -> Device:
        """Zero-touch provisioning: if device_id is unknown, register it using its
        MAC address as the api_key so it can authenticate on the very next request.
        """
        row, _ = DeviceModel.get_or_create(
            device_id=device_id,
            defaults={
                "farm_id": farm_id,
                "api_key": mac,
                "created_at": datetime.now(timezone.utc),
            },
        )
        return Device(row.device_id, row.farm_id, row.api_key, row.created_at)

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