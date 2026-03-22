# NOVALI Standalone Package

Read this file first.

This handoff package is the current release-candidate shape for one `novali-v5` agent:

- package version: `novali-v5-standalone-rc15`
- delivery model: zip-delivered single-agent Docker package
- operator UX: unzip -> load image -> run launcher -> open browser -> initialize
- canonical authority path: `operator shell -> launcher -> frozen session -> bootstrap -> governed execution`

The Docker container is the execution envelope for that path. It is not a second authority path.

Canonical browser entrypoint inside the package/container:

`python -m novali_v5.web_operator`

## First Run

If you only follow one path, use this one:

1. Unzip the package to a local folder you can write to.
2. Run `launch\02_run_browser_operator.bat`.
   Or use `launch\02_run_browser_operator.ps1`.
3. If the image is not loaded yet, the helper loads `image\novali-v5-standalone.tar`.
4. Open `http://127.0.0.1:8787/` in the browser.
5. In the browser UI, go to `Directive` and either:
   - choose `samples/directives/standalone_valid_directive.example.json` for a happy-path validation run, or
   - download the directive scaffold and save a real directive into `directive_inputs/`
6. In `Runtime Constraints And Envelope`, keep backend `local_guarded` for the packaged single-container browser flow, and use execution profile `bootstrap_only_initialization` for the first launch.
7. In `Launch / Resume`, keep `new_bootstrap` and `bootstrap_only`, then launch.
8. After successful initialization, switch to execution profile `bounded_active_workspace_coding` when you want governed post-bootstrap work in `novali-active_workspace/<workspace_id>/`.
9. For that bounded coding path, use `resume_existing` and `governed_execution`.
10. Current governed-work controller is conservative and operator-owned:
    - `single_cycle` runs one bounded cycle per `governed_execution` invocation, then returns control.
    - `multi_cycle` may continue through several bounded cycles in one invocation until directive completion, no admissible work, failure, or the operator-selected cap.
11. Continuation quality is now evidence-backed. Before each next-cycle decision, NOVALI consults read-only internal trusted planning evidence from `trusted_sources/knowledge_packs/` together with current workspace artifacts.
12. Typical bounded successor progression is now:
    - planning baseline
    - first implementation bundle
    - continuation gap analysis
    - successor readiness bundle
13. When that bounded successor package is complete, NOVALI now writes explicit review-and-promotion artifacts instead of silently implying that promotion or reseeding should happen automatically.
14. A first implementation bundle is not treated as directive completion by itself. Completion is now evaluated against the packaged successor-completion knowledge pack and current workspace outputs.
15. In `single_cycle` mode, run `governed_execution` again when the latest cycle summary recommends another bounded step. In `multi_cycle` mode, the controller may continue automatically until it reaches an explicit stop reason.
16. After completion, review remains explicit:
    - review status is recorded
    - promotion readiness is evaluated conservatively
    - a next bounded objective may be proposed
    - automatic continuation is still not authorized until an operator records a reseed decision or enables a bounded auto-continue policy for an already-approved objective class
17. Use the `Review, Reseed, And Continuation` section on the browser home page to inspect the latest proposal and explicitly:
    - approve
    - approve and continue
    - defer
    - reject
18. An approved reseed materializes the next bounded objective through artifact-backed lineage:
    - `artifacts/successor_reseed_request_latest.json`
    - `artifacts/successor_reseed_decision_latest.json`
    - `artifacts/successor_continuation_lineage_latest.json`
    - `artifacts/successor_effective_next_objective_latest.json`
19. Optional operator-owned auto-continue now exists for whitelisted bounded objective classes. It is disabled by default, it never bypasses the canonical launcher chain, and it never turns this slice into an endless loop. Its artifacts are:
    - `operator_state/successor_auto_continue_policy_latest.json`
    - `artifacts/successor_auto_continue_state_latest.json`
    - `artifacts/successor_auto_continue_decision_latest.json`
