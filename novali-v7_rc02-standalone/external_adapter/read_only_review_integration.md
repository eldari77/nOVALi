# rc87 Read-Only Review Integration

rc87 routes unsafe or malformed read-only observations into the existing operator review surfaces.

Review triggers:

- `read_only_schema_missing_field`
- `read_only_schema_invalid`
- `read_only_conflicting_observation`
- `read_only_stale_snapshot`
- `read_only_wrong_lane_attribution`
- `read_only_mutation_requested`
- `read_only_forbidden_domain_term`
- `read_only_secret_detected`
- `read_only_replay_missing`
- `read_only_rollback_ambiguity`
- `read_only_source_unavailable`
- `read_only_integrity_failed`

Severity:

- `warning`: stale but bounded, optional metadata gap
- `high`: missing required fields, conflicting observations, wrong-lane attribution, replay missing
- `critical`: mutation request, forbidden domain term, secret leakage, authority claim, external command request

rc88 extension:

- the same bad-observation outcomes can now raise local operator alerts with evidence bundles and lifecycle events
- acknowledgement and review stay local evidence-only notes
- no alert or review state can approve mutation

Boundaries:

- review tickets are operator-visible evidence only
- pending review does not auto-resolve
- no review item can approve mutation in rc87
- controller authority and review gates remain unchanged

Artifact locations:

- `artifacts/operator_proof/rc87/review_tickets/`
- `artifacts/operator_proof/rc87/review_ticket_summary.json`
- `artifacts/operator_proof/rc88/alerts/`
- `artifacts/operator_proof/rc88/evidence_bundles/`
