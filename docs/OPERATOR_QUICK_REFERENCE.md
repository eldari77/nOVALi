# NOVALI Operator Quick Reference

Use this when you need the next safe operator move.

## Start

Run:

```powershell
.\launch\00_first_run_wizard.ps1
```

Open:

```text
http://127.0.0.1:8787/shell
```

## Create A Directive

Use the scaffold helper instead of writing raw JSON by hand:

```powershell
.\novali-v7_rc01-standalone\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\novali-v7_rc01-standalone\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Initialize NOVALI for a bounded local research and implementation planning run." `
  --clarified-intent-summary "Create reviewable local artifacts, keep all execution governed, and preserve operator-readable evidence before continuation."
```

## Bootstrap

Bootstrap creates canonical directive/session state. If NOVALI asks for clarification, fix the directive before trying governed execution.

## Governed Execution

Use governed execution after bootstrap or when a valid checkpoint is ready. It stays bounded by workspace, runtime, review, memory, and emergency-stop gates.

## Continue

Continue only when the Operator Shell reports the session is ready and stale recovery is false. If a review gate is active, resolve the review first.

## Review

Review gates are intentional. Read the reason, inspect the evidence, then approve, defer, reject, or acknowledge from the Operator Shell.

## Autonomy

Autonomy is optional and governed. It may propose low-touch continuation, dossier work, Librarian evidence management, or validated trusted-source retrieval. High-impact work stays policy-gated.

## Librarian

The Librarian stores reusable Knowledge Packs and Skill Packs as local evidence. Packs do not grant execution authority.

## Pause And Emergency Stop

Use pause for intentional operator holds. Use emergency stop when the loop should refuse further work until explicitly cleared.

