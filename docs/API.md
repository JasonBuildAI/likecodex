# LikeCodex HTTP API

Base URLs:

- Python Engine: `http://127.0.0.1:9090`
- Rust Server: `http://127.0.0.1:8080`
- Web UI (dev): `http://127.0.0.1:3000`

---

## Rust Server Endpoints

The Rust server (`likecodex-server`) acts as the **control plane**, bridging clients to the Python engine and providing real-time event streaming.

### Health & Diagnostics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — returns `"ok"` if server is running |
| GET | `/config` | Redacted configuration (secrets excluded) |
| GET | `/metrics` | Prometheus-style metrics (proxied from engine) |
| GET | `/doctor` | Full environment diagnostics |

### Task Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/tasks` | Create and execute an agent task |
| POST | `/chat` | Stream chat response via SSE |
| POST | `/run` | Execute a one-shot prompt synchronously |
| POST | `/plan` | Generate a structured plan only |

#### POST /tasks

Request body:
```json
{
  "prompt": "add unit tests for utils.py",
  "session_id": "optional-session-id",
  "no_tools": false,
  "approval_mode": "auto"
}
```

Response:
```json
{
  "task": {
    "id": "task_abc123",
    "prompt": "add unit tests for utils.py",
    "status": "running",
    "created_at": "2026-07-02T12:00:00Z"
  }
}
```

### Streaming (SSE)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/events` | Global SSE event stream for all active tasks |
| GET | `/sessions/{id}/events` | SSE stream filtered to one session |

### Permissions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/permissions/pending` | List all pending permission requests |
| POST | `/permissions/{id}/respond` | Approve or deny a permission request |

Request body for `/permissions/{id}/respond`:
```json
{
  "response": "allow_once"
}
```

Valid responses: `allow_once`, `allow_forever`, `deny_once`, `deny_forever`

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions` | List all persisted sessions |
| GET | `/sessions/{id}` | Get session details and history |
| DELETE | `/sessions/{id}` | Delete a session |

### Execution

| Method | Path | Description |
|--------|------|-------------|
| POST | `/execute` | Execute a command (local or sandbox). Requires Bearer token if configured. |
| GET | `/execute/{id}` | Get execution result by ID |

Request body for `/execute`:
```json
{
  "command": "python test.py",
  "timeout": 30,
  "sandbox": false,
  "env": {"KEY": "value"}
}
```

### Index & Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/index/search?pattern=` | Search indexed filenames |
| POST | `/codegraph/search` | Semantic code search via CodeGraph |
| POST | `/codegraph/symbols` | Get symbol definitions |

### Checkpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/checkpoints` | List available checkpoints |
| POST | `/checkpoints/rewind` | Restore workspace to a checkpoint state |

---

## Python Engine Endpoints

The Python engine (`likecodex-engine`) is the **agent brain**, handling LLM interactions, tool execution, and context management.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — returns `{"status": "ok"}` |
| GET | `/metrics` | Cache metrics: `hit_rate`, `recent_hit_rate`, token counters |

### Agent Interaction

| Method | Path | Description |
|--------|------|-------------|
| POST | `/run` | Run prompt synchronously and return final output |
| POST | `/chat` | Stream agent output via Server-Sent Events (SSE) |
| POST | `/plan` | Generate plan only (no execution) |
| POST | `/tasks` | Create background task |

#### POST /run

Request:
```json
{
  "prompt": "list files in the workspace",
  "session_id": "my-session",
  "approval_mode": "auto",
  "model": "deepseek-v4-flash"
}
```

Response:
```json
{
  "outputs": [
    {"type": "text", "content": "Here are the files..."},
    {"type": "tool_call", "name": "read_file", "input": "..."},
    {"type": "tool_result", "content": "..."}
  ],
  "session_id": "my-session"
}
```

#### POST /chat (SSE Stream)

Request:
```json
{
  "prompt": "explain this codebase",
  "session_id": "my-session",
  "stream": true
}
```

Response is an SSE stream with events:
```text
data: {"type": "delta", "content": "This codebase..."}
data: {"type": "message", "content": "Final answer..."}
data: [DONE]
```

#### POST /tasks

Request:
```json
{
  "prompt": "refactor the auth module",
  "session_id": "my-session",
  "no_tools": false
}
```

Response:
```json
{
  "task_id": "task_xyz",
  "status": "started"
}
```

### Task Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks/{id}` | Get task status and outputs |
| GET | `/tasks/{id}/events` | Get SSE events for a task |

### Permissions (Engine)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/permissions/pending` | List pending approval requests |
| POST | `/permissions/{id}/respond` | Respond to a pending request |

### Sessions (Engine)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions` | List all sessions |
| GET | `/sessions/{id}` | Get session details |
| GET | `/sessions/{id}/events` | Get session event history |
| POST | `/sessions/cleanup` | Clean up stale sessions |

---

## SSE Event Format

The Rust server normalizes events using adjacently tagged JSON over `text/event-stream`:

```json
{"type":"stream_chunk","payload":{"task_id":"...","content":"..."}}
```

