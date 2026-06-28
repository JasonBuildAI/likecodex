"""Session ID resolution per working directory."""

from __future__ import annotations

import hashlib
from pathlib import Path


def canonical_working_dir(path: str | Path) -> Path:
    return Path(path).resolve()


def session_id_for_dir(working_dir: str | Path) -> str:
    """Stable session id for a working directory (Reasonix-style attach)."""
    canonical = str(canonical_working_dir(working_dir))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:16]
