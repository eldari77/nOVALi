# NOVALI Manual Acceptance Samples

These files exist only to support local manual operator validation.

They are:

- non-authoritative
- not auto-loaded by NOVALI
- not a replacement for canonical persisted governance artifacts
- safe to inspect and copy for manual testing

Use them as follows:

- copy a sample into an operator-chosen working location before editing
- review it in the GUI before launch
- do not treat sample files as production authority by default

Included assets:

- `valid_manual_acceptance_directive.json`
  - a valid formal directive wrapper suitable for manual bootstrap testing
- `incomplete_manual_acceptance_directive.json`
  - intentionally incomplete to trigger clarification/refusal behavior
- `trusted_source_bindings_env_example.json`
  - trusted-source metadata example using env-var/local-secret references only
- `operator_runtime_constraints_example.json`
  - runtime-constraint example showing supported and unsupported control classes clearly
- `trusted_source_reference_inventory_demo_directive.json`
  - bounded trusted-source demo candidate directive that starts local-first, defines the exact frozen-v5 knowledge gap, constrains the later trusted-source request shape, and names the future reusable skill-pack target
- `successor_package_readiness_benchmark_directive.json`
  - bounded real-work benchmark directive that frames a successor package-readiness review bundle refresh as the next post-demo operator-value lane using current repo, package, workspace, and acceptance-evidence artifacts
- `successor_package_readiness_review_decision_template.json`
  - bounded operator review template for recording an explicit promote / hold / defer / blocked outcome for the successor package-readiness benchmark without implying automatic promotion
