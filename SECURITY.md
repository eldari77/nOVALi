# Security Policy

NOVALI is experimental source-available software. Please do not disclose secrets or private runtime state in public issues, discussions, pull requests, screenshots, or logs.

## Reporting A Vulnerability

Report security concerns privately to:

```text
eldari77@gmail.com
```

Include:

- affected version or commit;
- a concise description of the issue;
- reproduction steps that do not include real credentials;
- impact and suggested mitigation, if known.

## Secret Handling

Never submit:

- API keys;
- OAuth tokens;
- bearer tokens;
- `.env` files;
- raw trusted-source provider output containing private data;
- runtime ledgers that may contain private local state.

NOVALI's public handoff should preserve redacted metadata and operator-readable evidence only.
