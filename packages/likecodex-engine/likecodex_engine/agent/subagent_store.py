"""Persisted sub-agent transcripts for continue/fork."""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from likecodex_engine.context.utils import stable_json_dumps
from likecodex_engine.llm.base import Message, Role


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_ref() -> str:
    return f"sa_{secrets.token_hex(4)}"


@dataclass
class SubagentSpec:
    kind: str = "task"
    name: str = ""
    parent_session: str = ""
    tool_scope: list[str] = field(default_factory=list)
    workspace_root: str = "."


@dataclass
class SubagentMeta:
    ref: str
    status: str
    kind: str
    name: str
    parent_session: str
    tool_scope: list[str]
    workspace_root: str
    created_at: str
    updated_at: str


@dataclass
class SubagentRun:
    ref: str
    meta: SubagentMeta
    messages: list[Message] = field(default_factory=list)
    _release: Any = field(default=None, repr=False)

    def release(self) -> None:
        if self._release:
            self._release()
            self._release = None


class SubagentStore:
    """File-backed sub-agent transcript store under `.likecodex/subagents/`."""

    def __init__(self, workspace_root: str) -> None:
        self.root = Path(workspace_root).resolve()
        self.dir = self.root / ".likecodex" / "subagents"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._locked: set[str] = set()

    def _meta_path(self, ref: str) -> Path:
        return self.dir / f"{ref}.meta.json"

    def _session_path(self, ref: str) -> Path:
        return self.dir / f"{ref}.jsonl"

    def _lock(self, ref: str) -> None:
        if ref in self._locked:
            raise ValueError(f"subagent {ref!r} is already running")
        self._locked.add(ref)

    def _unlock(self, ref: str) -> None:
        self._locked.discard(ref)

    def prepare_fresh(self, spec: SubagentSpec) -> SubagentRun:
        ref = _new_ref()
        now = _now_iso()
        meta = SubagentMeta(
            ref=ref,
            status="running",
            kind=spec.kind,
            name=spec.name,
            parent_session=spec.parent_session,
            tool_scope=list(spec.tool_scope),
            workspace_root=spec.workspace_root,
            created_at=now,
            updated_at=now,
        )
        self._write_meta(meta)
        self._lock(ref)

        def release() -> None:
            self._unlock(ref)

        return SubagentRun(ref=ref, meta=meta, _release=release)

    def prepare_continue(self, ref: str, spec: SubagentSpec) -> SubagentRun:
        meta = self._load_meta(ref)
        self._validate_reuse(meta, spec)
        if meta.status == "failed":
            raise ValueError(f"subagent {ref!r} failed and cannot be continued")
        if meta.status == "interrupted":
            raise ValueError(
                f"subagent {ref!r} was interrupted by a previous shutdown or crash and cannot be "
                "continued or forked; run a fresh subagent instead"
            )
        if meta.parent_session and spec.parent_session and meta.parent_session != spec.parent_session:
            raise ValueError(f"subagent {ref!r} belongs to another parent session; use fork_from instead")
        messages = self._load_messages(ref)
        meta.status = "running"
        meta.updated_at = _now_iso()
        self._write_meta(meta)
        self._lock(ref)

        def release() -> None:
            self._unlock(ref)

        return SubagentRun(ref=ref, meta=meta, messages=messages, _release=release)

    def prepare_fork(self, ref: str, spec: SubagentSpec) -> SubagentRun:
        source = self._load_meta(ref)
        if source.status == "failed":
            raise ValueError(f"subagent {ref!r} failed and cannot be forked")
        if source.status == "interrupted":
            raise ValueError(
                f"subagent {ref!r} was interrupted by a previous shutdown or crash and cannot be "
                "continued or forked; run a fresh subagent instead"
            )
        messages = self._load_messages(ref)
        fork = self.prepare_fresh(spec)
        fork.messages = list(messages)
        return fork

    def save_completed(self, run: SubagentRun, messages: list[Message]) -> None:
        if not run.ref:
            return
        meta = run.meta
        meta.status = "completed"
        meta.updated_at = _now_iso()
        self._write_meta(meta)
        self._write_messages(run.ref, messages)
        run.release()

    def save_failed(self, run: SubagentRun, messages: list[Message] | None = None) -> None:
        if not run.ref:
            return
        meta = run.meta
        meta.status = "failed"
        meta.updated_at = _now_iso()
        self._write_meta(meta)
        if messages:
            self._write_messages(run.ref, messages)
        run.release()

    def cleanup_stale_running(self) -> int:
        """Mark persisted running sub-agents as interrupted after a crash."""
        cleaned = 0
        now = _now_iso()
        for meta_path in self.dir.glob("*.meta.json"):
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if data.get("status") != "running":
                continue
            ref = meta_path.name.removesuffix(".meta.json")
            if ref in self._locked:
                continue
            data["status"] = "interrupted"
            data["updated_at"] = now
            meta_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            cleaned += 1
        return cleaned

    def _validate_reuse(self, meta: SubagentMeta, spec: SubagentSpec) -> None:
        if spec.name and meta.name and spec.name != meta.name:
            raise ValueError("subagent identity mismatch: name")
        if meta.tool_scope and spec.tool_scope and sorted(meta.tool_scope) != sorted(spec.tool_scope):
            raise ValueError("subagent identity mismatch: tools")

    def _load_meta(self, ref: str) -> SubagentMeta:
        path = self._meta_path(ref)
        if not path.exists():
            raise ValueError(f"unknown subagent reference: {ref!r}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return SubagentMeta(**data)

    def _write_meta(self, meta: SubagentMeta) -> None:
        self._meta_path(meta.ref).write_text(
            json.dumps(meta.__dict__, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _load_messages(self, ref: str) -> list[Message]:
        path = self._session_path(ref)
        if not path.exists():
            return []
        messages: list[Message] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            messages.append(
                Message(
                    role=Role(data["role"]),
                    content=data.get("content", ""),
                    tool_calls=data.get("tool_calls"),
                    tool_call_id=data.get("tool_call_id"),
                    raw_tool_calls=data.get("raw_tool_calls"),
                )
            )
        return messages

    def _write_messages(self, ref: str, messages: list[Message]) -> None:
        lines: list[str] = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue
            lines.append(
                json.dumps(
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                        "tool_calls": msg.tool_calls,
                        "tool_call_id": msg.tool_call_id,
                        "raw_tool_calls": msg.raw_tool_calls,
                    },
                    sort_keys=True,
                )
            )
        self._session_path(ref).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    @staticmethod
    def tool_scope_hash(tools: list[str] | None) -> str:
        return stable_json_dumps(sorted(tools or []))
