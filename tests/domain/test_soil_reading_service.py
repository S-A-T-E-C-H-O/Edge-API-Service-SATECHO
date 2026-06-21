from datetime import datetime, timezone

import pytest

from soil.domain.services import SoilReadingService


def _valid_kwargs(**overrides):
    base = dict(
        device_id=1,
        farm_id=2,
        zone_id=None,
        moisture=50.0,
        ec=5.0,
        ph=7.0,
        temperature=25.0,
        recorded_at=None,
    )
    base.update(overrides)
    return base


def test_valid_reading_fields():
    r = SoilReadingService.create_reading(**_valid_kwargs())
    assert r.device_id == 1
    assert r.farm_id == 2
    assert r.moisture == 50.0
    assert r.ec == 5.0
    assert r.ph == 7.0
    assert r.temperature == 25.0
    assert r.is_valid is True
    assert r.ambient_temperature is None


@pytest.mark.parametrize("moisture", [0, 100])
def test_moisture_boundary_valid(moisture):
    SoilReadingService.create_reading(**_valid_kwargs(moisture=moisture))


@pytest.mark.parametrize("moisture", [-0.1, 100.1])
def test_moisture_boundary_invalid(moisture):
    with pytest.raises(ValueError, match="moisture"):
        SoilReadingService.create_reading(**_valid_kwargs(moisture=moisture))


@pytest.mark.parametrize("ec", [0, 20])
def test_ec_boundary_valid(ec):
    SoilReadingService.create_reading(**_valid_kwargs(ec=ec))


@pytest.mark.parametrize("ec", [-1, 20.1])
def test_ec_boundary_invalid(ec):
    with pytest.raises(ValueError, match="ec"):
        SoilReadingService.create_reading(**_valid_kwargs(ec=ec))


@pytest.mark.parametrize("ph", [0, 14])
def test_ph_boundary_valid(ph):
    SoilReadingService.create_reading(**_valid_kwargs(ph=ph))


@pytest.mark.parametrize("ph", [-0.1, 14.1])
def test_ph_boundary_invalid(ph):
    with pytest.raises(ValueError, match="ph"):
        SoilReadingService.create_reading(**_valid_kwargs(ph=ph))


@pytest.mark.parametrize("temperature", [-10, 60])
def test_temperature_boundary_valid(temperature):
    SoilReadingService.create_reading(**_valid_kwargs(temperature=temperature))


@pytest.mark.parametrize("temperature", [-10.1, 60.1])
def test_temperature_boundary_invalid(temperature):
    with pytest.raises(ValueError, match="temperature"):
        SoilReadingService.create_reading(**_valid_kwargs(temperature=temperature))


@pytest.mark.parametrize("field,value", [
    ("moisture", "abc"),
    ("ec", None),
    ("ph", []),
    ("temperature", {}),
])
def test_non_numeric_raises(field, value):
    with pytest.raises(ValueError, match="Sensor values must be numeric"):
        SoilReadingService.create_reading(**_valid_kwargs(**{field: value}))


def test_recorded_at_iso8601_parsed():
    r = SoilReadingService.create_reading(
        **_valid_kwargs(recorded_at="2024-06-15T12:30:00+00:00")
    )
    assert r.recorded_at.year == 2024
    assert r.recorded_at.month == 6
    assert r.recorded_at.day == 15
    assert r.recorded_at.tzinfo is not None


def test_recorded_at_none_defaults_to_utc_now():
    before = datetime.now(timezone.utc)
    r = SoilReadingService.create_reading(**_valid_kwargs(recorded_at=None))
    after = datetime.now(timezone.utc)
    assert before <= r.recorded_at <= after


def test_recorded_at_invalid_raises():
    with pytest.raises(ValueError, match="recorded_at"):
        SoilReadingService.create_reading(**_valid_kwargs(recorded_at="not-a-date"))


def test_ambient_temperature_none_accepted():
    r = SoilReadingService.create_reading(**_valid_kwargs(ambient_temperature=None))
    assert r.ambient_temperature is None


def test_ambient_temperature_value_accepted():
    r = SoilReadingService.create_reading(**_valid_kwargs(ambient_temperature=22.5))
    assert r.ambient_temperature == 22.5
