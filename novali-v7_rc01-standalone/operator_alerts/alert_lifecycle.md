# rc88 Alert Lifecycle With rc88.1 Shutdown Evidence

Local state:

- candidates ledger: `data/operator_alerts/alert_candidates.jsonl`
- lifecycle ledger: `data/operator_alerts/alert_lifecycle.jsonl`
- proof artifacts: `artifacts/operator_proof/rc88/alerts/`
- lifecycle events: `artifacts/operator_proof/rc88/lifecycle_events/`

Operations:

- `raise_alert(...)`
- `acknowledge_alert(...)`
- `mark_alert_reviewed(...)`
- `close_alert_evidence_only(...)`
- `supersede_alert(...)`
- `summarize_alerts()`

Allowed transitions:

- `raised -> acknowledged`
- `raised -> blocked_waiting_operator`
- `raised -> superseded`
- `acknowledged -> reviewed`
- `acknowledged -> superseded`
- `reviewed -> evidence_only_closed`
- `blocked_waiting_operator -> acknowledged`
- `blocked_waiting_operator -> reviewed`

Forbidden transitions:

- any `-> approved_for_action`
- any `-> mutation_allowed`
- any `-> governance_approved`
- `reviewed -> execute`
- `evidence_only_closed -> mutation_allowed`

Local action endpoints:

- `POST /shell/api/operator-alerts/action`
- `POST /operator-alerts/action`

Supported local-only actions:

- `acknowledge_operator_alert`
- `review_operator_alert`
- `close_operator_alert_evidence_only`
- `supersede_operator_alert`

Boundaries:

- acknowledgement is not approval
- review is not approval
- closing evidence-only does not delete evidence
- supersession preserves history
- invalid transitions fail closed with bounded local evidence
- telemetry degradation acknowledgement/review remains non-approving and does not authorize mutation
