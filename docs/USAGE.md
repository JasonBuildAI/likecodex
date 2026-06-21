# LikeCodex Usage (DeepSeek V4)

## Quick Start

### Recommended daily workflow

```bash
likecodex setup          # first time: API key, config, project memory
likecodex start --web    # engine + API + Web UI (http://127.0.0.1:3000)
likecodex code           # terminal-only session
likecodex doctor --json  # health check with fix hints
```

### Legacy dev stack (contributors)

```bash
./scripts/dev.sh
# Windows: .\scripts\dev.ps1
```

### Configure LLM

User config: `~/.likecodex/config.toml`. Project overrides: `./likecodex.toml` or `./.likecodex/config.toml`.

```toml
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"   # or deepseek-v4-pro
api_key = "..."
base_url = "https://api.deepseek.com"

[deepseek]
thinking = false

[approval]
mode = "auto"  # read-only | auto | full-access | sandbox-required

[server]
port = 8080
engine_url = "http://127.0.0.1:9090"
api_token = "optional-local-token"

[sandbox]
enabled = true
allow_fallback = true
```

Or copy `.env.example` and set `DEEPSEEK_API_KEY`.

## Session continuity (cache hits)

Pass `session_id` to `/chat` or `/run` to continue a conversation and reuse the prompt prefix:

```bash
curl -X POST http://127.0.0.1:9090/run \
  -H "Content-Type: application/json" \
  -d '{"prompt":"first question","session_id":"my-session"}'

curl -X POST http://127.0.0.1:9090/run \
  -H "Content-Type: application/json" \
  -d '{"prompt":"follow up","session_id":"my-session"}'
```

## Cache metrics

```bash
curl http://127.0.0.1:9090/metrics
curl http://127.0.0.1:8080/metrics
```

Returns `hit_rate`, `recent_hit_rate`, and token counters from DeepSeek usage fields.

## CLI Commands

- `likecodex setup` — interactive first-time configuration
- `likecodex start [--web]` — launch engine + API server (+ Web UI)
- `likecodex "<prompt>"` — one-shot task
- `likecodex code` / `likecodex --tui` — terminal UI
- `likecodex doctor [--security] [--json]` — environment diagnostics
- `likecodex serve` — Rust API server only
- `likecodex config` — redacted config

## Development

```bash
cargo check --workspace
uv run pytest packages/likecodex-engine/tests tests -v
cd web && npm run lint && npm run type-check && npm run test
```

See [API.md](API.md) and [EVENTS.md](EVENTS.md).
