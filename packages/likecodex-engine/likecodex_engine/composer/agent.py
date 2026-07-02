"""Composer Agent — multi-file AI editing agent.

Wraps the existing AgentLoop to intercept file changes (write_file/edit_file tool calls)
and emit SSE events for the Composer panel UI.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import os
import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator


@dataclass
class FileChange:
    """Represents a single file change captured during Composer execution."""

    file_path: str
    change_type: str  # 'create' | 'modify' | 'delete'
    original_content: str = ""
    modified_content: str = ""
    language: str = ""


@dataclass
class ComposerConfig:
    """Configuration for the Composer Agent."""

    working_dir: str = "."
    max_iterations: int = 30
    auto_accept: bool = False


class ComposerAgent:
    """Multi-file editing agent that wraps AgentLoop.

    Instead of actually writing files to disk, this agent intercepts
    write_file/edit_file tool calls and emits file_change events.
    The user can then accept/reject each change in the UI.

    Supports:
    - Unified event format (composer_plan/composer_file_change/composer_done/composer_error)
    - Incremental diff per file change
    - Multi-file undo/redo stack
    - Background execution mode
    """

    def __init__(
        self,
        config: dict,
        working_dir: str = ".",
    ) -> None:
        self.config = config
        self.working_dir = working_dir
        self.change_set: list[FileChange] = []
        self._captured_paths: set[str] = set()
        self._undo_stack: list[list[dict]] = []  # stack of change snapshots for undo
        self._redo_stack: list[list[dict]] = []  # stack for redo
        self._bg_tasks: dict[str, asyncio.Task] = {}
        self._bg_results: dict[str, list[dict]] = {}

    # ============================================================
    # Public API
    # ============================================================

    async def execute(
        self,
        message: str,
        mentions: list[dict],
        session_id: str,
        background: bool = False,
    ) -> AsyncGenerator[dict, None]:
        """Execute a Composer task, yielding unified SSE events.

        Unified event types (Phase 3.1):
        - composer_plan: Modification plan with file list
        - composer_file_change: Single file change with original_content, language, diff
        - composer_done: Task complete
        - composer_error: Error occurred
        - delta: AI streaming response chunk
        - conflict_detected: File conflict detected

        If background=True (Phase 3.6), yields background_started with task_id.
        """
        if background:
            task_id = uuid.uuid4().hex[:12]
            yield {"type": "background_started", "task_id": task_id}
            # Launch background task
            loop_ = asyncio.get_event_loop()
            bg_task = loop_.create_task(
                self._run_background(task_id, message, mentions, session_id)
            )
            self._bg_tasks[task_id] = bg_task
            bg_task.add_done_callback(lambda _: self._bg_tasks.pop(task_id, None))
            return

        async for event in self._execute_inner(message, mentions, session_id):
            yield event

    async def undo(self) -> list[dict] | None:
        """Undo the last change group. Returns the restored changes or None."""
        if not self._undo_stack:
            return None
        snapshot = self._undo_stack.pop()
        # Push current state to redo
        self._redo_stack.append([
            {
                "file_path": c.file_path,
                "change_type": c.change_type,
                "original_content": c.original_content,
                "modified_content": c.modified_content,
                "language": c.language,
            }
            for c in self.change_set[-len(snapshot):]
        ])
        # Restore change_set (truncate)
        self.change_set = self.change_set[:-len(snapshot)]
        self._captured_paths = {c.file_path for c in self.change_set}
        return snapshot

    async def redo(self) -> list[dict] | None:
        """Redo the last undone change group. Returns the restored changes or None."""
        if not self._redo_stack:
            return None
        snapshot = self._redo_stack.pop()
        self.change_set.extend(
            FileChange(**c) for c in snapshot
        )
        self._captured_paths = {c.file_path for c in self.change_set}
        return snapshot

    async def apply_undo(self) -> list[dict] | None:
        """Undo the last change group AND write original content to disk.

        Returns the list of restored (original) change dicts, or None if nothing to undo.
        """
        snapshot = await self.undo()
        if snapshot is None:
            return None
        for change in snapshot:
            file_path = os.path.join(self.working_dir, change["file_path"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(change["original_content"])
        return snapshot

    async def apply_redo(self) -> list[dict] | None:
        """Redo the last undone change group AND write modified content to disk.

        Returns the list of restored change dicts, or None if nothing to redo.
        """
        snapshot = await self.redo()
        if snapshot is None:
            return None
        for change in snapshot:
            file_path = os.path.join(self.working_dir, change["file_path"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(change["modified_content"])
        return snapshot

    def reset_state(self):
        """Reset all undo/redo stacks and change set to empty."""
        self.change_set.clear()
        self._captured_paths.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ============================================================
    # Phase 3.10: Composer 会话持久化 (序列化/反序列化)
    #
    # 支持将 ComposerAgent 的完整执行状态保存为 JSON,
    # 从而实现会话中断恢复 / 跨工作区迁移 / 审计追踪。
    #
    # 序列化内容:
    # - change_set: 所有已捕获的文件变更 (含原始/修改内容)
    # - _captured_paths: 已处理的文件路径集合
    # - _undo_stack: 撤销堆栈快照
    # - _redo_stack: 重做堆栈快照
    # - config + working_dir: 用于重建 agent 上下文
    #
    # 反序列化后不保留:
    # - 后台任务 (_bg_tasks/_bg_results) — 需要重新执行
    # - SSE 连接 / abortController — 属于前端职责
    # ============================================================

    def serialize(self) -> dict:
        """Serialize current ComposerAgent state to a JSON-serializable dict."""
        return {
            "version": 1,
            "config": self.config,
            "working_dir": self.working_dir,
            "change_set": [
                {
                    "file_path": c.file_path,
                    "change_type": c.change_type,
                    "original_content": c.original_content,
                    "modified_content": c.modified_content,
                    "language": c.language,
                }
                for c in self.change_set
            ],
            "captured_paths": list(self._captured_paths),
            "undo_stack": list(self._undo_stack),
            "redo_stack": list(self._redo_stack),
        }

    @classmethod
    def deserialize(cls, data: dict) -> ComposerAgent:
        """Restore a ComposerAgent from a serialized dict.

        Args:
            data: Dict previously returned by serialize().

        Returns:
            A new ComposerAgent instance with restored change_set and undo/redo stacks.
        """
        agent = cls(
            config=data.get("config", {}),
            working_dir=data.get("working_dir", "."),
        )
        # Restore change_set
        agent.change_set = [
            FileChange(
                file_path=c["file_path"],
                change_type=c["change_type"],
                original_content=c["original_content"],
                modified_content=c["modified_content"],
                language=c.get("language", ""),
            )
            for c in data.get("change_set", [])
        ]
        # Restore captured paths
        agent._captured_paths = set(data.get("captured_paths", []))
        # Restore undo/redo stacks
        agent._undo_stack = list(data.get("undo_stack", []))
        agent._redo_stack = list(data.get("redo_stack", []))
        return agent

    async def get_bg_status(self, task_id: str) -> dict | None:
        """Get the status of a background task."""
        task = self._bg_tasks.get(task_id)
        if task is None:
            return {"type": "composer_error", "content": f"Task {task_id} not found"}
        if task.done():
            if task.exception():
                return {"type": "composer_error", "content": str(task.exception())}
            return {"type": "composer_done"}
        return {"type": "running"}

    async def get_bg_changes(self, task_id: str) -> list[dict] | None:
        """Get the changes collected from a completed background task."""
        return self._bg_results.get(task_id)

    # ============================================================
    # Internal execution
    # ============================================================

    async def _execute_inner(self, message, mentions, session_id):
        """Core execution logic shared by sync and background modes."""
        try:
            # Phase 1: Collect context from mentions
            context_files = self._collect_context(mentions)

            yield {"type": "delta", "content": "正在分析需求...\n\n"}

            # Phase 2: Build task prompt
            task = self._build_task_prompt(message, context_files)

            # Phase 3: Emit composer_plan event
            plan_files = [cf["path"] for cf in context_files]
            yield {
                "type": "composer_plan",
                "files": plan_files,
                "message": message,
            }

            # Phase 4: Create agent loop and run
            loop = self._create_agent_loop(session_id)

            async for resp in loop.run(task):
                event_type = getattr(resp, "event_type", "")
                content = getattr(resp, "content", "")
                tool_calls = getattr(resp, "tool_calls", []) or []

                # Stream assistant text
                if event_type == "assistant" and content:
                    yield {"type": "delta", "content": content}

                # Intercept file-modifying tool calls
                for tc in tool_calls:
                    tool_name = tc.name if hasattr(tc, "name") else tc.get("name", "")
                    args = tc.arguments if hasattr(tc, "arguments") else tc.get("arguments", {})

                    if tool_name in ("write_file", "edit_file", "multi_edit"):
                        change = await self._capture_change(
                            args.get("path", ""),
                            args.get("content", ""),
                            tool_name,
                            args,
                        )
                        if change and change.file_path not in self._captured_paths:
                            # ============================================================
                            # Phase 3.9: SHA256 文件变更冲突检测
                            #
                            # 在写入前校验磁盘文件是否已被外部修改。
                            # 使用 SHA256 而非字符串比较, 优势:
                            #   - 避免编码/换行符差异导致的误判
                            #   - 大文件 O(1) 复杂度比较
                            #   - 可持久化 hash 供后续审计/合并参考
                            #
                            # 冲突策略: 检测到冲突则跳过该文件, 继续处理其余文件,
                            # 并向 UI 发送 conflict_detected 事件供用户裁决。
                            # ============================================================
                            abs_path = change.file_path if os.path.isabs(change.file_path) else \
                                os.path.join(self.working_dir, change.file_path)
                            if os.path.exists(abs_path) and change.change_type != "create":
                                with open(abs_path, "rb") as f:
                                    current_content_bytes = f.read()
                                current_hash = hashlib.sha256(current_content_bytes).hexdigest()
                                original_hash = hashlib.sha256(
                                    change.original_content.encode("utf-8")
                                ).hexdigest()
                                if current_hash != original_hash:
                                    yield {
                                        "type": "conflict_detected",
                                        "filePath": change.file_path,
                                        "originalContent": change.original_content,
                                        "currentContent": current_content_bytes.decode("utf-8", errors="replace"),
                                        "modifiedContent": change.modified_content,
                                        "originalHash": original_hash,
                                        "currentHash": current_hash,
                                    }
                                    continue

                            # 3.5: Push undo snapshot before change
                            self._push_undo_snapshot()

                            self.change_set.append(change)
                            self._captured_paths.add(change.file_path)

                            # 3.2: Generate unified diff for each file change independently
                            diff_text = self._generate_diff(change)

                            # 3.1: Unified composer_file_change event
                            yield {
                                "type": "composer_file_change",
                                "filePath": change.file_path,
                                "changeType": change.change_type,
                                "originalContent": change.original_content,
                                "modifiedContent": change.modified_content,
                                "language": change.language,
                                "diff": diff_text,
                            }

                            # 3.2: Independent composer_diff event for diff-only display
                            yield {
                                "type": "composer_diff",
                                "filePath": change.file_path,
                                "diff": diff_text,
                                "language": change.language,
                            }

            # 3.1: composer_done event
            yield {"type": "composer_done"}

        except Exception as exc:
            # 3.1: composer_error event
            yield {"type": "composer_error", "content": str(exc)}

    async def _run_background(self, task_id: str, message: str, mentions: list[dict], session_id: str):
        """Run a composer task in the background, collecting changes.

        3.6: Uses a dedicated ComposerAgent instance for isolated background execution.
        Results are stored in _bg_results for later retrieval via get_bg_changes().
        """
        try:
            # Use a dedicated ComposerAgent instance for background execution
            bg_agent = ComposerAgent(self.config, self.working_dir)
            async for _event in bg_agent._execute_inner(message, mentions, session_id):
                pass
            # Store results
            self._bg_results[task_id] = [
                {
                    "file_path": c.file_path,
                    "change_type": c.change_type,
                    "original_content": c.original_content,
                    "modified_content": c.modified_content,
                    "language": c.language,
                }
                for c in bg_agent.change_set
            ]
        except Exception as exc:
            self._bg_results[task_id] = [{"type": "composer_error", "content": str(exc)}]

    def _push_undo_snapshot(self):
        """Push current change state as an undo snapshot."""
        snapshot = [
            {
                "file_path": c.file_path,
                "change_type": c.change_type,
                "original_content": c.original_content,
                "modified_content": c.modified_content,
                "language": c.language,
            }
            for c in self.change_set
        ]
        self._undo_stack.append(snapshot)
        # Clear redo stack on new change
        self._redo_stack.clear()

    @staticmethod
    def _generate_diff(change: FileChange) -> str:
        """Generate a unified diff string for a file change."""
        diff_lines = list(difflib.unified_diff(
            change.original_content.splitlines(keepends=True),
            change.modified_content.splitlines(keepends=True),
            fromfile=change.file_path,
            tofile=change.file_path,
        ))
        return "".join(diff_lines)

    # ============================================================
    # Context & Prompt helpers
    # ============================================================

    def _collect_context(self, mentions: list[dict]) -> list[dict]:
        """Collect file context from @ mentions."""
        context_files: list[dict] = []
        for m in mentions:
            mention_type = m.get("type", "")
            mention_id = m.get("id", "")
            if mention_type in ("file", "folder"):
                try:
                    full_path = os.path.join(self.working_dir, mention_id)
                    if os.path.isfile(full_path):
                        with open(full_path, encoding="utf-8", errors="replace") as f:
                            content = f.read()[:8000]
                        context_files.append({
                            "path": mention_id,
                            "content": content,
                        })
                    elif os.path.isdir(full_path):
                        for root, _dirs, files in os.walk(full_path):
                            for fname in sorted(files)[:20]:
                                fpath = os.path.join(root, fname)
                                rel = os.path.relpath(fpath, self.working_dir)
                                try:
                                    with open(fpath, encoding="utf-8", errors="replace") as f:
                                        content = f.read()[:4000]
                                    context_files.append({"path": rel, "content": content})
                                except (OSError, UnicodeDecodeError):
                                    pass
                except (OSError, PermissionError):
                    pass
        return context_files

    def _build_task_prompt(self, message: str, context_files: list[dict]) -> str:
        """Build the task prompt for the agent."""
        context_block = ""
        if context_files:
            parts = []
            for cf in context_files:
                parts.append(f"### {cf['path']}\n```\n{cf['content']}\n```")
            context_block = f"\n\n## Referenced Files\n{''.join(parts)}"

        return f"""{message}{context_block}

