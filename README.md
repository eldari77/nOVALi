# NOVALI

**NOVALI** is an experimental, operator-facing, governed agent framework for directive-driven work, bounded continuation, and reviewable self-improvement.

It is built around a simple principle:

> useful long-running agent behavior should stay **bounded, legible, resumable, and governed**.

---

## Current status

- **Latest confirmed milestone:** `rc70`
- **Canonical packaged handoff:** `novali-v6_rc70-standalone.zip`
- **Active development line:** `novali-v6`
- **Reference baseline:** `novali-v5`

NOVALI now supports:

- shell-first packaged startup on localhost
- directive-first initialization
- trusted-source validation in-session
- governed execution after bootstrap
- same-session bounded continuation
- intervention-aware resume loops
- durable attention and handoff memory
- actionable attention-to-packet jumps
- stale-attention triage
- a truthful cross-session operator portfolio queue

---

## What NOVALI is

NOVALI is a **bounded, governed agent system**.

It is designed to be:

- **directive-first**
- **artifact-governed**
- **operator-readable**
- **runtime-bounded**
- **workspace-scoped**
- **reviewable over time**

NOVALI is **not** an unrestricted autonomous system.

Governance truth lives in persisted artifacts. The UI is an operator surface over that governed state — not a second authority source.

---

## What the current product can do

From the packaged handoff, an operator can:

1. start the packaged browser operator
2. land on the Svelte shell by default
3. load a directive
4. validate a trusted-source credential for the current session if needed
5. run bootstrap initialization
6. prepare governed execution
7. launch governed execution
8. continue in the Operator Workspace
9. resume the **same** bounded session through repeated continuation / intervention / review cycles
10. choose the next session needing attention from a portfolio queue

### Current operator loop

`load directive -> bootstrap -> governed run -> workspace -> approve/resolve when required -> continue until next bounded stop -> repeat`

### Current portfolio loop

`open shell -> inspect session portfolio -> choose next session needing attention -> resolve / continue -> return to portfolio`

---

## What rc70 adds

`rc70` is the current canonical milestone.

It adds a **truthful cross-session portfolio queue** so the operator can tell which session needs attention next without manually opening every recent session.

### rc70 outcomes

- top-level portfolio queue on `/shell`
- distinct recent/active session cards
- queue buckets and recommendation text
- direct jump from portfolio to the correct blocking session/action
- preserved same-session identity after queue-based navigation
- healthy packaged validation and package-size hygiene

At this point, NOVALI is no longer just a single-session operator loop. It is now a **bounded multi-session operator portfolio** with governed continuation per session.

---

## Quick start

### Packaged handoff flow

1. unpack the handoff package
2. load the bundled Docker image archive
3. run the packaged browser operator launcher
4. open the localhost URL
5. land on the shell
6. load a directive
7. validate trusted-source credentials only if needed, and only for the current session
8. run bootstrap
9. prepare governed execution if prompted
10. run governed execution
11. continue in the workspace
12. use the attention inbox, handoff summary, and portfolio queue to manage repeat bounded continuation

### Default routes

- `/` redirects to `/shell`
- `/workspace` redirects to `/shell/workspace`

The shell is the intended primary operator entry. Legacy routes are compatibility-only.

---

## Core design principles

### 1. Directive-first initialization
NOVALI begins from a structured directive rather than freeform prompting alone.

### 2. Canonical artifact authority
Persisted artifacts define governance truth. Runtime/UI behavior must reflect that truth rather than invent it.

### 3. Bounded execution
Execution stays inside explicit runtime constraints, review gates, and workspace boundaries.

### 4. Governed self-improvement
Improvement work is allowed only inside reviewable, bounded paths.

### 5. Trusted-source discipline
Trusted sources provide bounded evidence, not governance authority.

### 6. Operator legibility
The operator should be able to tell:
- what changed
- why the session stopped
- what needs attention
- what action resumes work

---

## Execution modes

### Bootstrap-only initialization
Used to create or refresh canonical state for a directive/session.

### Governed execution
Used after initialization when NOVALI resumes under an approved bounded execution profile.

### Bounded long-run supervised continuation
Used **after the first governed seed** to continue the same session across checkpoints, review boundaries, intervention boundaries, and bounded stop conditions.

