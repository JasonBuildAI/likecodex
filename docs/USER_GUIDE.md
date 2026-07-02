# LikeCodex User Guide

## Table of Contents

- [Installation](#installation)
- [First-Time Setup](#first-time-setup)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
- [Agent Modes](#agent-modes)
- [Tool Usage Examples](#tool-usage-examples)
- [Configuration Guide](#configuration-guide)
- [Working with Sessions](#working-with-sessions)
- [Cache Optimization](#cache-optimization)
- [Troubleshooting](#troubleshooting)

---

## Installation

### Python-only (recommended for quick start)

```bash
pip install likecodex
```

This installs the core agent engine and Python CLI. You can run interactive chat and one-shot tasks immediately.

### Full installation (with Rust CLI, Web UI, desktop app)

**Prerequisites:**
- Python 3.11+
- Rust 1.70+
- Node.js 20+
- uv (recommended)

```bash
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex
uv sync --all-packages --extra dev
cd web && npm install --legacy-peer-deps && cd ..
cargo build --workspace
```

---

## First-Time Setup

### 1. Get a DeepSeek API key

Sign up at [https://platform.deepseek.com](https://platform.deepseek.com) and create an API key.

### 2. Run the setup wizard

```bash
likecodex --setup
```

This interactive wizard will:
- Prompt for your DeepSeek API key
- Create `~/.likecodex/config.toml` with defaults
- Set up project memory (`LIKECODEX.md`)
- Test connectivity to the DeepSeek API

### 3. Verify the setup

```bash
likecodex --doctor
```

The doctor checks:
- Python version compatibility
- DeepSeek API connectivity
- Config file validity
- Docker availability (if sandbox is enabled)
- Workspace permissions

---

## Quick Start

### Interactive chat

```bash
likecodex --chat
```

This starts a Rich-formatted interactive session. Type your requests in natural language:

```
> explain how the authentication module works
> add error handling to the database connection
> create a new React component for user login
```

### One-shot tasks

```bash
likecodex "find all TODO comments in the codebase"
likecodex --mode agent "refactor the main.py into smaller modules"
likecodex --model pro "design a caching strategy for the API"
```

### Pipe input

```bash
cat error.log | likecodex "analyze these errors"
echo "list all python files" | likecodex --json
```

### Web UI

```bash
likecodex --web
```

Opens the agent engine, Rust server, and launches the Web UI in your browser.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `likecodex` | Interactive chat (default) |
| `likecodex "prompt"` | One-shot task execution |
| `likecodex --chat` | Interactive chat mode |
| `likecodex --web` | Start engine + open Web UI |
| `likecodex --setup` | Interactive setup wizard |
| `likecodex --doctor` | Environment diagnostics |
| `likecodex --version` | Show version |

### Flags

| Flag | Description |
|------|-------------|
| `--mode ask` | Read-only Q&A mode |
| `--mode agent` | Autonomous execution mode |
| `--mode manual` | Step-by-step confirmation mode |
| `--model flash` | DeepSeek V4 Flash (fast) |
| `--model pro` | DeepSeek V4 Pro (capable) |
| `--json` | JSON output format |
| `--plain` | Plain text output (no Rich) |
| `--port PORT` | Engine port (default: 9090) |
| `--direct` | Connect directly to Python engine |

---

## Agent Modes

LikeCodex provides three agent modes to control autonomy:

### Ask Mode (read-only)

```bash
likecodex --mode ask "what does this function do?"
```

- AI can read files, search code, and answer questions
- **Cannot** modify files or execute commands
- Safe for exploration and code review
- No permission prompts needed

### Agent Mode (autonomous)

```bash
likecodex --mode agent "add input validation to the API endpoint"
```

- AI reads, writes, and executes commands autonomously
- Permission prompts for risky operations (configurable)
- Perfect for routine development tasks
- Uses `auto` approval mode

### Manual Mode (step-by-step)

```bash
likecodex --mode manual "deploy the application"
```

- AI proposes changes but waits for your confirmation
- You review and approve each file edit and command
- Maximum control for critical operations
- Uses `manual` approval mode

---

## Tool Usage Examples

### File Operations

```bash
likecodex "read the contents of src/main.py"
likecodex "find all Python files in the project"
likecodex "list the files in the docs directory"
likecodex "create a new file called config.yaml with these settings"
```

### Code Search

```bash
likecodex "search for 'deprecated' across the codebase"
likecodex "find all usages of the User class"
likecodex "show me the git log for the last 5 commits"
```

### Shell Commands

```bash
likecodex "run the test suite"
likecodex "install the project dependencies"
likecodex "check what processes are running on port 3000"
```

### Git Operations

```bash
likecodex "show me the current git status"
likecodex "create a commit with these changes"
likecodex "show the diff for the last commit"
```

### Web & Research

```bash
likecodex "search the web for the latest Python best practices"
likecodex "fetch the content of the API documentation page"
```

---

## Configuration Guide

### Configuration File Locations

Configuration is loaded in this order (later overrides earlier):

1. Built-in defaults
2. `~/.likecodex/config.toml` (user-level)
3. `./likecodex.toml` (project-level, in any parent directory)
4. Environment variables
5. CLI flags

### Example Configuration

```toml
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
api_key = "sk-..."           # Or set DEEPSEEK_API_KEY env variable
base_url = "https://api.deepseek.com"

[approval]
mode = "auto"                # read-only | auto | full-access | sandbox-required

[agent]
enable_planner = false       # Enable dual-model planner
token_mode = "full"          # full | economy

[server]
port = 8080
engine_url = "http://127.0.0.1:9090"
api_token = "optional-local-token"

[sandbox]
enabled = true
image = "likecodex/sandbox:latest"
allow_fallback = true

[mcp]
enabled = false
startup = "lazy"

[deepseek]
thinking = false             # Enable reasoning tokens

[cache]
enabled = true
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |
| `LIKECODEX_LLM_PROVIDER` | `deepseek` | LLM provider |
| `LIKECODEX_LLM_MODEL` | `deepseek-v4-flash` | Model name |
| `LIKECODEX_ENGINE_PORT` | `9090` | Engine port |
| `LIKECODEX_SERVER_PORT` | `8080` | Server port |
| `LIKECODEX_APPROVAL_MODE` | `auto` | Approval mode |
| `LIKECODEX_WORKING_DIR` | cwd | Workspace directory |
| `LIKECODEX_ENABLE_PLANNER` | `false` | Enable planner |
| `LIKECODEX_RUN_SANDBOX_TESTS` | — | Enable sandbox tests |

### Project-Level Config

Create a `likecodex.toml` file in your project root to override settings:

```toml
[llm]
model = "deepseek-v4-pro"

[approval]
mode = "full-access"

[mcp]
enabled = true
servers = ["my-custom-tools"]
```

---

## Working with Sessions

### Session Continuity

LikeCodex preserves conversation context across turns using `session_id`:

```bash
# First interaction
likecodex --chat
# Type: "let's work on the auth module"

# Continue later with the same session
# Session is auto-saved to SQLite database
```

### Cache Benefits

Reusing a `session_id` keeps the DeepSeek prefix cache hot, reducing costs and latency for subsequent turns in the same session.

### Session Lifecycle

- Sessions are created on first interaction
- Sessions persist in SQLite at `~/.likecodex/sessions.db`
- Stale sessions (>24h) are auto-cleaned
- Sessions can be listed via the API: `GET /sessions`

---

## Cache Optimization

### Understanding Prefix Caching

DeepSeek's automatic context caching requires the **exact same byte sequence from token 0** across turns. LikeCodex structures conversations as:

```
┌─────────────────────────────────────┐
│ IMMUTABLE PREFIX  (never rewritten) │
├─────────────────────────────────────┤
│ APPEND-ONLY LOG   (grows forward)   │
└─────────────────────────────────────┘
```

### Best Practices

1. **Use session continuity** — Always reuse `session_id` for related tasks
2. **Keep system prompt stable** — Don't change config mid-session
3. **Reduce tool schema changes** — Tool schemas are part of the prefix
4. **Check cache metrics** — Monitor via `/metrics` or Web UI header

### Monitoring Cache Health

```bash
curl http://127.0.0.1:9090/metrics
```

Returns:
```json
{
  "hit_rate": 0.85,
  "recent_hit_rate": 0.92,
  "total_prompt_tokens": 150000,
  "cached_tokens": 127500,
  "uncached_tokens": 22500
}
```

---

## Troubleshooting

### Common Issues

#### "Connection refused" when starting likecodex

```bash
# Ensure the engine is running
likecodex --doctor

# Or start the engine explicitly
likecodex --chat
```

#### "No module named 'likecodex_engine'"

```bash
# Reinstall the package
pip install --upgrade likecodex
# Or with uv
uv sync --all-packages
```

#### "DeepSeek API error: 401 Unauthorized"

```bash
# Run the setup wizard to configure your API key
likecodex --setup

# Or set the environment variable
$env:DEEPSEEK_API_KEY = "sk-your-key-here"
```

#### Permission prompts on every action

```bash
# Use a more permissive mode
likecodex --mode agent "task description"
# Or change default in config.toml:
# [approval]
# mode = "full-access"
```

#### Slow responses

```bash
# Use the flash model instead of pro
likecodex --model flash "quick task"

# Check cache metrics
curl http://127.0.0.1:9090/metrics

# Enable planning for complex tasks
# [agent]
# enable_planner = true
```

### Logs and Debugging

- Engine logs: `~/.likecodex/engine.log`
- Session database: `~/.likecodex/sessions.db`
- Config file: `~/.likecodex/config.toml`

### Getting Help

- **Issues**: https://github.com/JasonBuildAI/likecodex/issues
- **Documentation**: [docs/](https://github.com/JasonBuildAI/likecodex/tree/main/docs)
- **API Reference**: [docs/API.md](API.md)
- **Architecture**: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
