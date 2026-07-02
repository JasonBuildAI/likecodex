# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/likecodex)](https://pypi.org/project/likecodex/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/likecodex)](https://pypi.org/project/likecodex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Node.js 20+](https://img.shields.io/badge/node.js-20+-green.svg)](https://nodejs.org/)

**LikeCodex** 是一个基于 **DeepSeek V4** 的开源 AI 编程助手，专为深度绑定 DeepSeek 模型而设计。你只需用自然语言描述任务，LikeCodex 就能理解你的代码库、执行命令、编辑文件，并汇报结果 —— 对高风险操作支持人工审批，确保安全可控。

> [English README](README.md)

---

## 📖 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [架构概览](#架构概览)
- [三种 Agent 模式](#三种-agent-模式)
- [快速开始](#快速开始)
- [内置工具](#内置工具)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [文档与社区](#文档与社区)
- [许可证](#许可证)

---

## 项目简介

LikeCodex 是一个采用 **Rust + Python + TypeScript** 三语言架构的生产级 AI 编程助手。它的设计理念是 **控制与智能分离**：

- **Rust** 负责 HTTP 桥接、SSE 事件广播、沙箱执行、代码索引、ACP 协议 —— 确保安全性和性能
- **Python** 负责 Agent 循环、工具编排、LLM 调用、上下文管理、记忆与技能系统 —— 确保 Agent 逻辑的快速迭代
- **TypeScript (Next.js)** 提供对标 Cursor 的现代化 Web UI

全系统针对 **DeepSeek 前缀缓存** 深度优化，采用三区上下文模型（不可变前缀 + 只追加日志 + 易失草稿），使多轮工具循环既快又省。

### 为什么选择 LikeCodex？

| 场景 | 传统方案 | LikeCodex |
|------|---------|-----------|
| 代码理解与重构 | 手动浏览文件 | Agent 自动阅读代码库、分析依赖、执行重构 |
| Bug 修复 | 定位 -> 修改 -> 验证，多步手动操作 | 一句话描述，Agent 自动完成全流程 |
| 测试编写 | 逐文件编写测试用例 | Agent 分析代码后自动生成并运行测试 |
| 技术调研 | 搜索文档 -> 写 demo -> 验证 | Agent 联网搜索、编写代码、运行验证一站式完成 |
| 项目维护 | 记忆全部项目细节 | 向量记忆系统持久化项目知识，跨会话复用 |

---

## 核心特性

### 🧠 深度 DeepSeek 集成

- 原生适配 DeepSeek V4 Flash / Pro 双模型
- 三区上下文模型最大化前缀缓存命中率，降低调用成本
- 双模型协调：Pro 模型负责规划研究，Flash 模型负责执行落地
- 支持 thinking 推理模式、reasoning_effort 控制、缓存指标追踪

### 🛡️ 多层安全体系

- **三种审批模式**：Ask（只读）/ Agent（自动执行）/ Manual（每步确认）
- **Shell 风险分类**：40+ 只读命令自动放行，30+ 危险模式立即拒绝
- **Docker 沙箱**：高风险命令隔离执行，支持资源限制
- **Checkpoint 快照**：写入前自动备份文件，支持一键回滚
- **策略规则引擎**：按工具、路径、命令前缀灵活配置 allow/ask/deny

### 🔧 丰富的工具生态

内置 40+ 专业工具，覆盖文件系统、Shell 执行、代码搜索、Git 操作、网络爬取、浏览器自动化、视觉识别、数据库查询、代码审查、性能分析等场景。支持通过 MCP 协议扩展第三方工具。

### 🧩 智能 Agent 能力

- **Agent 循环**：LLM 推理 -> 工具调用 -> 结果反馈 -> 继续推理，最大 50 步自动循环
- **并行调度**：只读工具自动批量并行执行，提升效率
- **智能规划**：自动判断是否需要规划，生成多步结构化计划
- **子 Agent 编排**：复杂任务可委派给子 Agent 并行处理
- **Skills 技能系统**：Markdown 剧本化技能，可复用、可分享
- **证据账本**：自动跟踪 todo 和步骤完成状态

### 💾 三层记忆系统

- **工作记忆**：当前会话短期记忆
- **情景记忆**：跨会话近期的对话摘要，持久化到 ChromaDB
- **语义记忆**：长期知识沉淀，永不自动清除
- 支持 sentence-transformers / OpenAI / TF-IDF 多种嵌入后端

### 🌐 多形态交互

- **终端 CLI/TUI**：基于 Ratatui 的全屏终端界面
- **Web UI**：Next.js 15 构建的对标 Cursor 的现代化界面
- **桌面应用**：Tauri v2 原生桌面壳
- **ACP 协议**：标准 Agent Client Protocol v1，支持 VS Code、Zed 等编辑器深度集成
- **IM 集成**：通过 imbot 审批桥接，支持即时通讯工具交互

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    交互层 (Interfaces)                        │
│   CLI / TUI        Web UI :3000     Tauri Desktop    ACP    │
│  (Rust Ratatui)  (Next.js + React)   (Desktop)    (Editor) │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE / WebSocket
┌────────────────────────┴────────────────────────────────────┐
│                控制平面 (Rust :8080)                          │
│  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ HTTP 桥接 &  │ │ 事件总线  │ │ 沙箱网关  │ │ 代码索引  │  │
│  │ 会话代理      │ │ SSE广播   │ │ Docker   │ │ FileIndex │  │
│  │ EngineBridge  │ │ EventBus  │ │ 本地沙箱  │ │ CodeGraph │  │
│  └──────────────┘ └──────────┘ └──────────┘ └───────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST + SSE
┌────────────────────────┴────────────────────────────────────┐
│               Agent 引擎 (Python :9090)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │AgentLoop │ │ToolReg   │ │Context   │ │LLM Provider    │  │
│  │主循环     │ │40+ 工具   │ │缓存优先   │ │DeepSeek/OpenAI │  │
│  │Guards    │ │Registry  │ │Compaction│ │MCP/Claude/Gemini│  │
│  │Coordinator│ │MCP扩展    │ │记忆管理   │ │本地模型        │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ LLM API 调用
┌────────────────────────┴────────────────────────────────────┐
│                    外部服务 (External)                        │
│   DeepSeek V4 API     MCP 插件服务器     Docker 沙箱         │
│   (默认大模型)         (扩展工具)         (安全隔离)          │
└─────────────────────────────────────────────────────────────┘
```

### 一次任务的完整流程

以 Web UI 发送「给 `utils.py` 写单元测试并运行」为例：

```
浏览器          Rust 服务 :8080         Python 引擎 :9090         DeepSeek
  │                   │                       │                      │
  │ POST /tasks       │                       │                      │
  │──────────────────►│ POST /tasks (转发)     │                      │
  │                   │──────────────────────►│ AgentLoop.run()      │
  │                   │                       │─────────────────────►│
  │                   │                       │◄─────────────────────│ tool_calls
  │                   │                       │ read_file, edit_file │
  │                   │                       │ run_command          │
  │                   │◄── SSE 流式输出 ───────│                      │
  │                   │ 映射 → EventBus       │                      │
  │ GET /events       │                       │                      │
  │◄──────────────────│ stream_chunk          │                      │
  │                   │ tool_call_requested   │                      │
  │                   │ permission_requested  │                      │
  │                   │ task_completed        │                      │
```

---

## 三种 Agent 模式

LikeCodex 提供三种交互模式，对标 Cursor Agent 的使用体验：

| 模式 | 图标 | 说明 | 适用场景 |
|------|------|------|---------|
| **Ask (问答)** | 🟢 | 只读模式，Agent 仅使用读工具回答问题，不修改任何文件 | 代码理解、架构咨询、技术问答 |
| **Agent (代理)** | 🔵 | 全自动模式，Agent 自主读、写、执行命令，最小化人工干预 | 日常编码、Bug 修复、重构 |
| **Manual (手动)** | 🟠 | 逐步确认模式，每次写操作或命令执行都需要你审批 | 关键代码变更、不熟悉的项目 |

> 三种模式可在运行时随时切换，无需重启会话。

---

## 快速开始

### 环境要求

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | Agent 引擎必需 |
| uv / pip | 最新 | Python 包管理器 |
| Rust | 1.70+ | CLI 和 Server 必需 |
| Node.js | 20+ | Web UI 必需 |
| Docker | 最新 (可选) | 沙箱隔离 |

### 快速安装（仅 Python）

```bash
pip install likecodex

# 首次配置
likecodex --setup

# 交互式聊天
likecodex --chat

# 单次任务
likecodex "修复这个 bug"
```

### 完整安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex

# 安装 Python 依赖
uv sync --all-packages --extra dev

# 安装 Web UI 依赖
cd web && npm install --legacy-peer-deps && cd ..

# 编译 Rust 组件
cargo build --workspace

# 首次配置
likecodex setup

# 启动全栈服务
likecodex start --web

# 或仅终端 TUI
likecodex code
```

### Windows 用户注意

Windows 上需先安装 MSVC Build Tools，运行以下脚本检查环境：

```powershell
.\scripts\check-prerequisites.ps1
```

---

## 内置工具

LikeCodex 内置 40+ 专业工具，按类别划分：

| 类别 | 工具列表 |
|------|---------|
| **文件系统** | `read_file`, `write_file`, `edit_file`, `multi_edit`, `glob`, `ls`, `move_file`, `search_files` |
| **Shell 执行** | `run_command`, `bgjobs`, `bash_output`, `kill_shell`, `wait_job` |
| **代码搜索** | `grep_files`, `codegraph_search`, `codegraph_related`, `code_index`, `code_search`, `find_symbol`, `semantic_search` |
| **LSP 语义** | `lsp_definition`, `lsp_references`, `lsp_hover`, `lsp_diagnostics`, `lsp_code_action` |
| **Git 操作** | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_commit`, `git_push` |
| **GitHub** | `github_create_pr`, `github_review_pr`, `github_add_pr_comment`, `github_create_issue`, `github_list_prs`, `github_list_issues` |
| **代码审查** | `review_file`, `review_diff`, `check_dependencies` |
| **代码重构** | `refactor_rename`, `refactor_extract`, `refactor_move_to_file` |
| **测试** | `discover_tests`, `run_tests`, `analyze_failures`, `collect_coverage`, `coverage_summary` |
| **网络** | `web_search`, `web_fetch`, `net_ping`, `net_dns_lookup`, `net_traceroute`, `net_port_scan` |
| **数据库** | `db_query`, `db_schema`, `db_explain`, `db_list_tables` |
| **浏览器** | `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot` 等 |
| **视觉** | `vision_analyze`, `vision_compare`, `vision_extract_text` |
| **Agent 元** | `task` (子Agent), `parallel_tasks`, `run_skill`, `todo_write`, `complete_step`, `ask` |
| **记忆** | `remember`, `forget`, `memory_search`, `history` |
| **日志分析** | `log_analyze`, `log_tail`, `log_grep`, `log_error_summary` |
| **API 测试** | `api_http_request`, `api_websocket_test` |
| **MCP 扩展** | `mcp__<server>__<tool>` (通过外部 MCP 服务器注册) |

---

## 配置说明

配置采用分层合并策略（低优先级 -> 高优先级）：

```
默认值 → ~/.likecodex/config.toml → likecodex.toml → 环境变量 → CLI 参数
```

### 用户级配置 (`~/.likecodex/config.toml`)

```toml
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
api_key = "your-api-key"
base_url = "https://api.deepseek.com"

[approval]
mode = "auto"  # read-only | auto | full-access | sandbox-required

[agent]
enable_planner = false
token_mode = "full"  # full | economy
max_turns = 50

[server]
port = 8080
engine_url = "http://127.0.0.1:9090"

[sandbox]
enabled = true
allow_fallback = true
image = "likecodex/sandbox:latest"

[mcp]
enabled = false
startup = "lazy"  # lazy | eager

[deepseek]
thinking = false
reasoning_effort = "medium"
```

> 项目级覆盖：在仓库根目录创建 `likecodex.toml` 即可覆盖用户级配置。

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `LIKECODEX_ENGINE_PORT` | Python 引擎端口 (默认 9090) |
| `LIKECODEX_WORKING_DIR` | 工作目录路径 |

---

## 项目结构

```
likecodex/
├── crates/                           # Rust 工作区 (9 个 crate)
│   ├── likecodex-core/              # 共享类型、配置、事件总线
│   ├── likecodex-cli/               # CLI 入口、TUI 界面、栈管理
│   ├── likecodex-server/            # Axum HTTP/SSE 服务 + 引擎桥接
│   ├── likecodex-executor/          # 本地命令安全执行
│   ├── likecodex-sandbox/           # Docker/本地沙箱隔离执行
│   ├── likecodex-indexer/           # 文件索引 + CodeGraph 符号图
│   ├── likecodex-acp/               # Agent Client Protocol v1
│   ├── likecodex-desktop/           # Tauri 桌面应用壳
│   └── likecodex-ide-fs/            # IDE 文件系统抽象
├── packages/likecodex-engine/       # Python Agent 引擎 (核心智能)
│   └── likecodex_engine/
│       ├── agent/                   # AgentLoop、协调器、Guard 防护
│       ├── tools/                   # 40+ 内置工具注册表
│       ├── context/                 # 缓存优先上下文 + 压缩
│       ├── llm/                     # LLM 提供者 (DeepSeek/OpenAI/Claude 等)
│       ├── permissions/             # 审批模式 + 策略引擎 + 风险分类
│       ├── memory/                  # 三层向量记忆系统
│       ├── mcp/                     # MCP 客户端 + 管理器
│       ├── skills/                  # 技能系统 (Markdown 剧本)
│       ├── persistence/             # SQLite 会话持久化
│       ├── prompts/                 # 系统提示词模板
│       ├── hooks/                   # 钩子系统
│       ├── lsp/                     # LSP 语言服务客户端
│       ├── composer/                # Composer 多文件编辑
│       └── routes/                  # HTTP API 路由
├── web/                             # Next.js 15 Web UI
│   └── src/
│       ├── components/              # React 组件 (UI/输入区/消息/流式等)
│       ├── hooks/                   # 自定义 Hook
│       ├── lib/                     # 状态管理、API 服务、国际化
│       └── app/                     # 页面入口
├── docs/                            # 英文文档
├── doc/                             # 中文设计文档
├── docker/                          # Docker 构建文件
├── scripts/                         # 开发/安装脚本
├── tests/                           # Python 测试
├── benchmarks/                      # 性能基准测试
└── services/                        # 附加服务 (imbot 审批桥接)
```

---

## 文档与社区

| 资源 | 说明 |
|------|------|
| [README.md](README.md) | 英文文档 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构详解 |
| [docs/API.md](docs/API.md) | HTTP API 参考 |
| [docs/USAGE.md](docs/USAGE.md) | 使用指南 |
| [docs/SPEC-CACHE.md](docs/SPEC-CACHE.md) | 缓存优先上下文规范 |
| [docs/SPEC-AGENT.md](docs/SPEC-AGENT.md) | Agent 规范 |
| [docs/ACP.md](docs/ACP.md) | Agent Client Protocol 协议 |
| [docs/EVENTS.md](docs/EVENTS.md) | SSE 事件格式 |
| [docs/SECURITY.md](docs/SECURITY.md) | 安全策略 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 路线图 |
| [CHANGELOG.md](CHANGELOG.md) | 更新日志 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |

---

## 许可证

LikeCodex 采用 **MIT** 许可证开源，详见 [LICENSE](LICENSE)。

---

> 灵感来自 OpenAI Codex、Cursor 及更广泛的 AI 编程生态。
