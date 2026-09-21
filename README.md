# NOVALI

NOVALI is an experimental, operator-facing framework for bounded, reviewable agent work. It keeps long-running work legible, resumable, and governed: evidence may inform a decision, but it never creates a second authority path.

The current public handoff is [`novali-v7_rc02-standalone/`](novali-v7_rc02-standalone/). It is a source-first package built from the active v7 implementation and intentionally contains no authored, acceptance, or test directive files.

## Quick start

Prerequisites: Docker Desktop and PowerShell. Python is used only as a local fallback launcher.

```powershell
.\launch\00_first_run_wizard.ps1
```

The wizard builds the package image locally when it is not already available, starts the Web Operator, and opens `http://127.0.0.1:8787/shell`.

Create your own local directive only after the package is running:

```powershell
.\novali-v7_rc02-standalone\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\novali-v7_rc02-standalone\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Plan a bounded local research task with reviewable outputs." `
  --clarified-intent-summary "Keep execution governed and stop for operator review."
```

## What this handoff contains

- current NOVALI v7 source, Operator Shell, Docker configuration, and launch helpers;
- governance, audit, redaction, memory-pressure, checkpoint, and emergency-stop boundaries;
- local directive scaffolding so each operator starts with their own input;
- documentation for local setup, safe operation, and release hygiene.

It does not contain directives authored during development, acceptance/test directives, active workspaces, runtime ledgers, raw provider output, credentials, telemetry captures, or a stale prebuilt image archive.

Read [the operator quick reference](docs/OPERATOR_QUICK_REFERENCE.md), [package contents](docs/PUBLIC_PACKAGE_CONTENTS.md), and [AI operator guidance](AI_OPERATOR_SETUP.md) before extending or publishing it.

## Safety and governance

NOVALI is not an unrestricted autonomous system. Bootstrap, approval, broker, runtime policy, redaction, rollback, and emergency-stop controls remain binding. Local LLM output, trusted-source results, dashboards, and evidence packs are advisory inputs, not execution authority.

## License

NOVALI is source-available under the Business Source License 1.1. The Additional Use Grant is `None`; commercial, hosted, managed-service, customer-facing, or paid use requires a separate commercial license. See [LICENSE.md](LICENSE.md), [COMMERCIAL_USE.md](COMMERCIAL_USE.md), and [NOTICE.md](NOTICE.md).
