"""Adaptive reasoning control with 5-level depth.

Automatically adjusts LLM parameters (temperature, max_tokens, thinking)
based on task complexity analysis.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class ReasoningDepth(IntEnum):
    """Five levels of reasoning depth."""

    QUICK_QA = 0  # Simple Q&A, no thinking needed
    LIGHT_ANALYSIS = 1  # Basic refactoring, simple edits
    STANDARD = 2  # Normal coding tasks
    DEEP = 3  # Complex multi-step tasks
    FULL_REASONING = 4  # Architecture design, hard bugs


@dataclass
class TaskComplexity:
    """Result of task complexity analysis."""

    score: float = 0.0
    depth: ReasoningDepth = ReasoningDepth.STANDARD
    has_code: bool = False
    has_multi_step: bool = False
    has_debugging: bool = False
    has_architecture: bool = False
    token_estimate: int = 0
    reasoning: str = ""


# Heuristic weights for complexity scoring
_COMPLEXITY_WEIGHTS: dict[str, float] = {
    "code_block": 1.5,
    "multi_step": 2.0,
    "debug": 2.5,
    "architecture": 3.0,
    "question": 0.5,
    "explanation": 1.0,
    "external_ref": 1.5,
}


@dataclass
class ReasoningConfig:
    """LLM parameters for a given reasoning depth."""

    temperature: float = 0.7
    max_tokens: int = 4096
    thinking: bool = False
    top_p: float = 0.95
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


# Default parameter profiles for each depth level
_DEPTH_CONFIGS: dict[ReasoningDepth, ReasoningConfig] = {
    ReasoningDepth.QUICK_QA: ReasoningConfig(
        temperature=0.3,
        max_tokens=1024,
        thinking=False,
        top_p=0.9,
        presence_penalty=0.0,
        frequency_penalty=0.1,
    ),
    ReasoningDepth.LIGHT_ANALYSIS: ReasoningConfig(
        temperature=0.5,
        max_tokens=2048,
        thinking=False,
        top_p=0.92,
        presence_penalty=0.1,
        frequency_penalty=0.1,
    ),
    ReasoningDepth.STANDARD: ReasoningConfig(
        temperature=0.7,
        max_tokens=4096,
        thinking=False,
        top_p=0.95,
        presence_penalty=0.0,
        frequency_penalty=0.0,
    ),
    ReasoningDepth.DEEP: ReasoningConfig(
        temperature=0.8,
        max_tokens=8192,
        thinking=True,
        top_p=0.95,
        presence_penalty=0.1,
        frequency_penalty=0.0,
    ),
    ReasoningDepth.FULL_REASONING: ReasoningConfig(
        temperature=0.9,
        max_tokens=16384,
        thinking=True,
        top_p=0.98,
        presence_penalty=0.2,
        frequency_penalty=0.0,
    ),
}


class AdaptiveReasoningController:
    """Analyzes task prompts and adjusts LLM parameters accordingly.

    The controller uses heuristic analysis of the prompt text to estimate
    complexity, then selects the appropriate reasoning depth and parameter
    profile.
    """

    def __init__(
        self,
        default_depth: ReasoningDepth = ReasoningDepth.STANDARD,
        custom_configs: dict[ReasoningDepth, ReasoningConfig] | None = None,
    ) -> None:
        self.default_depth = default_depth
        self._configs = {**(_DEPTH_CONFIGS), **(custom_configs or {})}

    def analyze_task(self, prompt: str) -> TaskComplexity:
        """Analyze a prompt and return its complexity assessment.

        Uses lightweight heuristic scoring based on:
        - Presence of code blocks (```)
        - Multi-step indicators (numbered lists, "first", "then")
        - Debugging signals (error messages, stack traces)
        - Architecture signals (design, pattern, structure)
        - Question length and depth
        """
        complexity = TaskComplexity()
        score = 0.0

        # Code detection
        code_blocks = re.findall(r"```(?:\w+)?\n", prompt)
        if code_blocks:
            complexity.has_code = True
            score += len(code_blocks) * _COMPLEXITY_WEIGHTS["code_block"]

        # Multi-step detection
        step_patterns = re.findall(
            r"(?:\b(?:first|then|next|finally|step\s*\d+|步骤|然后|接着|最后)\b)",
            prompt,
            re.IGNORECASE,
        )
        if len(step_patterns) >= 2:
            complexity.has_multi_step = True
            score += math.log2(len(step_patterns)) * _COMPLEXITY_WEIGHTS["multi_step"]

        # Debugging signals
        debug_patterns = re.findall(
            r"(?:error|exception|traceback|bug|fix|crash|失败|错误|异常|bug)",
            prompt,
            re.IGNORECASE,
        )
        if debug_patterns:
            complexity.has_debugging = True
            score += len(debug_patterns) * _COMPLEXITY_WEIGHTS["debug"]

        # Architecture signals
        arch_patterns = re.findall(
            r"(?:architecture|design|pattern|structure|refactor|"
            r"架构|设计模式|重构|系统设计|方案)",
            prompt,
            re.IGNORECASE,
        )
        if arch_patterns:
            complexity.has_architecture = True
            score += len(arch_patterns) * _COMPLEXITY_WEIGHTS["architecture"]

        # Question depth (short questions are simpler)
        word_count = len(prompt.split())
        score += math.log2(max(word_count, 1)) * 0.3

        # External reference detection (file paths, URLs)
        refs = re.findall(r"(?:/[a-zA-Z0-9_./-]+|https?://\S+)", prompt)
        if refs:
            score += len(refs) * _COMPLEXITY_WEIGHTS["external_ref"]

        # Token estimate
        complexity.token_estimate = len(prompt) // 4  # rough estimate

        # Map score to depth
        depth_map = [
            (1.0, ReasoningDepth.QUICK_QA),
            (3.0, ReasoningDepth.LIGHT_ANALYSIS),
            (8.0, ReasoningDepth.STANDARD),
            (15.0, ReasoningDepth.DEEP),
        ]
        complexity.depth = ReasoningDepth.FULL_REASONING
        for threshold, depth in depth_map:
            if score <= threshold:
                complexity.depth = depth
                break

        complexity.score = round(score, 2)
        complexity.reasoning = (
            f"complexity_score={complexity.score}, depth={complexity.depth.name}, "
            f"code={complexity.has_code}, multi_step={complexity.has_multi_step}, "
            f"debug={complexity.has_debugging}, arch={complexity.has_architecture}"
        )
        return complexity

    def get_config(self, prompt: str | None = None, depth: ReasoningDepth | None = None) -> ReasoningConfig:
        """Get the reasoning config for the given prompt or explicit depth.

        Args:
            prompt: Optional prompt to analyze. If provided and depth is None,
                    the prompt will be analyzed to determine depth.
            depth: Optional explicit depth level. Takes precedence over analysis.
        """
        if depth is not None:
            return self._configs.get(depth, self._configs[self.default_depth])

        if prompt is not None:
            complexity = self.analyze_task(prompt)
            return self._configs.get(complexity.depth, self._configs[self.default_depth])

        return self._configs[self.default_depth]

    def apply_to_llm_kwargs(self, prompt: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Apply adaptive parameters to an LLM kwargs dict in-place.

        Modifies the kwargs dict with temperature, max_tokens, and other
        parameters appropriate for the given prompt's complexity.
        """
        config = self.get_config(prompt)
        kwargs["temperature"] = config.temperature
        kwargs["max_tokens"] = config.max_tokens
        kwargs["top_p"] = config.top_p
        kwargs["presence_penalty"] = config.presence_penalty
        kwargs["frequency_penalty"] = config.frequency_penalty
        if config.thinking:
            kwargs["thinking"] = True
        return kwargs

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation (characters / 4)."""
        return max(1, len(text) // 4)
