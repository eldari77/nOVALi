# NOVALI v5 Manual Acceptance Result Template

- Operator:
- Date:
- Desktop / OS:
- Preferred browser launch: `python -m novali_v5.web_operator`
- Desktop launch used for this acceptance pass: `python -m novali_v5.operator_shell`
- Directive used:
- State root used:
- Operator root used:

## Summary

- Overall result:
- Main observations:
- Any blocker:

## Successful Path Checks

- Directive validation:
- Fresh bootstrap-only launch:
- Dashboard posture visibility:
- Canonical artifact presence:
- Acceptance snapshot export:

## Refusal / Negative Path Checks

- Missing resume session refusal:
- Tampered resume session refusal:
- Invalid or incomplete directive handling:
- Invalid trusted-source binding handling:
- Invalid/unsaved constraint handling:

## Constraint Visibility

- Hard-enforced controls reviewed:
- Watchdog-enforced controls reviewed:
- Unsupported controls remained visibly unsupported:

## Trusted Sources

- Secret-source indication reviewed:
- No raw secrets committed into authority artifacts:

## Key Evidence Files

- `operator_launch_events.jsonl`:
- `effective_operator_session_latest.json`:
- exported acceptance snapshot:
- canonical artifact paths checked:

## Follow-Up Items

- UI clarity issues:
- Documentation issues:
- Packaging/launch issues:
- Deferred future-runtime notes:
