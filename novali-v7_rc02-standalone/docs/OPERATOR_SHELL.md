# NOVALI Operator Shell

## Role Boundary

The operator GUI is a thin shell over the existing `DirectiveSpec` bootstrap and governed runtime.

The preferred standalone product direction is now the localhost browser UI.

This desktop GUI remains available as a transitional local operator surface.

- Preferred standalone/browser startup is now:
  - `python -m novali_v5.web_operator`
  - equivalent convenience form: `python -m novali_v5`
  - when built: `http://127.0.0.1:8787/shell`
- When `/shell` is unavailable (missing `operator_shell/web_ui/build`), it falls back to legacy operator paths and keeps canonical flow intact.
- Transitional desktop startup remains:
  - `python -m novali_v5.operator_shell`
- Canonical startup authority still begins with the formal directive file and `bootstrap.py`.
- Canonical governance state still lives in persisted NOVALI artifacts:
  - `directive_state_latest.json`
  - `bucket_state_latest.json`
  - `branch_registry_latest.json`
  - `governance_memory_authority_latest.json`
  - `self_structure_state_latest.json`
- The GUI does not author those facts directly.
- The GUI only collects operator inputs, freezes operator policy for a run, invokes the existing bootstrap/runtime path, and displays persisted state.
- Direct `main.py` and `bootstrap.py` use remains available only as non-canonical developer/test surfaces.

See also:

- [HANDOFF_PACKAGE_README.md](./HANDOFF_PACKAGE_README.md)
- [DIRECTIVE_AUTHORING_GUIDE.md](./DIRECTIVE_AUTHORING_GUIDE.md)
- [LOCALHOST_WEB_OPERATOR_UI.md](./LOCALHOST_WEB_OPERATOR_UI.md)
- [LAUNCH_MATRIX.md](./LAUNCH_MATRIX.md)
- [RUNTIME_ENVELOPE.md](./RUNTIME_ENVELOPE.md)
- [STANDALONE_DOCKER_QUICKSTART.md](./STANDALONE_DOCKER_QUICKSTART.md)
- [STANDALONE_HANDOFF_ACCEPTANCE.md](./STANDALONE_HANDOFF_ACCEPTANCE.md)
- [MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md](./MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md)

## GUI Flow

The Tkinter operator shell is intentionally thin and conservative.

Core operator flow:

1. Select a directive file or choose resume mode.
2. Inspect directive-wrapper validation feedback before activation.
3. Review trusted-source bindings, credential strategy, secret-source indication, and conservative availability state.
4. Review runtime constraints together with their actual enforcement class.
5. Launch or resume through the canonical operator chain only when the GUI shows readiness.
6. Read posture, artifact presence, last launch outcome, frozen-session validity, and refusal context from persisted state.

The GUI does not invent authority if optional artifacts are missing. It surfaces absence and refusal instead of filling gaps with inferred state.

For desktop/manual validation, use the packaged/operator-facing guides rather than improvising startup inputs.

For standalone handoff use, prefer the directive scaffold helper and operator-facing docs rather than editing sample JSON by hand:

- `standalone_docker/generate_directive_scaffold.ps1`
- `standalone_docker/generate_directive_scaffold.py`
- `directive_inputs/` in the unpacked handoff package

## Trusted Source Credentials

Trusted-source authority is split across two operator-owned files:

- `trusted_source_bindings_latest.json`
  - non-secret source metadata
  - enable/disable status
  - credential strategy
  - credential reference names
- `trusted_source_secrets.local.json`
  - optional local secret values
  - stored outside canonical governance artifacts
  - intended for local operator use only
  - never part of directive authority
  - never copied into canonical governance artifacts

This keeps directive authority separate from operator credential handling.

Credential resolution model:

- `credential_strategy = env_var`
  - resolve from the named environment variable at launch time
- `credential_strategy = local_secret_store`
  - resolve from the operator-local secrets file
- `credential_strategy = none`
  - no secret is required

The GUI shows secret-source status conservatively:

- environment variable present / missing
- local secret stored / missing
- no secret required
- invalid or missing credential reference

## Runtime Constraint Model

Operator runtime policy lives outside NOVALI's self-modifiable governance surfaces.

Primary files:

- `operator_runtime_constraints_latest.json`
- `operator_runtime_envelope_spec_latest.json`
- `effective_operator_session_latest.json`
- `operator_runtime_launch_plan_latest.json`
- `operator_launch_events.jsonl`

The runtime envelope adds a backend-neutral execution layer above the existing local guard details.

Current envelope backends:

- `local_guarded`
  - default current launcher + runtime-guard path
- `local_docker`
  - Docker-first experimental scaffolding
  - opt-in only
  - no privileged mode
  - no Docker socket exposure to the agent
- reserved only, still deferred:
  - `k8s_job`
  - `k8s_pod`

Frozen operator state for a run means:

