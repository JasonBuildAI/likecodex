"""AutoResearch run state under .likecodex/autoresearch/."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def research_run_dir(working_dir: str, slug: str = "run") -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)[:40]
    path = Path(working_dir).resolve() / ".likecodex" / "autoresearch" / f"{ts}-{safe}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_research_state(run_dir: Path, objective: str) -> None:
    state = {
        "objective": objective,
        "hypotheses": [],
        "pivots": [],
        "started_at": datetime.now(UTC).isoformat(),
    }
    (run_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (run_dir / "log.md").write_text(f"# AutoResearch\n\nObjective: {objective}\n", encoding="utf-8")
