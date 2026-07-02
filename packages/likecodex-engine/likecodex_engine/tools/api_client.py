"""HTTP API client and WebSocket testing tools."""

from __future__ import annotations

import json
from typing import Any

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class ApiClientTools:
    """Tools for making HTTP requests and testing APIs."""

    @staticmethod
    def http_request_schema() -> dict[str, Any]:
        return {
            "description": "Make an HTTP request to any endpoint. Supports GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                        "default": "GET",
                    },
                    "url": {"type": "string", "description": "Full URL to request"},
                    "headers": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": "HTTP headers as key-value pairs",
                    },
                    "body": {
                        "type": "string",
                        "description": "Request body (JSON string or raw text)",
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 30,
                        "description": "Request timeout in seconds",
                    },
                },
                "required": ["url"],
            },
        }

    @staticmethod
    def api_test_schema() -> dict[str, Any]:
        return {
            "description": "Run a sequence of API test cases against an endpoint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "description": "Base URL of the API endpoint",
                    },
                    "tests": {
                        "type": "string",
                        "description": "JSON array of test objects. Each: {method, path, headers?, body?, expected_status?, expected_body_contains?}",
                    },
                },
                "required": ["endpoint", "tests"],
            },
        }

    @staticmethod
    def websocket_test_schema() -> dict[str, Any]:
        return {
            "description": "Test a WebSocket endpoint by sending a message and receiving a response.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "WebSocket URL (ws:// or wss://)"},
                    "message": {"type": "string", "description": "Message to send"},
                    "timeout": {
                        "type": "integer",
                        "default": 10,
                        "description": "Wait timeout in seconds",
                    },
                },
                "required": ["url", "message"],
            },
        }

    async def http_request(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout: int = 30,
    ) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required. Install with: pip install httpx"})
        try:
            content: Any = body
            if body and headers and headers.get("content-type", "").lower() in (
                "application/json",
                "application/json; charset=utf-8",
            ):
                try:
                    content = json.loads(body)
                except json.JSONDecodeError:
                    pass

            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method,
                    url,
                    headers=headers,
                    content=content if isinstance(content, str) else None,
                    json=content if not isinstance(content, str) else None,
                    timeout=timeout,
                )
                try:
                    response_body = resp.json()
                except Exception:
                    response_body = resp.text

                return json.dumps({
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": response_body,
                    "elapsed": resp.elapsed.total_seconds(),
                })
        except httpx.TimeoutException:
            return json.dumps({"error": "Request timed out", "url": url, "method": method})
        except Exception as e:
            return json.dumps({"error": str(e), "url": url, "method": method})

    async def api_test(self, endpoint: str, tests: str) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required"})
        try:
            test_cases: list[dict[str, Any]] = json.loads(tests)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid tests JSON: {e}"})

        results: list[dict[str, Any]] = []
        async with httpx.AsyncClient() as client:
            for i, tc in enumerate(test_cases):
                method = tc.get("method", "GET")
                path = tc.get("path", "/")
                url = endpoint.rstrip("/") + "/" + path.lstrip("/")
                headers = tc.get("headers")
                body = tc.get("body")
                expected_status = tc.get("expected_status")
                expected_body_contains = tc.get("expected_body_contains")

                content: Any = body
                if body and isinstance(body, str):
                    try:
                        content = json.loads(body)
                    except json.JSONDecodeError:
                        pass

                try:
                    resp = await client.request(
                        method,
                        url,
                        headers=headers,
                        json=content if not isinstance(content, str) else None,
                        content=content if isinstance(content, str) else None,
                        timeout=30,
                    )
                    passed = True
                    failures: list[str] = []
                    if expected_status is not None and resp.status_code != expected_status:
                        passed = False
                        failures.append(
                            f"Expected status {expected_status}, got {resp.status_code}"
                        )
                    if expected_body_contains:
                        text = resp.text
                        if expected_body_contains not in text:
                            passed = False
                            failures.append(
                                f"Body does not contain {expected_body_contains!r}"
                            )

                    results.append({
                        "test": i,
                        "method": method,
                        "path": path,
                        "status_code": resp.status_code,
                        "passed": passed,
                        "failures": failures,
                    })
                except Exception as e:
                    results.append({
                        "test": i,
                        "method": method,
                        "path": path,
                        "error": str(e),
                        "passed": False,
                    })

        passed_count = sum(1 for r in results if r["passed"])
        return json.dumps({
            "endpoint": endpoint,
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "results": results,
        })

    async def websocket_test(self, url: str, message: str, timeout: int = 10) -> str:
        try:
            import asyncio

            try:
                import websockets
            except ImportError:
                return json.dumps({
                    "error": "websockets is required. Install with: pip install websockets",
                })

            async with websockets.connect(url, timeout=timeout) as ws:
                await ws.send(message)
                response = await asyncio.wait_for(ws.recv(), timeout=timeout)
                return json.dumps({
                    "url": url,
                    "sent": message,
                    "received": str(response),
                })
        except asyncio.TimeoutError:
            return json.dumps({"error": "WebSocket response timed out", "url": url})
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})
