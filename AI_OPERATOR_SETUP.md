# AI Operator Setup Guide

This guide is for Codex or another AI operator assisting a human with the public NOVALI handoff.

## Safe Starting Rules

- Work from the repository root unless the human asks otherwise.
- Treat `novali-v7_rc01-standalone/` as the public handoff package.
- Never copy secrets, `.env` values, provider output, private runtime ledgers, or active workspace artifacts into docs or issues.
- Do not use private live directives as samples or default missions.
- Keep all autonomy language bounded: NOVALI proposes and executes only through policy, board, broker, memory, and emergency-stop gates.

## First Setup Sequence

1. Confirm Docker Desktop is running.
2. Run:

   ```powershell
   .\launch\00_first_run_wizard.ps1
   ```

3. Open `http://127.0.0.1:8787/shell` if the browser does not open automatically.
4. Generate a generic directive scaffold if no directive exists.
5. Guide the human through bootstrap, governed execution, review gates, and optional autonomy.

## Directive Generation

Use the packaged scaffold helper:

```powershell
.\novali-v7_rc01-standalone\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\novali-v7_rc01-standalone\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_run_v1 `
  --directive-text "Initialize NOVALI for a bounded local research and implementation planning run." `
  --clarified-intent-summary "Create reviewable local artifacts, keep all execution governed, and preserve operator-readable evidence before continuation."
```

Good directive text is specific, bounded, and reviewable. It should ask for local evidence artifacts, clear deliverables, and explicit stop/review conditions.

## Engaging Autonomy

Before enabling autonomy, verify:

- a directive is loaded,
- bootstrap has completed or a valid checkpoint exists,
- governed execution is launchable,
- emergency stop is not active,
- memory/OOM guard is normal,
- high-impact unattended actions are explicitly intended.

Autonomy may help continue governed work, refresh dossiers, maintain Librarian evidence, and request trusted-source retrieval only through validated policy paths.

## Validation Commands

Use these from the public repository root:

```powershell
.\scripts\public_handoff_hygiene.ps1
python -m py_compile .\novali-v7_rc01-standalone\standalone_docker\generate_directive_scaffold.py
python -m py_compile .\novali-v7_rc01-standalone\standalone_docker\assemble_handoff_package.py
```

If Node dependencies are installed for the React shell inside the package:

```powershell
npm --prefix .\novali-v7_rc01-standalone\operator_shell\web_ui test
npm --prefix .\novali-v7_rc01-standalone\operator_shell\web_ui run build
```

## What Not To Do

- Do not push private directives, pending LLM directives, active workspaces, runtime ledgers, or spill-volume state.
- Do not paste API keys into markdown, issues, PRs, prompts, or test fixtures.
- Do not present NOVALI as unrestricted or self-authorizing.
- Do not treat the Docker container, local LLM, trusted-source result, or Librarian pack as governance authority.

