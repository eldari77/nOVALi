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
4. choose a workspace id
5. resume with `resume_existing` + `governed_execution`

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

## Where To Look After Launch

- canonical artifacts:
  - `runtime_data/state/`
- logs:
  - `runtime_data/logs/`
- acceptance evidence:
  - `runtime_data/acceptance_evidence/`
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
