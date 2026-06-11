# NOVALI v7 Bootstrap Flow

## Entry Points

- Preferred standalone/browser operator entrypoint: `python -m novali_v5.web_operator`
- Equivalent convenience form: `python -m novali_v5`
- Transitional desktop operator entrypoint: `python -m novali_v5.operator_shell`
- Non-canonical developer/test bootstrap entrypoint: `python bootstrap.py --directive-file directives/novali_v5_bootstrap_directive_v1.json`
- Non-canonical developer/test runtime entrypoint with bootstrap handoff: `python main.py --directive-file directives/novali_v5_bootstrap_directive_v1.json --bootstrap-only`

For launch classification and allowed bypasses, see [LAUNCH_MATRIX.md](./LAUNCH_MATRIX.md).

## Flow

1. Load a formal `NOVALIDirectiveBootstrapFile` JSON document.
2. Validate the file wrapper and required `bootstrap_context`.
3. Compile `directive_spec` into a normalized `DirectiveSpec`.
4. Run clarification before activation when required fields are missing or ambiguous.
5. Refuse activation if the compiled `DirectiveSpec` violates posture invariants or governance requirements.
6. Materialize or refresh canonical governance artifacts:
   - `directive_state_latest.json`
   - `bucket_state_latest.json`
   - `branch_registry_latest.json`
   - `governance_memory_authority_latest.json`
   - `self_structure_state_latest.json`
7. Append activation provenance to `directive_history.jsonl` and `self_structure_ledger.jsonl`.
8. Re-read the canonical artifacts and refuse startup if they are inconsistent.
9. Hand off to the existing governed execution gate with artifact-backed authority already established.

## Authority Model

- Canonical current-state authority remains persisted artifacts, not runtime loop defaults.
- The startup order is:
  - `governance_memory_authority_latest.json`
  - `self_structure_state_latest.json`
  - `branch_registry_latest.json`
  - `directive_state_latest.json`
  - `bucket_state_latest.json`
- The bootstrap layer is authoritative only for initialization and consistency checks.
- The existing execution gate remains authoritative for runtime permission decisions after bootstrap.

## Clarification

- Missing or ambiguous required `DirectiveSpec` fields do not auto-fill silently.
- Bootstrap raises a clarification-required result before activation.
- Clarification responses can be supplied through a separate JSON file or an interactive caller using the library API.

## Intentionally Unchanged

- `theory/nined_core.py`
- routing logic
- threshold constants
- live policy behavior
- frozen benchmark semantics
- reopen standards and promotion gating semantics

## Test Coverage

- valid fresh bootstrap
- restart from persisted state
- invalid directive rejection
- clarification-required path
- refusal when canonical governance artifacts are inconsistent
