"""
blob_storage.py — content-addressed audio storage on local disk (D45, D-N2).

stabbur owns the canonical learning audio as files on disk, addressed by
sha256; `notes.audio_blob` stores only the hash, never the bytes. No
dependency on any other service's availability to serve them.
"""

from __future__ import annotations

import hashlib
import os

BLOB_DIR = os.environ.get("STABBUR_BLOB_DIR", "blobs")
BLOB_EXT = ".mp3"


def _path_for(sha256: str) -> str:
    return os.path.join(BLOB_DIR, f"{sha256}{BLOB_EXT}")


def store(data: bytes) -> str:
    """Write `data` under its sha256 if not already present. Idempotent —
    re-uploading identical bytes is a no-op and returns the same hash."""
    sha256 = hashlib.sha256(data).hexdigest()
    os.makedirs(BLOB_DIR, exist_ok=True)
    path = _path_for(sha256)
    if not os.path.exists(path):
        tmp_path = f"{path}.tmp-{os.getpid()}"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
    return sha256


def exists(sha256: str) -> bool:
    return os.path.exists(_path_for(sha256))


def path(sha256: str) -> str:
    return _path_for(sha256)
