# NOVALI

**NOVALI** is an experimental self-structuring agent framework designed to initialize from a formal directive, operate under explicit governance constraints, consult only approved trusted sources, and improve through bounded, auditable changes rather than open-ended self-modification.

The current standalone product direction is:

**unzip → load Docker image → run container → open browser on localhost → initialize NOVALI**

---

## What NOVALI is

NOVALI is built around the idea that an agent should not behave like an unrestricted autonomous process. Instead, it should:

- start from a formal directive bootstrap file
- preserve canonical governance state in explicit persisted artifacts
- operate inside a bounded runtime envelope
- use only operator-approved trusted sources
- perform self-improvement only inside approved mutable work areas
- keep protected core surfaces stable unless explicitly reviewed

This project is aimed at creating agents that are more **governable, inspectable, and structurally coherent over time**.

---

## Current Product Shape

The current near-term standalone deployment target is:

- a **zip-delivered package**
- containing a **prebuilt Docker image archive**
- with a **browser-based localhost operator UI**
- for initializing and running a **single NOVALI agent**

The current operator flow is:

1. unpack the handoff package
2. load the Docker image archive
3. run the packaged launcher
4. open the browser UI on localhost
5. select or generate a directive
6. configure runtime policy and trusted-source settings
7. initialize NOVALI
8. optionally resume into bounded governed execution

---

## Core Design Principles

### 1. Directive-first initialization
NOVALI does not start from freeform text alone. It initializes from a formal directive bootstrap file that carries structured intent and startup context.

### 2. Canonical artifact authority
Governance truth does not live in ad hoc runtime state. It lives in explicit persisted artifacts, including directive, bucket, branch, and self-structure surfaces.

### 3. Bounded execution
NOVALI is intended to operate under operator-owned runtime constraints that it cannot casually alter or bypass.

### 4. Trusted-source-only external evidence
NOVALI should only consult bounded, operator-approved trusted sources when additional information is required.

### 5. Governed self-improvement
Self-improvement is allowed only in the mutable shell and approved workspaces. Protected core surfaces remain fixed unless explicitly reviewed.

### 6. Auditability over cleverness
The system is designed to favor traceable structure, stable policy, and inspectable changes over opaque capability growth.

---

## Architecture Overview

NOVALI currently uses a browser-first operator flow over a governed execution chain:

`browser UI → launcher → frozen session → bootstrap → governed execution`

Important concepts:

- **Directive bootstrap**: formal structured initialization
- **Frozen operator session**: effective launch constraints and policy
- **Runtime envelope**: bounded execution profile and backend
- **Trusted sources**: operator-approved evidence channels
- **Active workspace**: bounded writable build area for governed coding runs
- **Canonical artifacts**: persisted governance state used as source of authority

---

## Execution Modes

### Bootstrap-only initialization
Used for first-time initialization and canonical state creation.

### Governed execution
Used after initialization when NOVALI resumes under an approved execution profile to perform bounded work.

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

This allows NOVALI to produce useful outputs without granting unrestricted write access across the repository or package.

---

## Deployment Modes

### Docker standalone
The primary near-term deployment path.

Use this when you want:
- one agent
- one container
- one localhost browser UI
- one bounded operator session

### Kubernetes orchestration
Deferred future phase.

This is intended for:
- multi-agent deployment
- swarm-like orchestration
- stronger platform-level scheduling and policy control

Kubernetes is **not** the current standalone target.

---

## Safety and Governance Posture

NOVALI is explicitly conservative by design.

By default, it does **not** assume permission to:

- mutate protected core files
- broaden routing or thresholds
- alter live policy
- expand external access
- claim unsupported runtime guarantees
- bypass operator-owned constraints

The system is designed to support bounded progress rather than unconstrained autonomy.

---

## Trusted Sources

Trusted sources are the bounded external or internal evidence channels NOVALI may consult while fulfilling a directive.

They are **not** the governance source of truth.

Current intended distinction:

- **Governance truth** = canonical persisted NOVALI artifacts
- **External evidence** = trusted-source channels approved by the operator

---

## Current Status

NOVALI is currently in an experimental but working standalone phase with:

- formal directive bootstrap
- browser-based localhost operator UI
- Docker-based standalone handoff packaging
- bounded runtime envelope
- governed execution path
- active workspace support for bounded coding runs

Recent milestones include:

- standalone packaged browser-first initialization
- prebuilt Docker image archive handoff
- bounded governed execution in `novali-active_workspace`
- packaged two-step flow:
  - `new_bootstrap + bootstrap_only`
  - `resume_existing + governed_execution`

---

## Intended Use Cases

NOVALI is being built for tasks such as:

- governed autonomous planning
- structured bounded coding runs
- agent-initialized implementation work inside approved workspaces
- directive-guided research or product tasks using trusted sources
- auditable self-improvement under explicit safety constraints

---

## Quickstart Concept

The exact packaged flow depends on the current release, but the intended user experience is:

1. install Docker
2. unzip the NOVALI handoff package
3. load the packaged image archive
4. run the packaged launcher
5. open the localhost browser UI
6. choose or generate a directive
7. initialize NOVALI
8. resume into governed execution when appropriate

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

## Roadmap

Near-term priorities:
- improve bounded coding outputs in active workspace runs
- strengthen trusted-source query protocol design
- continue standalone release polish
- improve operator observability and artifact review

Deferred priorities:
- richer trusted-source internal query channels
- broader governed skill acquisition
- Kubernetes-based multi-agent orchestration

---

## Contributing

This repository is evolving quickly. If you contribute:

- preserve the directive-first authority chain
- keep operator-owned policy frozen and auditable
- do not casually broaden write permissions or runtime claims
- prefer bounded, testable improvements over large speculative rewrites
- keep Docker standalone and Kubernetes orchestration concerns separate

A future CLA or contribution policy may be introduced to preserve consistent commercial licensing rights.

---

## Disclaimer

NOVALI is an experimental governed-agent framework. It is not a general unrestricted autonomous system and should not be treated as one. Use it with explicit operator oversight and bounded runtime policies.
