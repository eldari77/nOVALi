# Public Release Checklist

Run this checklist before committing or publishing a NOVALI public handoff.

## Required Checks

- [ ] Build or refresh the public handoff package.
- [ ] Confirm the package contains no private live directive.
- [ ] Confirm `directive_inputs/` contains only generic samples/placeholders.
- [ ] Confirm `novali-active_workspace/` contains only a README placeholder.
- [ ] Confirm `operator_state/` contains only a README placeholder or safe seed metadata.
- [ ] Confirm `runtime_data/` contains only README placeholders and safe acceptance evidence.
- [ ] Confirm `node_modules/`, caches, and test outputs are not tracked.
- [ ] Confirm screenshots are sanitized and do not show private runtime state.
- [ ] Run `.\scripts\public_handoff_hygiene.ps1`.
- [ ] Run Python compile checks for shipped helper scripts.
- [ ] Launch the wizard and verify `/shell` opens.

## Forbidden Public Content

- private mission directive text from local runs;
- raw provider output;
- `.env` files;
- API keys or bearer strings;
- active workspace artifacts;
- pending LLM directives;
- runtime JSONL ledgers;
- absolute local host paths except documentation examples that are clearly generic.
