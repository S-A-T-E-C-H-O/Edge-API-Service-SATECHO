from typing import Optional

from iam.domain.entities import Device


class AuthService:
    """Domain service: a device that exists in the registry is authenticated."""

    @staticmethod
    def authenticate(device: Optional[Device]) -> bool:
        return device is not None