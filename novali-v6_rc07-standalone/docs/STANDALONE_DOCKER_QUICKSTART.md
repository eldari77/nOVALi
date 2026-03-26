# NOVALI Standalone Docker Quickstart

This is the current single-agent standalone Docker handoff path for `novali-v6`.

For packaged operator use, start with `README_FIRST.md`. This quickstart is a supporting reference, not the primary first-run guide.

Canonical authority path remains unchanged:

`operator shell -> launcher -> frozen session -> bootstrap -> governed execution`

The Docker container is an execution envelope, not a second authority path. The new preferred standalone surface is browser-based localhost initialization.

## Canonical image tag

Use this local image tag for the current standalone handoff slice:

`novali-v6-standalone:local`

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

The canonical rc07 handoff is fully self-contained and includes the bundled Docker image archive at `image/novali-v6-standalone.tar`.

Or on Windows:

```text
launch\02_run_browser_operator.bat
```

That helper loads `image/novali-v6-standalone.tar` if needed, starts the standalone container, and points the operator to:

```text
http://127.0.0.1:8787/
```

## Packager Build / Export Path

Use this only when preparing the standalone handoff package.

From the `novali-v6` directory:

```powershell
docker build -t novali-v6-standalone:local -f Dockerfile .
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

Inside the browser UI:

1. Select the directive file.
2. In `Trusted Sources`, set the provider base URL and validate the external provider with either a session-only credential paste or a local credential file.
3. Set runtime constraints.
4. Select backend `local_docker`.
5. Set Docker image to `novali-v6-standalone:local`.
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
