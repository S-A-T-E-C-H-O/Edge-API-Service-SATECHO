import json
from unittest.mock import MagicMock, patch

from shared.infrastructure import device_ingest_subscriiber as sut


def _publish_result(rc=0):
    result = MagicMock()
    result.rc = rc
    return result


def _mqtt_client(connected=True, publish_rc=0):
    client = MagicMock()
    client.is_connected.return_value = connected
    client.publish.return_value = _publish_result(rc=publish_rc)
    return client


def test_handle_security_short_pulse_classifies_as_wind_not_person():
    payload = json.dumps({
        "pulse_duration_ms": 150,
        "triggers_per_minute": 1,
        "detectedAt": "2026-07-02T10:00:00Z",
    })
    topic = "agrosafe/raw/1/5/security/event"
    client = _mqtt_client(connected=True)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client):
        sut._handle_security(topic, payload)

    published_payload = json.loads(client.publish.call_args.args[1])
    assert published_payload["classification"] == "WIND"


def test_handle_security_sustained_low_frequency_classifies_as_person():
    payload = json.dumps({
        "pulse_duration_ms": 2500,
        "triggers_per_minute": 2,
        "detectedAt": "2026-07-02T10:00:00Z",
    })
    topic = "agrosafe/raw/1/5/security/event"
    client = _mqtt_client(connected=True)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client):
        sut._handle_security(topic, payload)

    published_payload = json.loads(client.publish.call_args.args[1])
    assert published_payload["classification"] == "PERSON"


def test_handle_security_uses_payload_zone_id():
    payload = json.dumps({
        "zone_id": 370,
        "pulse_duration_ms": 2500,
        "triggers_per_minute": 2,
        "detectedAt": "2026-07-02T10:00:00Z",
    })
    topic = "agrosafe/raw/1/5/security/event"
    client = _mqtt_client(connected=True)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client):
        sut._handle_security(topic, payload)

    published_payload = json.loads(client.publish.call_args.args[1])
    assert published_payload["zone_id"] == 370


def test_handle_security_mqtt_disconnected_persists_locally_instead_of_publishing():
    payload = json.dumps({
        "pulse_duration_ms": 2500,
        "triggers_per_minute": 2,
        "detectedAt": "2026-07-02T10:00:00Z",
    })
    topic = "agrosafe/raw/1/5/security/event"
    client = _mqtt_client(connected=False)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client), \
         patch("shared.infrastructure.device_ingest_subscriiber._persist_security_fallback") as fallback_mock:
        sut._handle_security(topic, payload)

    client.publish.assert_not_called()
    fallback_mock.assert_called_once()


def test_handle_security_publish_failure_persists_locally():
    payload = json.dumps({
        "pulse_duration_ms": 2500,
        "triggers_per_minute": 2,
        "detectedAt": "2026-07-02T10:00:00Z",
    })
    topic = "agrosafe/raw/1/5/security/event"
    client = _mqtt_client(connected=True, publish_rc=1)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client), \
         patch("shared.infrastructure.device_ingest_subscriiber._persist_security_fallback") as fallback_mock:
        sut._handle_security(topic, payload)

    fallback_mock.assert_called_once()


def test_handle_soil_mqtt_disconnected_persists_locally_instead_of_publishing():
    readings = [{"metricType": "humidity_fc28", "value": 45.0, "timestamp": "2026-07-02T10:00:00Z"}]
    topic = "agrosafe/raw/1/5/soil/reading"
    client = _mqtt_client(connected=False)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client), \
         patch("shared.infrastructure.device_ingest_subscriiber._persist_soil_fallback") as fallback_mock:
        sut._handle_soil(topic, json.dumps(readings))

    client.publish.assert_not_called()
    fallback_mock.assert_called_once()


def test_handle_soil_mqtt_connected_relays_without_persisting_fallback():
    readings = [{"metricType": "humidity_fc28", "value": 45.0, "timestamp": "2026-07-02T10:00:00Z"}]
    topic = "agrosafe/raw/1/5/soil/reading"
    client = _mqtt_client(connected=True)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client), \
         patch("shared.infrastructure.device_ingest_subscriiber._persist_soil_fallback") as fallback_mock:
        sut._handle_soil(topic, json.dumps(readings))

    client.publish.assert_called_once()
    fallback_mock.assert_not_called()


def test_handle_soil_uses_payload_zone_id():
    readings = [{
        "metricType": "humidity_fc28",
        "value": 45.0,
        "timestamp": "2026-07-02T10:00:00Z",
        "zone_id": 370,
    }]
    topic = "agrosafe/raw/1/5/soil/reading"
    client = _mqtt_client(connected=True)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client):
        sut._handle_soil(topic, json.dumps(readings))

    published_payload = json.loads(client.publish.call_args.args[1])
    assert published_payload["zone_id"] == 370


def test_handle_soil_uses_topic_zone_id():
    readings = [{"metricType": "humidity_fc28", "value": 45.0, "timestamp": "2026-07-02T10:00:00Z"}]
    topic = "agrosafe/raw/1/5/zones/371/soil/reading"
    client = _mqtt_client(connected=True)

    with patch("shared.infrastructure.device_ingest_subscriiber._mark_seen_and_drain"), \
         patch("shared.infrastructure.device_ingest_subscriiber.get_mqtt_client", return_value=client):
        sut._handle_soil(topic, json.dumps(readings))

    published_payload = json.loads(client.publish.call_args.args[1])
    assert published_payload["zone_id"] == 371


def test_persist_soil_fallback_writes_unsynced_row(_init_database):
    from soil.infrastructure.repositories import SoilReadingRepository

    sut._persist_soil_fallback(
        5, 1, 370,
        {"moisture": 42.0, "ec": 1.2, "temperature": 21.0},
        "2026-07-02T10:00:00Z",
    )

    rows = SoilReadingRepository.find_unsynced(limit=10)
    assert any(r.device_id == 5 and r.zone_id == 370 and r.moisture == 42.0 for r in rows)


def test_persist_security_fallback_writes_unsynced_row(_init_database):
    from pir.domain.entities import PirClassification
    from pir.infrastructure.repositories import PirEventRepository

    sut._persist_security_fallback(
        5, 1, 370, 2500, 2, PirClassification.PERSON, "2026-07-02T10:00:00Z",
    )

    rows = PirEventRepository.find_unsynced(limit=10)
    assert any(r.device_id == 5 and r.zone_id == 370 and r.classification == "PERSON" for r in rows)
