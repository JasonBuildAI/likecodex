# 方向四：DeepSeek 专属工具链方案

> **架构基础**: 本方案基于[01-架构精简方案](01-架构精简方案.md)的 Python-first 架构。
> **前置依赖**: 方向一 Phase 1（Python CLI 入口）+ 方向二（缓存诊断基础）完成后开始实施。
> **关联文档**: [02-DeepSeek深度绑定方案](02-DeepSeek深度绑定方案.md)（提供缓存诊断数据源） | [03-本地响应速度提升方案](03-本地响应速度提升方案.md)（工具性能优化）

## 一、设计目标

创建一套 DeepSeek V4 专属工具，这是 LikeCodex **区别于所有其他 coding agent 的核心竞争力**。这些工具让模型能够：

1. **自我诊断** — 检查自己的缓存效率和成本
2. **自我优化** — 调整提示词以获得更好的 DeepSeek V4 响应
3. **深度推理** — 调用专门的高强度推理能力
4. **智能分配合适的 DeepSeek 模型**

所有工具在 `token_mode="economy"` 时默认隐藏（减少 tool schema 对上下文的占用），检测到 DeepSeek provider 时自动激活。

## 二、工具设计

### 2.1 `deepseek_cache_analyze` — 缓存分析工具（P0）

让模型自己能检查当前会话的缓存效率。

**新建文件**: `likecodex_engine/tools/deepseek_tools.py`

```python
"""DeepSeek V4 专属工具集"""

import json
from typing import Optional
from likecodex_engine.context.cache_shape import CacheDiagnostics, PrefixShape
from likecodex_engine.llm.deepseek import DeepSeekUsage

TOOL_DEFINITIONS = {}

def tool(name, description, read_only=True):
    """装饰器：注册 DeepSeek 专属工具"""
    def decorator(func):
        TOOL_DEFINITIONS[name] = {
            "name": name,
            "description": description,
            "read_only": read_only,
            "handler": func,
        }
        return func
    return decorator


@tool(
    name="deepseek_cache_analyze",
    description="分析当前会话的 DeepSeek 前缀缓存命中效率，包含优化建议",
    read_only=True,
)
async def deepseek_cache_analyze(
    session_id: Optional[str] = None,
    detailed: bool = False,
) -> str:
    """
    分析 DeepSeek 缓存健康状况。
    
    Args:
        session_id: 会话 ID，默认使用当前会话
        detailed: 是否输出详细诊断信息
    
    Returns:
        缓存分析报告（JSON 格式）
    """
    # 通过 global 或 context 获取当前会话信息
    ctx = get_current_context(session_id)
    if not ctx:
        return json.dumps({"error": "无法获取会话上下文"})
    
    shape = PrefixShape.from_context(ctx)
    metrics = ctx.cache_metrics
    
    result = {
        "basic": {
            "hit_rate": metrics.hit_rate,
            "prompt_tokens": metrics.prompt_tokens,
            "cache_hit_tokens": metrics.cache_hit_tokens,
            "cache_miss_tokens": metrics.cache_miss_tokens,
            "estimated_savings": metrics.estimated_savings_usd,
        },
        "stability": {
            "system_hash": shape.system_hash[:8] + "...",
            "tools_hash": shape.tools_hash[:8] + "...",
            "prefix_stable": shape.is_prefix_stable(),
            "tool_schema_changes": shape.tool_schema_change_count,
        },
        "optimization_tips": [],
    }
    
    # 生成优化建议
    if result["basic"]["hit_rate"] < 0.3:
        result["optimization_tips"].append(
            "缓存命中率较低。可能原因：System prompt 最近被修改、工具 Schema 频繁变化。"
        )
    if not result["stability"]["prefix_stable"]:
        result["optimization_tips"].append(
            "System prompt 哈希不稳定，建议检查 hooks 是否动态修改了 system prompt。"
        )
    if result["stability"]["tool_schema_changes"] > 3:
        result["optimization_tips"].append(
            "工具 Schema 变动频繁，建议减少动态工具注册。"
        )
    
    if not result["optimization_tips"]:
        result["optimization_tips"].append("缓存状态良好，无需优化。")
    
    if detailed:
        result["detailed"] = {
            "prefix_length": shape.prefix_length,
            "log_length": len(ctx.log),
            "last_compaction": ctx.last_compaction_time,
            "session_age_seconds": ctx.age_seconds,
        }
    
    return json.dumps(result, indent=2, ensure_ascii=False)
```

### 2.2 `deepseek_reasoning` — 深度推理工具（P0）

当模型需要深度思考时，调用 Pro 模型 + 开启 thinking 模式。

