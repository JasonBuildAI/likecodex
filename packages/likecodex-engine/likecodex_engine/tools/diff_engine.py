"""Incremental Diff Engine — Myers diff algorithm implementation.

Provides:
- MyersDiff: O(ND) Myers diff algorithm for line-by-line comparison
- ChunkDiff: Chunk-by-chunk comparison for larger files
- Unified diff format output
- apply_diff and reverse_diff for partial diff application
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any


# ── Core Types ──────────────────────────────────────────────────────────


@dataclass
class DiffOp:
    """A single diff operation."""

    tag: str  # 'equal' | 'insert' | 'delete' | 'replace'
    old_start: int = 0
    old_end: int = 0
    new_start: int = 0
    new_end: int = 0
    content: list[str] = field(default_factory=list)

    @property
    def is_change(self) -> bool:
        return self.tag in ("insert", "delete", "replace")

    @property
    def old_lines(self) -> list[str]:
        if self.tag == "insert":
            return []
        return self.content if self.tag != "replace" else self.content[: len(self.content) // 2]

    @property
    def new_lines(self) -> list[str]:
        if self.tag == "delete":
            return []
        if self.tag == "insert":
            return self.content
        if self.tag == "replace":
            return self.content[len(self.content) // 2 :]
        return self.content


@dataclass
class DiffResult:
    """Result of a diff operation."""

    ops: list[DiffOp] = field(default_factory=list)
    old_lines: list[str] = field(default_factory=list)
    new_lines: list[str] = field(default_factory=list)

    @property
    def added(self) -> int:
        return sum(op.new_end - op.new_start for op in self.ops if op.tag == "insert")

    @property
    def removed(self) -> int:
        return sum(op.old_end - op.old_start for op in self.ops if op.tag == "delete")

    @property
    def modified(self) -> int:
        return sum(op.old_end - op.old_start for op in self.ops if op.tag == "replace")

    @property
    def net_changes(self) -> int:
        return self.added + self.removed + self.modified

    def to_unified_diff(
        self,
        fromfile: str = "a/file",
        tofile: str = "b/file",
        context: int = 3,
    ) -> str:
        """Generate unified diff format string."""
        lines: list[str] = []
        lines.append(f"--- {fromfile}")
        lines.append(f"+++ {tofile}")

        i = 0
        while i < len(self.ops):
            op = self.ops[i]
            if not op.is_change:
                i += 1
                continue

            # Find the hunk range
            hunk_start = max(0, i - context)
            hunk_end = min(len(self.ops), i + context + 1)

            old_start_line = 1
            new_start_line = 1
            for j in range(hunk_start):
                prev = self.ops[j]
                old_start_line += prev.old_end - prev.old_start
                new_start_line += prev.new_end - prev.new_start

            hunk_old_lines: list[str] = []
            hunk_new_lines: list[str] = []
            hunk_old_count = 0
            hunk_new_count = 0

            for j in range(hunk_start, hunk_end):
                hop = self.ops[j]
                if hop.tag == "equal":
                    ctx = hop.content
                    if j < i:
                        # Before the first change — include context lines
                        take = max(0, len(ctx) - (0 if j == hunk_start else 0))
                        ctx_taken = ctx[-take:] if take > 0 else []
                        hunk_old_lines.extend(ctx_taken)
                        hunk_new_lines.extend(ctx_taken)
                        hunk_old_count += len(ctx_taken)
                        hunk_new_count += len(ctx_taken)
                    elif j < hunk_end - context:
                        # After the last change — include context lines
                        ctx_taken = ctx[:context]
                        hunk_old_lines.extend(ctx_taken)
                        hunk_new_lines.extend(ctx_taken)
                        hunk_old_count += len(ctx_taken)
                        hunk_new_count += len(ctx_taken)
                elif hop.tag == "delete":
                    for line in hop.old_lines:
                        hunk_old_lines.append(f"-{line}")
                        hunk_old_count += 1
                elif hop.tag == "insert":
                    for line in hop.new_lines:
                        hunk_new_lines.append(f"+{line}")
                        hunk_new_count += 1
                elif hop.tag == "replace":
                    for line in hop.old_lines:
                        hunk_old_lines.append(f"-{line}")
                        hunk_old_count += 1
                    for line in hop.new_lines:
                        hunk_new_lines.append(f"+{line}")
                        hunk_new_count += 1

            # Emit hunk header
            line_start = old_start_line + len([op for op in self.ops[:hunk_start] if op.is_change])
            lines.append(
                f"@@ -{old_start_line},{hunk_old_count} +{new_start_line},{hunk_new_count} @@"
            )
            lines.extend(hunk_old_lines)
            lines.extend(hunk_new_lines)

            i = hunk_end
            old_start_line = 1
            new_start_line = 1

        return "\n".join(lines)


# ── Myers Diff Algorithm ──────────────────────────────────────────────


class MyersDiff:
    """Myers O(ND) diff algorithm implementation.

    Finds the shortest edit script (SES) between two sequences of lines.
    Uses the standard divide-and-conquer approach with a linear-space
    variant that finds the middle snake, then recurses.
    """

    @staticmethod
    def diff(
        old_lines: list[str],
        new_lines: list[str],
    ) -> DiffResult:
        """Compute the diff between two lists of lines.

        Args:
            old_lines: Original file lines.
            new_lines: Modified file lines.

        Returns:
            DiffResult containing all operations.
        """
        ops: list[DiffOp] = []
        MyersDiff._compute(old_lines, new_lines, 0, 0, ops)
        return DiffResult(ops=ops, old_lines=old_lines, new_lines=new_lines)

    @staticmethod
    def _compute(
        a: list[str],
        b: list[str],
        a_offset: int,
        b_offset: int,
        ops: list[DiffOp],
    ) -> None:
        """Recursive divide-and-conquer Myers diff.

        Args:
            a: Old sequence (original lines).
            b: New sequence (modified lines).
            a_offset: Line offset in the original file.
            b_offset: Line offset in the new file.
            ops: Output list of DiffOp objects.
        """
        n, m = len(a), len(b)

        # Base cases
        if n == 0 and m == 0:
            return

        # All insertions
        if n == 0:
            ops.append(
                DiffOp(
                    tag="insert",
                    old_start=a_offset,
                    old_end=a_offset,
                    new_start=b_offset,
                    new_end=b_offset + m,
                    content=list(b),
                )
            )
            return

        # All deletions
        if m == 0:
            ops.append(
                DiffOp(
                    tag="delete",
                    old_start=a_offset,
                    old_end=a_offset + n,
                    new_start=b_offset,
                    new_end=b_offset,
                    content=list(a),
                )
            )
            return

        # Find the middle snake using the linear-space Myers algorithm
        snake = MyersDiff._find_middle_snake(a, b)
        x, y, u, v = snake

        # Collect equal prefix
        if x > 0 and y > 0 and a[:x] == b[:y]:
            eq_lines = a[:x]
            ops.append(
                DiffOp(
                    tag="equal",
                    old_start=a_offset,
                    old_end=a_offset + x,
                    new_start=b_offset,
                    new_end=b_offset + y,
                    content=list(eq_lines),
                )
            )

        # Recurse on the left part
        MyersDiff._compute(a[:x], b[:y], a_offset, b_offset, ops)

        # Handle the middle snake itself
        snake_len = u - x
        if snake_len > 0:
            ops.append(
                DiffOp(
                    tag="equal",
                    old_start=a_offset + x,
                    old_end=a_offset + u,
                    new_start=b_offset + y,
                    new_end=b_offset + v,
                    content=list(a[x:u]),
                )
            )

        # Recurse on the right part
        MyersDiff._compute(a[u:], b[v:], a_offset + u, b_offset + v, ops)

    @staticmethod
    def _find_middle_snake(
        a: list[str],
        b: list[str],
    ) -> tuple[int, int, int, int]:
        """Find the middle snake of the edit graph.

        Implements the linear-space Myers algorithm to find a single
        snake (x,y) -> (u,v) on the middle diagonal.

        Returns:
            Tuple (x, y, u, v) representing the snake.
        """
        n, m = len(a), len(b)
        max_d = (n + m + 1) // 2 + 1

        # Forward and reverse V arrays
        # Use dicts since diagonals can be negative
        Vf: dict[int, int] = {1: 0}
        Vr: dict[int, int] = {-1: n + m}

        for d in range(max_d + 1):
            # Forward pass
            for k in range(-d, d + 1, 2):
                if k == -d or (k != d and Vf.get(k - 1, -1) < Vf.get(k + 1, -1)):
                    x = Vf.get(k + 1, 0)
                else:
                    x = Vf.get(k - 1, 0) + 1
                y = x - k
                # Follow the snake
                while x < n and y < m and a[x] == b[y]:
                    x += 1
                    y += 1
                Vf[k] = x

                # Check for overlap with reverse path
                if d >= (n + m + 1) // 2:
                    break

            if d < (n + m + 1) // 2:
                continue

            # Check for overlap
            for k in range(-d, d + 1, 2):
                x = Vf.get(k, 0)
                y = x - k
                # Check if this point is reachable from the reverse path
                if k in Vr:
                    rx = Vr[k]
                    ry = rx - k
                    if rx <= x and ry <= y:
                        # Found the middle snake
                        return x, y, x, y

        # Fallback: return whole sequences as a snake (shouldn't happen)
        return n, m, n, m


# ── Chunk Diff ──────────────────────────────────────────────────────────


class ChunkDiff:
    """Chunk-by-chunk comparison for larger files.

    Splits files into logical chunks (by function/class boundaries)
    and diffs each chunk separately for better performance and readability.
    """

    CHUNK_PATTERNS = [
        re.compile(r"^(def |class |async def |pub fn |fn |func |public )"),
        re.compile(r"^(export (default )?(function|class|const|let|var) )"),
        re.compile(r"^(impl .+ for |trait |struct |enum )"),
        re.compile(r"^(func |type |interface )"),
    ]

    @classmethod
    def split_chunks(cls, lines: list[str]) -> list[tuple[str, list[str]]]:
        """Split lines into named chunks.

        Returns:
            List of (chunk_name, chunk_lines) tuples.
        """
        if not lines:
            return []

        chunks: list[tuple[str, list[str]]] = []
        current_name = "<header>"
        current_chunk: list[str] = []

        for line in lines:
            matched = False
            for pat in cls.CHUNK_PATTERNS:
                m = pat.match(line.strip())
                if m:
                    if current_chunk:
                        chunks.append((current_name, current_chunk))
                    current_name = line.strip()[:60]
                    current_chunk = [line]
                    matched = True
                    break

            if not matched:
                current_chunk.append(line)

        if current_chunk:
            chunks.append((current_name, current_chunk))

        return chunks

    @classmethod
    def diff(cls, old_lines: list[str], new_lines: list[str]) -> DiffResult:
        """Compute chunk-by-chunk diff.

        Aligns chunks by name and diffs matching pairs.
        """
        old_chunks = cls.split_chunks(old_lines)
        new_chunks = cls.split_chunks(new_lines)

        all_ops: list[DiffOp] = []
        old_idx = 0
        new_idx = 0
        old_accum = 0
        new_accum = 0

        while old_idx < len(old_chunks) or new_idx < len(new_chunks):
            if old_idx >= len(old_chunks):
                # Remaining new chunks are insertions
                name, chunk = new_chunks[new_idx]
                all_ops.append(
                    DiffOp(
                        tag="insert",
                        old_start=old_accum,
                        old_end=old_accum,
                        new_start=new_accum,
                        new_end=new_accum + len(chunk),
                        content=list(chunk),
                    )
                )
                new_accum += len(chunk)
                new_idx += 1

            elif new_idx >= len(new_chunks):
                # Remaining old chunks are deletions
                name, chunk = old_chunks[old_idx]
                all_ops.append(
                    DiffOp(
                        tag="delete",
                        old_start=old_accum,
                        old_end=old_accum + len(chunk),
                        new_start=new_accum,
                        new_end=new_accum,
                        content=list(chunk),
                    )
                )
                old_accum += len(chunk)
                old_idx += 1

            elif old_chunks[old_idx][0] == new_chunks[new_idx][0]:
                # Same chunk name — diff the contents
                oname, ochunk = old_chunks[old_idx]
                _nname, nchunk = new_chunks[new_idx]

                # Merge equal prefix
                prefix_len = 0
                while (
                    prefix_len < len(ochunk)
                    and prefix_len < len(nchunk)
                    and ochunk[prefix_len] == nchunk[prefix_len]
                ):
                    prefix_len += 1

                if prefix_len > 0:
                    all_ops.append(
                        DiffOp(
                            tag="equal",
                            old_start=old_accum,
                            old_end=old_accum + prefix_len,
                            new_start=new_accum,
                            new_end=new_accum + prefix_len,
                            content=list(ochunk[:prefix_len]),
                        )
                    )

                # Diff the rest using Myers
                inner = MyersDiff.diff(ochunk[prefix_len:], nchunk[prefix_len:])
                for op in inner.ops:
                    if op.tag != "equal" or (op.old_end - op.old_start) > 0:
                        op.old_start += old_accum + prefix_len
                        op.old_end += old_accum + prefix_len
                        op.new_start += new_accum + prefix_len
                        op.new_end += new_accum + prefix_len
                        all_ops.append(op)

                size = max(len(ochunk), len(nchunk))
                old_accum += len(ochunk)
                new_accum += len(nchunk)
                old_idx += 1
                new_idx += 1

            else:
                # Different chunk names — treat as delete + insert
                oname, ochunk = old_chunks[old_idx]
                nname, nchunk = new_chunks[new_idx]
                all_ops.append(
                    DiffOp(
                        tag="delete",
                        old_start=old_accum,
                        old_end=old_accum + len(ochunk),
                        new_start=new_accum,
                        new_end=new_accum,
                        content=list(ochunk),
                    )
                )
                old_accum += len(ochunk)
                old_idx += 1

        return DiffResult(ops=all_ops, old_lines=old_lines, new_lines=new_lines)


# ── Diff Application ──────────────────────────────────────────────────


def apply_diff(
    original_text: str,
    diff_ops: list[DiffOp],
) -> str | None:
    """Apply a sequence of diff operations to original text.

    Args:
        original_text: The original file content.
        diff_ops: List of DiffOp operations to apply.

    Returns:
        The modified text, or None if application fails.
    """
    lines = original_text.splitlines(keepends=True)

    # Sort operations from bottom to top to preserve line numbers
    sorted_ops = sorted(
        [op for op in diff_ops if op.is_change],
        key=lambda op: op.old_start,
        reverse=True,
    )

    result = list(lines)
    for op in sorted_ops:
        start = op.old_start
        end = op.old_end

        if start > len(result) or end > len(result):
            return None

        # Verify content matches
        old_slice = result[start:end]
        expected = [
            l if not l.endswith("\n") else l for l in op.old_lines
        ]
        actual = [
            l.rstrip("\n") if isinstance(l, str) else "".join(l).rstrip("\n")
            for l in old_slice
        ]
        if expected and expected != actual:
            return None

        new_lines_with_newlines = [
            (l if l.endswith("\n") else l + "\n") for l in op.new_lines
        ]
        result = result[:start] + new_lines_with_newlines + result[end:]

    return "".join(result)


def apply_unified_diff(original_text: str, unified_diff_text: str) -> str | None:
    """Apply a unified diff string to original text.

    Parses the unified diff format and applies hunks sequentially.

    Args:
        original_text: The original file content.
        unified_diff_text: The unified diff string to apply.

    Returns:
        The patched text, or None if patching fails.
    """
    lines = original_text.splitlines(keepends=True)
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    raw_hunks = unified_diff_text.split("\n@@ ")
    parsed_hunks: list[tuple[int, int, list[str], list[str]]] = []

    for raw in raw_hunks:
        if not raw.strip():
            continue
        hunk_str = raw if raw.startswith("@@") else "@@ " + raw
        hunk_lines = hunk_str.splitlines(keepends=True)
        if not hunk_lines:
            continue

        header_match = hunk_re.match(hunk_lines[0].strip())
        if not header_match:
            continue

        old_start = int(header_match.group(1))
        old_hunk: list[str] = []
        new_hunk: list[str] = []

        for hl in hunk_lines[1:]:
            if hl.startswith("-"):
                old_hunk.append(hl[1:])
            elif hl.startswith("+"):
                new_hunk.append(hl[1:])
            else:
                stripped = hl[1:] if hl.startswith(" ") else hl
                old_hunk.append(stripped)
                new_hunk.append(stripped)

        parsed_hunks.append((old_start, len(old_hunk), old_hunk, new_hunk))

    result = list(lines)
    for old_start, _old_count, old_hunk, new_hunk in sorted(
        parsed_hunks, key=lambda x: -x[0]
    ):
        old_slice_start = old_start - 1
        old_slice_end = old_slice_start + len(old_hunk)

        if result[old_slice_start:old_slice_end] != old_hunk:
            return None

        result = result[:old_slice_start] + new_hunk + result[old_slice_end:]

    return "".join(result)


def reverse_diff(diff_ops: list[DiffOp]) -> list[DiffOp]:
    """Reverse a diff operation sequence.

    Swaps old/new positions so the reversed diff undoes the original.

    Args:
        diff_ops: Original diff operations.

    Returns:
        Reversed diff operations.
    """
    reversed_ops: list[DiffOp] = []
    for op in reversed(diff_ops):
        if op.tag == "equal":
            reversed_ops.append(
                DiffOp(
                    tag="equal",
                    old_start=op.new_start,
                    old_end=op.new_end,
                    new_start=op.old_start,
                    new_end=op.old_end,
                    content=list(op.content),
                )
            )
        elif op.tag == "insert":
            reversed_ops.append(
                DiffOp(
                    tag="delete",
                    old_start=op.new_start,
                    old_end=op.new_end,
                    new_start=op.old_start,
                    new_end=op.old_end,
                    content=list(op.old_lines),
                )
            )
        elif op.tag == "delete":
            reversed_ops.append(
                DiffOp(
                    tag="insert",
                    old_start=op.new_start,
                    old_end=op.new_end,
                    new_start=op.old_start,
                    new_end=op.old_end,
                    content=list(op.new_lines),
                )
            )
        elif op.tag == "replace":
            reversed_ops.append(
                DiffOp(
                    tag="replace",
                    old_start=op.new_start,
                    old_end=op.new_end,
                    new_start=op.old_start,
                    new_end=op.old_end,
                    content=list(op.new_lines + op.old_lines),
                )
            )
    return reversed_ops


def compute_diff(
    old_text: str,
    new_text: str,
    algorithm: str = "myers",
) -> DiffResult:
    """Compute diff between two texts.

    Args:
        old_text: Original file content.
        new_text: Modified file content.
        algorithm: 'myers' or 'chunk'.

    Returns:
        DiffResult with operations.
    """
    old_lines = old_text.splitlines(keepends=False)
    new_lines = new_text.splitlines(keepends=False)

    if algorithm == "chunk":
        return ChunkDiff.diff(old_lines, new_lines)
    return MyersDiff.diff(old_lines, new_lines)


def diff_stats(diff_result: DiffResult) -> dict[str, Any]:
    """Compute statistics from a diff result.

    Returns:
        Dict with added, removed, modified, and total change counts.
    """
    return {
        "added": diff_result.added,
        "removed": diff_result.removed,
        "modified": diff_result.modified,
        "total": diff_result.net_changes,
    }