### Event Types

| Type | Payload | Description |
|------|---------|-------------|
| `task_started` | `Task` | Task created and queued |
| `task_completed` | `Task` | Task finished (check `status` field) |
| `stream_chunk` | `{task_id, content}` | Assistant text chunk |
| `stream_finished` | `{task_id}` | Stream ended normally |
| `stream_retrying` | `{task_id, attempt, max, message, reason}` | Stream recovery or provider retry |
| `compaction_started` | `{task_id, trigger}` | Context compaction beginning |
| `compaction_done` | `{task_id, messages, summary_chars, archive?}` | Context compaction completed |
| `checkpoint_created` | `{task_id, checkpoint_id, label, files}` | File snapshot before write |
| `tool_call_requested` | `{task_id, call}` | Tool about to execute |
| `tool_call_completed` | `{task_id, result}` | Tool execution finished |
| `tool_dispatch` | `{task_id, calls[]}` | Batch tool dispatch event |
| `permission_requested` | `{task_id, request}` | User approval needed |
| `permission_responded` | `{task_id, request_id, response}` | Approval decision |
| `plan_created` | `Plan` | Planner generated a plan |
| `plan_updated` | `Plan` | Plan was modified |
| `message_added` | `{task_id, message}` | Conversation message added |
| `usage` | `{task_id, tokens, cache}` | Per-turn token usage with cache metrics |
| `notice` | `{task_id, message, type}` | Important notice (truncation, finish_reason warnings) |
| `error` | `{task_id?, message, recoverable?}` | Error occurred |

### SSE Stream Example

```
data: {"type":"task_started","payload":{"id":"task_123","status":"running"}}

data: {"type":"stream_chunk","payload":{"task_id":"task_123","content":"I'll analyze"}}

data: {"type":"tool_call_requested","payload":{"task_id":"task_123","call":{"name":"read_file","input":{"path":"utils.py"}}}}

data: {"type":"tool_call_completed","payload":{"task_id":"task_123","result":{"exit_code":0,"stdout":"def foo():"}}}

data: {"type":"task_completed","payload":{"id":"task_123","status":"completed"}}

data: [DONE]
```

---

## Tool Registration API

Tools are registered server-side in the Python engine. The following endpoints expose tool metadata:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tools` | List all registered tools and their schemas |
| GET | `/tools/{name}` | Get schema for a specific tool |

### Tool Schema Response

```json
{
  "name": "read_file",
  "description": "Read the contents of a file",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Path to the file to read"
      }
    },
    "required": ["path"]
  },
  "category": "filesystem"
}
```

### Tool Categories

- `filesystem` — read, write, edit, glob, ls, move operations
- `shell` — command execution, background jobs
- `search` — grep, codegraph, LSP diagnostics
- `git` — status, diff, log, branch, commit, push
- `web` — web_search, web_fetch
- `agent` — task, parallel_tasks, run_skill, ask
- `memory` — remember, forget, memory_search
- `review` — code_review, autoresearch
- `mcp` — mcp__\<server\>__\<tool\> (dynamic plugins)

---

## Authentication

### API Token

The Rust server supports optional Bearer token authentication on the `/execute` endpoint:

```
Authorization: Bearer <your-api-token>
```

Configure via `config.toml`:
```toml
[server]
api_token = "your-secret-token"
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPSEEK_API_KEY` | DeepSeek API key (required) |
| `LIKECODEX_LLM_PROVIDER` | LLM provider (`deepseek` or `mock`) |
| `LIKECODEX_LLM_MODEL` | Model name override |
| `LIKECODEX_ENGINE_PORT` | Python engine port (default: 9090) |
| `LIKECODEX_SERVER_PORT` | Rust server port (default: 8080) |
| `LIKECODEX_APPROVAL_MODE` | Default approval mode |
| `LIKECODEX_WORKING_DIR` | Workspace directory |
| `LIKECODEX_ENABLE_PLANNER` | Enable dual-model planner (`true`/`false`) |

---

## Configuration

Configuration is loaded from (priority low → high):

```
defaults → ~/.likecodex/config.toml → ./likecodex.toml → env vars → CLI flags
```

Full configuration reference: [docs/USAGE.md](USAGE.md)

---

## Error Handling

All endpoints return standard HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid JSON, missing fields) |
| 401 | Unauthorized (invalid/missing API token) |
| 404 | Resource not found (task, session, etc.) |
| 500 | Internal server error |
| 502 | Upstream error (engine unreachable) |
| 504 | Timeout (task exceeded deadline) |

Error response format:
```json
{
  "error": "description of what went wrong",
  "code": "ERROR_CODE",
  "details": {}
}
```

---

## Rate Limiting

The engine has built-in safeguards:

- Max tool calls per turn: 50
- Default command timeout: 60 seconds
- Max output length: 32KB (head + tail truncation with notice)
- Max session age: 24 hours (stale sessions auto-cleaned)

---

See [EVENTS.md](EVENTS.md) for full SSE payload schema.
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
