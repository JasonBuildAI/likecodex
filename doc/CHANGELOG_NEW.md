# v0.2.0 大版本更新日志

> 发布日期：2026-07-02

## 概述

v0.2.0 是 LikeCodex 自 0.1.0 初始发布以来的首次重大版本更新。本次更新围绕 **架构精简**、**多模型支持**、**Agent 定义系统**、**前端重构** 和 **桌面端增强** 五大方向，共包含 11 个阶段性里程碑（Phase 0–3D）。

---

## 🏗️ 架构精简 (Phase 0)

- 将单体 crate 重构为专注的子模块：core, cli, server, executor, sandbox, indexer, acp
- 分离 Rust 控制平面与 Python Agent 引擎
- 引入工作区级依赖管理 (Cargo.toml workspace)
- 简化构建管线，统一使用 `cargo build --workspace`

## 🤖 多模型支持 (Phase 1A)

- **Anthropic Claude**：完整集成 Claude 3 Opus/Sonnet/Haiku 支持
- **Google Gemini**：原生 Gemini 1.5 Pro/Flash 提供者，支持 thinking 模式
- **Ollama 本地模型**：通过 Ollama API 支持本地托管模型
- **统一 LLM 接口**：基于工厂模式的抽象 `LLMProvider`
- **动态模型切换**：会话中切换提供者/模型无需重启
- **提供者限流与重试**：可配置退避策略的限流和重试逻辑
- **模型回退链**：失败时自动回退到备用提供者

## 📝 Agent 定义系统 (Phase 1B)

- `AGENTS.md` — 声明式 Agent 规范，包含名称、模型、指令、工具、环境变量
- `.likecodex/rules/` — 按 Agent 的规则文件，自动加载到 system prompt
- **Agent 路由**：基于意图匹配将任务路由到专用 Agent
- **Agent 继承**：`extends` 关键字用于组合 Agent 配置
- **运行时 Agent 切换**：对话中途切换活跃 Agent

## ⚡ Agent Loop 优化 (Phase 1D)

- **并行工具调度**：只读工具并发执行批量调度
- **确定性输出提前退出**：收集足够证据后停止循环
- **指数退避智能重试**：临时 LLM 故障自动重试
- **工具结果去重**：跨轮次缓存相同工具结果
- **精简开销**：优化上下文窗口管理和 token 计数
- **流式优先循环**：LLM 流式集成到 Agent 循环以降低延迟

## 🛠️ 高级工具集 (Phase 1E)

- **GitHub 集成**：创建/审查 PR、添加评论、创建 Issue、列出 PR/Issue
- **数据库工具**：支持 MySQL/PostgreSQL/SQLite 的查询、Schema 查看、EXPLAIN、表列表
- **网络诊断**：Ping、DNS 查询、Traceroute、端口扫描
- **性能分析**：CPU/内存/IO 性能剖析
- **日志分析**：日志分析、实时 Tail、日志搜索、错误汇总
- **API 测试**：HTTP 请求、WebSocket 测试、响应验证

## 💬 会话管理 (Phase 1F)

- **会话分享**：将会话导出/导入为便携 JSON 文件
- **会话分支**：从任意检查点分叉出新会话
- **会话元数据**：标题、标签、描述、模型信息持久化
- **会话搜索**：全文搜索所有保存的会话
- **会话对比**：并排 diff 查看器比较会话
- **自动上下文恢复**：重连时从会话重建工作上下文

## 🎨 前端重构 (Phase 2)

- **模块化组件架构**：重构为原子化组件树
- **拖拽面板系统**：可自定义的工作区布局
- **增强键盘快捷键**：完整的快捷键系统，含速查表
- **通知中心**：统一的通知系统处理事件和告警
- **深色/浅色主题重构**：基于 CSS 变量的完整主题系统
- **流式 UI 优化**：工具调用的实时流式渲染
- **响应式设计**：完整的移动/平板响应式布局
- **无障碍 (a11y)**：WCAG 2.1 AA 合规，屏幕阅读器支持

## 📁 IDE-FS Crate (Phase 3A)

- `likecodex-ide-fs` — 新的 Rust crate，提供文件系统抽象层
- **虚拟文件系统覆盖**：项目的文件快照与虚拟表示
- **文件监视器**：通过 `notify` crate 实现实时文件变更监控
- **Git 感知操作**：尊重 `.gitignore` 和 Git 追踪状态
- **大文件处理**：>10MB 文件流式读取及截断
- **编码检测**：自动检测 UTF-8/UTF-16/GBK/GB18030

## 🔧 Server 重构 (Phase 3B)

- **模块化路由组织**：按功能分组的 Axum 端点模块
- **中间件管线**：标准化的认证、日志、限流中间件
- **WebSocket 支持**：除 SSE 外的实时双向通信
- **健康检查端点**：`/health`、`/ready`、`/live` 探针 (k8s 就绪)
- **优雅关闭**：SIGTERM/SIGINT 处理，排空进行中请求
- **指标改造**：Prometheus 指标覆盖请求延迟、错误率、LLM 用量

## 🖥️ 桌面端增强 (Phase 3D)

- **系统托盘集成**：最小化到托盘，快速操作菜单
- **多窗口支持**：将聊天面板分离为独立窗口
- **自动更新**：Tauri updater 集成，版本频道选择
- **原生通知**：任务完成的 OS 原生通知
- **自定义标题栏**：无边框窗口与自定义标题栏
- **Touch Bar 支持**：macOS Touch Bar 快捷操作

## 🚀 ACP/CLI 增强

- **ACP v1.1 协议**：扩展的 Agent Client Protocol，支持流式工具调用
- **ACP over WebSocket**：双向流式 ACP 传输
- **CLI 输出格式**：JSON、JSONL、NDJSON 输出模式，适配脚本
- **CLI 管道模式**：`likecodex --pipe` 用于 Unix 管道集成
- **CLI 会话附加**：`likecodex attach <session-id>` 加入运行中的会话
- **ACP 编辑器集成**：VS Code 扩展清单、Zed 扩展存根

---

有关详细的逐项更新列表，请参阅 [CHANGELOG.md](../CHANGELOG.md)。
