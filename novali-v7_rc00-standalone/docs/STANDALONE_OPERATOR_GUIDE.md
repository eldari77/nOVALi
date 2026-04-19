# NOVALI Standalone Operator Guide

This is the primary operator-facing guide for the standalone `novali-v7` handoff package.

Branch-status note:

- this guide documents the active `novali-v7` clean baseline
- `novali-v6` is now the frozen historical reference line at `rc88.1`
- `novali-v5` remains older preserved historical context only

If you are working from an unpacked handoff package, read `README_FIRST.md` before this guide.

The current browser UI is intentionally more guided than earlier rc builds:

- the directive wrapper is presented as the initialization core
- the landing page now uses one integrated startup surface instead of splitting initialization status, startup guidance, and launch controls across separate panels
- bootstrap-only initialization is visually separated from the later governed-execution step
- the home page now emphasizes what step you are on and what the operator should do next before the lower-level control sections
- the top workflow guide now also tells you what changed, what NOVALI is waiting on, and when the saved runtime policy does not match the launch action you selected
- the dashboard pulse now makes system state, operator attention, current recommendation, and recent activity visible without opening a deeper page first
- the home, observability, workspace, timeline, and cycle pages now surface recent accomplishments, why the current result matters, and the most important outputs more directly for demo/readability use
- the default operator preset is now `Long-run / low-touch`, backed by the calibrated normal-bounded posture for practical multi-cycle work after initialization
- a `Focused / tighter-control` preset is available for narrower runs that should reach review and stop conditions sooner
- detailed provider, governance, runtime, and auto-continue controls now live on a separate `Settings` page so normal startup does not require low-level tuning
- the landing page now also treats return visits as first-class: it distinguishes fresh-start, resume-ready, review-required, paused/held, and long-run continuation states before showing the launch form
- the continuity summary surfaces the active directive/workspace, last preset, effective policy continuity, last mission state, and next recommended operator action on return
- review-required and intervention-needed sessions now also surface through an explicit operator review workspace that groups pending decisions, explains why review is needed, recommends the next bounded action, and points to the relevant evidence pages
- trusted-source mission policy is now explicit at operator level: a bounded mission may stay local-only, reuse indexed trusted-source knowledge, justify a bounded external re-query, or stop for operator review before further escalation
- trusted-source external escalation now also shows explicit budget, retry, and cost-governance posture so an operator can see when NOVALI chose the cheapest sufficient path and when it stopped retrying instead of spending more external budget

The intended product flow is:

`unzip -> load image if needed -> run launcher -> open browser -> initialize NOVALI`

Canonical authority remains unchanged:

`browser UI / operator surface -> launcher -> frozen session -> bootstrap -> governed execution`

SvelteKit entrypoint (rc51+) is:

`http://127.0.0.1:8787/shell`

If `operator_shell/web_ui/build` is missing, that route falls back to the existing
legacy operator surfaces (`/`, `/observability`, `/workspace`) so operator startup and continuity behavior stay intact.

To enable the SvelteKit shell in this package, run before launch or packaging:

```powershell
npm --prefix operator_shell/web_ui install
npm --prefix operator_shell/web_ui run build
```

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
- `runtime_data/generated/`
  - bounded generated outputs used by packaged runtime-policy profiles
- `runtime_data/acceptance_evidence/`
  - exported evidence snapshots
