"""Tool registry and dispatch."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from likecodex_engine.tools.agent_memory import AgentMemoryTools
from likecodex_engine.tools.api_client import ApiClientTools
from likecodex_engine.tools.ask import ask_tool_schema
from likecodex_engine.tools.code_index import CodeIndexTools
from likecodex_engine.tools.code_review import CodeReviewTools
from likecodex_engine.tools.code_search import CodeSearchTools
from likecodex_engine.tools.database import DatabaseTools
from likecodex_engine.tools.economy import ToolEconomy
from likecodex_engine.tools.edit_file import EditFileTools
from likecodex_engine.tools.filesystem import FileSystemTools
from likecodex_engine.tools.git import GitTools
from likecodex_engine.tools.github import GitHubTools
from likecodex_engine.tools.history import HistoryTools
from likecodex_engine.tools.log_analyzer import LogAnalyzerTools
from likecodex_engine.tools.lsp import LspTools
from likecodex_engine.tools.lsp_tools import LspSemanticTools
from likecodex_engine.tools.network import NetworkTools
from likecodex_engine.tools.notebook import NotebookTools
from likecodex_engine.tools.plan_progress import PlanProgressTools
from likecodex_engine.tools.profiler import ProfilerTools
from likecodex_engine.tools.refactor import RefactorTools
from likecodex_engine.tools.session_share import SessionShareTools
from likecodex_engine.tools.shell import ShellTools
from likecodex_engine.tools.todo import TodoTools
from likecodex_engine.tools.web_fetch import WebFetchTools
from likecodex_engine.tools.web_search import WebSearchTools

AgentFactory = Callable[[list[str] | None, int | None], Any]


class ToolRegistry:
    """Registers tools and dispatches calls."""

    def __init__(
        self,
        working_dir: str | None = None,
        agent_factory: AgentFactory | None = None,
        session_log_provider: Callable[[], list[Any]] | None = None,
        config: dict[str, Any] | None = None,
        register_defaults: bool = True,
    ) -> None:
        self.working_dir = working_dir or "."
        self._tools: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[..., Awaitable[str]]] = {}
        self._read_only: set[str] = set()
        self._hidden: set[str] = set()
        self._connected_sources: set[str] = set()
        self._engine_config = config or {}
        self._token_mode = str(self._engine_config.get("token_mode", "full")).lower()
        self._agent_factory = agent_factory
        self._session_log = session_log_provider
        self._session_id = ""
        self.todo = TodoTools()
        self.plan_progress = PlanProgressTools(session_log_provider, self.todo)
        if register_defaults:
            self._register_defaults(agent_factory)
        elif agent_factory:
            self._register_meta_tools(agent_factory)
        if self._token_mode == "economy":
            self._apply_economy_hiding()
            self._register_connect_tool_source()

    def _register_defaults(self, agent_factory: AgentFactory | None) -> None:
        fs = FileSystemTools(self.working_dir)
        self.register("read_file", fs.read_file_schema(), fs.read_file, read_only=True)
        self.register("write_file", fs.write_file_schema(), fs.write_file)
        self.register("list_dir", fs.list_dir_schema(), fs.list_dir, read_only=True)
        self.register("ls", fs.ls_schema(), fs.ls, read_only=True)
        self.register("glob", fs.glob_schema(), fs.glob, read_only=True)
        self.register("move_file", fs.move_file_schema(), fs.move_file)
        self.register("search_files", fs.search_files_schema(), fs.search_files, read_only=True)

        edit = EditFileTools(self.working_dir)
        self.register("edit_file", edit.edit_file_schema(), edit.edit_file)
        self.register("multi_edit", edit.multi_edit_schema(), edit.multi_edit)
        self.register("delete_range", edit.delete_range_schema(), edit.delete_range)
        self.register("delete_symbol", edit.delete_symbol_schema(), edit.delete_symbol)

        shell = ShellTools(self.working_dir)
        self.register("run_command", shell.run_command_schema(), shell.run_command)
        self.register("bgjobs", shell.bgjobs_schema(), shell.bgjobs)
        self.register("bash_output", shell.bash_output_schema(), shell.bash_output, read_only=True)
        self.register("kill_shell", shell.kill_shell_schema(), shell.kill_shell)
        self.register("wait_job", shell.wait_job_schema(), shell.wait_job, read_only=True)

        search = CodeSearchTools(self.working_dir)
        self.register("grep_files", search.grep_schema(), search.grep_files, read_only=True)
        self.register("find_symbol", search.find_symbol_schema(), search.find_symbol, read_only=True)
        self.register("index_search", search.index_search_schema(), search.index_search, read_only=True)
        self.register("codegraph_search", search.codegraph_search_schema(), search.codegraph_search, read_only=True)
        self.register("codegraph_symbols", search.codegraph_symbols_schema(), search.codegraph_symbols, read_only=True)
        self.register("codegraph_callers", search.codegraph_callers_schema(), search.codegraph_callers, read_only=True)
        self.register("codegraph_viz", search.codegraph_viz_schema(), search.codegraph_viz, read_only=True)
        self.register("codegraph_reindex", search.codegraph_reindex_schema(), search.codegraph_reindex, read_only=True)
        self.register("semantic_search", search.semantic_search_schema(), search.semantic_search, read_only=True)

        code_index = CodeIndexTools(self.working_dir)
        self.register("code_index", code_index.code_index_schema(), code_index.code_index, read_only=True)

        git = GitTools(self.working_dir)
        self.register("git_status", git.status_schema(), git.git_status, read_only=True)
        self.register("git_diff", git.diff_schema(), git.git_diff, read_only=True)
        self.register("git_log", git.log_schema(), git.git_log, read_only=True)
        self.register("git_branch", git.branch_schema(), git.git_branch, read_only=True)
        self.register("git_commit", git.commit_schema(), git.git_commit)

        review = CodeReviewTools(self.working_dir)
        self.register("review_file", review.review_file_schema(), review.review_file, read_only=True)
        self.register("review_diff", review.review_diff_schema(), review.review_diff, read_only=True)
        self.register(
            "check_dependencies",
            review.check_dependencies_schema(),
            review.check_dependencies,
            read_only=True,
        )

        search_web = WebSearchTools()
        self.register("web_search", search_web.search_schema(), search_web.web_search, read_only=True)

        fetch = WebFetchTools()
        self.register("web_fetch", fetch.fetch_schema(), fetch.web_fetch, read_only=True)

        notebook = NotebookTools(self.working_dir)
        self.register("notebook_edit", notebook.notebook_edit_schema(), notebook.notebook_edit)

        refactor = RefactorTools(self.working_dir)
        self.register("refactor_rename", refactor.refactor_rename_schema(), refactor.refactor_rename)
        self.register("refactor_extract", refactor.refactor_extract_schema(), refactor.refactor_extract)
        self.register("refactor_move_to_file", refactor.refactor_move_to_file_schema(), refactor.refactor_move_to_file)

        lsp_sem = LspSemanticTools(self.working_dir)
        self.register("lsp_definition", lsp_sem.lsp_definition_schema(), lsp_sem.lsp_definition, read_only=True)
        self.register("lsp_references", lsp_sem.lsp_references_schema(), lsp_sem.lsp_references, read_only=True)
        self.register("lsp_hover", lsp_sem.lsp_hover_schema(), lsp_sem.lsp_hover, read_only=True)
        self.register("lsp_diagnostics", lsp_sem.lsp_diagnostics_schema(), lsp_sem.lsp_diagnostics, read_only=True)
        self.register("lsp_code_action", lsp_sem.lsp_code_action_schema(), lsp_sem.lsp_code_action, read_only=True)
        self.register("lsp_code_action_apply", lsp_sem.lsp_code_action_apply_schema(), lsp_sem.lsp_code_action_apply, read_only=True)
        self.register("lsp_suggest_fixes", lsp_sem.lsp_suggest_fixes_schema(), lsp_sem.lsp_suggest_fixes, read_only=True)

        from likecodex_engine.tools.test_runner import TestRunner as _TestRunner

        test_runner = _TestRunner(self.working_dir)
        self.register("discover_tests", test_runner.discover_tests_schema(), test_runner.discover_tests, read_only=True)
        self.register("run_tests", test_runner.run_tests_schema(), test_runner.run_tests, read_only=False)
        self.register("analyze_failures", test_runner.analyze_failures_schema(), test_runner.analyze_failures, read_only=True)
        self.register("collect_coverage", test_runner.collect_coverage_schema(), test_runner.collect_coverage, read_only=True)
        self.register("coverage_summary", test_runner.coverage_summary_schema(), test_runner.coverage_summary, read_only=True)
        self.register("coverage_lcov", test_runner.coverage_lcov_schema(), test_runner.coverage_lcov, read_only=False)

        checker = LspTools(self.working_dir)
        self._checker = checker

        hist = HistoryTools(self.working_dir)
        self.register("history", hist.history_schema(), hist.history, read_only=True)

        share = SessionShareTools()
        self.register("session_share", share.share_schema(), share.share, read_only=True)
        self.register("session_export", share.export_schema(), share.export, read_only=True)
        self.register("session_import", share.import_schema(), share.import_, read_only=True)

        gh = GitHubTools()
        self.register("github_create_pr", gh.create_pr_schema(), gh.create_pr)
        self.register("github_review_pr", gh.review_pr_schema(), gh.review_pr)
        self.register("github_add_pr_comment", gh.add_pr_comment_schema(), gh.add_pr_comment)
        self.register("github_create_issue", gh.create_issue_schema(), gh.create_issue)
        self.register("github_list_prs", gh.list_prs_schema(), gh.list_prs, read_only=True)
        self.register("github_list_issues", gh.list_issues_schema(), gh.list_issues, read_only=True)

        profiler = ProfilerTools()
        self.register("profile_python", profiler.profile_python_schema(), profiler.profile_python)
        self.register("profile_function", profiler.profile_function_schema(), profiler.profile_function)
        self.register("memory_profile", profiler.memory_profile_schema(), profiler.memory_profile)

        mem = AgentMemoryTools(self.working_dir)
        self.register("remember", mem.remember_schema(), mem.remember)
        self.register("forget", mem.forget_schema(), mem.forget)
        self.register("memory_search", mem.memory_search_schema(), mem.memory_search, read_only=True)

        async def memory_op(operation: str, query: str = "", key: str = "", limit: int = 10) -> str:
            if operation == "search":
                return await mem.memory_search(query, limit=limit)
            if operation == "list":
                root = mem.memory_dir
                keys = [p.stem for p in root.glob("*.md")]
                return json.dumps({"keys": keys[:limit]})
            if operation == "read":
                path = mem._path_for(key)
                if not path.exists():
                    return json.dumps({"error": f"Unknown memory key {key!r}"})
                return json.dumps({"key": key, "content": path.read_text(encoding="utf-8")})
            return json.dumps({"error": f"Unknown memory operation {operation!r}"})

        self.register(
            "memory",
            {
                "description": "Search, list, or read agent memory files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["search", "list", "read"]},
                        "query": {"type": "string"},
                        "key": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["operation"],
                },
            },
            memory_op,
            read_only=True,
        )

        async def ask_stub(**kwargs: Any) -> str:
            return json.dumps({"error": "ask is handled by AgentLoop"})

        self.register("ask", ask_tool_schema(), ask_stub, read_only=True)

        self.register("todo_write", self.todo.todo_write_schema(), self.todo.todo_write)
        self.register(
            "complete_step",
            self.plan_progress.complete_step_schema(),
            self.plan_progress.complete_step,
        )

        if agent_factory:
            self._register_meta_tools(agent_factory)

    def _is_economy_optional(self, name: str) -> bool:
        if name == "connect_tool_source":
            return False
        if name.startswith("mcp__") or name.startswith("lsp_") or name.startswith("deepseek_"):
            return True
        return name in {
            "web_fetch",
            "web_search",
            "run_skill",
            "task",
            "parallel_tasks",
        }

    def _apply_economy_hiding(self) -> None:
        for name in list(self._tools.keys()):
            if self._is_economy_optional(name):
                self._hidden.add(name)

    def _register_connect_tool_source(self) -> None:
        async def connect_tool_source(source: str, name: str = "") -> str:
            return await self._connect_tool_source(source, name)

        self.register(
            "connect_tool_source",
            {
                "description": (
                    "Token economy mode: enable an optional tool source when needed. "
                    "Sources: mcp, lsp, web_fetch, skills, task. For mcp, pass server name."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Tool source to enable",
                        },
                        "name": {
                            "type": "string",
                            "description": "MCP server name when source is mcp",
                        },
                    },
                    "required": ["source"],
                },
            },
            connect_tool_source,
            read_only=True,
        )
        self._hidden.discard("connect_tool_source")

    async def _connect_tool_source(self, source: str, name: str = "") -> str:
        source = source.strip().lower()
        self._connected_sources.add(source)
        enabled: list[str] = []

        if source == "mcp":
            from likecodex_engine.mcp.loader import register_mcp_tools

            cfg = {**self._engine_config, "working_dir": self.working_dir}
            if name:
                servers = cfg.get("mcp_servers") or {}
                if name not in servers:
                    return json.dumps({"error": f"MCP server '{name}' not configured", "servers": sorted(servers)})
            added = await register_mcp_tools(self, cfg)
            for tool_name in added:
                self._hidden.discard(tool_name)
                enabled.append(tool_name)
        else:
            # Map source to either a prefix or a fixed set of tool names.
            _SOURCE_PREFIX = {"lsp": "lsp_", "deepseek": "deepseek_"}
            _SOURCE_TOOLS = {
                "web_fetch": ("web_fetch", "web_search"),
                "skills": ("run_skill",),
                "task": ("task", "parallel_tasks"),
            }
            prefix = _SOURCE_PREFIX.get(source)
            tool_names = _SOURCE_TOOLS.get(source)
            if prefix is not None:
                tool_names = tuple(n for n in self._tools if n.startswith(prefix))
            if tool_names is None:
                return json.dumps({"error": f"Unknown source '{source}'"})
            for tool_name in tool_names:
                self._hidden.discard(tool_name)
                if tool_name in self._tools:
                    enabled.append(tool_name)

        return json.dumps({"source": source, "enabled_tools": enabled})

    def reveal_tool(self, name: str) -> None:
        self._hidden.discard(name)

    def set_session_log_provider(self, provider: Callable[[], list[Any]]) -> None:
        self._session_log = provider
        self.plan_progress._session_log = provider

    def set_evidence_ledger(self, ledger: Any) -> None:
        self.todo.set_evidence_ledger(ledger)

    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id

    def set_agent_factory(self, factory: AgentFactory) -> None:
        self._agent_factory = factory
        self._register_meta_tools(factory)
        if self._token_mode == "economy":
            self._apply_economy_hiding()

    def _register_meta_tools(self, factory: AgentFactory) -> None:
        from likecodex_engine.agent.parallel_tasks import ParallelTasksTool
        from likecodex_engine.agent.subagent_store import SubagentStore
        from likecodex_engine.agent.task import TaskTool
        from likecodex_engine.skills.runner import SkillRunner

        store = SubagentStore(self.working_dir)
        store.cleanup_stale_running()
        task = TaskTool(
            factory,
            store=store,
            parent_session=self._session_id,
            working_dir=self.working_dir,
        )
        self.register("task", task.task_schema(), task.task)
        parallel = ParallelTasksTool(factory)
        self.register("parallel_tasks", parallel.parallel_tasks_schema(), parallel.parallel_tasks)
        skills = SkillRunner(
            self.working_dir,
            factory,
            disabled=self._engine_config.get("disabled_skills"),
        )
        self.register("run_skill", skills.run_skill_schema(), skills.run_skill)

        for alias in ("explore", "review", "research", "security_review"):

            async def _skill_alias(task: str = "", _name: str = alias, **_: Any) -> str:
                return await skills.run_skill(_name, task)

            self.register(
                alias,
                {
                    "description": f"Invoke built-in {alias} skill (subagent playbook).",
                    "parameters": {
                        "type": "object",
                        "properties": {"task": {"type": "string"}},
                        "required": ["task"],
                    },
                },
                _skill_alias,
            )

    def register(
        self,
        name: str,
        schema: dict[str, Any],
        handler: Callable[..., Awaitable[str]],
        read_only: bool = False,
    ) -> None:
        self._tools[name] = schema
        self._handlers[name] = handler
        if read_only:
            self._read_only.add(name)

    def is_read_only(self, name: str) -> bool:
        return name in self._read_only

    def filter_names(self, names: list[str]) -> list[str]:
        return [n for n in names if n in self._tools]

    def to_openai_schema(self) -> list[dict[str, Any]]:
        return [
            {"type": "function", "function": {"name": name, **schema}}
            for name, schema in sorted(self._tools.items(), key=lambda item: item[0])
            if name not in self._hidden
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if name in self._hidden:
            return json.dumps(
                {
                    "error": f"Tool '{name}' is hidden in token economy mode. Call connect_tool_source first.",
                }
            )
        handler = self._handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Tool '{name}' not found"})
        try:
            return await handler(**arguments)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def handlers(self) -> dict[str, Callable[..., Awaitable[str]]]:
        return self._handlers
