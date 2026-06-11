# NOVALI Directive Authoring Guide

This guide is for operators preparing a formal directive file for the standalone `novali-v7` package.

Directive-first bootstrap remains mandatory.

Raw freeform text is not the startup authority path.

## What You Need To Produce

NOVALI expects a formal JSON wrapper with:

- `schema_name = NOVALIDirectiveBootstrapFile`
- `schema_version = novali_directive_bootstrap_file_v1`
- a valid `bootstrap_context`
- a valid `directive_spec`

The easiest safe way to create one is the scaffold helper.

## Fastest Safe Path

From the package root:

```powershell
.\standalone_docker\generate_directive_scaffold.ps1 `
  --output .\directive_inputs\my_first_directive.json `
  --directive-id directive_my_first_bootstrap_v1 `
  --directive-text "Initialize NOVALI for a bounded standalone operator run." `
  --clarified-intent-summary "Bootstrap novali-v7 through the canonical operator flow and preserve governed artifact authority before execution."
```

This writes a formal directive wrapper that already includes:

- the current `novali-v7` bootstrap context
- the carried-forward held baseline and routing posture
- a conservative milestone model
- conservative stop conditions
- a bounded trusted-source list
- a valid `bucket_spec`

## Where To Save The File

Recommended location in the standalone handoff package:

- `directive_inputs/`

Example:

- `directive_inputs/my_first_directive.json`

After the directive is ready, continue through the canonical operator launch path:

- `python -m novali_v5.web_operator`
- equivalent convenience form: `python -m novali_v5`
- transitional desktop path: `python -m novali_v5.operator_shell`

## Required Human Meaning

The scaffold helper gives you a valid formal wrapper, but you still own the operator meaning of:

- `directive_id`
- `directive_text`
- `clarified_intent_summary`

Keep those fields specific and operator-readable.

## Valid vs Incomplete Examples

Packaged samples:

- `samples/directives/standalone_valid_directive.example.json`
- `samples/directives/standalone_incomplete_directive.example.json`

Use the valid sample only as a reference or starting point.

Use the incomplete sample only to verify refusal/clarification behavior.

Both samples are non-authoritative.

## Clarification Before Activation

If required fields are missing or ambiguous, NOVALI should refuse activation and surface clarification requirements before governed execution begins.

That is expected behavior, not a packaging failure.

Typical causes:

- missing clarified intent summary
- placeholder or ambiguous required fields
- malformed wrapper/schema

## Trusted Sources

Your directive may name trusted sources, but raw credentials must not appear in the directive file.

Credentials belong in:

- environment variables, or
- the operator-local secrets file

## What This Guide Does Not Change

This guide does not change:

- directive-first bootstrap
- canonical artifact authority
- routing
- thresholds
- live policy
- benchmark semantics
- immutable kernel boundaries
