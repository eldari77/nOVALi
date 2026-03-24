# NOVALI Localhost Web Operator UI

This is the first browser-based operator surface for `novali-v5`.

It is intentionally conservative.

For packaged standalone use, `README_FIRST.md` is the primary operator guide and this document is supporting detail.

Canonical authority is unchanged:

`operator shell -> launcher -> frozen session -> bootstrap -> governed execution`

The browser UI is only a thin operator surface over that same flow.

This rc now includes a first operator-productization pass:

- darker, more intentional visual hierarchy
- a directive-core initialization treatment on the home page
- clearer staging between directive selection, bootstrap-only initialization, and the return to governed execution
- stronger top-level observability summaries before the deeper raw state sections
- a state-driven workflow guide that surfaces what changed, what the operator should do next, and when the saved runtime policy does not match the selected action

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

In the packaged standalone path, the container launcher now creates and mounts that generated-output root explicitly so a fresh handoff still satisfies bounded-coding runtime policies that reference `runtime_data/generated/`.

It does not grant broad package or repo write access.

Recommended browser flow for coding-capable runs:

1. initialize once with `new_bootstrap` + `bootstrap_only`
2. in the packaged standalone container, keep backend `local_guarded`
3. if the home page warns that the selected action and saved runtime policy do not match, save Runtime Constraints And Envelope before launching
4. switch to `bounded_active_workspace_coding`
5. choose governed execution mode:
   - `single_cycle` for one bounded cycle per invocation
   - `multi_cycle` for a conservative bounded sequence with an explicit cycle cap
6. use `resume_existing` + `governed_execution`
7. if the first governed result reports `planning_only`, either run `governed_execution` again to advance in `single_cycle` mode or let `multi_cycle` continue until it reaches an explicit stop reason

When `multi_cycle` is active, the controller now consults read-only internal trusted planning evidence before each next-cycle decision. In this slice that evidence stays local and packaged:

- `trusted_sources/knowledge_packs/successor_completion_knowledge_pack_v1.json`
- `trusted_sources/knowledge_packs/workspace_continuation_knowledge_pack_v1.json`
- `trusted_sources/knowledge_packs/successor_promotion_review_knowledge_pack_v1.json`

Those knowledge packs are evidence inputs only. They do not add authority, permissions, or live network behavior.

NOVALI now also includes a first bounded skill-pack layer under `trusted_sources/skill_packs/`.

- knowledge packs remain read-only planning and review evidence
- skill packs are bounded execution capabilities

Current packaged successor-quality skill packs:

- `trusted_sources/skill_packs/successor_workspace_review_pack_v1.json`
- `trusted_sources/skill_packs/successor_test_strengthening_pack_v1.json`
- `trusted_sources/skill_packs/successor_manifest_quality_pack_v1.json`
- `trusted_sources/skill_packs/successor_docs_readiness_pack_v1.json`
- `trusted_sources/skill_packs/successor_artifact_index_consistency_pack_v1.json`
- `trusted_sources/skill_packs/successor_handoff_completeness_pack_v1.json`

The browser observability views now also surface the successor-quality roadmap layer:

- `artifacts/successor_quality_roadmap_latest.json`
- `artifacts/successor_quality_priority_matrix_latest.json`
- `artifacts/successor_quality_composite_evaluation_latest.json`
- `artifacts/successor_quality_next_pack_plan_latest.json`

Those artifacts explain which quality dimension is weakest, which pack ran last, what should run next, and whether the successor is materially stronger than the admitted candidate reference target in aggregate.

The observability views now also surface generation-over-generation progress governance:

- `artifacts/successor_generation_history_latest.json`
- `artifacts/successor_generation_delta_latest.json`
- `artifacts/successor_progress_governance_latest.json`
- `artifacts/successor_progress_recommendation_latest.json`

Those artifacts explain whether the latest revised candidate improved, plateaued, churned, or regressed relative to the prior admitted candidate, and whether NOVALI should continue bounded improvement, remediate, pause, or escalate review.

The observability views now also surface bounded strategy selection:

- `artifacts/successor_strategy_selection_latest.json`
- `artifacts/successor_strategy_rationale_latest.json`
- `artifacts/successor_strategy_follow_on_plan_latest.json`
- `artifacts/successor_strategy_decision_support_latest.json`

Those artifacts explain what bounded strategy NOVALI is recommending after generational assessment, which follow-on family it maps to, whether operator review is advised before execution, and which alternatives were not selected.

The observability views now also surface the bounded campaign-governance layer:

- `artifacts/successor_campaign_history_latest.json`
- `artifacts/successor_campaign_delta_latest.json`
- `artifacts/successor_campaign_governance_latest.json`
- `artifacts/successor_campaign_recommendation_latest.json`
- `artifacts/successor_campaign_wave_plan_latest.json`

Those artifacts explain how successive strategy waves accumulate into one bounded campaign, whether campaign gains are still broadening or flattening, what weak dimensions remain, and whether NOVALI should continue, shift to remediation, refresh the revised candidate, or pause for review.

The observability views now also surface the bounded campaign-cycle governance layer:

- `artifacts/successor_campaign_cycle_history_latest.json`
- `artifacts/successor_campaign_cycle_delta_latest.json`
- `artifacts/successor_campaign_cycle_governance_latest.json`
- `artifacts/successor_campaign_cycle_recommendation_latest.json`
- `artifacts/successor_campaign_cycle_follow_on_plan_latest.json`

Those artifacts explain how one completed campaign cycle compares to prior rolled-reference-target cycles, whether gains are still worth another full campaign, and whether NOVALI should start another campaign, hold the new target, open targeted post-rollover remediation, or pause for review.

