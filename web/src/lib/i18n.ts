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
  'tool.search_code': 'Search Code',
  'tool.search_memory': 'Search Memory',
  'tool.read_file_window': 'Read File Window',
  'tool.glob': 'Glob Search',
  'tool.grep': 'Grep Search',
  'tool.bash': 'Run Bash',
  'tool.ask_user': 'Ask User',
  'tool.complete_task': 'Complete Task',
  'tool.diagram': 'Generate Diagram',
  'tool.plan': 'Create Plan',

  // Settings panel
  'settings.title': 'Settings',
  'settings.general': 'General',
  'settings.editor': 'Editor',
  'settings.agent': 'Agent',
  'settings.git': 'Git',
  'settings.theme': 'Theme',
  'settings.keybindings': 'Keybindings',
  'settings.mcp': 'MCP',
  'settings.search': 'Search settings...',
  'settings.fontSize': 'Font Size',
  'settings.lineHeight': 'Line Height',
  'settings.accentColor': 'Accent Color',
  'settings.systemTheme': 'System Theme',

  // Composer
  'composer.title': 'Composer',
  'composer.placeholder': 'Describe your changes... (@ to mention files, Cmd+Enter to send)',
  'composer.send': 'Send',
  'composer.stop': 'Stop',
  'composer.clear': 'Clear',
  'composer.acceptAll': 'Accept All',
  'composer.rejectAll': 'Reject All',
  'composer.newSession': 'New Session',
  'composer.contextFiles': 'Context Files',
  'composer.empty': 'Describe the changes you want, AI will edit multiple files.',

  // Git panel
  'git.changes': 'Changes',
  'git.history': 'History',
  'git.branches': 'Branches',
  'git.staged': 'Staged',
  'git.unstaged': 'Unstaged',
  'git.commit': 'Commit',
  'git.commitPlaceholder': 'Commit message (Ctrl+Enter to commit)',
  'git.discard': 'Discard',
  'git.stageAll': 'Stage All',
  'git.unstageAll': 'Unstage All',
  'git.pull': 'Pull',
  'git.push': 'Push',
  'git.fetch': 'Fetch',
  'git.stash': 'Stash',
  'git.newBranch': 'New Branch',
  'git.switchBranch': 'Switch',
  'git.deleteBranch': 'Delete',
  'git.noRepo': 'Not a Git repository',
  'git.noChanges': 'No changes',

  // Search
  'search.title': 'Search',
  'search.placeholder': 'Search file contents...',
  'search.composerPlaceholder': 'Search pending changes...',
  'search.replace': 'Replace',
  'search.replaceWith': 'Replace with...',
  'search.replaceAll': 'Replace All',
  'search.clear': 'Clear',
  'search.noResults': 'No results found',
  'search.history': 'Recent Searches',

  // File tree
  'fileTree.explorer': 'Explorer',
  'fileTree.filter': 'Filter files...',
  'fileTree.newFile': 'New File',
  'fileTree.newFolder': 'New Folder',
  'fileTree.rename': 'Rename',
  'fileTree.delete': 'Delete',
  'fileTree.loading': 'Loading...',
  'fileTree.noWorkspace': 'No workspace found',
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
  'tool.search_code': '搜索代码',
  'tool.search_memory': '搜索记忆',
  'tool.read_file_window': '读取文件窗口',
  'tool.glob': '文件搜索',
  'tool.grep': '正则搜索',
  'tool.bash': '执行命令',
  'tool.ask_user': '询问用户',
  'tool.complete_task': '完成任务',
  'tool.diagram': '生成图表',
  'tool.plan': '创建计划',

  // Settings panel
  'settings.title': '设置',
  'settings.general': '通用',
  'settings.editor': '编辑器',
  'settings.agent': '代理',
  'settings.git': 'Git',
  'settings.theme': '主题',
  'settings.keybindings': '快捷键',
  'settings.mcp': 'MCP',
  'settings.search': '搜索设置...',
  'settings.fontSize': '字体大小',
  'settings.lineHeight': '行高',
  'settings.accentColor': '强调色',
  'settings.systemTheme': '系统主题',

  // Composer
  'composer.title': 'Composer',
  'composer.placeholder': '描述修改需求... (@ 引用文件, Cmd+Enter 发送)',
  'composer.send': '发送',
  'composer.stop': '停止',
  'composer.clear': '清除',
  'composer.acceptAll': '全部接受',
  'composer.rejectAll': '全部拒绝',
  'composer.newSession': '新建会话',
  'composer.contextFiles': '上下文文件',
  'composer.empty': '描述你想要的修改，AI 将自动编辑多个文件。',

  // Git panel
  'git.changes': '变更',
  'git.history': '历史',
  'git.branches': '分支',
  'git.staged': '已暂存',
  'git.unstaged': '未暂存',
  'git.commit': '提交',
  'git.commitPlaceholder': '提交信息 (Ctrl+Enter 提交)',
  'git.discard': '丢弃',
  'git.stageAll': '全部暂存',
  'git.unstageAll': '全部取消暂存',
  'git.pull': '拉取',
  'git.push': '推送',
  'git.fetch': '获取',
  'git.stash': '暂存',
  'git.newBranch': '新建分支',
  'git.switchBranch': '切换',
  'git.deleteBranch': '删除',
  'git.noRepo': '不是 Git 仓库',
  'git.noChanges': '没有变更',

  // Search
  'search.title': '搜索',
  'search.placeholder': '搜索文件内容...',
  'search.composerPlaceholder': '搜索待变更内容...',
  'search.replace': '替换',
  'search.replaceWith': '替换为...',
  'search.replaceAll': '全部替换',
  'search.clear': '清除',
  'search.noResults': '未找到结果',
  'search.history': '最近搜索',

  // File tree
  'fileTree.explorer': '资源管理器',
  'fileTree.filter': '过滤文件...',
  'fileTree.newFile': '新建文件',
  'fileTree.newFolder': '新建文件夹',
  'fileTree.rename': '重命名',
  'fileTree.delete': '删除',
  'fileTree.loading': '加载中...',
  'fileTree.noWorkspace': '未找到工作区',
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
  'common.delete': '削除',
  'common.results': '件の結果',
  'common.noResults': '結果が見つかりません',
  'status.connected': '接続済み',
  'status.disconnected': '切断済み',
  'status.connecting': '接続中...',
  'permission.title': '権限リクエスト',
  'permission.allow': '許可',
  'permission.deny': '拒否',
  'permission.alwaysAllow': '常に許可',
  'tool.read_file': 'ファイルを読む',
  'tool.write_file': 'ファイルに書き込む',
  'tool.edit_file': 'ファイルを編集',
  'tool.run_command': 'コマンド実行',
  'tool.grep_search': '検索',
  'tool.list_dir': 'ディレクトリ一覧',
  'tool.search_code': 'コード検索',
  'tool.search_memory': 'メモリ検索',
  'tool.read_file_window': 'ファイルウィンドウ読み取り',
  'tool.glob': 'ファイル検索',
  'tool.grep': '正規表現検索',
  'tool.bash': 'コマンド実行',
  'tool.ask_user': 'ユーザーに質問',
  'tool.complete_task': 'タスク完了',
  'tool.diagram': '図を生成',
  'tool.plan': '計画を作成',

  // Settings
  'settings.title': '設定',
  'settings.general': '一般',
  'settings.editor': 'エディタ',
  'settings.agent': 'エージェント',
  'settings.git': 'Git',
  'settings.theme': 'テーマ',
  'settings.keybindings': 'ショートカット',
  'settings.mcp': 'MCP',
  'settings.search': '設定を検索...',
  'settings.fontSize': 'フォントサイズ',
  'settings.lineHeight': '行の高さ',
  'settings.accentColor': 'アクセントカラー',
  'settings.systemTheme': 'システムテーマ',

  // Composer
  'composer.title': 'Composer',
  'composer.placeholder': '変更内容を説明... (@ ファイル参照, Cmd+Enter 送信)',
  'composer.send': '送信',
  'composer.stop': '停止',
  'composer.clear': 'クリア',
  'composer.acceptAll': 'すべて承認',
  'composer.rejectAll': 'すべて拒否',
  'composer.newSession': '新規セッション',
  'composer.contextFiles': 'コンテキストファイル',
  'composer.empty': '変更内容を説明してください。AIが複数のファイルを自動編集します。',

  // Git
  'git.changes': '変更',
  'git.history': '履歴',
  'git.branches': 'ブランチ',
  'git.staged': 'ステージ済み',
  'git.unstaged': '未ステージ',
  'git.commit': 'コミット',
  'git.commitPlaceholder': 'コミットメッセージ (Ctrl+Enter コミット)',
  'git.discard': '破棄',
  'git.stageAll': 'すべてステージ',
  'git.unstageAll': 'すべてアンステージ',
  'git.pull': 'プル',
  'git.push': 'プッシュ',
  'git.fetch': 'フェッチ',
  'git.stash': 'スタッシュ',
  'git.newBranch': '新規ブランチ',
  'git.switchBranch': '切り替え',
  'git.deleteBranch': '削除',
  'git.noRepo': 'Gitリポジトリではありません',
  'git.noChanges': '変更はありません',

  // Search
  'search.title': '検索',
  'search.placeholder': 'ファイル内容を検索...',
  'search.composerPlaceholder': '保留中の変更を検索...',
  'search.replace': '置換',
  'search.replaceWith': '置換後...',
  'search.replaceAll': 'すべて置換',
  'search.clear': 'クリア',
  'search.noResults': '結果が見つかりません',
  'search.history': '最近の検索',

  // File tree
  'fileTree.explorer': 'エクスプローラー',
  'fileTree.filter': 'ファイルをフィルター...',
  'fileTree.newFile': '新規ファイル',
  'fileTree.newFolder': '新規フォルダ',
  'fileTree.rename': '名前変更',
  'fileTree.delete': '削除',
  'fileTree.loading': '読み込み中...',
  'fileTree.noWorkspace': 'ワークスペースが見つかりません',
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
