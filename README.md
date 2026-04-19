# NOVALI

**NOVALI** is an experimental, operator-facing, governed agent framework for directive-driven work, bounded continuation, reviewable self-improvement, and evidence-preserving external-adapter readiness.

It is built around a simple principle:

> useful long-running agent behavior should stay **bounded, legible, resumable, observable, replayable, and governed**.

---

## Current status

- **Latest confirmed milestone:** `v7rc00 topology-corrected`
- **Active development line:** `novali-v7`
- **Active physical source root:** `novali-v7`
- **Canonical packaged handoff:** `dist/novali-v7_rc00-standalone.zip`
- **Canonical packaged root:** `dist/novali-v7_rc00-standalone`
- **Canonical image archive:** `dist/image/novali-v7-standalone.tar`
- **Frozen historical reference:** `novali-v6 rc88.1`

`v7rc00` is a clean active baseline reset from the final `novali-v6` line. It is not a behavior-expansion milestone. It preserves the validated v6 governance, observability, replay, review, rollback, alert, read-only adapter, and controller-isolation invariants while moving future development into the physical `novali-v7` source root.

Future development should start from `novali-v7`, not from the frozen `novali-v6` reference tree.

NOVALI currently supports:

- shell-first packaged startup on localhost
- directive-first initialization
- trusted-source validation in-session
- governed execution after bootstrap
- same-session bounded continuation
- intervention-aware resume loops
- durable attention and handoff memory
- truthful cross-session portfolio and manager queues
- deferred-pressure response outcome tracking
- collector-first OpenTelemetry instrumentation
- LogicMonitor-compatible telemetry export through an OpenTelemetry Collector
- shell-visible observability and telemetry shutdown status
- local evidence-only operator alerts
- generic external adapter membrane
- review, replay, rollback, and checkpoint evidence linkage
- inactive/mock-only controller-isolation lanes
- generic non-network read-only fixture adapter proof
- package-truth validation from fresh unpacked handoffs

---

## What NOVALI is

NOVALI is a **bounded, governed agent system**.

It is designed to be:

- **directive-first**
- **artifact-governed**
- **operator-readable**
- **runtime-bounded**
- **workspace-scoped**
- **observable**
- **replayable**
- **reviewable over time**

NOVALI is **not** an unrestricted autonomous system.

Governance truth lives in persisted artifacts. The UI is an operator surface over that governed state — not a second authority source. Telemetry, alerts, replay packets, review tickets, rollback analyses, and adapter observations are evidence surfaces; they do not become governance authority.

---

## v7rc00 baseline

`v7rc00` establishes the clean active baseline for the next development line.

It carries forward the final v6 capabilities while correcting the version boundary:

- `novali-v6` is frozen as the historical reference at `rc88.1`
- `novali-v7` is the active source root
- `dist/novali-v7_rc00-standalone.zip` is the active packaged handoff
- old v7 artifacts previously built under the v6 tree are superseded
- active v7 package truth now lives under the `novali-v7` directory

The baseline preserves all core invariants:

- Controller remains the sole coordination and adoption authority
- backend truth remains authoritative
- review and intervention gates remain binding
- telemetry is evidence only
- LogicMonitor is observability tooling only
- alerts are evidence only
- alert acknowledgement is not approval
- alert review is not approval
- replay packets are evidence only
- rollback remains evidence-preserving analysis unless separately approved
- read-only observations do not authorize action
- identity lanes remain inactive/mock-only
- no second authority path is introduced

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
9. resume the **same** bounded session through repeated continuation, intervention, and review cycles
10. choose the next session needing attention from a portfolio queue
11. inspect manager/deferred-pressure guidance and response outcomes
12. view observability and telemetry shutdown status
13. inspect local operator alerts and evidence bundles
14. inspect read-only adapter status and mutation-refusal evidence
15. inspect controller-isolation status and identity-bleed findings

### Current operator loop

`load directive -> bootstrap -> governed run -> workspace -> approve/resolve when required -> continue until next bounded stop -> repeat`

### Current portfolio loop

`open shell -> inspect session portfolio -> choose next session needing attention -> resolve / continue -> return to portfolio`

### Current evidence loop

