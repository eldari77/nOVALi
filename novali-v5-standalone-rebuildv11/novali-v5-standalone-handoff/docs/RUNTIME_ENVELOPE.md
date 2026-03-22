# NOVALI Runtime Envelope

## Purpose

`OperatorRuntimeEnvelopeSpec` is the operator-owned execution-envelope layer that sits:

- above low-level runtime-guard detail
- below governed NOVALI runtime execution
- outside agent-owned self-structure

It does not replace directive-first bootstrap.

Canonical authority still flows through:

`operator shell -> launcher -> frozen session -> bootstrap -> governed execution`

The envelope is frozen before launch and carried inside the effective operator session for that run.

## Current Backends

Implemented now:

- `local_guarded`
  - current host-process launcher + runtime-guard path
  - remains the default
- `local_docker`
  - Docker-first experimental scaffolding
  - opt-in only
  - no privileged mode
  - no Docker socket exposure to the agent
  - no silent fallback to unrestricted local execution if selected

Reserved but not implemented:

- `k8s_job`
- `k8s_pod`

Kubernetes remains deferred to a later orchestration tier.

## What The Envelope Freezes

The frozen envelope records:

- backend kind
- launch mode metadata
- memory-limit intent
- CPU quota intent
- session-timeout intent
- writable-mount policy
- working-directory boundary
- subprocess-policy source
- network-policy intent
- backend settings such as Docker image and conservative security defaults
- per-field enforcement classification

## Docker Translation Scope

Current `local_docker` translation is conservative.

Translated now:

- memory ceiling -> Docker memory limit
- CPU quota intent -> Docker `--cpus` when explicitly requested
- read-only root filesystem -> Docker `--read-only`
- writable-path policy -> explicit bind mounts only for approved write roots
- non-root execution -> numeric non-root user
- dropped capabilities -> `--cap-drop=ALL`
- no-new-privileges -> Docker security opt
- deny-all network intent -> `--network none`
- session timeout -> launcher watchdog outside the container
- subprocess / working-directory / write-boundary policy -> runtime guard remains active inside the container through a derived frozen runtime session

Refused now instead of faked:

- selected Docker backend when Docker is unavailable
- enabled `network_api` trusted sources under `local_docker`
- required backend translations that cannot be satisfied honestly

Unsupported or deferred:

- Kubernetes execution
- host/network allowlist policy beyond Docker `--network none`
- request-rate ceilings
- broader CPU utilization guarantees beyond Docker quota intent

## Live Docker Validation Status

`local_docker` has now been exercised on a Docker-capable workstation for the bounded control-plane slice.

Validated outcomes in this pass:

- Docker preflight succeeded on a live host
- bootstrap happy path completed under `local_docker`
- incomplete directive produced a governed clarification/refusal outcome under `local_docker`
- restart from persisted state completed under `local_docker`
- enabled `network_api` trusted sources were refused before launch under `local_docker`
- Docker CLI misconfiguration was refused before launch

One concrete live bug was fixed from this validation:

- container paths are now forced to POSIX form when Docker plans are built on Windows hosts

Still important:

- this does not broaden enforcement claims beyond the existing `hard_enforced` / `watchdog_enforced` / `unsupported_on_this_platform` classifications
- current live validation is for the canonical bootstrap/control-plane path first
- broader governed runtime dependency locking for a final standalone image remains a later follow-up

## Standalone Docker Product Prep

The repository now includes the first standalone single-container packaging assets:

- `Dockerfile`
- `.dockerignore`
- `STANDALONE_DOCKER_QUICKSTART.md`
- `standalone_docker/build_standalone_image.ps1`
- `standalone_docker/launch_web_operator.ps1`
- `standalone_docker/run_web_operator_container.ps1`
- `standalone_docker/standalone.env.template`

Preferred standalone/browser operator launch is now:

`python -m novali_v5.web_operator`

The transitional desktop surface remains available at:

`python -m novali_v5.operator_shell`

The Docker image is an execution envelope for that same authority path, not a replacement for it.

## Secrets Model

Secrets remain separate from directive authority.

Still true in Docker mode:

- directive files do not hold raw secrets
- trusted-source bindings hold metadata and references only
- raw secrets resolve from environment variables or the local operator secret store

Current Docker slice is conservative:

- enabled network API sources are refused for `local_docker`
- no raw secret values are written into the envelope spec
- no secret values are written into summary renderers

## Authority Boundary

The governed agent may:

- read effective envelope summary for observability

The governed agent may not:

- rewrite the operator runtime envelope spec
- rewrite the frozen effective session
- elevate its backend
- relax container/runtime controls through normal package APIs

Operator-owned runtime controls remain outside agent-owned self-structure and are guarded before governed execution starts.

## What Remains Unchanged

This envelope layer does not change:

- `nined_core.py`
- routing logic
- thresholds
- live policy
- benchmark semantics
- directive / bucket / branch / governance / self-structure authority meaning

It is a runtime-hardening layer, not a behavior-retuning layer.
