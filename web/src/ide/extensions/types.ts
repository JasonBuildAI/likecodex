/** Extension system type definitions */

export interface CommandDefinition {
  id: string;
  label: string;
  keybindings?: string[];
  description?: string;
  icon?: string;
  category?: string;
}

export interface ViewDefinition {
  id: string;
  label: string;
  icon: string;
  location: 'sidebar' | 'panel' | 'activitybar';
}

export interface ThemeDefinition {
  id: string;
  label: string;
  base: 'dark' | 'light';
  colors: Record<string, string>;
}

export interface MenuContribution {
  id: string;
  label: string;
  location: string;
  order?: number;
}

export interface KeybindingOverride {
  command: string;
  keys: string[];
  when?: string;
}

/** Manages contribution points from an extension */
export interface ExtensionContribution {
  commands?: CommandDefinition[];
  keybindings?: KeybindingOverride[];
  themes?: ThemeDefinition[];
  views?: ViewDefinition[];
  menus?: MenuContribution[];
}

/** Lifecycle hooks for an extension */
export interface ExtensionLifecycleHooks {
  onInstall?: () => Promise<void>;
  onUninstall?: () => Promise<void>;
  onEnable?: () => Promise<void>;
  onDisable?: () => Promise<void>;
  onConfigChange?: (key: string, value: unknown) => Promise<void>;
}

/** The full manifest for an extension plugin */
export interface ExtensionManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  license?: string;
  enabled: boolean;
  installed?: boolean;
  installPath?: string;
  contributed?: ExtensionContribution;
  main: string;
  icon?: string;
  /** Minimum engine version required */
  engineVersion?: string;
  /** List of extension IDs this depends on */
  dependencies?: string[];
  /** URLs */
  repository?: string;
  homepage?: string;
  bugs?: string;
  /** Lifecycle scripts (file paths in the extension dir) */
  scripts?: {
    install?: string;
    uninstall?: string;
  };
}

export interface ExtensionActivationResult {
  activate?: () => Record<string, (...args: unknown[]) => unknown>;
  deactivate?: () => void;
}

/** Status of an extension in its lifecycle */
export type ExtensionStatus =
  | 'installed'
  | 'enabled'
  | 'disabled'
  | 'activating'
  | 'active'
  | 'deactivating'
  | 'error';

/** Full extension info with runtime state */
export interface ExtensionInfo {
  manifest: ExtensionManifest;
  status: ExtensionStatus;
  activationResult?: ExtensionActivationResult;
  error?: string;
  installedAt?: number;
  updatedAt?: number;
}
/** Extension system type definitions */

export interface CommandDefinition {
  id: string;
  label: string;
  keybindings?: string[];
  description?: string;
}

export interface ViewDefinition {
  id: string;
  label: string;
  icon: string;
  location: 'sidebar' | 'panel' | 'activitybar';
}

export interface ThemeDefinition {
  id: string;
  label: string;
  base: 'dark' | 'light';
  colors: Record<string, string>;
}

export interface MenuContribution {
  id: string;
  label: string;
  location: string;
  order?: number;
}

export interface KeybindingOverride {
  command: string;
  keys: string[];
  when?: string;
}

export interface ExtensionManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  enabled: boolean;
  contributes: {
    commands?: CommandDefinition[];
    keybindings?: KeybindingOverride[];
    themes?: ThemeDefinition[];
    views?: ViewDefinition[];
    menus?: MenuContribution[];
  };
  main: string;
  icon?: string;
}

export interface ExtensionActivationResult {
  activate?: () => Record<string, (...args: unknown[]) => unknown>;
  deactivate?: () => void;
}
