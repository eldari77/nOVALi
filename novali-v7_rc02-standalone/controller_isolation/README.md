# rc86 Controller Isolation

rc86 adds dual-controller isolation primitives for `novali-v6`, and rc87 consumes those primitives for lane-attributed read-only observation evidence.

Boundaries:

- identity lanes are isolation scaffolding, not independent controllers
- the existing operational controller remains the only coordination and adoption authority
- the Director lane is a mediation namespace only
- `sovereign_good` and `sovereign_dark` are isolated mock lanes only
- no new adoption authority is created
- no real external-world mutation is allowed
- no Space Engineers behavior is active

What rc86 adds:

- a three-lane registry: `director`, `sovereign_good`, `sovereign_dark`
- separate doctrine, memory, summary, intervention, replay, and review namespaces
- a Director-mediated replayable cross-lane message envelope
- identity-bleed detection for shared namespaces, hidden scratchpads, wrong-lane writes, and authority bleed
- operator-visible review evidence when bleed is detected
- lane-aware telemetry on the existing observability substrate
- lane attribution scaffolding for rc87 read-only observation replay and review evidence

What rc86 does not add:

- independent runtime controllers
- live sovereign behavior
- live Space Engineers bridges
- hidden shared scratchpads
- direct sovereign-to-sovereign communication
- any activation of sovereign lanes during rc87 read-only proof paths

rc87 integration note:

- read-only sandbox observations default to `lane_director`
- sovereign lanes remain inactive/mock-only
- wrong-lane attribution becomes review evidence
- cross-lane observation sharing must still use a Director-mediated replayable envelope

Supporting docs:

- `controller_isolation/lane_schema.md`
- `controller_isolation/namespace_isolation.md`
- `controller_isolation/cross_lane_channel.md`
- `controller_isolation/identity_bleed_detector.md`
- `controller_isolation/review_integration.md`
- `observability/controller_isolation_telemetry.md`
