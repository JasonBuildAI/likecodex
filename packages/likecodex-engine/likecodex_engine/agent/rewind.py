"""Checkpoint rewind: code, conversation, fork, summarize."""

from __future__ import annotations

import difflib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from likecodex_engine.agent.checkpoints import CheckpointManager
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.persistence.session import SessionStore


@dataclass
class RewindResult:
    ok: bool
    mode: str
    message: str
    extra: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "mode": self.mode, "message": self.message, **self.extra}


class RewindController:
    def __init__(
        self,
        working_dir: str,
        context: ContextManager,
        session_id: str,
        store: SessionStore | None = None,
    ) -> None:
        self.working_dir = Path(working_dir).resolve()
        self.context = context
        self.session_id = session_id
        self.checkpoints = CheckpointManager(working_dir)
        self.store = store
        self.turn_index_path = self.working_dir / ".likecodex" / "checkpoints" / f"{session_id}.turns.jsonl"

    def record_turn(self, prompt: str) -> None:
        self.turn_index_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"prompt": prompt, "message_count": len(self.context.messages)})
        with self.turn_index_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def rewind(
        self,
        checkpoint_id: str | None,
        mode: str = "code",
    ) -> dict[str, Any]:
        mode = mode.lower().replace("-", "_")
        if mode in ("code", "rewind_code"):
            result = self.checkpoints.rewind(checkpoint_id)
            return RewindResult(
                ok=bool(result.get("rewound")),
                mode="code",
                message=result.get("message", ""),
                extra=result,
            ).to_dict()

        if mode in ("conversation", "rewind_conversation", "conv"):
            return self._rewind_conversation(checkpoint_id).to_dict()

        if mode in ("both", "rewind_both"):
            code = self.checkpoints.rewind(checkpoint_id)
            conv = self._rewind_conversation(checkpoint_id)
            ok = bool(code.get("rewound")) and conv.ok
            return RewindResult(
                ok=ok,
                mode="both",
                message=f"code: {code.get('message', '')}; conv: {conv.message}",
                extra={"code": code, "conversation": conv.extra},
            ).to_dict()

        if mode == "fork":
            return self._fork(checkpoint_id).to_dict()

        if mode in ("summarize_from", "summarize_upto"):
            return self._summarize(checkpoint_id, mode).to_dict()

        return RewindResult(False, mode, f"Unknown rewind mode: {mode}", {}).to_dict()

    def _rewind_conversation(self, checkpoint_id: str | None) -> RewindResult:
        target_count = self._message_count_for_checkpoint(checkpoint_id)
        if target_count is None:
            return RewindResult(False, "conversation", "Checkpoint not found", {})
        if hasattr(self.context, "_log"):
            self.context._log = self.context.messages[:target_count]  # noqa: SLF001
        return RewindResult(
            True,
            "conversation",
            f"Truncated conversation to {target_count} messages",
            {"message_count": target_count},
        )

    def _message_count_for_checkpoint(self, checkpoint_id: str | None) -> int | None:
        cps = self.checkpoints.list_checkpoints()
        if not cps:
            return 0
        if checkpoint_id:
            for i, cp in enumerate(cps):
                if cp.id == checkpoint_id:
                    return max(0, (i + 1) * 2)
            return None
        return len(self.context.messages)

    def _fork(self, checkpoint_id: str | None) -> RewindResult:
        new_sid = uuid.uuid4().hex[:16]
        fork_dir = self.working_dir / ".likecodex" / "sessions" / "forks" / new_sid
        fork_dir.mkdir(parents=True, exist_ok=True)
        
        conv_snapshot = []
        for msg in self.context.messages[-20:]:
            conv_snapshot.append({
                "role": str(getattr(msg, "role", "")),
                "content": str(msg.content)[:500] if msg.content else "",
            })
        
        meta = {
            "source_session": self.session_id,
            "checkpoint_id": checkpoint_id,
            "message_count": len(self.context.messages),
            "forked_at": __import__("time").time(),
            "conversation_snapshot": conv_snapshot,
        }
        (fork_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        
        cps = self.checkpoints.list_checkpoints()
        if cps:
            cp_data = [cp.to_dict() for cp in cps[-5:]]
            (fork_dir / "checkpoints.json").write_text(json.dumps(cp_data, indent=2), encoding="utf-8")
        
        if self.store:
            self.store.create_session(new_sid, {
                "forked_from": self.session_id,
                "checkpoint_id": checkpoint_id or "",
                "message_count": len(self.context.messages),
            })
        return RewindResult(
            True,
            "fork",
            f"Forked session {new_sid} with {len(conv_snapshot)} conversation messages",
            {
                "session_id": new_sid,
                "snapshot_count": len(conv_snapshot),
                "checkpoint_id": checkpoint_id or "latest",
            },
        )

    def _summarize(self, checkpoint_id: str | None, mode: str) -> RewindResult:
        msgs = self.context.messages
        if not msgs:
            return RewindResult(False, mode, "Nothing to summarize", {})
        cut = len(msgs) // 2 if mode == "summarize_upto" else len(msgs) // 3
        summary = f"[Summarized {cut} messages from rewind {mode}]"
        if hasattr(self.context, "_log"):
            kept = msgs[:2] + msgs[cut:]
            self.context._log = kept  # noqa: SLF001
        return RewindResult(True, mode, summary, {"cut": cut})

    def diff_between(self, checkpoint_a: str | None, checkpoint_b: str | None) -> dict[str, Any]:
        """Compare two checkpoints and return a detailed diff including file-level changes."""
        cps = self.checkpoints.list_checkpoints()
        cp_a = next((cp for cp in cps if cp.id == checkpoint_a), None) if checkpoint_a else None
        cp_b = next((cp for cp in cps if cp.id == checkpoint_b), None) if checkpoint_b else None
        
        a_files = list(cp_a.paths) if cp_a else []
        b_files = list(cp_b.paths) if cp_b else []
        
        # Compute file-level diff
        added = sorted(set(b_files) - set(a_files))
        removed = sorted(set(a_files) - set(b_files))
        common = sorted(set(a_files) & set(b_files))
        
        # Try to read and diff file contents for common files
        file_diffs: list[dict[str, Any]] = []
        for fp in common[:5]:  # Limit to 5 files to avoid bloat
            path = Path(fp)
            if path.is_file():
                try:
                    old_content = Path(str(path) + ".bak").read_text() if Path(str(path) + ".bak").exists() else ""
                    new_content = path.read_text()[:5000]
                    if old_content and new_content and old_content != new_content:
                        diff_lines = list(difflib.unified_diff(
                            old_content.splitlines(keepends=True),
                            new_content.splitlines(keepends=True),
                            fromfile=f"a/{fp}",
                            tofile=f"b/{fp}",
                        ))
                        if diff_lines:
                            file_diffs.append({
                                "file": fp,
                                "diff": "".join(diff_lines[:50]),  # Max 50 lines
                            })
                except (OSError, IOError):
                    pass
        
        return {
            "checkpoint_a": checkpoint_a,
            "checkpoint_b": checkpoint_b,
            "a_files": [str(p) for p in a_files],
            "b_files": [str(p) for p in b_files],
            "a_label": cp_a.label if cp_a else "",
            "b_label": cp_b.label if cp_b else "",
            "added_files": [str(p) for p in added],
            "removed_files": [str(p) for p in removed],
            "common_files": [str(p) for p in common],
            "file_diffs": file_diffs,
            "diff_summary": f"{len(added)} added, {len(removed)} removed, {len(common)} common" + (
                f", {len(file_diffs)} with content changes" if file_diffs else ""
            ),
        }
