/** Settings type definitions */

export type SettingType = 'string' | 'number' | 'boolean' | 'select' | 'array' | 'object';

export interface SettingDefinition {
  id: string;
  label: string;
  description: string;
  type: SettingType;
  default: unknown;
  value: unknown;
  options?: string[];
}

export interface SettingsCategory {
  id: string;
  label: string;
  settings: SettingDefinition[];
}

export interface Keybinding {
  id: string;
  command: string;
  label: string;
  keys: string[];
  when: string;
}

export interface KeybindingConflict {
  keys: string;
  bindings: Keybinding[];
}
