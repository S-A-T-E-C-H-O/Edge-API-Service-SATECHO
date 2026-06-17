import asyncio
import logging
import os
import threading

from shared.infrastructure import cloud_client

logger = logging.getLogger(__name__)

_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
_DEVICE_ID = int(os.getenv("EDGE_DEVICE_ID", "5"))


async def _run_loop() -> None:
    while True:
        await asyncio.sleep(_INTERVAL)
        try:
            ok = await asyncio.to_thread(
                cloud_client.post_heartbeat, _DEVICE_ID, battery_level=None
            )
            if not ok:
                logger.debug("Heartbeat not sent (cloud disabled or unreachable)")
        except Exception as exc:
            logger.warning("Heartbeat error: %s", exc)


def start() -> None:
    """Register the heartbeat coroutine with the shared async background runner."""
    _get_bg_runner().add_task(_run_loop())


# ── shared async background runner (asyncio.gather) ──────────────────────────
_bg_runner_singleton: "_AsyncBgRunner | None" = None


class _AsyncBgRunner:
    """Runs multiple async coroutines concurrently via asyncio.gather() in a daemon thread.

    Supports dynamic task addition: new coroutines are scheduled on the running
    event loop via ``asyncio.run_coroutine_threadsafe``.
    """

    def __init__(self):
        self._tasks: list = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def add_task(self, coro) -> None:
        with self._lock:
            if self._loop is not None and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, self._loop)
                logger.debug("Task added to running event loop")
                return
            self._tasks.append(coro)
        self._ensure_running()

    def _ensure_running(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="async-bg-runner", daemon=True)
        self._thread.start()
        logger.info("Async background runner started")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        with self._lock:
            tasks = list(self._tasks)
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))


def _get_bg_runner() -> _AsyncBgRunner:
    global _bg_runner_singleton
    if _bg_runner_singleton is None:
        _bg_runner_singleton = _AsyncBgRunner()
    return _bg_runner_singleton