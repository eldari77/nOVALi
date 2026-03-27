# NOVALI

**NOVALI** is an experimental governed-agent framework for building agents that initialize from explicit directives, operate inside bounded runtime constraints, improve through auditable work, and remain legible to the operator throughout the process.

Current product direction:

**unzip → load bundled Docker image → run container → open browser on localhost → initialize NOVALI → continue into bounded governed execution**

---

## What NOVALI is

NOVALI is not an unrestricted autonomous system.

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

Current packaged reference:
- **`novali-v6_rc20-standalone.zip`**

Current branch posture:
- **active development branch:** `novali-v6`
- **frozen reference / operator surface baseline:** `novali-v5`

Current architecture posture:
- **Controller-only coordination and adoption authority**
- **single-generation bounded delegation**
- **trusted sources as evidence-only, not governance authority**
- **packaged standalone delivery with bundled image archive**
- **conservative default posture with explicit reviewability**

At this point, NOVALI is best understood as a **governed standalone operator product** with bounded external evidence support and bounded specialist delegation.

---

## What rc20 added

Rc20 strengthened NOVALI’s bounded delegation layer without broadening authority.

New rc20 capabilities include:

- persisted **mission delegation plans**
- persisted **child admissibility / prerequisite state**
- persisted **blocked delegation alternatives**
- a typed **Librarian → Verifier** handoff contract
- operator-visible delegation state in **Home**, **Observability**, and the **review workspace**

The Controller can now explicitly record and surface why it chose one of the current bounded paths:

- `local`
- `librarian`
- `verifier`
- `sequential_librarian_then_verifier`

Rc20 remains intentionally conservative:

- no new specialist roles
- no recursive delegation
- no autonomous research mode by default
- no broader orchestration substrate
- no Kubernetes runtime target

---

## Current Product Shape

The near-term standalone deployment target is:

- a **zip-delivered package**
- containing a **bundled Docker image archive**
- launched with a **browser-based localhost operator UI**
- for initializing and running a **single governed NOVALI agent**

The current golden path is:

1. unpack the handoff package
2. load the bundled Docker image archive
3. run the packaged launcher
4. open the browser UI on localhost
5. select or generate a directive
6. run **bootstrap-only initialization**
7. transition back to the bounded governed-execution profile
8. continue NOVALI into governed execution when appropriate

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

`browser UI → launcher → frozen session → bootstrap → governed execution`

Key concepts:

- **Directive bootstrap**: structured initialization intent
- **Frozen operator session**: effective runtime policy and launch constraints
- **Runtime envelope**: bounded execution profile and backend
- **Trusted sources**: operator-approved evidence channels
- **Active workspace**: bounded writable build area for governed runs
- **Canonical artifacts**: persisted authority surfaces used to drive state and decisions
- **Delegation plan**: persisted Controller-owned record of why a bounded path was chosen
- **Typed handoff contract**: explicit bounded contract for the current `Librarian -> Verifier` sequence

---

## Execution Modes

### Bootstrap-only initialization
Used to create canonical state for a new directive or session.

### Governed execution
Used after initialization when NOVALI resumes under an approved bounded execution profile.

---

## Current Bounded Delegation Paths

NOVALI currently supports a narrow set of bounded paths under Controller authority:

- **Local** — Controller keeps the mission local
- **Librarian** — bounded library / reference / knowledge-hygiene support
- **Verifier** — bounded readiness / integrity / contract-compliance checking
- **Sequential Librarian → Verifier** — fixed two-step bounded delegation with explicit typed handoff

These paths are operator-readable, artifact-backed, and intentionally limited in scope.

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
- review / promotion / admission flows
- admitted-candidate preservation and comparison
- bounded future-reference-target rollover
- skill-pack-driven quality improvement
- multi-wave campaign management
- campaign-cycle and loop-of-loops governance
- trusted-source evidence acquisition and reuse
- operator-configured external provider validation and handshake
- mission-level trusted-source orchestration across:
  - local-only
  - indexed reuse
  - justified external re-query
  - operator review / escalation control
- operator-facing observability over runtime, campaign, cycle, artifact, trusted-source, and delegation state
- bounded specialist delegation through:
  - `local`
  - `librarian`
  - `verifier`
  - `sequential_librarian_then_verifier`

This means NOVALI is no longer just an initialization shell. It is now an **experimental governed improvement system** with a browser operator surface, bounded external evidence support, and explicit bounded delegation structure.

---

