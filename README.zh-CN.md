# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Node.js 20+](https://img.shields.io/badge/node.js-20+-green.svg)](https://nodejs.org/)

**LikeCodex** 是一个面向生产环境的开源编程 Agent，灵感来自 [OpenAI Codex](https://openai.com/index/introducing-codex/)。项目采用 **Rust 控制平面**（CLI、HTTP API、沙箱执行）+ **Python Agent 引擎**（LLM 循环、工具调用、规划、记忆）+ **Next.js Web 界面** 的混合架构，在终端、TUI 和浏览器中提供统一体验。

**[English README](README.md)**

---

## 目录

- [为什么选择 LikeCodex？](#为什么选择-likecodex)
- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
  - [CLI 与 TUI](#cli-与-tui)
  - [Web 界面](#web-界面)
  - [HTTP API](#http-api)
- [内置工具](#内置工具)
- [配置说明](#配置说明)
- [安全与审批模式](#安全与审批模式)
- [项目结构](#项目结构)
- [本地开发](#本地开发)
- [测试](#测试)
- [Docker 部署](#docker-部署)
- [常见问题](#常见问题)
- [文档索引](#文档索引)
- [路线图](#路线图)
- [贡献与许可证](#贡献与许可证)

---

## 为什么选择 LikeCodex？

许多编程 Agent 要么是 LLM 的薄 CLI 封装，要么是单体 Python 应用。LikeCodex 有意拆分职责：

| 层级 | 技术栈 | 职责 |
|------|--------|------|
| **交互层** | Rust CLI/TUI、Next.js | 用户交互、流式展示 |
| **桥接层** | Rust Axum 服务 | HTTP/SSE、权限、会话 API |
| **智能层** | Python 引擎 | Agent 循环、LLM 调用、工具编排 |
| **执行层** | Rust 执行器 + Docker 沙箱 | 带路径约束的 shell/git 执行 |

这种设计在 Rust 侧保证 **执行速度与安全性**，在 Python 侧保证 **Agent 逻辑的快速迭代**，CLI 与 Web 共用同一套 SSE 事件协议。

---

## 功能特性

### 多种交互方式

| 方式 | 命令 / 地址 | 适用场景 |
|------|-------------|----------|
| **单次 CLI** | `cargo run -p likecodex-cli -- "提示词"` | 脚本、CI、快速任务 |
| **交互 REPL** | `likecodex interactive` | 轻量终端对话 |
| **Ratatui TUI** | `likecodex --tui` | 富文本终端界面 |
| **Web UI** | http://localhost:3000 | 聊天、Diff、权限、会话历史 |

### Agent 能力

- **工具调用循环** — 多轮推理，结构化工具结果回传
- **任务规划器** — 可选分步计划（`LIKECODEX_ENABLE_PLANNER=true`）
- **子 Agent 编排** — 将子任务委派给独立 Agent 运行
- **MCP 集成** — 通过 Model Context Protocol 注册外部工具
- **会话持久化** — SQLite 会话 + JSONL 事件历史
- **向量记忆** — 可选长期记忆（`.likecodex/memory.jsonl`）

### 支持的模型

| 提供商 | 配置值 | 说明 |
|--------|--------|------|
| OpenAI | `provider = "openai"` | GPT-4o 及兼容模型 |
| Anthropic | `provider = "anthropic"` | Claude 系列 |
| Mock | `provider = "mock"` | 测试用确定性响应 |

API Key 可从 `config.toml` 或环境变量 `{PROVIDER}_API_KEY` 读取。

---

## 系统架构

```text
┌──────────────────────────────────────────────────────────────┐
│                        用户交互层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ CLI / REPL  │  │  Ratatui    │  │   Next.js Web UI    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼─────────────────────┼────────────┘
          │                │                     │
          └────────────────┼─────────────────────┘
                           │  HTTP / SSE
                ┌──────────▼──────────┐
                │   Rust API 服务     │  :8080
                │ (likecodex-server)  │
                │   • /tasks /chat    │
                │   • /events (SSE)   │
                │   • /permissions    │
                │   • /execute        │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   Python 引擎       │  :9090
                │ (likecodex-engine)  │
                │   • AgentLoop       │
                │   • ToolRegistry    │
                │   • LLM 提供商      │
                └──────────┬──────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
┌─────────▼────────┐ ┌─────▼─────┐ ┌───────▼────────┐
│ 本地执行器       │ │ Docker    │ │ 文件索引       │
│ (shell, git)     │ │ 沙箱      │ │ (搜索)         │
└──────────────────┘ └───────────┘ └────────────────┘
```

**Web 聊天请求流程：**

1. 浏览器向 Rust 服务（`:8080`）发送 `POST /tasks` 或 `POST /chat`
2. Rust 服务转发至 Python 引擎（`:9090`）
3. 引擎运行 Agent 循环，调用各类工具
4. 高风险 shell 命令通过 `POST /execute` 路由至 Docker 沙箱
5. 事件经 `GET /events`（SSE）实时推送到 Web/CLI
6. 审批模式下，敏感操作会弹出权限确认

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| [Rust](https://rustup.rs/) | 1.70+ | CLI、服务、沙箱、执行器 |
| [Python](https://www.python.org/) | 3.11+ | Agent 引擎 |
| [uv](https://github.com/astral-sh/uv) | 最新 | Python 依赖管理 |
| [Node.js](https://nodejs.org/) | 20+ | Web 前端 |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 可选 | 隔离命令执行 |

**平台说明：**

- **Windows**：使用 `scripts/dev.ps1`；Rust 编译可能需要 MSVC Build Tools
- **macOS / Linux**：使用 `scripts/dev.sh`
- **沙箱**：首次需构建镜像 — `docker build -t likecodex/sandbox:latest docker/sandbox`

---

## 安装

```bash
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex

# Python 依赖
uv sync --all-packages

# Web 依赖
cd web && npm install --legacy-peer-deps && cd ..

# Rust 工作区
cargo build --workspace
```

复制环境变量模板：

```bash
cp .env.example .env
# 在 .env 中填入 API Key
```

创建用户配置文件 `~/.likecodex/config.toml`（见 [配置说明](#配置说明)）。

---

## 快速开始

### 1. 配置 LLM

编辑 `~/.likecodex/config.toml`：

```toml
[llm]
provider = "openai"
model = "gpt-4o"
api_key = "sk-..."          # 或在 .env 中设置 OPENAI_API_KEY
temperature = 0.0
max_tokens = 4096

[approval]
mode = "auto"               # read-only | auto | full-access | sandbox-required

[sandbox]
enabled = true
image = "likecodex/sandbox:latest"
allow_fallback = true       # sandbox-required 模式下应设为 false
timeout_secs = 120
memory_mb = 512

[server]
host = "127.0.0.1"
port = 8080
engine_url = "http://127.0.0.1:9090"
# api_token = "your-local-token"   # 保护 POST /execute 接口
```

### 2. 启动开发环境

```bash
# macOS / Linux
./scripts/dev.sh

# Windows PowerShell
.\scripts\dev.ps1

# 仅启动引擎和服务（不启动 Web）
.\scripts\dev.ps1 -SkipWeb
```

| 服务 | 地址 | 说明 |
|------|------|------|
| Python 引擎 | http://127.0.0.1:9090 | Agent 循环、工具、LLM |
| Rust API 服务 | http://127.0.0.1:8080 | 桥接、SSE、沙箱、会话 |
| Web UI | http://localhost:3000 | 浏览器聊天界面 |

健康检查：

```bash
curl http://127.0.0.1:9090/health   # Python 引擎
curl http://127.0.0.1:8080/health   # Rust 服务
```

### 3. 运行第一个任务

```bash
# 单次任务：创建并运行脚本
cargo run -p likecodex-cli -- "创建一个打印 1 到 10 的 Python 脚本并运行"

# TUI 交互模式
cargo run -p likecodex-cli -- --tui

# 或在浏览器打开 http://localhost:3000 输入提示词
```

---

## 使用指南

### CLI 与 TUI

```bash
# 单次提示（ positional 参数）
cargo run -p likecodex-cli -- "重构登录模块"

# 子命令
cargo run -p likecodex-cli -- run "修复失败的测试"
cargo run -p likecodex-cli -- interactive    # 普通 REPL
cargo run -p likecodex-cli -- --tui          # Ratatui 终端 UI
cargo run -p likecodex-cli -- serve          # 仅启动 Rust API 服务
cargo run -p likecodex-cli -- config         # 打印脱敏后的配置

# 参数覆盖
cargo run -p likecodex-cli -- --approval read-only "分析此仓库"
cargo run -p likecodex-cli -- --config /path/to/config.toml "提示词"
cargo run -p likecodex-cli -- --engine-url http://127.0.0.1:9090 "提示词"
```

在 `auto` 审批模式下，Agent 请求权限时 CLI 会在终端提示，确认或拒绝后引擎自动继续。

### Web 界面

Web UI 采用三栏布局：

| 栏位 | 内容 |
|------|------|
| **左侧** | 会话列表、任务时间线、计划步骤 |
| **中间** | 流式聊天消息 |
| **右侧** | 文件变更 Diff 查看器 |

其他功能：

- **权限弹窗** — 审批模式下批准/拒绝工具调用
- **实时 SSE** — 订阅 `GET /events` 获取实时更新
- **会话历史** — 从 SQLite 加载历史对话

开发环境默认 `NEXT_PUBLIC_API_BASE=/api`；生产环境可指向 `http://127.0.0.1:8080`。

### HTTP API

**Rust 服务**（`:8080`）— Web 与外部集成的主入口：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/config` | 脱敏配置 |
| POST | `/tasks` | 创建后台 Agent 任务 |
| POST | `/chat` | 流式聊天（SSE 响应） |
| GET | `/events` | 全局 SSE 事件流 |
| GET | `/permissions/pending` | 待审批请求 |
| POST | `/permissions/{id}/respond` | 批准或拒绝 |
| POST | `/execute` | 沙箱命令（可配置 Bearer Token） |
| GET | `/sessions` | 会话列表 |
| GET | `/sessions/{id}/events` | 会话事件历史 |
| GET | `/index/search?pattern=` | 文件名索引搜索 |

**Python 引擎**（`:9090`）— CLI 直连或通过 Rust 桥接：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/run` | 同步执行提示词 |
| POST | `/chat` | 流式 Agent 输出（SSE） |
| POST | `/plan` | 仅生成计划不执行 |
| POST | `/tasks` | 后台任务 |
| GET | `/tasks/{id}` | 任务状态与输出 |

示例 — 创建任务：

```bash
curl -X POST http://127.0.0.1:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "列出项目中所有 Python 文件"}'
```

示例 — 订阅事件流：

```bash
curl -N http://127.0.0.1:8080/events
```

完整参考：[docs/API.md](docs/API.md) · 事件格式：[docs/EVENTS.md](docs/EVENTS.md)

---

## 内置工具

Python 引擎默认注册以下工具：

| 分类 | 工具名 | 说明 |
|------|--------|------|
| **文件系统** | `read_file` | 读取文件（路径受限） |
| | `write_file` | 写入或创建文件 |
| | `list_dir` | 列出目录 |
| | `search_files` | Glob 风格文件搜索 |
| **Shell** | `run_command` | 执行 shell 命令（审批 + 沙箱路由） |
| **搜索** | `grep_files` | 跨文件正则搜索 |
| | `find_symbol` | 符号查找（索引辅助） |
| | `index_search` | 查询 Rust 索引服务 |
| **Git** | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_commit` | Git 操作 |
| **代码审查** | `review_file`, `review_diff`, `check_dependencies` | 审查辅助 |

启用 MCP 工具：设置 `LIKECODEX_ENABLE_MCP=true` 并在 `config.toml` 中配置：

```toml
[mcp.servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/root"]
```

---

## 配置说明

配置合并优先级（后者覆盖前者）：

1. 代码默认值
2. `~/.likecodex/config.toml`
3. 环境变量（`.env` 或 shell）
4. CLI 参数（`--approval`、`--config`、`--engine-url`）

### config.toml 各节

| 节 | 主要字段 |
|----|----------|
| `[llm]` | `provider`, `model`, `api_key`, `base_url`, `temperature`, `max_tokens` |
| `[approval]` | `mode` |
| `[sandbox]` | `enabled`, `image`, `allow_fallback`, `timeout_secs`, `memory_mb`, `max_cpus`, `writable_roots` |
| `[server]` | `host`, `port`, `engine_url`, `api_token` |
| `[mcp.servers.*]` | `command`, `args`, `env` |

### 环境变量

详见 [.env.example](.env.example)：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LIKECODEX_LLM_PROVIDER` | `openai` | LLM 提供商 |
| `LIKECODEX_LLM_MODEL` | `gpt-4o` | 模型名称 |
| `LIKECODEX_LLM_API_KEY` | — | API Key（也可用 `OPENAI_API_KEY`） |
| `LIKECODEX_ENGINE_URL` | `http://127.0.0.1:9090` | Python 引擎地址 |
| `LIKECODEX_ENGINE_HOST` | `127.0.0.1` | 引擎绑定主机 |
| `LIKECODEX_ENGINE_PORT` | `9090` | 引擎绑定端口 |
| `LIKECODEX_WORKING_DIR` | `.` | Agent 工作目录 |
| `LIKECODEX_APPROVAL_MODE` | `auto` | 审批模式覆盖 |
| `LIKECODEX_API_TOKEN` | — | `/execute` 的 Bearer Token |
| `LIKECODEX_SANDBOX_URL` | `http://127.0.0.1:8080/execute` | 沙箱端点 |
| `LIKECODEX_ENABLE_PLANNER` | `false` | 启用任务规划器 |
| `LIKECODEX_ENABLE_MCP` | `false` | 注册 MCP 工具服务 |
| `LIKECODEX_MEMORY_PATH` | `.likecodex/memory.jsonl` | 向量记忆文件 |
| `LIKECODEX_SESSION_DB` | `.likecodex/sessions.db` | SQLite 会话库 |
| `NEXT_PUBLIC_API_BASE` | `/api` | Web UI API 基地址 |

---

## 安全与审批模式

LikeCodex 采用多层防护：

- **路径约束** — 文件系统与 Git 工具无法越出配置的工作目录
- **命令分级** — shell 工具按风险等级分类（只读 / 中等 / 高）
- **用户审批** — 中等风险操作在 CLI 或 Web 中提示确认
- **Docker 沙箱** — 高风险命令在隔离容器中执行
- **API Token** — 可选的 `POST /execute` Bearer 认证
- **配置脱敏** — `/config` 与 `likecodex config` 不暴露明文密钥

### 审批模式对照

| 模式 | 只读工具 | 写入 / shell | 高风险 shell | Fallback |
|------|----------|--------------|--------------|----------|
| `read-only` | ✅ | ❌ 禁止 | ❌ 禁止 | — |
| `auto` | ✅ 自动 | ⚠️ 需确认 | 🐳 沙箱 | ✅ Docker 不可用时回退 |
| `full-access` | ✅ 自动 | ✅ 自动 | ✅ 本地执行 | — |
| `sandbox-required` | ✅ 自动 | 🐳 仅沙箱 | 🐳 仅沙箱 | ❌ 禁止回退 |

处理不可信提示词或在共享 CI 环境运行时，建议使用 `sandbox-required` 且 `allow_fallback = false`。

漏洞报告：[SECURITY.md](SECURITY.md)

---

## 项目结构

```text
likecodex/
├── crates/                         # Rust 工作区
│   ├── likecodex-core/             # 共享类型、配置、事件
│   ├── likecodex-cli/              # CLI + Ratatui TUI
│   ├── likecodex-server/           # Axum HTTP/SSE 桥接
│   ├── likecodex-executor/         # 本地命令执行
│   ├── likecodex-sandbox/          # Docker 沙箱编排
│   └── likecodex-indexer/          # 文件索引搜索
├── packages/
│   └── likecodex-engine/           # Python Agent 核心
│       └── likecodex_engine/
│           ├── agent/              # Agent 循环、规划、权限
│           ├── tools/              # 文件、shell、git、审查
│           ├── llm/                # OpenAI、Anthropic、Mock
│           ├── context/            # 提示词组装
│           └── memory/             # 会话与向量记忆
├── web/                            # Next.js 前端
│   └── src/
│       ├── app/                    # 页面
│       ├── components/             # 聊天、Diff、权限弹窗
│       └── lib/                    # API 客户端、SSE、状态管理
├── docs/                           # 架构、API、事件、使用说明
├── tests/                          # 集成与安全测试
├── docker/                         # 沙箱与服务 Dockerfile
├── scripts/                        # dev.sh、dev.ps1
├── .github/workflows/              # CI 流水线
├── docker-compose.yml              # 实验性全栈部署
├── .env.example                    # 环境变量模板
├── CONTRIBUTING.md
├── SECURITY.md
└── CHANGELOG.md
```

---

## 本地开发

```bash
# Rust 格式化与 lint
cargo fmt --all
cargo clippy --workspace --all-targets -- -D warnings

# Python lint
uv run ruff check packages/likecodex-engine tests

# Web lint
cd web && npm run lint && npm run type-check

# 单独启动各服务
uv run python -m likecodex_engine.server          # :9090
cargo run -p likecodex-server                     # :8080
cd web && npm run dev                             # :3000
```

PR 规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 测试

```bash
# Rust 单元与集成测试
cargo test --workspace

# Python 测试
uv sync --all-packages
uv run pytest packages/likecodex-engine/tests tests -v

# Web 测试
cd web && npm install --legacy-peer-deps && npm run test

# 本地模拟 CI
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
uv run pytest packages/likecodex-engine/tests tests -v
cd web && npm run lint && npm run type-check && npm run test && npm run build
```

---

## Docker 部署

```bash
# 构建沙箱镜像（沙箱模式必需）
docker build -t likecodex/sandbox:latest docker/sandbox

# 实验性全栈启动
docker compose up
```

`docker-compose.yml` 定义三个服务：`engine`（:9090）、`server`（:8080）、`web`（:3000）。

---

## 常见问题

| 现象 | 可能原因 | 解决方法 |
|------|----------|----------|
| `failed to connect to LikeCodex engine` | 引擎未启动 | 运行 `dev.ps1` / `dev.sh` 或手动启动引擎 |
| `engine error: ... api_key` | 缺少 LLM Key | 在 `config.toml` 或 `.env` 中配置 |
| 沙箱命令失败 | Docker 未运行 / 镜像缺失 | 启动 Docker 并构建沙箱镜像 |
| Web 无事件流 | 服务不可达 | 检查 `:8080/health` 与 `NEXT_PUBLIC_API_BASE` |
| 权限卡住 | 未响应 UI/CLI | 在 Web 弹窗或 CLI 中批准/拒绝 |
| Windows 下 Rust 编译失败 | 缺少 MSVC 链接器 | 安装 [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |

开启详细日志：

```bash
RUST_LOG=debug cargo run -p likecodex-server
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 英文文档 |
| [docs/USAGE.md](docs/USAGE.md) | 详细使用指南 |
| [docs/API.md](docs/API.md) | HTTP API 参考 |
| [docs/EVENTS.md](docs/EVENTS.md) | SSE 事件格式 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [SECURITY.md](SECURITY.md) | 安全策略 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更 |

---

## 路线图

- [ ] 在 `likecodex-indexer` 中集成 Tree-sitter 符号索引
- [ ] MCP SSE/WebSocket 传输
- [ ] 生产部署指南（Docker Compose、Kubernetes）
- [ ] 自定义工具插件市场
- [ ] 更多 LLM 提供商（Azure OpenAI、本地 Ollama）

---

## 贡献与许可证

欢迎提交 Issue 和 Pull Request！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

本项目采用 [MIT License](LICENSE) 开源。

---

## 致谢

灵感来自 OpenAI Codex 及更广泛的 Agent 编程生态。使用 Rust、Python 与 Next.js 构建。
