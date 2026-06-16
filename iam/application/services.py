from typing import Optional

from iam.domain.entities import Device
from iam.domain.services import AuthService
from iam.infrastructure.repositories import DeviceRepository


class AuthApplicationService:

    def __init__(self):
        self.device_repository = DeviceRepository()
        self.auth_service = AuthService()

    def authenticate(self, device_id: int, api_key: str) -> bool:
        device: Optional[Device] = self.device_repository.find_by_id_and_api_key(device_id, api_key)
        return self.auth_service.authenticate(device)

    def get_or_create_test_device(self) -> Device:
        return self.device_repository.get_or_create_test_device()