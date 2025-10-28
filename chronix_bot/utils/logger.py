"""Simple logging utilities for Chronix.

This module configures a standard library logger and provides an async
enqueueing writer function for non-blocking DB/file writes. It's intentionally
small for Phase 0 — we'll extend it later with DB queue writes.
"""
import logging
import asyncio
from typing import Optional

_queue: Optional[asyncio.Queue] = None


def get_logger(name: str = "chronix") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def start_background_writer(loop: Optional[asyncio.AbstractEventLoop] = None) -> asyncio.Queue:
    """Start a background queue and writer coroutine for log writes.

    Returns the queue instance where callers can put dicts/messages to be
    written asynchronously. This is a minimal implementation for Phase 0.
    """
    global _queue
    if _queue is not None:
        return _queue

    if loop is None:
        loop = asyncio.get_event_loop()

    _queue = asyncio.Queue()

    async def _writer():
        logger = get_logger("chronix.logger_writer")
        while True:
            item = await _queue.get()
            try:
                # In Phase 0 we simply log the item; later this will flush to DB/file
                logger.info("LOG: %s", item)
            except Exception:
                logger.exception("Failed to write log item")
            finally:
                _queue.task_done()

    loop.create_task(_writer())
    return _queue
