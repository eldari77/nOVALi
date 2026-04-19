# NOVALI Standalone Package

Read this file first.

This repository now maintains two truths at once:

- frozen historical reference: `novali-v6` at `rc88.1`
- active clean baseline: `novali-v7` at `v7rc00`
- active physical source root: `novali-v7`
- frozen v6 physical source root: sibling `../novali-v6`

Active package identity:

- package version: `novali-v7_rc00-standalone`
- canonical zip: `dist/novali-v7_rc00-standalone.zip`
- canonical unpacked package: `dist/novali-v7_rc00-standalone`
- canonical browser operator entrypoint: `python -m novali_v5.web_operator`
- delivery model: zip-delivered single-agent Docker/browser handoff
- canonical authority path: `operator shell -> launcher -> frozen session -> bootstrap -> governed execution`
- canonical image archive: `image/novali-v7-standalone.tar`
- canonical image tag: `novali-v7-standalone:local`
- canonical topology: build and package from `novali-v7`, not from `novali-v6`

Frozen v6 reference:

- final milestone: `rc88.1`
- final package: `dist/novali-v6_rc88_1-standalone.zip`
- final unpacked package: `dist/novali-v6_rc88_1-standalone`
- status: `frozen_reference`

Topology correction:

- the first `v7rc00` package assembled under `novali-v6/dist/novali-v7_rc00*` is superseded due to wrong physical workspace topology
- the topology-correct canonical package is the one rebuilt from `novali-v7/dist/novali-v7_rc00-standalone.zip`
- future v7 development must start from `novali-v7`

v7rc00 truth:

- v7rc00 is a clean baseline setup, not a feature expansion
- v7rc00 does not begin Space Engineers work
- v7rc00 does not add new autonomy
- v7rc00 does not add network connectors
- v7rc00 does not add mutation paths
- v7rc00 preserves telemetry/alerts as evidence only
- v7rc00 preserves LogicMonitor as tooling/evidence only
- v7rc00 preserves read-only adapter admission gates
- v7rc00 preserves review/replay/rollback evidence posture
- v7rc00 preserves controller-isolation inactive/mock-only lanes
- v7rc00 preserves the non-activating SE transition memo
- v7rc00 preserves alerts, telemetry, replay, review, rollback, read-only observations, and identity lanes as evidence/gating only

First run:

1. Unzip `dist/novali-v7_rc00-standalone.zip`.
2. Run `launch\\02_run_browser_operator.bat` or `launch\\02_run_browser_operator.ps1`.
3. If the image is not loaded yet, the helper loads `image\\novali-v7-standalone.tar`.
4. Open `http://127.0.0.1:8787/`.
5. `/` redirects to `/shell` and `/workspace` redirects to `/shell/workspace`.
6. Use the packaged directive sample or scaffold for initialization.
7. Keep the default governance posture unchanged unless the operator explicitly decides otherwise.

Guardrails:

- Controller remains the sole coordination and adoption authority
- review/intervention gates remain binding
- telemetry, alerts, replay packets, review tickets, rollback analyses, and lane artifacts remain evidence/gating surfaces only
- no real external-world mutation is introduced
- no LogicMonitor API integration is introduced
- no Space Engineers implementation is introduced
- no second authority path is introduced

Preserved observability source-of-truth:

- `observability/logicmonitor/rc83_2_portal_confirmation_snapshot.json`
- `artifacts/operator_proof/rc83_2/portal_confirmation_summary.json`

Operator-readable proofs:

- `artifacts/operator_proof/v6_closeout/`
- `artifacts/operator_proof/v7rc00/`
- `artifacts/operator_proof/rc88_1/`
- `artifacts/operator_proof/rc88/`
- `artifacts/operator_proof/rc87/`
- `artifacts/operator_proof/rc86/`
- `artifacts/operator_proof/rc85/`
