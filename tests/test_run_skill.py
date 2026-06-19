"""run_skill tests."""

import json

import pytest
from likecodex_engine.skills.runner import SkillRunner


@pytest.mark.asyncio
async def test_run_skill_inline(tmp_path):
    skills = tmp_path / ".likecodex" / "skills"
    skills.mkdir(parents=True)
    (skills / "review.md").write_text(
        "---\nname: review\ndescription: Code review\nrunAs: inline\n---\nReview carefully.\n",
        encoding="utf-8",
    )
    runner = SkillRunner(str(tmp_path))
    out = json.loads(await runner.run_skill("review"))
    assert out["mode"] == "inline"
    assert "Review carefully" in out["body"]
