# 06：多文件 Composer

> **系列文档**: [05-智能上下文与引用系统](05-智能上下文与引用系统.md) → 本文 → [07-AI终端集成](07-AI终端集成.md)
> **前置依赖**: 04-AI代码补全与内联编辑（Diff 视图复用），05-智能上下文与引用系统（@ 引用系统复用）。
> **关联文档**: [01-IDE整体架构规划](01-IDE整体架构规划.md)（Composer 面板架构）| [03-高级编辑器核心](03-高级编辑器核心.md)（Diff 视图复用）| [07-AI终端集成](07-AI终端集成.md)（Composer 可自动执行命令）

---

## 一、目标

实现类似 Cursor Composer 的**多文件 AI 编辑面板**，让用户通过自然语言描述一整个任务，AI 自动修改多个文件并提供变更预览。

### 1.1 核心能力

| 能力 | 说明 | 优先级 |
|------|------|--------|
| **多轮对话** | 在 Composer 中与 AI 持续对话，逐步完善修改 | P0 |
| **多文件编辑** | AI 同时修改多个文件，自动处理跨文件依赖 | P0 |
| **变更预览** | 每个文件修改展示 Diff，可单独接受/拒绝 | P0 |
| **文件创建/删除** | AI 根据需要创建新文件或删除无用文件 | P1 |
| **终端命令执行** | AI 在修改后自动运行命令（如 `npm install`） | P1 |
| **检查点回滚** | 每次 Composer 修改前自动创建 Git checkpoint | P1 |
| **取消/恢复** | 部分接受修改，撤销不想要的变更 | P2 |

### 1.2 对标 Cursor Composer

| 功能 | Cursor Composer | LikeCodex 目标 |
|------|----------------|---------------|
| 多文件编辑 | ✅ 自动识别需要修改的文件 | ✅ 基于 Agent 的分析 |
| Diff 预览 | ✅ 每个文件单独的 Diff | ✅ 复用 03 的 Diff 视图 |
| 文件创建 | ✅ AI 自动创建 | ✅ 已有 write_file 工具 |
| 终端命令 | ✅ 自动运行 | ✅ Agent 已有 run_command |
| Checkpoint | ✅ 自动 Git commit | ✅ 已有 checkpoint 系统 |
| Normal/Agent 模式 | ✅ Normal 单文件，Agent 多文件 | ✅ 复用 planner-executor |
| 上下文引用 | ✅ @file, @folder | ✅ 复用 05 的 @ 系统 |

---

## 二、交互设计

### 2.1 Composer 面板布局

```
┌─ Composer ─────────────────────────────────────┐
│                                                 │
│  [消息历史区域]                                  │
│                                                 │
│  用户: 帮我添加用户认证功能                       │
│  ──────────────────────────────────             │
│  AI: 我需要修改以下文件：                         │
│    ✅ src/auth/login.tsx (创建)                 │
│    ✅ src/auth/useAuth.ts (创建)                │
│    ✅ src/App.tsx (修改)                        │
│    ✅ package.json (修改 - 添加依赖)             │
│                                                 │
│  ┌─ 变更预览 ────────────────────────────────┐ │
│  │ [src/auth/login.tsx] [src/App.tsx] ...    │ │
│  │ ┌────────────────────────────────────────┐ │ │
│  │ │ Diff 内容 (复用 03 DiffViewer)         │ │ │
│  │ └────────────────────────────────────────┘ │ │
│  │ 全部接受 全部拒绝  单个文件: [✓] [✗]        │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  [输入区域] @ 引用文件...                        │
│  └──────────────────────────────────────────────┘
```

### 2.2 交互流程

```
1. 用户打开 Composer 面板 (Cmd+I)
2. 用户输入任务描述 + @ 引用相关文件
3. AI Agent 开始分析：
   a. 理解需求 → 确定需要修改哪些文件
   b. 并行读取相关文件
   c. 制定修改计划
4. 计划展示：AI 列出将修改的所有文件及变更类型
5. 用户确认计划后，AI 执行修改
6. 每个文件的 Diff 展示在变更预览区
7. 用户可逐个文件接受/拒绝
8. 接受后 AI 可能自动运行后续命令（依赖安装等）
9. 全部接受后自动创建 checkpoint
```

---

## 三、技术方案

### 3.1 整体架构