`observation/review condition -> replay packet -> review ticket -> rollback or evidence analysis -> operator-visible alert -> local acknowledgement/review without authority expansion`

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
12. use attention, portfolio, manager, alert, and evidence surfaces to manage bounded continuation

### Default routes

- `/` redirects to `/shell`
- `/workspace` redirects to `/shell/workspace`

The shell is the intended primary operator entry. Legacy routes are compatibility-only.

---

## Core design principles

### 1. Directive-first initialization

NOVALI begins from a structured directive rather than freeform prompting alone.

### 2. Canonical artifact authority

Persisted artifacts define governance truth. Runtime and UI behavior must reflect that truth rather than invent it.

### 3. Bounded execution

Execution stays inside explicit runtime constraints, review gates, workspace boundaries, and operator-visible stop conditions.

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
- what evidence supports a recommendation
- what is blocked pending review

### 7. Evidence preservation

Failure, uncertainty, bad observations, rollback ambiguity, telemetry degradation, and alert conditions should preserve diagnostic evidence rather than hide or erase it.

### 8. Projection-safe state reporting

Critical authority changes, risks, blocked states, and uncertainty should not be hidden by compressed or optimistic summaries.

---

## Execution modes

### Bootstrap-only initialization

Used to create or refresh canonical state for a directive/session.

### Governed execution

Used after initialization when NOVALI resumes under an approved bounded execution profile.

### Bounded long-run supervised continuation

Used **after the first governed seed** to continue the same session across checkpoints, review boundaries, intervention boundaries, and bounded stop conditions.

This is still governed and bounded. It is **not** unrestricted always-on autonomy.

### Read-only fixture observation

Used to validate a generic read-only adapter membrane against local, static, non-network fixtures. This mode observes and records evidence only; it does not mutate source fixtures or external systems.

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
- manager digest, agenda, and throughput state
- deferred queue policy and due-return ordering
- deferred-pressure response outcome tracking
- local operator alert lifecycle evidence
- telemetry shutdown/degradation status

---

## Current operator surfaces

### Shell landing

The shell provides:

- directive loading
- trusted-source onboarding/validation
- bootstrap initialization
- governed execution launch
- portfolio-level session queue
- manager digest and agenda
- deferred-pressure guidance and response outcomes
- observability status
- operator alerts
- read-only adapter status
- controller-isolation status
- recommendation about which session or evidence item needs attention next

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

## Observability

NOVALI includes a collector-first OpenTelemetry foundation.

Telemetry is disabled by default and can be enabled through environment-driven OTLP configuration. The supported posture is:

- emit telemetry to an OpenTelemetry Collector
- use collector processors for redaction, sampling, tagging, batching, and normalization
- export onward to LogicMonitor or another approved collector destination
- keep observability evidence separate from governance authority

Current observability surfaces include:

- shell-visible observability status
- resource identity for active package/version
- traces, metrics, and structured redacted events
- live collector proof history
- Dockerized agent-to-collector proof history
- LogicMonitor portal visibility recorded as human/operator-confirmed evidence
- telemetry shutdown cleanup and degraded-state classification

Important boundaries:

- LogicMonitor is tooling/evidence only
- OpenTelemetry is evidence transport only
- collector availability is not required for NOVALI startup
- telemetry failure does not authorize or block work by itself
- telemetry status must not expose credentials, headers, raw secrets, or raw stack traces

---

## Operator alerts

NOVALI includes a local evidence-only operator alert loop.

Alerts may be raised from:

- read-only adapter validation failures
- mutation-refusal events
- evidence-integrity failures
- source immutability failures
- wrong-lane attribution
- controller-isolation findings
- telemetry shutdown/export degradation
- review-hold or checkpoint concerns
- rollback ambiguity
- redaction failures
- scope-expansion pressure

Alert lifecycle actions include:

- acknowledge
- mark reviewed
- close evidence-only
- supersede

These actions are local evidence records. They do **not** approve mutation, authorize external action, override review gates, or change governance truth.

---

## External adapter posture

NOVALI has a generic external-world adapter membrane and a read-only fixture adapter proof.

Current adapter capabilities are intentionally bounded:

- generic adapter contract
- mock/no-op external adapter lifecycle
- replay packets
- rollback analysis
- kill-switch evidence
- review-ticket integration
- read-only fixture ingestion
- schema and integrity validation
- mutation refusal
- source immutability proof
- lane attribution

Current adapter boundaries:

- no real external connector is active
- no network read-only connector is active
- no mutation connector is active
- read-only observations are evidence only
- replay packets are evidence only
- review tickets are operator-visible gates, not executors

---

## Controller isolation

NOVALI includes inactive/mock-only controller-isolation primitives.

The current isolation model defines three identity lanes:

- `lane_director`
- `lane_sovereign_good`
- `lane_sovereign_dark`

These are **identity namespaces**, not independent runtime controllers.

They provide:

- separated doctrine, memory, summary, intervention, replay, and review namespaces
- Director-mediated cross-lane message envelopes
- identity-bleed detection
- operator-visible review evidence for high/critical findings
- lane-aware telemetry dimensions

Current boundaries:

- lanes are inactive by default
- lanes are mock-only
- lanes have no adoption authority
- lanes have no coordination authority
- lanes cannot execute external actions
- no hidden shared scratchpad is allowed

---

## Review, replay, and rollback

NOVALI preserves evidence around uncertain or unsafe conditions.

Current evidence structures include:

- replay packets
- review tickets
- rollback analyses
- checkpoint references
- prior-stable-state references
- evidence bundles
- mutation-refusal records
- identity-bleed findings
- telemetry degradation alerts

Rollback remains analysis-first and evidence-preserving. It does not silently restore real runtime state unless a future approved workflow explicitly allows that behavior.

---

## Current bounded delegation paths

NOVALI currently supports a narrow, governed set of bounded paths under Controller authority:

- `local`
- `librarian`
- `verifier`
- `sequential_librarian_then_verifier`

These remain intentionally limited and reviewable.

Child/helper roles do not become governance authority or adoption authority.

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
- treat telemetry, alerts, or external observations as governance authority
- operate outside bounded runtime/workspace rules
- mutate external systems

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
- optional collector-backed observability

### Not the current target

The following remain deferred:

- Kubernetes runtime target
- broad multi-agent orchestration
- real external connectors
- external mutation connectors
- external alert delivery as a core requirement
- automatic rollback against real runtime state
- independent autonomous controller processes

---

## Current product phase

NOVALI is now best described as:

**a governed, packaged, operator-facing, observable, evidence-preserving bounded continuation framework**

What is already demonstrated:

- packaged shell-first operator flow
- governed execution after initialization
- same-session bounded continuation
- durable re-entry and handoff summaries
- local attention delivery
- actionable packet jumps
- stale-attention triage
- truthful cross-session portfolio queue
- manager/deferred-pressure outcome loop
- collector-first observability
- LogicMonitor-visible traces through an OpenTelemetry Collector
- generic external adapter membrane
- review/replay/rollback evidence linkage
- inactive/mock-only controller isolation
- generic non-network read-only fixture observation
- local evidence-only operator alerts
- clean v7 source-root topology

What remains intentionally bounded:

- no unrestricted autonomy
- no open internet outside approved trusted-source posture
- no independent controller authority
- no broad multi-agent swarm behavior
- no second authority path
- no external mutation connector
- no real network read-only connector
- no Kubernetes runtime target as the default product path

---

## Version history summary

### Final v6 reference

`novali-v6` is frozen at `rc88.1`.

Final v6 introduced and validated the current generation of:

- observability
- LogicMonitor-compatible collector proof
- generic external adapter membrane
- review/replay/rollback evidence
- controller isolation
- read-only fixture adapter
- operator alert loop
- telemetry shutdown cleanup

### Active v7 baseline

`novali-v7` starts at `v7rc00`.

`v7rc00` is the topology-correct clean baseline for future development. It preserves v6 behavior and invariants while moving active work into the physical `novali-v7` source root.

---

## Final note

NOVALI is an experimental governed-agent product focused on:

- operator legibility
- bounded self-improvement
- durable continuation over time
- truthful attention handling
- stable execution shape
- explicit reviewability
- evidence-preserving observability
- replayable adapter boundaries
- safe versioned evolution

The current `v7rc00` line is a clean baseline for future work — not an expansion of autonomy or authority.