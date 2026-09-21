# Public Release Checklist

Use this checklist before committing or publishing a NOVALI public handoff.

## Package

- [ ] Build a new versioned package rather than overwrite the previous public candidate.
- [ ] Confirm the package is assembled from the intended source revision.
- [ ] Confirm the package has no authored, acceptance, or test directive files.
- [ ] Confirm `directive_inputs/`, `operator_state/`, `novali-active_workspace/`, and runtime folders contain only their public README placeholders.
- [ ] Confirm no active-workspace evidence, provider output, runtime ledgers, telemetry, or `.env` files are present.
- [ ] Confirm any image archive matches the packaged source; otherwise omit it and document the local-build path.

## Documentation and validation

- [ ] Update the root README, quick reference, package contents, and AI operator guide to the new package name.
- [ ] Run `./scripts/public_handoff_hygiene.ps1`.
- [ ] Compile the shipped directive-scaffold helper.
- [ ] Start the wizard and verify `/shell` opens against the new package.
- [ ] Review the final file list for absolute local paths, credentials, and stale release references.