```
┌────────────────────────────────────────────────────┐
│               Composer 面板 (Web UI)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Chat     │  │ File     │  │ Change           │ │
│  │ History  │  │ List     │  │ Preview (Diff)   │ │
│  └────┬─────┘  └────┬─────┘  └───────┬──────────┘ │
│       │             │                │            │
│  ┌────┴─────────────┴────────────────┴──────────┐ │
│  │            composerStore (Zustand)             │ │
│  │  - messages: ComposerMessage[]                │ │
│  │  - fileChanges: Map<path, FileChange>        │ │
│  │  - status: 'idle' | 'planning' | 'executing' │ │
│  └─────────────────────┬────────────────────────┘ │
└────────────────────────┼──────────────────────────┘
                         │ POST /api/ide/composer/chat
                         │ SSE /api/ide/composer/events
                         │ POST /api/ide/composer/accept
┌────────────────────────┼──────────────────────────┐
│        Python likecodex-engine                      │
│  ┌─────────────────────┴────────────────────────┐ │
│  │           ComposerAgent                        │ │
│  │  - 继承现有的 AgentLoop                       │ │
│  │  - 增强：批量文件编辑 + ChangeSet 管理        │ │
│  │  - 计划 → 执行 → Diff 生成 → Results         │ │
│  └──────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

### 3.2 Zustand Store

```typescript
// web/src/stores/composerStore.ts
import { create } from 'zustand';

/** Composer 中的一条消息 */
interface ComposerMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

/** 单个文件的变更 */
interface FileChange {
  /** 文件路径 */
  filePath: string;
  /** 变更类型 */
  changeType: 'create' | 'modify' | 'delete';
  /** 原始内容（用于 Diff） */
  originalContent: string;
  /** 修改后内容 */
  modifiedContent: string;
  /** 是否已被接受 */
  accepted: boolean | null;  // null = 待决定, true = 接受, false = 拒绝
  /** 文件语言 */
  language: string;
}

type ComposerStatus = 'idle' | 'planning' | 'awaiting_approval' | 'executing' | 'done' | 'error';

interface ComposerState {
  // 面板状态
  isOpen: boolean;
  
  // 对话状态
  messages: ComposerMessage[];
  status: ComposerStatus;
  
  // 变更状态
  fileChanges: Map<string, FileChange>;
  
  // 操作
  openComposer: () => void;
  closeComposer: () => void;
  sendMessage: (content: string, mentions: ContextMention[]) => Promise<void>;
  acceptChange: (filePath: string) => void;
  rejectChange: (filePath: string) => void;
  acceptAll: () => Promise<void>;
  rejectAll: () => void;
  clearComposer: () => void;
}