- canonical `v7rc00` handoffs include the bundled image archive under `image/novali-v7-standalone.tar`
- canonical rc51 handoffs also include a curated successor-improvement bundle under `runtime_data/acceptance_evidence/successor_improvement/`
- canonical rc51 handoffs surface operator-configurable trusted-source governance controls in the packaged UI and observability pages
- canonical rc51 handoffs also include multi-mission trusted-source policy calibration artifacts for cross-mission comparison
- canonical rc49 handoffs add explicit session continuity artifacts, resume-aware landing guidance, the operator review workspace, operational review-action controls, a mission-integrated Librarian delegation path, a mission-integrated Controller-governed Verifier path that checks returned bundles before the Controller decides whether adoption is ready, the fixed sequential Librarian-to-Verifier mission workflow when both bounded steps materially strengthen the same mission, the converged startup surface that keeps initialization status, missing-state clarity, and launch controls together, the rc20 delegation-plan layer that makes blocked delegation options and the typed Librarian-to-Verifier handoff visible before final Controller adoption, the rc21 delegation-evidence layer that surfaces recent path outcomes, blocked-option trends, and advisory recommendation support, the rc22 recommendation-quality layer that adds clearer reason summaries, conservative local fallbacks under ambiguity, the rc23 recommendation-audit layer that shows recommendation versus chosen path versus later bounded outcome together with calibration summaries, the rc24 recommendation-stability layer that shows the active evidence window, recency posture, contradiction/drift posture, stale support, and conservative local fallback reasons directly in the packaged operator surfaces, the rc25 recommendation-governance layer that makes follow, hold, defer, override, and no-strong-recommendation posture explicit on Home, Observability, and the review workspace without widening authority, the rc26 intervention-audit layer that keeps later follow/override/hold/defer/no-strong outcomes visible for audit and calibration without turning operator history into automatic policy, the rc27 intervention-prudence / trust-signal layer that surfaces bounded prudence summaries and conservative reliability wording without turning intervention history into hidden preference learning, the rc28 governance-summary / recommendation-state consolidation layer that surfaces one bounded governance snapshot without hiding the underlying artifact-backed recommendation, stability, audit, prudence, trust, and no-strong-recommendation detail, the rc29 governance-trend / temporal-drift layer that shows whether that bounded governance state is strengthening, weakening, oscillating, or drifting more cautious/supportive over time without turning history into hidden policy synthesis, the rc30 operator decision-support / action-guidance layer that surfaces the suggested next operator action, action-guidance posture, and bounded why-not-other-actions detail without creating automatic execution or a second authority path, the rc31 operator action-readiness / guided-handoff layer that surfaces action readiness, blockers, missing evidence, and the next bounded surface without creating automatic execution or hidden policy synthesis, the rc32 operator-flow / demo-readiness layer that surfaces current step, next step, success condition, and bounded surface-to-surface handoff clarity without creating a special demo mode or hidden policy synthesis, the rc33 bounded demo-scenario scaffolding layer that surfaces one packaged sample-directive walkthrough, current demo run readiness, explicit operator walkthrough steps, expected outputs, and a reviewable success rubric without introducing demo-only runtime behavior, the rc34 bounded demo-execution evidence / result-capture layer that surfaces demo run status, produced/pending/reviewable outputs, result summaries, and an evidence trail without faking completion, the rc35 bounded demo-output completion / reviewable-artifact generation layer that surfaces output completion state, reviewable artifact inventory, completion summaries, and generated reviewable artifacts without faking broader completion, the rc36 bounded trusted-source demo scenario selection / directive-generation layer that preserves the local-first packaged baseline while surfacing one additional repo-aware trusted-source growth-demo candidate, its directive summary, expected knowledge-gap escalation point, bounded success rubric, and reusable skill-target definition without executing a live trusted-source run, the rc37 bounded trusted-source demo execution / growth-artifact capture layer that surfaces the local-first phase, explicit knowledge gap, minimal request/response capture, incorporation evidence, before/after delta, and the reusable trusted-reference-integration skill pack without widening authority, the rc38 bounded live trusted-source connectivity / external-evidence validation layer that preserves the baseline and preserved-source trusted-demo path while proving one real minimal OpenAI external request, response receipt, and non-secret connectivity evidence capture without leaking credentials or widening authority, the rc39 bounded live trusted-source demo result-improvement / before-after-delta layer that preserves that baseline, preserved-source path, and live-connectivity proof while using one minimal live external request to strengthen the trusted-source demo outputs, update the reusable skill pack, and persist non-secret improvement evidence without widening authority, the rc40 bounded demo-presentation / storyline consolidation layer that keeps the full proof chain readable with an ordered storyline, a concise narration guide, and a clear explanation of why the truthful end state remains awaiting review, the rc41 bounded demo-runbook / facilitator-mode layer that keeps that same proof chain intact while adding a repeatable runbook, facilitator checklist, artifact-backed checkpoints, and an acceptance rubric so the operator can run the demo without improvisation while still ending truthfully at awaiting review, the rc42 packaged demo completeness / rubric-closure layer that closes the rc41 packaged proof gaps so the shipped runbook rubric can truthfully land at `pass_with_review_gate` without weakening the final `awaiting_review` state, the rc43 demo handoff-kit / presenter-package layer that adds a presenter handoff summary, quickstart sheet, audience summaries, pre-demo sanity guidance, and post-demo review pointers so the shipped demo can be handed to another operator without weakening either `pass_with_review_gate` or `awaiting_review`, the rc44 audience-mode / short-form demo optimization layer that adds a five-minute short form, a fuller walkthrough mode, must-show checkpoint priorities, and audience-specific talk tracks so the shipped demo is easier to deliver without weakening either `pass_with_review_gate` or `awaiting_review`, the rc45 bounded real-work benchmark baseline layer that preserves that shipped demo stack while adding one successor package readiness review bundle refresh benchmark lane, its directive, output contract, success rubric, operator-value summary, and selection rationale without claiming the workflow is already executed, the rc46 bounded real-work benchmark execution layer that keeps that benchmark fixed while producing the first local-first readiness bundle, surfacing the produced-output inventory, and classifying the run truthfully without broadening authority, the rc47 bounded real-work benchmark closure / repeatability layer that re-runs that same benchmark in a fresh bounded context, records closure and repeatability evidence, narrows the `successor_readiness_bundle` gap to rebuilt-handoff review, and keeps promotion explicitly review-gated without broadening authority, the rc48 bounded benchmark closure-decision / promotion-packet layer that preserves that benchmark lane while turning the repeatability, closure, and promotion-readiness evidence into an explicit promote/hold/defer/blocked operator packet without broadening authority, and the rc49 bounded review-action / promotion-outcome layer that preserves that same benchmark lane while turning the rc48 decision packet into an explicit operator review packet, review checklist, review decision template, and awaiting-confirmation promotion outcome without fabricating human confirmation or broadening authority
- rc49 remains the prior canonical milestone for the review-action layer; rc50 adds the explicit review-confirmation / promotion-outcome capture layer, and the current repo-root persisted truth now records explicit operator confirmation with `promotion_confirmed_with_review_gate` and `no_material_confirmation_gap` while preserving the explicit review gate as advisory-only
- `samples/`
  - non-authoritative sample directives and configuration examples

