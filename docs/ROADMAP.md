# AI Software Factory: Product and Engineering Roadmap

Status: proposed
Updated: 2026-06-27

## 1. Product direction

AI Software Factory should evolve from a fixed, one-shot project generator into a
safe, persistent, repository-aware coding agent. The current seven-agent generation
flow remains useful, but it should become one workflow rather than the whole product.

The target product has three jobs:

1. Interactive repository work: inspect an existing repository, discuss a task, edit
   files incrementally, run commands, review diffs, and continue the session.
2. Non-interactive automation: run bounded tasks in scripts and CI with stable JSON
   or JSONL output and meaningful exit codes.
3. Greenfield generation: retain the existing planner, coder, reviewer, tester, and
   deployer flow behind an explicit generate command.

The central shift is:

> Move from sending an entire synthetic project through a fixed pipeline to running
> a model-driven tool loop over a real repository, with explicit permissions,
> durable state, and optional specialist agents.

## 2. Current-state assessment

### Useful foundations

- Packaged Python CLI with interactive and direct prompt modes.
- Rich terminal rendering for stages, plans, reviews, files, and summaries.
- Typed Pydantic models for plans, files, reviews, tests, and pipeline state.
- Specialized prompts for planning, coding, review, testing, and deployment.
- Review/improvement and test/fix loops.
- Offline demo fixtures that can support deterministic integration tests.

### Immediate correctness and safety work

| Issue | Current behavior | Required correction |
|---|---|---|
| Demo routing | Pipeline._run_crew_or_mock exists, but stage methods instantiate CrewAI directly. | Route all model calls through one execution abstraction and add an offline end-to-end test. |
| Output override | --output-dir assigns to the read-only settings.output_path property. | Assign settings.output_dir and test CLI precedence. |
| False sandbox claim | run_command is a normal host subprocess with a timeout. | Rename it until enforcement exists, then add OS/container sandbox backends. |
| Path traversal | File containment uses string startswith checks. | Resolve paths, use Path.is_relative_to, and reject symlink escapes. |
| Stale tests | Runs reuse output/_test_run without guaranteed cleanup. | Use a unique temporary workspace per run and clean it deterministically. |
| Language assumption | Every generated project runs pytest tests/. | Detect project commands from repository metadata and approved configuration. |
| Fragile output parsing | JSON is requested by prompt, regex-extracted, and silently replaced by empty fallbacks. | Use native structured output/tool calls and typed retryable failures. |
| No recovery | Pipeline state is memory-only and files are written near the end. | Persist turns, calls, approvals, checkpoints, and artifacts as they occur. |
| Context growth | Complete codebases are repeatedly serialized into prompts. | Load relevant files lazily and compact old tool output. |
| Provider lock-in | Setup, config, credentials, and model lists are OpenAI-specific. | Add provider interfaces and provider-scoped credentials/configuration. |

### Architectural limitation

CrewAI currently creates one agent and one task for each stage and executes all
stages sequentially. There is no dynamic delegation, shared tool registry,
repository exploration, approval engine, enforced sandbox, or persistent
conversation. The system is multi-prompt, but not yet a modern interactive coding
agent.

## 3. Capability benchmark

Modern coding agents converge on a common set of product capabilities. This project
should adopt the underlying patterns while remaining provider-neutral and auditable.

| Capability | Codex / Claude pattern | AI Software Factory direction |
|---|---|---|
| Repository-native loop | Read files, edit, run commands, and inspect diffs conversationally. | Make this the default ai-factory experience. |
| Plan mode | Read-only exploration produces a plan before implementation. | Add /plan and a technically read-only policy. |
| Permissions | Actions are allowed, denied, or approval-gated by risk and scope. | Add a central policy engine for every local and MCP tool. |
| OS isolation | Commands execute inside explicit filesystem and network boundaries. | Support Linux bwrap, macOS Seatbelt, and a Docker fallback. |
| Sessions | Conversations and tool activity can be resumed. | Persist sessions in SQLite and expose resume/list/delete commands. |
| Checkpoints | Per-turn edits can be rewound without replacing Git. | Store file preimages and manifests for every mutation. |
| Project instructions | Hierarchical repository instructions load automatically. | Support the open AGENTS.md convention and nested overrides. |
| Extensibility | MCP, hooks, skills, commands, and specialist agents. | Build extensions on versioned tool and event contracts. |
| Parallel agents | Specialists run in isolated contexts and worktrees. | Add only after the single-agent loop and safety model are reliable. |
| Automation | Headless runs stream structured output for CI and scripts. | Add exec --jsonl, bounded turns, budgets, and stable exit codes. |
| Observability | Plans, actions, results, diffs, usage, and failures are visible. | Use an append-only event log and optional OpenTelemetry export. |

