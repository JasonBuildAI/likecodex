# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Node.js 20+](https://img.shields.io/badge/node.js-20+-green.svg)](https://nodejs.org/)

**LikeCodex** 是一个由 **DeepSeek V4** 驱动的开源编程 Agent。它采用 **Rust 控制平面**（CLI、HTTP API、沙箱执行）+ **Python Agent 引擎**（LLM 循环、工具、规划、记忆）+ **Next.js Web 界面** 的混合架构，并针对 **DeepSeek 上下文缓存命中率** 做了专门优化，以降低多轮工具循环的 API 成本。

**[English README](README.md)**

---

## 目录

- [LikeCodex 是什么？](#likecodex-是什么)
- [系统架构](#系统架构)
  - [设计理念](#设计理念)
  - [四层模型](#四层模型)
  - [运行时拓扑](#运行时拓扑)
  - [组件地图](#组件地图)
  - [端到端请求流程](#端到端请求流程)
  - [Agent 循环（Python 引擎）](#agent-循环python-引擎)
  - [事件协议（SSE）](#事件协议sse)
  - [缓存优先的上下文模型](#缓存优先的上下文模型)
  - [安全与执行路由](#安全与执行路由)
- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [内置工具](#内置工具)
- [配置说明](#配置说明)
- [本地开发](#本地开发)
- [测试](#测试)
- [项目结构](#项目结构)
- [文档索引](#文档索引)
- [路线图](#路线图)
- [贡献与许可证](#贡献与许可证)

---

## LikeCodex 是什么？

LikeCodex 让你用**自然语言**完成代码编辑、运行和理解：你描述任务，Agent 会读文件、执行命令、写入补丁并汇报结果；对高风险操作还可选择**人工审批**。

市面上常见的编程 Agent 通常属于两类：

- **LLM API 的薄 CLI 封装** — 功能简单，难以扩展安全与 UI；
- **单体 Python 应用** — UI、安全、Agent 逻辑耦合，迭代和部署都较重。

LikeCodex **刻意拆分职责**：

| 关注点 | 所在层 | 原因 |
|--------|--------|------|
| 快速、安全的 shell/git 执行 | Rust | 路径约束、沙箱路由、低开销 |
| Agent 逻辑快速迭代 | Python | 工具循环、LLM、规划、压缩 |
| CLI 与 Web 统一体验 | Rust 服务 + SSE 事件 | 一套事件协议服务所有客户端 |
| 富交互浏览器界面 | Next.js | 聊天、Diff、权限、会话历史 |

**默认 LLM：** DeepSeek V4（`deepseek-v4-flash` 或 `deepseek-v4-pro`），通过 OpenAI 兼容 API 调用。

---

## 系统架构

### 设计理念

1. **控制与智能分离** — Rust 负责 I/O、HTTP、权限广播、命令执行；Python 负责推理与工具编排。
2. **所有客户端共享一条事件流** — CLI、TUI、Web 都订阅 `likecodex-server` 发出的统一 SSE 事件。
3. **缓存稳定性是一等公民** — 上下文结构为 DeepSeek 前缀缓存服务，工具循环多轮对话仍保持高命中率（见 [缓存优先的上下文模型](#缓存优先的上下文模型)）。
4. **纵深防御** — 路径约束、命令风险分级、用户审批、可选 Docker 沙箱。

---

### 四层模型

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ 第 1 层 — 交互层（你如何与 LikeCodex 对话）                              │
│   • likecodex-cli     单次任务 / REPL / Ratatui TUI                     │
│   • web/              Next.js 三栏 UI（:3000）                          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  HTTP + SSE
┌───────────────────────────────▼─────────────────────────────────────────┐
│ 第 2 层 — 控制平面（likecodex-server，:8080）                            │
│   • 转发 /tasks、/chat、/run、/plan 到 Python 引擎                       │
│   • GET /events 广播规范化 SSE 事件                                      │
│   • 权限 API + 会话持久化代理                                            │
│   • POST /execute → Docker 沙箱或本地执行器                              │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  HTTP（引擎桥接）
┌───────────────────────────────▼─────────────────────────────────────────┐
│ 第 3 层 — Agent 引擎（likecodex-engine，:9090）                          │
│   • AgentLoop — 多轮 LLM ↔ 工具循环                                     │
│   • ToolRegistry — 文件、shell、git、搜索、MCP 等                         │
│   • ContextManager — 缓存优先的提示词组装 + 历史压缩                      │
│   • Permissions — 策略规则 + 审批模式                                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  工具调用
┌───────────────────────────────▼─────────────────────────────────────────┐
│ 第 4 层 — 执行层（Rust）                                                 │
│   • likecodex-executor   工作目录内的本地 shell/git                       │
│   • likecodex-sandbox    Docker 隔离执行                                 │
│   • likecodex-indexer    文件名 / 代码图搜索辅助                          │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    DeepSeek V4 API（OpenAI 兼容）
```

---

### 运行时拓扑

运行 `scripts/dev.sh` 或 `scripts/dev.ps1` 后，会启动三个进程：

| 进程 | 端口 | 包名 | 职责 |
|------|------|------|------|
| Python 引擎 | **9090** | `likecodex-engine` | Agent 大脑 — 循环、工具、LLM |
| Rust API 服务 | **8080** | `likecodex-server` | 桥接、SSE 总线、沙箱网关 |
| Next.js 开发服务 | **3000** | `web/` | 浏览器 UI（开发环境代理 API） |

**健康检查：**

```bash
curl http://127.0.0.1:9090/health   # Python 引擎
curl http://127.0.0.1:8080/health   # Rust 服务
```

CLI 可以**直连** Python 引擎（`--engine-url`），也可以走 Rust 服务（与 Web 相同路径）。

---

### 组件地图

#### Rust 工作区（`crates/`）

| Crate | 职责 |
|-------|------|
| **likecodex-core** | 共享类型：`Config`、`Event`、`Task`、权限模型、事件总线 |
| **likecodex-cli** | 终端入口：单次任务、REPL、Ratatui TUI、可选自动启动引擎 |
| **likecodex-server** | Axum HTTP 服务：引擎桥接、SSE `/events`、`/execute`、会话 API |
| **likecodex-executor** | 在配置的工作目录内本地执行 shell/git |
| **likecodex-sandbox** | 为高风险命令启动 Docker 容器 |
| **likecodex-indexer** | 文件索引与代码图搜索（计划集成 Tree-sitter） |

#### Python 引擎（`packages/likecodex-engine/`）

| 模块 | 职责 |
|------|------|
| **agent/loop.py** | 核心 Agent 循环：流式 LLM → 解析 tool_calls → 执行 → 重复 |
| **agent/planner.py** | 可选：执行前先产出分步计划 |
| **agent/coordinator.py** | 双模型协作（Pro 规划 → Flash 执行） |
| **agent/subagent*.py** | 子 Agent：委派独立子任务 |
| **agent/guards.py** | 循环/风暴/重复成功守卫、空回答保护 |
| **agent/plan_mode.py** | 规划模式下限制写入类工具 |
| **tools/** | 内置工具：文件系统、shell、git、grep、LSP、审查、MCP 等 |
| **llm/deepseek.py** | DeepSeek V4 提供商 + 缓存用量指标 |
| **context/** | 缓存优先的上下文组装、压缩、裁剪 |
| **permissions/** | 审批模式、策略规则、风险分级 |
| **persistence/** | SQLite 会话 + JSONL 事件历史 |
| **memory/** | 可选向量记忆（`.likecodex/memory.jsonl`） |

#### Web 界面（`web/`）

| 区域 | 职责 |
|------|------|
| **src/app/page.tsx** | 三栏布局：时间线 / 聊天 / Diff |
| **src/lib/api.ts** | HTTP 客户端 + SSE 解析（`parseRustEvent`） |
| **src/lib/store.ts** | Zustand 状态：消息、任务、权限、Diff |

---

### 端到端请求流程

示例：用户在 Web UI 输入 *「为 utils.py 添加单元测试」*。

```text
  浏览器                 Rust 服务 (:8080)           Python 引擎 (:9090)          DeepSeek API
     │                          │                            │                          │
     │  POST /tasks             │                            │                          │
     │ ───────────────────────► │  POST /tasks（转发）        │                          │
     │                          │ ─────────────────────────► │                          │
     │                          │                            │  AgentLoop.run()         │
     │                          │                            │ ────────────────────────►│
     │                          │                            │ ◄────────────────────────│ tool_calls
     │                          │                            │                          │
     │                          │                            │  read_file / write_file  │
     │                          │                            │  run_command（可能）      │
     │                          │ ◄── 引擎 SSE 片段 ──────── │                          │
     │                          │  map_engine_output()       │                          │
     │  GET /events (SSE)       │  EventBus.emit()           │                          │
     │ ◄─────────────────────── │                            │                          │
     │  stream_chunk            │                            │                          │
     │  tool_call_requested     │                            │                          │
     │  permission_requested?   │                            │                          │
     │  task_completed          │                            │                          │
```

**步骤说明：**

1. **Web/CLI** 向 Rust 服务发送 `POST /tasks` 或 `POST /chat`，携带 `{ "prompt": "...", "session_id": "..." }`。
2. **Rust 服务** 生成客户端可见的 `task_id`，发出 `task_started`，并转发至 Python `/tasks` 或 `/chat`。
3. **Python 引擎** 运行 `AgentLoop`：
   - 从缓存优先上下文组装消息（静态 SYSTEM 前缀 + 历史）。
   - 携带工具 schema 调用 DeepSeek。
   - 执行工具（只读工具可并行）。
   - 流式输出 assistant 片段与工具事件。
4. **高风险 shell**（`run_command`）可能经 Rust `POST /execute` 路由到 Docker 沙箱（取决于审批模式）。
5. **Rust 服务** 将 Python 扁平输出对象映射为 typed `Event`，经 `/events` 广播。
6. **Web/CLI** 渲染流式文本、工具卡片、权限弹窗与文件 Diff。

在 `auto` 审批模式下，客户端通过 `POST /permissions/{id}/respond` 批准或拒绝；引擎恢复被阻塞的工具调用。

---

### Agent 循环（Python 引擎）

LikeCodex 的核心是 `packages/likecodex-engine/likecodex_engine/agent/loop.py` 中的 `AgentLoop`：

```text
┌──────────────┐
│ 用户提示词    │
└──────┬───────┘
       ▼
┌──────────────────────────────────────┐
│ 组装上下文（CacheFirstContext）       │
│   SYSTEM 前缀 + 历史 + [Context]     │
└──────┬───────────────────────────────┘
       ▼
┌──────────────────────────────────────┐
│ LLM.complete / stream（DeepSeek V4） │
└──────┬───────────────────────────────┘
       │
       ├── 纯文本 ──► 最终回答 ──► 结束
       │
       └── tool_calls ──► 权限检查
                │
                ├── 拒绝 ──► 错误回传模型 ──► 继续循环
                │
                └── 允许 ──► 执行工具（本地 / 沙箱）
                         │
                         └── 追加 tool 结果 ──► 再次循环
```

**重要机制：**

- **守卫（Guards）** — 检测死循环、连续失败、工具调用风暴。
- **压缩（Compaction）** — 上下文接近 token 上限时摘要尾部，**不修改** SYSTEM 前缀。
- **子 Agent** — `task` 工具在独立上下文中运行子任务。
- **检查点（Checkpoints）** — 写文件前快照；`/rewind` 可回滚。
- **规划模式（Plan mode）** — 限制变更类工具，直到退出规划。

---

### 事件协议（SSE）

所有客户端通过 `GET /events` 消费**邻接标签 JSON**（adjacently tagged）：

```json
{"type":"stream_chunk","payload":{"task_id":"…","content":"部分文本"}}
{"type":"tool_call_requested","payload":{"task_id":"…","call":{"id":"…","name":"read_file","arguments":{…}}}}
{"type":"permission_requested","payload":{"task_id":"…","request":{…}}}
{"type":"task_completed","payload":{"id":"…","status":"completed"}}
```

Python 引擎输出扁平对象，如 `{"type":"assistant","content":"…"}`；**`likecodex-server`** 通过 `event_mapping.rs` 映射为结构化 `Event`，保证 CLI、TUI、Web 行为一致。

完整 schema：[docs/EVENTS.md](docs/EVENTS.md)

---

### 缓存优先的上下文模型

DeepSeek **自动上下文缓存**要求从第 0 个 token 起的提示词前缀**字节级一致**。LikeCodex 将缓存稳定性作为设计不变量。

```text
┌─────────────────────────────────────────┐
│ 不可变前缀（会话内不修改）                │
│   system.md + skills + 项目记忆          │
│   + 排序后的工具 JSON schema             │
├─────────────────────────────────────────┤
│ 只追加日志（Append-Only Log）            │
│   user → assistant → tool → …           │
├─────────────────────────────────────────┤
│ 易失暂存区（不发送给 API）               │
│   规划器原始输出、调试 trace             │
└─────────────────────────────────────────┘
```

| 策略 | 作用 |
|------|------|
| 版本化 `system.md`（>1024 tokens） | 稳定的 SYSTEM 消息 |
| 工具 schema 按 key 排序 | 确定性的 `tools` 参数 |
| 动态记忆放在尾部 `[Context]` USER 消息 | 不污染前缀 |
| 同一 `session_id` 复用 `ContextManager` | 跨 HTTP 请求保持前缀 |
| 仅裁剪尾部历史（Compaction） | 压缩时不改 SYSTEM 块 |

监控缓存指标：

```bash
curl http://127.0.0.1:9090/metrics
curl http://127.0.0.1:8080/metrics
```

Web UI 顶栏显示实时 cache hit %。完整规范：[docs/SPEC-CACHE.md](docs/SPEC-CACHE.md)

---

### 安全与执行路由

| 审批模式 | 只读工具 | 写入 / 中等 shell | 高风险 shell | 说明 |
|----------|----------|-------------------|--------------|------|
| `read-only` | 允许 | 禁止 | 禁止 | 安全分析 |
| `auto` | 自动 | 需用户确认 | Docker 沙箱 | 默认；Docker 不可用时可回退 |
| `full-access` | 自动 | 自动 | 本地执行 | 仅可信环境 |
| `sandbox-required` | 自动 | 仅沙箱 | 仅沙箱 | CI / 不可信提示词 |

**防护层次：**

- **路径约束** — 文件/Git 工具无法越出 `LIKECODEX_WORKING_DIR`。
- **风险分级** — shell 命令分为只读 / 中等 / 高。
- **策略规则** — 配置中对工具 allow / ask / deny。
- **Docker 沙箱** — 隔离容器 + 资源限制。
- **API Token** — 可选保护 `POST /execute`。
- **配置脱敏** — `/config` 不返回明文密钥。

详见 [SECURITY.md](SECURITY.md)

---

## 功能特性

### 多种交互方式

| 方式 | 命令 / 地址 | 适用场景 |
|------|-------------|----------|
| 单次 CLI | `cargo run -p likecodex-cli -- "提示词"` | 脚本、CI、快速任务 |
| 交互 REPL | `likecodex interactive` | 轻量终端对话 |
| Ratatui TUI | `likecodex --tui` | 富文本终端界面 |
| Web UI | http://localhost:3000 | 聊天、Diff、权限、会话 |

### Agent 能力

- 多轮 **工具调用循环**，结构化结果回传
- 可选 **任务规划器**（`LIKECODEX_ENABLE_PLANNER=true`）
- **子 Agent 编排**，委派子任务
- **MCP 集成**，接入外部工具服务
- **会话持久化**（SQLite + JSONL 事件）
- **向量记忆**（可选 `.likecodex/memory.jsonl`）
- **检查点与回滚**（写文件前快照）
- **斜杠命令**（`/compact`、`/init` 等）

### 模型（DeepSeek V4）

| 模型 | 配置值 | 说明 |
|------|--------|------|
| `deepseek-v4-flash` | 默认 | 速度快、成本低、缓存最省 |
| `deepseek-v4-pro` | 规划 / 复杂任务 | 质量更高 |

API Key：`DEEPSEEK_API_KEY` 或 `LIKECODEX_LLM_API_KEY`。Thinking 模式：`LIKECODEX_DEEPSEEK_THINKING=true`。

---

## 环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| [Rust](https://rustup.rs/) | 1.70+ | CLI、服务、沙箱、执行器 |
| [Python](https://www.python.org/) | 3.11+ | Agent 引擎 |
| [uv](https://github.com/astral-sh/uv) | 最新 | Python 依赖管理 |
| [Node.js](https://nodejs.org/) | 20+ | Web 前端 |
| [Docker](https://www.docker.com/products/docker-desktop/) | 可选 | 沙箱执行 |

**平台说明：**

- **Windows**：使用 `scripts/dev.ps1`；Rust 需 **MSVC Build Tools** — 运行 `.\scripts\check-prerequisites.ps1`
- **macOS / Linux**：使用 `scripts/dev.sh`
- **沙箱**：`docker build -t likecodex/sandbox:latest docker/sandbox`

---

## 安装

```bash
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex

uv sync --all-packages --extra dev
cd web && npm install --legacy-peer-deps && cd ..
cargo build --workspace

cp .env.example .env
# 在 .env 中填入 DEEPSEEK_API_KEY
```

创建用户配置 `~/.likecodex/config.toml`（见 [配置说明](#配置说明)）。

---

## 快速开始

### 1. 配置 LLM

编辑 `~/.likecodex/config.toml`：

```toml
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
api_key = "..."               # 或在 .env 中设置 DEEPSEEK_API_KEY
base_url = "https://api.deepseek.com"

[deepseek]
thinking = false

[approval]
mode = "auto"

[sandbox]
enabled = true
image = "likecodex/sandbox:latest"
allow_fallback = true

[server]
host = "127.0.0.1"
port = 8080
engine_url = "http://127.0.0.1:9090"
```

### 2. 启动开发环境

```bash
# macOS / Linux
./scripts/dev.sh

# Windows PowerShell
.\scripts\dev.ps1

# 仅引擎 + 服务（不启动 Web）
.\scripts\dev.ps1 -SkipWeb
```

### 3. 运行第一个任务

```bash
cargo run -p likecodex-cli -- "创建一个打印 1 到 10 的 Python 脚本并运行"
cargo run -p likecodex-cli -- --tui
# 或在浏览器打开 http://localhost:3000
```

---

## 使用指南

### CLI 与 TUI

```bash
cargo run -p likecodex-cli -- "重构登录模块"
cargo run -p likecodex-cli -- run "修复失败的测试"
cargo run -p likecodex-cli -- interactive
cargo run -p likecodex-cli -- --tui
cargo run -p likecodex-cli -- serve
cargo run -p likecodex-cli -- config

# 参数覆盖
cargo run -p likecodex-cli -- --approval read-only "分析此仓库"
cargo run -p likecodex-cli -- --engine-url http://127.0.0.1:9090 "提示词"
```

### Web 界面

三栏布局：**会话与任务** | **流式聊天** | **文件 Diff**。

功能：权限弹窗、实时 SSE、顶栏 cache hit %、会话历史。

### HTTP API

**Rust 服务（`:8080`）** — Web 与外部集成的主入口：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/config` | 脱敏配置 |
| POST | `/tasks` | 创建后台 Agent 任务 |
| POST | `/chat` | 流式聊天（SSE） |
| GET | `/events` | 全局 SSE 事件流 |
| GET/POST | `/permissions/*` | 审批流程 |
| POST | `/execute` | 沙箱命令 |
| GET | `/sessions` | 会话列表 |

**Python 引擎（`:9090`）** — CLI 直连或通过 Rust 桥接：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/run` | 同步执行 |
| POST | `/chat` | 流式 SSE |
| POST | `/plan` | 仅生成计划 |
| POST | `/tasks` | 后台任务 |
| GET | `/metrics` | 缓存指标 |

示例：

```bash
curl -X POST http://127.0.0.1:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "列出项目中所有 Python 文件"}'

curl -N http://127.0.0.1:8080/events
```

完整参考：[docs/API.md](docs/API.md)

---

## 内置工具

| 分类 | 工具 |
|------|------|
| 文件系统 | `read_file`、`write_file`、`list_dir`、`search_files`、`edit_file` |
| Shell | `run_command`、后台任务相关 |
| 搜索 | `grep_files`、`find_symbol`、`index_search`、LSP 工具 |
| Git | `git_status`、`git_diff`、`git_log`、`git_branch`、`git_commit` |
| 审查 | `review_file`、`review_diff`、`check_dependencies` |
| Agent | `task`、`parallel_tasks`、`remember`/`forget`、`todo` |

启用 MCP：设置 `LIKECODEX_ENABLE_MCP=true` 并在 `config.toml` 中配置 `[mcp.servers.*]`。

---

## 配置说明

配置合并优先级（后者覆盖前者）：代码默认值 → `~/.likecodex/config.toml` → 环境变量 → CLI 参数。

主要环境变量 — 见 [.env.example](.env.example)：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | — | API Key |
| `LIKECODEX_LLM_MODEL` | `deepseek-v4-flash` | 模型 |
| `LIKECODEX_WORKING_DIR` | `.` | Agent 工作目录 |
| `LIKECODEX_APPROVAL_MODE` | `auto` | 审批模式 |
| `LIKECODEX_ENABLE_PLANNER` | `false` | 任务规划器 |
| `LIKECODEX_SESSION_DB` | `.likecodex/sessions.db` | 会话数据库 |

---

## 本地开发

```bash
cargo fmt --all && cargo clippy --workspace --all-targets -- -D warnings
uv run ruff check packages/likecodex-engine tests
cd web && npm run lint && npm run type-check

# 单独启动各服务
uv run python -m likecodex_engine.server    # :9090
cargo run -p likecodex-server                # :8080
cd web && npm run dev                          # :3000
```

PR 规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 测试

```bash
# Rust
cargo test --workspace

# Python（无 Rust 时可排除 integration）
uv sync --all-packages --extra dev
uv run pytest packages/likecodex-engine/tests tests -m "not integration" -v

# 全栈 E2E（需 cargo build -p likecodex-server）
uv run pytest tests/e2e/test_full_stack.py -m integration -v
uv run python scripts/smoke_test.py

# Web
cd web && npm run test && npm run build

# 基准
uv run python benchmarks/cache/run.py --turns 10 --simulate-cache
uv run python benchmarks/agent/run.py --check
```

每次 push 触发 CI — 见 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)。

---

## 项目结构

```text
likecodex/
├── crates/                    # Rust 工作区
│   ├── likecodex-core/        # 共享类型、配置、事件
│   ├── likecodex-cli/         # CLI + TUI
│   ├── likecodex-server/      # HTTP/SSE 桥接
│   ├── likecodex-executor/    # 本地执行
│   ├── likecodex-sandbox/     # Docker 沙箱
│   └── likecodex-indexer/     # 文件/代码搜索
├── packages/likecodex-engine/ # Python Agent 核心
├── web/                       # Next.js 前端
├── tests/                     # 集成与安全测试
├── scripts/                   # dev.sh、dev.ps1、smoke_test.py
├── benchmarks/                # 缓存与 Agent 回归门
├── docs/                      # 架构、API、事件、缓存规范
└── docker/                    # 沙箱与服务镜像
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 英文文档 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构详解 |
| [docs/SPEC-CACHE.md](docs/SPEC-CACHE.md) | 缓存优先上下文规范 |
| [docs/API.md](docs/API.md) | HTTP API 参考 |
| [docs/EVENTS.md](docs/EVENTS.md) | SSE 事件格式 |
| [docs/USAGE.md](docs/USAGE.md) | 详细使用指南 |
| [docs/PARITY-CHECKLIST.md](docs/PARITY-CHECKLIST.md) | 能力 ↔ 测试映射 |
| [SECURITY.md](SECURITY.md) | 安全策略 |

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

灵感来自 OpenAI Codex 及更广泛的 Agent 编程生态。
