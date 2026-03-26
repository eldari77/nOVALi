# NOVALI Version Status

`novali-v6` is the active development branch.

`novali-v5` is the frozen reference / operator surface baseline.

`novali-v4` remains a preserved historical reference, not the primary live reference.

Current closeout-ready standalone reference package:

- `novali-v5-standalone-rc44`

Current canonical v6 standalone handoff artifact:

- `dist/novali-v6_rc07-standalone.zip`

Canonical human-facing local launch for the frozen `novali-v5` reference surface remains:

- preferred standalone/browser surface: `python -m novali_v5.web_operator`
- transitional desktop surface: `python -m novali_v5.operator_shell`
- equivalent convenience form for the preferred browser surface: `python -m novali_v5`

Direct `main.py` and `bootstrap.py` entrypoints remain available only as non-canonical developer/test surfaces.

Current operator acceptance references:

- [HANDOFF_PACKAGE_README.md](./HANDOFF_PACKAGE_README.md)
- [DIRECTIVE_AUTHORING_GUIDE.md](./DIRECTIVE_AUTHORING_GUIDE.md)
- [LOCALHOST_WEB_OPERATOR_UI.md](./LOCALHOST_WEB_OPERATOR_UI.md)
- [STANDALONE_HANDOFF_ACCEPTANCE.md](./STANDALONE_HANDOFF_ACCEPTANCE.md)
- [MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md](./MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md)

## Canonical Source Of Truth

Current branch-transition handoff / roadmap / project-state source of truth:

- `NOVALI_Consolidated_Handoff_and_Roadmap_2026-03-24.md`
- `data/branch_transition_status.json`
- `data/version_handoff_status.json`
- `data/branch_registry_latest.json`

Historical handoff references retained for context:

- `NOVALI_Consolidated_Handoff_and_Roadmap_2026-03-21.md`
- `NOVALI_Consolidated_Handoff_and_Roadmap_2026-03-20.md`

## Current Branch Authority

- active development branch: `novali-v6`
- frozen reference / operator surface baseline: `novali-v5`
- preserved historical reference: `novali-v4`
- older preserved references: `novali-v3`, `novali-v2`
- carried-forward branch state: `paused_with_baseline_held`
- carried-forward operating stance: `hold_and_consolidate`
- on-disk active working directory: this `novali-v6/` root
- active-root materialization mode: curated v6 scaffold copied from `novali-v5` source-facing surfaces while leaving generated/runtime outputs as fresh v6-owned placeholders
- held baseline carried forward: `proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1`
- carried-forward hardened incumbent-quality candidate: `swap_C = recovery_02 + recovery_03 + recovery_12`
- routing remains deferred
- live policy, thresholds, and frozen benchmark semantics remain unchanged

Template names may still retain legacy `v4` lineage labels where they refer to established governed artifact families. New branch-authority edits should now target `novali-v6`, while `novali-v5` stays frozen except for critical fixes.

## novali-v5 Closeout

`novali-v5` is now treated as a deliberate closeout-ready product/reference branch.

What `novali-v5` achieved:

- stable directive-first bootstrap as the sole canonical startup authority path
- stable browser-first operator flow: `browser UI / operator surface -> launcher -> frozen session -> bootstrap -> governed execution`
- stable bounded governed execution with explicit review / promotion / admission / reseed / continuation flows
- admitted-candidate lifecycle plus future-reference-target rollover without protected/live baseline replacement
- bounded skill-pack execution and successor-quality improvement sequencing
- bounded campaign, campaign-cycle, and loop-of-loops governance
- operator productization, workflow refinement, dashboard actionability, and showcase/demo polish
- closeout-ready packaged standalone reference at `novali-v5-standalone-rc44`

Closeout posture:

- `novali-v5` is frozen except for critical fixes
- `novali-v5` remains the operator-surface and packaged-reference baseline for future comparison
- `novali-v5` replaces `novali-v4` as the primary frozen reference line for the next generation

## novali-v6 Kickoff Posture

`novali-v6` begins from a stronger proven base than `novali-v5` did.

Starting posture:

- inherit the bounded governance/control-plane stack from `novali-v5` without reopening it immediately
- treat `novali-v5` as the frozen reference/operator surface baseline
- do not treat `novali-v4` as the primary live reference anymore
- keep baseline replacement deferred
- keep the canonical browser-first directive/launcher/bootstrap/governed-execution flow unchanged
- use `novali-v6` for the next generation of bounded agent-development work

Initial v6 mission framing remains conservative:

- design and implement the next-generation bounded agent from the frozen `novali-v5` reference line
- keep delivery workspace-local and bounded
- aim toward successor handoff completeness and single-zip successor delivery
- do not treat this kickoff as authorization for broad new runtime or governance changes

## Runtime / Product Continuity

This transition does not widen NOVALI authority or runtime claims.

Still unchanged:

- directive-first canonical authority
- routing logic
- thresholds
- live policy
- benchmark semantics
- protected core surfaces
- protected/live baseline behavior
- Kubernetes and live trusted-source networking remain deferred

`novali-v5-standalone-rc44` remains the frozen closeout-ready package reference. `dist/novali-v6_rc07-standalone.zip` is the current canonical v6 handoff build for this active branch, and this rc07 rebuild remains fully self-contained with the bundled Docker image archive included while carrying the trusted-source cost/budget/retry governance layer on top of the operator-driven external mission path. This transition updates branch authority and source-of-truth artifacts, and this directory root now serves as the materialized active working scaffold; it does not change packaged runtime behavior.

## Deferred Items Carried Forward

- automatic live baseline replacement
- endless reseeding
- live trusted-source querying
- broader writable roots
- Kubernetes / orchestrator work
- multi-agent orchestration
- deeper UX modernization track
- deferred operator UI modernization items:
  - modernized magic+technology UI
  - dark / green / dark-purple theme deepening
  - directive-core initialization animation sequence

## Summary

`novali-v5` is now clearly the frozen reference/product branch.

`novali-v6` is now clearly the active development branch.

This `novali-v6/` directory is now the on-disk active working root for future bounded mission work.

Future work should build from the proven `novali-v5` `rc44` reference line rather than anchoring primarily on `novali-v4`.
