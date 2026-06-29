# Continuity: Agent Harness and Memory Architecture

Status: implementation started
Target: v0.5.0
Updated: 2026-06-29

## Purpose

Continuity turns the repository agent from a bounded in-memory tool loop into a
resumable workflow that can operate across context windows without repeatedly sending
the complete conversation or losing verified task state.

The central distinction is:

> Memory is durable, auditable knowledge. Context is a bounded projection assembled
> for one model request.

Repository files, Git state, tests, and explicit user instructions remain authoritative.
Memory entries must retain provenance and must never silently override those sources.

## Harness lifecycle

Every implementation task will move through an enforced lifecycle:

~~~text
ORIENT -> PLAN -> ACT -> VERIFY -> RECORD -> HANDOFF
             ^          |
             +----------+
~~~

- Orient loads repository identity, instructions, dirty state, active tasks, and the
  latest verified checkpoint.
- Plan selects one bounded objective and explicit acceptance criteria.
- Act executes permission-checked tools against that objective.
- Verify records concrete test, diff, or inspection evidence.
- Record persists events, decisions, failures, artifacts, and task state.
- Handoff emits the compact state required by the next context or resumed session.

A task cannot transition to complete without verification evidence.

## Memory layers

1. Working state: the active objective, constraints, recent failures, and next action.
2. Task ledger: acceptance criteria, priority, status, blockers, and verification.
3. Session history: append-only turns, tool calls, usage, checkpoints, and handoffs.
4. Repository memory: scoped instructions, symbols, commands, architecture, and
   content-hash-aware facts.
5. Procedural memory: verified reusable workflows promoted from successful traces.
6. Artifact storage: immutable full logs and large outputs referenced from compact
   events and model messages.

SQLite is the indexed source for sessions, events, tasks, and later memory metadata.
Large payloads use content-addressed SHA-256 blobs. SQLite FTS5, paths, symbols, and
Git metadata will be the first retrieval layer; embeddings remain optional.

## Context assembly

The context compiler:

- reserves capacity for model output;
- keeps stable instructions before dynamic task state;
- always retains the initial user objective;
- treats an assistant tool call and its tool results as one atomic block;
- keeps the newest complete blocks that fit;
- truncates only the newest block when it cannot fit whole;
- emits estimated, dropped, and truncated token accounting;
- fails explicitly when mandatory instructions and task state exceed the budget.

Provider-specific tokenizers can implement the token-estimator contract. The default
uses a conservative four-characters-per-token estimate.

## Implemented foundation

- Token-bounded context compiler and runtime context-preparation events.
- Provider usage accumulation in runtime results and events.
- SQLite session records and append-only runtime events.
- Structured task ledger with verification-gated completion.
- Compact task-state serialization for model context.
- Immutable content-addressed artifact storage.
- Artifact-backed truncation of oversized tool results.
- Provenance fields on tool-completion events for artifact lookup.
- Normalized user, assistant, tool-call, and tool-result message persistence.
- Provider-safe replay that marks interrupted tool calls without rerunning them.
- Persistent runtime sessions with global turn numbering across process restarts.
- Durable harness phase, transition history, and optimistic revision checks.
- Atomic task, phase, and session-status transitions at lifecycle boundaries.
- The ORIENT, PLAN, ACT, VERIFY, RECORD, HANDOFF, and terminal COMPLETE lifecycle.

These contracts are exposed as Python APIs but not yet through the interactive CLI.
Cross-session semantic and procedural memory retrieval is not yet implemented.

## Next implementation slices

### Durable interactive sessions

- Add JSONL export, retention controls, corruption recovery, and schema migrations.
- Expose session list, status, replay, and resume through the interactive CLI.
- Persist checkpoints and workspace ownership alongside the lifecycle state.

### Harness controller

- Add checkpoint requirements before mutating ACT operations.
- Generate orientation and handoff packets from repository and verification evidence.
- Connect the ledger to plan, implement, review, and status commands.

### Repository memory

- Add provenance-bearing facts, decisions, procedures, and supersession.
- Invalidate memories by branch, commit, path, and content hash.
- Add FTS5 and symbol-aware retrieval with a strict token packer.
- Add inspect, pin, correct, forget, and explain-selection commands.

### Evaluation and release

- Compare full-history, recent-window, summary, and hybrid context strategies.
- Test interruption, contradiction, stale branches, secrets, and repository isolation.
- Measure task success, input tokens, cached tokens, retrieval use, latency, and cost.

## v0.5.0 release gates

- At least 50% median input-token reduction on long repository workflows.
- No more than two percentage points of short-task success regression.
- Resume orientation in one model turn for 95% of deterministic cases.
- No stale or cross-repository memory use in the adversarial evaluation suite.
- No persisted secrets in redaction tests.
- Provenance for every durable memory injected into model context.
- Deterministic event replay and tested schema migrations.
- No provider request exceeding its configured context budget.
