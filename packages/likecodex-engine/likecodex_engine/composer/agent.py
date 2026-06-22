"""Composer Agent — multi-file AI editing agent.

Wraps the existing AgentLoop to intercept file changes (write_file/edit_file tool calls)
and emit SSE events for the Composer panel UI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
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

    async def execute(
        self,
        message: str,
        mentions: list[dict],
        session_id: str,
    ) -> AsyncGenerator[dict, None]:
        """Execute a Composer task, yielding SSE events.

        Event types:
        - delta: AI streaming response chunk
        - plan: Modification plan
        - file_change: Single file change captured
        - done: Task complete
        - error: Error occurred
        """
        try:
            # Phase 1: Collect context from mentions
            context_files = self._collect_context(mentions)

            yield {"type": "delta", "content": "正在分析需求...\n\n"}

            # Phase 2: Build task prompt
            task = self._build_task_prompt(message, context_files)

            # Phase 3: Create agent loop and run
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
                            self.change_set.append(change)
                            self._captured_paths.add(change.file_path)
                            yield {
                                "type": "file_change",
                                "filePath": change.file_path,
                                "changeType": change.change_type,
                                "originalContent": change.original_content,
                                "modifiedContent": change.modified_content,
                                "language": change.language,
                            }

            yield {"type": "done"}

        except Exception as exc:
            yield {"type": "error", "content": str(exc)}

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

        # For edit_file/multi_edit, the content is the result after editing
        # For write_file, new_content is the full content
        if tool_name == "write_file":
            modified = new_content
        elif tool_name == "edit_file":
            # edit_file returns the patched content
            modified = new_content if new_content else original
        else:
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