export const useComposerStore = create<ComposerState>((set, get) => ({
  isOpen: false,
  messages: [],
  status: 'idle',
  fileChanges: new Map(),
  
  openComposer: () => set({ isOpen: true }),
  closeComposer: () => set({ isOpen: false }),
  
  sendMessage: async (content, mentions) => {
    const userMessage: ComposerMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    
    set(state => ({
      messages: [...state.messages, userMessage],
      status: 'planning',
    }));
    
    // 连接 SSE 流
    const response = await fetch('/api/ide/composer/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: content,
        mentions: mentions.map(m => ({ id: m.id, type: m.type })),
        sessionId: 'composer-' + Date.now(),
      }),
    });
    
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let assistantContent = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value);
      for (const line of chunk.split('\n').filter(l => l.startsWith('data: '))) {
        const data = JSON.parse(line.slice(6));
        
        switch (data.type) {
          case 'delta':
            assistantContent += data.content;
            break;
            
          case 'plan':
            // AI 列出将修改的文件
            set({ status: 'awaiting_approval' });
            break;
            
          case 'file_change':
            // 收到单个文件的变更
            set(state => {
              const changes = new Map(state.fileChanges);
              changes.set(data.filePath, {
                filePath: data.filePath,
                changeType: data.changeType,
                originalContent: data.originalContent,
                modifiedContent: data.modifiedContent,
                accepted: null,
                language: data.language,
              });
              return { fileChanges: changes };
            });
            break;
            
          case 'done':
            set({ status: 'done' });
            set(state => ({
              messages: [...state.messages, {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: assistantContent,
                timestamp: Date.now(),
              }],
            }));
            break;
            
          case 'error':
            set({ status: 'error' });
            break;
        }
      }
    }
  },
  
  acceptChange: (filePath) => {
    set(state => {
      const changes = new Map(state.fileChanges);
      const change = changes.get(filePath);
      if (change) {
        changes.set(filePath, { ...change, accepted: true });
      }
      return { fileChanges: changes };
    });
    
    // 立即写入文件
    const change = get().fileChanges.get(filePath);
    if (change && change.accepted) {
      fetch('/api/ide/fs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: filePath,
          content: change.modifiedContent,
        }),
      });
    }
  },
  
  acceptAll: async () => {
    const { fileChanges } = get();
    for (const [path, change] of fileChanges) {
      if (change.accepted === null) {
        get().acceptChange(path);
      }
    }
  },
  
  rejectAll: () => {
    set(state => {
      const changes = new Map(state.fileChanges);
      for (const [path, change] of changes) {
        changes.set(path, { ...change, accepted: false });
      }
      return { fileChanges: changes };
    });
  },
}));
```

### 3.3 Composer 面板组件

```tsx
// web/src/ide/composer/ComposerPanel.tsx
export function ComposerPanel() {
  const { isOpen, messages, status, fileChanges, acceptChange, rejectChange } = useComposerStore();
  
  if (!isOpen) return null;
  
  return (
    <div className="w-[600px] h-full bg-composer-background border-l border-gray-700 flex flex-col">
      {/* 标题 */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <h2 className="text-sm font-semibold text-white">Composer</h2>
        <span className="text-xs text-gray-400">
          {status === 'planning' && 'AI 正在分析...'}
          {status === 'awaiting_approval' && '等待确认'}
          {status === 'executing' && '正在修改...'}
          {status === 'done' && '修改完成'}
        </span>
      </div>
      
      {/* 消息历史 */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map(msg => (
          <div key={msg.id} className={clsx(
            'p-2 rounded-lg text-sm',
            msg.role === 'user' ? 'bg-blue-900 bg-opacity-30 ml-8' : 'bg-gray-800 mr-8'
          )}>
            {msg.content}
          </div>
        ))}
        
        {/* 变更预览 */}
        {fileChanges.size > 0 && (
          <div className="border border-gray-700 rounded-lg overflow-hidden">
            {/* 文件标签 */}
            <div className="flex border-b border-gray-700 overflow-x-auto">
              {Array.from(fileChanges.entries()).map(([path, change]) => (
                <div
                  key={path}
                  className={clsx(
                    'px-3 py-1.5 text-xs cursor-pointer border-r border-gray-700 whitespace-nowrap',
                    change.accepted === true && 'bg-green-900 bg-opacity-30',
                    change.accepted === false && 'bg-red-900 bg-opacity-30 opacity-50',
                  )}
                >
                  {change.changeType === 'create' ? '+' : change.changeType === 'delete' ? '-' : '~'}
                  {' '}{path.split('/').pop()}
                </div>
              ))}
            </div>
            
            {/* Diff 内容 */}
            <div className="h-[300px]">
              {Array.from(fileChanges.values()).filter(c => c.accepted === null).slice(0, 1).map(change => (
                <DiffViewer
                  key={change.filePath}
                  original={change.originalContent}
                  modified={change.modifiedContent}
                  language={change.language}
                  originalLabel="原始"
                  modifiedLabel="修改后"
                />
              ))}
            </div>
            
            {/* 操作按钮 */}
            <div className="flex items-center justify-between px-3 py-2 border-t border-gray-700">
              <div className="flex gap-2">
                <button
                  onClick={() => acceptAll()}
                  className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
                >
                  全部接受
                </button>
                <button
                  onClick={() => rejectAll()}
                  className="px-3 py-1 bg-gray-600 text-white text-xs rounded hover:bg-gray-700"
                >
                  全部拒绝
                </button>
              </div>
              <span className="text-xs text-gray-500">
                {Array.from(fileChanges.values()).filter(c => c.accepted === true).length} / {fileChanges.size} 已接受
              </span>
            </div>
          </div>
        )}
      </div>
      
      {/* 输入区域 */}
      <ComposerInput />
    </div>
  );
}
```

### 3.4 Python Composer Agent

**新增文件**: `packages/likecodex-engine/likecodex_engine/composer/agent.py`

```python
"""Composer Agent - 多文件 AI 编辑代理"""
from dataclasses import dataclass, field
from typing import AsyncGenerator

@dataclass
class FileChange:
    file_path: str
    change_type: str  # 'create' | 'modify' | 'delete'
    original_content: str = ""
    modified_content: str = ""
    language: str = ""

class ComposerAgent:
    """多文件编辑代理，继承现有 Agent 的能力"""
    
    def __init__(self, engine):
        self.agent_loop = engine.create_agent_loop()
        self.file_service = engine.file_service
        self.change_set: list[FileChange] = []
        
    async def execute(
        self,
        message: str,
        mentions: list[dict],
        session_id: str,
    ) -> AsyncGenerator[dict, None]:
        """
        执行 Composer 任务
        
        生成的事件:
        - delta: AI 流式回复
        - plan: 修改计划
        - file_change: 单个文件变更
        - done: 完成
        - error: 错误
        """
        # Phase 1: 分析需求
        yield {"type": "delta", "content": "正在分析需求..."}
        
        # 收集上下文（提及的文件 + 自动检测）
        context_files = await self._collect_context(mentions)
        
        # Phase 2: Agent 执行
        task = f"""
用户需求: {message}

相关文件:
{self._format_context_files(context_files)}

请完成以下步骤：
1. 分析需要修改哪些文件
2. 读取所有相关文件
3. 制定修改计划
4. 执行修改（使用 edit_file 或 write_file 工具）
5. 验证修改结果

每次修改后，请返回完整的文件内容。
"""
        
        # 使用现有 Agent 循环执行
        async for event in self.agent_loop.run(task, session_id=session_id):
            if event.type == "plan":
                yield {"type": "plan", "content": event.plan}
            
            elif event.type == "tool_call" and event.tool_name in ("write_file", "edit_file"):
                # 捕获文件变更
                change = await self._capture_change(
                    event.args["path"],
                    event.args.get("content", ""),
                )
                if change:
                    self.change_set.append(change)
                    yield {"type": "file_change", **change.__dict__}
            
            elif event.type == "delta":
                yield {"type": "delta", "content": event.content}
        
        yield {"type": "done"}
    
    async def _capture_change(self, file_path: str, new_content: str) -> FileChange | None:
        """捕获文件变更，读取原始内容用于 Diff"""
        try:
            original = await self.file_service.read(file_path)
            if original != new_content:
                return FileChange(
                    file_path=file_path,
                    change_type="modify" if original else "create",
                    original_content=original or "",
                    modified_content=new_content,
                    language=self._detect_language(file_path),
                )
        except FileNotFoundError:
            return FileChange(
                file_path=file_path,
                change_type="create",
                original_content="",
                modified_content=new_content,
                language=self._detect_language(file_path),
            )
        return None
```

### 3.5 Composer API 路由

```python
# 在 likecodex_engine/server.py 中添加

@routes.post('/api/ide/composer/chat')
async def handle_composer_chat(request):
    """Composer 多文件编辑"""
    data = await request.json()
    agent = ComposerAgent(request.app['engine'])
    
    response = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        },
    )
    await response.prepare(request)
    
    async for event in agent.execute(
        message=data['message'],
        mentions=data.get('mentions', []),
        session_id=data.get('sessionId', 'composer-' + str(uuid.uuid4())),
    ):
        await response.write(f"data: {json.dumps(event)}\n\n".encode())
    
    await response.write(b"data: [DONE]\n\n")
    return response
