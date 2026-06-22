# 方向六：Web UI 差异化优势方案

> **架构基础**: 本方案基于[01-架构精简方案](01-架构精简方案.md)的 Python-first 架构。Web UI 构建产物内嵌到 Python 包中，用户无需 Node.js 环境。
> **前置依赖**: 方向一 Phase 1（Python CLI 入口 + 包结构）+ 方向二 Phase 1（缓存数据源）完成后开始实施。
> **关联文档**: [02-DeepSeek深度绑定方案](02-DeepSeek深度绑定方案.md)（缓存可视化数据源） | [04-DeepSeek专属工具链方案](04-DeepSeek专属工具链方案.md)（专属工具 Web 面板）

## 一、当前状态与定位

### 1.1 竞争格局

| 产品 | CLI/TUI | Web UI | 桌面应用 |
|------|---------|--------|----------|
| Reasonix | ✅ Bubble Tea | ❌ **无** | ✅ Wails |
| LikeCodex | ✅ ratatui | ✅ **有** | ⏳ Tauri WIP |
| Cursor | ⏳ 有限 | ✅ | ✅ 原生 |
| Windsurf | ❌ | ✅ | ✅ Electron |

**Web UI 是 LikeCodex 相对于 Reasonix 的独特优势。** 但如果需要用户装 Node.js + npm run dev，这个优势就大打折扣。

### 1.2 当前 Web UI 的问题

| 问题 | 影响 | 严重程度 |
|------|------|----------|
| 需要 Node.js 20 + npm install | 用户额外安装费时 | **高** |
| Next.js 15 开发服务器启动慢 | 等待 5-10 秒 | **高** |
| 未内嵌到 Python 包 | 需要额外启动一个进程 | **高** |
| 没有 DeepSeek 专属面板 | 与通用 chat UI 无区别 | **中** |
| Monaco Editor 体积大（~20MB） | 加载慢 | **低** |

## 二、改造方案

### 2.1 静态构建产物内嵌（P0）

将 Next.js 构建产物打包到 Python 包中，用户 `pip install likecodex` 后就能直接用 Web UI。

**步骤 1：配置 Next.js 静态导出**

**修改文件**: `web/next.config.js`

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',  // 静态 HTML 导出
  trailingSlash: true,
  images: {
    unoptimized: true,  // 静态导出不需要图片优化
  },
}
module.exports = nextConfig
```

**步骤 2：CI 构建并复制到 Python 包**

**新建文件**: `.github/workflows/build-web.yml`

```yaml
name: Build Web UI
on:
  release:
    types: [published]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          
      - run: cd web && npm ci && npm run build
      
      # 将构建产物复制到 Python 包
      - run: |
          rm -rf packages/likecodex-engine/likecodex_engine/static
          cp -r web/out packages/likecodex-engine/likecodex_engine/static
      
      # 提交并发布
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build && python -m build
      - run: twine upload dist/*
```

**步骤 3：Python 引擎提供静态文件服务**

**修改文件**: `likecodex_engine/server.py`

```python
import os
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"

def setup_web_ui(app: web.Application):
    """配置 Web UI 静态文件路由"""
    
    if not STATIC_DIR.exists():
        logger.warning(f"Web UI 静态文件未找到: {STATIC_DIR}")
        logger.warning("用户需构建 Web UI 或安装完整版: pip install likecodex[full]")
        return
    
    # 静态文件服务
    app.router.add_static(
        '/_next', 
        path=str(STATIC_DIR / '_next'),
        name='next_static',
    )
    
    # SPA 支持：所有非 API 路由返回 index.html
    async def spa_handler(request):
        index_path = STATIC_DIR / 'index.html'
        if not index_path.exists():
            return web.Response(
                text="Web UI 未构建，请运行: cd web && npm run build",
                status=200,
            )
        return web.FileResponse(index_path)
    
    app.router.add_get('/', spa_handler)
    app.router.add_get('/{tail:.*}', spa_handler)
```

用户只需：

```bash
pip install likecodex
likecodex --web
# 浏览器自动打开 http://localhost:9090
```

### 2.2 DeepSeek 专属面板（P1）

在 Web UI 中增加 Reasonix 不可能有的 DeepSeek 专属面板。

**修改文件**: `web/src/app/page.tsx`（示意结构）

```tsx
// 主布局增加 DeepSeek 侧边栏
export default function Home() {
  return (
    <div className="flex h-screen">
      {/* 左侧：DeepSeek 专属面板（新增） */}
      <DeepSeekPanel />
      
      {/* 中间：会话列表 */}
      <SessionSidebar />
      
      {/* 右侧：主聊天区域 */}
      <ChatArea />
    </div>
  );
}
```

**新建文件**: `web/src/components/DeepSeekPanel.tsx`

```tsx
import { useEffect, useState } from 'react';
import { useSSE } from '@/lib/sse';

