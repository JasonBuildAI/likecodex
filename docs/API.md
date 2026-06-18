# LikeCodex HTTP API

Base URLs:

- Python Engine: `http://127.0.0.1:9090`
- Rust Server: `http://127.0.0.1:8080`
- Web UI (dev): `http://127.0.0.1:3000`

## Rust Server

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/config` | Redacted configuration |
| POST | `/tasks` | Create agent task |
| POST | `/chat` | Stream chat via SSE |
| POST | `/execute` | Sandbox command execution (Bearer token if configured) |
| GET | `/events` | Global SSE event stream |
| GET | `/permissions/pending` | Pending permission requests |
| POST | `/permissions/{id}/respond` | Approve/deny permission |
| GET | `/sessions` | List persisted sessions |
| GET | `/sessions/{id}/events` | Session event history |
| GET | `/index/search?pattern=` | Filename index search |

## Python Engine

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/run` | Run prompt synchronously |
| POST | `/chat` | Stream agent output (SSE) |
| POST | `/plan` | Generate plan only |
| POST | `/tasks` | Background task |
| GET | `/tasks/{id}` | Task status and outputs |
| GET | `/permissions/pending` | Pending approvals |
| POST | `/permissions/{id}/respond` | Respond to approval |
| GET | `/sessions` | List sessions |
| GET | `/sessions/{id}/events` | Session events |

See [EVENTS.md](EVENTS.md) for SSE payload format.
