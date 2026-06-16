from datetime import datetime


class Device:
    """Aggregate root representing a registered edge sensor device."""

    def __init__(self, device_id: int, farm_id: int, api_key: str, created_at: datetime):
        self.device_id = device_id
        self.farm_id = farm_id
        self.api_key = api_key
        self.created_at = created_at