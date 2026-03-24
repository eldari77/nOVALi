# NOVALI Version Status

`novali-v5` is the active development branch.

`novali-v4` remains the frozen governance-memory reference and operator surface.

Canonical human-facing local launch for `novali-v5` is:

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

Current branch-transition handoff / roadmap / project-state source of truth for this branch:

- `NOVALI_Consolidated_Handoff_and_Roadmap_2026-03-21.md` in the development branch root

Supporting branch-transition artifact:

- `data/branch_transition_status.json` in a live working tree or runtime state root

The copied `2026-03-20` handoff remains historical reference only.

## Current Operating Stance

- active development branch: `novali-v5`
- frozen reference / operator surface: `novali-v4`
- frozen fallback/reference: `novali-v3`
- older frozen fallback/reference: `novali-v2`
- branch state carried forward: `paused_with_baseline_held`
- operating stance carried forward: `hold_and_consolidate`
- held baseline carried forward: `proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1`
- carried-forward hardened incumbent-quality candidate: `swap_C = recovery_02 + recovery_03 + recovery_12`
- routing remains deferred
- live policy, thresholds, and frozen benchmark semantics remain unchanged

Template names may still retain `v4` lineage labels where that matches the established governed artifact family. New edits should still land in `novali-v5`.

## Local Operator Shell Milestone

The local operator-shell milestone is complete for `novali-v5`.

Manual validation completed on:

- happy-path directive bootstrap through the canonical operator shell
- governed refusal / clarification-required handling for an incomplete directive
- restart from persisted state with consistency passed and execution-ready posture
- frozen operator session validity and canonical artifact presence checks
- honest runtime-constraint visibility across `hard_enforced`, `watchdog_enforced`, and `unsupported_on_this_platform`

This closeout does not widen NOVALI authority or runtime claims.

Still intentionally deferred:

- Kubernetes/orchestrator work
- any new routing, threshold, live-policy, benchmark-semantic, or kernel changes

## Runtime Envelope Track

The next hardening track has now started in `novali-v5` with a backend-neutral runtime envelope model and Docker-first scaffolding.

Current state:

- `OperatorRuntimeEnvelopeSpec` now exists as operator-owned policy
- `local_guarded` remains the default backend
- `local_docker` now exists as an experimental opt-in backend scaffold
- live `local_docker` bootstrap/refusal/restart validation has now been completed on a Docker-capable workstation
- standalone single-container Docker handoff packaging assets now exist in the branch
- Kubernetes remains deferred and unimplemented
- operator-owned runtime controls remain frozen outside agent-owned self-structure

Still intentionally deferred inside this track:

- Kubernetes execution
- cluster/orchestrator policy work
- final dependency-locked standalone runtime image hardening beyond the currently validated bootstrap/control-plane slice
- any broader runtime guarantee claims beyond current hard/watchdog/unsupported classifications

## Standalone Handoff Readiness

The near-term product target remains a zip-delivered standalone package for one NOVALI agent.

Release-candidate closeout status for the standalone browser-first package is now materially in place and focused on one clean operator handoff story through `README_FIRST.md`.

Current release-candidate closeout points:

- one primary packaged onboarding story through `README_FIRST.md`
- clearer package/image manifest auditing
- simpler packaged helper messaging for less-technical operators
- browser-first packaged validation from an unpacked handoff directory

Current handoff/readiness state:

- one canonical standalone Docker image path is defined: `novali-v5-standalone:local`
- one packaged standalone image archive path is now defined: `image/novali-v5-standalone.tar`
- current packaged standalone release-candidate version: `novali-v5-standalone-rc37`
- one preferred standalone localhost web launch path is defined: `python -m novali_v5.web_operator`
- one packaged launcher path is now defined: `launch\02_run_browser_operator.ps1`
- one canonical standalone container wrapper is defined: `.\standalone_docker\run_web_operator_container.ps1`
- the desktop GUI remains available as a transitional surface
- a zip-ready handoff layout and assembly helper now exist
- operator-facing directive authoring, GUI/init, credential, runtime-constraint, and standalone acceptance docs now exist
- packaging remains single-container and operator-oriented
- a bounded post-bootstrap coding path now exists through execution profile `bounded_active_workspace_coding`
- bounded coding writes are constrained to `novali-active_workspace/<workspace_id>/` plus approved generated/log roots
- conservative multi-cycle governed execution now evaluates continuation using packaged internal trusted planning evidence under `trusted_sources/knowledge_packs/`
- bounded successor completion is now evaluated against packaged successor-completion criteria rather than shallow “first implementation exists” heuristics
- read-only browser observability now surfaces trusted planning evidence, missing deliverables, next-step derivation, and completion evaluation artifacts
- bounded successor completion now also produces review, promotion-recommendation, and next-objective proposal artifacts for operator-visible post-completion governance
- operator-authorized reseed now materializes explicit continuation request, decision, lineage, and effective-next-objective artifacts before any follow-on bounded run
- operator-owned auto-continue policy now exists for whitelisted bounded objective classes, with explicit chain caps, state/decision artifacts, and fallback to manual review
- same-session auto-continue execution now bridges directly into the next eligible bounded cycle when policy gates pass and the current invocation still has remaining cycle budget
- generation-over-generation progress governance now records admitted-candidate lineage, explicit deltas, and conservative continue/remediate/pause/escalate recommendations without mutating the protected live baseline
- a bounded strategy-selection layer now consumes generation-history and progress-governance artifacts to recommend the next bounded work mode, its rationale, and the next follow-on family without broadening authority or mutating the protected live baseline
- a bounded campaign-governance layer now accumulates successive strategy waves into explicit campaign history, campaign deltas, convergence/diminishing-returns signals, and conservative continue/shift/refresh/pause recommendations without broadening authority or mutating the protected live baseline
- a bounded campaign-cycle governance layer now compares completed campaign cycles across rolled reference targets, records cycle-over-cycle deltas and diminishing-returns signals, and conservatively recommends whether to start another campaign, hold the new reference target, remediate, or pause for review without broadening authority or mutating the protected live baseline
- the packaged standalone launcher now creates and mounts `runtime_data/generated/` so fresh handoff roots satisfy saved bounded-coding runtime policies before live branch validation begins
- near the counted cycle cap, explicitly whitelisted compact follow-on objectives can now run in-session with artifact-backed staging rationale instead of spilling silently into a fresh invocation
- once an admitted candidate is already the active bounded reference target, a later bounded review can now propose one conservative successor-quality follow-on objective before repeating candidate-promotion work, enabling the first real packaged skill-pack path without changing the authority chain
- post-skill-pack quality chains now write an explicit reentry artifact and can derive a conservative compact test-strengthening follow-on from a completed readiness/manifest step, which makes cycle-cap stops and reentry actions more explicit without loosening hard caps
- candidate promotion bundles now also pass through an explicit baseline-admission review gate with recommendation, decision, and remediation artifacts, while still avoiding any protected-surface baseline replacement
- approved admission now also materializes an admitted-candidate handoff, bounded baseline comparison, and future bounded reference-target artifact set without replacing the protected live baseline
- a first bounded skill-pack layer now exists under `trusted_sources/skill_packs/`, explicitly distinct from read-only knowledge packs, and successor-quality runs now write skill-pack invocation/result plus quality-gap/improvement artifacts inside the active workspace
- successor-quality work is now also sequenced through explicit roadmap, priority-matrix, composite-evaluation, and next-pack-plan artifacts so NOVALI can improve across more than one bounded quality dimension relative to the admitted candidate reference target
- when that improved successor becomes materially stronger in aggregate, NOVALI can now materialize a revised candidate bundle, send it back through explicit promotion/admission review, and roll the future bounded reference target forward to the revised admitted candidate without replacing the protected/live baseline
- `bootstrap_only_initialization` remains available and unchanged for pure initialization runs

Still intentionally deferred in the product track:

- Kubernetes and multi-agent/swarm orchestration
- any second authority path outside directive-first bootstrap plus the operator launcher chain