Reference behavior:

- [Codex CLI features](https://developers.openai.com/codex/cli/features)
- [Codex approvals and sandboxing](https://developers.openai.com/codex/agent-approvals-security)
- [Codex subagents](https://developers.openai.com/codex/subagents)
- [Codex AGENTS.md guidance](https://developers.openai.com/codex/guides/agents-md)
- [Codex MCP support](https://developers.openai.com/codex/mcp)
- [Claude Code checkpointing](https://code.claude.com/docs/en/checkpointing)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code project memory](https://code.claude.com/docs/en/memory)

## 4. Product principles

1. Safe by default. Workspace writes, command execution, network access, secrets,
   and external side effects have separate controls.
2. One transparent agent loop first. Specialist agents are optional workers, not
   mandatory stages.
3. Repository state is the source of truth. Models receive selected context, not a
   synthetic replacement for the working tree.
4. Every action is inspectable. Tool input, result, approval, diff, duration, and
   failure are represented as events.
5. Provider-neutral core. Provider-specific features live behind adapters.
6. Human control scales with risk. Reading is cheap; writes are reviewable;
   dangerous or external actions require authority.
7. Git-compatible, not Git-dependent. Basic sessions and checkpoints also work
   outside Git repositories.
8. Backward-compatible migration. Preserve the generator as ai-factory generate.

## 5. Target user experience

### Top-level commands

~~~text
ai-factory                         Start an interactive repository session
ai-factory "fix the auth bug"      Start with an initial prompt
ai-factory exec "run the linter"   Run a headless bounded task
ai-factory resume                  Pick a previous session
ai-factory resume --last           Resume the latest repository session
ai-factory review                  Review the current diff without editing
ai-factory init                    Create starter instructions and project config
ai-factory generate "build an API" Run the legacy greenfield factory workflow
ai-factory mcp list                Show configured MCP servers
ai-factory doctor                  Validate provider, tools, and sandbox
~~~

### Interactive commands

~~~text
/plan          Switch to read-only planning
/implement     Approve the active plan and allow edits
/permissions   Inspect or change the permission profile
/diff          Show session changes
/review        Run a read-only review of a selected diff
/undo          Restore the latest checkpoint
/compact       Summarize older context while preserving durable state
/model         Change provider/model settings
/agents        Show, start, or stop specialist agents
/mcp           Inspect MCP tools and server status
/status        Show repository, session, budget, and sandbox state
/help          Show commands and key bindings
/exit          End the session safely
~~~

### Permission profiles

| Profile | Files | Commands | Network | Use |
|---|---|---|---|---|
| plan | Read-only | Safe read commands | Off | Exploration and planning |
| workspace | Workspace read/write | Approval by risk | Off | Default coding session |
| networked | Workspace read/write | Approval by risk | Allow-listed | Dependencies and docs |
| full-access | User-configured | Minimal prompts | On | Explicit trusted isolation only |

## 6. Target architecture

~~~text
CLI / TUI
commands · composer · streaming · diff view · approvals
    |
    v
Session Runtime
turn loop · plan state · context budget · cancellation · resume
    |
    +--> Provider Adapters: OpenAI · Anthropic · Ollama · compatible APIs
    |
    +--> Tool Registry: file · search · patch · shell · Git · MCP
    |        |
    |        v
    |    Policy Engine: risk · approval · path · network
    |        |
    |        v
    |    Sandbox / Workspace: bwrap · Seatbelt · Docker · checkpoints
    |
    +--> Agent Scheduler: specialists · jobs · worktrees · budgets
    |
    v
Persistence / Telemetry: SQLite · JSONL · optional OpenTelemetry
~~~

### Proposed package layout

~~~text
src/
├── cli/
│   ├── app.py
│   ├── interactive.py
│   ├── renderer.py
│   └── slash_commands.py
├── core/
│   ├── runtime.py
│   ├── context.py
│   ├── events.py
│   ├── policy.py
│   └── instructions.py
├── providers/
│   ├── base.py
│   ├── openai.py
│   ├── anthropic.py
│   └── ollama.py
├── tools/
│   ├── registry.py
│   ├── filesystem.py
│   ├── search.py
│   ├── patch.py
│   ├── shell.py
│   └── git.py
├── sandbox/
│   ├── base.py
│   ├── linux.py
│   ├── macos.py
│   └── docker.py
├── sessions/
│   ├── store.py
│   ├── checkpoints.py
│   └── migrations/
├── extensions/
│   ├── hooks.py
│   ├── skills.py
│   └── mcp.py
├── agents/
│   ├── scheduler.py
│   └── definitions.py
└── legacy/
    └── pipeline.py
~~~

## 7. Core technical contracts

### Provider adapter

The runtime should not depend on CrewAI response objects. Providers implement a
small async streaming interface that accepts normalized messages, tool schemas,
model settings, and optional structured-output schemas. Provider events normalize
text deltas, tool calls, usage, completion, and typed errors.

CrewAI may remain inside the legacy generator initially. The repository agent should
call model APIs through the provider interface so native tool calling, streaming,
usage accounting, retries, and cancellation remain available.

### Tool contract

Each tool declares:

- a stable name and version;
- a Pydantic input model;
- risk and side-effect metadata;
- an async execute operation;
- a structured result containing model text, display text, metadata, duration,
  truncation state, artifacts, and file changes.

The runtime, built-in tools, hooks, and MCP tools all pass through the same policy
and event pipeline.

### Approval model

Policies evaluate each proposed action using:

- tool identity and declared risk;
- normalized paths and writable roots;
- parsed commands and command-prefix rules;
- network destinations;
- destructive or external-side-effect annotations;
- active profile and remembered session approvals.

The result is allow, deny, or prompt. A reusable approval must be constrained to a
specific command prefix, path, host, or MCP tool.

### Session and event model

Use SQLite for indexed state and JSONL for portable export. Important event types:

- session.started, session.resumed, session.ended;
- turn.started, turn.completed, turn.failed;
- message.created, context.compacted;
- model.started, model.delta, model.usage, model.completed;
- tool.proposed, approval.requested, approval.resolved;
- tool.started, tool.completed, tool.failed;
- checkpoint.created, checkpoint.restored;
- agent.started, agent.completed, agent.failed.

Store secrets only by reference to environment variables or OS credential storage.
Never persist them in prompts, displays, events, or exported transcripts.

### Checkpoints

Create a checkpoint before every mutating tool batch. Store:

- a manifest of touched paths and metadata;
- content-addressed preimage blobs for changed or deleted files;
- created-file markers;
- related turn and tool-call IDs;
- a post-action diff summary.

For shell commands, compare the workspace before and after execution. Later,
execute mutating parallel jobs in isolated Git worktrees and apply reviewed patches.

## 8. Delivery roadmap

Estimates assume one experienced full-time engineer. Parallel contributors can
shorten elapsed time, but phases should keep this dependency order.

### Phase 0 — Stabilize the current CLI (v0.2, 1 week)

Goal: make existing behavior honest, testable, and safe enough to extend.

- Fix demo mode and --output-dir.
- Harden path containment and temporary test workspaces.
- Rename the current executor to avoid claiming OS sandboxing.
- Replace silent JSON fallbacks with typed pipeline failures.
- Add tests for parsing, configuration, paths, models, and demo mode.
- Add Ruff, mypy, pytest, and GitHub Actions.
- Pin compatible dependency ranges and supported Python versions.

Exit criteria:

- Demo mode completes offline from a clean checkout.
- Invalid model output cannot produce a misleading successful project.
- Generated paths cannot escape the run directory.
- Non-provider pipeline branches are covered by tests.

### Phase 1 — Repository agent loop (v0.3, 2–3 weeks)

Goal: ship the smallest useful Codex/Claude-style workflow.

Implementation status (started 2026-06-28):

- Complete: provider-neutral model events, tool contracts, registry, bounded runtime,
  repeated-call detection, repository discovery, Git-aware file listing, bounded file
  reads, text search, Git status/diff tools, scoped AGENTS.md loading, ai-factory
  inspect, and the explicit ai-factory generate command.
- Next: OpenAI and Anthropic adapters, write tools, permission policy, plan mode,
  cancellation, budgets, and sandboxed shell execution.

- Add provider, model-event, tool, and runtime interfaces.
- Implement OpenAI and Anthropic adapters, followed by OpenAI-compatible/Ollama.
- Add list_files, read_file, search, apply_patch, git_status, git_diff, and shell.
- Add repository discovery, ignore rules, file-size limits, and symlink handling.
- Implement native tool calling with max turns, cancellation, timeout, budget, and
  repeated-call loop detection.
- Add read-only plan mode and an explicit implementation transition.
- Preserve the current workflow as ai-factory generate.

Exit criteria:

- The agent can inspect a real repository, make a focused patch, run a relevant
  test, and summarize the diff.
- It does not send the entire repository by default.
- Every tool call validates arguments and emits lifecycle events.
- One runtime works with at least two providers.

### Phase 2 — Safe execution and undo (v0.4, 2–3 weeks)

Goal: make local autonomy understandable and reversible.

- Add permission profiles and a central allow/deny/prompt policy engine.
- Add one-time and constrained reusable approvals.
- Add Linux bwrap/seccomp first, macOS Seatbelt second, Docker fallback third.
- Keep network off by default and support destination allow lists.
- Protect sensitive files and detect writes outside the workspace.
- Add pre-turn checkpoints, /undo, and session-scoped diff tracking.
- Add a read-only /review workflow.
- Add ai-factory doctor sandbox self-tests.

Exit criteria:

- Workspace mode cannot write outside configured roots without approval.
- Plan and review modes cannot mutate the workspace.
- Disabled network is technically blocked, not merely prohibited by prompts.
- Agent edits can be restored after a failed turn.

### Phase 3 — Persistent interactive CLI (v0.5, 2 weeks)

Goal: create a daily-use terminal experience.

Continuity foundation status (started 2026-06-29):

- Complete: token-bounded context compiler, context and usage events, SQLite session
  and event storage, normalized message persistence, interruption-safe replay,
  persistent runtime resume, verification-gated task ledger, compact task-state
  projection, content-addressed artifacts, artifact-backed large-result truncation,
  and the durable ORIENT-to-HANDOFF controller.
- Next: checkpoints, CLI session controls, JSONL export, repository-memory retrieval,
  invalidation, and user-facing memory controls.

- Replace the setup wizard as default with a streaming interactive REPL.
- Add multiline input, history, cancellation, queued follow-ups, file mentions,
  and concise tool progress.
- Add SQLite sessions and JSONL export.
- Add resume, resume --last, session listing, and retention controls.
- Add the target slash commands.
- Add context budgeting, result truncation, and /compact.
- Add headless exec with text, JSON, and JSONL output.
- Define stable exit codes for success, denial, provider error, budget exhaustion,
  validation failure, and interruption.

Exit criteria:

- Interrupted work resumes without repeating completed actions.
- Headless mode emits machine-readable output without terminal decoration.
- Compaction retains plans, decisions, changed files, failures, and instructions.

### Phase 4 — Customization and integration (v0.6, 2–3 weeks)

Goal: let teams extend behavior without forking.

- Load global, repository, and nested AGENTS.md with deterministic precedence.
- Add user/project TOML configuration and trust-gate project configuration.
- Add PreToolUse, PostToolUse, ApprovalRequested, TurnCompleted, and SessionEnd hooks.
- Add reusable Markdown skills with metadata and tool restrictions.
- Add MCP STDIO and streamable HTTP clients with OAuth and bearer-token support.
- Normalize MCP tools into the standard policy/event pipeline.
- Add project slash commands and prompt templates.

Exit criteria:

- Nested instructions affect only their directory scope.
- Untrusted repositories cannot silently activate hooks or MCP servers.
- Hooks can block actions with visible explanations.
- MCP tools receive the same approvals as local tools.

### Phase 5 — Specialist and parallel agents (v0.7, 3 weeks)

Goal: use multiple agents only where isolation or parallelism helps.

- Convert planner, reviewer, tester, and security roles into configurable specialists.
- Add explicit delegation, background jobs, cancellation, and budgets.
- Return structured summaries instead of raw subagent logs.
- Add parallel read-only exploration and review.
- Add Git worktree isolation for parallel mutating jobs.
- Detect overlapping file ownership before applying worker patches.
- Limit agent depth, concurrency, cost, and wall time.

Exit criteria:

- Parallel reviewers cannot edit the repository.
- Mutating jobs operate in separate worktrees.
- Conflicting patches are surfaced, not silently applied.
- Small tasks still use a single agent by default.

### Phase 6 — Quality and v1.0 (2 weeks, then ongoing)

Goal: make releases measurable and contributor-friendly.

- Build evaluations for exploration, bug fixing, test repair, instruction following,
  permission enforcement, and checkpoint recovery.
- Track success, regressions, usage, tool failures, approvals, and latency.
- Add optional redacted OpenTelemetry export, disabled by default.
- Stabilize extension contracts before adding plugin packaging.
- Publish architecture decisions, extension examples, threat model, security policy,
  and contributor setup.
- Gate releases on Linux and macOS; document the Windows/WSL support tier.

Exit criteria:

- Release candidates pass deterministic safety and regression evaluations.
- Public extension contracts are versioned with compatibility rules.
- Installation, first run, provider setup, and sandbox diagnostics work cleanly.

## 9. Prioritized backlog

### P0 — Foundation

1. Fix demo mode and output configuration.
2. Add project tests and CI.
3. Introduce versioned event and error models.
4. Implement provider and tool interfaces.
5. Build repository-safe filesystem, search, patch, Git, and shell tools.
6. Build the single-agent tool loop.
7. Add enforced permissions and command isolation.
8. Add session persistence and checkpoints.

### P1 — Public beta

1. Streaming REPL and slash commands.
2. Plan, implement, review, diff, undo, compact, and resume workflows.
3. AGENTS.md instruction hierarchy.
4. OpenAI, Anthropic, and local provider support.
5. Structured non-interactive execution.
6. Hooks and MCP.
7. Usage, budget, and failure visibility.

### P2 — Differentiators

1. Worktree-isolated parallel agents.
2. Auditable project memory stored as user-visible files.
3. Plugin packaging and discovery.
4. Browser and image tools.
5. Cloud/offloaded workers.
6. IDE integration through a local app-server protocol.

## 10. First two sprints

### Sprint 1 — Reliability baseline

- Move the existing pipeline under src/legacy without behavior changes.
- Fix demo routing and output override.
- Harden file containment and temporary directory handling.
- Add typed errors and remove silent completion on malformed output.
- Add pytest, Ruff, mypy, and CI.
- Add offline end-to-end coverage for generate --demo.

Deliverable: a trustworthy v0.2 release of the current product.

### Sprint 2 — Read-only repository agent

- Add ModelProvider, ModelEvent, Tool, ToolResult, and event-store contracts.
- Add repository discovery and AGENTS.md loading.
- Implement read-only file, search, Git, and safe shell tools.
- Implement the async model/tool loop with streaming and cancellation.
- Add interactive plan mode and exec --read-only.
- Add Python, JavaScript, and mixed-language repository fixtures.

Deliverable: the agent can explain a repository, investigate a bug, and produce a
grounded implementation plan without modifying the workspace.

## 11. Testing strategy

### Unit tests

- Path normalization, symlinks, ignore patterns, and containment.
- Command parsing, risk classification, policy precedence, and reusable rules.
- Provider event normalization and retry/error mapping.
- Tool schemas, truncation, redaction, and event serialization.
- Instruction discovery and nested precedence.
- Checkpoint create/restore for create, edit, delete, rename, and binary files.

### Integration tests

- Fake providers drive deterministic tool-call sequences.
- Every permission profile is tested against allowed and forbidden operations.
- Sandbox escape attempts verify filesystem and network enforcement.
- Session interruption/resume verifies idempotency.
- Fake MCP servers verify discovery, calls, timeouts, approvals, and redaction.
- Worktree tests verify isolation and conflict reporting.

### Agent evaluations

- Locate the correct files before editing.
- Produce minimal patches and preserve unrelated user changes.
- Select and run relevant tests.
- Follow nested instructions and explicit constraints.
- Ask when required authority is missing.
- Recover from failures without loops.
- Report changes, validation, and remaining risk accurately.

## 12. Key risks

| Risk | Mitigation |
|---|---|
| UI built before runtime contracts stabilize | Keep rendering event-driven and make headless tests the first consumer. |
| Prompt rules treated as security | Enforce boundaries outside the model in policy and sandbox layers. |
| Multi-agent overuse | Require isolated context or parallelizable work to justify delegation. |
| Provider abstraction hides useful features | Normalize common events while exposing capability discovery. |
| Session storage leaks secrets | Redact before persistence and test every export path. |
| Undo overwrites user edits | Record ownership/preimages and detect external modifications. |
| Shell output exhausts context | Store full output as an artifact and return bounded summaries. |
| Scope expands too quickly | Treat P0/P1 as the product and defer cloud, IDE, browser, and marketplace. |

## 13. Definition of v1.0

A developer can safely open an existing repository, ask the agent to investigate and
implement a change, review meaningful actions, validate in an enforced sandbox,
inspect or undo the diff, resume later, and automate the same workflow in CI. This
works with multiple model providers and does not require the legacy greenfield
pipeline.