- the effective operator session has been materialized
- that session hashes and anchors the effective runtime constraints, runtime envelope, and trusted-source bindings for the run
- canonical operator-mode resume refuses if that frozen session is missing, tampered, or incoherent

The GUI makes these distinctions explicit:

- editable controls that are actually part of the current operator policy
- effective frozen session state for the current or last run
- unsupported controls that remain visible for honesty but are not claimed as enforced

At launch time the operator layer:

1. Validates trusted-source bindings and runtime constraints.
2. Freezes an effective session snapshot for that run.
3. Starts the real NOVALI runtime with environment pointers to the frozen session.
4. Installs runtime guards before governed execution.

The agent runtime may read effective constraints for awareness, but it may not mutate operator policy.

Resume behavior is conservative:

- canonical resume validates the previously frozen operator session before re-entry
- tampered or incoherent frozen sessions cause refusal instead of fallback

## Enforcement Classes

Each constraint is classified explicitly.

- `hard_enforced`
  - enforced in the launched Python runtime or launcher boundary
  - examples: write-root boundary, subprocess disable/bounds, thread limits, operator-policy mutation lock, working-directory boundary
- `watchdog_enforced`
  - monitored by the parent launcher and terminated on violation
  - examples: session time limit, Windows memory watchdog
- `unsupported_on_this_platform`
  - not claimed as a guarantee
  - examples in this first slice: CPU utilization cap, network egress sandbox, request-rate ceilings

Unsupported constraints are surfaced explicitly and are not treated as active guarantees.

In the current local operator slice, unsupported controls remain visible in summaries for operator clarity, but the GUI does not represent them as enforceable protections.

With the new runtime-envelope layer, the same honesty rule still holds:

- `local_guarded` keeps the previously verified host-process enforcement classes
- `local_docker` only claims what Docker or the launcher watchdog can actually enforce
- unsupported backend translations are refused or labeled unsupported instead of silently downgraded

## Observability

The operator dashboard reads persisted state and frozen-session artifacts to show:

- directive file in use
- launch mode
- last launch result or refusal reason
- posture / branch summary from canonical artifacts when present
- trusted-source binding summary
- trusted-source secret resolution status without exposing raw values
- effective runtime constraints and enforcement class
- runtime backend selection and backend availability
- latest persisted launch-plan summary and launch-plan artifact location
- unsupported controls as unsupported, not as soft guarantees
- artifact locations used for the run

It also surfaces:

- whether the frozen operator session is present and valid
- the last launch event and refusal/failure context when available
- canonical artifact presence without claiming missing artifacts are present
- exportable manual-acceptance evidence from the status tab

## What Remains Unchanged

This slice does not change:

- `nined_core.py`
- routing logic
- thresholds
- live policy
- benchmark semantics
- the meaning of existing governance-memory authority surfaces

It adds an operator shell and runtime boundary around the existing directive-first bootstrap without introducing a second authority path.

## Operator Profile

The GUI now keeps a small local convenience profile at:

- `operator_gui_profile.local.json`

This profile is explicitly non-authoritative. It stores recent GUI selections such as:

- last-used directive path
- last-used state root
- recent resume mode
- recent launch action
- display preferences such as whether to show raw JSON in the dashboard

It does not store authority overrides, does not replace canonical artifacts, and does not bypass the frozen operator session or launcher validation.

## Manual Acceptance And Evidence

For operator acceptance on a real desktop:

- for the standalone handoff package, follow [STANDALONE_HANDOFF_ACCEPTANCE.md](./STANDALONE_HANDOFF_ACCEPTANCE.md)
- for local desktop/operator validation in the development tree, follow `MANUAL_ACCEPTANCE_CHECKLIST.md`
- record outcomes with [MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md](./MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md)
- use `Export Acceptance Snapshot` from the GUI status tab to write a non-authoritative markdown evidence file

The exported evidence is for audit and handoff only. It does not replace canonical directive, bucket, branch, governance-memory authority, or self-structure artifacts.

## Milestone Closeout

The first local operator-shell milestone is now manually validated and complete.

Validated outcomes:

- canonical operator bootstrap completed successfully on desktop
- incomplete directives produced governed refusal / clarification-required outcomes
- resume from persisted state completed successfully after frozen-session and canonical-state checks
- runtime-constraint reporting stayed honest about `hard_enforced`, `watchdog_enforced`, and `unsupported_on_this_platform`

Closeout polish in this pass focuses on clearer operator wording and evidence export only:

- successful launches and resumes are no longer presented with misleading failure wording
- governed refusals are presented explicitly as refusals, not successes
- manual acceptance exports distinguish the latest attempted action from frozen-session state that may predate a refusal

Still deferred:

- Kubernetes follow-on work after the Docker-first runtime envelope scaffolding
- final dependency-locked standalone image hardening beyond the currently validated bootstrap/control-plane slice
