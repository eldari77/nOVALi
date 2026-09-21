# rc87 Read-Only External Adapter

rc87 adds a generic non-SE read-only adapter sandbox proof.
rc88 wraps those read-only outcomes in a local operator alert loop and formal admission criteria for future read-only adapters.

Boundaries:

- read-only adapter: observation only
- no real external-world mutation
- no outbound network access
- no real external API connector
- alerts are evidence signals, not authority
- acknowledgement is not approval
- no Space Engineers behavior is active
- observation replay packets are evidence, not authority
- review tickets are operator-visible gates, not executors
- rollback/recovery analysis preserves evidence and does not silently restore real runtime state
- identity lanes remain inactive/mock-only
- controller authority and review gates remain unchanged

Implementation:

- module: `operator_shell/external_adapter/read_only/`
- adapter class: `StaticFixtureReadOnlyAdapter`
- source type: local static JSON fixtures only
- default proof lane: `lane_director`
- proof runner: `operator_shell/scripts/rc87_read_only_adapter_sandbox_proof.py`
- alert-loop proof runner: `operator_shell/scripts/rc88_operator_alert_loop_proof.py`
- rc88 admission criteria doc: `external_adapter/read_only_admission_criteria.md`

The rc87 adapter may:

- load a local sandbox fixture
- validate snapshot schema
- validate observation integrity
- summarize the observation in a bounded redacted form
- write observation replay packets
- write review tickets when the observation is unsafe or malformed
- write rollback/recovery analysis that preserves bad snapshot evidence
- refuse mutation-bearing requests
- surface bad observation evidence into the local operator alert loop

The rc87 adapter may not:

- mutate the source fixture
- execute a command against an external system
- open a network connection
- command a server, game, service, or device
- activate a sovereign lane
- infer that observation implies permission to act
- approve action through acknowledgement or review
