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
