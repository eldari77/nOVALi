# rc85 Rollback Integration

rc85 keeps rollback analysis evidence-only and links it to replay plus checkpoint context.

Key points:

- rollback analyses are written under `artifacts/operator_proof/rc85/rollback_analysis/`
- the summary file is `artifacts/operator_proof/rc85/rollback_analysis_summary.json`
- analyses link `replay_packet_id`, `action_id`, `checkpoint_ref`, and `prior_stable_state_ref`
- `restore_allowed=false` by default in rc85
- `restore_performed=false` for the rc85 mock proof
- missing or ambiguous rollback evidence creates review-required items

Required linkage:

- replay packet id
- checkpoint ref or explicit checkpoint-unavailable state
- prior stable state reference
- ambiguity level and ambiguity reasons
- evidence paths that preserve diagnostic context

Boundaries:

- rollback analysis is evidence and planning only
- rollback does not erase replay or failure evidence
- rollback does not silently restore real runtime or external state
