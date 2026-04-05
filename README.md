# NOVALI

**NOVALI** is an experimental governed-agent framework for building agents that initialize from explicit directives, operate inside bounded runtime constraints, improve through auditable work, and remain legible to the operator throughout the process.

Current product direction:

**unzip → load bundled Docker image → run packaged launcher → open browser on localhost → land on the Svelte operator shell → initialize NOVALI → continue into bounded governed execution → optionally continue the same bounded session through long-run supervised continuation**

---

## What NOVALI is

NOVALI is **not** an unrestricted autonomous system.

It is designed to be:

- **directive-first**
- **artifact-governed**
- **runtime-bounded**
- **operator-readable**
- **workspace-scoped for self-improvement**
- **conservative by default**

NOVALI keeps authority in persisted governance artifacts rather than letting runtime behavior become the source of truth. The browser UI is the operator surface over a governed execution chain.

---

## Current Status

NOVALI is currently in a **working standalone product phase** built around a packaged Docker handoff and a browser-based localhost operator UI.

### Latest confirmed milestone
- **`rc60`**

### Canonical packaged handoff
- **`novali-v6_rc60-standalone.zip`**

### Active branch posture
- **active development line:** `novali-v6`
- **frozen reference / trusted preserved-source baseline:** `novali-v5`

### Current architecture posture
- **Controller-only coordination and adoption authority**
- **single-generation bounded delegation**
- **trusted sources as evidence-only, not governance authority**
- **governed mutable shell over an immutable conceptual core**
- **packaged standalone delivery with bundled image archive**
- **bounded long-run supervised continuation after first governed seed**
- **conservative default posture with explicit reviewability**

At this point, NOVALI is best understood as a **governed standalone operator product** with bounded external evidence support, bounded specialist delegation, a packaged browser-first operator workflow, and now-demonstrated packaged bounded continuation from the Operator Workspace.

---

## What rc60 adds

`rc60` closes the main packaged operator path from initialization through bounded continuation.

### rc60 outcomes
- packaged startup through the browser operator path is materially more robust
- shell status endpoints return valid JSON from fresh packaged state
- the default packaged entry lands on the newer Svelte shell
- trusted-source setup is more coherent and remains session-only
- landing now shows operator-safe startup/progress feedback
- long-run supervised mode is more discoverable in the shell/workspace
- the governed launch path no longer clicks through from bootstrap-only policy into an invalid governed start
- end-to-end packaged proof now covers:
  - directive load
  - trusted-source validation
  - bootstrap
  - governed preparation
  - first governed execution
  - workspace redirect
  - same-session bounded continuation from the workspace without reseed

### Current bounded-continuation proof
The current packaged operator proof shows that NOVALI can:
- seed a governed session
- checkpoint bounded progress
- resume the **same** long-run session from the Operator Workspace
- advance checkpoint/cycle state without directive reload, bootstrap restart, or reseed
- stop cleanly on an explicit bounded reason when budget is exhausted

---

## Current Product Shape

The near-term standalone deployment target is:

- a **zip-delivered package**
- containing a **bundled Docker image archive**
- launched with a **browser-based localhost operator UI**
- for initializing and running a **single governed NOVALI agent**

### Current golden path
1. unpack the handoff package
2. load the bundled Docker image archive
3. run the packaged launcher
4. open the browser UI on localhost
5. land on the Svelte shell (default `/` entry)
6. load a directive
7. optionally validate a trusted-source provider credential for the current session
8. run **Bootstrap Initialization**
9. use **Prepare governed execution** when required
10. run **Governed Execution Run**
11. continue in **Operator Workspace**
12. when appropriate, continue the same bounded session through the **Bounded Continuation Pilot** / long-run supervised path

### Default route behavior
- `/` redirects to `/shell`
- `/workspace` redirects to `/shell/workspace`
- legacy pages are compatibility-only paths, not the primary operator entry

---

## Core Design Principles

### 1. Directive-first initialization
NOVALI initializes from a formal directive bootstrap file rather than freeform prompting alone.

### 2. Canonical artifact authority
Governance truth lives in persisted artifacts, not in ad hoc runtime state.

