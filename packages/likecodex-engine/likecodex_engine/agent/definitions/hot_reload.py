"""File watcher for hot-reloading agent definitions and rules."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class FileChangeEvent:
    """Event emitted when a watched file changes."""

    file_path: str
    change_type: str  # modified, created, deleted
    timestamp: float = 0.0


class HotReloadWatcher:
    """Watches files/directories for changes and triggers reload callbacks.

    Uses polling-based file monitoring to detect modifications.
    Designed for development workflows where configuration files
    (AGENTS.md, rules/*.yaml) may change at runtime.

    Usage::

        watcher = HotReloadWatcher()
        watcher.watch("AGENTS.md", callback=on_agents_change)
        watcher.watch_directory(".likecodex/rules/", callback=on_rules_change)
        watcher.start()
        # ...
        watcher.stop()
    """

    def __init__(self, poll_interval: float = 2.0) -> None:
        self.poll_interval = poll_interval
        self._watched_files: dict[str, tuple[float, Callable[[FileChangeEvent], None]]] = {}
        self._watched_dirs: dict[str, tuple[set[str], Callable[[FileChangeEvent], None]]] = {}
        self._thread: Thread | None = None
        self._running: bool = False

    def watch(
        self,
        file_path: str,
        callback: Callable[[FileChangeEvent], None],
    ) -> None:
        """Watch a single file for changes."""
        abs_path = str(Path(file_path).resolve())
        if os.path.isfile(abs_path):
            mtime = os.path.getmtime(abs_path)
        else:
            mtime = time.time()
        self._watched_files[abs_path] = (mtime, callback)
        logger.debug("Watching file: %s", abs_path)

    def watch_directory(
        self,
        dir_path: str,
        callback: Callable[[FileChangeEvent], None],
        pattern: str | None = None,
    ) -> None:
        """Watch a directory for file changes.

        Args:
            dir_path: Directory path to watch.
            callback: Function to call on changes.
            pattern: Optional glob pattern to filter files (e.g., '*.yaml').
        """
        abs_path = str(Path(dir_path).resolve())
        if not os.path.isdir(abs_path):
            logger.warning("Directory does not exist, will watch when created: %s", abs_path)
        self._watched_dirs[abs_path] = (set(), callback)
        logger.debug("Watching directory: %s", abs_path)

    def start(self) -> None:
        """Start the file watcher in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = Thread(target=self._poll_loop, daemon=True, name="hot-reload-watcher")
        self._thread.start()
        logger.info("Hot reload watcher started (interval=%ss)", self.poll_interval)

    def stop(self) -> None:
        """Stop the file watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Hot reload watcher stopped.")

    def unwatch(self, file_path: str) -> None:
        """Stop watching a specific file."""
        abs_path = str(Path(file_path).resolve())
        self._watched_files.pop(abs_path, None)
        self._watched_dirs.pop(abs_path, None)

    def clear_all(self) -> None:
        """Remove all watched files and directories."""
        self._watched_files.clear()
        self._watched_dirs.clear()

    def _poll_loop(self) -> None:
        """Main polling loop running in background thread."""
        while self._running:
            try:
                self._check_files()
                self._check_directories()
            except Exception as exc:
                logger.error("Error in hot reload poll loop: %s", exc)
            time.sleep(self.poll_interval)

    def _check_files(self) -> None:
        """Check all watched files for modifications."""
        now = time.time()
        for file_path, (last_mtime, callback) in list(self._watched_files.items()):
            try:
                if not os.path.isfile(file_path):
                    continue
                current_mtime = os.path.getmtime(file_path)
                if current_mtime > last_mtime:
                    self._watched_files[file_path] = (current_mtime, callback)
                    event = FileChangeEvent(
                        file_path=file_path,
                        change_type="modified",
                        timestamp=now,
                    )
                    try:
                        callback(event)
                    except Exception as exc:
                        logger.error("Error in reload callback for %s: %s", file_path, exc)
            except OSError as exc:
                logger.debug("Error checking file %s: %s", file_path, exc)

    def _check_directories(self) -> None:
        """Check all watched directories for new/deleted/modified files."""
        now = time.time()
        for dir_path, (known_files, callback) in list(self._watched_dirs.items()):
            try:
                if not os.path.isdir(dir_path):
                    continue

                # Scan current files
                current_files: set[str] = set()
                for entry in os.scandir(dir_path):
                    if entry.is_file():
                        current_files.add(entry.name)

                # Detect new files
                new_files = current_files - known_files
                for fname in new_files:
                    event = FileChangeEvent(
                        file_path=os.path.join(dir_path, fname),
                        change_type="created",
                        timestamp=now,
                    )
                    try:
                        callback(event)
                    except Exception as exc:
                        logger.error("Error in reload callback for %s: %s", fname, exc)

                # Detect deleted files
                deleted_files = known_files - current_files
                for fname in deleted_files:
                    event = FileChangeEvent(
                        file_path=os.path.join(dir_path, fname),
                        change_type="deleted",
                        timestamp=now,
                    )
                    try:
                        callback(event)
                    except Exception as exc:
                        logger.error("Error in reload callback for %s: %s", fname, exc)

                self._watched_dirs[dir_path] = (current_files, callback)
            except OSError as exc:
                logger.debug("Error checking directory %s: %s", dir_path, exc)

    @property
    def is_running(self) -> bool:
        return self._running
