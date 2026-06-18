# LikeCodex Security Guide

LikeCodex is designed as a **safer long-running terminal agent** compared to full-access-only tools.

## Approval modes

Configure in `~/.likecodex/config.toml`:

```toml
[approval]
mode = "auto"   # auto | prompt | sandbox-required
```

- **auto** — low-risk tools run locally; high-risk prompts or routes to sandbox
- **prompt** — user confirms each risky operation (TUI/Web permission flow)
- **sandbox-required** — shell execution prefers Docker sandbox

## Sandbox

Build the sandbox image:

```bash
docker build -t likecodex/sandbox:latest docker/sandbox
```

Verify setup:

```bash
likecodex doctor --security
```

Checks:

- Docker available
- `likecodex/sandbox` image present
- Current approval mode

## Path safety

File tools resolve paths under the working directory and reject traversal (`../etc/passwd`).

## Planner / subagent isolation

Planner and subagents use **separate LLM sessions** — plan output is injected as a single `[Plan]` USER block so executor prefix cache is not polluted.

## HTTP API

Set `LIKECODEX_API_TOKEN` for team deployments. Engine listens on `127.0.0.1:9090` by default.
