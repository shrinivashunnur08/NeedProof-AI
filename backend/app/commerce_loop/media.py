"""Where shop product photos live: local disk (free profile) or Cloud Storage (MEDIA_STORE=gcs).

Files are always written to local disk as a cache; with gcs they are also uploaded to MEDIA_BUCKET and
read back from it when the local copy is gone (Cloud Run instances have ephemeral disks).
The bucket stays private; the backend serves photos, so no public bucket or signed URLs are needed.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.commerce_loop.providers import get_providers, setting

log = logging.getLogger(__name__)
_BUCKET = None


def _bucket():
    global _BUCKET
    if _BUCKET is None:
        from google.cloud import storage

        p = get_providers()
        _BUCKET = storage.Client(project=p.gcp_project or None).bucket(setting("MEDIA_BUCKET"))
    return _BUCKET


def gcs_enabled() -> bool:
    return get_providers().media_store == "gcs" and bool(setting("MEDIA_BUCKET"))


def save(local_path: Path, key: str, data: bytes, mime: str) -> None:
    local_path.write_bytes(data)
    if gcs_enabled():
        try:
            _bucket().blob(key).upload_from_string(data, content_type=mime)
        except Exception as exc:  # noqa: BLE001 - keep the local copy; report in logs
            log.warning("Cloud Storage upload failed for %s: %s", key, type(exc).__name__)


def ensure_local(local_path: Path, key: str) -> bool:
    if local_path.is_file():
        return True
    if not gcs_enabled():
        return False
    try:
        blob = _bucket().blob(key)
        if not blob.exists():
            return False
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local_path))
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Cloud Storage download failed for %s: %s", key, type(exc).__name__)
        return False
