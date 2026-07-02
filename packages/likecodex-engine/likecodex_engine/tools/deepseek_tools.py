"""DeepSeek V4 specific tools for LikeCodex.

These tools are registered only when the DeepSeek provider is active.
They provide DeepSeek-specific capabilities: cache analysis, reasoning,
prompt optimization, model switching, and cost estimation.
"""

from __future__ import annotations

import json
import time
from typing import Any

from likecodex_engine.llm.base import Message, Role
from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.llm.factory import create_provider

# Tool registry for conditional registration
TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {}


def tool(
    name: str,
    description: str,
    read_only: bool = True,
    parameters: dict | None = None,
) -> Any:
    """Decorator to register a DeepSeek-specific tool."""

    def decorator(func: Any) -> Any:
        TOOL_DEFINITIONS[name] = {
            "name": name,
            "description": description,
            "read_only": read_only,
            "handler": func,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        return func

    return decorator


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


@tool(
    name="deepseek_cache_analyze",
    description=(
        "Analyze current session's DeepSeek prefix cache efficiency, "
        "including hit rate, stability diagnostics, and optimization suggestions."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Optional session ID to analyze"},
            "detailed": {"type": "boolean", "description": "Include detailed diagnostics"},
        },
    },
)
async def deepseek_cache_analyze(
    session_id: str = "",
    detailed: bool = False,
) -> str:
    """Analyze DeepSeek prefix cache health for the current session."""
    ctx = _get_current_context(session_id)
    if not ctx:
        return json.dumps({"error": "Could not resolve session context"}, ensure_ascii=False)

    metrics = global_cache_metrics()
    hit_rate = metrics.hit_rate
    recent_rate = metrics.recent_hit_rate

    result: dict[str, Any] = {
        "basic": {
            "hit_rate": round(hit_rate, 4),
            "recent_hit_rate": round(recent_rate, 4),
            "request_count": metrics.request_count,
            "total_hit_tokens": metrics.total_hit_tokens,
            "total_miss_tokens": metrics.total_miss_tokens,
        },
        "optimization_tips": [],
    }

    if hit_rate < 0.3:
        result["optimization_tips"].append(
            "Low cache hit rate. Possible causes: system prompt recently changed, "
            "tool schemas fluctuating frequently, or session is very new."
        )
    elif hit_rate < 0.6:
        result["optimization_tips"].append("Moderate hit rate. Session should improve with more turns.")

    if not result["optimization_tips"]:
        result["optimization_tips"].append("Cache health is good, no optimization needed.")

    if detailed:
        result["detailed"] = {
            "session_id": session_id or "(current)",
            "cache_reset_count": metrics.cache_reset_count,
        }

    return json.dumps(result, indent=2, ensure_ascii=False)


