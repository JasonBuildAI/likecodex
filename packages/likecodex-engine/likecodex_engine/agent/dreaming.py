"""Dreaming Engine — idle learning system.

Mimics Claude Code's "Dreaming" mechanism:
when the Agent is idle, it automatically reviews past sessions,
extracts patterns, and consolidates knowledge into long-term memory.

Classes:
    SessionReviewer    — analyse a single session
    PatternMiner       — cross-session pattern mining
    KnowledgeDistiller — distil persistent knowledge from sessions
    DreamingEngine     — main orchestrator with async idle loop
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

_DREAMING_ENABLED = os.environ.get("LIKECODEX_ENABLE_DREAMING", "true").lower() in (
    "1",
    "true",
    "yes",
)


_DREAMING_FEATURE_FLAG: bool = _DREAMING_ENABLED


def _is_dreaming_enabled() -> bool:
    return _DREAMING_FEATURE_FLAG


def _default_dream_path() -> Path:
    base = Path(os.environ.get("LIKECODEX_HOME", Path.home() / ".likecodex"))
    return base / "dreaming" / "insights.jsonl"


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SessionInsight:
    """Insight extracted from a single session review."""

    session_id: str
    decisions: list[dict[str, Any]] = field(default_factory=list)
    patterns: list[dict[str, Any]] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    errors_encountered: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MinedPattern:
    """A re-usable pattern mined across sessions."""

    pattern_id: str = ""
    category: str = "unknown"
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    frequency: int = 1
    confidence: float = 0.0  # 0.0 — 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DistilledKnowledge:
    """Persistent knowledge distilled from many sessions."""

    project_rules: list[str] = field(default_factory=list)
    tool_tips: list[str] = field(default_factory=list)
    architecture_notes: list[str] = field(default_factory=list)
    recurring_issues: list[dict[str, Any]] = field(default_factory=list)
    best_practices: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# SessionReviewer
# ---------------------------------------------------------------------------


class SessionReviewer:
    """Analyse a single session and extract decisions, patterns and learnings."""

    # Tool names that indicate a decision was made
    _DECISION_TOOLS: set[str] = {
        "edit_file",
        "create_file",
        "search_replace",
        "write_file",
        "delete_file",
        "bash",
        "execute_command",
        "approve",
        "reject",
        "install_package",
        "add_dependency",
    }

    # Tool names that help understand the session flow
    _INFO_TOOLS: set[str] = {
        "read_file",
        "grep",
        "search_codebase",
        "search_symbol",
        "glob",
        "list_dir",
        "web_search",
        "web_fetch",
    }

    async def review_session(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyse a single session and return structured insight."""
        try:
            decisions = self._extract_decisions(messages)
            patterns = self._extract_patterns(messages)
            learnings = self._extract_learnings(messages)
            tools_used = self._collect_tools_used(messages)
            errors = self._extract_errors(messages)
            summary = self._summarise(session_id, decisions, patterns, learnings, tools_used, errors)

            insight = SessionInsight(
                session_id=session_id,
                decisions=decisions,
                patterns=patterns,
                learnings=learnings,
                tools_used=tools_used,
                errors_encountered=errors,
                summary=summary,
            )
            logger.info(
                "Session %s reviewed: %d decisions, %d patterns, %d learnings, %d errors",
                session_id[:8],
                len(decisions),
                len(patterns),
                len(learnings),
                len(errors),
            )
            return insight.to_dict()
        except Exception:
            logger.exception("SessionReviewer.review_session failed for %s", session_id[:8])
            return {"session_id": session_id, "error": "review_failed"}

    # -- internal helpers ------------------------------------------------

    def _extract_decisions(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls") or []

            # Assistant messages containing tool calls are potential decisions
            if role == "assistant" and tool_calls:
                for tc in tool_calls:
                    func_name = ""
                    if isinstance(tc, dict):
                        func = tc.get("function", {})
                        func_name = (
                            func.get("name", "")
                            if isinstance(func, dict)
                            else str(func)
                        )
                    if func_name in self._DECISION_TOOLS:
                        arguments = ""
                        if isinstance(tc, dict):
                            func = tc.get("function", {})
                            arguments = (
                                func.get("arguments", "")
                                if isinstance(func, dict)
                                else ""
                            )
                        decisions.append({
                            "type": "tool_decision",
                            "tool": func_name,
                            "arguments_snippet": arguments[:200],
                            "timestamp": _now(),
                        })

            # User messages with explicit choices
            if role == "user" and any(
                keyword in content for keyword in ("选择", "decision", "decide", "改用", "使用")
            ):
                decisions.append({
                    "type": "explicit_choice",
                    "content": content.strip()[:300],
                    "timestamp": _now(),
                })

        return decisions

    def _extract_patterns(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        patterns: list[dict[str, Any]] = []
        text_blocks = [
            m.get("content", "")
            for m in messages
            if isinstance(m.get("content"), str) and len(m["content"]) > 50
        ]
        full_text = "\n".join(text_blocks)

        # Pattern: error → fix sequence
        if any(kw in full_text for kw in ("error", "Error", "exception", "Exception", "traceback")):
            error_lines = [
                line.strip() for line in full_text.split("\n")
                if any(kw in line for kw in ("error", "Error", "traceback", "File "))
            ]
            fix_lines = [
                line.strip() for line in full_text.split("\n")
                if any(kw in line for kw in ("fix", "Fix", "改为", "修改", "修复"))
            ]
            if error_lines and fix_lines:
                patterns.append({
                    "type": "error_recovery",
                    "error_snippet": error_lines[-1][:200] if error_lines else "",
                    "fix_snippet": fix_lines[-1][:200] if fix_lines else "",
                    "count": 1,
                })

        # Pattern: code style indicators
        if "import " in full_text and "def " in full_text:
            patterns.append({
                "type": "code_style",
                "detail": "session_contains_code_definition",
                "count": 1,
            })

        # Pattern: test-driven
        if any(kw in full_text for kw in ("test_", "assert ", "pytest", "unittest")):
            patterns.append({
                "type": "testing",
                "detail": "test_code_detected",
                "count": 1,
            })

        return patterns

    def _extract_learnings(self, messages: list[dict[str, Any]]) -> list[str]:
        learnings: list[str] = []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue

            # Explicit learning markers in assistant responses
            markers = [
                "学到了", "发现", "注意", "重要的是",
                "lesson", "learned", "note", "important",
                "记住", "remember", "tip", "hint",
            ]
            lines = content.split("\n")
            for i, line in enumerate(lines):
                trimmed = line.strip()
                if any(trimmed.lower().startswith(m) for m in markers):
                    learnings.append(trimmed[:300])
                # Bullet points after learning markers
                if trimmed.startswith("- ") and i > 0 and any(
                    lines[i - 1].strip().lower().startswith(m) for m in markers
                ):
                    learnings.append(trimmed[:300])

        return learnings

    def _collect_tools_used(self, messages: list[dict[str, Any]]) -> list[str]:
        tools: set[str] = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                tool_calls = msg.get("tool_calls") or []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        func = tc.get("function", {})
                        name = func.get("name", "") if isinstance(func, dict) else str(func)
                        if name:
                            tools.add(name)
        return sorted(tools)

    def _extract_errors(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            tool_call_id = msg.get("tool_call_id", "")
            role = msg.get("role", "")

            # Tool results with errors
            if role == "tool" and any(
                kw in content for kw in ("error", "Error", "traceback", "Traceback", "failed", "Failed")
            ):
                errors.append({
                    "tool_call_id": tool_call_id,
                    "error_snippet": content[:500],
                    "timestamp": _now(),
                })

            # Assistant error recognition
            if role == "assistant" and any(
                kw in content for kw in ("出错了", "遇到错误", "修复了", "fixed the error")
            ):
                errors.append({
                    "type": "acknowledged_error",
                    "snippet": content[:300],
                    "timestamp": _now(),
                })

        return errors

    def _summarise(
        self,
        session_id: str,
        decisions: list[dict[str, Any]],
        patterns: list[dict[str, Any]],
        learnings: list[str],
        tools_used: list[str],
        errors: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = [f"Session {session_id[:8]}"]
        if decisions:
            parts.append(f"made {len(decisions)} key decisions")
        if patterns:
            categories = Counter(p.get("type", "unknown") for p in patterns)
            parts.append(f"showed patterns: {dict(categories)}")
        if learnings:
            parts.append(f"extracted {len(learnings)} learnings")
        if errors:
            parts.append(f"encountered {len(errors)} errors")
        if tools_used:
            parts.append(f"used tools: {', '.join(tools_used[:5])}")
        return " · ".join(parts)


# ---------------------------------------------------------------------------
# PatternMiner
# ---------------------------------------------------------------------------


class PatternMiner:
    """Cross-session pattern mining — find recurring patterns and errors."""

    async def mine_patterns(self, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Mine all patterns from a list of already-reviewed session insights."""
        try:
            frequent = await self.find_frequent_patterns(sessions)
            error_ptns = await self.find_error_patterns(sessions)

            all_patterns: list[MinedPattern] = []
            seen_signatures: set[str] = set()

            for p in frequent + error_ptns:
                sig = f"{p.get('category', '')}:{p.get('description', '')}"
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    all_patterns.append(
                        MinedPattern(
                            pattern_id=uuid.uuid4().hex[:12],
                            category=p.get("category", "unknown"),
                            description=p.get("description", ""),
                            evidence=p.get("evidence", []),
                            frequency=p.get("frequency", 1),
                            confidence=p.get("confidence", 0.5),
                        )
                    )

            all_patterns.sort(key=lambda x: x.confidence, reverse=True)
            logger.info(
                "PatternMiner: mined %d unique patterns from %d sessions",
                len(all_patterns),
                len(sessions),
            )
            return [p.to_dict() for p in all_patterns]
        except Exception:
            logger.exception("PatternMiner.mine_patterns failed")
            return []

    async def find_frequent_patterns(
        self,
        sessions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Frequency analysis: detect tools and categories used repeatedly."""
        await asyncio.sleep(0)  # yield control

        tool_counter: Counter[str] = Counter()
        category_counter: Counter[str] = Counter()
        total = len(sessions)

        for session in sessions:
            patterns = session.get("patterns", [])
            tools = session.get("tools_used", [])
            for p in patterns:
                ptype = p.get("type", "unknown")
                category_counter[ptype] += 1
            for t in tools:
                tool_counter[t] += 1

        patterns: list[dict[str, Any]] = []

        for tool, count in tool_counter.most_common(10):
            freq = count / max(total, 1)
            if freq >= 0.3:
                patterns.append({
                    "category": "tool_usage",
                    "description": f"频繁使用工具: {tool} (出现在 {count}/{total} 会话中)",
                    "evidence": [f"tool={tool}, sessions={count}"],
                    "frequency": count,
                    "confidence": min(0.9, freq),
                })

        for category, count in category_counter.most_common(5):
            freq = count / max(total, 1)
            if freq >= 0.25:
                patterns.append({
                    "category": self.category_pattern(category),
                    "description": f"重复模式: {category} (出现在 {count} 次)",
                    "evidence": [f"category={category}, occurrences={count}"],
                    "frequency": count,
                    "confidence": min(0.8, freq),
                })

        return patterns

    async def find_error_patterns(
        self,
        sessions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Cluster similar errors across sessions to find recurring pitfalls."""
        await asyncio.sleep(0)

        error_texts: list[str] = []
        for session in sessions:
            for err in session.get("errors_encountered", []):
                snippet = err.get("error_snippet", err.get("snippet", ""))
                if snippet:
                    error_texts.append(snippet)

        if not error_texts:
            return []

        # Simple keyword-based clustering
        clusters: dict[str, list[str]] = defaultdict(list)
        error_keywords: dict[str, str] = {
            "import_error": "ImportError",
            "syntax_error": "SyntaxError",
            "type_error": "TypeError",
            "value_error": "ValueError",
            "key_error": "KeyError",
            "attribute_error": "AttributeError",
            "index_error": "IndexError",
            "timeout": "timeout",
            "connection": "ConnectionError",
            "permission": "PermissionError",
            "file_not_found": "FileNotFoundError",
            "module_not_found": "ModuleNotFoundError",
        }

        for text in error_texts:
            assigned = False
            for cluster_key, keyword in error_keywords.items():
                if keyword.lower() in text.lower():
                    clusters[cluster_key].append(text[:200])
                    assigned = True
                    break
            if not assigned:
                clusters["other"].append(text[:200])

        patterns: list[dict[str, Any]] = []
        for cluster_key, examples in clusters.items():
            if len(examples) >= 1:
                patterns.append({
                    "category": "error_recovery",
                    "description": f"重复错误模式: {cluster_key} (出现 {len(examples)} 次)",
                    "evidence": examples[:3],
                    "frequency": len(examples),
                    "confidence": min(0.85, len(examples) / max(len(error_texts), 1) + 0.3),
                })

        return patterns

    @staticmethod
    def category_pattern(pattern: dict[str, Any] | str) -> str:
        """Classify a pattern into a high-level category."""
        if isinstance(pattern, str):
            ptype = pattern
        else:
            ptype = pattern.get("type", pattern.get("category", "unknown"))

        category_map: dict[str, str] = {
            "error_recovery": "error_recovery",
            "code_style": "code_style",
            "testing": "code_style",
            "tool_usage": "tool_usage",
            "tool_decision": "decision_making",
            "explicit_choice": "decision_making",
        }
        return category_map.get(ptype, "general")


# ---------------------------------------------------------------------------
# KnowledgeDistiller
# ---------------------------------------------------------------------------


class KnowledgeDistiller:
    """Distil persistent knowledge from multiple session insights."""

    async def distill(self, sessions: list[dict[str, Any]]) -> dict[str, Any]:
        """Full distillation: rules, tips, architecture notes, best practices."""
        try:
            rules = await self.generate_project_rules(sessions)
            tips = await self.generate_tool_usage_tips(sessions)
            issues = self._extract_recurring_issues(sessions)
            practices = self._extract_best_practices(sessions, rules, tips)
            architecture = self._extract_architecture_notes(sessions)

            knowledge = DistilledKnowledge(
                project_rules=rules,
                tool_tips=tips,
                architecture_notes=architecture,
                recurring_issues=issues,
                best_practices=practices,
            )
            logger.info(
                "KnowledgeDistiller: distilled %d rules, %d tips, %d practices",
                len(rules),
                len(tips),
                len(practices),
            )
            return knowledge.to_dict()
        except Exception:
            logger.exception("KnowledgeDistiller.distill failed")
            return {"project_rules": [], "tool_tips": [], "architecture_notes": []}

    async def generate_project_rules(
        self,
        sessions: list[dict[str, Any]],
    ) -> list[str]:
        """Generate project-level rules from repeated patterns."""
        await asyncio.sleep(0)

        rules: list[str] = []
        tool_mentions: Counter[str] = Counter()
        style_mentions: Counter[str] = Counter()

        for session in sessions:
            for p in session.get("patterns", []):
                ptype = p.get("type", "")
                if ptype == "code_style":
                    style_mentions["遵循现有代码风格"] += 1
                elif ptype == "testing":
                    rules.append("为关键逻辑编写测试")
                elif ptype == "error_recovery":
                    error_snippet = p.get("error_snippet", "")
                    if "import" in error_snippet:
                        rules.append("导入前检查依赖是否已安装")

            for t in session.get("tools_used", []):
                tool_mentions[t] += 1

        # Build rules from tool usage
        if tool_mentions["edit_file"] >= 2:
            rules.append("使用 edit_file 修改代码前先阅读目标文件")
        if tool_mentions["bash"] >= 3:
            rules.append("在执行破坏性命令前先进行预览")

        # Deduplicate
        seen: set[str] = set()
        deduped: list[str] = []
        for r in rules:
            if r not in seen:
                seen.add(r)
                deduped.append(r)

        return deduped[:10]

    async def generate_tool_usage_tips(
        self,
        sessions: list[dict[str, Any]],
    ) -> list[str]:
        """Generate actionable tips for better tool usage."""
        await asyncio.sleep(0)

        tips: list[str] = []
        all_tools: Counter[str] = Counter()
        error_contexts: list[str] = []

        for session in sessions:
            for t in session.get("tools_used", []):
                all_tools[t] += 1
            for err in session.get("errors_encountered", []):
                snippet = err.get("error_snippet", "")
                if "edit_file" in snippet or "search_replace" in snippet:
                    error_contexts.append("编辑操作")

        # Generate tips based on usage
        total_sessions = max(len(sessions), 1)
        for tool, count in all_tools.most_common(8):
            freq = count / total_sessions
            if freq >= 0.5:
                tips.append(f"高频工具: {tool} (出现在 {count}/{total_sessions} 个会话中)")

        if error_contexts:
            tips.append("编辑文件时，建议先使用 read_file 确认内容后再修改")

        if not tips:
            tips.append("持续使用工具，将生成更多工具使用建议")

        return tips[:8]

    def _extract_recurring_issues(
        self,
        sessions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract issues that appear in multiple sessions."""
        error_clusters: dict[str, list[str]] = defaultdict(list)

        for session in sessions:
            for err in session.get("errors_encountered", []):
                snippet = err.get("error_snippet", err.get("snippet", ""))
                if "import" in snippet.lower() and "error" in snippet.lower():
                    error_clusters["导入错误"].append(snippet[:100])
                elif "timeout" in snippet.lower():
                    error_clusters["超时问题"].append(snippet[:100])
                elif "syntax" in snippet.lower():
                    error_clusters["语法错误"].append(snippet[:100])
                elif "type" in snippet.lower():
                    error_clusters["类型错误"].append(snippet[:100])

        issues: list[dict[str, Any]] = []
        for title, examples in error_clusters.items():
            if len(examples) >= 1:
                issues.append({
                    "title": title,
                    "occurrences": len(examples),
                    "example": examples[0][:200],
                })
        return issues

    def _extract_best_practices(
        self,
        sessions: list[dict[str, Any]],
        rules: list[str],
        tips: list[str],
    ) -> list[str]:
        """Derive best practices from rules + tips + patterns."""
        practices: list[str] = list(rules[:3])
        practices.extend(tips[:3])

        # Add practices based on aggregated data
        total_decisions = sum(len(s.get("decisions", [])) for s in sessions)
        if total_decisions > 10:
            practices.append("保持小步提交，每次聚焦一个决策点")

        total_learnings = sum(len(s.get("learnings", [])) for s in sessions)
        if total_learnings > 5:
            practices.append("将会话中的学习点记录到长期记忆中")

        seen: set[str] = set()
        deduped: list[str] = []
        for p in practices:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        return deduped[:10]

    def _extract_architecture_notes(
        self,
        sessions: list[dict[str, Any]],
    ) -> list[str]:
        """Extract architecture/design notes from sessions."""
        notes: list[str] = []
        for session in sessions:
            for p in session.get("patterns", []):
                detail = p.get("detail", "")
                if detail and "architecture" in detail.lower():
                    notes.append(detail[:200])
            for d in session.get("decisions", []):
                args = d.get("arguments_snippet", "")
                if "class" in args or "interface" in args or "struct" in args:
                    notes.append(f"架构决策: {args[:200]}")
        return notes[:5]

    @staticmethod
    def rank_by_importance(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank a list of insight entries by estimated importance."""
        scored: list[tuple[float, dict[str, Any]]] = []
        for insight in insights:
            score = 0.0

            # Frequency-based
            freq = insight.get("frequency", insight.get("occurrences", 1))
            score += min(freq * 0.2, 2.0)

            # Confidence-based
            confidence = insight.get("confidence", 0.5)
            score += confidence * 1.5

            # Category bonus
            category = insight.get("category", insight.get("type", ""))
            if category in ("error_recovery", "decision_making"):
                score += 1.0
            elif category == "code_style":
                score += 0.5

            scored.append((score, insight))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]


# ---------------------------------------------------------------------------
# DreamingEngine
# ---------------------------------------------------------------------------


class DreamingEngine:
    """Main orchestrator for the idle learning (dreaming) system.

    Runs a background asyncio loop that periodically reviews recent sessions,
    mines patterns, distils knowledge, and persists insights.
    """

    def __init__(
        self,
        session_reviewer: SessionReviewer | None = None,
        pattern_miner: PatternMiner | None = None,
        knowledge_distiller: KnowledgeDistiller | None = None,
        dream_interval: int = 300,
        min_sessions_for_dreaming: int = 3,
        insights_path: str | Path | None = None,
        memory: Any = None,
    ) -> None:
        self._session_reviewer = session_reviewer or SessionReviewer()
        self._pattern_miner = pattern_miner or PatternMiner()
        self._knowledge_distiller = knowledge_distiller or KnowledgeDistiller()

        self._is_dreaming: bool = False
        self._dream_interval: int = dream_interval
        self._last_dream_time: float = 0.0
        self._min_sessions_for_dreaming: int = min_sessions_for_dreaming

        self._insights_path: Path = Path(insights_path) if insights_path else _default_dream_path()
        self._insights_path.parent.mkdir(parents=True, exist_ok=True)

        self._memory = memory
        self._dreaming_task: asyncio.Task[None] | None = None

        # Accumulated results
        self._insights: list[dict[str, Any]] = []
        self._patterns: list[dict[str, Any]] = []
        self._knowledge: dict[str, Any] = DistilledKnowledge().to_dict()

        self._dream_count: int = 0
        self._total_sessions_analysed: int = 0

        logger.info(
            "DreamingEngine initialized (interval=%ds, min_sessions=%d, enabled=%s)",
            self._dream_interval,
            self._min_sessions_for_dreaming,
            _is_dreaming_enabled(),
        )

    # -- Lifecycle -------------------------------------------------------

    async def start(self, interval: int | None = None) -> None:
        """Start the idle learning loop in the background.

        Args:
            interval: Override the dream interval in seconds (default 300).
        """
        if not _is_dreaming_enabled():
            logger.info("Dreaming is disabled by LIKECODEX_ENABLE_DREAMING")
            return

        if interval is not None:
            self._dream_interval = interval

        if self._dreaming_task is not None and not self._dreaming_task.done():
            logger.warning("DreamingEngine is already running")
            return

        self._is_dreaming = True
        self._dreaming_task = asyncio.create_task(
            self._dream_loop(),
            name="dreaming-engine",
        )
        logger.info(
            "DreamingEngine started with interval=%ds",
            self._dream_interval,
        )

    async def stop(self) -> None:
        """Stop the idle learning loop."""
        self._is_dreaming = False

        if self._dreaming_task is not None and not self._dreaming_task.done():
            self._dreaming_task.cancel()
            try:
                await self._dreaming_task
            except asyncio.CancelledError:
                pass
            self._dreaming_task = None

        self._persist()
        logger.info(
            "DreamingEngine stopped. Total dreams: %d, sessions analysed: %d",
            self._dream_count,
            self._total_sessions_analysed,
        )

    async def _dream_loop(self) -> None:
        """Internal background loop."""
        while self._is_dreaming:
            try:
                await self.dream()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Dream cycle failed, will retry next interval")

            # Wait for the next cycle (check every second for cancellation)
            for _ in range(self._dream_interval):
                if not self._is_dreaming:
                    return
                await asyncio.sleep(1)

    # -- Core dreaming ---------------------------------------------------

    async def dream(self) -> None:
        """Execute a single complete learning cycle."""
        logger.info("🔄 Dream cycle starting...")
        start_ts = _now()

        try:
            # 1. Analyse recent sessions
            recent = await self.analyze_recent_sessions(limit=10)

            new_sessions = recent.get("sessions", [])
            if len(new_sessions) < self._min_sessions_for_dreaming:
                logger.debug(
                    "Not enough sessions to dream (need %d, have %d)",
                    self._min_sessions_for_dreaming,
                    len(new_sessions),
                )
                return

            # 2. Mine cross-session patterns
            patterns = await self._pattern_miner.mine_patterns(new_sessions)
            if patterns:
                self._patterns.extend(patterns)
                # Keep only the most recent 100 patterns
                self._patterns = self._patterns[-100:]

            # 3. Distil knowledge
            knowledge = await self._knowledge_distiller.distill(new_sessions)
            if knowledge.get("project_rules") or knowledge.get("tool_tips"):
                self._knowledge = knowledge

            # 4. Write insights to memory
            await self._write_to_memory(recent, patterns, knowledge)

            # 5. Persist to JSONL
            self._persist()

            elapsed = _now() - start_ts
            self._dream_count += 1
            self._last_dream_time = _now()

            logger.info(
                "✅ Dream cycle completed in %.2fs (dream #%d, %d sessions, %d patterns, %d rules)",
                elapsed,
                self._dream_count,
                len(new_sessions),
                len(patterns),
                len(knowledge.get("project_rules", [])),
            )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dream cycle failed unexpectedly")

    async def analyze_recent_sessions(
        self,
        limit: int = 10,
        messages_provider: Any = None,
    ) -> dict[str, Any]:
        """Analyse recent sessions by reviewing each one individually.

        Args:
            limit: Maximum number of sessions to analyse.
            messages_provider: Optional callable that returns messages for a
                session_id. If not provided, sessions are reconstructed from
                the insight history.

        Returns:
            Dict with keys: session_ids, sessions (list of reviewed insights),
            total_analysed.
        """
        try:
            # If we have a real messages provider, load actual session data
            if messages_provider is not None and callable(messages_provider):
                reviewed: list[dict[str, Any]] = []
                session_ids: list[str] = []
                # The provider should return (session_id, messages) pairs
                async for session_id, messages in messages_provider(limit):
                    if not messages:
                        continue
                    insight = await self._session_reviewer.review_session(
                        session_id, messages,
                    )
                    reviewed.append(insight)
                    session_ids.append(session_id)
                    self._total_sessions_analysed += 1

                # Store in rolling insights list
                self._insights.extend(reviewed)
                # Keep only the most recent 200 insights
                self._insights = self._insights[-200:]

                return {
                    "session_ids": session_ids,
                    "sessions": reviewed,
                    "total_analysed": len(reviewed),
                }

            # Fallback: use already-stored insights
            recent = self._insights[-limit:]
            return {
                "session_ids": [s.get("session_id", "") for s in recent],
                "sessions": recent,
                "total_analysed": len(recent),
            }

        except Exception:
            logger.exception("analyze_recent_sessions failed")
            return {"session_ids": [], "sessions": [], "total_analysed": 0}

    # -- Memory & Persistence --------------------------------------------

    async def _write_to_memory(
        self,
        recent: dict[str, Any],
        patterns: list[dict[str, Any]],
        knowledge: dict[str, Any],
    ) -> None:
        """Write distilled insights to the memory system."""
        if self._memory is None:
            return

        try:
            # Store significant patterns as semantic memories
            for p in patterns:
                if p.get("confidence", 0) > 0.6:
                    text = (
                        f"[Dreaming] Pattern ({p.get('category', 'unknown')}): "
                        f"{p.get('description', '')}"
                    )
                    self._memory.add_semantic(
                        text,
                        metadata={
                            "type": "dreaming_pattern",
                            "category": p.get("category", "unknown"),
                            "confidence": p.get("confidence", 0),
                            "timestamp": _now(),
                        },
                    )

            # Store project rules
            for rule in knowledge.get("project_rules", []):
                self._memory.add_semantic(
                    f"[Project Rule] {rule}",
                    metadata={
                        "type": "project_rule",
                        "source": "dreaming",
                        "timestamp": _now(),
                    },
                )

            # Store tool tips
            for tip in knowledge.get("tool_tips", []):
                self._memory.add_semantic(
                    f"[Tool Tip] {tip}",
                    metadata={
                        "type": "tool_tip",
                        "source": "dreaming",
                        "timestamp": _now(),
                    },
                )

            logger.debug("Wrote %d memories from dreaming cycle", len(patterns) + len(knowledge.get("project_rules", [])))
        except Exception:
            logger.exception("Failed to write dreaming insights to memory")

    def _persist(self) -> None:
        """Persist all accumulated insights to the JSONL file."""
        try:
            payload: dict[str, Any] = {
                "timestamp": _now(),
                "dream_count": self._dream_count,
                "total_sessions_analysed": self._total_sessions_analysed,
                "last_dream_time": self._last_dream_time,
                "insights_count": len(self._insights),
                "patterns_count": len(self._patterns),
                "knowledge": self._knowledge,
                "patterns": self._patterns[-20:],  # Keep last 20 patterns
                "recent_insights": self._insights[-10:],  # Keep last 10 insights
            }

            with self._insights_path.open("w", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

            logger.debug("Dreaming insights persisted to %s", self._insights_path)
        except Exception:
            logger.exception("Failed to persist dreaming insights")

    # -- Query methods ---------------------------------------------------

    def get_insights(self) -> dict[str, Any]:
        """Get the current accumulated learning results.

        Returns a dict formatted as a context block suitable for LLM consumption.
        """
        try:
            # Try to load latest persisted insights
            if self._insights_path.exists():
                raw = self._insights_path.read_text(encoding="utf-8").strip()
                if raw:
                    try:
                        persisted = json.loads(raw)
                        # Merge with in-memory state
                        self._knowledge = persisted.get("knowledge", self._knowledge)
                        self._patterns = persisted.get("patterns", self._patterns)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

        knowledge = self._knowledge
        patterns = self._patterns

        context_blocks: list[str] = []

        # Project rules block
        rules = knowledge.get("project_rules", [])
        if rules:
            context_blocks.append("<dreaming_project_rules>\n" + "\n".join(f"- {r}" for r in rules) + "\n</dreaming_project_rules>")

        # Tool tips block
        tips = knowledge.get("tool_tips", [])
        if tips:
            context_blocks.append("<dreaming_tool_tips>\n" + "\n".join(f"- {t}" for t in tips) + "\n</dreaming_tool_tips>")

        # Best practices block
        practices = knowledge.get("best_practices", [])
        if practices:
            context_blocks.append("<dreaming_best_practices>\n" + "\n".join(f"- {p}" for p in practices) + "\n</dreaming_best_practices>")

        # Architecture notes block
        notes = knowledge.get("architecture_notes", [])
        if notes:
            context_blocks.append("<dreaming_architecture>\n" + "\n".join(f"- {n}" for n in notes) + "\n</dreaming_architecture>")

        # Patterns block
        high_confidence_patterns = [p for p in patterns if p.get("confidence", 0) > 0.5]
        if high_confidence_patterns:
            lines: list[str] = []
            for p in high_confidence_patterns[:5]:
                lines.append(
                    f"- [{p.get('category', 'unknown')}] "
                    f"{p.get('description', '')} "
                    f"(confidence: {p.get('confidence', 0):.2f})"
                )
            context_blocks.append("<dreaming_patterns>\n" + "\n".join(lines) + "\n</dreaming_patterns>")

        return {
            "has_insights": bool(context_blocks),
            "context_blocks": context_blocks,
            "full_context": "\n\n".join(context_blocks) if context_blocks else "",
            "dream_count": self._dream_count,
            "total_sessions_analysed": self._total_sessions_analysed,
            "last_dream_time": self._last_dream_time,
            "patterns_count": len(self._patterns),
            "rules_count": len(knowledge.get("project_rules", [])),
            "tips_count": len(knowledge.get("tool_tips", [])),
        }

    def get_status(self) -> dict[str, Any]:
        """Get current dreaming engine status."""
        return {
            "is_dreaming": self._is_dreaming,
            "is_running": self._dreaming_task is not None and not self._dreaming_task.done(),
            "dream_interval": self._dream_interval,
            "last_dream_time": self._last_dream_time,
            "seconds_since_last_dream": _now() - self._last_dream_time if self._last_dream_time > 0 else -1,
            "dream_count": self._dream_count,
            "total_sessions_analysed": self._total_sessions_analysed,
            "insights_stored": len(self._insights),
            "patterns_mined": len(self._patterns),
            "has_knowledge": bool(self._knowledge.get("project_rules")),
            "min_sessions_for_dreaming": self._min_sessions_for_dreaming,
            "enabled": _is_dreaming_enabled(),
            "insights_path": str(self._insights_path),
        }
