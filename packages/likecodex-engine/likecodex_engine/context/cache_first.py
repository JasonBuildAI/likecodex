"""Cache-first context model: ImmutablePrefix + AppendOnlyLog + VolatileScratch."""

from __future__ import annotations

import hashlib
import importlib.resources as pkg_resources
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from likecodex_engine.context.cache_shape import PrefixShape, capture_prefix_shape
from likecodex_engine.context.compaction import CacheFirstCompactor
from likecodex_engine.context.prune import prune_stale_tool_results
from likecodex_engine.context.utils import CONTEXT_PREFIX, DEFAULT_SYSTEM_PROMPT_PATH, stable_tool_calls_json
from likecodex_engine.llm.base import Message, Role
from likecodex_engine.llm.tool_repair import sanitize_tool_pairing

PLAN_PREFIX = "[Plan]\n"
DEFAULT_CONTEXT_WINDOW = 1_000_000
DEFAULT_COMPACT_RATIO = 0.8
DEFAULT_SOFT_COMPACT_RATIO = 0.5
DEFAULT_COMPACT_FORCE_RATIO = 0.9


def _default_system_prompt() -> str:
    try:
        return pkg_resources.files("likecodex_engine").joinpath(DEFAULT_SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")
    except Exception:
        return "You are LikeCodex, a DeepSeek-powered software engineering agent."


@dataclass
class ImmutablePrefix:
    """Byte-stable prefix pinned for the session."""

    system_content: str
    skills_content: str = ""
    project_memories: str = ""

    @property
    def combined(self) -> str:
        parts = [self.system_content]
        if self.skills_content:
            parts.append(f"## Skills\n{self.skills_content}")
        if self.project_memories:
            parts.append(f"## Project Memory\n{self.project_memories}")
        return "\n\n".join(parts)

    def hash(self) -> str:
        return hashlib.sha256(self.combined.encode("utf-8")).hexdigest()


@dataclass
class VolatileScratch:
    """Transient state never sent to the LLM."""

    entries: list[str] = field(default_factory=list)

    def add(self, content: str) -> None:
        self.entries.append(content)

    def clear(self) -> None:
        self.entries.clear()


class CacheFirstContext:
    """Three-region context optimized for DeepSeek prefix caching."""

    def __init__(
        self,
        system_prompt: str | None = None,
        skills_content: str = "",
        max_messages: int = 200,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        compact_ratio: float = DEFAULT_COMPACT_RATIO,
        soft_compact_ratio: float = DEFAULT_SOFT_COMPACT_RATIO,
        compact_force_ratio: float = DEFAULT_COMPACT_FORCE_RATIO,
        messages: list[Message] | None = None,
    ) -> None:
        self.prefix = ImmutablePrefix(
            system_content=system_prompt if system_prompt is not None else _default_system_prompt(),
            skills_content=skills_content,
        )
        self.scratch = VolatileScratch()
        self.compactor = CacheFirstCompactor(
            max_messages=max_messages,
            context_window=context_window,
            compact_ratio=compact_ratio,
            soft_compact_ratio=soft_compact_ratio,
            compact_force_ratio=compact_force_ratio,
            working_dir=".",
        )
        self._compact_llm = None
        self.last_prompt_tokens = 0
        self.cache_reset_count = 0
        self.rewrite_version = 0
        self._soft_notice_emitted = False
        self._log_version = 0
        self._build_cache: list[Message] | None = None
        self._build_cache_log_version = -1

        if messages is not None:
            self._log: list[Message] = list(messages)
        else:
            self._log = []

    @property
    def messages(self) -> list[Message]:
        """Compatibility: flat message list including SYSTEM."""
        return [Message(role=Role.SYSTEM, content=self.prefix.combined), *self._log]

    def prefix_hash(self) -> str:
        return self.prefix.hash()

    def capture_prefix_shape(self, tool_schemas: list[dict[str, Any]]) -> PrefixShape:
        return capture_prefix_shape(self.prefix.combined, tool_schemas, self.rewrite_version)

    def set_skills_content(self, content: str) -> None:
        self.prefix.skills_content = content

    def set_project_memories(self, content: str) -> None:
        self.prefix.project_memories = content

    def inject_active_files(self, file_paths: list[str], working_dir: str = ".") -> None:
        """Inject content from active files into context.

        Args:
            file_paths: List of file paths to read and inject
            working_dir: Base directory for resolving relative paths
        """
        if not file_paths:
            return

        file_contents = []
        base_dir = Path(working_dir).resolve()

        for file_path in file_paths[:10]:  # Limit to 10 files max
            try:
                # Resolve path relative to working_dir if not absolute
                path = Path(file_path)
                if not path.is_absolute():
                    path = base_dir / path

                if path.exists() and path.is_file():
                    # Read file with size limit (max 50KB per file)
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    if len(content) > 50000:
                        content = content[:50000] + "\n... [truncated]"

                    # Use relative path for display if possible
                    try:
                        display_path = str(path.relative_to(base_dir))
                    except ValueError:
                        display_path = str(path)

                    file_contents.append(f"### {display_path}\n```\n{content}\n```")
            except Exception:
                # Skip files that can't be read
                pass

        if file_contents:
            block = "## Active Files\n" + "\n\n".join(file_contents)
            self.add_context_block(block)

    def add_scratch(self, content: str) -> None:
        self.scratch.add(content)

    def add_user_message(self, content: str) -> None:
        self._log.append(Message(role=Role.USER, content=content))
        self._log_version += 1

    def add_context_block(self, content: str) -> None:
        block = content if content.startswith(CONTEXT_PREFIX) else f"{CONTEXT_PREFIX}{content}"
        self._log.append(Message(role=Role.USER, content=block))
        self._log_version += 1

    def add_plan_block(self, content: str) -> None:
        block = content if content.startswith(PLAN_PREFIX) else f"{PLAN_PREFIX}{content}"
        self._log.append(Message(role=Role.USER, content=block))
        self._log_version += 1

    def add_system_note(self, content: str) -> None:
        self.add_context_block(content)

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        raw_tool_calls: str | None = None,
        reasoning_content: str | None = None,
    ) -> None:
        serialized = raw_tool_calls
        if tool_calls is not None and serialized is None:
            serialized = stable_tool_calls_json(tool_calls)
        self._log.append(
            Message(
                role=Role.ASSISTANT,
                content=content,
                tool_calls=tool_calls,
                raw_tool_calls=serialized,
                reasoning_content=reasoning_content,
            )
        )
        self._log_version += 1

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self._log.append(Message(role=Role.TOOL, content=content, tool_call_id=tool_call_id))
        self._log_version += 1

    def update_tool_result(self, tool_call_id: str, content: str) -> bool:
        for msg in reversed(self._log):
            if msg.role == Role.TOOL and msg.tool_call_id == tool_call_id:
                msg.content = content
                self._log_version += 1
                return True
        return False

    def set_working_dir(self, working_dir: str) -> None:
        self.compactor.working_dir = Path(working_dir)

    def set_compact_llm(self, llm: Any) -> None:
        self._compact_llm = llm

    def record_prompt_tokens(self, usage: dict[str, int] | None) -> None:
        if not usage:
            return
        self.last_prompt_tokens = int(usage.get("prompt_tokens", self.last_prompt_tokens))
        if self.compactor.should_compact(self.last_prompt_tokens):
            # Sync compact triggered; async LLM compact done via compact_async
            self._compact_sync()

    def _compact_core(
        self,
        foldable: list[Message],
        pinned: list[Message],
        summary: str,
    ) -> dict[str, Any]:
        """Shared post-summarize logic for compact_async and _compact_sync."""
        new_log = [*pinned, Message(role=Role.USER, content=f"{CONTEXT_PREFIX}{summary}")]
        old_size = sum(len(m.content) for m in self._log)
        new_size = sum(len(m.content) for m in new_log)

        if new_size >= old_size * 0.95:
            self.compactor._consecutive_noop_compacts += 1
        else:
            self.compactor._consecutive_noop_compacts = 0

        self._log = new_log
        self.cache_reset_count += 1
        self.rewrite_version += 1
        return {"old_size": old_size, "new_size": new_size}

    async def compact_async(
        self,
        *,
        instructions: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        """LLM compaction with archive and advanced strategies.

        Args:
            instructions: Optional focus instructions for LLM summary
            force: If True, bypass fold_economics (used by /compact command and force-ratio)
        """
        # Prune stale tool results first
        self._log, prune_stats = prune_stale_tool_results(self._log)

        # Check if compactor is stuck (consecutive no-op compacts)
        if self.compactor.compact_stuck():
            return {
                "compacted": False,
                "reason": "compact_stuck",
                "message": "Compaction paused: consecutive compactions produced no meaningful reduction",
            }

        # Split into pinned vs foldable
        pinned, foldable = self.compactor.split_compactable(self._log)
        if not foldable:
            return {"compacted": False, "reason": "nothing_to_fold"}

        # Apply fold economics (skip if foldable is too small) unless forced
        if not force and not self.compactor.fold_economics(foldable):
            return {
                "compacted": False,
                "reason": "fold_economics_skip",
                "message": "Foldable content too small to justify compaction overhead",
            }

        # Track log size before compaction for economics calculation
        total_foldable_chars = sum(len(m.content) for m in foldable)
        self.compactor._last_log_size = total_foldable_chars

        # Archive foldable messages
        archive_path = self.compactor.archive_messages(foldable)

        # Attempt LLM summary with fallback to mechanical summary
        summary: str
        if self._compact_llm is not None:
            try:
                summary = await self.compactor.llm_summarize(
                    foldable,
                    self._compact_llm,
                    instructions=instructions,
                )
            except Exception:
                summary = self.compactor.summarize_log(foldable)
        else:
            summary = self.compactor.summarize_log(foldable)

        result = self._compact_core(foldable, pinned, summary)
        self._log_version += 1

        return {
            "compacted": True,
            "archive": str(archive_path) if archive_path else None,
            "cache_reset_count": self.cache_reset_count,
            "pruned_results": prune_stats.results,
            "pruned_chars": prune_stats.saved_chars,
            "consecutive_noop_compacts": self.compactor._consecutive_noop_compacts,
        }

    def _compact_sync(self) -> None:
        """Synchronous compaction triggered by should_compact threshold."""
        if self.compactor.compact_stuck():
            return

        self._log, _ = prune_stale_tool_results(self._log)
        pinned, foldable = self.compactor.split_compactable(self._log)
        if not foldable:
            return

        if not self.compactor.fold_economics(foldable):
            return

        total_foldable_chars = sum(len(m.content) for m in foldable)
        self.compactor._last_log_size = total_foldable_chars

        self.compactor.archive_messages(foldable)
        summary = self.compactor.summarize_log(foldable)
        self._compact_core(foldable, pinned, summary)

    def build_for_llm(self) -> list[Message]:
        """Cached build: reuses previous result when nothing changed."""
        if self._build_cache is not None and self._build_cache_log_version == self._log_version:
            return self._build_cache
        out: list[Message] = [Message(role=Role.SYSTEM, content=self.prefix.combined)]
        for message in sanitize_tool_pairing(self._log):
            if message.role == Role.ASSISTANT and message.tool_calls:
                tool_calls = json.loads(message.raw_tool_calls) if message.raw_tool_calls else message.tool_calls
                out.append(
                    Message(
                        role=message.role,
                        content=message.content,
                        tool_calls=tool_calls,
                        raw_tool_calls=message.raw_tool_calls,
                    )
                )
            else:
                out.append(message.model_copy(deep=True))
        self._build_cache = out
        self._build_cache_log_version = self._log_version
        return out

    def get_messages(self) -> list[Message]:
        return self.build_for_llm()

    def estimate_tokens(self) -> int:
        total = len(self.prefix.combined) // 4
        for m in self._log:
            total += len(m.content) // 4
            if m.raw_tool_calls:
                total += len(m.raw_tool_calls) // 4
        return total