20. When enabled, auto-continue only materializes an eligible already-approved next objective class for the next governed run. If the proposal is ineligible, the chain cap is reached, or first-entry approval is still required, the flow falls back to explicit manual review.
21. Use the browser observability pages to inspect the latest run without hunting through files manually:
    - `/observability`
    - `/workspace`
    - `/timeline`
    - `/cycle`

Inside the packaged standalone browser UI, `local_docker` is not the intended default. The current container already provides the Docker execution envelope. Keep `local_docker` for operator-host flows that have direct Docker access outside the standalone container.

Use `samples/directives/standalone_incomplete_directive.example.json` only when you intentionally want a clarification/refusal test.

## What Is In This Package

- `README_FIRST.md`
  - this primary operator guide
- `image/`
  - prebuilt image archive and image manifest
- `launch/`
  - simplest packaged load/run helpers
- `docs/`
  - supporting operator and technical guides
- `samples/`
  - non-authoritative examples only
- `directive_inputs/`
  - where real formal directive files should go
- `trusted_sources/`
  - operator-provided local trusted-source material
  - packaged internal knowledge packs also live here as read-only planning evidence
- `operator_state/`
  - operator-owned policy/session files
- `novali-active_workspace/`
  - bounded governed mutable-shell work outputs for post-bootstrap coding runs
- `runtime_data/state/`
  - persisted NOVALI canonical artifacts
- `runtime_data/logs/`
  - runtime and helper logs
- `runtime_data/acceptance_evidence/`
  - exported evidence snapshots

Compatibility folders are also present:

- `data/`
- `logs/`

Those exist because some current defaults still recognize them. For standalone use, prefer `runtime_data/state` and `runtime_data/logs`.

For bounded coding runs, inspect outputs under `novali-active_workspace/<workspace_id>/`. The packaged launcher mounts that folder into the container so governed work products remain visible on the host.

The packaged browser UI now includes read-only observability pages over those same persisted artifacts:

- latest run overview: `/observability`
- workspace artifact browser: `/workspace`
- runtime event timeline: `/timeline`
- latest cycle summary: `/cycle`

Those views now also show:

- controller mode
- cycles completed
- explicit stop reason
- per-cycle summary links
- trusted planning evidence summaries
- missing deliverables and next-step derivation
- directive-completion evaluation
- review status, promotion recommendation, and next-objective proposal
- reseed decision state and continuation lineage
- effective approved next objective when one has been materialized
- auto-continue policy, chain state, and the last continuation reason

## Audit Files

Use these files when you want to verify exactly what package you received:

- `handoff_layout_manifest.json`
  - package version, image tag, default command, primary scripts, localhost URL
- `image/image_archive_manifest.json`
  - image-archive presence, archive hash, image tag, default command, preferred load/run scripts

## Directive Files

Directive-first bootstrap remains mandatory.

Use a formal `NOVALIDirectiveBootstrapFile` only.

Good packaged starting points:

- valid starter sample:
  - `samples/directives/standalone_valid_directive.example.json`
- refusal test sample:
  - `samples/directives/standalone_incomplete_directive.example.json`
- scaffold helper:
  - `standalone_docker/generate_directive_scaffold.ps1`

Incomplete directives are expected to trigger clarification/refusal before activation. That is correct behavior.

See:

- [STANDALONE_OPERATOR_GUIDE.md](./docs/STANDALONE_OPERATOR_GUIDE.md)
- [DIRECTIVE_AUTHORING_GUIDE.md](./docs/DIRECTIVE_AUTHORING_GUIDE.md)
- [LOCALHOST_WEB_OPERATOR_UI.md](./docs/LOCALHOST_WEB_OPERATOR_UI.md)

## Trusted Sources And Secrets

Do not put raw secrets in directives.

Use:

- environment variables, or
- `trusted_source_secrets.local.json`

Bindings remain metadata/reference only. For a safe packaged placeholder flow, start with:

- `samples/trusted_sources/standalone.env.template`

This release-candidate package also includes read-only internal planning evidence under:

- `trusted_sources/knowledge_packs/successor_completion_knowledge_pack_v1.json`
- `trusted_sources/knowledge_packs/workspace_continuation_knowledge_pack_v1.json`
- `trusted_sources/knowledge_packs/successor_promotion_review_knowledge_pack_v1.json`