### 3. Bounded execution
NOVALI operates inside operator-owned runtime constraints and cannot casually broaden its own permissions.

### 4. Governed self-improvement
Improvement is limited to approved mutable work areas and reviewed bounded flows.

### 5. Trusted-source discipline
Trusted sources are bounded evidence channels, not the governance source of truth.

### 6. Auditability over cleverness
NOVALI prefers explicit structure, inspectable changes, and stable policy over opaque capability growth.

---

## Architecture Overview

NOVALI currently uses a browser-first operator flow over a governed execution chain:

`browser UI → launcher → directive load → bootstrap → governed execution → workspace continuation`

Key concepts:

- **Directive bootstrap**: structured initialization intent
- **Frozen operator session**: effective runtime policy and launch constraints
- **Runtime envelope**: bounded execution profile and backend
- **Trusted sources**: operator-approved evidence channels
- **Active workspace**: bounded writable build area for governed runs
- **Canonical artifacts**: persisted authority surfaces used to drive state and decisions
- **Governed long-run session**: persisted session/checkpoint state for bounded continuation
- **Supervisor / lease model**: bounded ownership and recovery structure for continued sessions
- **Operator guidance**: bounded next-step decision support for the human operator

---

## Execution Modes

### Bootstrap-only initialization
Used to create canonical state for a new directive or session.

### Governed execution
Used after initialization when NOVALI resumes under an approved bounded execution profile.

### Bounded long-run supervised continuation
Used **after the first governed seed** to continue the same session through bounded checkpoints, operator-visible lifecycle state, and explicit pause/resume/stop semantics.

This is still bounded and governed. It is not unrestricted always-on autonomy.

---

## Current Bounded Delegation Paths

NOVALI currently supports a narrow set of bounded paths under Controller authority:

- **Local** — Controller keeps the mission local
- **Librarian** — bounded library / reference / knowledge-hygiene support
- **Verifier** — bounded readiness / integrity / contract-compliance checking
- **Sequential Librarian → Verifier** — fixed two-step bounded delegation with explicit typed handoff

These paths are operator-readable, artifact-backed, and intentionally limited in scope.

---

## Current Long-Run / Continuation Capabilities

NOVALI now supports bounded long-run session state with:

- checkpointed continuation
- resume from the latest valid checkpoint
- explicit lifecycle state
- explicit halt/completion reasons
- duplicate-launch blocking
- supervisor/lease visibility
- pause / resume / stop controls
- operator-visible checkpoint and cycle state

Current long-run posture:
- continuation begins only after the first governed seed
- continuation remains workspace-scoped and bounded
- restart/resume is governed and artifact-backed
- broader always-on autonomy is still **not** assumed

---

## Active Workspace Model

For coding-capable runs, NOVALI writes only inside a governed workspace such as:

`novali-active_workspace/<workspace_id>/`

Typical subfolders include:

- `src/`
- `tests/`
- `docs/`
- `artifacts/`
- `plans/`

This allows NOVALI to produce useful outputs without unrestricted write access across the repository or package.

---

## What NOVALI can currently do

The current `novali-v6` line can support, in bounded form:

- browser-first bootstrap and resume flows
- bounded governed execution
- directive-guided planning and implementation cycles
- trusted-source provider validation in the packaged UI
- bounded external evidence acquisition and reuse
- review / promotion / admission flows
- bounded specialist delegation through:
  - `local`
  - `librarian`
  - `verifier`
  - `sequential_librarian_then_verifier`
- operator-readable system state, readiness, and intervention context
- packaged startup guidance and directed launch flow
- long-run workspace continuation after first seed
- checkpointed bounded continuation with explicit stop reasons

This means NOVALI is no longer just an initialization shell. It is an **experimental governed improvement system** with a browser operator surface, bounded external evidence support, bounded continuation over time, and explicit artifact-governed control.

---

## Trusted Sources

Trusted sources are bounded evidence channels NOVALI may consult while fulfilling a directive.

Important distinction:

- **Governance truth** = canonical persisted NOVALI artifacts
- **External evidence** = trusted-source channels approved by the operator

