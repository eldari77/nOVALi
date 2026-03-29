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

NOVALI is currently in a **working standalone product phase** built around a packaged Docker handoff and a browser-based localhost operator UI. The current canonical packaged handoff is:

- **`novali-v6_rc40-standalone.zip`**

Current branch posture:

- **active development line:** `novali-v6`
- **frozen reference / trusted preserved-source baseline:** `novali-v5`

Current architecture posture:

- **Controller-only coordination and adoption authority**
- **single-generation bounded delegation**
- **trusted sources as evidence-only, not governance authority**
- **advisory-only recommendation, governance, guidance, and demo layers**
- **packaged standalone delivery with bundled image archive**
- **conservative default posture with explicit reviewability**

At this point, NOVALI is best understood as a **governed standalone operator product** with bounded external evidence support, bounded specialist delegation, bounded operator decision support, and a now-demonstrated bounded trusted-source demo path. :contentReference[oaicite:2]{index=2}

---

## What rc40 adds

Rc40 consolidates the existing demo work into a single operator-readable story without broadening execution authority or changing the bounded path set.

New rc40 capabilities include:

- persisted **demo storyline** artifacts
- persisted **presentation summary** artifacts
- persisted **narration guide** artifacts
- persisted **review-readiness explanation** artifacts
- a visible **ordered proof chain** across the full trusted-source demo
- a clearer explanation of **why the result still truthfully ends at `awaiting_review`**

The proof chain now reads, in order:

- local-first baseline
- knowledge gap identified
- narrow escalation justified
- live external response received
- knowledge incorporated
- reusable skill artifact updated
- outputs improved
- awaiting review

Rc40 remains intentionally conservative:

- storyline and narration are **advisory only**
- no auto-delegation
- no auto-adoption
- no policy mutation
- no second authority path
- no new specialist roles
- no recursive delegation
- no autonomous research mode by default
- no broader orchestration substrate
- no Kubernetes runtime target

Rc40 improves presentation coherence only. It does not broaden mission-path behavior. :contentReference[oaicite:3]{index=3}

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

The current demo path now also supports:

1. a **local-first bounded baseline demo**
2. a **trusted-source-capable demo scenario**
3. a **bounded live external proof step**
4. a **reviewable before/after improvement story**
5. a **review-gated final presentation state**

That gives NOVALI a credible packaged demo path without claiming unrestricted autonomy. :contentReference[oaicite:4]{index=4}

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
- **Governance summary**: consolidated operator-readable view of current bounded governance state
- **Governance trend / temporal drift**: bounded visibility into how that state is changing over time
- **Operator guidance**: bounded next-step decision support for the human operator
- **Demo storyline**: a bounded operator-readable proof chain explaining what the trusted-source demo showed and why review still remains appropriate



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

These paths are operator-readable, artifact-backed, and intentionally limited in scope. Rc40 did not broaden this path set. 

---

## Current Governance, Guidance, and Demo Stack

The current `novali-v6` line includes a layered bounded stack over the four existing paths:

- **delegation structure**
- **delegation evidence**
- **recommendation quality**
- **recommendation audit and calibration**
- **recommendation stability / evidence-window governance**
- **recommendation governance controls and override visibility**
- **operator-intervention audit**
- **intervention prudence / trust-signal visibility**
- **consolidated governance summary**
- **governance trend / temporal drift visibility**
- **operator decision support / action guidance**
- **operator action-readiness / guided handoff**
- **operator flow coherence / demo-readiness**
- **bounded demo-scenario scaffolding**
- **demo execution evidence / result capture**
- **demo output completion / reviewable artifact generation**
- **trusted-source demo candidate and on-disk directive**
- **live trusted-source connectivity validation**
- **live trusted-source demo result improvement**
- **demo storyline / presentation / narration / review-readiness consolidation**

This stack is intended to improve readability, operator judgment, and reviewability, not to replace operator authority. :contentReference[oaicite:7]{index=7}

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

This allows NOVALI to produce useful outputs without unrestricted write access across the repository or package. :contentReference[oaicite:8]{index=8}

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
- bounded specialist delegation through:
  - `local`
  - `librarian`
  - `verifier`
  - `sequential_librarian_then_verifier`
- bounded operator decision support through:
  - governance summary
  - trend / temporal drift visibility
  - suggested next action
  - action guidance
  - why-not-other-actions visibility
  - readiness / guided handoff visibility
- bounded demo support through:
  - a packaged local-first baseline demo
  - a trusted-source-capable demo scenario
  - a live external connectivity proof
  - a live before/after improvement demonstration
  - a consolidated storyline and review-readiness explanation

This means NOVALI is no longer just an initialization shell. It is now an **experimental governed improvement system** with a browser operator surface, bounded external evidence support, explicit bounded delegation structure, advisory-only operator guidance, and a reviewable trusted-source demo path. 

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
- operator-configured governance over external trusted-source usage
- bounded live external connectivity validation
- bounded incorporation of external evidence into reviewable outputs
- bounded reusable skill-artifact updates derived from trusted-source-supported work

