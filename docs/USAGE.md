# LikeCodex Usage

## Quick Start

1. Configure your LLM provider in `~/.likecodex/config.toml`:

```toml
[llm]
provider = "openai"
model = "gpt-4o"
api_key = "sk-..."

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

2. Start the full dev stack:

```bash
./scripts/dev.sh
# or on Windows: .\scripts\dev.ps1
```

Services:

- Python Engine: `http://127.0.0.1:9090`
- Rust API Server: `http://127.0.0.1:8080`
- Web UI: `http://127.0.0.1:3000`

3. Run a one-shot task from the CLI:

```bash
cargo run -p likecodex-cli -- "create a python script that prints 1..10 and run it"
```

4. Or start the interactive TUI:

```bash
cargo run -p likecodex-cli -- --tui
```

## CLI Commands

- `likecodex "<prompt>"` - run a single prompt.
- `likecodex interactive` - plain REPL.
- `likecodex --tui` - terminal UI.
- `likecodex run "<prompt>"` - same as one-shot.
- `likecodex serve` - start the Rust API server.
- `likecodex config` - print loaded configuration (redacted).
- `likecodex --approval auto` - override approval mode for the session.

## Approval Modes

- `read-only`: agent cannot write files or run commands.
- `auto`: low-risk commands run automatically; medium-risk prompts for approval; high-risk uses sandbox.
- `full-access`: all commands run without asking.
- `sandbox-required`: non-read operations must run inside Docker; fallback disabled.

## API Docs

See [API.md](API.md) and [EVENTS.md](EVENTS.md).

## Development

```bash
cargo check --workspace
uv run pytest packages/likecodex-engine/tests tests -v
cd web && npm run lint && npm run type-check && npm run test && npm run build
```

Copy `.env.example` to `.env` for local environment variables.