The observability views now also surface the bounded loop-of-loops governance layer:

- `artifacts/successor_loop_history_latest.json`
- `artifacts/successor_loop_delta_latest.json`
- `artifacts/successor_loop_governance_latest.json`
- `artifacts/successor_loop_recommendation_latest.json`
- `artifacts/successor_loop_follow_on_plan_latest.json`

Those artifacts explain how one completed full campaign-refresh loop compares to prior completed loops, whether repeated loops are still broadening meaningfully, and whether NOVALI should start another full loop, hold the current bounded target, allow only targeted remediation, or pause for review.

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

Continuation-quality outputs may also include:

- `plans/successor_continuation_gap_analysis.md`
- `docs/successor_package_readiness_note.md`
- `src/successor_shell/successor_manifest.py`
- `tests/test_successor_manifest.py`
- `artifacts/trusted_planning_evidence_latest.json`
- `artifacts/missing_deliverables_latest.json`
- `artifacts/next_step_derivation_latest.json`
- `artifacts/completion_evaluation_latest.json`
- `artifacts/successor_readiness_evaluation_latest.json`
- `artifacts/successor_delivery_manifest_latest.json`
- `artifacts/successor_review_summary_latest.json`
- `artifacts/successor_promotion_recommendation_latest.json`
- `artifacts/successor_next_objective_proposal_latest.json`

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
  - latest run overview including directive id, workspace id/root, execution mode, execution profile, backend, controller mode, cycles completed, stop reason, cycle kind, next recommended cycle, summary artifact path, runtime event log path, and trusted-evidence artifact paths
- `/workspace`
  - grouped listing of `plans/`, `docs/`, `src/`, `tests/`, and `artifacts/` with preview links
- `/timeline`
  - operator-readable timeline rendered from the JSONL runtime event log
- `/cycle`
  - latest cycle summary showing what NOVALI created, skipped, deferred, what trusted planning evidence it consulted, and what should happen next
- `/preview?path=...`
  - read-only preview for supported markdown/json/python/text artifacts under the packaged operator roots

These views do not add editing capability or a second authority path. They are read-only windows over the same persisted artifacts the packaged standalone flow already writes, including the trusted planning evidence, missing-deliverables, next-step-derivation, and completion-evaluation artifacts produced by governed continuation.

After bounded completion, those same views now also surface:

- review status
- promotion recommendation
- next bounded objective proposal
- reseed request state
- reseed decision state
- continuation lineage
- effective approved next objective
- baseline-admission review, recommendation, decision, and remediation proposal
- auto-continue policy, chain count, and last continuation reason
- successor skill-pack selection, invocation/result artifacts, quality-gap summaries, and quality-improvement state relative to the active bounded reference target
- successor-quality roadmap, composite evaluation, weakest-dimension tracking, and next-pack recommendation

The browser home page now has a separate `Candidate Admission` section. That section is conservative and operator-owned:

- it records approve / defer / reject as artifact-backed admission state
- it may mark an `admitted_bounded_baseline_candidate`
- it does not replace any live baseline or protected-surface reference in this slice

That layer is recommendation-only. It does not auto-promote a new baseline or start an open-ended continuation loop.

After admission approval, the browser now also exposes an `Admitted Candidate Lifecycle` view derived from:

- `artifacts/successor_admitted_candidate_latest.json`
- `artifacts/successor_admitted_candidate_handoff_latest.json`
- `artifacts/successor_baseline_comparison_latest.json`
- `artifacts/successor_reference_target_latest.json`
- `artifacts/successor_reference_target_consumption_latest.json`

That lifecycle shows:

- what candidate bundle was admitted
- whether the candidate is handoff-ready
- whether it is stronger than the current bounded baseline under the packaged comparison rubric
- whether it is eligible as a future bounded reference target
- whether a later run actually consumed that target or fell back to the protected baseline
- what bounded remediation is still proposed if the comparison is not strong enough yet

This remains non-destructive. The admitted candidate may be recorded and used as a future bounded reference target without replacing any live or protected baseline surface in this slice.

## Review, Reseed, And Continuation

After bounded successor completion, the browser home page now includes a conservative `Review, Reseed, And Continuation` section.

That section reads the current review and next-objective proposal artifacts and lets the operator explicitly:

- approve
- approve and continue
- defer
- reject

The resulting continuation state is written as auditable artifacts inside the active workspace:

- `artifacts/successor_reseed_request_latest.json`
- `artifacts/successor_reseed_decision_latest.json`
- `artifacts/successor_continuation_lineage_latest.json`
- `artifacts/successor_effective_next_objective_latest.json`

This still does not create an automatic endless loop. Approval is required before continuation, and the approved next objective is then launched only through the same canonical launcher and governed-execution chain.

## Auto-Continue Policy

The browser home page now also includes an `Auto-Continue Policy` section.

This is an operator-owned convenience layer, not a second authority path. It is:

- disabled by default
- limited to explicit bounded objective classes
- chain-capped
- fallback-safe to manual review

It may materialize and, when the current governed-execution invocation still has remaining cycle budget, start an eligible already-approved next objective class without another approval click only when the class is whitelisted, first-entry approval rules are satisfied, and the configured chain cap has not been reached.

Artifacts:

- `operator_state/successor_auto_continue_policy_latest.json`
- `artifacts/successor_auto_continue_state_latest.json`
- `artifacts/successor_auto_continue_decision_latest.json`

The browser observability views expose whether auto-continue is enabled, why it did or did not happen, whether the next objective was only authorized/materialized or actually started in the same session, and whether the current step was manual or policy-auto-continued.

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
