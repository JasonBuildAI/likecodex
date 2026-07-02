"""Google Gemini LLM provider."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import google.generativeai as genai

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, Role, ToolCall
from likecodex_engine.llm.openai_stream import complete_with_reconnect


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model, api_key, base_url)
        key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        genai.configure(api_key=key, transport="rest")
        self._model = genai.GenerativeModel(model_name=model)

    # ------------------------------------------------------------------
    # Message conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_gemini_contents(messages: list[Message]) -> list[dict[str, Any]]:
        """Convert internal messages to Gemini content parts format.

        Gemini uses:
          - contents: list of {"role": "user"|"model", "parts": [...]}
          - system_instruction (separate field)
        """
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == Role.SYSTEM:
                # System messages are handled separately; skip here
                continue

            role = "model" if m.role == Role.ASSISTANT else "user"
            parts: list[dict[str, Any]] = []

            if m.content:
                parts.append({"text": m.content})

            if m.tool_calls:
                for tc in m.tool_calls:
                    fn_name = tc.get("function", {}).get("name", "")
                    fn_args = tc.get("function", {}).get("arguments", "{}")
                    if isinstance(fn_args, str):
                        fn_args = json.loads(fn_args) if fn_args else {}
                    parts.append(
                        {
                            "functionCall": {
                                "name": fn_name,
                                "args": fn_args,
                            }
                        }
                    )

            if m.role == Role.TOOL and m.tool_call_id:
                parts.append(
                    {
                        "functionResponse": {
                            "name": m.name or m.tool_call_id,
                            "response": {
                                "name": m.name or m.tool_call_id,
                                "content": m.content,
                            },
                        }
                    }
                )

            out.append({"role": role, "parts": parts})
        return out

    @staticmethod
    def _get_system_instruction(messages: list[Message]) -> str | None:
        for m in messages:
            if m.role == Role.SYSTEM:
                return m.content
        return None

    @staticmethod
    def _to_gemini_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Convert OpenAI-style tool definitions to Gemini format."""
        if not tools:
            return None

        gemini_tools: list[dict[str, Any]] = []
        for tool in tools:
            fn = tool.get("function", tool)
            gemini_tools.append(
                {
                    "function_declarations": [
                        {
                            "name": fn.get("name", ""),
                            "description": fn.get("description", ""),
                            "parameters": fn.get("parameters", {}),
                        }
                    ]
                }
            )
        return gemini_tools

    @staticmethod
    def _parse_candidate(candidate: Any) -> tuple[str, list[ToolCall], str | None]:
        """Extract text and tool_calls from a Gemini candidate."""
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        finish_reason: str | None = None

        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason:
            finish_reason = str(finish_reason)

        content = getattr(candidate, "content", None)
        if content is None:
            return "".join(content_parts), tool_calls, finish_reason

        for part in content.parts:
            if hasattr(part, "text") and part.text:
                content_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call is not None:
                fc = part.function_call
                args = {}
                if hasattr(fc, "args") and fc.args:
                    args = dict(fc.args.items()) if hasattr(fc.args, "items") else {}
                tool_calls.append(
                    ToolCall(
                        id=getattr(fc, "name", "call_1"),
                        name=getattr(fc, "name", ""),
                        arguments=args,
                    )
                )

        return "".join(content_parts), tool_calls, finish_reason

    @staticmethod
    def _parse_usage(response: Any) -> dict[str, int]:
        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta is None:
            return {}
        return {
            "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0) or 0,
            "completion_tokens": getattr(usage_meta, "candidates_token_count", 0) or 0,
            "total_tokens": getattr(usage_meta, "total_token_count", 0) or 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        contents = self._to_gemini_contents(messages)
        system_instruction = self._get_system_instruction(messages)
        gemini_tools = self._to_gemini_tools(tools)

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # Build the generative model with system instruction if present
        model = self._model
        if system_instruction:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_instruction,
            )

        async def _create():
            return await model.generate_content_async(
                contents=contents,
                tools=gemini_tools,
                generation_config=generation_config,
            )

        resp = await complete_with_reconnect(_create)

        candidate = resp.candidates[0] if resp.candidates else None
        if candidate is None:
            return LLMResponse(content="", model=self.model)

        text_content, tool_calls, finish_reason = self._parse_candidate(candidate)
        usage = self._parse_usage(resp)
        if finish_reason:
            usage["finish_reason"] = finish_reason

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            model=self.model,
            usage=usage,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        contents = self._to_gemini_contents(messages)
        system_instruction = self._get_system_instruction(messages)
        gemini_tools = self._to_gemini_tools(tools)

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        model = self._model
        if system_instruction:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_instruction,
            )

        async def create_stream():
            return await model.generate_content_async(
                contents=contents,
                tools=gemini_tools,
                generation_config=generation_config,
                stream=True,
            )

        stream_resp = await create_stream()

        content_parts: list[str] = []
        tool_calls: list[ToolCall] | None = None
        finish_reason: str | None = None
        usage: dict[str, int] | None = None
        emitted = False

        async for chunk in stream_resp:
            if usage is None:
                usage = self._parse_usage(chunk)

            candidate = chunk.candidates[0] if chunk.candidates else None
            if candidate is None:
                continue

            fr = getattr(candidate, "finish_reason", None)
            if fr:
                finish_reason = str(fr)

            content = getattr(candidate, "content", None)
            if content is None:
                continue

            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    emitted = True
                    content_parts.append(part.text)
                    yield LLMResponse(
                        content=part.text,
                        model=self.model,
                        event_type="delta",
                    )

                if hasattr(part, "function_call") and part.function_call is not None:
                    fc = part.function_call
                    args = {}
                    if hasattr(fc, "args") and fc.args:
                        args = dict(fc.args.items()) if hasattr(fc.args, "items") else {}
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append(
                        ToolCall(
                            id=getattr(fc, "name", "call_1"),
                            name=getattr(fc, "name", ""),
                            arguments=args,
                        )
                    )
                    emitted = True
                    yield LLMResponse(
                        content="",
                        model=self.model,
                        event_type="tool_dispatch",
                        metadata={"tool_name": getattr(fc, "name", "")},
                    )

        final_content = "".join(content_parts)
        if final_content or tool_calls or finish_reason:
            merged_usage = dict(usage or {})
            if finish_reason:
                merged_usage["finish_reason"] = finish_reason
            yield LLMResponse(
                content=final_content,
                tool_calls=tool_calls or [],
                model=self.model,
                usage=merged_usage or None,
                event_type="assistant",
            )
