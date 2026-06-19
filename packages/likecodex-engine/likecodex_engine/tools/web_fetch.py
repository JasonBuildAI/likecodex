"""Fetch a URL and return readable text, with SSRF protections."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.request
from typing import Any
from urllib.parse import urlparse

_MAX_BYTES = 512_000
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n\s*\n\s*\n+")


class WebFetchTools:
    def fetch_schema(self) -> dict[str, Any]:
        return {
            "description": "Fetch a public http/https URL and return its text content (HTML stripped).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Absolute http(s) URL"},
                    "max_chars": {"type": "integer", "default": 8000},
                },
                "required": ["url"],
            },
        }

    async def web_fetch(self, url: str, max_chars: int = 8000) -> str:
        error = self._validate_url(url)
        if error:
            return json.dumps({"error": error, "url": url})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LikeCodex/0.1"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - validated above
                final_url = resp.geturl()
                # Re-validate after redirects to avoid SSRF via redirect.
                redirect_error = self._validate_url(final_url)
                if redirect_error:
                    return json.dumps({"error": f"redirect blocked: {redirect_error}", "url": final_url})
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read(_MAX_BYTES)
        except Exception as exc:
            return json.dumps({"error": str(exc), "url": url})

        text = raw.decode("utf-8", errors="replace")
        if "html" in content_type.lower() or "<html" in text[:2000].lower():
            text = self._html_to_text(text)
        text = text.strip()
        truncated = len(text) > max_chars
        return json.dumps(
            {
                "url": url,
                "content_type": content_type,
                "content": text[:max_chars],
                "truncated": truncated,
            }
        )

    @staticmethod
    def _html_to_text(html: str) -> str:
        html = _TAG_RE.sub(" ", html)
        html = _HTML_TAG_RE.sub(" ", html)
        html = (
            html.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
        )
        lines = [line.strip() for line in html.splitlines()]
        return _WS_RE.sub("\n\n", "\n".join(line for line in lines if line))

    @staticmethod
    def _validate_url(url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return "only http/https URLs are allowed"
        host = parsed.hostname
        if not host:
            return "missing host"
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror:
            return f"cannot resolve host: {host}"
        for info in infos:
            ip_str = info[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return f"blocked non-public address: {ip_str}"
        return None