## Fastest Operator Path

On Windows, the simplest launch path is:

1. Open the unpacked package folder.
2. Run `launch\02_run_browser_operator.bat`.
3. If the image tag is not already loaded, the script loads `image\novali-v7-standalone.tar`.
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

When you return later, start at Home instead of reopening setup from scratch:

- the integrated startup summary shows whether NOVALI sees a fresh path, a resume-ready governed session, a review-required stop, a held/completed state, or an active long-run continuation
- the current session summary repeats directive id, workspace id, last preset, and current policy continuity
- the same surface also shows what is missing, why the current step matters, and the exact next action without leaving Home
- when review is required, the Home review workspace summarizes pending decisions, explains the review reason in operator language, shows recommended actions, lets you record bounded approve/defer/reject/acknowledge actions, and links straight to Observability, Workspace, Timeline, Cycle, or Settings
- `/settings` remains the place for advanced tuning; it is not required for ordinary resume flow

Browser observability pages for operator spot checks:

- `/observability`
  - latest run status, workspace id/root, controller mode, cycles completed, stop reason, next cycle, and artifact paths
- `/workspace`
  - grouped view of `plans/`, `docs/`, `src/`, `tests/`, and `artifacts/`
- `/timeline`
  - runtime JSONL events rendered as a readable timeline
- `/cycle`
  - latest planning or implementation cycle summary, created files, skipped items, and deferred items

Trusted-source provider onboarding is now operator-visible on the browser `Settings` page:

