"""Network diagnostic tools (ping, DNS, traceroute, HTTP, port scan)."""

from __future__ import annotations

import json
import subprocess
from typing import Any

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class NetworkTools:
    """Tools for network diagnostics and inspection."""

    @staticmethod
    def ping_schema() -> dict[str, Any]:
        return {
            "description": "Ping a host to check reachability and latency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Hostname or IP address to ping",
                    },
                    "count": {
                        "type": "integer",
                        "default": 4,
                        "description": "Number of ping packets",
                    },
                },
                "required": ["host"],
            },
        }

    @staticmethod
    def dns_lookup_schema() -> dict[str, Any]:
        return {
            "description": "Perform a DNS lookup for a domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain name to resolve"},
                },
                "required": ["domain"],
            },
        }

    @staticmethod
    def traceroute_schema() -> dict[str, Any]:
        return {
            "description": "Trace the network route to a host.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target hostname or IP"},
                },
                "required": ["host"],
            },
        }

    @staticmethod
    def http_headers_schema() -> dict[str, Any]:
        return {
            "description": "Fetch HTTP response headers from a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP/HTTPS URL"},
                    "method": {
                        "type": "string",
                        "enum": ["GET", "HEAD"],
                        "default": "HEAD",
                    },
                },
                "required": ["url"],
            },
        }

    @staticmethod
    def port_scan_schema() -> dict[str, Any]:
        return {
            "description": "Check whether specific TCP ports are open on a host.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Hostname or IP"},
                    "ports": {
                        "type": "string",
                        "description": "Comma-separated ports or range (e.g. 22,80,443 or 1-1024)",
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 2,
                        "description": "Connection timeout in seconds",
                    },
                },
                "required": ["host", "ports"],
            },
        }

    async def ping(self, host: str, count: int = 4) -> str:
        try:
            cmd = ["ping", "-n", str(count), host]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return json.dumps({
                "host": host,
                "count": count,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "ping timed out", "host": host})
        except FileNotFoundError:
            return json.dumps({"error": "ping command not found", "host": host})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def dns_lookup(self, domain: str) -> str:
        try:
            import socket

            info = socket.getaddrinfo(domain, None)
            addresses = sorted(set(item[4][0] for item in info))
            return json.dumps({
                "domain": domain,
                "addresses": addresses,
                "count": len(addresses),
            })
        except socket.gaierror as e:
            return json.dumps({"error": f"DNS resolution failed: {e}", "domain": domain})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def traceroute(self, host: str) -> str:
        try:
            cmd = ["tracert", "-h", "20", host]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return json.dumps({
                "host": host,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "traceroute timed out", "host": host})
        except FileNotFoundError:
            return json.dumps({"error": "tracert command not found"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def http_headers(self, url: str, method: str = "HEAD") -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required. Install with: pip install httpx"})
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, url, timeout=15)
                headers = dict(resp.headers)
                return json.dumps({
                    "url": str(resp.url),
                    "status_code": resp.status_code,
                    "headers": headers,
                })
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})

    async def port_scan(self, host: str, ports: str, timeout: int = 2) -> str:
        try:
            import socket as sock_mod

            parsed_ports: list[int] = []
            for part in ports.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-", 1)
                    parsed_ports.extend(range(int(start), int(end) + 1))
                else:
                    parsed_ports.append(int(part))

            open_ports: list[dict[str, Any]] = []
            closed_ports: list[int] = []

            for port in parsed_ports[:100]:  # limit to 100 ports
                try:
                    s = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
                    s.settimeout(timeout)
                    result = s.connect_ex((host, port))
                    if result == 0:
                        try:
                            service = sock_mod.getservbyport(port)
                        except OSError:
                            service = "unknown"
                        open_ports.append({"port": port, "service": service})
                    else:
                        closed_ports.append(port)
                    s.close()
                except Exception:
                    closed_ports.append(port)

            return json.dumps({
                "host": host,
                "scanned": len(parsed_ports),
                "open": open_ports,
                "open_count": len(open_ports),
                "closed_count": len(closed_ports),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