Rc40’s trusted-source demo story now explicitly explains the whole chain from local insufficiency to narrow escalation to live evidence receipt to skill-artifact update, while still keeping the final state review-gated. 

---

## Demo State

NOVALI now has a bounded packaged demo track with two important layers:

### 1. Local-first baseline demo
A packaged bounded walkthrough that proves the operator flow, produces reviewable outputs, and stays inside the `local` path.

### 2. Trusted-source growth demo
A bounded trusted-source scenario that shows:

- local-first analysis
- explicit knowledge-gap detection
- narrow trusted-source escalation
- live external response receipt
- knowledge incorporation
- reusable skill-artifact update
- improved outputs
- final `awaiting_review` governance state

The current demo story is intentionally truthful:

- it shows meaningful improvement
- it does not hide unresolved review gates
- it does not pretend external evidence becomes governance authority
- it does not use a demo-only runtime path

This is a governed demo of **bounded growth and self-structuring**, not a claim of unrestricted autonomy. :contentReference[oaicite:11]{index=11}

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
- observability over mission state, artifact state, trusted-source policy state, delegation state, governance state, and guidance state
- review workspace visibility for pending decisions and intervention paths
- operator-visible delegation path, blocked options, and typed handoff state
- operator-visible governance summary
- operator-visible governance trend / temporal drift
- operator-visible suggested next action
- operator-visible action guidance
- operator-visible why-not-other-actions context
- operator-visible demo storyline
- operator-visible ordered proof chain
- operator-visible presentation summary
- operator-visible narration guide
- operator-visible review-readiness explanation

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

Kubernetes is **not** the current standalone target. :contentReference[oaicite:13]{index=13}

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
- auto-delegate based on summary, trend, guidance, or demo layers
- auto-adopt operator guidance as execution policy
- convert trusted-source evidence into governance authority
- hide review-gated states behind demo polish

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

It should not be treated as proof of a scientific claim. :contentReference[oaicite:15]{index=15}

---

## Current Product Phase

NOVALI is now best described as:

**Governed, operator-facing, delegation-capable, externally-capable, packaging-complete, demo-capable, and review-gated by design**

That means:

- major governance/control-plane layers are functioning
- trusted-source integration is bounded and policy-governed
- the packaged standalone handoff is self-contained
- bounded specialist delegation is first-class and artifact-backed
- bounded governance and guidance summaries are operator-visible
- bounded trusted-source live connectivity is proven
- bounded trusted-source demo improvement is proven
- the demo is now narratable and presentation-ready without hiding the review gate

Current effort is focused on operator control, mission usefulness, disciplined capability growth, and repeatable demo presentation. :contentReference[oaicite:16]{index=16}

---

## Intended Use Cases

NOVALI is being built for tasks such as:

- governed autonomous planning
- structured bounded coding runs
- agent-initialized implementation work inside approved workspaces
- auditable improvement of successor artifacts under explicit safety constraints
- bounded acquisition of external implementation knowledge when local knowledge is insufficient
- product/research workflows that need inspectable operator oversight
- bounded operator-supervised decision support over evolving governance state
- bounded trusted-source-assisted artifact generation and skill-pack growth
- bounded live demo scenarios that show improvement without hiding review requirements



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
9. use governance summary, trend, action guidance, and readiness surfaces to supervise next steps
10. use the demo storyline and trusted-source demo surfaces to review the bounded growth path
11. continue NOVALI into bounded work as appropriate



---

## Roadmap

### Active priorities
- improve bounded operator decision support across the existing four delegation paths
- improve mission usefulness under explicit runtime constraints
- keep packaged standalone delivery self-contained and reliable
- preserve auditability as governance, trend, guidance, and demo layers grow
- keep all operator guidance and demo presentation layers advisory-only and artifact-backed
- improve repeatable demo facilitation and reviewable operator runbooks

### Deferred priorities
- automatic live baseline replacement
- recursive delegation
- additional specialist roles without clear bounded evidence
- autonomous research mode as a default posture
- broader writable roots
- Kubernetes-based orchestration
- multi-agent orchestration
- broad multi-scenario demo framework



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

:contentReference[oaicite:20]{index=20}

---

## Contributing

This repository is evolving quickly. If you contribute:

- preserve the directive-first authority chain
- keep operator-owned policy frozen and auditable
- do not casually broaden write permissions or runtime claims
- preserve Controller-only authority unless a phase explicitly revisits it
- prefer bounded, testable improvements over speculative rewrites
- keep Docker standalone and Kubernetes orchestration concerns separate
- keep guidance, summary, trend, trusted-source, and demo layers advisory-only unless a future phase explicitly revisits that posture

A future CLA or contribution policy may be introduced to preserve consistent commercial licensing rights. 

---

## Disclaimer

NOVALI is an experimental governed-agent framework. It is not a general unrestricted autonomous system and should not be treated as one. Use it with explicit operator oversight and bounded runtime policies. :contentReference[oaicite:22]{index=22}