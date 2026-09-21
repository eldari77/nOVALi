# AI Operator Setup Guide

This guide applies to Codex and other AI assistants helping a human use the public NOVALI handoff.

## Operating boundary

- Use `novali-v7_rc02-standalone/` as the current public package; `rc01` is retained as historical reference.
- Keep public work source-first. The package deliberately has no authored, acceptance, or test directives.
- Never copy secrets, `.env` values, local runtime state, active workspaces, raw provider output, or telemetry captures into the repository.
- Treat generated local evidence as advisory. Approval, broker, runtime policy, and emergency-stop gates remain authoritative.

## First setup

1. Confirm Docker Desktop is running.
2. Run `./launch/00_first_run_wizard.ps1` from the repository root.
3. Open `http://127.0.0.1:8787/shell` if the browser did not open.
4. Have the human create a new directive with the packaged scaffold helper.
5. Guide bootstrap, governed execution, review, and optional autonomy without bypassing any gate.

## Local directive scaffold

```powershell
.\novali-v7_rc02-standalone\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\novali-v7_rc02-standalone\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Plan a bounded local research task with reviewable outputs." `
  --clarified-intent-summary "Keep execution governed and stop for operator review."
```

The output is local operator input; do not add it to this public repository.

## Handoff checks

```powershell
.\scripts\public_handoff_hygiene.ps1
python -m py_compile .\novali-v7_rc02-standalone\standalone_docker\generate_directive_scaffold.py
```

Do not add test directives or runtime fixtures merely to demonstrate a workflow. A public package should demonstrate its boundaries through code and documentation, then let each operator author their own local input.
