# Standalone Handoff Acceptance

This checklist simulates the release-style operator experience from an unpacked standalone handoff package.

It is intentionally narrower than developer-repo validation.

Use `MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md` to record the outcome of the pass if you need a short operator-facing evidence note alongside exported acceptance markdown.

Preferred standalone/browser operator launch is now:

- `python -m novali_v5.web_operator`
- equivalent convenience form: `python -m novali_v5`

## Goal

Confirm that an unpacked handoff package supports:

1. prebuilt image archive load
2. browser-operator launch
3. directive generation or selection
4. happy-path bootstrap
5. bounded coding path visibility after bootstrap
6. clarification/refusal path
7. expected artifact/log/evidence placement

## Suggested Clean Validation Sequence

1. Unpack the handoff package into a clean directory.

Expected:

- package root contains `README_FIRST.md`
- docs, samples, standalone_docker, directive_inputs, trusted_sources, operator_state, runtime_data, data, and logs are visible

2. Load or auto-load the standalone image archive.

Run:

```powershell
.\launch\01_load_image_archive.ps1
```

Expected:

- packaged image archive loads successfully
- image tag is `novali-v5-standalone:local`

3. Generate a directive file.

Run:

```powershell
.\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\directive_inputs\acceptance_directive.json `
  --directive-id directive_acceptance_bootstrap_v1 `
  --directive-text "Initialize NOVALI from the standalone handoff package." `
  --clarified-intent-summary "Bootstrap novali-v5 under the canonical standalone operator flow and preserve artifact-backed governance authority before execution."
```

Expected:

- a formal directive file appears in `directive_inputs/`

4. Launch the browser operator surface.

Run:

```powershell
.\launch\02_run_browser_operator.ps1
```

Expected:

- the localhost web operator starts
- the browser URL is `http://127.0.0.1:8787/`
- the canonical launch path remains browser UI / operator surface -> launcher -> frozen session -> bootstrap -> governed execution

5. Configure the happy path.

In the browser UI:

- select the generated directive file
- set State Root to `runtime_data/state`
- configure runtime constraints so allowed write roots include `runtime_data/state` and `runtime_data/logs`
- select backend `local_docker`
- set Docker image to `novali-v5-standalone:local`
- keep only local trusted sources enabled
- save/apply runtime constraints
- launch bootstrap

Expected:

- bootstrap completes
- canonical artifacts appear under `runtime_data/state`
- launch/evidence files appear under operator-owned paths and logs

6. Confirm the bounded coding path is available.

In the browser UI after successful bootstrap:

- keep the same persisted State Root
- switch execution profile to `bounded_active_workspace_coding`
- confirm an active workspace root appears under `novali-active_workspace/<workspace_id>/`
- use `resume_existing` plus `governed_execution`

Expected:

- the packaged browser flow clearly distinguishes `bootstrap_only` from `governed_execution`
- the bounded coding profile is visible as a separate operator choice
- the active workspace root is shown as bounded workspace state, not broad package write access

7. Trigger the refusal path.

In the GUI:

- select `samples/directives/standalone_incomplete_directive.example.json`
- launch bootstrap

Expected:

- activation is refused before governed execution
- clarification-required messaging is visible
- refusal is captured in launch status and operator evidence surfaces

8. Export acceptance evidence.

Expected:

- the exported markdown evidence is operator-readable
- it distinguishes the latest attempted action from prior successful state where relevant

## Honest Limits

This acceptance flow does not imply:

- Kubernetes support
- multi-agent deployment
- broader runtime guarantees than currently enforced
- a second authority path outside the existing directive/bootstrap/operator flow
