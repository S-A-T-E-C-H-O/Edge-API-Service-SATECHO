"""Tracks which devices are currently online and buffers pending actuator commands.

A device is considered online if it sent data within the last ONLINE_WINDOW_SECONDS.
When a device that was offline comes back online, buffered commands are drained
and republished to its MQTT topic.
"""

import logging
import threading
import time
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)

ONLINE_WINDOW_SECONDS = int(60)

_lock = threading.Lock()
_last_seen: dict[int, float] = {}
_pending_commands: dict[int, list[tuple[str, str]]] = defaultdict(list)  # device_id → [(topic, payload)]
_drain_callback: Callable[[str, str], None] | None = None


def set_drain_callback(cb: Callable[[str, str], None]) -> None:
    """Register the function to call when draining buffered commands (topic, payload)."""
    global _drain_callback
    _drain_callback = cb


def mark_seen(device_id: int) -> None:
    """Record that a device just sent data. Drains any buffered commands."""
    with _lock:
        was_offline = _is_offline_locked(device_id)
        _last_seen[device_id] = time.monotonic()
        pending = list(_pending_commands.pop(device_id, []))

    if was_offline and pending:
        logger.info("Device %d back online — draining %d buffered commands", device_id, len(pending))
        _drain(pending)


def is_online(device_id: int) -> bool:
    with _lock:
        return not _is_offline_locked(device_id)


def buffer_command(device_id: int, topic: str, payload: str) -> None:
    with _lock:
        _pending_commands[device_id].append((topic, payload))
    logger.info("Buffered actuator command for offline device %d (topic=%s)", device_id, topic)


def _is_offline_locked(device_id: int) -> bool:
    last = _last_seen.get(device_id)
    if last is None:
        return True
    return (time.monotonic() - last) > ONLINE_WINDOW_SECONDS


def _drain(commands: list[tuple[str, str]]) -> None:
    cb = _drain_callback
    if cb is None:
        logger.warning("No drain callback set — buffered commands dropped")
        return
    for topic, payload in commands:
        try:
            cb(topic, payload)
        except Exception as exc:
            logger.error("Error draining command (topic=%s): %s", topic, exc)
