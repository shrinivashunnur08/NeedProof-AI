"""Keep the app's SQLite state across Cloud Run restarts and redeploys.

The container disk is wiped whenever Cloud Run starts a new instance (deploys, maintenance). With
STATE_BUCKET (or the media bucket when MEDIA_STORE=gcs) set, the database is restored from Cloud Storage
when an instance starts, snapshotted a few seconds after every change, and flushed on shutdown.
The service runs a single instance (max-instances 1), so one writer owns the snapshot.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
import time

from app.commerce_loop.providers import get_providers, setting

log = logging.getLogger(__name__)
OBJECT = "state/commerce_loop.db"
INTERVAL_S = 5.0
_state = {"last": None, "thread": None, "restored": False, "last_snapshot": None, "error": None}


def bucket_name() -> str | None:
    explicit = setting("STATE_BUCKET")
    if explicit:
        return explicit
    if get_providers().media_store == "gcs" and setting("MEDIA_BUCKET"):
        return setting("MEDIA_BUCKET")
    return None


def _blob():
    from google.cloud import storage

    p = get_providers()
    return storage.Client(project=p.gcp_project or None).bucket(bucket_name()).blob(OBJECT)


def restore(path: str) -> bool:
    """Before the database is opened: fetch the last snapshot if this instance has no local database yet."""
    if _state["restored"] or not bucket_name() or os.path.exists(path):
        return False
    _state["restored"] = True
    try:
        blob = _blob()
        if not blob.exists():
            return False
        blob.download_to_filename(path)
        log.info("Restored app state from gs://%s/%s", bucket_name(), OBJECT)
        return True
    except Exception as exc:  # noqa: BLE001 - start empty rather than not at all
        _state["error"] = f"restore: {type(exc).__name__}"
        log.warning("Could not restore app state: %s", exc)
        return False


def snapshot(force: bool = False) -> bool:
    from app.commerce_loop import store

    if not bucket_name():
        return False
    with store._LOCK:  # noqa: SLF001
        c = store.conn()
        changes = c.total_changes
        if not force and changes == _state["last"]:
            return False
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        dst = sqlite3.connect(tmp)
        c.backup(dst)
        dst.close()
        _state["last"] = changes
    try:
        _blob().upload_from_filename(tmp, content_type="application/x-sqlite3")
        _state["last_snapshot"] = time.time()
        _state["error"] = None
        return True
    except Exception as exc:  # noqa: BLE001 - try again on the next change
        _state["last"] = None
        _state["error"] = f"snapshot: {type(exc).__name__}"
        log.warning("Could not snapshot app state: %s", exc)
        return False
    finally:
        os.unlink(tmp)


def _loop() -> None:
    while True:
        time.sleep(INTERVAL_S)
        try:
            snapshot()
        except Exception as exc:  # noqa: BLE001
            log.warning("snapshot loop: %s", exc)


def start() -> None:
    from app.commerce_loop import store

    if not bucket_name() or _state["thread"]:
        return
    store.conn()  # restores first, then opens
    _state["last"] = store.conn().total_changes
    t = threading.Thread(target=_loop, name="state-snapshot", daemon=True)
    t.start()
    _state["thread"] = t


def flush() -> None:
    if bucket_name():
        snapshot(force=True)


def status() -> dict:
    return {"bucket": bucket_name(), "object": OBJECT if bucket_name() else None,
            "last_snapshot_age_s": round(time.time() - _state["last_snapshot"]) if _state["last_snapshot"] else None,
            "error": _state["error"]}
