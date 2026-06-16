from datetime import datetime, timezone

from dateutil.parser import parse

from pir.domain.entities import PirEvent, PirClassification

# ── Classification thresholds ────────────────────────────────────────────────
# WIND   : very short pulse (< 300 ms) caused by leaves/curtains fluttering,
#          OR rapid repeated triggers (>= 5/min) with short pulse (< 800 ms).
# PERSON : sustained heat source — pulse >= 2 000 ms and low frequency (<= 3/min).
# ANIMAL : everything else — medium duration, irregular frequency.
_WIND_MAX_PULSE_MS   = 300
_WIND_RAPID_FREQ     = 5      # triggers/min threshold for high-frequency wind pattern
_WIND_RAPID_MAX_MS   = 800
_PERSON_MIN_PULSE_MS = 2_000
_PERSON_MAX_FREQ     = 3


class PirClassificationService:
    """Domain service: classifies a PIR event and constructs the aggregate."""

    @staticmethod
    def classify(pulse_duration_ms: float, triggers_per_minute: int) -> PirClassification:
        """Return the classification for the given raw PIR signal characteristics.

        Args:
            pulse_duration_ms:   Duration the PIR pin stayed HIGH in milliseconds.
            triggers_per_minute: Number of detections in the last 60-second window.

        Returns:
            PirClassification: WIND, ANIMAL, or PERSON.
        """
        # Short isolated pulse → wind (leaf flutter, air draught)
        if pulse_duration_ms < _WIND_MAX_PULSE_MS:
            return PirClassification.WIND

        # High-frequency short pulses → wind pattern (repeated gusts)
        if triggers_per_minute >= _WIND_RAPID_FREQ and pulse_duration_ms < _WIND_RAPID_MAX_MS:
            return PirClassification.WIND

        # Long sustained detection, low repetition → human body heat signature
        if pulse_duration_ms >= _PERSON_MIN_PULSE_MS and triggers_per_minute <= _PERSON_MAX_FREQ:
            return PirClassification.PERSON

        # Medium duration or irregular frequency → animal
        return PirClassification.ANIMAL

    @staticmethod
    def create_event(
        device_id: int,
        farm_id: int,
        zone_id: int | None,
        pulse_duration_ms: float,
        triggers_per_minute: int,
        recorded_at: str | None,
    ) -> PirEvent:
        """Validate raw values and return a transient PirEvent aggregate.

        Raises:
            ValueError: If pulse_duration_ms or triggers_per_minute are invalid,
                or if recorded_at is not a valid ISO 8601 string.
        """
        try:
            pulse_duration_ms   = float(pulse_duration_ms)
            triggers_per_minute = int(triggers_per_minute)
        except (TypeError, ValueError):
            raise ValueError("pulse_duration_ms and triggers_per_minute must be numeric")

        if pulse_duration_ms < 0:
            raise ValueError("pulse_duration_ms must be >= 0")
        if triggers_per_minute < 0:
            raise ValueError("triggers_per_minute must be >= 0")

        if recorded_at:
            try:
                ts = parse(recorded_at).astimezone(timezone.utc)
            except (ValueError, TypeError):
                raise ValueError("recorded_at must be a valid ISO 8601 timestamp")
        else:
            ts = datetime.now(timezone.utc)

        classification = PirClassificationService.classify(pulse_duration_ms, triggers_per_minute)

        return PirEvent(
            device_id, farm_id, zone_id,
            pulse_duration_ms, triggers_per_minute,
            classification, ts,
        )