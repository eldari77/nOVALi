# rc87 External Adapter Membrane

`novali-v6` now carries two bounded external-adapter slices:

- the rc84-rc85 mock/no-op action membrane
- the rc87 generic non-SE read-only observation sandbox

Shared boundaries:

- controller authority and review gates remain unchanged
- no second authority path is created
- replay packets are evidence, not authority
- review items are operator-gated evidence, not executors
- rollback analysis is evidence and recovery planning, not automatic restore
- LogicMonitor remains observability/evidence only
- no Space Engineers behavior is active

What exists now:

- a reusable adapter contract under `operator_shell/external_adapter/`
- a `MockExternalWorldAdapter` implementation with bounded `noop.*` verbs for rc84-rc85 proof paths
- rc85 review-hold and rollback/checkpoint linkage for mock adapter evidence
- a read-only adapter module under `operator_shell/external_adapter/read_only/`
- a `StaticFixtureReadOnlyAdapter` that only ingests local static fixtures and only writes NOVALI proof/evidence artifacts
- rc87 observation replay packets under `artifacts/operator_proof/rc87/observation_replay_packets/`
- rc87 review tickets under `artifacts/operator_proof/rc87/review_tickets/`
- rc87 rollback analyses under `artifacts/operator_proof/rc87/rollback_analyses/`
- replay ledgers at `data/external_adapter_replay.jsonl` and `data/read_only_adapter_observation_replay.jsonl`
- proof runners:
  - `operator_shell/scripts/rc84_external_adapter_mock_proof.py`
  - `operator_shell/scripts/rc85_review_rollback_integration_proof.py`
  - `operator_shell/scripts/rc87_read_only_adapter_sandbox_proof.py`

Supporting docs:

- `external_adapter/replay_schema.md`
- `external_adapter/mock_adapter.md`
- `external_adapter/review_hold_integration.md`
- `external_adapter/rollback_integration.md`
- `external_adapter/read_only_adapter.md`
- `external_adapter/read_only_fixture_schema.md`
- `external_adapter/observation_replay_schema.md`
- `external_adapter/read_only_review_integration.md`
- `external_adapter/read_only_rollback_recovery.md`
- `observability/external_adapter_telemetry.md`
- `observability/read_only_adapter_telemetry.md`

What does not exist yet:

- real external adapters
- outbound network connectors
- live external-world mutation
- Space Engineers bridges or active game/server behavior
- automatic rollback restore
- approval for any real external action
