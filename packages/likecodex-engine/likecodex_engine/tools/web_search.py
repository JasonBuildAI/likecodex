"""Web search tool (configurable engine)."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


class WebSearchTools:
    def search_schema(self) -> dict:
        return {
            "description": "Search the web for documentation or recent information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        }

    async def web_search(self, query: str, max_results: int = 5) -> str:
        engine = os.environ.get("LIKECODEX_SEARCH_ENGINE", "duckduckgo")
        if engine == "tavily" and os.environ.get("TAVILY_API_KEY"):
            return await self._tavily_search(query, max_results)
        return await self._duckduckgo_search(query, max_results)

    async def _duckduckgo_search(self, query: str, max_results: int) -> str:
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": 1}
        )
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return json.dumps({"error": str(exc), "query": query})
        results = []
        for item in (data.get("RelatedTopics") or [])[:max_results]:
            if isinstance(item, dict) and "Text" in item:
                results.append({"text": item["Text"], "url": item.get("FirstURL", "")})
        return json.dumps({"engine": "duckduckgo", "query": query, "results": results})

    async def _tavily_search(self, query: str, max_results: int) -> str:
        api_key = os.environ.get("TAVILY_API_KEY", "")
        payload = json.dumps({"api_key": api_key, "query": query, "max_results": max_results}).encode()
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return json.dumps({"error": str(exc), "query": query})
        results = [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content", "")[:300]}
            for r in data.get("results", [])
        ]
        return json.dumps({"engine": "tavily", "query": query, "results": results})