```python
@tool(
    name="deepseek_reasoning",
    description="对复杂问题使用 DeepSeek V4 Pro 模型进行深度推理（带思维链），"
                "适用于复杂逻辑、数学、架构设计等场景",
    read_only=True,
)
async def deepseek_reasoning(
    question: str,
    context: Optional[str] = None,
    detail_level: str = "high",
) -> str:
    """
    使用 DeepSeek V4 Pro 进入深度推理模式。
    
    Args:
        question: 需要深度推理的问题
        context: 额外的上下文信息（代码片段、日志等）
        detail_level: high/medium/low 推理深度
    
    Returns:
        推理结果（含 reasoning_content 和最终答案）
    """
    pro_llm = get_pro_llm()  # 获取 Pro 模型实例
    
    messages = [{"role": "user", "content": question}]
    if context:
        messages.insert(0, {
            "role": "system",
            "content": f"额外上下文：\n{context}"
        })
    
    reasoning_effort = {"high": "high", "medium": "medium", "low": "low"}.get(detail_level, "high")
    
    response = await pro_llm.complete(
        messages=messages,
        thinking={"type": "enabled"},
        reasoning_effort=reasoning_effort,
        max_tokens=16384,
    )
    
    result = {
        "reasoning_process": response.reasoning_content,
        "answer": response.content,
        "model": response.model,
        "usage": {
            "reasoning_tokens": response.usage.reasoning_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    }
    
    return json.dumps(result, indent=2, ensure_ascii=False)
```

### 2.3 `deepseek_tune_prompt` — 提示词优化工具（P1）

模型可以通过此工具自我优化 system prompt，适配 DeepSeek V4 的特性。

```python
@tool(
    name="deepseek_tune_prompt",
    description="分析和优化针对 DeepSeek V4 的提示词模板，"
                "以获得更好的指令跟随和代码生成效果",
    read_only=True,
)
async def deepseek_tune_prompt(
    current_prompt: str,
    pain_points: str,
) -> str:
    """
    基于实际问题优化提示词。
    
    Args:
        current_prompt: 当前的 system prompt 内容
        pain_points: 遇到的问题描述（如'工具调用格式不一致'、'代码经常不完整'）
    
    Returns:
        优化后的提示词模板
    """
    optimizer_llm = get_flash_llm()  # 用 Flash 做优化（便宜）
    
    optimization_prompt = f"""你是一个 DeepSeek V4 提示词优化专家。
分析以下问题并提出优化后的提示词。

当前提示词:
```
{current_prompt[:2000]}
```

遇到的问题:
{pain_points}

请提供优化后的完整提示词。优化原则：
1. 保持格式稳定（维护前缀缓存）
2. 明确工具使用规则
3. 利用 DeepSeek V4 的指令跟随能力
4. 针对实际问题定向修复

只返回优化后的提示词，不要额外解释。"""
    
    response = await optimizer_llm.complete(
        messages=[{"role": "user", "content": optimization_prompt}],
        temperature=0.3,
        max_tokens=4096,
    )
    
    return response.content
```

### 2.4 `deepseek_switch_model` — 模型切换工具（P1）

允许模型在执行过程中，根据任务复杂度动态在 Flash 和 Pro 之间切换。

```python
@tool(
    name="deepseek_switch_model",
    description="在当前会话中动态切换 DeepSeek 模型（flash/pro），"
                "适用于任务复杂度变化时需要更强/更快的模型",
    read_only=False,
)
async def deepseek_switch_model(
    model: str,
    reason: str,
) -> str:
    """
    切换当前会话使用的 DeepSeek 模型。
    
    Args:
        model: "flash" 或 "pro"
        reason: 切换原因说明
    
    Returns:
        切换结果
    """
    valid_models = {"flash": "deepseek-v4-flash", "pro": "deepseek-v4-pro"}
    
    if model not in valid_models:
        return json.dumps({
            "success": False,
            "error": f"无效模型: {model}，可选: {list(valid_models.keys())}"
        })
    
    # 从全局获取当前会话并切换模型
    session = get_current_session()
    old_model = session.llm.model
    session.llm = create_provider(
        provider="deepseek",
        model=valid_models[model],
    )
    
    # 记录切换事件
    log_model_switch(session.id, old_model, valid_models[model], reason)
    
    return json.dumps({
        "success": True,
        "switched_from": old_model,
        "switched_to": valid_models[model],
        "reason": reason,
        "note": f"已切换到 {model}，后续请求将使用 {valid_models[model]}"
    })
```

### 2.5 `deepseek_cost_estimate` — 成本预估工具（P2）

在任务执行前估算 token 消耗，帮助用户做成本决策。