```

---

## 四、实现步骤

### 4.1 Phase 1：Composer UI 基础（第 1 周）

1. 创建 `composerStore`（Zustand）
2. 实现 `ComposerPanel` 组件（布局 + 消息历史 + 输入区域）
3. 实现 `ComposerInput` 组件（集成 @ 引用系统）
4. 实现 SSE 流式接收 AI 回复
5. 注册快捷键 Cmd+I 打开/关闭 Composer

### 4.2 Phase 2：变更管理（第 2 周）

1. Python 端 `ComposerAgent` 实现（继承 AgentLoop）
2. 实现文件变更捕获（write_file/edit_file 钩子）
3. 实现变更列表展示（文件标签 + Diff 预览）
4. 实现单个文件接受/拒绝
5. 实现全部接受/全部拒绝
6. 接受后自动写入文件

### 4.3 Phase 3：高级功能（第 3 周）

1. 实现修改前自动 Git checkpoint
2. 实现 Composer 模式切换（Normal/Agent）
3. 实现 AI 自动依赖安装（检测 package.json 变更 → 自动 `npm install`）
4. 实现取消/回滚功能
5. 性能优化：大项目的上下文窗口管理

---

## 五、键盘快捷键

| 快捷键 | 功能 | 阶段 |
|--------|------|------|
| `Cmd+I` | 打开/关闭 Composer | P1 |
| `Cmd+Enter` | 发送 Composer 消息 | P1 |
| `Cmd+Backspace` | 清除 Composer | P2 |
| `Cmd+Shift+A` | 接受所有变更 | P2 |

---

## 六、验收标准

| 验收项 | 通过条件 |
|--------|----------|
| 打开 Composer | Cmd+I 打开面板，延迟 < 200ms |
| 多文件编辑 | "添加用户认证"能修改 3+ 文件 |
| 变更预览 | 每个文件展示 Diff，行级高亮正确 |
| 接受/拒绝 | 单个接受正常写入，全部接受批量写入 |
| 多轮对话 | 在 Composer 中连续对话，AI 能记住上下文 |
| 文件创建 | AI 可以创建新文件并在 Diff 中展示 |
| 检查点 | 每次 Composer 前自动创建 Git checkpoint |