- set the external provider base URL explicitly
- paste a session-only API credential or point to a local credential file
- run `Validate External Provider`
- confirm non-secret readiness artifacts:
  - `trusted_source_credential_status_latest.json`
  - `trusted_source_provider_status_latest.json`
  - `trusted_source_handshake_latest.json`
  - `trusted_source_session_contract_latest.json`
  - `trusted_source_request_contract_latest.json`
  - `trusted_source_response_template_latest.json`
- the raw secret is not written into repo files, workspace artifacts, or ordinary logs

For packaged Docker use, `standalone_docker/run_web_operator_container.ps1` now passes through these session env vars when present:

- `OPENAI_API_KEY`
- `NOVALI_TRUSTED_SOURCE_API_BASE_URL`

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
- successor skill-pack selection, quality-gap summary, and quality-improvement result artifacts
- successor quality roadmap, priority matrix, composite evaluation, and next-pack recommendation
- successor generation history, per-generation delta, and conservative progress-governance recommendation
- successor strategy selection, strategy rationale, and bounded follow-on family recommendation
- quality-chain reentry state, next staged quality objective, and recommended reentry action

When an admitted candidate is already the active bounded reference target, a later bounded review may now propose one conservative successor-quality follow-on objective before repeating candidate-promotion work. That follow-on still goes through the same explicit review/reseed path.

Post-skill-pack quality-chain reentry is now explicit:

- `artifacts/successor_quality_chain_reentry_latest.json`
- the artifact tells you whether the current quality step is complete, whether another bounded quality objective was staged, whether it was deferred because of cycle budget, and what the operator should do next

Generation-over-generation progress is now explicit too:

- `artifacts/successor_generation_history_latest.json`
- `artifacts/successor_generation_delta_latest.json`
- `artifacts/successor_progress_governance_latest.json`
- `artifacts/successor_progress_recommendation_latest.json`
- those artifacts tell you whether the latest revised/admitted candidate is stronger than the prior admitted candidate, whether the lineage is plateauing or regressing, and whether another bounded improvement cycle is justified

Bounded strategy selection now sits on top of that progress evidence:

- `artifacts/successor_strategy_selection_latest.json`
- `artifacts/successor_strategy_rationale_latest.json`
- `artifacts/successor_strategy_follow_on_plan_latest.json`
- `artifacts/successor_strategy_decision_support_latest.json`
- those artifacts tell you what NOVALI is recommending next:
  - continue refining the current reference target
  - open a targeted remediation wave
  - start the next bounded quality wave
  - hold and observe
  - or pause for operator review
  and they keep that recommendation explicit without changing the protected/live baseline

NOVALI now also includes a bounded campaign-governance layer over successive strategy waves:

- `artifacts/successor_campaign_history_latest.json`
- `artifacts/successor_campaign_delta_latest.json`
- `artifacts/successor_campaign_governance_latest.json`
- `artifacts/successor_campaign_recommendation_latest.json`
- `artifacts/successor_campaign_wave_plan_latest.json`
- those artifacts explain which waves belong to the current campaign, what dimensions improved across the campaign, whether gains are still broadening or flattening, and whether NOVALI should continue, shift wave type, refresh the revised candidate, or pause for operator review

NOVALI now also includes a bounded campaign-cycle governance layer across rolled reference targets:

- `artifacts/successor_campaign_cycle_history_latest.json`
- `artifacts/successor_campaign_cycle_delta_latest.json`
- `artifacts/successor_campaign_cycle_governance_latest.json`
- `artifacts/successor_campaign_cycle_recommendation_latest.json`
- `artifacts/successor_campaign_cycle_follow_on_plan_latest.json`
- those artifacts explain how one completed campaign cycle compares to prior rolled-reference-target cycles and whether NOVALI should start another campaign, hold the new reference target, open targeted post-rollover remediation, or pause for operator review

NOVALI now also includes a bounded loop-of-loops governance layer across repeated refreshed-reference-target rollovers:

- `artifacts/successor_loop_history_latest.json`
- `artifacts/successor_loop_delta_latest.json`
- `artifacts/successor_loop_governance_latest.json`
- `artifacts/successor_loop_recommendation_latest.json`
- `artifacts/successor_loop_follow_on_plan_latest.json`
- those artifacts explain how one completed full campaign-refresh loop compares to prior completed loops and whether NOVALI should start another full loop, hold the current bounded target, allow only targeted remediation, or pause for operator review

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

