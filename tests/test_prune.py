"""Tool result pruning tests."""

from likecodex_engine.context.prune import prune_stale_tool_results
from likecodex_engine.llm.base import Message, Role


def test_prunes_large_old_tool_results():
    log = [
        Message(role=Role.USER, content="hi"),
        Message(role=Role.TOOL, content="x" * 2000, tool_call_id="1"),
        Message(role=Role.USER, content="next"),
        Message(role=Role.ASSISTANT, content="ok"),
    ]
    pruned, stats = prune_stale_tool_results(log, tail_keep=2)
    assert stats.results == 1
    assert pruned[1].content.startswith("[elided tool result")
