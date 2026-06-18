# LikeCodex Event Schema

Rust server emits events over SSE at `GET /events` using adjacently tagged JSON:

```json
{"type":"stream_chunk","payload":{"task_id":"...","content":"..."}}
```

## Event Types

| type | payload shape | Description |
|------|---------------|-------------|
| `task_started` | `Task` | Task created |
| `task_completed` | `Task` | Task finished (check `status`) |
| `stream_chunk` | `{ task_id, content }` | Assistant text chunk |
| `stream_finished` | `{ task_id }` | Stream ended |
| `tool_call_requested` | `{ task_id, call }` | Tool invocation |
| `tool_call_completed` | `{ task_id, result }` | Tool result |
| `permission_requested` | `{ task_id, request }` | Needs user approval |
| `permission_responded` | `{ task_id, response }` | Approval decision |
| `plan_created` / `plan_updated` | `Plan` | Planner output |
| `message_added` | `{ task_id, message }` | Conversation message |
| `error` | `{ task_id?, message }` | Error |

## Python Engine Output

The Python engine uses flat objects in task outputs:

```json
{"type":"assistant","content":"...","tool_calls":[],"model":"gpt-4o"}
```

The Rust server maps these to structured `Event` values before broadcasting.
