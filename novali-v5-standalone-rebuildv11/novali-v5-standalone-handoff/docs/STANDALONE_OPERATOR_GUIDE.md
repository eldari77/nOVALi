# NOVALI Standalone Operator Guide

This is the primary operator-facing guide for the standalone `novali-v5` handoff package.

If you are working from an unpacked handoff package, read `README_FIRST.md` before this guide.

The intended product flow is:

`unzip -> load image if needed -> run launcher -> open browser -> initialize NOVALI`

Canonical authority remains unchanged:

`browser UI / operator surface -> launcher -> frozen session -> bootstrap -> governed execution`

## What The Package Contains

Key folders for an operator:

- `image/`
  - packaged Docker image archive and archive manifest
- `launch/`
  - the simplest load/run helpers
- `docs/`
  - operator guides and supporting notes
- `directive_inputs/`
  - where to place real formal directive files
- `trusted_sources/`
  - operator-owned trusted-source material
- `operator_state/`
  - operator-owned runtime/session policy files
- `runtime_data/state/`
  - persisted NOVALI canonical artifacts
- `runtime_data/logs/`
  - launch/runtime logs
- `runtime_data/acceptance_evidence/`
  - exported evidence snapshots
- `samples/`
  - non-authoritative sample directives and configuration examples

## Fastest Operator Path

On Windows, the simplest launch path is:

1. Open the unpacked package folder.
2. Run `launch\02_run_browser_operator.bat`.
3. If the image tag is not already loaded, the script loads `image\novali-v5-standalone.tar`.
4. The script starts the standalone container with localhost-only port mapping.
5. Open `http://127.0.0.1:8787/` in the browser.

For a first governed coding run:

1. complete a successful `new_bootstrap` + `bootstrap_only` initialization
2. keep backend `local_guarded` in the packaged browser UI
3. save runtime policy with execution profile `bounded_active_workspace_coding`
4. choose governed execution mode:
   - `single_cycle` for one bounded cycle per invocation
   - `multi_cycle` for a conservative bounded sequence with an explicit cycle cap
5. choose a workspace id
6. resume with `resume_existing` + `governed_execution`

Browser observability pages for operator spot checks:

- `/observability`
  - latest run status, workspace id/root, controller mode, cycles completed, stop reason, next cycle, and artifact paths
- `/workspace`
  - grouped view of `plans/`, `docs/`, `src/`, `tests/`, and `artifacts/`
- `/timeline`
  - runtime JSONL events rendered as a readable timeline
- `/cycle`
  - latest planning or implementation cycle summary, created files, skipped items, and deferred items

Those views now also expose the continuation evidence used by the controller:

- trusted planning evidence summary
- missing bounded deliverables
- next-step derivation
- directive-completion evaluation
- review status
- promotion recommendation
- next bounded objective proposal
- reseed request / decision state
- continuation lineage and effective approved next objective
- auto-continue policy, chain count, and last continuation reason

Inside the packaged standalone handoff, the browser UI is already running inside the Docker envelope. `local_docker` remains a host-level operator option and is not the intended in-container backend for this single-container product path.

PowerShell equivalents:

- `launch\01_load_image_archive.ps1`
- `launch\02_run_browser_operator.ps1`

Underlying browser entrypoint inside the standalone package/container:

- `python -m novali_v5.web_operator`

## Directive Files

Use a formal directive wrapper only.

To create one:

- use the browser UI scaffold download
- or use the packaged guide `docs/DIRECTIVE_AUTHORING_GUIDE.md`
- or use the packaged samples as references only

Keep these distinctions clear:

- valid starter sample:
  - `samples/directives/standalone_valid_directive.example.json`
- incomplete refusal sample:
  - `samples/directives/standalone_incomplete_directive.example.json`

Incomplete directives are expected to trigger clarification/refusal before activation.

## Trusted Sources And Secrets

Do not place raw secrets in directive files.

Use:

- environment variables
- or `trusted_source_secrets.local.json`

Bindings remain metadata/reference only.

## Runtime Constraints

Runtime constraints are configured through the browser UI and remain operator-owned.

Current enforcement classes remain honest:

- `hard_enforced`
- `watchdog_enforced`
- `unsupported_on_this_platform`

Unsupported controls are not guaranteed.

The bounded coding profile is intentionally narrow.

It permits writes only inside:

- `novali-active_workspace/<workspace_id>/`
- `runtime_data/generated/`
- `runtime_data/logs/`

Protected surfaces remain outside those writable roots by default, including canonical state, directive inputs, frozen operator files, `main.py`, and `theory/nined_core.py`.

## What Governed Execution Now Produces

The bounded governed workspace now has two conservative output phases.

First cycle, look for the planning baseline:

- `novali-active_workspace/<workspace_id>/plans/bounded_work_cycle_plan.md`
- `novali-active_workspace/<workspace_id>/docs/mutable_shell_successor_design_note.md`
- `novali-active_workspace/<workspace_id>/src/README.md`
- `novali-active_workspace/<workspace_id>/tests/README.md`
- `novali-active_workspace/<workspace_id>/artifacts/bounded_work_file_plan.json`
- `novali-active_workspace/<workspace_id>/artifacts/bounded_work_summary_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/governed_execution_session_latest.json`