interface CacheMetrics {
  hit_rate: number;
  cache_hit_tokens: number;
  cache_miss_tokens: number;
  estimated_savings_usd: number;
  prefix_stable: boolean;
}

export function DeepSeekPanel() {
  const [metrics, setMetrics] = useState<CacheMetrics | null>(null);
  const [model, setModel] = useState('deepseek-v4-flash');
  
  // 通过 SSE 接收缓存指标
  const { lastEvent } = useSSE('/events');
  
  useEffect(() => {
    if (lastEvent?.type === 'cache_metrics') {
      setMetrics(lastEvent.payload);
    }
  }, [lastEvent]);
  
  return (
    <div className="w-64 bg-gray-900 p-4 border-r border-gray-700">
      <h2 className="text-lg font-bold text-white mb-4">DeepSeek</h2>
      
      {/* 模型选择 */}
      <div className="mb-4">
        <label className="text-xs text-gray-400">当前模型</label>
        <select
          value={model}
          onChange={(e) => switchModel(e.target.value)}
          className="w-full mt-1 bg-gray-800 text-white rounded px-2 py-1"
        >
          <option value="deepseek-v4-flash">V4 Flash（快速）</option>
          <option value="deepseek-v4-pro">V4 Pro（深度）</option>
        </select>
      </div>
      
      {/* 缓存命中率 */}
      <div className="mb-4">
        <label className="text-xs text-gray-400">缓存命中率</label>
        <div className="mt-1 bg-gray-800 rounded h-6 overflow-hidden">
          <div
            className="bg-green-500 h-full transition-all"
            style={{ width: `${metrics?.hit_rate || 0}%` }}
          />
        </div>
        <span className="text-sm text-gray-300">
          {metrics?.hit_rate?.toFixed(1) || '--'}%
        </span>
      </div>
      
      {/* 节省金额 */}
      <div className="mb-4">
        <label className="text-xs text-gray-400">本会话节省</label>
        <div className="text-green-400 font-mono">
          ${metrics?.estimated_savings_usd?.toFixed(4) || '0.0000'}
        </div>
      </div>
      
      {/* 缓存稳定性 */}
      <div className="mb-4">
        <label className="text-xs text-gray-400">缓存前缀状态</label>
        <div className="flex items-center mt-1">
          <div className={`w-2 h-2 rounded-full mr-2 ${
            metrics?.prefix_stable ? 'bg-green-400' : 'bg-yellow-400'
          }`} />
          <span className="text-sm text-gray-300">
            {metrics?.prefix_stable ? '稳定' : '变动中'}
          </span>
        </div>
      </div>
      
      {/* Token 统计 */}
      <div className="border-t border-gray-700 pt-4">
        <h3 className="text-sm font-bold text-gray-400 mb-2">Token 统计</h3>
        <div className="space-y-1 text-xs text-gray-400">
          <div className="flex justify-between">
            <span>提示 Tokens</span>
            <span className="text-white">{metrics?.cache_mit_tokens ?? 0}</span>
          </div>
          <div className="flex justify-between">
            <span>缓存命中 Tokens</span>
            <span className="text-green-400">{metrics?.cache_hit_tokens ?? 0}</span>
          </div>
        </div>
      </div>
      
      {/* 模型切换按钮 */}
      <button
        onClick={() => {/* 调用 API 切换模型 */}}
        className="w-full mt-4 bg-blue-600 text-white rounded py-2 hover:bg-blue-700"
      >
        切换模型
      </button>
    </div>
  );
}
```

### 2.3 轻量化 Web UI 版本（P1）

除了完整的 Next.js Web UI，提供零依赖的纯 HTML 版本。

**新建文件**: `likecodex_engine/static/lite/index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LikeCodex Lite</title>
<style>
/* 内联 CSS，不到 200 行 */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #1a1a2e; color: #eee; height: 100vh;
  display: flex; flex-direction: column;
}
#chat { flex: 1; overflow-y: auto; padding: 16px; }
.msg { margin-bottom: 12px; padding: 10px; border-radius: 8px; }
.msg.user { background: #16213e; margin-left: 40px; }
.msg.assistant { background: #0f3460; margin-right: 40px; }
.msg.tool { background: #1a1a2e; border-left: 3px solid #e94560; font-size: 0.85em; }
pre { 
  background: #0d0d1a; padding: 10px; border-radius: 4px;
  overflow-x: auto; margin: 8px 0; font-size: 0.9em;
}
code { font-family: 'Fira Code', 'Cascadia Code', monospace; }
#input-area {
  display: flex; padding: 12px; border-top: 1px solid #333; gap: 8px;
}
#input { 
  flex: 1; background: #16213e; border: 1px solid #333;
  color: #eee; padding: 10px; border-radius: 6px;
  font-size: 14px; resize: none;
}
#send {
  background: #e94560; color: white; border: none;
  padding: 10px 20px; border-radius: 6px; cursor: pointer;
}
/* 状态栏 */
#status {
  display: flex; gap: 16px; padding: 6px 16px;
  background: #0f3460; font-size: 0.8em; color: #aaa;
}
#status .hit-rate { color: #4ade80; }
</style>
</head>
<body>
<div id="status">
  <span>LikeCodex Lite</span>
  <span>模型: <span id="model-name">deepseek-v4-flash</span></span>
  <span>缓存: <span id="cache-rate" class="hit-rate">--%</span></span>
