import json
from unittest.mock import patch, MagicMock

from shared.infrastructure import actuator_command_subscriber as sut


def _publish_result(rc=0):
    result = MagicMock()
    result.rc = rc
    return result


def setup_function():
    sut._pending_commands.clear()


def test_handle_command_device_online_observes_without_republishing():
    """Anti-storm regression: the device already got the broker's original
    delivery, so the Edge must NOT publish back to the same topic it is
    subscribed to (that echo used to re-trigger this handler forever)."""
    payload = json.dumps({"action": "IRRIGATE_ON", "zone_id": 7, "source": "manual"})
    topic = "agrosafe/10/devices/42/actuator/command"
    mock_client = MagicMock()

    with patch("shared.infrastructure.actuator_command_subscriber.device_tracker.is_online", return_value=True), \
         patch("shared.infrastructure.actuator_command_subscriber.get_mqtt_client", return_value=mock_client), \
         patch("shared.infrastructure.actuator_command_subscriber.cloud_client.post_actuator_log") as log_mock:
        sut._handle_actuator_command(topic, payload)

    mock_client.publish.assert_not_called()
    log_mock.assert_called_once()
    assert log_mock.call_args.args[0] == 42             # device_id
    assert log_mock.call_args.args[3] == "IRRIGATE_ON"  # action
    assert log_mock.call_args.args[5] is True           # success
    assert sut._pending_commands == {}


def test_handle_command_ignores_own_relayed_echo():
    """A payload tagged edge_relayed is our own drain re-publish coming back
    from the broker: no log, no buffer, no publish — the loop must break here."""
    payload = json.dumps({"action": "IRRIGATE_ON", "zone_id": 7, "edge_relayed": True})
    topic = "agrosafe/10/devices/42/actuator/command"
    mock_client = MagicMock()

    with patch("shared.infrastructure.actuator_command_subscriber.device_tracker.is_online", return_value=True), \
         patch("shared.infrastructure.actuator_command_subscriber.get_mqtt_client", return_value=mock_client), \
         patch("shared.infrastructure.actuator_command_subscriber.cloud_client.post_actuator_log") as log_mock:
        sut._handle_actuator_command(topic, payload)

    mock_client.publish.assert_not_called()
    log_mock.assert_not_called()
    assert sut._pending_commands == {}


def test_one_command_produces_at_most_one_processing_cycle():
    """End-to-end anti-loop: process a live command, then feed the handler the
    exact message a drain would publish — the second pass must be a no-op."""
    topic = "agrosafe/10/devices/42/actuator/command"
    original = json.dumps({"action": "IRRIGATE_ON", "zone_id": 7})
    mock_client = MagicMock()
    mock_client.publish.return_value = _publish_result(rc=0)

    with patch("shared.infrastructure.actuator_command_subscriber.device_tracker.is_online", return_value=True), \
         patch("shared.infrastructure.actuator_command_subscriber.get_mqtt_client", return_value=mock_client), \
         patch("shared.infrastructure.actuator_command_subscriber.cloud_client.post_actuator_log") as log_mock:
        sut._handle_actuator_command(topic, original)

        # Whatever a drain would re-publish carries the relay marker; simulate
        # that broker echo hitting the subscriber again.
        relayed = json.dumps({"action": "IRRIGATE_ON", "zone_id": 7, "edge_relayed": True})
        sut._handle_actuator_command(topic, relayed)

    mock_client.publish.assert_not_called()
    assert log_mock.call_count == 1


def test_handle_command_device_offline_buffers_without_publishing():
    payload = json.dumps({"action": "IRRIGATE_ON", "zone_id": 7, "source": "manual"})
    topic = "agrosafe/10/devices/42/actuator/command"
    mock_client = MagicMock()

    with patch("shared.infrastructure.actuator_command_subscriber.device_tracker.is_online", return_value=False), \
         patch("shared.infrastructure.actuator_command_subscriber.get_mqtt_client", return_value=mock_client), \
         patch("shared.infrastructure.actuator_command_subscriber.cloud_client.post_actuator_log") as log_mock:
        sut._handle_actuator_command(topic, payload)

    mock_client.publish.assert_not_called()
    log_mock.assert_not_called()
    assert 42 in sut._pending_commands
    assert len(sut._pending_commands[42]) == 1


def test_drain_pending_republishes_with_relay_marker_and_clears():
    sut._pending_commands[42] = [
        ("agrosafe/10/devices/42/actuator/command", json.dumps({"action": "IRRIGATE_ON"}), 7, "IRRIGATE_ON", "manual")
    ]
    mock_client = MagicMock()
    mock_client.publish.return_value = _publish_result(rc=0)

    with patch("shared.infrastructure.actuator_command_subscriber.get_mqtt_client", return_value=mock_client), \
         patch("shared.infrastructure.actuator_command_subscriber.cloud_client.post_actuator_log") as log_mock:
        sut.drain_pending(42)

    mock_client.publish.assert_called_once()
    published_topic, published_payload = mock_client.publish.call_args.args[:2]
    assert published_topic == "agrosafe/10/devices/42/actuator/command"
    assert json.loads(published_payload)["edge_relayed"] is True
    log_mock.assert_called_once()
    assert 42 not in sut._pending_commands


def test_drain_pending_with_nothing_buffered_is_noop():
    mock_client = MagicMock()
    with patch("shared.infrastructure.actuator_command_subscriber.get_mqtt_client", return_value=mock_client), \
         patch("shared.infrastructure.actuator_command_subscriber.cloud_client.post_actuator_log") as log_mock:
        sut.drain_pending(999)

    mock_client.publish.assert_not_called()
    log_mock.assert_not_called()