tool(
    name="deepseek_reasoning",
    description=(
        "Perform deep reasoning using DeepSeek V4 Pro model with chain-of-thought. "
        "Use for complex logic, mathematics, architecture design, and debugging. "
        "Returns structured reasoning with step-by-step analysis."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The complex question to reason about"},
            "context": {"type": "string", "description": "Optional context or background information"},
            "detail_level": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Level of detail in reasoning",
            },
            "reasoning_steps": {
                "type": "integer",
                "description": "Number of structured reasoning steps (1-8)",
            },
            "output_format": {
                "type": "string",
                "enum": ["structured", "freeform"],
                "description": "Whether to enforce step-by-step structured output",
            },
        },
        "required": ["question"],
    },
)
async def deepseek_reasoning(
    question: str,
    context: str = "",
    detail_level: str = "high",
    reasoning_steps: int = 4,
    output_format: str = "structured",
) -> str:
    """Invoke DeepSeek V4 Pro with thinking mode for complex reasoning.

    Enhanced with structured step-by-step reasoning, configurable detail levels,
    and explicit reasoning trace for complex problem-solving.
    """
    start_time = time.time()

    pro_llm = create_provider(
        provider="deepseek",
        model="deepseek-v4-pro",
        thinking=True,
        reasoning_effort=detail_level,
    )

    # Build structured reasoning prompt
    reasoning_prompt = _build_reasoning_prompt(
        question=question,
        context=context,
        detail_level=detail_level,
        reasoning_steps=min(max(reasoning_steps, 1), 8),
        output_format=output_format,
    )

    messages = [{"role": "user", "content": reasoning_prompt}]
    if context and output_format == "freeform":
        messages.insert(
            0,
            {
                "role": "system",
                "content": f"Context:\n{context}",
            },
        )

    response = await pro_llm.complete(
        messages=[_to_message(m) for m in messages],
        max_tokens=16384,
    )

    elapsed = time.time() - start_time

    # Extract reasoning steps from thinking content if available
    reasoning_steps_list: list[dict[str, str]] = []
    if response.reasoning_content and output_format == "structured":
        reasoning_steps_list = _extract_reasoning_steps(
            response.reasoning_content
        )

    result: dict[str, Any] = {
        "reasoning_process": response.reasoning_content or "",
        "answer": response.content,
        "model": response.model,
        "usage": response.usage,
        "timing": {
            "elapsed_seconds": round(elapsed, 2),
            "detail_level": detail_level,
        },
    }

    if reasoning_steps_list:
        result["structured_steps"] = reasoning_steps_list

    if output_format == "structured" and not reasoning_steps_list:
        # Parse steps from answer content if thinking content not available
        result["structured_steps"] = _extract_steps_from_answer(
            response.content or ""
        )

    result["reasoning_metadata"] = {
        "steps_requested": reasoning_steps,
        "steps_extracted": len(result.get("structured_steps", [])),
        "thinking_mode": bool(response.reasoning_content),
        "output_format": output_format,
    }

    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Reasoning helpers
# ---------------------------------------------------------------------------


def _build_reasoning_prompt(
    question: str,
    context: str,
    detail_level: str,
    reasoning_steps: int,
    output_format: str,
) -> str:
    """Build a structured reasoning prompt for DeepSeek V4 Pro."""
    if output_format == "freeform":
        base = f"Please reason about the following: {question}"
        if context:
            base = f"Context: {context}\n\n{base}"
        return base

    steps_guide = "\n".join(
        f"Step {i+1}: {_get_step_description(i, reasoning_steps)}"
        for i in range(reasoning_steps)
    )

    detail_guide = {
        "low": "Keep each step concise (1-2 sentences).",
        "medium": "Provide moderate detail in each step (2-4 sentences).",
        "high": "Be thorough. Explain assumptions, alternatives, and reasoning in each step.",
    }

    prompt = (
        "You are an expert reasoning system. Analyze the following question "
        f"step by step using exactly {reasoning_steps} reasoning steps.\n\n"
        f"## Question\n{question}\n\n"
    )

    if context:
        prompt += f"## Context\n{context}\n\n"

    prompt += (
        "## Reasoning Steps\n"
        f"Follow these {reasoning_steps} steps:\n{steps_guide}\n\n"
        f"## Style\n{detail_guide.get(detail_level, detail_guide['medium'])}\n\n"
        "## Output Format\n"
        "Return your answer in this exact format:\n"
        "```\n"
        "**Step 1: [title]**\n[content]\n\n"
        "**Step 2: [title]**\n[content]\n\n"
        "...\n\n"
        "**Conclusion**\n[final answer]\n```"
    )

    return prompt


def _get_step_description(step_index: int, total_steps: int) -> str:
    """Get a description for each reasoning step."""
    step_templates = [
        "Problem restatement and goal clarification",
        "Identify key constraints, assumptions, and known facts",
        "Explore possible approaches and relevant knowledge",
        "Develop a step-by-step solution or analysis",
        "Evaluate the solution for correctness and edge cases",
        "Consider alternatives and trade-offs",
        "Synthesize findings into a coherent answer",
        "Final verification and summary",
    ]
    return step_templates[step_index] if step_index < len(step_templates) else f"Reasoning step {step_index + 1}"


