"""Background task execution system.

Allows Agent to run tasks in the background without blocking the main session.
Supports concurrency control, progress tracking, pause/resume, and timeout.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class BackgroundTaskStatus(str, Enum):
    """Status of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundTask:
    """Represents a single background task with its state and metadata."""

    def __init__(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id: str = uuid.uuid4().hex
        self.name: str = name
        self.description: str = description
        self.status: BackgroundTaskStatus = BackgroundTaskStatus.PENDING
        self.created_at: float = time.time()
        self.started_at: float | None = None
        self.completed_at: float | None = None
        self.progress: float = 0.0
        self.result: dict | None = None
        self.error: str | None = None
        self.metadata: dict[str, Any] = metadata or {}

        # Internal control signals
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()
        self._cancelled: bool = False

    def mark_running(self) -> None:
        self.status = BackgroundTaskStatus.RUNNING
        self.started_at = time.time()

    def mark_completed(self, result: dict | None = None) -> None:
        self.status = BackgroundTaskStatus.COMPLETED
        self.completed_at = time.time()
        self.progress = 100.0
        if result is not None:
            self.result = result

    def mark_failed(self, error: str) -> None:
        self.status = BackgroundTaskStatus.FAILED
        self.completed_at = time.time()
        self.error = error

    def mark_cancelled(self) -> None:
        self.status = BackgroundTaskStatus.CANCELLED
        self.completed_at = time.time()
        self._cancelled = True

    def update_progress(self, value: float) -> None:
        self.progress = max(0.0, min(100.0, value))

    def pause(self) -> None:
        if self.status == BackgroundTaskStatus.RUNNING:
            self.status = BackgroundTaskStatus.PAUSED
            self._pause_event.clear()

    def resume(self) -> None:
        if self.status == BackgroundTaskStatus.PAUSED:
            self.status = BackgroundTaskStatus.RUNNING
            self._pause_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class BackgroundTaskManager:
    """Manages background task lifecycle with concurrency control.

    Uses asyncio primitives for true async execution and thread-safe state.
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._max_concurrent: int = max(1, max_concurrent)
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(self._max_concurrent)
        self._lock: asyncio.Lock = asyncio.Lock()
        logger.info(
            "BackgroundTaskManager initialized with max_concurrent=%d",
            self._max_concurrent,
        )

    async def start_task(
        self,
        name: str,
        description: str,
        coro_func: Callable[..., Any],
        *args: Any,
        timeout: float | None = None,
        progress_callback: Callable[[float], None] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Start a background task and return its task_id.

        The coro_func will be executed asynchronously with concurrency control.
        """
        task = BackgroundTask(
            name=name,
            description=description,
            metadata=metadata,
        )

        async with self._lock:
            self._tasks[task.id] = task

        async def _wrapped() -> None:
            task.mark_running()
            try:
                async with self._semaphore:
                    if task.is_cancelled:
                        task.mark_cancelled()
                        return

                    def _progress(value: float) -> None:
                        task.update_progress(value)
                        if progress_callback:
                            try:
                                progress_callback(value)
                            except Exception:
                                logger.warning(
                                    "progress_callback failed for task %s",
                                    task.id,
                                    exc_info=True,
                                )

                    if timeout is not None and timeout > 0:
                        try:
                            result = await asyncio.wait_for(
                                coro_func(*args, **kwargs, progress_callback=_progress),
                                timeout=timeout,
                            )
                        except asyncio.TimeoutError:
                            task.mark_failed(f"Task timed out after {timeout}s")
                            logger.warning(
                                "Task %s (%s) timed out after %ss",
                                task.id, name, timeout,
                            )
                            return
                    else:
                        result = await coro_func(
                            *args, **kwargs, progress_callback=_progress,
                        )

                    if task.is_cancelled:
                        task.mark_cancelled()
                    else:
                        task.mark_completed(
                            result if isinstance(result, dict) else {"result": str(result)},
                        )

            except asyncio.CancelledError:
                task.mark_cancelled()
                logger.info("Task %s (%s) was cancelled", task.id, name)
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                task.mark_failed(error_msg)
                logger.error(
                    "Task %s (%s) failed: %s",
                    task.id, name, error_msg,
                    exc_info=True,
                )
            finally:
                async with self._lock:
                    self._running_tasks.pop(task.id, None)

        asyncio_task = asyncio.create_task(_wrapped(), name=f"bg-{task.id[:8]}")
        async with self._lock:
            self._running_tasks[task.id] = asyncio_task

        logger.info("Started background task %s: %s", task.id, name)
        return task.id

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or pending task. Returns True if cancelled."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                logger.warning("Attempted to cancel unknown task %s", task_id)
                return False

            if task.status in (
                BackgroundTaskStatus.COMPLETED,
                BackgroundTaskStatus.FAILED,
                BackgroundTaskStatus.CANCELLED,
            ):
                return False

            task.mark_cancelled()

            running = self._running_tasks.get(task_id)
            if running is not None and not running.done():
                running.cancel()
                self._running_tasks.pop(task_id, None)
                logger.info("Cancelled running asyncio task %s", task_id)

        logger.info("Cancelled background task %s: %s", task_id, task.name)
        return True

    async def pause_task(self, task_id: str) -> bool:
        """Pause a running task. Returns True if paused."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status != BackgroundTaskStatus.RUNNING:
                return False
            task.pause()
        logger.info("Paused background task %s", task_id)
        return True

    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task. Returns True if resumed."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status != BackgroundTaskStatus.PAUSED:
                return False
            task.resume()
        logger.info("Resumed background task %s", task_id)
        return True

    def get_task(self, task_id: str) -> BackgroundTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(
        self, status: BackgroundTaskStatus | None = None,
    ) -> list[BackgroundTask]:
        """List all tasks, optionally filtered by status."""
        if status is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.status == status]

    def get_active_count(self) -> int:
        """Return the number of currently running or paused tasks."""
        return sum(
            1 for t in self._tasks.values()
            if t.status in (BackgroundTaskStatus.RUNNING, BackgroundTaskStatus.PAUSED)
        )

    async def cleanup(self, max_age_seconds: float = 3600.0) -> int:
        """Remove completed/failed/cancelled tasks older than max_age_seconds.

        Returns the number of tasks removed.
        """
        now = time.time()
        stale_ids: list[str] = []
        async with self._lock:
            for tid, task in list(self._tasks.items()):
                if task.status in (
                    BackgroundTaskStatus.COMPLETED,
                    BackgroundTaskStatus.FAILED,
                    BackgroundTaskStatus.CANCELLED,
                ):
                    if task.completed_at and (now - task.completed_at) > max_age_seconds:
                        stale_ids.append(tid)

            for tid in stale_ids:
                running = self._running_tasks.pop(tid, None)
                if running is not None and not running.done():
                    running.cancel()
                del self._tasks[tid]

        if stale_ids:
            logger.info("Cleaned up %d stale background tasks", len(stale_ids))
        return len(stale_ids)


class BackgroundAgent:
    """High-level wrapper for running agent workflows in the background.

    Provides convenience methods for common background task patterns.
    """

    def __init__(
        self,
        manager: BackgroundTaskManager | None = None,
    ) -> None:
        self._manager = manager or BackgroundTaskManager()
        logger.info("BackgroundAgent initialized")

    async def run_agent_task(
        self,
        name: str,
        description: str,
        agent_loop: Any,
        prompt: str,
        config: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> str:
        """Run a complete Agent loop in the background.

        The agent_loop must be an object with an async ``run(prompt)`` method
        that yields LLMResponse events.
        """
        metadata = config or {}

        async def _run(
            prompt: str,
            progress_callback: Callable[[float], None] | None = None,
        ) -> dict:
            collected: list[str] = []
            tool_calls_count = 0
            step = 0

            async for resp in agent_loop.run(prompt):
                if resp.event_type == "assistant" and resp.content:
                    collected.append(resp.content)
                if resp.event_type == "tool_call":
                    tool_calls_count += 1
                step += 1
                if progress_callback and step % 5 == 0:
                    progress_callback(min(step, 99))

            final_text = "\n".join(collected).strip() or "(no output)"
            if progress_callback:
                progress_callback(100.0)

            return {
                "response": final_text,
                "tool_calls": tool_calls_count,
                "steps": step,
            }

        return await self._manager.start_task(
            name=name,
            description=description,
            coro_func=_run,
            prompt=prompt,
            timeout=timeout,
            metadata=metadata,
        )

    async def run_tool_task(
        self,
        name: str,
        description: str,
        tool_func: Callable[..., Any],
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> str:
        """Run a single tool function in the background."""

        async def _run(
            progress_callback: Callable[[float], None] | None = None,
        ) -> dict:
            if progress_callback:
                progress_callback(10.0)

            result = await tool_func(*args, **kwargs)

            if progress_callback:
                progress_callback(100.0)

            return {"result": str(result)} if not isinstance(result, dict) else result

        return await self._manager.start_task(
            name=name,
            description=description,
            coro_func=_run,
            timeout=timeout,
        )

    async def run_shell_task(
        self,
        name: str,
        description: str,
        command: str,
        timeout: float = 120.0,
    ) -> str:
        """Run a shell command in the background using asyncio subprocess."""

        async def _run(
            progress_callback: Callable[[float], None] | None = None,
        ) -> dict:
            import sys

            if progress_callback:
                progress_callback(10.0)

            if sys.platform == "win32":
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    shell=True,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise

            if progress_callback:
                progress_callback(100.0)

            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "return_code": proc.returncode,
                "command": command,
            }

        return await self._manager.start_task(
            name=name,
            description=description,
            coro_func=_run,
            timeout=timeout + 10.0,
        )

    def get_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status as a dict (including progress)."""
        task = self._manager.get_task(task_id)
        if task is None:
            return None
        return task.to_dict()

    def get_results(self, task_id: str) -> dict | None:
        """Get the result of a completed task."""
        task = self._manager.get_task(task_id)
        if task is None:
            return None
        if task.status == BackgroundTaskStatus.COMPLETED:
            return task.result
        return None

    @property
    def manager(self) -> BackgroundTaskManager:
        return self._manager
