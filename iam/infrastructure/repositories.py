import logging
from datetime import datetime, timezone
from typing import Optional

import peewee

from iam.domain.entities import Device
from iam.infrastructure.models import Device as DeviceModel

logger = logging.getLogger(__name__)


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
        """Zero-touch provisioning: register device on first MQTT contact.

        The ESP32 MAC address is used as the api_key — unique per hardware unit,
        no shared secret required. If the device already exists with a different
        api_key (legacy), the stored key is updated to the MAC.
        """
        row, created = DeviceModel.get_or_create(
            device_id=device_id,
            defaults={
                "farm_id": farm_id,
                "api_key": mac,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if created:
            logger.info("Device provisioned — id=%d farm=%d mac=%s", device_id, farm_id, mac)
        elif row.api_key != mac:
            DeviceModel.update(api_key=mac).where(DeviceModel.device_id == device_id).execute()
            row.api_key = mac
            logger.info("Device api_key updated to MAC — id=%d mac=%s", device_id, mac)
        return Device(row.device_id, row.farm_id, row.api_key, row.created_at)