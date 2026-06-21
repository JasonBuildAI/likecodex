# LikeCodex Agent Engineering Spec

> Agent harness contract for DeepSeek V4 coding tasks. Complements [SPEC-CACHE.md](./SPEC-CACHE.md).
> Change this spec first, then the code.

## 1. AgentLoop

The canonical loop: `LLM complete → assistant → tool calls → tool results → repeat`, bounded by `max_steps`.

### 1.1 Modules

| Module | Responsibility |
|--------|----------------|
| `agent/loop.py` | Main loop, permission routing, checkpoint snapshots |
| `agent/guards.py` | Storm/loop guard on repeated tool failures |
| `agent/plan_mode.py` | Read-only plan mode tool/bash filtering |
| `agent/dispatch.py` | Parallel batch for read-only tools |
| `agent/output_limit.py` | 32KB cap on tool results |
| `agent/coordinator.py` | Dual-model planner + executor handoff |
| `agent/plan_state.py` | Interactive plan mode state machine |
| `agent/task.py` | Sub-agent `task` tool |
| `agent/parallel_tasks.py` | Concurrent sub-agents |

### 1.2 Loop guard

When the same `(tool_name, stable_args)` fails `storm_break_threshold` times (default 3), inject `[loop guard]` into the tool result and emit a user notice. Reset on success or different args.

### 1.3 Plan mode

Orthogonal to permission policy. When active:

- Deny: `write_file`, `edit_file`, `multi_edit`, `move_file`, `delete_range`, `delete_symbol`, `notebook_edit`, `git_commit`
- Bash: block shell metacharacters (`&&`, `||`, `;`, `|`, redirects, subshells)
- Allow safe read-only bash prefixes only (see `plan_mode.py`)

Toggle via `/plan` slash command or `agent.plan_mode=on`.

## 2. Coordinator (dual-model)

When planner is enabled:

- **Planner** (`deepseek-v4-pro`): isolated message list, read-only tool registry, `planner_max_steps`
- **Executor** (`deepseek-v4-flash`): cache-stable session, full tools
- `should_plan(prompt)` skips trivial greetings/short Q&A
- Handoff: `[Plan]` USER block only; planner raw output goes to VolatileScratch

## 3. Compaction

See SPEC-CACHE §4. LLM compaction uses **deepseek-v4-flash** with structured headings:

- Standing facts, Goal, Decisions, Files, Commands, Errors, Pending/next step

Preserves: short user turns verbatim, prior digests verbatim. Archives dropped messages to `.likecodex/archive/<timestamp>.jsonl`.

## 4. Sub-agents

### 4.1 Boundaries

Meta tools excluded from sub-agents: `task`, `parallel_tasks`, `run_skill`, `parallel_tasks`. Background job tools excluded: `bgjobs`, `bash_output`, `kill_shell`, `wait_job`.

Sub-agent bash is foreground-only.

### 4.2 Skills

- `runAs=inline`: body injected as tool result
- `runAs=subagent`: isolated loop via `task` infrastructure; only final answer returned to parent

Prefix pins name+description only; bodies load on demand.

## 5. Permissions

Precedence: `deny` > `ask` > `allow` > fallback.

Rule syntax:

- `Bash(npm run test:*)` — command prefix
- `Edit(src/**)` — path glob for write tools
- Bare `Tool` matches any call in family

Session grants stored in `.likecodex/approvals.json`.

`remember` / `forget` always require user approval regardless of mode.

## 6. complete_step evidence

Kinds: `verification`, `diff`, `files`, `manual`.

`verification` requires `command` matching a prior `run_command` in the session log. Rejected if no match.

On acceptance, host advances `todo_write` list (one in_progress → completed, next pending → in_progress).

## 7. LSP

Tools: `lsp_definition`, `lsp_references`, `lsp_hover`, `lsp_diagnostics`.

Read-only, parallel-batch eligible. Fallback: `code_index` + subprocess checkers when LSP unavailable.

## 8. Metrics

Compaction emits `compaction_started` / `compaction_done` SSE events and increments `cache_reset_count` in `/metrics`.

## 9. Non-goals (this spec)

- Multi-provider LLM (DeepSeek-first by design)
- Token-level LLM streaming in loop (implemented: delta + tool_dispatch + recovery)

Implemented beyond prior non-goals: Goal / AutoResearch, checkpoint fork/rewind modes, ask tool.
