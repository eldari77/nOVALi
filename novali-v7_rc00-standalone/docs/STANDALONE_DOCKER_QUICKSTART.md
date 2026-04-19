# NOVALI Standalone Docker Quickstart

This is the current single-agent standalone Docker handoff path for the active `novali-v7` clean baseline.

For packaged operator use, start with `README_FIRST.md`. This quickstart is a supporting reference, not the primary first-run guide.

Canonical authority path remains unchanged:

`operator shell -> launcher -> frozen session -> bootstrap -> governed execution`

The Docker container is an execution envelope, not a second authority path. The new preferred standalone surface is browser-based localhost initialization.

## Canonical image tag

Use this local image tag for the current standalone handoff slice:

`novali-v7-standalone:local`

## What this slice is validated for

The current Docker-backed validation in this repository covers:

- Docker preflight success on a Docker-capable host
- bootstrap happy path
- clarification/refusal path
- restart from persisted canonical state
- refusal when `network_api` trusted sources are enabled under `local_docker`
- packaged/containerized external trusted-source provider validation with non-secret credential/provider/handshake artifacts
- packaged observability for trusted-source budget, retry, and cost-governance posture

Current scope is intentionally bounded.

Bootstrap/control-plane behavior is validated.
Broader governed runtime paths may still depend on additional runtime dependencies that are not container-locked in this pass.

## Primary Operator Path

For less-technical end users, the primary path is the packaged prebuilt image archive, not a source build.

From the unpacked handoff package:

```powershell
.\launch\02_run_browser_operator.ps1
```

The canonical `v7rc00` handoff target is fully self-contained and includes the bundled Docker image archive at `image/novali-v7-standalone.tar`.

