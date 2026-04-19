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
8. optional external trusted-source provider onboarding without persisting the raw secret
9. trusted-source budget/retry stop reasons surfacing explicitly when external escalation is not worth continuing
10. review-required states offering explicit approve / defer / reject / evidence-first controls with truthful post-decision session state

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
- the archive is bundled inside the handoff at `image\novali-v7-standalone.tar`
- image tag is `novali-v7-standalone:local`

3. Generate a directive file.

Run:

```powershell
.\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\directive_inputs\acceptance_directive.json `
  --directive-id directive_acceptance_bootstrap_v1 `
  --directive-text "Initialize NOVALI from the standalone handoff package." `
  --clarified-intent-summary "Bootstrap novali-v7 under the canonical standalone operator flow and preserve artifact-backed governance authority before execution."
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
- the landing page is one integrated startup surface
- the landing page distinguishes fresh start vs resumable session state before the launch form
- review-required states surface through the operator review workspace instead of appearing as ordinary resume-ready sessions
- the review workspace exposes explicit bounded actions such as approve continuation, defer/hold, reject/stop, and evidence-first return when they are admissible
- when a bounded child return is pending, the same review workspace shows the Controller-child adoption or defer/reject decision instead of inventing a second hidden review path
- when mission-integrated Librarian delegation is used, the same operator surfaces show why the child was delegated, what maintenance bundle returned, and whether the Controller adopted it into the active library-hygiene/readiness mission
- when a bounded Verifier child is used, the same operator surfaces show what bundle or mission output was checked, which contract/provenance/adoption-readiness checks were run, and whether the Controller treated the verification result as support for adoption, defer, rejection, or later revision
- when the fixed sequential Librarian-to-Verifier workflow is used, the same operator surfaces show both bounded steps in order, preserve the distinct outputs from each child, and make it clear that only the Controller decides whether the verified Librarian result becomes adopted mission truth
- when delegation is in scope, the same operator surfaces also show the explicit delegation plan, blocked alternatives, per-role admissibility, and the typed Librarian-to-Verifier handoff state rather than leaving those Controller choices implicit
- the default preset is `Long-run / low-touch`
- advanced controls are available on a separate `Settings` page
- the canonical launch path remains browser UI / operator surface -> launcher -> frozen session -> bootstrap -> governed execution

5. Configure the happy path.

In the browser UI Home startup surface:

- select the generated directive file
- keep the default `Long-run / low-touch` preset unless a tighter run is needed
- use the bootstrap preparation card to save the bootstrap runtime posture
- use the launch/resume card on the same Home surface to launch bootstrap

If you need to customize provider onboarding, trusted-source governance, or runtime constraints first, open `Settings`.

Expected:

- bootstrap completes
- canonical artifacts appear under `runtime_data/state`
- launch/evidence files appear under operator-owned paths and logs
- when you refresh or revisit Home afterward, the continuity summary shows the current directive/workspace, last preset, and the next recommended action instead of sending you back through first-time setup
- if review is required later, the operator review workspace groups pending decisions, explains why review is needed, shows the recommended next bounded action, and records explicit operator decision outcomes before deeper inspection
- if a Librarian child is used, verify that the Controller remains the only authority actor, that the child return is explicitly adopted, deferred, rejected, or revoked before it is treated as usable, and that only an adopted bundle is shown as improving the active mission
- if a Verifier child is used, verify that it only returns a bounded verification summary, that it cannot self-authorize adoption or governance changes, and that the Controller still makes the explicit adopt/defer/reject/revoke decision after reviewing the verification result
- if the sequential Librarian-to-Verifier workflow is used, verify that the Verifier is checking the Librarian return rather than acting as a second authority, that both child steps remain bounded and one-generation only, and that the final adopt/defer/reject/review decision still belongs entirely to the Controller
- if delegation planning is visible, verify that blocked or inadmissible child paths are shown explicitly, that the chosen path remains Controller-owned, and that the typed handoff contract only applies when a real Librarian bundle is being handed to the bounded Verifier

6. Confirm the bounded coding path is available.

In the browser UI after successful bootstrap:

- keep the same persisted State Root
- use the governed-execution preparation step on Home, or open `Settings` and switch execution profile to `bounded_active_workspace_coding`
- confirm an active workspace root appears under `novali-active_workspace/<workspace_id>/`
- use `resume_existing` plus `governed_execution`

Expected:

- the packaged browser flow clearly distinguishes `bootstrap_only` from `governed_execution`
- the bounded coding profile is visible as a separate operator choice
- the active workspace root is shown as bounded workspace state, not broad package write access
- the Home continuity strip now shows a resume-ready or active bounded session state rather than a first-time initialization state

7. Validate packaged trusted-source provider onboarding.

In the browser `Settings` page:

- go to `Trusted Sources`
- set the provider base URL
- paste a session-only credential or provide a local credential file path
- choose `Validate External Provider`

Expected:

- provider validation succeeds or fails with a truthful non-secret status
- `trusted_source_credential_status_latest.json` and `trusted_source_provider_status_latest.json` update without containing the raw secret
- handshake/session/request-contract artifacts are visible if validation succeeds
- the packaged runtime proves outbound provider reachability without changing governance authority

8. Trigger the refusal path.

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
