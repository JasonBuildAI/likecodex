# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**LikeCodex** 是一个生产级、开源的仿 Codex 编程 Agent，采用 Rust + Python 混合架构，提供 CLI、TUI 与 Web 三种交互方式。

[English](README.md) · [架构文档](docs/ARCHITECTURE.md) · [API 参考](docs/API.md)

---

## 特性

- **双端交互**：CLI 终端 + Ratatui TUI + Next.js Web UI
- **混合架构**：Rust 负责执行/沙箱/桥接，Python 负责 Agent 逻辑
- **分层安全**：路径边界、审批模式、Docker 沙箱、API Token
- **高级能力**：任务规划、子代理、MCP 工具、向量记忆、会话持久化

---

## 快速开始

### 环境要求

- Rust toolchain
- Python 3.11+ 与 uv
- Node.js 20+
- Docker Desktop（可选，用于沙箱）

### 配置

复制环境变量模板：

```bash
cp .env.example .env
```

创建 `~/.likecodex/config.toml`：

```toml
[llm]
provider = "openai"
model = "gpt-4o"
api_key = "sk-..."

[approval]
mode = "auto"

[sandbox]
enabled = true
allow_fallback = true

[server]
port = 8080
engine_url = "http://127.0.0.1:9090"
```

### 启动

```powershell
# Windows
.\scripts\dev.ps1

# macOS / Linux
./scripts/dev.sh
```

| 服务 | 端口 |
|------|------|
| Python Engine | 9090 |
| Rust API Server | 8080 |
| Web UI | 3000 |

### 使用

```bash
# 单次任务
cargo run -p likecodex-cli -- "创建一个 Python 脚本并运行"

# TUI 交互
cargo run -p likecodex-cli -- --tui

# Web 界面
# 浏览器打开 http://localhost:3000
```

---

## 项目结构

```text
likecodex/
├── crates/               # Rust 工作区（CLI、Server、Sandbox…）
├── packages/likecodex-engine/  # Python Agent 引擎
├── web/                  # Next.js 前端
├── docs/                 # 文档
├── tests/                # 集成测试
└── scripts/              # 开发脚本
```

---

## 审批模式

| 模式 | 说明 |
|------|------|
| `read-only` | 仅允许只读工具 |
| `auto` | 低风险自动；中风险需确认；高风险走沙箱 |
| `full-access` | 全部本地执行 |
| `sandbox-required` | 非只读操作必须沙箱，禁止 fallback |

---

## 测试

```bash
cargo test --workspace
uv run pytest packages/likecodex-engine/tests tests -v
cd web && npm run test
```

---

## 参与贡献

欢迎提交 Issue 和 PR！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

[MIT License](LICENSE)
