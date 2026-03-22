# NOVALI Standalone Package

Read this file first.

This handoff package is the current release-candidate shape for one `novali-v5` agent:

- package version: `novali-v5-standalone-rc9`
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
11. If a cycle ends planning-only with `next_recommended_cycle = materialize_workspace_local_implementation`, either run `governed_execution` again in `single_cycle` mode or save `multi_cycle` mode with a conservative cap for the next invocation.
12. Use the browser observability pages to inspect the latest run without hunting through files manually:
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

## Runtime Constraints

Runtime constraints remain operator-owned and are frozen before launch.

Current enforcement classes remain honest:

- `hard_enforced`
- `watchdog_enforced`
- `unsupported_on_this_platform`

Do not treat unsupported controls as guarantees.

For the packaged standalone single-container path, keep backend `local_guarded` in the browser UI. The standalone container is already the Docker envelope for that operator session.

The bounded coding profile is intentionally narrow. It authorizes writes only inside the frozen active workspace plus approved generated/log roots. It does not authorize broad mutation of the packaged NOVALI surfaces.

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
