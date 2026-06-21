# LikeCodex IM Bot

Thin webhook adapter calling the Rust control plane (`LIKECODEX_API_BASE`, default `http://127.0.0.1:8080`).

## Run

```bash
cd services/imbot
python main.py
# listens on :9091
```

## Endpoints

- `POST /webhook/feishu` — Feishu/Lark event payload
- `POST /webhook/wechat` — WeChat-style JSON payload
- `POST /webhook/action` — permission/ask card button callbacks
- `GET /health`

Each chat thread maps to a stable `session_id` for context reuse. Async tasks use `POST /tasks`. The process also subscribes to `GET /events` SSE and forwards `permission_requested` / `ask_requested` as platform cards via `approval_bridge.py`.

## Config

Add to project `likecodex.toml`:

```toml
[imbot]
enabled = true
port = 9091
feishu_app_id = "..."
wechat_token = "..."
```

See Reasonix [BOT_GUIDE.zh-CN.md](https://github.com/esengine/DeepSeek-Reasonix/blob/main/docs/BOT_GUIDE.zh-CN.md) for UX patterns.