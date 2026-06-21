"""Benchmark framework for LikeCodex agent validation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkTask:
    """A single benchmark task."""
    
    id: str
    name: str
    description: str
    prompt: str
    expected_files: list[str] = field(default_factory=list)
    expected_patterns: list[str] = field(default_factory=list)
    max_steps: int = 50
    timeout_seconds: int = 300
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "expected_files": self.expected_files,
            "expected_patterns": self.expected_patterns,
            "max_steps": self.max_steps,
            "timeout_seconds": self.timeout_seconds,
            "tags": self.tags,
        }


@dataclass
class BenchmarkResult:
    """Result of a benchmark task execution."""
    
    task_id: str
    task_name: str
    success: bool
    duration_seconds: float
    steps_used: int
    tokens_used: int = 0
    files_created: list[str] = field(default_factory=list)
    patterns_found: list[str] = field(default_factory=list)
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "steps_used": self.steps_used,
            "tokens_used": self.tokens_used,
            "files_created": self.files_created,
            "patterns_found": self.patterns_found,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkSuite:
    """Collection of benchmark tasks."""
    
    name: str
    tasks: list[BenchmarkTask] = field(default_factory=list)
    
    def add_task(self, task: BenchmarkTask) -> None:
        self.tasks.append(task)
    
    def get_task(self, task_id: str) -> BenchmarkTask | None:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_tasks_by_tag(self, tag: str) -> list[BenchmarkTask]:
        return [t for t in self.tasks if tag in t.tags]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkSuite:
        suite = cls(name=data["name"])
        for task_data in data.get("tasks", []):
            suite.add_task(BenchmarkTask(**task_data))
        return suite


class BenchmarkRunner:
    """Executes benchmark tasks and collects results."""
    
    def __init__(self, working_dir: Path | None = None):
        self.working_dir = working_dir or Path.cwd()
        self.results: list[BenchmarkResult] = []
    
    async def run_task(
        self,
        task: BenchmarkTask,
        agent_factory: Any,
    ) -> BenchmarkResult:
        """Run a single benchmark task."""
        start_time = time.time()
        
        try:
            # Create agent
            agent = agent_factory(working_dir=self.working_dir)
            
            # Execute task
            steps_used = 0
            tokens_used = 0
            files_created = []
            
            async for event in agent.run(task.prompt):
                steps_used += 1
                if hasattr(event, "usage") and event.usage:
                    tokens_used += event.usage.get("total_tokens", 0)
                
                # Track file creation
                if event.event_type == "tool_result":
                    # Parse tool result to detect file creation
                    pass
                
                if steps_used >= task.max_steps:
                    break
            
            # Validate results
            duration = time.time() - start_time
            patterns_found = []
            
            # Check expected files
            for expected_file in task.expected_files:
                file_path = self.working_dir / expected_file
                if file_path.exists():
                    files_created.append(expected_file)
            
            # Check expected patterns
            for pattern in task.expected_patterns:
                # Search for pattern in created files
                for file_path in self.working_dir.rglob("*"):
                    if file_path.is_file():
                        try:
                            content = file_path.read_text()
                            if pattern in content:
                                patterns_found.append(pattern)
                                break
                        except Exception:
                            pass
            
            success = (
                len(files_created) == len(task.expected_files)
                and len(patterns_found) == len(task.expected_patterns)
            )
            
            result = BenchmarkResult(
                task_id=task.id,
                task_name=task.name,
                success=success,
                duration_seconds=duration,
                steps_used=steps_used,
                tokens_used=tokens_used,
                files_created=files_created,
                patterns_found=patterns_found,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            result = BenchmarkResult(
                task_id=task.id,
                task_name=task.name,
                success=False,
                duration_seconds=duration,
                steps_used=0,
                error_message=str(e),
            )
        
        self.results.append(result)
        return result
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of all benchmark results."""
        if not self.results:
            return {"total": 0, "success_rate": 0.0}
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        total_duration = sum(r.duration_seconds for r in self.results)
        total_steps = sum(r.steps_used for r in self.results)
        total_tokens = sum(r.tokens_used for r in self.results)
        
        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "total_duration_seconds": total_duration,
            "avg_duration_seconds": total_duration / total if total > 0 else 0.0,
            "total_steps": total_steps,
            "avg_steps": total_steps / total if total > 0 else 0.0,
            "total_tokens": total_tokens,
            "avg_tokens": total_tokens / total if total > 0 else 0.0,
        }
    
    def save_results(self, output_path: Path) -> None:
        """Save benchmark results to JSON file."""
        data = {
            "summary": self.get_summary(),
            "results": [r.to_dict() for r in self.results],
        }
        output_path.write_text(json.dumps(data, indent=2))
