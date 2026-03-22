# NOVALI Localhost Web Operator UI

This is the first browser-based operator surface for `novali-v5`.

It is intentionally conservative.

For packaged standalone use, `README_FIRST.md` is the primary operator guide and this document is supporting detail.

Canonical authority is unchanged:

`operator shell -> launcher -> frozen session -> bootstrap -> governed execution`

The browser UI is only a thin operator surface over that same flow.

## Current Intended Use

Use this slice for local single-operator initialization and status review.

Default host-local launch:

- `python -m novali_v5.web_operator`
- equivalent convenience form: `python -m novali_v5`
- `.\standalone_docker\launch_web_operator.ps1`

Packaged handoff launch:

- `launch\02_run_browser_operator.bat`
- `launch\02_run_browser_operator.ps1`

Container-oriented standalone launch:

- `.\standalone_docker\run_web_operator_container.ps1`

Expected browser URL:

- `http://127.0.0.1:8787/`

## Exposure Model

Default intent is localhost-only.

- host-local launch binds to `127.0.0.1`
- container launch may bind the web server to `0.0.0.0` inside the container
- host port mapping should still stay on `127.0.0.1`

This slice does not implement multi-user auth or remote security controls.

Do not treat it as a public network service.

## What The First Slice Supports

- status/home page
- observability dashboard page
- workspace artifact browser
- runtime event timeline
- latest cycle summary page
- read-only artifact previews for markdown, json, python, and log files
- directive path selection
- directive upload
- packaged sample directive selection
- runtime-constraint and runtime-envelope edit/save
- trusted-source summary and secret-handling guidance
- launch / resume actions through the existing launcher
- launch result / refusal display
- acceptance evidence export
- backend visibility for `local_guarded` and `local_docker`

## Directive Handling

Directive-first bootstrap remains mandatory.

The browser UI does not replace `DirectiveSpec`.

Use:

- `DIRECTIVE_AUTHORING_GUIDE.md`
- the scaffold download endpoint in the web UI
- packaged sample directives for validation/refusal testing only

Raw secrets still do not belong in directive files.

## Trusted Sources And Secrets

Trusted-source bindings and raw secrets remain outside directive authority.

Current safe paths:

- environment variables
- `trusted_source_secrets.local.json`

The web UI only surfaces summaries and file locations in this first slice.

It does not introduce a second secrets-authoring authority path.

## Runtime Constraints

Runtime constraints remain operator-owned and frozen outside agent-owned self-structure.

The browser UI edits the same persisted operator policy files used by the existing launcher/runtime guard.

Unsupported controls remain explicitly unsupported.

Current execution profiles:

- `bootstrap_only_initialization`
  - intended for first-run initialization and canonical state materialization
- `bounded_active_workspace_coding`
  - intended for post-bootstrap governed work inside `novali-active_workspace/<workspace_id>/`

The bounded coding profile derives:

- active workspace root under `novali-active_workspace/`
- generated-output root under `runtime_data/generated/`
- log root under `runtime_data/logs/`

It does not grant broad package or repo write access.

Recommended browser flow for coding-capable runs:

1. initialize once with `new_bootstrap` + `bootstrap_only`
2. in the packaged standalone container, keep backend `local_guarded`
3. switch to `bounded_active_workspace_coding`
4. choose governed execution mode:
   - `single_cycle` for one bounded cycle per invocation
   - `multi_cycle` for a conservative bounded sequence with an explicit cycle cap
5. use `resume_existing` + `governed_execution`
6. if the first governed result reports `planning_only`, either run `governed_execution` again to advance in `single_cycle` mode or let `multi_cycle` continue until it reaches an explicit stop reason

## First Bounded Work Loop

The governed coding slice now progresses in two conservative workspace-local stages:

1. a first planning/scaffold cycle
2. a follow-on implementation-bearing cycle when that planning baseline already exists

Controller modes:

- `single_cycle`
  - one bounded cycle runs, writes artifacts, and returns control to the operator
- `multi_cycle`
  - planning and implementation cycles may continue in one invocation until directive completion, no-work, failure, or cap

Planning-baseline outputs inside `novali-active_workspace/<workspace_id>/`:

- `plans/bounded_work_cycle_plan.md`
- `docs/mutable_shell_successor_design_note.md`
- `src/README.md`
- `tests/README.md`
- `artifacts/bounded_work_file_plan.json`
- `artifacts/bounded_work_summary_latest.json`
- `artifacts/governed_execution_session_latest.json`

Implementation-bearing follow-on outputs now include:

- `src/successor_shell/__init__.py`
- `src/successor_shell/workspace_contract.py`
- `tests/test_workspace_contract.py`
- `docs/successor_shell_iteration_notes.md`
- `artifacts/workspace_artifact_index_latest.json`
- `artifacts/implementation_bundle_summary_latest.json`

Expected runtime events now include:

- `governed_execution_controller_started`
- `governed_execution_cycle_started`
- `governed_execution_cycle_completed`
- `directive_stop_condition_evaluated`
- `governed_execution_controller_stopped`
- `governed_execution_planning_started`
- `implementation_planning_started`
- `work_item_selected`
- `implementation_item_selected`
- `work_item_skipped`
- `file_write_planned`
- `file_write_completed`
- `test_scaffold_created`
- `implementation_bundle_completed`
- `implementation_bundle_deferred`
- `work_loop_completed`
- `no_admissible_bounded_work`
- `bounded_work_failure`

If no admissible bounded task exists, the run should stop explicitly with:

- session status `no_admissible_bounded_work`
- `plans/no_admissible_bounded_work.md`
- a matching summary artifact under `artifacts/`

## Browser Observability Views

The browser UI now includes read-only spot-check pages built from the persisted workspace and runtime artifacts:

- `/observability`
  - latest run overview including directive id, workspace id/root, execution mode, execution profile, backend, controller mode, cycles completed, stop reason, cycle kind, next recommended cycle, summary artifact path, and runtime event log path
- `/workspace`
  - grouped listing of `plans/`, `docs/`, `src/`, `tests/`, and `artifacts/` with preview links
- `/timeline`
  - operator-readable timeline rendered from the JSONL runtime event log
- `/cycle`
  - latest cycle summary showing what NOVALI created, skipped, deferred, and what should happen next
- `/preview?path=...`
  - read-only preview for supported markdown/json/python/text artifacts under the packaged operator roots

These views do not add editing capability or a second authority path. They are read-only windows over the same persisted artifacts the packaged standalone flow already writes.

## Docker Alignment

The single-container standalone target now points toward the browser UI.

Current container behavior:

- image exposes port `8787`
- default container command starts the localhost web operator
- expected host mapping is `127.0.0.1:8787:8787`
- mounted operator-visible paths should cover:
  - `directive_inputs/`
  - `trusted_sources/`
  - `operator_state/`
  - `runtime_data/state/`
  - `runtime_data/logs/`
  - `runtime_data/acceptance_evidence/`

For the packaged handoff product, prefer the prebuilt archive under `image/` plus the helper scripts under `launch/`.

For that packaged single-container handoff, the browser UI is already running inside the Docker execution envelope. Keep backend `local_guarded` in the UI for in-container launches. Use `local_docker` only from an operator environment with direct Docker access.

## Honest Limits

Still intentionally deferred:

- Kubernetes
- multi-agent/swarm orchestration
- remote/multi-user security model
- broader runtime guarantees beyond current honest `hard_enforced`, `watchdog_enforced`, and `unsupported_on_this_platform` classifications