Those knowledge packs do not grant permissions or override governance. They are evidence inputs used to evaluate missing bounded deliverables, derive the next admissible cycle, and assess promotion readiness conservatively.

## Runtime Constraints

Runtime constraints remain operator-owned and are frozen before launch.

Current enforcement classes remain honest:

- `hard_enforced`
- `watchdog_enforced`
- `unsupported_on_this_platform`

Do not treat unsupported controls as guarantees.

For the packaged standalone single-container path, keep backend `local_guarded` in the browser UI. The standalone container is already the Docker envelope for that operator session.

The bounded coding profile is intentionally narrow. It authorizes writes only inside the frozen active workspace plus approved generated/log roots. It does not authorize broad mutation of the packaged NOVALI surfaces.

Directive completion is also conservative. The controller now stops with `completed_by_directive_stop_condition` only when the bounded successor-completion rubric is satisfied inside the active workspace. A planning bundle plus first implementation bundle alone is not considered complete if required bounded docs, tests, or readiness artifacts are still missing.

After bounded completion, the controller now writes:

- `artifacts/successor_review_summary_latest.json`
- `artifacts/successor_promotion_recommendation_latest.json`
- `artifacts/successor_next_objective_proposal_latest.json`

After operator review, the continuation bridge may also write:

- `artifacts/successor_reseed_request_latest.json`
- `artifacts/successor_reseed_decision_latest.json`
- `artifacts/successor_continuation_lineage_latest.json`
- `artifacts/successor_effective_next_objective_latest.json`

Those artifacts keep human governance explicit. A proposal may be approved, rejected, or deferred, and only an approved reseed materializes the next bounded objective for the next governed run.

If you want less friction without granting broader autonomy, use the browser `Auto-Continue Policy` section. It is operator-owned, whitelist-based, chain-capped, and still records why a continuation did or did not happen.

## Logs, Artifacts, And Evidence

Recommended packaged locations:

- canonical artifacts: `runtime_data/state/`
- logs: `runtime_data/logs/`
- evidence exports: `runtime_data/acceptance_evidence/`
- operator-owned session/policy files: `operator_state/`

## Supporting Guides

Use these only as supporting references after reading `README_FIRST.md`:

- [STANDALONE_OPERATOR_GUIDE.md](./docs/STANDALONE_OPERATOR_GUIDE.md)
- [STANDALONE_HANDOFF_ACCEPTANCE.md](./docs/STANDALONE_HANDOFF_ACCEPTANCE.md)
- [STANDALONE_DOCKER_QUICKSTART.md](./docs/STANDALONE_DOCKER_QUICKSTART.md)
- [RUNTIME_ENVELOPE.md](./docs/RUNTIME_ENVELOPE.md)
- [OPERATOR_SHELL.md](./docs/OPERATOR_SHELL.md)
- [LAUNCH_MATRIX.md](./docs/LAUNCH_MATRIX.md)
- [ACTIVE_VERSION_STATUS.md](./docs/ACTIVE_VERSION_STATUS.md)

## Honest Limits In This Release-Candidate Slice

Implemented now:

- one standalone Docker image archive path
- one standalone single-container launch path
- one browser-first localhost operator path
- directive-first governed bootstrap
- operator-owned frozen runtime constraints and runtime envelope

Still deferred or intentionally unsupported:

- Kubernetes and swarm orchestration
- remote/multi-user security model
- any runtime guarantee beyond the current honest enforcement classifications
- any change to routing, thresholds, live policy, benchmark semantics, or the immutable kernel

## Packager-Only Notes

If you are preparing this handoff package rather than consuming it:

1. Build the image:
   - `.\standalone_docker\build_standalone_image.ps1`
2. Export the image archive:
   - `.\standalone_docker\export_standalone_image_archive.ps1`
3. Assemble the handoff package:
   - `.\standalone_docker\assemble_handoff_package.ps1 --output-root .\dist --zip`

Packager steps are not the primary end-user path.
