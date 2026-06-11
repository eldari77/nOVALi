# NOVALI Guided Standalone Handoff

Read this file first if you are inside the packaged handoff directory.

This package is a sanitized public NOVALI v7 handoff. It is intended for local single-operator evaluation, research, and non-production experimentation under the repository license.

## Start

From the repository root, prefer:

```powershell
.\launch\00_first_run_wizard.ps1
```

From this package directory, use:

```powershell
.\standalone_docker\run_web_operator_container.ps1
```

Then open:

```text
http://127.0.0.1:8787/shell
```

## First Operator Loop

1. Generate or choose a directive under `directive_inputs/`.
2. Load the directive in the Operator Shell.
3. Run bootstrap initialization.
4. Start governed execution.
5. Resolve review/attention gates when they appear.
6. Continue bounded work only when the shell reports it is safe.
7. Enable autonomy only after the governed path is healthy and the operator understands the emergency stop.

## Generic Directive Scaffold

```powershell
.\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Initialize NOVALI for a bounded local research and implementation planning run." `
  --clarified-intent-summary "Create reviewable local artifacts, keep all execution governed, and preserve operator-readable evidence before continuation."
```

## Public Handoff Boundaries

This package intentionally excludes private live directives, active workspaces, runtime ledgers, pending LLM directives, secrets, and raw trusted-source provider output.

NOVALI evidence surfaces such as telemetry, dossiers, trusted-source summaries, and Librarian packs do not become governance authority. Governed execution remains bounded by operator controls, review gates, memory guards, and emergency stop.
