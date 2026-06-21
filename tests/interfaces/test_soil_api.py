from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from soil.domain.entities import SoilReading


def _make_reading():
    r = SoilReading(
        device_id=1, farm_id=2, zone_id=None,
        moisture=50.0, ec=5.0, ph=7.0, temperature=25.0,
        recorded_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        ambient_temperature=22.0,
        security_pir_status=None,
    )
    r.id = 10
    return r


def _valid_esp32_body():
    return {
        "device_id": 1,
        "farm_id": 2,
        "humidity_fc28": 50.0,
        "salinity_hr202l": 5.0,
        "soil_temp_ds18b20": 25.0,
        "ph": 7.0,
    }


def _valid_legacy_body():
    return {
        "device_id": 1,
        "farm_id": 2,
        "moisture": 50.0,
        "ec": 5.0,
        "temperature": 25.0,
        "ph": 7.0,
    }


def test_missing_api_key_returns_401(client):
    resp = client.post(
        "/api/v1/soil-monitoring/readings",
        json={"device_id": 1, "farm_id": 2},
    )
    assert resp.status_code == 401


def test_missing_device_id_returns_401(client):
    resp = client.post(
        "/api/v1/soil-monitoring/readings",
        headers={"X-API-Key": "key"},
        json={"farm_id": 2},
    )
    assert resp.status_code == 401


def test_missing_farm_id_returns_400(client):
    with patch("iam.interfaces.services._auth_service") as mock_auth:
        mock_auth.authenticate.return_value = True
        resp = client.post(
            "/api/v1/soil-monitoring/readings",
            headers={"X-API-Key": "key"},
            json={"device_id": 1},
        )
    assert resp.status_code == 400


def test_valid_esp32_fields_returns_201(client):
    reading = _make_reading()
    with patch("soil.interfaces.services._soil_service") as mock_svc, \
         patch("iam.interfaces.services._auth_service") as mock_auth:
        mock_auth.authenticate.return_value = True
        mock_svc.record_reading.return_value = reading
        resp = client.post(
            "/api/v1/soil-monitoring/readings",
            headers={"X-API-Key": "mac-key"},
            json=_valid_esp32_body(),
        )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["device_id"] == 1
    assert data["farm_id"] == 2
    assert data["moisture"] == 50.0
    assert data["ec"] == 5.0
    assert data["ph"] == 7.0
    assert data["temperature"] == 25.0
    assert "recorded_at" in data


def test_valid_legacy_fields_returns_201(client):
    reading = _make_reading()
    with patch("soil.interfaces.services._soil_service") as mock_svc, \
         patch("iam.interfaces.services._auth_service") as mock_auth:
        mock_auth.authenticate.return_value = True
        mock_svc.record_reading.return_value = reading
        resp = client.post(
            "/api/v1/soil-monitoring/readings",
            headers={"X-API-Key": "mac-key"},
            json=_valid_legacy_body(),
        )
    assert resp.status_code == 201


def test_invalid_sensor_value_returns_400(client):
    with patch("soil.interfaces.services._soil_service") as mock_svc, \
         patch("iam.interfaces.services._auth_service") as mock_auth:
        mock_auth.authenticate.return_value = True
        mock_svc.record_reading.side_effect = ValueError("moisture 999 out of range")
        body = _valid_esp32_body()
        body["humidity_fc28"] = 999
        resp = client.post(
            "/api/v1/soil-monitoring/readings",
            headers={"X-API-Key": "mac-key"},
            json=body,
        )
    assert resp.status_code == 400
    assert "moisture" in resp.get_json()["error"]
