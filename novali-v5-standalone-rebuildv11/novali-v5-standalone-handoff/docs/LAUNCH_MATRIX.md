# NOVALI v5 Launch Matrix

## Preferred Standalone Launch

Preferred standalone/browser-facing operation should start here:

- packaged handoff helper: `launch\02_run_browser_operator.bat`
- packaged handoff PowerShell helper: `launch\02_run_browser_operator.ps1`
- `python -m novali_v5.web_operator`
- equivalent convenience form: `python -m novali_v5`
- `.\standalone_docker\launch_web_operator.ps1`
- `.\standalone_docker\run_web_operator_container.ps1`

Transitional desktop GUI paths still exist:

- `python -m novali_v5.operator_shell`
- equivalent convenience form: `python -m novali_v5`
- legacy compatibility wrapper: `python operator_gui.py`

Canonical chain:

1. operator shell
2. launcher / supervisor
3. frozen effective operator session
4. `bootstrap.py`
5. governed execution in `main.py`

This is the only documented routine authority path. The browser UI and the transitional desktop GUI both feed the same chain.

For the packaged release-candidate handoff, `README_FIRST.md` is the primary onboarding story.

For packagers preparing that handoff:

- build the image with `docker build -t novali-v5-standalone:local -f Dockerfile .`
- or use `.\standalone_docker\build_standalone_image.ps1`
- export the packaged image archive with `.\standalone_docker\export_standalone_image_archive.ps1`
- then launch the localhost browser UI path
- choose `local_docker` in the browser UI when Docker-backed execution is desired

For manual desktop validation of that path, use:

- [STANDALONE_HANDOFF_ACCEPTANCE.md](./STANDALONE_HANDOFF_ACCEPTANCE.md)
- [MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md](./MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md)

For directive creation/operator onboarding in the standalone package, use:

- [DIRECTIVE_AUTHORING_GUIDE.md](./DIRECTIVE_AUTHORING_GUIDE.md)
- [LOCALHOST_WEB_OPERATOR_UI.md](./LOCALHOST_WEB_OPERATOR_UI.md)
- `standalone_docker/generate_directive_scaffold.ps1`

## Non-Canonical Developer / Test Paths

These entrypoints still exist for development, CI, and focused testing:

- `python bootstrap.py --directive-file ...`
- `python main.py --directive-file ... --bootstrap-only`
- `python main.py --proposal-analytics`
- direct library calls into `bootstrap.bootstrap_runtime(...)`
- focused launcher/runtime-guard probes under `tests/`

These are allowed because NOVALI still needs direct harnesses for:

- automated tests
- CI validation
- local debugging
- deterministic bootstrap inspection

They are not the canonical operator workflow.

## Bypass Rule

Direct `main.py` / `bootstrap.py` launches are classified as non-canonical developer/test paths.

Canonical operator-mode launches require:

- a frozen operator session
- a frozen operator runtime envelope
- launcher-provided runtime lock
- operator-owned policy root

If that frozen operator session is absent or invalid for a canonical operator-mode launch, startup refuses.

If the selected runtime envelope backend is unavailable or cannot satisfy required translations honestly, startup also refuses instead of silently downgrading.

## Guidance

- Use the localhost browser UI for the standalone product direction.
- Keep the desktop GUI available for transitional local/manual workflows.
- Use direct CLI/library entrypoints only for tests, CI, or deliberate developer debugging.
- Do not treat direct CLI use as the default operator surface.

## Closeout Note

The local operator-shell milestone has completed manual acceptance on the canonical path:

- bootstrap happy path validated
- governed refusal / clarification-required path validated
- resume-from-persisted-state path validated

This launch matrix remains unchanged by the runtime-envelope addition. The canonical operator path is still the same:

- localhost browser UI is now the preferred standalone surface over the same operator authority chain
- desktop GUI remains a transitional local surface
- `local_guarded` remains the default backend inside that path
- `local_docker` is an opt-in experimental backend under the same operator flow
- standalone single-container packaging assets now exist for the Docker-first track
- Kubernetes remains deferred and unimplemented
