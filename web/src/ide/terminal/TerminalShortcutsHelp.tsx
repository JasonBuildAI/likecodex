'use client';

/**
 * TerminalShortcutsHelp — Keyboard shortcuts reference overlay for terminal.
 *
 * Displays a modal with all available keyboard shortcuts and their descriptions.
 * Triggered by Ctrl+Shift+? or a help button in the terminal.
 */

interface ShortcutGroup {
  title: string;
  shortcuts: { keys: string; description: string }[];
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: '命令输入',
    shortcuts: [
      { keys: 'Enter', description: '执行当前命令' },
      { keys: '↑ / ↓', description: '浏览命令历史' },
      { keys: 'Tab', description: '自动补全命令/路径' },
      { keys: 'Ctrl+R', description: '反向搜索命令历史' },
      { keys: 'Ctrl+K', description: 'AI 命令建议' },
      { keys: 'Esc', description: '关闭补全/搜索' },
      { keys: 'Ctrl+C', description: '中断当前命令' },
    ],
  },
  {
    title: '会话管理',
    shortcuts: [
      { keys: 'Ctrl+Shift+T', description: '新建终端标签' },
      { keys: 'Ctrl+Shift+W', description: '关闭当前终端' },
      { keys: 'Ctrl+Tab', description: '切换终端标签' },
      { keys: 'Ctrl+Shift+Tab', description: '切换上一个终端标签' },
    ],
  },
  {
    title: 'AI 功能',
    shortcuts: [
      { keys: 'Ctrl+K', description: '打开 AI 命令建议' },
      { keys: 'Ctrl+Shift+K', description: 'AI 错误诊断' },
    ],
  },
  {
    title: '视图控制',
    shortcuts: [
      { keys: 'Ctrl+L', description: '清屏' },
      { keys: 'Ctrl+Shift+?', description: '显示此帮助面板' },
      { keys: 'Ctrl+Shift+F', description: '在终端输出中搜索' },
    ],
  },
];

export function TerminalShortcutsHelp({
  onClose,
}: {
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-[#1e1e2e] border border-gray-700 rounded-lg shadow-2xl w-[480px] max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <h2 className="text-sm font-semibold text-gray-200">终端快捷键</h2>
          <button
            onClick={onClose}
            className="text-xs text-gray-500 hover:text-white px-2 py-1 rounded hover:bg-gray-700"
          >
            ✕ 关闭 (Esc)
          </button>
        </div>

        {/* Shortcuts */}
        <div className="p-4 space-y-4">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title}>
              <h3 className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mb-2">
                {group.title}
              </h3>
              <div className="space-y-1">
                {group.shortcuts.map((shortcut) => (
                  <div
                    key={shortcut.keys}
                    className="flex items-center justify-between py-1 px-2 rounded hover:bg-gray-800/50"
                  >
                    <span className="text-xs text-gray-300">{shortcut.description}</span>
                    <kbd className="text-[10px] font-mono bg-gray-800 text-gray-200 px-2 py-0.5 rounded border border-gray-600 ml-2 shrink-0">
                      {shortcut.keys}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-gray-700 text-[10px] text-gray-500">
          按 <kbd className="bg-gray-800 px-1 rounded border border-gray-600">Esc</kbd> 关闭此面板
        </div>
      </div>
    </div>
  );
}
