# LikeCodex Engine

Python agent core for [LikeCodex](https://github.com/JasonBuildAI/likecodex).

## Modules

| Module | Description |
|--------|-------------|
| `agent/` | Agent loop, planner, sub-agent orchestrator |
| `llm/` | OpenAI, Anthropic, mock providers |
| `tools/` | Filesystem, shell, git, code search, review |
| `permissions/` | Risk classification and approval evaluation |
| `memory/` | Vector memory with JSONL/chromadb fallback |
| `mcp/` | MCP client and tool loader |
| `persistence/` | SQLite session store |
| `context/` | Conversation management and compaction |

## Run standalone

```bash
uv run python -m likecodex_engine.server
```

Default: `http://127.0.0.1:9090`

## Test

```bash
uv run pytest tests -v
```
