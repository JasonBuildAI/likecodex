"""Release cache guard: prefix hash must stay stable across turns."""

from __future__ import annotations

import os

import pytest

from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.llm.mock import MockProvider


@pytest.mark.skipif(
    os.environ.get("LIKECODEX_RELEASE_CACHE_GUARD") != "1",
    reason="set LIKECODEX_RELEASE_CACHE_GUARD=1 to enforce release cache guard",
)
def test_prefix_hash_stable_over_cache_test_turns():
    context = CacheFirstContext()
    llm = MockProvider.for_cache_test(turns=5)
    hashes: set[str] = {context.prefix_hash()}
    for turn in range(1, 6):
        # simulate loop adding user/assistant without mutating prefix
        context.add_user_message(f"turn {turn}")
        context.add_assistant_message(content=f"response {turn}")
        hashes.add(context.prefix_hash())
    assert len(hashes) == 1