```python
@tool(
    name="deepseek_cost_estimate",
    description="预估执行指定任务需要的 token 数量和成本",
    read_only=True,
)
async def deepseek_cost_estimate(
    task_description: str,
    estimated_steps: int = 5,
    files_to_read: list[str] = None,
) -> str:
    """
    预估任务成本。
    
    Args:
        task_description: 任务描述
        estimated_steps: 预估的 agent 循环步数
        files_to_read: 需要读取的文件列表
    
    Returns:
        成本预估报告
    """
    # 估算 system prompt 大小
    system_prompt_size = 2000  # tokens
    
    # 估算文件读取量
    file_tokens = 0
    if files_to_read:
        for fpath in files_to_read:
            try:
                content = await read_file_content(fpath)
                file_tokens += len(content) // 2  # 粗略估算
            except:
                pass
    
    # 每步估算
    step_input = system_prompt_size + file_tokens + 500  # 用户输入
    step_output = 1000  # 模型输出
    
    total_input = step_input * (estimated_steps + 1)  # +1 首轮
    total_output = step_output * estimated_steps
    
    # 缓存假设（首轮未命中，后续命中）
    cache_hit_rate = 0.6  # 假设 60%
    cached_tokens = int(total_input * cache_hit_rate)
    uncached_tokens = total_input - cached_tokens
    
    # DeepSeek V4 Flash 价格
    cost = {
        "uncached_input": uncached_tokens / 1_000_000 * 0.10,
        "cached_input": cached_tokens / 1_000_000 * 0.01,
        "output": total_output / 1_000_000 * 0.40,
        "total_usd": 0,
    }
    cost["total_usd"] = round(cost["uncached_input"] + cost["cached_input"] + cost["output"], 6)
    
    return json.dumps({
        "task": task_description,
        "estimated_steps": estimated_steps,
        "estimated_tokens": {
            "input_total": total_input,
            "output_total": total_output,
            "cache_hit_estimate": f"{cache_hit_rate * 100}%",
        },
        "estimated_cost_usd": cost,
        "disclaimer": "此为预估值，实际消耗可能有所不同。"
    }, indent=2, ensure_ascii=False)
```

## 三、工具注册与激活机制

### 3.1 条件注册

**修改文件**: `likecodex_engine/tools/registry.py`

```python
class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self._deepseek_tools = {}  # DeepSeek 专属工具
        
    def register_deepseek_tools(self, provider: str):
        """检测到 DeepSeek provider 时注册专属工具"""
        if provider == "deepseek" and not self._deepseek_tools_registered:
            from likecodex_engine.tools import deepseek_tools
            for name, tool_def in deepseek_tools.TOOL_DEFINITIONS.items():
                self._tools[name] = tool_def
                self._deepseek_tools[name] = tool_def
            self._deepseek_tools_registered = True
```

### 3.2 Token Economy 兼容

在 `token_mode="economy"` 时，DeepSeek 专属工具默认展开（因为用户明确在使用 DeepSeek），而其他可选工具折叠：

```python
# 在 dispatch.py 中
def get_visible_tools(token_mode: str, provider: str) -> list:
    tools = []
    for name, tool_def in registry._tools.items():
        if token_mode == "economy":
            # 经济模式：只显示核心 + DeepSeek 专属
            if name.startswith("deepseek_") and provider == "deepseek":
                tools.append(tool_def)  # DeepSeek 工具始终可见
            elif name in CORE_TOOLS:
                tools.append(tool_def)
            # 其他可选工具隐藏
        else:
            tools.append(tool_def)
    return tools
```

## 四、命名空间与冲突避免

DeepSeek 专属工具使用 `deepseek_` 前缀，避免与通用工具命名冲突：

| 工具名 | 不与以下冲突 | 原因 |
|--------|-------------|------|
| `deepseek_cache_analyze` | 任何通用工具 | `deepseek_` 前缀唯一命名空间 |
| `deepseek_reasoning` | 同上 | 同上 |
| `deepseek_tune_prompt` | 同上 | 同上 |
| `deepseek_switch_model` | 同上 | 同上 |
| `deepseek_cost_estimate` | 同上 | 同上 |

## 五、与其他文档的关联

| 关联文档 | 依赖关系 | 说明 |
|----------|----------|------|
| [01-架构精简方案](01-架构精简方案.md) | 前置基础 | 工具注册到 `likecodex_engine/tools/` 目录 |
| [02-DeepSeek深度绑定方案](02-DeepSeek深度绑定方案.md) | **强依赖** | `deepseek_cache_analyze` 使用方向二的 `CacheDiagnostics` 和 `PrefixShape` |
| [03-本地响应速度提升方案](03-本地响应速度提升方案.md) | 协同 | 工具结果缓存机制可加速 `deepseek_cost_estimate` |

## 六、实施里程碑

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| P0 | 1 周 | `deepseek_cache_analyze` + `deepseek_reasoning` 两个核心工具可用 |
| P1 | 1 周 | `deepseek_tune_prompt` + `deepseek_switch_model` + 条件注册机制 |
| P2 | 可选 | `deepseek_cost_estimate` + Token Economy 适配 |