## Trusted Sources

Trusted sources are bounded evidence channels NOVALI may consult while fulfilling a directive.

Important distinction:

- **Governance truth** = canonical persisted NOVALI artifacts
- **External evidence** = trusted-source channels approved by the operator

Trusted sources can help NOVALI acquire missing implementation knowledge, but they do **not** replace governance authority.

NOVALI currently supports:

- bounded trusted-source evidence capture
- provenance-preserving ingestion
- indexed reusable knowledge artifacts
- reuse vs re-query decisions
- supersession and invalidation hygiene
- operator-configurable governance over external trusted-source usage

---

## Operator Experience

NOVALI is designed to be usable from a packaged localhost browser UI.

Current operator-facing capabilities include:

- integrated startup / initialization guidance on Home
- clearer bootstrap-only vs governed-execution transitions
- explicit review-required vs resume-ready vs fresh-start distinctions
- at-a-glance system state, operator attention, current objective, and recommendation
- review / continue / admission / promotion visibility
- packaged trusted-source provider configuration and validation
- observability over mission state, artifact state, trusted-source policy state, and delegation state
- review workspace visibility for pending decisions and intervention paths
- operator-visible delegation path, blocked options, and typed handoff state

The current standalone handoff is intended to be self-contained, including the bundled Docker image archive.

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
- broaden routing or thresholds
- alter live policy
- expand external access without bounded policy
- self-authorize structural adoption
- add new specialist roles without explicit governed work
- recurse into broader delegation trees
- claim unsupported runtime guarantees
- bypass operator-owned constraints

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

**Governed, operator-facing, delegation-capable, externally-capable, and packaging-complete**

That means:

- major governance/control-plane layers are functioning
- trusted-source integration is bounded and policy-governed
- the packaged standalone handoff is self-contained
- bounded specialist delegation is now first-class and artifact-backed
- current effort is focused on operator control, mission usefulness, and disciplined capability growth

---

## Intended Use Cases

NOVALI is being built for tasks such as:

- governed autonomous planning
- structured bounded coding runs
- agent-initialized implementation work inside approved workspaces
- auditable improvement of successor artifacts under explicit safety constraints
- bounded acquisition of external implementation knowledge when local knowledge is insufficient
- product/research workflows that need inspectable operator oversight

---

## Quickstart Concept

The exact packaged flow depends on the current release, but the intended user experience is:

1. install Docker
2. unzip the NOVALI handoff package
3. load the bundled image archive
4. run the packaged launcher
5. open the localhost browser UI
6. choose or generate a directive
7. run bootstrap-only initialization
8. switch back to governed execution
9. continue NOVALI into bounded work as appropriate

---

## Roadmap

### Active priorities
- improve selection quality across the existing bounded delegation paths
- continue bounded successor-improvement work inside `novali-v6`
- improve mission usefulness under explicit runtime constraints
- keep packaged standalone delivery self-contained and reliable
- preserve auditability as external evidence support and delegation structure grow

### Deferred priorities
- automatic live baseline replacement
- recursive delegation
- additional specialist roles without clear bounded evidence
- autonomous research mode as a default posture
- broader writable roots
- Kubernetes-based orchestration
- multi-agent orchestration

---

## Licensing

NOVALI is available under the **Business Source License 1.1 (BSL 1.1)**.

- Source is available for review, modification, redistribution, and non-production use.
- Production use and commercial deployment require a separate commercial license from the Licensor unless an explicit additional grant says otherwise.
- Each released version converts to **Apache License 2.0** on its Change Date.

See:

- [`LICENSE.md`](./LICENSE.md)
- [`COMMERCIAL_USE.md`](./COMMERCIAL_USE.md)
- [`NOTICE.md`](./NOTICE.md)

Commercial licensing contact:  
**eldari77@gmail.com**

---

## Contributing

This repository is evolving quickly. If you contribute:

- preserve the directive-first authority chain
- keep operator-owned policy frozen and auditable
- do not casually broaden write permissions or runtime claims
- preserve Controller-only authority unless a phase explicitly revisits it
- prefer bounded, testable improvements over speculative rewrites
- keep Docker standalone and Kubernetes orchestration concerns separate

A future CLA or contribution policy may be introduced to preserve consistent commercial licensing rights.

---

## Disclaimer

NOVALI is an experimental governed-agent framework. It is not a general unrestricted autonomous system and should not be treated as one. Use it with explicit operator oversight and bounded runtime policies.