That first governed invocation is a completed bounded cycle, not a stall. In `single_cycle` mode, if the summary reports `cycle_kind = planning_only` and `next_recommended_cycle = materialize_workspace_local_implementation`, run `resume_existing + governed_execution` again to advance. In `multi_cycle` mode, the controller may continue automatically until it reaches a conservative stop reason.

You can now confirm that directly in the browser instead of opening the files by hand:

- `/observability` shows the latest cycle kind and next recommended cycle
- `/cycle` shows what the latest cycle created, skipped, and deferred
- `/timeline` shows the structured runtime events for that cycle

Second cycle, if that baseline already exists, look for the first implementation-bearing bundle:

- `novali-active_workspace/<workspace_id>/src/successor_shell/__init__.py`
- `novali-active_workspace/<workspace_id>/src/successor_shell/workspace_contract.py`
- `novali-active_workspace/<workspace_id>/tests/test_workspace_contract.py`
- `novali-active_workspace/<workspace_id>/docs/successor_shell_iteration_notes.md`
- `novali-active_workspace/<workspace_id>/artifacts/workspace_artifact_index_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/implementation_bundle_summary_latest.json`

Later bounded continuation may then add:

- `novali-active_workspace/<workspace_id>/plans/successor_continuation_gap_analysis.md`
- `novali-active_workspace/<workspace_id>/docs/successor_package_readiness_note.md`
- `novali-active_workspace/<workspace_id>/src/successor_shell/successor_manifest.py`
- `novali-active_workspace/<workspace_id>/tests/test_successor_manifest.py`
- `novali-active_workspace/<workspace_id>/artifacts/trusted_planning_evidence_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/missing_deliverables_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/next_step_derivation_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/completion_evaluation_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_readiness_evaluation_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_delivery_manifest_latest.json`

Those later cycles are driven by read-only internal trusted planning evidence under `trusted_sources/knowledge_packs/`. That evidence helps the controller answer what bounded successor deliverables still matter, what is still missing, and whether the next admissible step should be planning or implementation. It does not grant permissions or override operator policy.

Current bounded successor completion is conservative. The controller does not treat “some implementation exists” as equivalent to “directive complete.” It now checks completion against the packaged successor-completion knowledge pack and stops with `completed_by_directive_stop_condition` only when the bounded workspace deliverables satisfy that rubric.

After that bounded completion, the standalone flow now writes explicit review-and-promotion artifacts:

- `novali-active_workspace/<workspace_id>/artifacts/successor_review_summary_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_promotion_recommendation_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_next_objective_proposal_latest.json`

Those artifacts answer different questions:

- review summary:
  - is operator review required
  - what bounded deliverables are present
  - what weak areas remain
- promotion recommendation:
  - is promotion recommended or not recommended
  - why
  - with what conservative confidence
- next-objective proposal:
  - what bounded objective is proposed next
  - why it was proposed
  - that it is not automatically authorized for execution

The packaged review rubric is also read-only and internal:

- `trusted_sources/knowledge_packs/successor_promotion_review_knowledge_pack_v1.json`

Promotion remains recommendation-only in this slice. A complete bounded successor package is not silently promoted to a new baseline, and a next objective proposal does not automatically reseed execution.

The next bounded objective now has an explicit operator-reviewed bridge. After a bounded successor package completes, inspect the `Review, Reseed, And Continuation` section on the browser home page and choose one of:

- approve
- approve and continue
- defer
- reject

That decision is recorded through these artifact-backed surfaces:

- `novali-active_workspace/<workspace_id>/artifacts/successor_reseed_request_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_reseed_decision_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_continuation_lineage_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_effective_next_objective_latest.json`

An approved decision materializes the next bounded objective for the next governed run. Rejected or deferred decisions remain explicit and do not execute.

The browser home page now also includes an `Auto-Continue Policy` section. It is operator-owned, disabled by default, whitelist-based, and chain-capped. It may materialize an eligible already-approved next objective class without another approval click only when:

- the objective class is whitelisted
- first-entry approval rules are satisfied
- review-supported proposal requirements are satisfied
- the current chain count remains below the configured cap

Its artifacts are explicit and auditable:

- `operator_state/successor_auto_continue_policy_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_auto_continue_state_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_auto_continue_decision_latest.json`

If those conditions are not satisfied, the flow stops with an explicit reason and falls back to manual review.

If no bounded task is admissible, expect an explicit stop with:

- `status = no_admissible_bounded_work`
- `plans/no_admissible_bounded_work.md`
- a matching summary artifact in `artifacts/`

Controller stop reasons now surface explicitly in the browser and controller artifact, including:

- `completed_by_directive_stop_condition`
- `no_admissible_bounded_work`
- `bounded_failure`
- `max_cycle_cap_reached`
- `single_cycle_invocation_completed`

## Where To Look After Launch

- canonical artifacts:
  - `runtime_data/state/`
- logs:
  - `runtime_data/logs/`
- acceptance evidence:
  - `runtime_data/acceptance_evidence/`
- bounded governed work outputs:
  - `novali-active_workspace/`

In the packaged standalone launcher, `novali-active_workspace/` is mounted from the host package directory into the container so bounded work outputs remain visible after the container stops.
- operator-owned launch/session state:
  - `operator_state/`

## What Docker Mode Really Means Today

Current standalone Docker mode is conservative.

It does not imply:

- public remote access
- multi-user security
- Kubernetes support
- any runtime guarantee beyond the current honest enforcement classifications

Kubernetes remains a later multi-agent/swarm phase and is not part of this standalone package.
