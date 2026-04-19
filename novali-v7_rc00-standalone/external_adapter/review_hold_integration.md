# rc85 Review-Hold Integration

rc85 turns external-adapter review-required outcomes into first-class operator-visible evidence without creating a second governance engine.

Key points:

- review items are written as redacted JSON under `artifacts/operator_proof/rc85/review_items/`
- the review ledger summary lives at `artifacts/operator_proof/rc85/review_item_ledger_summary.json`
- review items link to replay packets, rollback analyses, and checkpoint refs when present
- review items surface through the existing operator review/intervention snapshot as advisory evidence
- no review item can approve a real external action in rc85

Review statuses:

- `pending_review`
- `acknowledged`
- `resolved_mock_only`
- `blocked`
- `escalated`
- `superseded`
- `evidence_missing`

Escalation triggers include:

- unknown action type
- forbidden action type
- failed preconditions
- repeated uncertain outcomes
- missing replay packet
- rollback ambiguity
- unsafe payload
- live-mutation request
- kill switch triggered
- redaction failure

Boundaries:

- review items are evidence only
- controller authority and review gates remain unchanged
- mock review resolution does not authorize live external mutation