After the browser opens, Home now uses one integrated startup surface with the default `Long-run / low-touch` preset selected. That same surface shows current startup state, what is missing, the exact next safe action, the relevant directive/preset/runtime step cards, and the launch control itself without splitting startup across separate panels. On return visits, it still distinguishes fresh start, resume-ready, review-required, and held/continuation states truthfully. Review-required sessions continue to surface through the dedicated operator review workspace so the operator can see the pending decision, reason, recommended next move, and explicit approve/defer/reject/acknowledge controls before resuming. The packaged observability and review surfaces now also show the bounded Controller-child delegation prototype when a Librarian child is leased for mission-integrated library-hygiene/readiness support, when a Verifier child is leased to inspect returned bundles for contract/provenance/adoption-readiness before explicit Controller action, or when the Controller runs the fixed sequential Librarian-to-Verifier mission workflow before final adoption. Rc20 adds explicit delegation-plan visibility on top of that flow, rc21 adds delegation outcome evidence, recent path history, blocked-option trend visibility, and advisory recommendation support, rc22 makes that recommendation layer more conservative and legible by surfacing recommendation strength, evidence inputs, and why alternatives were not preferred, rc23 closes the loop with recommendation audit and calibration summaries that compare earlier recommendations with chosen bounded paths and later outcomes, rc24 makes the active evidence window, stability/drift posture, stale-support handling, and conservative local fallback reasons operator-visible instead of letting older support silently harden into hidden policy, rc25 makes recommendation-governance posture explicit by surfacing follow, hold, defer, override, and no-strong-recommendation state together with later audit tracking, rc26 adds intervention-audit and intervention-calibration visibility so the operator can see whether recent follows, overrides, holds, defers, and no-strong-recommendation postures later appeared supported, prudent, mixed, or unresolved without creating automatic policy mutation, rc27 adds intervention-prudence and recommendation-trust summaries so the operator can see whether recent intervention history currently supports caution, weak trust, mixed trust, or unresolved trust language without turning that history into hidden preference learning, rc28 adds one bounded governance-summary / recommendation-state layer so the operator can read the current recommendation, strength, stability, governance posture, operator action, intervention audit/prudence, trust signal, and no-strong-recommendation state together without losing the underlying detail, rc29 adds governance-trend / temporal-drift visibility so the operator can see whether that bounded governance state is strengthening, weakening, oscillating, or drifting more cautious/supportive over time without turning that history into hidden policy synthesis, rc30 adds explicit operator decision-support / action-guidance so the operator can see the suggested next bounded action, why it is suggested, and why alternative actions were not preferred without creating automatic execution, rc31 adds explicit operator action-readiness / guided-handoff visibility so the operator can see whether the suggested next action is ready now, what blockers or missing evidence remain, and which bounded surface to use next without creating automatic execution, rc32 adds explicit operator-flow / demo-readiness visibility so the operator can see the current step, next step, success condition, blockers, and next bounded surface as one coherent work loop without creating a demo-only path, rc33 adds one bounded packaged sample-directive demo scenario with explicit demo-run readiness, operator walkthrough steps, expected outputs, and a reviewable success rubric without introducing demo-only runtime behavior, rc34 adds explicit demo-execution evidence, produced-vs-pending output inventory, result summaries, and an evidence trail so packaged demo runs can stay truthful even when they are partial or awaiting more evidence, rc35 adds explicit demo-output completion state, reviewable artifact inventory, completion summaries, and generated reviewable artifacts so the packaged walkthrough can yield stronger reviewable evidence without faking broader completion, rc36 adds one bounded trusted-source demo candidate alongside that local-first baseline so operators can inspect the new repo-aware scenario definition, directive summary, knowledge-gap escalation point, and reusable skill-target before any live trusted-source run is attempted, rc37 executes that bounded trusted-source candidate in a reviewable way so operators can see the local-first phase, explicit knowledge gap, minimal request/response scope, incorporation evidence, before/after delta, and reusable skill-pack output without broadening authority, rc38 adds one bounded live OpenAI connectivity proof so operators can see a real minimal external request, response receipt, and non-secret evidence capture without widening authority, rc39 adds one bounded live trusted-source demo improvement layer so operators can see a real before/after delta, updated skill-pack guidance, and strengthened trusted-source demo outputs without widening authority, rc40 adds one bounded demo-presentation / storyline consolidation layer so operators can see the full local-first-to-live-improvement proof chain, a concise narration guide, and an explicit explanation of why the truthful end state remains awaiting review, rc41 adds one bounded demo-runbook / facilitator-mode layer so operators can see the repeatable run order, artifact-backed preflight checks, facilitator checkpoints, and the acceptance rubric that makes the final review gate easier to present without weakening it, rc42 adds one packaged demo completeness / rubric-closure layer so the shipped handoff carries forward the live-connectivity proof and explicit packaged growth-artifact path needed for a truthful `pass_with_review_gate` packaged classification, rc43 adds one demo handoff-kit / presenter-package layer so the shipped handoff also carries presenter-facing quickstart, audience, sanity, and post-demo review aids without weakening `pass_with_review_gate` or the final `awaiting_review` state, rc44 adds one audience-mode / short-form optimization layer so the shipped handoff also carries a five-minute version, a fuller walkthrough mode, must-show checkpoint priorities, and tighter audience-specific talk tracks without weakening either `pass_with_review_gate` or the final `awaiting_review` state, rc45 adds one bounded real-work benchmark baseline layer so the shipped handoff also carries a successor package readiness review bundle refresh benchmark lane, its on-disk directive, output contract, success rubric, operator-value summary, and selection rationale without claiming that workflow is already executed, rc46 adds one bounded real-work benchmark execution layer so the shipped handoff also carries the first local-first readiness bundle, produced-output inventory, missing-output summary, and rubric classification for that benchmark without widening authority, and rc47 adds one bounded real-work benchmark closure / repeatability layer so the shipped handoff also carries repeat-run evidence, closure state, promotion-readiness state, and a narrowed `successor_readiness_bundle` explanation without widening authority. Open `/settings` only when you need detailed provider, trusted-source governance, runtime, or auto-continue tuning.

Rc48 also adds one bounded benchmark closure-decision / promotion-packet layer so the shipped handoff carries an explicit promote/hold/defer/blocked operator packet, a review-gate packet, a final blocker summary, and next-action guidance without widening authority.

Rc49 also adds one bounded review-action / promotion-outcome layer so the shipped handoff carries an explicit operator review packet, a review checklist, a benchmark review decision template, and an awaiting-confirmation promotion outcome without fabricating human confirmation or widening authority.

