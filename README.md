# NOVALI

**NOVALI** is an experimental governed-agent framework built around one core idea: an agent should initialize from a formal directive, operate inside explicit runtime constraints, improve only through bounded and auditable work, and remain understandable to the operator throughout the process.

The current product direction is:

**unzip → load Docker image → run container → open browser on localhost → initialize NOVALI → continue into bounded governed execution**

---

## What NOVALI is

NOVALI is not designed as an unrestricted autonomous system. It is designed to be:

- **directive-first**
- **artifact-governed**
- **runtime-bounded**
- **operator-readable**
- **workspace-scoped for self-improvement**
- **conservative by default**

Instead of letting runtime behavior become the source of truth, NOVALI keeps authority in explicit persisted artifacts and uses the browser UI as the operator surface over a governed execution chain.

---

## Current Status

NOVALI is currently in a **working standalone product phase** built around a packaged Docker handoff and a browser-based localhost operator UI.

Current packaged reference:
- **`novali-v5-standalone-rc42`**

Recent progress has moved NOVALI beyond basic initialization into a much deeper bounded improvement stack, including:

- directive-first bootstrap
- governed execution in bounded active workspaces
- bounded coding profiles
- review / promotion / reseed / continuation flows
- admitted-candidate lifecycle
- future-reference-target rollover
- bounded skill-pack execution for quality improvement
- campaign, campaign-cycle, and loop-level governance
- first productization and guided workflow refinement in the operator UI

At this point, the governance/control-plane stack is stable enough that current effort is shifting toward **product-facing operator experience**, not more governance expansion.

---

## Current Product Shape

The near-term standalone deployment target is:

- a **zip-delivered package**
- containing a **prebuilt Docker image archive**
- launched with a **browser-based localhost operator UI**
- for initializing and running a **single governed NOVALI agent**

The current golden path is:

1. unpack the handoff package
2. load the Docker image archive
3. run the packaged launcher
4. open the browser UI on localhost
5. select or generate a directive
6. run **bootstrap-only initialization**
7. switch back to the bounded governed-execution profile
8. resume NOVALI into governed execution when appropriate

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

---

## Execution Modes

### Bootstrap-only initialization
Used to create canonical state for a new directive/session.

### Governed execution
Used after initialization when NOVALI resumes under an approved bounded execution profile.

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

## What NOVALI can now do

The current `novali-v5` line can now support, in bounded form:

- browser-first bootstrap and resume flows
- bounded governed execution
- directive-guided planning and implementation cycles
- review / promotion / admission flows
- admitted-candidate preservation and comparison
- bounded future-reference-target rollover
- skill-pack-driven quality improvement
- multi-wave campaign management
- campaign-cycle and loop-of-loops governance
- operator-facing observability over runtime, campaign, cycle, and artifact state

This means NOVALI is no longer just an initialization shell. It is now an **experimental governed improvement system** with a browser operator surface.

---

## Operator Experience Direction

Current productization work is focused on making NOVALI easier to use and easier to understand.

Recent operator UX improvements include:

- a clearer staged initialization story
- stronger home/landing guidance
- a more cohesive browser UI
- clearer bootstrap-only vs governed-execution guidance
- more actionable summary layers in observability
- a stronger “what is happening / what next” presentation model

Current visual direction:
- dark primary palette
- green secondary accents
- dark purple tertiary accents
- a restrained **magic + technology** aesthetic

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
- expand external access
- claim unsupported runtime guarantees
- bypass operator-owned constraints

The system is meant to support **bounded progress**, not unconstrained autonomy.

---

## Trusted Sources

Trusted sources are bounded evidence channels NOVALI may consult while fulfilling a directive.

Important distinction:

- **Governance truth** = canonical persisted NOVALI artifacts
- **External evidence** = trusted-source channels approved by the operator

Trusted sources inform work. They do not replace governance authority.

---

## Current Product Phase

NOVALI is now best described as:

**Governance-stable, productizing, and operator-facing**

That means:
- major governance/control-plane layers are functioning
- current effort is moving toward workflow clarity, dashboard actionability, and showcase readiness
- deeper runtime/governance expansion is intentionally paused while product-facing polish improves

---

## Intended Use Cases

NOVALI is being built for tasks such as:

- governed autonomous planning
- structured bounded coding runs
- agent-initialized implementation work inside approved workspaces
- auditable improvement of successor artifacts under explicit safety constraints
- product/research workflows that need inspectable operator oversight

---

## Quickstart Concept

The exact packaged flow depends on the current release, but the intended user experience is:

1. install Docker
2. unzip the NOVALI handoff package
3. load the packaged image archive
4. run the packaged launcher
5. open the localhost browser UI
6. choose or generate a directive
7. run bootstrap-only initialization
8. switch back to governed execution
9. continue NOVALI into bounded work as appropriate

---

## Roadmap

### Active priorities
- refine operator workflow clarity
- improve dashboard actionability and runtime summaries
- continue standalone product polish
- improve showcase/demo quality
- strengthen bounded quality-improvement outputs inside active workspaces

### Deferred priorities
- automatic live baseline replacement
- endless reseeding
- live trusted-source querying
- broader writable roots
- Kubernetes-based orchestration
- multi-agent orchestration
- deeper UX modernization beyond the current productization baseline

### Deferred UX track
A future operator UX pass is planned around:
- a more modern **magic + technology** visual treatment
- stronger directive-core presentation
- a more cinematic initialization sequence where the directive is treated as the system core being brought online

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
- prefer bounded, testable improvements over speculative rewrites
- keep Docker standalone and Kubernetes orchestration concerns separate

A future CLA or contribution policy may be introduced to preserve consistent commercial licensing rights.

---

## Disclaimer

NOVALI is an experimental governed-agent framework. It is not a general unrestricted autonomous system and should not be treated as one. Use it with explicit operator oversight and bounded runtime policies.
