# rc87 Read-Only Rollback / Recovery

rc87 adds rollback/recovery evidence for bad snapshot ingestion.

Purpose:

- preserve prior good observation state
- preserve bad snapshot evidence
- avoid silent overwrite or deletion
- keep recovery planning operator-readable

Rollback analysis fields:

- `schema_version=rc87.v1`
- `rollback_analysis_id`
- `replay_packet_id`
- `snapshot_id`
- `prior_good_snapshot_ref`
- `checkpoint_ref`
- `recovery_possible`
- `recovery_action`
- `recovery_performed`
- `restore_allowed`
- `restore_performed`
- `evidence_preserved`
- `bad_snapshot_evidence_ref`
- `operator_action_required`
- `ambiguity_detected`
- `ambiguity_reasons`
- `created_at`
- `package_version=rc87`
- `branch=novali-v6`

Rules:

- `restore_allowed=false` by default
- `restore_performed=false` by default
- recovery may preserve a prior-good pointer for proof state only
- source fixtures are never mutated
- real runtime state is never restored
- ambiguity creates review evidence