Trusted sources can help NOVALI acquire missing implementation knowledge, but they do **not** replace governance authority.

NOVALI currently supports:

- operator-visible provider onboarding in the packaged UI
- session-only credential validation
- bounded live external connectivity proof
- provenance-preserving evidence use
- reuse vs re-query decisions
- supersession and invalidation hygiene
- bounded incorporation of external evidence into reviewable outputs

---

## Operator Experience

NOVALI is designed to be usable from a packaged localhost browser UI.

Current operator-facing capabilities include:

### Landing / startup
- default landing on the newer Svelte shell
- integrated startup / initialization guidance
- stage-gated startup actions:
  - **Load Directive**
  - **Bootstrap Initialization**
  - **Governed Execution Run**
- explicit governed-preparation flow when runtime policy is not yet ready
- trusted-source credential flow that remains session-only
- startup/progress feed with operator-safe status updates

### Workspace
- redirect into **Operator Workspace** after governed start
- live state/event surfaces for runtime progress
- intervention and review visibility
- long-run supervised continuation visibility
- checkpoint / cycle / lifecycle summaries
- bounded continuation controls

### Compatibility
- legacy routes still exist only for compatibility/fallback use
- the intended primary operator entry is the shell, not the legacy HTML surface

---

## Deployment Modes

### Docker standalone
This is the primary deployment path today.

Use this when you want:

- one agent
- one container
- one localhost browser UI
- one bounded operator session

### Kubernetes orchestration
Deferred future phase.

Intended for:

- multi-agent deployment
- stronger orchestration and scheduling
- broader infrastructure control

Kubernetes is **not** the current standalone target.

---

## Safety and Governance Posture

NOVALI is conservative by design.

By default, it does **not** assume permission to:

- mutate protected core files
- broaden routing or thresholds casually
- alter live policy without governed pathing
- expand external access without bounded policy
- self-authorize structural adoption
- add new specialist roles without explicit governed work
- recurse into broader delegation trees
- claim unsupported runtime guarantees
- bypass operator-owned constraints
- convert trusted-source evidence into governance authority
- broaden bounded continuation into unrestricted autonomy
- hide review-gated or bounded-stop states behind UI polish

The system is meant to support **bounded progress**, not unconstrained autonomy.

---

## Conceptual Reference

NOVALI uses the **9D Theorem whitepaper** as a conceptual reference for planning and architecture review.

That whitepaper should be treated as:

- **exploratory**
- **speculative**
- **not established science**

Operationally, it is used as a disciplined lens for:

- projection safety
- coherence over time
- hidden-structure awareness
- self-model quality
- perspective stability
- bounded improvement with explicit review

It should not be treated as proof of a scientific claim.

---

## Current Product Phase

NOVALI is now best described as:

**Governed, operator-facing, packaged, trusted-source-capable, bounded-continuation-capable standalone agent framework**

What is now demonstrated:

- packaged startup on localhost
- shell-first operator flow
- directive-first initialization
- coherent trusted-source validation
- governed execution after preparation
- workspace redirect and live operator surface
- same-session bounded continuation from the workspace

What remains intentionally bounded:

- no unrestricted autonomy
- no open internet outside approved trusted-source posture
- no recursive delegation
- no swarm / broad multi-agent orchestration
- no Kubernetes runtime target
- no second authority path

---

## Recommended First Run

For a clean first run from the packaged handoff:

1. unpack the package
2. load the bundled image archive
3. run the packaged browser operator launcher
4. open the base localhost URL
5. load a directive
6. validate trusted-source credentials only if needed for the task, and only for the current session
7. run bootstrap
8. prepare governed execution if prompted
9. run governed execution
10. continue in the workspace
11. use bounded continuation only after the first governed seed has materialized the session

---

## Final Note

NOVALI should be understood as an **experimental governed-agent product** designed for bounded self-improvement, operator legibility, and stable execution shape over time.

The current system demonstrates meaningful progress in:
- operator usability
- packaged delivery
- trusted-source integration
- governed execution
- checkpointed bounded continuation

But it remains intentionally conservative about authority, scope expansion, and autonomy.