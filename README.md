# NOVALI

NOVALI is an experimental, operator-facing, governed agent framework for directive-driven work, bounded continuation, reusable evidence packs, and reviewable autonomy.

Its operating principle is simple:

> useful long-running agent behavior should stay bounded, legible, resumable, and governed.

This public handoff is designed for a first-time local operator. It ships a guided NOVALI v7 standalone package, a browser Operator Shell, generic directive scaffolds, and public documentation. It intentionally does not ship private live directives, active workspaces, runtime ledgers, secrets, or telemetry state.

![Operator Shell overview](docs/assets/operator-shell-overview.svg)

## First 10 Minutes

### 1. Prerequisites

- Windows with PowerShell 7 or Windows PowerShell
- Docker Desktop running
- Python on `PATH` as a fallback launcher
- Optional: an external trusted-source API key, supplied through your local shell or the Operator Shell when needed

### 2. Start the guided handoff

From the repository root:

```powershell
.\launch\00_first_run_wizard.ps1
```

The wizard checks Docker, loads or builds the local image if needed, starts the standalone Web Operator, and opens:

```text
http://127.0.0.1:8787/shell
```

### 3. Create or choose a directive

NOVALI starts from a directive, not from an unrestricted prompt. For a generic scaffold:

```powershell
.\novali-v7_rc01-standalone\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\novali-v7_rc01-standalone\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Initialize NOVALI for a bounded local research and implementation planning run." `
  --clarified-intent-summary "Create reviewable local artifacts, keep all execution governed, and preserve operator-readable evidence before continuation."
```

Then load that file from the Operator Shell.

### 4. Bootstrap, govern, continue

In `/shell`:

1. Load the directive.
2. Run bootstrap initialization.
3. Start governed execution.
4. Use the workspace and attention queue to review blockers.
5. Continue bounded work only when the UI shows it is safe.
6. Use pause or emergency stop whenever the run should halt.

### 5. Optional autonomy

Autonomy remains governed. It can propose and execute only policy-allowed operations through NOVALI's broker, board, memory guard, and emergency-stop gates. Start with the Operator Shell's autonomy status and keep high-impact actions explicitly validated.

## What Is Included

- `novali-v7_rc01-standalone/` - the sanitized runnable handoff package
- `launch/00_first_run_wizard.ps1` - first-run guided launcher
- `AI_OPERATOR_SETUP.md` - safe setup notes for Codex and other AI operators
- `docs/OPERATOR_QUICK_REFERENCE.md` - operator action reference
- `docs/PUBLIC_PACKAGE_CONTENTS.md` - included/excluded package contents
- `docs/PUBLIC_RELEASE_CHECKLIST.md` - repeatable public update checklist
- `docs/assets/` - sanitized Operator Shell screenshots

## What Is Not Included

This public handoff intentionally excludes:

- private mission directives from local runs
- pending LLM directives from local runs
- active workspaces and generated directive dossiers
- runtime ledgers, telemetry, secrets, cache state, and spill-volume state
- raw trusted-source provider output or credentials

## Current NOVALI v7 Surface

The public package documents and ships the current v7 operating shape:

- React Operator Shell served at `/shell`
- governed bootstrap and execution
- checkpointed long-run continuation
- autonomy kernel with approval-board and broker boundaries
- directive work program and research dossier artifacts
- Librarian pack library for reusable local evidence
- memory smoothing, OOM guard, and disk-spill metadata
- trusted-source validation and redacted evidence handling
- local LLM drafting as explain-and-draft evidence only

## Operator Model

NOVALI is not an unrestricted autonomous system. Governance truth lives in persisted artifacts. The UI, telemetry, Librarian, trusted-source results, dossiers, and pack refs are evidence surfaces; they do not become a second authority path.

## Licensing

NOVALI is source-available under the Business Source License 1.1. See:

- `LICENSE.md`
- `COMMERCIAL_USE.md`
- `NOTICE.md`
- `TRADEMARKS.md`

The Additional Use Grant is `None`. Production, hosted, managed-service, commercial product integration, customer-facing operational use, and paid delivery built around NOVALI require a separate commercial license from the Licensor.

This repository is not legal advice. If you intend to rely on these terms commercially, obtain legal review.

## For AI Operators

Start with `AI_OPERATOR_SETUP.md`. Do not load secrets into prompts, do not use private live workspaces as public examples, and do not treat trusted-source or Librarian evidence as execution authority.

