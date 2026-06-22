# 方向二：DeepSeek V4 深度绑定方案

> **架构基础**: 本方案基于[01-架构精简方案](01-架构精简方案.md)的 Python-first 架构，所有改动集中在 Python 引擎层。
> **前置依赖**: 方向一 Phase 1（Python CLI 入口）完成后开始实施。
> **关联文档**: [04-DeepSeek专属工具链方案](04-DeepSeek专属工具链方案.md)（工具层面的 DeepSeek 增强）

## 一、当前 DeepSeek 集成状况评估

### 1.1 已实现的能力

| 能力 | 状态 | 代码位置 |
|------|------|----------|
| DeepSeek API 调用 | ✅ | [deepseek.py](file:///d:/App/AgentProjects/likecodex/likecodex/packages/likecodex-engine/likecodex_engine/llm/deepseek.py) |
| 自动前缀缓存 | ✅ | [cache_first.py](file:///d:/App/AgentProjects/likecodex/likecodex/packages/likecodex-engine/likecodex_engine/context/cache_first.py) |
| Token 使用量解析 | ✅ | `deepseek.py::_parse_usage()` |
| 思维链模式 | ✅ | `thinking={"type":"enabled"}` |
| 双模型协调 | ✅ | [coordinator.py](file:///d:/App/AgentProjects/likecodex/likecodex/packages/likecodex-engine/likecodex_engine/agent/coordinator.py) |
| 三级上下文压缩 | ✅ | [compaction.py](file:///d:/App/AgentProjects/likecodex/likecodex/packages/likecodex-engine/likecodex_engine/context/compaction.py) |
| 缓存形状诊断 | ✅ | [cache_shape.py](file:///d:/App/AgentProjects/likecodex/likecodex/packages/likecodex-engine/likecodex_engine/context/cache_shape.py) |

### 1.2 缺失的能力

| 能力 | 缺失影响 | 优先级 |
|------|----------|--------|
| 缓存命中率可视化 | 用户无法感知缓存优惠，无法优化 | **高** |
| 系统 Prompt 针对 DS V4 定制 | 通用 prompt 未发挥 DS V4 最佳指令跟随能力 | **高** |
| 智能双模型路由 | 固定 pro/flash 分配，不灵活 | **中** |
| 推理过程消费追踪 | 无法区分 reasoning token 成本 | **中** |
| 缓存预热 | 首轮交互缓存未命中，体验差 | **低** |
| 缓存压力测试 | 大规模长会话下缓存行为未知 | **低** |

## 二、改造方案

### 2.1 缓存可视化（P0）

让用户实时看到缓存命中率，这是 DeepSeek 用户最关心的核心指标。

**修改文件**: `likecodex_engine/llm/deepseek.py`

```python
# 增强 _parse_usage 方法，将缓存指标广播出去
def _parse_usage(self, response, event_callback=None):
    usage = response.get("usage", {})
    cache_metrics = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "cache_hit_tokens": usage.get("prompt_cache_hit_tokens", 0),
        "cache_miss_tokens": usage.get("prompt_cache_miss_tokens", 0),
    }
    
    if cache_metrics["prompt_tokens"] > 0:
        hit_rate = cache_metrics["cache_hit_tokens"] / cache_metrics["prompt_tokens"]
        cache_metrics["hit_rate"] = round(hit_rate * 100, 1)
        # 估算节省金额（DeepSeek 缓存命中享 1折）
        cache_metrics["estimated_savings_usd"] = (
            cache_metrics["cache_hit_tokens"] * 0.00001  # DS 缓存价格
        )
    
    if event_callback:
        event_callback("cache_metrics", cache_metrics)
    
    return usage
```

**修改文件**: `likecodex_engine/context/cache_shape.py`

```python
# 添加缓存健康诊断报告
class CacheDiagnostics:
    """扩展诊断，提供可操作建议"""
    
    def health_report(self) -> str:
        issues = []
        
        if self.hit_rate < 0.3:
            issues.append("⚠️ 缓存命中率低于 30%，建议：")
            if self.prefix_changed_recently:
                issues.append("  - 系统提示词近期已变更，缓存已重置")
            issues.append("  - 考虑增加会话轮次以建立缓存")
        
        if self.tools_changed_recently:
            issues.append("  - 工具描述发生变更，建议保持工具 Schema 稳定")
        
        return "\n".join(issues)
    
    def summary(self) -> dict:
        """简洁摘要，供 CLI 状态栏和 Web UI 使用"""
        return {
            "hit_rate": self.hit_rate,
            "prefix_stable": self.is_prefix_stable(),
            "estimated_tokens_saved": self.estimated_tokens_saved,
            "health": self.health_report(),
        }
```

**修改文件**: `likecodex_engine/agent/loop.py`

在 `_run_inner()` 的 usage 记录处添加事件广播（全程约第 6 步）：

```python
# 在流式请求完成后
usage = self.llm.last_usage
if usage and self.on_event:
    cache_metrics = self.llm.get_cache_metrics()
    if cache_metrics:
        await self.on_event("cache_metrics", cache_metrics)
```

**TUI 显示改造**（`likecodex_engine/cli/tui.py`，方向一新建）：

```
┌─────────────────────────────────────────────┐
│ LikeCodex │ 模型: deepseek-v4-flash          │
│            │ 缓存: ████████░░ 82%            │
│            │ 节省: $0.047                    │
├─────────────────────────────────────────────┤
│ ...聊天内容...                                │
└─────────────────────────────────────────────┘
```

### 2.2 系统 Prompt 深度定制（P0）

针对 DeepSeek V4 的指令跟随特性设计系统提示词。

**新建文件**: `likecodex_engine/prompts/deepseek_v4_system.txt`

```text
你是一个专门针对 DeepSeek V4 优化的 AI 编程助手。

【核心原则】
1. 你在与用户协作完成编程任务，保持简洁专业
2. DeepSeek V4 擅长理解复杂的多步指令，充分利用这一点
3. 自动前缀缓存对性能至关重要，保持输出格式稳定

【工具使用规则】
- 读操作（read_file、grep、glob、ls）
  → 可以批量并行执行，不需要等前一个完成
  → 先了解全貌再动手修改
- 写操作（write_file、edit_file）
  → 确保修改内容完整、准确
  → 复杂修改前先读取确认
- Shell 执行
  → 优先使用后台 shell 运行长时间任务
  → 关注退出码和错误输出

【输出规范】
- 代码块必须标注语言（python、rust、javascript 等）
- 解释要简洁，重点在"为什么"而不是"是什么"
- 涉及修改时，指出修改的文件和行号
- 使用中文回复用户

【协作模式】
- 对于复杂任务（>3 步），先制定计划再执行
- 如果工具返回错误，分析原因并修正后重试
- 同一个错误连续 3 次失败应告知用户
```

**修改文件**: `likecodex_engine/llm/deepseek.py`

```python
class DeepSeekProvider:
    def __init__(self, ...):
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "deepseek_v4_system.txt"
        return prompt_path.read_text(encoding="utf-8")
```

### 2.3 智能双模型调度（P1）

当前 [coordinator.py](file:///d:/App/AgentProjects/likecodex/likecodex/packages/likecodex-engine/likecodex_engine/agent/coordinator.py) 使用固定规则判断是否需要规划器。改为智能分类器。

**修改文件**: `likecodex_engine/agent/coordinator.py`

```python
class SmartRouter:
    """智能任务路由 - 根据任务特征选择最佳模型组合"""
    
    # 使用 Flash 模型做轻量分类（< 100 tokens）
    CLASSIFIER_PROMPT = """分析以下用户请求，选择最合适的执行策略。

任务: {prompt}

请选择分类（仅返回字母）:
A) simple - 简单查询、问候、文件读取 - 只需 Flash
B) coding - 编码任务、调试、重构 - Flash执行，Pro可选升级
C) reasoning - 复杂逻辑、数学、架构设计 - 需要Pro
D) planning - 多步骤复杂项目 - Pro规划 + Flash执行

分类:"""
    
    async def classify(self, prompt: str, flash_llm) -> str:
        """用 Flash 模型快速分类"""
        response = await flash_llm.complete(
            messages=[{"role": "user", "content": self.CLASSIFIER_PROMPT.format(prompt=prompt)}],
            max_tokens=10,
            temperature=0,
        )
        return response.content.strip()[0]  # A/B/C/D
    
    async def route(self, prompt: str, flash_llm, pro_llm) -> RoutePlan:
        category = await self.classify(prompt, flash_llm)
        
        if category == "A":
            return RoutePlan(executor="flash", planner=None)
        elif category == "B":
            return RoutePlan(executor="flash", planner=None, can_escalate=True)
        elif category == "C":
            return RoutePlan(executor="pro", planner=None)
        elif category == "D":
            return RoutePlan(executor="flash", planner="pro")
        else:
            return RoutePlan(executor="flash", planner=None)
```

### 2.4 推理 Token 成本追踪（P1）

DeepSeek 的推理 token 单独计费，需要专门追踪。

**修改文件**: `likecodex_engine/llm/deepseek.py`

```python
@dataclass
class DeepSeekUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    reasoning_tokens: int = 0
    
    # DeepSeek V4 价格（每 1M tokens，美元）
    PRICES = {
        "deepseek-v4-flash": {"input": 0.10, "output": 0.40, "cache_hit": 0.01, "reasoning": 0.40},
        "deepseek-v4-pro":   {"input": 0.50, "output": 2.00, "cache_hit": 0.05, "reasoning": 2.00},
    }
    
    def cost_usd(self, model: str) -> float:
        p = self.PRICES.get(model, self.PRICES["deepseek-v4-flash"])
        input_cost = (self.prompt_tokens - self.cache_hit_tokens) / 1_000_000 * p["input"]
        cache_cost = self.cache_hit_tokens / 1_000_000 * p["cache_hit"]
        output_cost = self.completion_tokens / 1_000_000 * p["output"]
        reasoning_cost = self.reasoning_tokens / 1_000_000 * p.get("reasoning", p["output"])
        return round(input_cost + cache_cost + output_cost + reasoning_cost, 6)
```

### 2.5 缓存预热（P2）

**修改文件**: `likecodex_engine/server.py`

```python
async def warmup_cache(engine):
    """在后台预热 DeepSeek 前缀缓存"""
    if engine.config.llm.provider != "deepseek":
        return  # 非 DeepSeek 模型跳过
    
    logger.info("[预热] 开始预热 DeepSeek 前缀缓存...")
    try:
        warmup_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "预热查询。"},
            {"role": "assistant", "content": "好的，准备就绪。"},
        ]
        # 发送极短请求建立缓存前缀
        await engine.llm.complete(warmup_messages, max_tokens=5)
        logger.info("[预热] 缓存预热完成")
    except Exception as e:
        logger.warning(f"[预热] 跳过（{e}）")
```

在服务器启动时异步调用：

```python
# server.py main()
async def start():
    ...
    asyncio.create_task(warmup_cache(engine))  # 后台预热
    ...
```

### 2.6 Provider 配置分层

**修改文件**: `likecodex_engine/llm/deepseek.py`

```python
class DeepSeekProviderConfig:
    """DeepSeek V4 专属配置，支持细粒度调优"""
    
    # 不同任务模式下的参数模板
    MODE_CONFIGS = {
        "chat": {
            "temperature": 0.0,
            "max_tokens": 4096,
            "thinking": {"type": "disabled"},
        },
        "code": {
            "temperature": 0.1,
            "max_tokens": 8192,
            "thinking": {"type": "disabled"},
        },
        "reasoning": {
            "temperature": 0.6,
            "max_tokens": 16384,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        },
        "planning": {
            "temperature": 0.3,
            "max_tokens": 4096,
            "thinking": {"type": "disabled"},
        },
    }
    
    def get_config(self, mode: str) -> dict:
        return self.MODE_CONFIGS.get(mode, self.MODE_CONFIGS["chat"])
```

## 三、与其他文档的关联

| 关联文档 | 依赖关系 | 说明 |
|----------|----------|------|
| [01-架构精简方案](01-架构精简方案.md) | 前置基础 | 本方案的 CLI 状态栏/Web UI 改造依赖方向一的 Python-first 架构 |
| [03-本地响应速度提升方案](03-本地响应速度提升方案.md) | 协同 | 缓存预热（2.5）与后台 shell（方向三 3.1）配合提升交互流畅度 |
| [04-DeepSeek专属工具链方案](04-DeepSeek专属工具链方案.md) | 增强 | 本方案的缓存诊断能力暴露为 `deepseek_cache_analyze` 工具 |

## 四、实施里程碑

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| P0 | 1 周 | 缓存可视化 + System Prompt 定制完成，用户可见缓存命中率和节省金额 |
| P1 | 2 周 | SmartRouter + 成本追踪完成，Pro/Flash 自动调配 |
| P2 | 1 周 | 缓存预热 + Provider 配置分层完成 |