</div>
<div id="chat"></div>
<div id="input-area">
  <textarea id="input" rows="2" placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"></textarea>
  <button id="send" onclick="sendMessage()">发送</button>
</div>

<script>
// 完整的 chat 功能，不到 200 行 JavaScript
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const cacheRate = document.getElementById('cache-rate');

let sessionId = crypto.randomUUID();
let isStreaming = false;

function addMessage(role, content) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = marked(content);  // 简单 markdown 渲染
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

// SSE 流式连接
async function sendMessage() {
  if (isStreaming) return;
  const text = input.value.trim();
  if (!text) return;
  
  addMessage('user', text);
  input.value = '';
  isStreaming = true;
  
  const response = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: text,
      session_id: sessionId,
      stream: true,
    }),
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let assistantMsg = '';
  
  // 添加助手消息占位
  const assistantDiv = document.createElement('div');
  assistantDiv.className = 'msg assistant';
  chat.appendChild(assistantDiv);
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n').filter(l => l.startsWith('data: '));
    
    for (const line of lines) {
      const data = line.slice(6);
      if (data === '[DONE]') continue;
      
      try {
        const json = JSON.parse(data);
        if (json.type === 'delta' && json.content) {
          assistantMsg += json.content;
          assistantDiv.innerHTML = marked(assistantMsg);
          chat.scrollTop = chat.scrollHeight;
        } else if (json.type === 'cache_metrics' && json.payload) {
          cacheRate.textContent = json.payload.hit_rate + '%';
        }
      } catch {}
    }
  }
  
  isStreaming = false;
}

// Enter 发送，Shift+Enter 换行
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
</script>
</body>
</html>
```

Lite 版本的核心优势：

| 指标 | 完整 Web UI | Lite 版本 |
|------|-------------|-----------|
| 依赖 | Node.js + npm | 零依赖 |
| 文件大小 | ~50MB（含 node_modules） | **<10KB** |
| 启动方式 | 独立进程 | Python 服务器直接提供 |
| 功能 | 完整（Monaco 编辑器、diff 视图等） | 核心聊天功能 |
| 适用场景 | 需要完整 IDE 体验 | 快速调试、嵌入使用 |

### 2.4 缓存监控 Dashboard（P2）

在 Web UI 中增加完整的缓存监控页面：

**访问路径**: `http://localhost:9090/dashboard`