Rc50 adds the bounded review-confirmation / promotion-outcome capture layer, and the current repo-root persisted truth now records explicit operator confirmation with `promotion_confirmed_with_review_gate` and `no_material_confirmation_gap` while preserving the explicit review gate as advisory-only.

Or on Windows:

```text
launch\02_run_browser_operator.bat
```

That helper loads `image/novali-v7-standalone.tar` if needed, starts the standalone container, and points the operator to:

```text
http://127.0.0.1:8787/
```

For rc51+, when the optional SvelteKit shell is built in `operator_shell/web_ui/build`, the landing route is also:

```text
http://127.0.0.1:8787/shell
```

If the shell build is not present, `/shell` falls back to the legacy operator pages so core launch and observability remain usable.

It now mounts the unpacked handoff root into `/workspace/novali` read-only, then overlays the operator-owned writable paths for `operator_state/`, `runtime_data/`, and `novali-active_workspace/` so packaged browser behavior stays aligned with the shipped rc51 files.

## Packager Build / Export Path

Use this only when preparing the standalone handoff package.

From the active `novali-v7` baseline directory:

```powershell
docker build -t novali-v7-standalone:local -f Dockerfile .
```

Or use:

```powershell
.\standalone_docker\build_standalone_image.ps1
```

Then export the prebuilt archive:

```powershell
.\standalone_docker\export_standalone_image_archive.ps1
```

To assemble a zip-ready standalone handoff directory first, use:

```powershell
.\standalone_docker\assemble_handoff_package.ps1 --output-root .\dist --zip
```

Then work from the unpacked handoff package root and follow `README_FIRST.md`.

## Direct Localhost Launch Paths

For host-local development use:

```powershell
python -m novali_v5.web_operator
```

Equivalent convenience form:

```powershell
python -m novali_v5
```

Or use:

```powershell
.\standalone_docker\launch_web_operator.ps1
```

For the standalone container-oriented path, use:

```powershell
.\standalone_docker\run_web_operator_container.ps1
```

Then open:

```text
http://127.0.0.1:8787/
```

If you want the SvelteKit shell, build it before launch:

```powershell
npm --prefix operator_shell/web_ui install
npm --prefix operator_shell/web_ui run build
```

Then use `/shell`.

Inside the browser UI:

1. Select the directive file.
2. In `Trusted Sources`, set the provider base URL and validate the external provider with either a session-only credential paste or a local credential file.
3. Set runtime constraints.
4. Select backend `local_docker`.
5. Set Docker image to `novali-v7-standalone:local`.
6. Save / Apply runtime constraints.
7. Launch through the existing bootstrap flow.

## Suggested handoff layout

Keep operator-owned and canonical state separate:

- `directive_inputs/`
- `trusted_sources/`
- `operator_state/`
- `runtime_data/state/`
- `runtime_data/logs/`
- `runtime_data/acceptance_evidence/`

Directive files and trusted-source credentials remain outside canonical governance authority.

For packaged/container validation, you may also start the container from a shell session that already has:

- `OPENAI_API_KEY`
- `NOVALI_TRUSTED_SOURCE_API_BASE_URL`

`standalone_docker/run_web_operator_container.ps1` passes those env vars through to the container without echoing the raw credential.

## Secrets

Do not put raw secrets in directives.

Use:

- environment variables, or
- `trusted_source_secrets.local.json`

See:

- [STANDALONE_OPERATOR_GUIDE.md](./STANDALONE_OPERATOR_GUIDE.md)
- [OPERATOR_SHELL.md](./OPERATOR_SHELL.md)
- [LOCALHOST_WEB_OPERATOR_UI.md](./LOCALHOST_WEB_OPERATOR_UI.md)
- [RUNTIME_ENVELOPE.md](./RUNTIME_ENVELOPE.md)
- [HANDOFF_PACKAGE_README.md](./HANDOFF_PACKAGE_README.md)
- [DIRECTIVE_AUTHORING_GUIDE.md](./DIRECTIVE_AUTHORING_GUIDE.md)
- `standalone_docker/standalone.env.template`

## Honest limitations in this pass

- `local_guarded` remains the default backend.
- `local_docker` remains experimental and opt-in inside the same operator flow.
- Unsupported controls remain unsupported.
- Kubernetes is deferred and unimplemented.
- There is no silent fallback from Docker mode to unrestricted local execution.


