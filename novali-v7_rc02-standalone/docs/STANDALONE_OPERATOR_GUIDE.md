# Standalone Operator Guide

## Begin with the browser shell

Run the repository-level first-run wizard, then use `http://127.0.0.1:8787/shell`. The browser shell is the normal operator surface; direct CLI calls are reserved for development and diagnostics.

## Supply an operator-owned directive

This public package contains no sample, acceptance, or test directive. Generate a local wrapper with `standalone_docker/generate_directive_scaffold.ps1`, save it under `directive_inputs/`, and review its scope, deliverables, and stop conditions before loading it.

## Follow the authority chain

1. Select the local directive.
2. Complete bootstrap.
3. Start governed execution only when the shell says it is ready.
4. Resolve review gates before continuation.
5. Use pause or emergency stop whenever work should halt.

Autonomy is optional and bounded. It may act only through the existing policy, approval board, operations broker, runtime, memory-pressure, rollback, redaction, and emergency-stop controls. Local LLM output, trusted-source results, evidence packs, dashboards, and telemetry do not grant authority by themselves.

## Keep local state local

Never commit generated directives, workspaces, runtime ledgers, provider output, credentials, or telemetry. The package placeholders identify suitable local locations but are not public evidence stores.
