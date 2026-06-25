/**
 * Internationalization (i18n) utilities for LikeCodex
 * Lightweight i18n without external dependencies
 */

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────
export type Locale = 'en' | 'zh' | 'ja';

export interface TranslationKey {
  [key: string]: string | TranslationKey;
}

// ─────────────────────────────────────────────
// Translation dictionaries
// ─────────────────────────────────────────────
const en: TranslationKey = {
  'app.title': 'LikeCodex',
  'app.tagline': 'AI-Powered Coding Agent',
  'mode.ask': 'Ask',
  'mode.agent': 'Agent',
  'mode.manual': 'Manual',
  'mode.ask.desc': 'Read-only Q&A',
  'mode.agent.desc': 'Auto-execute tasks',
  'mode.manual.desc': 'Step-by-step confirmation',
  'input.placeholder': 'Ask anything, or @mention files...',
  'input.send': 'Send',
  'input.stop': 'Stop',
  'input.attach': 'Attach file',
  'chat.empty': 'Start a conversation with AI',
  'chat.thinking': 'Thinking...',
  'chat.generating': 'Generating response...',
  'chat.copy': 'Copy',
  'chat.copyDone': 'Copied!',
  'chat.regenerate': 'Regenerate',
  'chat.clear': 'Clear chat',
  'sidebar.explorer': 'Explorer',
  'sidebar.search': 'Search',
  'sidebar.git': 'Source Control',
  'sidebar.debug': 'Debug',
  'sidebar.extensions': 'Extensions',
  'command.placeholder': 'Type a command...',
  'shortcuts.title': 'Keyboard Shortcuts',
  'shortcuts.search': 'Search shortcuts...',
  'shortcuts.all': 'All',
  'shortcuts.navigation': 'Navigation',
  'shortcuts.editing': 'Editing',
  'shortcuts.agent': 'Agent',
  'shortcuts.view': 'View',
  'shortcuts.system': 'System',
  'welcome.title': 'Welcome to LikeCodex',
  'welcome.subtitle': 'AI-powered coding assistant for faster development',
  'welcome.startTour': 'Start Tour',
  'welcome.dismiss': 'Explore later',
  'tour.step1': 'Welcome to LikeCodex',
  'tour.step2': 'Three Agent Modes',
  'tour.step3': '@ Mention System',
  'tour.step4': 'Keyboard Shortcuts',
  'tour.step5': 'Start Your Journey',
  'tour.next': 'Next',
  'tour.prev': 'Previous',
  'tour.skip': 'Skip',
  'tour.complete': 'Get Started',
  'common.cancel': 'Cancel',
  'common.confirm': 'Confirm',
  'common.save': 'Save',
  'common.delete': 'Delete',
  'common.close': 'Close',
  'common.loading': 'Loading...',
  'common.error': 'Something went wrong',
  'common.retry': 'Retry',
  'common.results': 'results',
  'common.noResults': 'No results found',
  'status.connected': 'Connected',
  'status.disconnected': 'Disconnected',
  'status.connecting': 'Connecting...',
  'permission.title': 'Permission Request',
  'permission.allow': 'Allow',
  'permission.deny': 'Deny',
  'permission.alwaysAllow': 'Always allow',
  'tool.read_file': 'Read File',
  'tool.write_file': 'Write File',
  'tool.edit_file': 'Edit File',
  'tool.run_command': 'Run Command',
  'tool.grep_search': 'Search',
  'tool.list_dir': 'List Directory',
};

