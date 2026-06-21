from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from iam.domain.entities import Device


def _make_device():
    return Device(device_id=1, farm_id=2, api_key="AA:BB:CC:DD:EE:FF", created_at=datetime.now(timezone.utc))


def test_register_missing_field_returns_400(client):
    resp = client.post(
        "/api/v1/devices/register",
        json={"device_id": 1, "farm_id": 2},
    )
    assert resp.status_code == 400
    assert "mac" in resp.get_json()["error"]


def test_register_valid_returns_200(client):
    device = _make_device()
    with patch("iam.infrastructure.repositories.DeviceRepository.find_or_create_by_mac", return_value=device):
        resp = client.post(
            "/api/v1/devices/register",
            json={"device_id": 1, "farm_id": 2, "mac": "aa:bb:cc:dd:ee:ff"},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["device_id"] == 1
    assert data["farm_id"] == 2
    assert "api_key" in data


def test_device_status_not_found_returns_404(client):
    import peewee
    with patch("iam.infrastructure.models.Device.get", side_effect=peewee.DoesNotExist):
        resp = client.get("/api/v1/devices/999/status")
    assert resp.status_code == 404


def test_device_status_found_returns_200(client):
    mock_row = MagicMock()
    mock_row.device_id = 1
    mock_row.farm_id = 2
    mock_row.api_key = "AA:BB:CC:DD:EE:FF"
    with patch("iam.infrastructure.models.Device.get", return_value=mock_row), \
         patch("shared.infrastructure.device_tracker.is_online", return_value=True):
        resp = client.get("/api/v1/devices/1/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["device_id"] == 1
    assert data["online"] is True
