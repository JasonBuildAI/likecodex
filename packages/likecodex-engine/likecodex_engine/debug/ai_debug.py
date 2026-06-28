"""AI Debug Assistant — analyzes errors and provides fix suggestions."""

from __future__ import annotations

import os
from typing import Any

from likecodex_engine.llm.base import Message, Role


class AIDebugAssistant:
    """AI assistant for debugging — analyzes errors and suggests fixes."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def analyze_error(
        self,
        error_message: str,
        stack_trace: str,
        relevant_code: str,
        file_path: str,
    ) -> dict[str, str]:
        """Analyze an error and provide fix suggestions.

        Returns dict with: root_cause, fix, prevention
        """
        language = self._detect_language(file_path)

        prompt = f"""Analyze the following code error and provide a fix.

File: {file_path}
Error: {error_message}
Stack trace:
{stack_trace[:2000]}

Relevant code:
```{language}
{relevant_code[:3000]}
```

Provide:
1. Root cause (one sentence)
2. Fix (specific code change description)
3. Prevention (how to avoid in future)

Respond in this format:
Root Cause: <one sentence>
Fix: <specific fix description>
Prevention: <prevention tip>"""

        messages = [
            Message(role=Role.SYSTEM, content="You are a debugging expert. Analyze errors and provide clear fixes."),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            response = await self.llm.complete(messages, max_tokens=800, temperature=0.2)
            text = response.content.strip()

            # Parse the response
            root_cause = ""
            fix = ""
            prevention = ""

            for line in text.split("\n"):
                lower = line.lower()
                if lower.startswith("root cause"):
                    root_cause = line.split(":", 1)[1].strip() if ":" in line else ""
                elif lower.startswith("fix"):
                    fix = line.split(":", 1)[1].strip() if ":" in line else ""
                elif lower.startswith("prevention"):
                    prevention = line.split(":", 1)[1].strip() if ":" in line else ""

            return {
                "root_cause": root_cause or text[:200],
                "fix": fix or "See analysis above",
                "prevention": prevention or "",
            }
        except Exception as exc:
            return {
                "root_cause": f"Analysis failed: {exc}",
                "fix": "",
                "prevention": "",
            }

    @staticmethod
    def _detect_language(file_path: str) -> str:
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".tsx": "typescript", ".rs": "rust", ".go": "go",
            ".java": "java", ".c": "c", ".cpp": "cpp",
        }
        _, ext = os.path.splitext(file_path)
        return ext_map.get(ext.lower(), "text")