This is still governed and bounded. It is **not** unrestricted always-on autonomy.

---

## Current long-run capabilities

NOVALI currently supports:

- checkpointed same-session continuation
- resume from latest valid checkpoint
- intervention-required stop states
- post-intervention resume on the same session
- pause / resume / stop controls
- supervisor / lease visibility
- duplicate-launch blocking
- headroom and policy visibility
- operator-editable long-run policy slice
- low-touch continuation until next bounded stop
- durable attention memory
- actionable attention signals
- stale-attention escalation and archive triage
- portfolio-level session selection

---

## Current operator surfaces

### Shell landing
The shell provides:

- directive loading
- trusted-source onboarding/validation
- bootstrap initialization
- governed execution launch
- portfolio-level session queue
- recommendation about which session needs attention next

### Workspace
The workspace provides:

- live session state
- checkpoint / cycle / lifecycle summaries
- policy and headroom visibility
- attention inbox
- intervention/review packet handling
- durable handoff summary
- actionable attention signal
- archive and history views
- continuation controls

---

## Current bounded delegation paths

NOVALI currently supports a narrow, governed set of bounded paths under Controller authority:

- `local`
- `librarian`
- `verifier`
- `sequential_librarian_then_verifier`

These remain intentionally limited and reviewable.

---

## Active workspace model

Coding-capable work occurs inside a governed active workspace such as:

`novali-active_workspace/<workspace_id>/`

Typical subfolders include:

- `src/`
- `tests/`
- `docs/`
- `artifacts/`
- `plans/`

This keeps work bounded and reviewable instead of granting unrestricted write access across the repo or host.

---

## Trusted sources

Trusted sources are bounded evidence channels NOVALI may consult while fulfilling a directive.

Important distinction:

- **Governance truth** = persisted NOVALI artifacts
- **External evidence** = trusted-source channels approved by the operator

Trusted sources may help fill implementation gaps, but they do **not** replace governance authority.

Current product behavior includes:

- session-only credential handling
- operator-visible validation flow
- bounded evidence use
- provenance-aware reuse vs re-query logic
- reviewable incorporation of external evidence

---

## Safety and governance posture

NOVALI is intentionally conservative.

By default, it does **not** assume permission to:

- broaden its own authority
- rewrite governance truth
- bypass review gates
- self-authorize structural adoption
- expand into unrestricted autonomy
- recurse into broad delegation trees
- treat trusted-source evidence as governance authority
- operate outside bounded runtime/workspace rules

The system is built for **bounded progress**, not unconstrained autonomy.

---

## Conceptual reference

NOVALI uses the **9D Theorem whitepaper** as a conceptual reference for planning and architecture review.

It should be treated as:

- exploratory
- speculative
- not established science

Operationally, it is used as a lens for:

- projection safety
- coherence over time
- hidden-structure awareness
- self-model quality
- perspective stability
- bounded, reviewable improvement

---

## Deployment

### Current target
The current supported product target is **Docker standalone** with a localhost browser UI.

Use this when you want:

- one packaged handoff
- one bundled image archive
- one operator-facing browser surface
- one bounded runtime at a time
- one or more recent/active sessions visible in the queue

### Not the current target
Kubernetes, broad multi-agent orchestration, and open-ended external alerting/export are still deferred.

---

## Current product phase

NOVALI is now best described as:

**a governed, packaged, operator-facing, multi-session bounded continuation framework**

What is already demonstrated:

- packaged shell-first operator flow
- governed execution after initialization
- same-session bounded continuation
- durable re-entry and handoff summaries
- local attention delivery
- actionable packet jumps
- stale-attention triage
- truthful cross-session portfolio queue

What remains intentionally bounded:

- no unrestricted autonomy
- no open internet outside approved trusted-source posture
- no multi-agent swarm behavior
- no second authority path
- no external alert/export infrastructure as a core requirement
- no Kubernetes runtime target as the default product path

---

## Final note

NOVALI is an experimental governed-agent product focused on:

- operator legibility
- bounded self-improvement
- durable continuation over time
- truthful attention handling
- stable execution shape
- explicit reviewability

The current `rc70` line shows meaningful progress in product usability, packaged delivery, same-session continuation, and portfolio-scale operator management — while still keeping governance and autonomy intentionally bounded.