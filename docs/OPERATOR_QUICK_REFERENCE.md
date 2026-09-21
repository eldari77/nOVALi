# NOVALI Operator Quick Reference

## Start

```powershell
.\launch\00_first_run_wizard.ps1
```

Open `http://127.0.0.1:8787/shell`. The first run builds `novali-v7_rc02-standalone` locally when needed.

## Create a local directive

The public handoff contains no sample or test directives. Create a local one with:

```powershell
.\novali-v7_rc02-standalone\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\novali-v7_rc02-standalone\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Plan a bounded local research task with reviewable outputs." `
  --clarified-intent-summary "Keep execution governed and stop for operator review."
```

## Work safely

1. Load the directive and complete bootstrap.
2. Use governed execution only when the shell reports it ready.
3. Resolve review gates in the shell before continuing.
4. Use autonomy only under its configured policy, board, broker, memory, and emergency-stop controls.
5. Keep directives, runtime data, provider output, and credentials local.

Pause for an intentional hold. Use emergency stop when the loop should refuse further work until explicitly cleared.
