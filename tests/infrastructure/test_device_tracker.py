from unittest.mock import patch

from shared.infrastructure import device_tracker


def test_unknown_device_is_offline():
    assert device_tracker.is_online(9999) is False


def test_device_is_online_right_after_mark_seen():
    device_tracker.mark_seen(1)
    assert device_tracker.is_online(1) is True


def test_device_becomes_offline_after_window_expires():
    with patch("shared.infrastructure.device_tracker.time.time", return_value=1000.0):
        device_tracker.mark_seen(2)
    with patch("shared.infrastructure.device_tracker.time.time",
               return_value=1000.0 + device_tracker.ONLINE_WINDOW_SECONDS + 1):
        assert device_tracker.is_online(2) is False


def test_device_still_online_within_window():
    with patch("shared.infrastructure.device_tracker.time.time", return_value=2000.0):
        device_tracker.mark_seen(3)
    with patch("shared.infrastructure.device_tracker.time.time",
               return_value=2000.0 + device_tracker.ONLINE_WINDOW_SECONDS - 1):
        assert device_tracker.is_online(3) is True
