"""Simple logging utilities for Chronix.

This module configures a standard library logger and provides an async
enqueueing writer function for non-blocking DB/file writes. It's intentionally
small for Phase 0 — we'll extend it later with DB queue writes.
"""
import logging
import asyncio
from typing import Optional
import json
from pathlib import Path
import time
from typing import Dict

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
        # ensure data dir exists and open archive file
        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        archive_file = data_dir / "logs.jsonl"
        while True:
            item = await _queue.get()
            try:
                # ensure a timestamp exists on the item
                if isinstance(item, dict) and "ts" not in item:
                    try:
                        item["ts"] = int(time.time())
                    except Exception:
                        item["ts"] = None

                # In Phase 0 we simply log the item; later this will flush to DB/file
                logger.info("LOG: %s", item)
                # append to a JSONL archive for export/analytics
                try:
                    with archive_file.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(item, default=str, ensure_ascii=False) + "\n")
                except Exception:
                    logger.exception("Failed to append to log archive")
            except Exception:
                logger.exception("Failed to write log item")
            finally:
                _queue.task_done()

    loop.create_task(_writer())
    return _queue


def enqueue_log(item: object) -> None:
    """Enqueue a log item for asynchronous writing.

    This will lazily start the background writer if it isn't running yet.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No running loop; skip enqueue in this environment
        loop = None

    if loop is not None:
        q = start_background_writer(loop)
        # put_nowait is safe because queue is unbounded in this simple impl
        q.put_nowait(item)


def prune_jsonl_archive(days: int = 30, archive_path: Optional[Path] = None) -> int:
    """Prune entries older than `days` from the JSONL archive.

    Returns the number of kept entries (after pruning). This function is
    synchronous and suitable for calling from background tasks.
    """
    data_dir = Path.cwd() / "data"
    if archive_path is None:
        archive_path = data_dir / "logs.jsonl"
    if not archive_path.exists():
        return 0

    cutoff = int(time.time()) - int(days) * 24 * 60 * 60
    kept = []
    try:
        with archive_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    ts = int(obj.get("ts") or 0)
                    if ts >= cutoff:
                        kept.append(line)
                except Exception:
                    # preserve unknown-format lines
                    kept.append(line)
        # write back
        tmp = archive_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as out:
            for l in kept:
                out.write(l)
        tmp.replace(archive_path)
        return len(kept)
    except Exception:
        # If anything fails, avoid deleting the archive; return 0 to indicate no-op
        return 0