def _extract_reasoning_steps(reasoning_content: str) -> list[dict[str, str]]:
    """Extract structured reasoning steps from thinking content."""
    steps: list[dict[str, str]] = []
    lines = reasoning_content.split("\n")
    current_step: dict[str, str] = {}

    for line in lines:
        stripped = line.strip()
        # Match "Step N:" or "**Step N:**" patterns
        if stripped.lower().startswith("step") and ":" in stripped[:15]:
            if current_step and "content" in current_step:
                steps.append(current_step)
            title = stripped.split(":", 1)[-1].strip().strip("*").strip()
            current_step = {"title": title or f"Step {len(steps) + 1}", "content": ""}
        elif current_step:
            if current_step["content"]:
                current_step["content"] += "\n" + stripped
            else:
                current_step["content"] = stripped

    if current_step and "content" in current_step:
        steps.append(current_step)

    return steps


def _extract_steps_from_answer(answer: str) -> list[dict[str, str]]:
    """Extract reasoning steps from answer content."""
    steps: list[dict[str, str]] = []
    import re

    # Try to match markdown-style step headers
    pattern = r"\*\*Step\s+(\d+):?\s*([^*]+)\*\*"
    matches = list(re.finditer(pattern, answer))

    if matches:
        for i, match in enumerate(matches):
            step_num = match.group(1)
            title = match.group(2).strip()
            # Get content between this step header and the next
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(answer)
            content = answer[start:end].strip()
            steps.append({
                "title": f"Step {step_num}: {title}",
                "content": content,
            })
    else:
        # Fallback: split by numbered lists
        parts = re.split(r"\n(?=\d+\.\s+|Step\s+\d+[\s:]+)", answer)
        for part in parts:
            if part.strip():
                steps.append({
                    "title": f"Step {len(steps) + 1}",
                    "content": part.strip(),
                })

    return steps


@tool(
    name="deepseek_switch_model",
    description=(
        "Dynamically switch between DeepSeek V4 Flash and Pro models "
        "for the current session. Use when task complexity changes."
    ),
    read_only=False,
    parameters={
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "enum": ["flash", "pro"],
                "description": "Target model to switch to",
            },
            "reason": {"type": "string", "description": "Reason for switching models"},
        },
        "required": ["model"],
    },
)
async def deepseek_switch_model(
    model: str,
    reason: str = "",
) -> str:
    """Switch the current session's model."""
    valid_models = {
        "flash": "deepseek-v4-flash",
        "pro": "deepseek-v4-pro",
    }

    normalized = model.strip().lower()
    if normalized not in valid_models:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid model '{model}'. Choose from: {list(valid_models.keys())}",
            },
            ensure_ascii=False,
        )

    # Attempt to find and update the current session's LLM provider
    session = _get_current_session()
    if session and hasattr(session, "llm"):
        old_model = getattr(session.llm, "model", "unknown")
        session.llm = create_provider(
            provider="deepseek",
            model=valid_models[normalized],
        )
        return json.dumps(
            {
                "success": True,
                "switched_from": old_model,
                "switched_to": valid_models[normalized],
                "reason": reason or "No reason given",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "success": False,
            "error": "Could not find an active session to update.",
        },
        ensure_ascii=False,
    )


