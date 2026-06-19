"""Sub-agent tool registry boundaries."""

from __future__ import annotations

from likecodex_engine.tools.registry import ToolRegistry

META_TOOLS = frozenset(
    {
        "task",
        "parallel_tasks",
        "run_skill",
    }
)

JOB_TOOLS = frozenset(
    {
        "bgjobs",
        "bash_output",
        "kill_shell",
        "wait_job",
    }
)


def subagent_tool_registry(parent: ToolRegistry, whitelist: list[str] | None = None) -> ToolRegistry:
    """Build a tool registry for sub-agents with meta/job tools excluded."""
    sub = ToolRegistry(parent.working_dir, register_defaults=False)
    allowed = set(whitelist) if whitelist else set(parent.list_tools())
    exclude = META_TOOLS | JOB_TOOLS
    for name in sorted(allowed):
        if name in exclude or name not in parent.list_tools():
            continue
        schema = parent._tools.get(name)
        handler = parent.handlers.get(name)
        if schema and handler:
            sub.register(name, schema, handler, read_only=parent.is_read_only(name))
    return sub
