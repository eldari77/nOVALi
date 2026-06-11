# Operator Quick Reference

## Start

- Run `launch/00_first_run_wizard.ps1` from the public repository root.
- Open `http://127.0.0.1:8787/shell`.
- Confirm the shell reports a safe or paused state before starting autonomy.

## Directive

- Use a generic sample from `samples/directives/` or create a new directive in the shell.
- Do not place private mission directives or secrets in the public repo.
- Directives should describe outcomes, constraints, deliverables, and success criteria.

## Governed Work

- Use governed continuation for bounded, auditable progress.
- Review blockers in the Attention Queue before approving high-impact work.
- Use pause or emergency stop when the state is unclear.

## Librarian

- Librarian packs are reusable evidence and skill references.
- Packs do not grant execution authority or bypass governance.
- Store runtime-developed packs on the configured spill volume.

