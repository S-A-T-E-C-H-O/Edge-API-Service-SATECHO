from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from soil.application.services import SoilReadingApplicationService, _consecutive_invalid_counts
from soil.domain.entities import SoilReading
from iam.domain.entities import Device


def _make_service():
    svc = SoilReadingApplicationService.__new__(SoilReadingApplicationService)
    svc.reading_service = MagicMock()
    svc.reading_repository = MagicMock()
    svc.publisher = MagicMock()
    svc.device_repository = MagicMock()
    return svc


def _make_device():
    return Device(device_id=1, farm_id=2, api_key="test-key", created_at=datetime.now(timezone.utc))


def _make_reading(device_id=1, is_valid=True):
    r = SoilReading(
        device_id=device_id, farm_id=2, zone_id=None,
        moisture=50.0, ec=5.0, ph=7.0, temperature=25.0,
        recorded_at=datetime.now(timezone.utc), is_valid=is_valid,
    )
    r.id = 99
    return r


def _call_record(svc, **overrides):
    kwargs = dict(
        device_id=1, farm_id=2, zone_id=None,
        moisture=50.0, ec=5.0, ph=7.0, temperature=25.0,
        recorded_at=None, api_key="test-key",
    )
    kwargs.update(overrides)
    return svc.record_reading(**kwargs)


def test_device_not_found_raises():
    svc = _make_service()
    svc.device_repository.find_by_id_and_api_key.return_value = None
    with pytest.raises(ValueError, match="Device not found or invalid API key"):
        _call_record(svc)


def test_valid_reading_saved_and_published():
    svc = _make_service()
    svc.device_repository.find_by_id_and_api_key.return_value = _make_device()
    expected = _make_reading()
    svc.reading_service.create_reading.return_value = expected
    svc.reading_repository.save.return_value = expected

    result = _call_record(svc)

    svc.reading_repository.save.assert_called_once_with(expected)
    svc.publisher.publish.assert_called_once_with(expected)
    assert result is expected


def test_invalid_sensor_values_persisted_as_invalid_and_reraised():
    svc = _make_service()
    svc.device_repository.find_by_id_and_api_key.return_value = _make_device()
    svc.reading_service.create_reading.side_effect = ValueError("moisture 999 out of range")

    with pytest.raises(ValueError, match="moisture"):
        _call_record(svc, moisture=999)

    svc.reading_repository.save.assert_called_once()
    saved_raw = svc.reading_repository.save.call_args[0][0]
    assert saved_raw.is_valid is False


def test_consecutive_invalid_counter_increments():
    svc = _make_service()
    svc.device_repository.find_by_id_and_api_key.return_value = _make_device()
    svc.reading_service.create_reading.side_effect = ValueError("ec out of range")

    device_id = 42
    _consecutive_invalid_counts.pop(device_id, None)

    for expected_count in range(1, 4):
        with pytest.raises(ValueError):
            _call_record(svc, device_id=device_id)
        assert _consecutive_invalid_counts[device_id] == expected_count


def test_valid_reading_resets_invalid_counter():
    svc = _make_service()
    svc.device_repository.find_by_id_and_api_key.return_value = _make_device()

    device_id = 77
    _consecutive_invalid_counts[device_id] = 5

    reading = _make_reading(device_id=device_id)
    svc.reading_service.create_reading.return_value = reading
    svc.reading_repository.save.return_value = reading

    _call_record(svc, device_id=device_id)
    assert _consecutive_invalid_counts[device_id] == 0
