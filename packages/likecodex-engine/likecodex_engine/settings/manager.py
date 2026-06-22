"""SettingsManager — Read/write IDE settings from .likecodex/config.toml."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class SettingsManager:
    """Manage IDE settings with schema-driven defaults."""

    SETTINGS_SCHEMA: dict[str, dict[str, Any]] = {
        "editor.fontSize": {"type": "number", "default": 14, "category": "editor", "label": "Font Size", "description": "Editor font size in pixels"},
        "editor.tabSize": {"type": "number", "default": 2, "category": "editor", "label": "Tab Size", "description": "Number of spaces per tab"},
        "editor.autoSave": {"type": "boolean", "default": True, "category": "editor", "label": "Auto Save", "description": "Automatically save files"},
        "editor.wordWrap": {"type": "boolean", "default": False, "category": "editor", "label": "Word Wrap", "description": "Wrap long lines"},
        "editor.minimap": {"type": "boolean", "default": True, "category": "editor", "label": "Minimap", "description": "Show code minimap"},
        "editor.formatOnSave": {"type": "boolean", "default": False, "category": "editor", "label": "Format On Save", "description": "Format code when saving"},
        "terminal.fontSize": {"type": "number", "default": 13, "category": "terminal", "label": "Terminal Font Size", "description": "Terminal font size in pixels"},
        "terminal.defaultShell": {"type": "string", "default": "", "category": "terminal", "label": "Default Shell", "description": "Override default shell (empty = auto-detect)"},
        "terminal.scrollback": {"type": "number", "default": 10000, "category": "terminal", "label": "Scrollback Lines", "description": "Number of lines to keep in terminal buffer"},
        "ai.provider": {"type": "string", "default": "deepseek", "category": "ai", "label": "AI Provider", "description": "LLM provider name"},
        "ai.model": {"type": "string", "default": "deepseek-v4-flash", "category": "ai", "label": "AI Model", "description": "Model identifier"},
        "ai.approvalMode": {
            "type": "select", "default": "auto",
            "options": ["read-only", "auto", "auto-approve", "full-access", "yolo", "sandbox-required"],
            "category": "ai", "label": "Approval Mode", "description": "How tools are approved",
        },
        "ai.compactRatio": {"type": "number", "default": 0.8, "category": "ai", "label": "Compact Ratio", "description": "Context compaction threshold (0-1)"},
        "ai.autoPlan": {"type": "boolean", "default": True, "category": "ai", "label": "Auto Plan", "description": "Automatically create plans for complex tasks"},
        "ai.temperature": {"type": "number", "default": 0.0, "category": "ai", "label": "Temperature", "description": "LLM sampling temperature (0-2)"},
        "ai.maxTokens": {"type": "number", "default": 8192, "category": "ai", "label": "Max Tokens", "description": "Maximum tokens per response"},
        "git.userName": {"type": "string", "default": "", "category": "git", "label": "Git User Name", "description": "Git commit author name"},
        "git.userEmail": {"type": "string", "default": "", "category": "git", "label": "Git User Email", "description": "Git commit author email"},
        "git.autoStage": {"type": "boolean", "default": False, "category": "git", "label": "Auto Stage", "description": "Automatically stage files before commit"},
        "theme.mode": {"type": "select", "default": "dark", "options": ["dark", "light"], "category": "theme", "label": "Theme Mode", "description": "UI color theme"},
        "theme.accentColor": {"type": "string", "default": "#3b82f6", "category": "theme", "label": "Accent Color", "description": "Primary accent color (hex)"},
    }

    DEFAULT_KEYBINDINGS: list[dict[str, Any]] = [
        {"id": "file.quickOpen", "command": "file.quickOpen", "label": "Quick Open File", "keys": ["Ctrl", "P"], "when": "always"},
        {"id": "file.save", "command": "file.save", "label": "Save File", "keys": ["Ctrl", "S"], "when": "editorFocus"},
        {"id": "ai.inlineEdit", "command": "ai.inlineEdit", "label": "Inline Edit (Ctrl+K)", "keys": ["Ctrl", "K"], "when": "editorFocus"},
        {"id": "composer.toggle", "command": "composer.toggle", "label": "Toggle Composer", "keys": ["Ctrl", "I"], "when": "always"},
        {"id": "terminal.toggle", "command": "terminal.toggle", "label": "Toggle Terminal", "keys": ["Ctrl", "J"], "when": "always"},
        {"id": "palette.open", "command": "palette.open", "label": "Command Palette", "keys": ["Ctrl", "Shift", "P"], "when": "always"},
        {"id": "sidebar.toggle", "command": "sidebar.toggle", "label": "Toggle Sidebar", "keys": ["Ctrl", "B"], "when": "always"},
        {"id": "debug.start", "command": "debug.start", "label": "Start Debugging", "keys": ["F5"], "when": "always"},
        {"id": "debug.stepOver", "command": "debug.stepOver", "label": "Step Over", "keys": ["F10"], "when": "debugging"},
        {"id": "debug.stepInto", "command": "debug.stepInto", "label": "Step Into", "keys": ["F11"], "when": "debugging"},
        {"id": "debug.stepOut", "command": "debug.stepOut", "label": "Step Out", "keys": ["Shift", "F11"], "when": "debugging"},
        {"id": "debug.stop", "command": "debug.stop", "label": "Stop Debugging", "keys": ["Shift", "F5"], "when": "debugging"},
        {"id": "git.open", "command": "git.open", "label": "Open Git Panel", "keys": ["Ctrl", "Shift", "G"], "when": "always"},
        {"id": "search.global", "command": "search.global", "label": "Global Search", "keys": ["Ctrl", "Shift", "F"], "when": "always"},
        {"id": "session.new", "command": "session.new", "label": "New Session", "keys": ["Ctrl", "N"], "when": "always"},
    ]

    def __init__(self, working_dir: str = ".") -> None:
        self.working_dir = Path(working_dir).resolve()
        self.config_dir = self.working_dir / ".likecodex"
        self.settings_file = self.config_dir / "ide_settings.json"
        self.keybindings_file = self.config_dir / "keybindings.json"
        self._settings: dict[str, Any] = {}
        self._keybindings: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load settings from disk, falling back to defaults."""
        # Load settings
        if self.settings_file.exists():
            try:
                self._settings = json.loads(self.settings_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._settings = {}
        else:
            self._settings = {}

        # Load keybindings
        if self.keybindings_file.exists():
            try:
                self._keybindings = json.loads(self.keybindings_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._keybindings = list(self.DEFAULT_KEYBINDINGS)
        else:
            self._keybindings = list(self.DEFAULT_KEYBINDINGS)

    def _save(self) -> None:
        """Persist settings to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps(self._settings, indent=2, ensure_ascii=False), encoding="utf-8")
        self.keybindings_file.write_text(json.dumps(self._keybindings, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_all(self) -> dict[str, Any]:
        """Get all settings with defaults applied."""
        result: dict[str, Any] = {}
        for key, schema in self.SETTINGS_SCHEMA.items():
            result[key] = self._settings.get(key, schema["default"])
        return result

    def get(self, key: str) -> Any:
        """Get a single setting value."""
        schema = self.SETTINGS_SCHEMA.get(key)
        if schema is None:
            return self._settings.get(key)
        return self._settings.get(key, schema["default"])

    def set(self, key: str, value: Any) -> None:
        """Set a single setting value and persist."""
        self._settings[key] = value
        self._save()

    def set_many(self, updates: dict[str, Any]) -> None:
        """Set multiple settings at once and persist."""
        self._settings.update(updates)
        self._save()

    def reset(self, key: str) -> None:
        """Reset a setting to its default value."""
        schema = self.SETTINGS_SCHEMA.get(key)
        if schema:
            self._settings.pop(key, None)
            self._save()

    def reset_all(self) -> None:
        """Reset all settings to defaults."""
        self._settings = {}
        self._save()

    def get_categories(self) -> list[dict[str, Any]]:
        """Get settings grouped by category."""
        categories: dict[str, list[dict[str, Any]]] = {}
        for key, schema in self.SETTINGS_SCHEMA.items():
            cat = schema["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                "id": key,
                "label": schema["label"],
                "description": schema["description"],
                "type": schema["type"],
                "default": schema["default"],
                "value": self._settings.get(key, schema["default"]),
                "options": schema.get("options"),
            })
        return [{"id": cat, "label": cat.capitalize(), "settings": items} for cat, items in sorted(categories.items())]

    def get_keybindings(self) -> list[dict[str, Any]]:
        """Get all keybindings."""
        return list(self._keybindings)

    def set_keybinding(self, binding_id: str, keys: list[str]) -> None:
        """Update a keybinding and persist."""
        for kb in self._keybindings:
            if kb["id"] == binding_id:
                kb["keys"] = keys
                self._save()
                return
        # If not found, add it
        self._keybindings.append({"id": binding_id, "command": binding_id, "label": binding_id, "keys": keys, "when": "always"})
        self._save()

    def reset_keybindings(self) -> None:
        """Reset all keybindings to defaults."""
        self._keybindings = list(self.DEFAULT_KEYBINDINGS)
        self._save()

    def check_conflicts(self) -> list[dict[str, Any]]:
        """Check for keybinding conflicts."""
        seen: dict[str, list[dict[str, Any]]] = {}
        for kb in self._keybindings:
            key_str = "+".join(kb["keys"])
            if key_str not in seen:
                seen[key_str] = []
            seen[key_str].append(kb)
        conflicts = []
        for key_str, bindings in seen.items():
            if len(bindings) > 1:
                conflicts.append({"keys": key_str, "bindings": bindings})
        return conflicts
