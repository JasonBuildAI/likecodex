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

    async def _fetch_json(self, request_or_url, *, query: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None, timeout: int = 10) -> tuple[dict | None, str | None]:
        """Fetch JSON from a URL. Returns (data, None) on success or (None, error_json) on failure."""
        if isinstance(request_or_url, str):
            req = urllib.request.Request(request_or_url)
        else:
            req = request_or_url
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8")), None
        except Exception as exc:
            return None, json.dumps({"error": str(exc), "query": query})

    async def _duckduckgo_search(self, query: str, max_results: int) -> str:
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1})
        data, err = await self._fetch_json(url, query=query)
        if err:
            return err
        results = [
            {"text": item["Text"], "url": item.get("FirstURL", "")}
            for item in (data.get("RelatedTopics") or [])[:max_results]
            if isinstance(item, dict) and "Text" in item
        ]
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
        data, err = await self._fetch_json(req, query=query, timeout=15)
        if err:
            return err
        results = [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "content": r.get("content", "")[:300],
            }
            for r in data.get("results", [])
        ]
        return json.dumps({"engine": "tavily", "query": query, "results": results})
