# LikeCodex Roadmap — Phase 5 (deferred follow-ups)

Phases 1–4 of the "catch up to Reasonix" plan are implemented (see `CHANGELOG.md`).
Phase 5 items are intentionally deferred; they are large surfaces that build on the
now-stable engine HTTP API and do not affect the core coding-agent loop. This
document scopes them so they can be picked up independently.

## 1. Desktop App

**Goal:** ship a single desktop binary wrapping the existing Next.js Web UI.

- **Approach:** wrap `web/` with [Tauri](https://tauri.app) (Rust-native, small
  footprint, matches the existing Rust toolchain) rather than Electron.
- **Process model:** the Tauri shell spawns the Rust control-plane (`likecodex-server`)
  which in turn supervises the Python engine, exactly like the CLI does today via
  `ensure_engine`. The webview points at the local server URL.
- **Work items:** add `crates/likecodex-desktop` (Tauri), a `tauri.conf.json`,
  bundle the built `web/` assets, reuse `EngineBridge` for IPC, add packaging to
  `release.yml` (dmg/msi/AppImage).

## 2. IM Bots (Feishu/Lark, WeChat)

**Goal:** drive the agent from chat platforms.

- **Approach:** a thin adapter service that translates platform webhooks into calls
  against the engine's `/tasks` (async) and `/tasks/{id}` (poll) endpoints, then
  streams results back. Keep it a separate process so platform SDKs never enter the
  core engine.
- **Work items:** `services/imbot/` (Python, aiohttp) with per-platform adapters;
  map a chat thread → a `session_id` for context reuse; signature verification and
  per-user approval gating (reuse `PermissionEvaluator` semantics over HTTP).

## 3. ACP (Agent Client Protocol)

**Goal:** interoperate with ACP-speaking editors/clients.

- **Approach:** add an ACP transport that maps ACP requests onto the existing engine
  endpoints and event stream (`EVENTS.md`). Reuse the SSE event mapping already in
  `crates/likecodex-server/src/event_mapping.rs`.
- **Work items:** `crates/likecodex-acp` (or a Python module) implementing the ACP
  handshake, capability advertisement, and streaming bridge; conformance tests.

## Dependencies satisfied by Phases 1–4

- Stable engine HTTP API (`/chat`, `/run`, `/tasks`, `/checkpoints`, `/sessions`).
- Checkpoints/rewind for safe automated edits from non-interactive clients.
- Project memory + slash commands so external clients inherit the same conventions.
