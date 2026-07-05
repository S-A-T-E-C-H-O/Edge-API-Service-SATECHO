"""Tracks which ESP32 devices have been seen recently (online/offline).

Used by the actuator command subscriber to decide whether a command can be
forwarded immediately or must be buffered until the device reconnects, and by
the device status endpoint to report liveness.
"""

import threading
import time

ONLINE_WINDOW_SECONDS = 60

_last_seen: dict[int, float] = {}
_lock = threading.Lock()


def mark_seen(device_id: int) -> None:
    """Record that a device was just observed (raw MQTT message, heartbeat, or authenticated request)."""
    with _lock:
        _last_seen[device_id] = time.time()


def is_online(device_id: int) -> bool:
    """A device is online if it was seen within the last ONLINE_WINDOW_SECONDS."""
    with _lock:
        last = _last_seen.get(device_id)
    if last is None:
        return False
    return (time.time() - last) < ONLINE_WINDOW_SECONDS
