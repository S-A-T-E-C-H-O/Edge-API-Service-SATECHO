from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from shared.infrastructure import sync_service


def _fake_row(id_, device_id=1, farm_id=2, zone_id=3, classification="PERSON"):
    row = MagicMock()
    row.id = id_
    row.device_id = device_id
    row.farm_id = farm_id
    row.zone_id = zone_id
    row.classification = classification
    row.triggers_per_minute = 1
    row.pulse_duration_ms = 2500.0
    row.recorded_at = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    return row


def test_sync_pir_once_no_unsynced_events_does_nothing():
    with patch("pir.infrastructure.repositories.PirEventRepository.find_unsynced", return_value=[]) as find_mock, \
         patch("shared.infrastructure.cloud_client.post_security_event") as post_mock:
        sync_service._sync_pir_once()
    find_mock.assert_called_once()
    post_mock.assert_not_called()


def test_sync_pir_once_success_marks_synced():
    rows = [_fake_row(1), _fake_row(2)]
    with patch("pir.infrastructure.repositories.PirEventRepository.find_unsynced", return_value=rows), \
         patch("pir.infrastructure.repositories.PirEventRepository.mark_synced") as mark_mock, \
         patch("shared.infrastructure.cloud_client.post_security_event", return_value=True) as post_mock:
        sync_service._sync_pir_once()

    assert post_mock.call_count == 2
    mark_mock.assert_called_once_with([1, 2])


def test_sync_pir_once_cloud_failure_leaves_events_unsynced():
    rows = [_fake_row(1)]
    with patch("pir.infrastructure.repositories.PirEventRepository.find_unsynced", return_value=rows), \
         patch("pir.infrastructure.repositories.PirEventRepository.mark_synced") as mark_mock, \
         patch("shared.infrastructure.cloud_client.post_security_event", return_value=False):
        sync_service._sync_pir_once()

    mark_mock.assert_not_called()


def test_sync_pir_once_partial_success_marks_only_successful_ones():
    ok_row, fail_row = _fake_row(1), _fake_row(2)
    with patch("pir.infrastructure.repositories.PirEventRepository.find_unsynced", return_value=[ok_row, fail_row]), \
         patch("pir.infrastructure.repositories.PirEventRepository.mark_synced") as mark_mock, \
         patch("shared.infrastructure.cloud_client.post_security_event", side_effect=[True, False]):
        sync_service._sync_pir_once()

    mark_mock.assert_called_once_with([1])