## Instructions
1. Analyze what files need to be created or modified.
2. Use write_file to create new files or edit_file to modify existing ones.
3. For each file change, provide the complete file content.
4. After making changes, briefly summarize what was done.

Important: Make all file changes using write_file or edit_file tools. Do not use run_command for file operations.
"""

    # ============================================================
    # Agent & change capture
    # ============================================================

    # ============================================================
    # Phase 3.8: 批量文件创建向导
    #
    # 当 change_type == 'create' 时, AI 自动发现需要创建的新文件。
    # 批量文件创建流程:
    #   1. AI 分析需求 → 列出待创建文件清单 (composer_plan event)
    #   2. 用户确认文件清单 (可选择排除不需要的文件)
    #   3. AI 逐文件生成内容 → 以 composer_file_change 事件推送
    #   4. 用户逐文件预览/编辑 → 点击 acceptAll 批量写入
    #
    # 当前实现:
    # - _capture_change 通过 original 是否为空判定 'create' vs 'modify'
    # - 暂不支持用户在确认步骤中选择排除文件 (后续可通过 event 添加)
    # - 暂不支持中间编辑 (后续可加入 ContentEditable diff)
    # ============================================================

    def _create_agent_loop(self, session_id: str) -> Any:
        """Create an AgentLoop for Composer execution."""
        from likecodex_engine.server import _make_agent

        cfg = dict(self.config)
        cfg["working_dir"] = self.working_dir
        cfg["max_steps"] = cfg.get("max_steps", 30)

        loop = _make_agent(
            cfg,
            enable_planner=False,
            session_id=session_id,
            no_tools=False,
        )
        return loop

    async def _capture_change(
        self,
        file_path: str,
        new_content: str,
        tool_name: str,
        args: dict,
    ) -> FileChange | None:
        """Capture a file change, reading original content for diff."""
        if not file_path:
            return None

        full_path = os.path.join(self.working_dir, file_path)

        # Read original content
        original = ""
        try:
            with open(full_path, encoding="utf-8", errors="replace") as f:
                original = f.read()
        except (FileNotFoundError, OSError):
            original = ""

        # For all tool types, new_content is the final content
        modified = new_content

        if original == modified and original:
            return None

        change_type = "create" if not original else "modify"

        return FileChange(
            file_path=file_path,
            change_type=change_type,
            original_content=original,
            modified_content=modified,
            language=self._detect_language(file_path),
        )

    @staticmethod
    def _detect_language(file_path: str) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".ts": "typescript", ".tsx": "typescript",
            ".js": "javascript", ".jsx": "javascript",
            ".py": "python", ".rs": "rust", ".go": "go",
            ".json": "json", ".css": "css", ".scss": "scss",
            ".html": "html", ".md": "markdown", ".yaml": "yaml",
            ".yml": "yaml", ".sh": "shell", ".sql": "sql",
            ".toml": "ini", ".java": "java", ".c": "c", ".cpp": "cpp",
        }
        _, ext = os.path.splitext(file_path)
        return ext_map.get(ext.lower(), "plaintext")