```tsx
// web/src/app/dashboard/page.tsx
export default function Dashboard() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">DeepSeek 缓存监控</h1>
      
      {/* 缓存命中率趋势图 */}
      <div className="grid grid-cols-2 gap-4">
        <Card title="缓存命中率">
          <LineChart data={cacheHistory} />
        </Card>
        <Card title="Token 消耗">
          <BarChart data={tokenUsage} />
        </Card>
        <Card title="前缀稳定性">
          <StabilityIndicator shape={prefixShape} />
        </Card>
        <Card title="节省金额">
          <CostSavings value={totalSavings} />
        </Card>
      </div>
      
      {/* 缓存诊断建议 */}
      <Card title="优化建议" className="mt-4">
        <OptimizationTips tips={diagnosisTips} />
      </Card>
    </div>
  );
}
```

### 2.5 会话对比视图（P2）

允许用户在同一 Web UI 中开两个并列会话，对比 Flash 和 Pro 的输出：

```tsx
// web/src/app/compare/page.tsx
export default function CompareView() {
  return (
    <div className="flex h-full">
      <div className="flex-1 border-r">
        <h2 className="p-2 bg-gray-800 text-sm">Flash 模型</h2>
        <ChatArea model="deepseek-v4-flash" />
      </div>
      <div className="flex-1">
        <h2 className="p-2 bg-gray-800 text-sm">Pro 模型</h2>
        <ChatArea model="deepseek-v4-pro" />
      </div>
    </div>
  );
}
```

### 2.6 Python 引擎 API 增强

为支持 Web UI 的 DeepSeek 面板，新增以下 API 端点：

**修改文件**: `likecodex_engine/server.py`

```python
# DeepSeek 专属 API 路由
app.router.add_get('/api/deepseek/cache-stats', handle_cache_stats)
app.router.add_post('/api/deepseek/switch-model', handle_switch_model)
app.router.add_get('/api/deepseek/session-cost', handle_session_cost)
app.router.add_get('/api/deepseek/diagnostics', handle_diagnostics)

async def handle_cache_stats(request):
    """返回当前会话的缓存统计"""
    session = get_current_session(request)
    return web.json_response(session.cache_metrics.summary())

async def handle_switch_model(request):
    """切换当前会话的模型"""
    data = await request.json()
    model = data.get('model')  # 'flash' 或 'pro'
    session = get_current_session(request)
    session.switch_model(model)
    return web.json_response({"status": "ok", "model": model})

async def handle_session_cost(request):
    """返回当前会话的累计成本"""
    session = get_current_session(request)
    return web.json_response(session.usage_aggregator.total_cost())
```

## 三、Web UI 改造后的架构

```
用户访问:
  http://localhost:9090/
    ├── /  →  SPA 主页（完整 Web UI）
    ├── /lite → 轻量版（零依赖）
    ├── /dashboard → 缓存监控面板
    ├── /compare → 双模型对比
    └── /api/* → Python 引擎 API

不用额外启动任何进程，一个 Python 进程搞定所有。
```

## 四、与其他文档的关联

| 关联文档 | 依赖关系 | 说明 |
|----------|----------|------|
| [01-架构精简方案](01-架构精简方案.md) | 前置基础 | Web UI 静态文件内嵌到 `likecodex_engine/static/` |
| [02-DeepSeek深度绑定方案](02-DeepSeek深度绑定方案.md) | 数据源 | DeepSeek 面板的缓存数据来自方向二的 `cache_metrics` 事件 |
| [03-本地响应速度提升方案](03-本地响应速度提升方案.md) | 协同 | Lite 版本直接通过 SSE 连接引擎，省去 WebSocket 转换层 |
| [05-用户体验简化方案](05-用户体验简化方案.md) | 协同 | 一键安装后 `likecodex --web` 直接打开浏览器 |

## 五、实施里程碑

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| P0 | 1 周 | Next.js 静态导出 + 内嵌 Python 包 + `likecodex --web` 可用 |
| P1 | 2 周 | DeepSeek 专属面板 + Lite HTML 版本 + 模型切换 API |
| P2 | 可选 | 缓存监控 Dashboard + 双模型对比视图 |

注意：P0 完成后，用户只需 `pip install likecodex && likecodex --web` 即可在浏览器中使用 LikeCodex，不再需要任何 Node.js 环境。