const zh: TranslationKey = {
  'app.title': 'LikeCodex',
  'app.tagline': 'AI 驱动的编码助手',
  'mode.ask': '问答',
  'mode.agent': '代理',
  'mode.manual': '手动',
  'mode.ask.desc': '只读问答',
  'mode.agent.desc': '自动执行任务',
  'mode.manual.desc': '逐步确认',
  'input.placeholder': '输入问题，或 @提及文件...',
  'input.send': '发送',
  'input.stop': '停止',
  'input.attach': '附加文件',
  'chat.empty': '开始与 AI 对话',
  'chat.thinking': '思考中...',
  'chat.generating': '正在生成回复...',
  'chat.copy': '复制',
  'chat.copyDone': '已复制！',
  'chat.regenerate': '重新生成',
  'chat.clear': '清空对话',
  'sidebar.explorer': '资源管理器',
  'sidebar.search': '搜索',
  'sidebar.git': '版本控制',
  'sidebar.debug': '调试',
  'sidebar.extensions': '扩展',
  'command.placeholder': '输入命令...',
  'shortcuts.title': '键盘快捷键',
  'shortcuts.search': '搜索快捷键...',
  'shortcuts.all': '全部',
  'shortcuts.navigation': '导航',
  'shortcuts.editing': '编辑',
  'shortcuts.agent': 'Agent',
  'shortcuts.view': '视图',
  'shortcuts.system': '系统',
  'welcome.title': '欢迎使用 LikeCodex',
  'welcome.subtitle': 'AI 驱动的编码助手，让开发更高效',
  'welcome.startTour': '开始引导',
  'welcome.dismiss': '稍后探索',
  'tour.step1': '欢迎使用 LikeCodex',
  'tour.step2': '三种 Agent 模式',
  'tour.step3': '@ 提及系统',
  'tour.step4': '快捷键',
  'tour.step5': '开始你的旅程',
  'tour.next': '下一步',
  'tour.prev': '上一步',
  'tour.skip': '跳过',
  'tour.complete': '开始使用',
  'common.cancel': '取消',
  'common.confirm': '确认',
  'common.save': '保存',
  'common.delete': '删除',
  'common.close': '关闭',
  'common.loading': '加载中...',
  'common.error': '出错了',
  'common.retry': '重试',
  'common.results': '个结果',
  'common.noResults': '未找到结果',
  'status.connected': '已连接',
  'status.disconnected': '已断开',
  'status.connecting': '连接中...',
  'permission.title': '权限请求',
  'permission.allow': '允许',
  'permission.deny': '拒绝',
  'permission.alwaysAllow': '始终允许',
  'tool.read_file': '读取文件',
  'tool.write_file': '写入文件',
  'tool.edit_file': '编辑文件',
  'tool.run_command': '执行命令',
  'tool.grep_search': '搜索',
  'tool.list_dir': '列出目录',
};

const ja: TranslationKey = {
  'app.title': 'LikeCodex',
  'app.tagline': 'AI搭載コーディングアシスタント',
  'mode.ask': '質問',
  'mode.agent': 'エージェント',
  'mode.manual': '手動',
  'mode.ask.desc': '読み取り専用Q&A',
  'mode.agent.desc': 'タスク自動実行',
  'mode.manual.desc': 'ステップ確認',
  'input.placeholder': '質問を入力、または @ファイル...',
  'input.send': '送信',
  'input.stop': '停止',
  'input.attach': 'ファイル添付',
  'chat.empty': 'AIとの会話を開始',
  'chat.thinking': '考え中...',
  'chat.generating': '応答を生成中...',
  'chat.copy': 'コピー',
  'chat.copyDone': 'コピー済み！',
  'chat.regenerate': '再生成',
  'chat.clear': 'チャットをクリア',
  'sidebar.explorer': 'エクスプローラー',
  'sidebar.search': '検索',
  'sidebar.git': 'ソース管理',
  'sidebar.debug': 'デバッグ',
  'sidebar.extensions': '拡張機能',
  'command.placeholder': 'コマンドを入力...',
  'shortcuts.title': 'キーボードショートカット',
  'shortcuts.search': 'ショートカットを検索...',
  'shortcuts.all': 'すべて',
  'shortcuts.navigation': 'ナビゲーション',
  'shortcuts.editing': '編集',
  'shortcuts.agent': 'エージェント',
  'shortcuts.view': '表示',
  'shortcuts.system': 'システム',
  'common.cancel': 'キャンセル',
  'common.confirm': '確認',
  'common.save': '保存',
  'common.close': '閉じる',
  'common.loading': '読み込み中...',
  'common.error': 'エラーが発生しました',
  'common.retry': '再試行',
};

// ─────────────────────────────────────────────
// Dictionary map
// ─────────────────────────────────────────────
const DICT: Record<Locale, TranslationKey> = { en, zh, ja };

// ─────────────────────────────────────────────
// i18n manager (singleton)
// ─────────────────────────────────────────────
class I18nManager {
  private locale: Locale = 'zh';
  private listeners: Set<() => void> = new Set();

  constructor() {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('likecodex_locale') as Locale | null;
      const browser = navigator.language.startsWith('zh') ? 'zh' :
                       navigator.language.startsWith('ja') ? 'ja' : 'en';
      this.locale = saved || (browser as Locale);
    }
  }

  getLocale(): Locale { return this.locale; }

  setLocale(locale: Locale) {
    this.locale = locale;
    if (typeof window !== 'undefined') {
      localStorage.setItem('likecodex_locale', locale);
    }
    this.listeners.forEach(fn => fn());
  }

  t(key: string): string {
    const dict = DICT[this.locale];
    const val = dict[key] ?? DICT.en[key] ?? key;
    return typeof val === 'string' ? val : key;
  }

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
}

const i18n = new I18nManager();

export default i18n;
export { i18n };
