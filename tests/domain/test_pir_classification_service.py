from datetime import datetime, timezone

import pytest

from pir.domain.services import PirClassificationService
from pir.domain.entities import PirClassification


# ── classify() ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pulse_ms,freq", [
    (0, 0),
    (100, 0),
    (299.9, 10),
])
def test_classify_short_pulse_is_wind(pulse_ms, freq):
    assert PirClassificationService.classify(pulse_ms, freq) == PirClassification.WIND


@pytest.mark.parametrize("pulse_ms,freq", [
    (300, 5),
    (799.9, 5),
    (500, 10),
])
def test_classify_rapid_short_pulse_is_wind(pulse_ms, freq):
    assert PirClassificationService.classify(pulse_ms, freq) == PirClassification.WIND


@pytest.mark.parametrize("pulse_ms,freq", [
    (2000, 0),
    (2000, 3),
    (5000, 1),
])
def test_classify_long_slow_pulse_is_person(pulse_ms, freq):
    assert PirClassificationService.classify(pulse_ms, freq) == PirClassification.PERSON


@pytest.mark.parametrize("pulse_ms,freq", [
    (800, 4),
    (1500, 4),
    (1999, 2),
    (2000, 4),
])
def test_classify_medium_pulse_is_animal(pulse_ms, freq):
    assert PirClassificationService.classify(pulse_ms, freq) == PirClassification.ANIMAL


# ── create_event() ───────────────────────────────────────────────────────────

def test_create_event_valid():
    event = PirClassificationService.create_event(
        device_id=1,
        farm_id=2,
        zone_id=None,
        pulse_duration_ms=2500,
        triggers_per_minute=2,
        recorded_at="2024-06-15T10:00:00+00:00",
    )
    assert event.device_id == 1
    assert event.farm_id == 2
    assert event.pulse_duration_ms == 2500.0
    assert event.triggers_per_minute == 2
    assert event.classification == PirClassification.PERSON
    assert event.recorded_at.tzinfo is not None


def test_create_event_negative_pulse_raises():
    with pytest.raises(ValueError, match="pulse_duration_ms"):
        PirClassificationService.create_event(1, 2, None, -1, 1, None)


def test_create_event_negative_frequency_raises():
    with pytest.raises(ValueError, match="triggers_per_minute"):
        PirClassificationService.create_event(1, 2, None, 500, -1, None)


@pytest.mark.parametrize("pulse,freq", [
    ("abc", 1),
    (None, 1),
    (500, "abc"),
])
def test_create_event_non_numeric_raises(pulse, freq):
    with pytest.raises(ValueError, match="numeric"):
        PirClassificationService.create_event(1, 2, None, pulse, freq, None)


def test_create_event_invalid_recorded_at_raises():
    with pytest.raises(ValueError, match="recorded_at"):
        PirClassificationService.create_event(1, 2, None, 500, 1, "not-a-date")


def test_create_event_recorded_at_none_defaults_to_now():
    before = datetime.now(timezone.utc)
    event = PirClassificationService.create_event(1, 2, None, 500, 1, None)
    after = datetime.now(timezone.utc)
    assert before <= event.recorded_at <= after
