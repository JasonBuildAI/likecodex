"""File checkpoint / rewind safety net.

Before the agent runs a write-type tool, the affected files are snapshotted to
``.likecodex/checkpoints``. The user (via CLI ``rewind``, TUI Esc-Esc, or the Web
UI) can roll the workspace back to any checkpoint. New files created after a
checkpoint are removed on rewind; modified files are restored byte-for-byte.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Tool name -> argument keys that carry the affected path(s).
WRITE_TOOL_PATHS: dict[str, tuple[str, ...]] = {
    "write_file": ("path",),
    "edit_file": ("path",),
    "multi_edit": ("path",),
    "delete_range": ("path",),
    "delete_symbol": ("path",),
    "notebook_edit": ("path",),
    "move_file": ("source", "destination"),
}


@dataclass
class FileState:
    path: str
    existed: bool
    blob: str | None  # relative blob filename when existed, else None


@dataclass
class Checkpoint:
    id: str
    label: str
    created_at: float
    files: list[FileState] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "created_at": self.created_at,
            "files": [{"path": f.path, "existed": f.existed, "blob": f.blob} for f in self.files],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Checkpoint:
        return cls(
            id=data["id"],
            label=data.get("label", ""),
            created_at=data.get("created_at", 0.0),
            files=[FileState(**f) for f in data.get("files", [])],
        )


class CheckpointManager:
    def __init__(self, working_dir: str | Path) -> None:
        self.working_dir = Path(working_dir).resolve()
        self.root = self.working_dir / ".likecodex" / "checkpoints"
        self.manifest = self.root / "manifest.jsonl"

    def _ensure(self) -> None:
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)

    def _resolve_in_workspace(self, rel_path: str) -> Path | None:
        """Resolve a relative path, returning None if it escapes the workspace."""
        target = (self.working_dir / rel_path).resolve()
        try:
            target.relative_to(self.working_dir)
            return target
        except ValueError:
            return None

    def snapshot(self, paths: list[str], label: str = "") -> Checkpoint | None:
        """Snapshot the given paths (relative to working dir). Returns the checkpoint."""
        if not paths:
            return None
        self._ensure()
        checkpoint = Checkpoint(id=uuid.uuid4().hex[:12], label=label, created_at=time.time())
        for rel in paths:
            target = self._resolve_in_workspace(rel)
            if target is None:
                continue  # never snapshot outside the workspace
            if target.exists() and target.is_file():
                blob_name = f"{checkpoint.id}_{uuid.uuid4().hex[:8]}.blob"
                (self.root / "blobs" / blob_name).write_bytes(target.read_bytes())
                checkpoint.files.append(FileState(path=rel, existed=True, blob=blob_name))
            else:
                checkpoint.files.append(FileState(path=rel, existed=False, blob=None))
        with open(self.manifest, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(checkpoint.to_dict()) + "\n")
        return checkpoint

    def list_checkpoints(self) -> list[Checkpoint]:
        if not self.manifest.exists():
            return []
        checkpoints: list[Checkpoint] = []
        for line in self.manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                checkpoints.append(Checkpoint.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError):
                continue
        return checkpoints

    def rewind(self, checkpoint_id: str | None = None) -> dict:
        """Restore the workspace to a checkpoint (latest if id is None)."""
        checkpoints = self.list_checkpoints()
        if not checkpoints:
            return {"rewound": False, "reason": "no checkpoints"}
        if checkpoint_id is None:
            checkpoint = checkpoints[-1]
        else:
            checkpoint = next((c for c in checkpoints if c.id == checkpoint_id), None)
            if checkpoint is None:
                return {"rewound": False, "reason": f"checkpoint not found: {checkpoint_id}"}

        restored: list[str] = []
        removed: list[str] = []
        for state in checkpoint.files:
            target = self._resolve_in_workspace(state.path)
            if target is None:
                continue
            if state.existed and state.blob:
                blob = self.root / "blobs" / state.blob
                if blob.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(blob.read_bytes())
                    restored.append(state.path)
            else:
                # File did not exist at snapshot time -> remove if present now.
                if target.exists() and target.is_file():
                    target.unlink()
                    removed.append(state.path)
        return {
            "rewound": True,
            "checkpoint_id": checkpoint.id,
            "label": checkpoint.label,
            "restored": restored,
            "removed": removed,
        }

    @staticmethod
    def paths_for_tool(tool_name: str, arguments: dict) -> list[str]:
        keys = WRITE_TOOL_PATHS.get(tool_name)
        if not keys:
            return []
        paths: list[str] = []
        for key in keys:
            value = arguments.get(key)
            if isinstance(value, str) and value:
                paths.append(value)
        return paths

    def session_snapshot(self, session_id: str, session_events: list[dict]) -> str:
        """Snapshot the session state alongside file checkpoints.

        Saves session metadata to a JSON file in the checkpoints directory.
        Returns the snapshot ID.
        """
        self._ensure()
        snap_id = f"sess_{uuid.uuid4().hex[:12]}"
        snap_path = self.root / "blobs" / f"{snap_id}_session.json"
        data = {
            "snapshot_id": snap_id,
            "session_id": session_id,
            "created_at": time.time(),
            "event_count": len(session_events),
            "events": session_events[-50:],  # keep last 50 events
        }
        snap_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return snap_id

    def list_session_snapshots(self) -> list[dict]:
        """List all session snapshots stored in checkpoints."""
        blob_dir = self.root / "blobs"
        if not blob_dir.exists():
            return []
        snapshots: list[dict] = []
        for f in sorted(blob_dir.glob("*_session.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                snapshots.append(data)
            except (json.JSONDecodeError, OSError):
                pass
        return snapshots
