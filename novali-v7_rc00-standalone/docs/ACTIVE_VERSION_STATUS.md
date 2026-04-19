# ACTIVE_VERSION_STATUS

`novali-v6` is closed and frozen as the historical reference line at `rc88.1`.
`novali-v7` is the active clean baseline after `v7rc00` validation.
The active physical source root is `novali-v7`, and future v7 development must start from this sibling workspace rather than `novali-v6`.
Future v7 development must start from `novali-v7`.

Latest confirmed milestone:

- `v7rc00`
- active line: `novali-v7`
- active physical source root: `novali-v7`
- canonical handoff: `dist/novali-v7_rc00-standalone.zip`
- canonical unpacked handoff: `dist/novali-v7_rc00-standalone`
- canonical browser operator entrypoint: `python -m novali_v5.web_operator`
- topology note: the earlier `novali-v6/dist/novali-v7_rc00*` package is superseded because it was built from the wrong physical source root

Frozen v6 reference:

- final v6 milestone: `rc88.1`
- final v6 package: `dist/novali-v6_rc88_1-standalone.zip`
- final v6 unpacked package: `dist/novali-v6_rc88_1-standalone`
- frozen physical source root: sibling `../novali-v6`
- v6 status: `frozen_reference`
- further v6 work is not recommended unless a critical regression requires a narrow patch

v7rc00 posture:

- clean baseline reset from accepted v6 `rc88.1`
- behavior-equivalent to v6 `rc88.1` except for version identity, package identity, source-of-truth docs, and proof/package artifacts
- not a behavior-expansion milestone
- no Space Engineers work is active
- no new autonomy is added
- no new external connectors are added
- no new mutation path is added
- topology-correct canonical package is built from `novali-v7`, not from `novali-v6`

Preserved invariants:

- Controller remains the sole coordination and adoption authority
- backend blocked/resumable/completed truth remains authoritative
- review/intervention gates remain binding
- telemetry remains evidence only
- LogicMonitor remains tooling/evidence only
- alerts remain evidence only
- acknowledgement is not approval
- review is not approval
- read-only adapter remains non-mutating and read-only / mock-safe only
- replay, review, rollback, and lane artifacts remain evidence/gating surfaces only
- controller-isolation lanes remain inactive/mock-only
- no second authority path exists
- `/ -> /shell` and `/workspace -> /shell/workspace` remain unchanged
- no Space Engineers implementation is active

Preserved evidence:

- `observability/logicmonitor/rc83_2_portal_confirmation_snapshot.json`
- `artifacts/operator_proof/rc83_2/portal_confirmation_summary.json`
- `artifacts/operator_proof/rc85/review_rollback_integration_summary.json`
- `artifacts/operator_proof/rc86/dual_controller_isolation_summary.json`
- `artifacts/operator_proof/rc87/read_only_adapter_sandbox_summary.json`
- `artifacts/operator_proof/rc88/operator_alert_loop_summary.json`
- `artifacts/operator_proof/rc88_1/telemetry_shutdown_cleanup_summary.json`
- `artifacts/operator_proof/v6_closeout/v6_closeout_summary.json`
- `artifacts/operator_proof/v7rc00/v7rc00_baseline_summary.json`

Current bottleneck:

- first v7 planning decision after baseline setup

Next recommended milestone:

- Space Engineers read-only bridge planning only, if the operator explicitly approves it
- otherwise generic v7 hardening / maintenance

Space Engineers posture:

- `sandbox_candidate:not_active`
