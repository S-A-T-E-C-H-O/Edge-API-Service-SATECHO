import logging
import threading
import time
from collections import deque
from functools import partial
from typing import Any, Callable

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_BASE_DELAY = 5  # seconds
_MAX_DELAY = 300


class RetryQueue:
    """In-memory retry queue for items that failed to sync to cloud.

    On reconnect, pending items are replayed with exponential backoff.
    Items exceeding _MAX_RETRIES are moved to a dead-letter store (logged).
    """

    def __init__(self, max_retries: int = _MAX_RETRIES):
        self._queue: deque[tuple[Callable, tuple, dict, int]] = deque()
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._flush_event = threading.Event()
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    def enqueue(self, fn: Callable, *args: Any, **kwargs: Any) -> None:
        """Enqueue a callable with arguments for retry."""
        with self._lock:
            self._queue.append((fn, args, kwargs, 0))
        self._flush_event.set()

    def flush_now(self) -> int:
        """Immediately attempt to drain the queue. Returns count of successful replays."""
        succeeded = 0
        with self._lock:
            items = list(self._queue)
            self._queue.clear()
        for fn, args, kwargs, attempt in items:
            try:
                fn(*args, **kwargs)
                succeeded += 1
                logger.debug("Retry item replayed successfully (attempt %d)", attempt + 1)
            except Exception as exc:
                logger.warning("Retry item failed: %s", exc)
                if attempt + 1 < self._max_retries:
                    self.enqueue(fn, *args, **kwargs)
                else:
                    logger.error("DEAD LETTER: item exceeded %d retries — %s(%s, %s)",
                                 self._max_retries, fn.__name__, args, kwargs)
        return succeeded

    def start(self) -> None:
        """Start background retry thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="retry-queue", daemon=True)
        self._thread.start()
        logger.info("Retry queue started — max_retries=%d", self._max_retries)

    def stop(self) -> None:
        self._running = False
        self._flush_event.set()

    def _run_loop(self) -> None:
        delay = _BASE_DELAY
        while self._running:
            self._flush_event.wait(timeout=delay)
            self._flush_event.clear()
            if not self._running:
                return
            with self._lock:
                count = len(self._queue)
            if count > 0:
                succeeded = self.flush_now()
                delay = _BASE_DELAY if succeeded > 0 else min(delay * 2, _MAX_DELAY)
            else:
                delay = _BASE_DELAY


_retry_queue: RetryQueue | None = None


def get_retry_queue() -> RetryQueue:
    global _retry_queue
    if _retry_queue is None:
        _retry_queue = RetryQueue()
    return _retry_queue


def start() -> None:
    get_retry_queue().start()