@tool(
    name="deepseek_cost_estimate",
    description=(
        "Estimate token usage and cost for a task before executing it. Helps users decide whether to proceed."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "Description of the task to estimate",
            },
            "estimated_steps": {
                "type": "integer",
                "description": "Estimated number of steps/turns",
            },
            "files_to_read": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths that will be read",
            },
            "model": {
                "type": "string",
                "enum": ["flash", "pro"],
                "description": "Model to use for estimation",
            },
        },
        "required": ["task_description"],
    },
)
async def deepseek_cost_estimate(
    task_description: str,
    estimated_steps: int = 5,
    files_to_read: list[str] | None = None,
    model: str = "flash",
) -> str:
    """Estimate the cost of a task."""
    model_prices = {
        "flash": {"input": 0.10, "output": 0.40, "cache_hit": 0.01},
        "pro": {"input": 0.50, "output": 2.00, "cache_hit": 0.05},
    }
    prices = model_prices.get(model, model_prices["flash"])

    # Rough estimation
    system_prompt_tokens = 2000
    file_tokens = len(files_to_read or []) * 500  # ~500 tokens per file

    step_input = system_prompt_tokens + file_tokens + 500
    step_output = 1000
    total_input = step_input * (estimated_steps + 1)
    total_output = step_output * estimated_steps

    # Assume 60% cache hit rate after first turn
    cache_hit_rate = 0.6
    cached_tokens = int(total_input * cache_hit_rate)
    uncached_tokens = total_input - cached_tokens

    cost = {
        "uncached_input": round(uncached_tokens / 1_000_000 * prices["input"], 6),
        "cached_input": round(cached_tokens / 1_000_000 * prices["cache_hit"], 6),
        "output": round(total_output / 1_000_000 * prices["output"], 6),
    }
    cost["total_usd"] = round(cost["uncached_input"] + cost["cached_input"] + cost["output"], 6)

    return json.dumps(
        {
            "task": task_description[:200],
            "model": model,
            "estimated_steps": estimated_steps,
            "estimated_tokens": {
                "input": total_input,
                "output": total_output,
                "cache_hit_estimate": f"{cache_hit_rate * 100:.0f}%",
            },
            "estimated_cost_usd": cost,
            "note": "Estimate only. Actual costs may vary.",
        },
        indent=2,
        ensure_ascii=False,
    )


@tool(
    name="deepseek_tune_prompt",
    description=(
        "Analyze and optimize system prompts for DeepSeek V4 models. "
        "Use when the model is not following instructions well or producing "
        "suboptimal code. Suggests improved prompt templates."
    ),
    read_only=True,
    parameters={
        "type": "object",
        "properties": {
            "current_prompt": {
                "type": "string",
                "description": "Current system prompt content to optimize",
            },
            "pain_points": {
                "type": "string",
                "description": (
                    "Description of issues encountered (e.g., 'tool call format "
                    "inconsistent', 'code often incomplete')"
                ),
            },
        },
        "required": ["current_prompt", "pain_points"],
    },
)
async def deepseek_tune_prompt(
    current_prompt: str,
    pain_points: str,
) -> str:
    """Use Flash to analyze and suggest improvements for DeepSeek V4 prompts."""
    flash_llm = create_provider(
        provider="deepseek",
        model="deepseek-v4-flash",
        thinking=False,
    )

    optimization_prompt = (
        "You are a DeepSeek V4 prompt optimization expert.\n"
        "Analyze the following issues and suggest an optimized system prompt.\n\n"
        f"Current prompt:\n```\n{current_prompt[:3000]}\n```\n\n"
        f"Issues encountered:\n{pain_points}\n\n"
        "Provide an optimized complete system prompt. Guidelines:\n"
        "1. Keep format stable (maintain prefix cache)\n"
        "2. Make tool usage rules explicit\n"
        "3. Leverage DeepSeek V4's instruction following capability\n"
        "4. Address the specific issues mentioned\n\n"
        "Return ONLY the optimized prompt, no additional explanation."
    )

    response = await flash_llm.complete(
        messages=[_to_message({"role": "user", "content": optimization_prompt})],
        max_tokens=4096,
    )

    return response.content or "Could not generate optimized prompt."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_current_context: dict[str, Any] = {}
_current_session: Any = None


def _get_current_context(session_id: str = "") -> Any:
    """Get the current context manager (simplified)."""
    if session_id and session_id in _current_context:
        return _current_context[session_id]
    if _current_context:
        return next(iter(_current_context.values()))
    return None


def _get_current_session() -> Any:
    """Get the current active session."""
    return _current_session


def set_current_session(session: Any, ctx: Any, session_id: str = "") -> None:
    """Set the current session and context (called by server on each request)."""
    global _current_session, _current_context
    _current_session = session
    if session_id:
        _current_context[session_id] = ctx
    else:
        _current_context["default"] = ctx


def _to_message(d: dict[str, Any]) -> Any:
    """Convert a dict to an LLM Message object."""
    return Message(
        role=Role(d.get("role", "user")),
        content=d.get("content", ""),
    )
