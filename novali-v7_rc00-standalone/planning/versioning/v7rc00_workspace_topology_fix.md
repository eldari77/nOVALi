# v7rc00 Workspace Topology Fix

This note records the physical workspace correction for `v7rc00`.

Active topology:

- active physical source root: `novali-v7`
- active line: `novali-v7`
- active milestone: `v7rc00`

Frozen reference:

- frozen physical source root: sibling `../novali-v6`
- frozen line: `novali-v6`
- frozen milestone: `rc88.1`
- frozen final package reference: `dist/novali-v6_rc88_1-standalone.zip`

Superseded package note:

- the first `v7rc00` package assembled under `novali-v6/dist/novali-v7_rc00*` is superseded due to wrong physical topology
- the topology-correct canonical package is built from `novali-v7/dist/novali-v7_rc00-standalone.zip`
- future v7 development must start from `novali-v7`

Boundary rules remain unchanged:

- v7rc00 remains a clean baseline, not behavior expansion
- Space Engineers remains inactive and `sandbox_candidate:not_active`
- the first SE-related v7 milestone must be planning-only unless separately approved
- LogicMonitor remains evidence/tooling only
- alerts, telemetry, replay, review, rollback, read-only observations, and identity lanes remain evidence/gating only
