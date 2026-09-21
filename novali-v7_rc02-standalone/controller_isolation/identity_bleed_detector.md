# rc86 Identity-Bleed Detector

Identity bleed means unauthorized sharing or ambiguity across lane doctrine, memory, summaries, intervention history, replay/review evidence, or telemetry identity.

rc86 detects:

- shared doctrine namespaces
- shared memory namespaces
- shared summary namespaces
- shared intervention history paths
- hidden shared scratchpad paths
- direct sovereign-to-sovereign writes
- missing Director mediation
- forbidden message types
- doctrine transfer attempts
- memory dump attempts
- missing lane identity on lane-aware telemetry
- wrong-lane replay/review evidence writes
- authority claims from any lane
- active lane claims without proof-only justification
- credential-like or fake-secret leakage inside lane artifacts

Severity guide:

- `warning`: incomplete but non-authoritative metadata
- `high`: unauthorized cross-lane communication or wrong-lane writes
- `critical`: hidden shared scratchpad, authority claim, doctrine transfer, memory dump, fake-secret leakage

High and critical findings create operator-visible review evidence and are never auto-resolved.