The packaged container launcher now creates and mounts `runtime_data/generated/` for fresh handoff roots so saved bounded-coding policies do not fail just because the generated-output root was missing from an unpacked package.

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

NOVALI now also includes a first bounded skill-pack layer for successor-quality work:

- `trusted_sources/skill_packs/successor_workspace_review_pack_v1.json`
- `trusted_sources/skill_packs/successor_test_strengthening_pack_v1.json`
- `trusted_sources/skill_packs/successor_manifest_quality_pack_v1.json`
- `trusted_sources/skill_packs/successor_docs_readiness_pack_v1.json`
- `trusted_sources/skill_packs/successor_artifact_index_consistency_pack_v1.json`
- `trusted_sources/skill_packs/successor_handoff_completeness_pack_v1.json`

Keep these roles separate:

- knowledge packs are read-only planning and review evidence
- skill packs are bounded execution capabilities

Successor-quality sequencing is now also recorded explicitly:

- `novali-active_workspace/<workspace_id>/artifacts/successor_quality_roadmap_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_quality_priority_matrix_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_quality_composite_evaluation_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_quality_next_pack_plan_latest.json`

Those artifacts let an operator see which quality dimensions are tracked, which one is currently weakest, which pack should run next, and whether the successor is materially stronger than the admitted candidate in aggregate.

When a successor-quality gap is addressed through a skill pack, inspect:

- `novali-active_workspace/<workspace_id>/artifacts/successor_skill_pack_invocation_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_skill_pack_result_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_quality_gap_summary_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_quality_improvement_summary_latest.json`

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

After the bounded flow reaches a candidate promotion bundle, inspect the browser `Candidate Admission` section. That gate now records:

- `novali-active_workspace/<workspace_id>/artifacts/successor_baseline_admission_review_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_baseline_admission_recommendation_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_baseline_admission_decision_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_baseline_remediation_proposal_latest.json`

Admission remains conservative. The operator may approve, defer, or reject. Approval only marks an admitted bounded baseline candidate for audit and later review. It does not replace the live baseline or mutate protected surfaces.

After admission approval, NOVALI now writes an admitted-candidate lifecycle layer:

- `novali-active_workspace/<workspace_id>/artifacts/successor_admitted_candidate_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_admitted_candidate_handoff_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_baseline_comparison_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_reference_target_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_reference_target_consumption_latest.json`

Those artifacts preserve the admitted candidate as a reusable bounded handoff, compare it against the current bounded baseline rubric, record whether it is eligible as a future bounded reference target, and then record whether a later run actually consumed it as the active bounded reference target or fell back explicitly to the protected baseline. They do not replace the live baseline automatically.

The browser `Settings` page now includes the detailed `Auto-Continue Policy` controls. They remain operator-owned, disabled by default, whitelist-based, and chain-capped. They may materialize and, when the current invocation still has remaining cycle budget, start an eligible already-approved next objective class without another approval click only when:

- the objective class is whitelisted
- first-entry approval rules are satisfied
- the current invocation still has remaining counted cycle budget

After admission approval, the active workspace now records an explicit admitted-candidate lifecycle:

- `novali-active_workspace/<workspace_id>/artifacts/successor_admitted_candidate_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_admitted_candidate_handoff_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_baseline_comparison_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_reference_target_latest.json`
- `novali-active_workspace/<workspace_id>/artifacts/successor_reference_target_consumption_latest.json`

Those artifacts answer the next bounded lifecycle questions:

- what bounded candidate was admitted
- whether the admitted candidate is handoff-ready
- how it compares against the current bounded baseline rubric
- whether it is strong enough to be marked as a future bounded reference target
- whether a later run actually consumed that admitted candidate as the active bounded reference target
- what fallback reason applied if the protected baseline still had to be used
- what bounded remediation is still proposed if it is not strong enough yet

This layer remains conservative. It records an admitted candidate and a possible future bounded reference target. It does not replace the live baseline, rewrite protected surfaces, or change the canonical authority chain.
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


