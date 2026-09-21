from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .operator_feedback_obligations import (
    assess_operator_feedback_obligations,
    parse_operator_feedback_obligations,
    source_rejected_by_operator_feedback,
)
from .support_evidence import assess_support_field_coverage, normalize_support_field_name, normalize_support_role_lane

RESIDENT_ARTIFACT_ORDER = [
    "technical_documentation.md",
    "subsystem_matrix.json",
    "interface_specifications.json",
    "dependency_matrix.json",
    "validation_protocols.json",
    "prototype_milestones.json",
    "claim_evidence_register.json",
    "novelty_delta.json",
    "bill_of_materials.json",
    "device_capability_manifest.json",
    "prototype_assembly_plan.json",
    "validation_fixtures.json",
    "risk_controls.json",
    "implementation_readiness_review.json",
    "schematics.md",
    "electrical_interface_spec.json",
    "bench_test_protocol.json",
    "safety_case.json",
    "research_evidence_register.json",
    "regulatory_assumption_log.json",
    "directive_deliverables.json",
    "directive_blueprint.md",
]

MOUNT_FAULT_EXIT_CODE = 74
FULL_DIVE_HARDWARE_DOCUMENTATION_ARTIFACTS = (
    "schematics.md",
    "electrical_interface_spec.json",
    "bench_test_protocol.json",
    "safety_case.json",
    "research_evidence_register.json",
    "regulatory_assumption_log.json",
)
FULL_DIVE_HARDWARE_REQUIRED_FIELDS = {
    "bill_of_materials.json": {
        "row_key": "items",
        "fields": (
            "manufacturer",
            "mpn",
            "datasheet_url",
            "quantity",
            "unit_cost",
            "electrical_rating",
            "compliance_notes",
            "alternatives",
            "linked_risk_control_ref",
            "validation_fixture_ref",
            "execution_gate",
        ),
    },
    "interface_specifications.json": {
        "row_key": "interfaces",
        "fields": (
            "connector",
            "pinout",
            "protocol",
            "signal_level",
            "sample_rate",
            "bandwidth",
            "latency_budget",
            "electrical_isolation",
            "safety_limit",
            "failure_behavior",
            "validation_hooks",
            "hardware_abstraction_layer_id",
            "device_capability_manifest_ref",
        ),
    },
    "validation_fixtures.json": {
        "row_key": "fixtures",
        "fields": (
            "equipment",
            "fixture_wiring",
            "calibration_steps",
            "measurement_method",
            "pass_fail_thresholds",
            "expected_file",
            "expected_outputs",
            "go_no_go_trace",
            "linked_bom_refs",
            "linked_risk_control_refs",
            "execution_gate",
        ),
    },
    "risk_controls.json": {
        "row_key": "controls",
        "fields": (
            "hazard_id",
            "failure_mode",
            "effect",
            "severity",
            "occurrence",
            "detection",
            "rpn",
            "mitigation",
            "residual_risk",
            "standard_ref",
            "verification_method",
            "linked_bom_ref",
            "verification_fixture_ref",
            "execution_gate",
        ),
    },
}
INTERFACE_MATERIALIZED_REQUIRED_FIELDS = (
    *FULL_DIVE_HARDWARE_REQUIRED_FIELDS["interface_specifications.json"]["fields"],
    "bom_ref",
    "validation_fixture_ref",
    "linked_risk_control_ref",
)
SUPPORT_ADEQUACY_REQUIRED_FIELDS_BY_ARTIFACT = {
    artifact_name: tuple(spec.get("fields", ()))
    for artifact_name, spec in FULL_DIVE_HARDWARE_REQUIRED_FIELDS.items()
    if isinstance(spec, Mapping)
}
SUPPORT_ADEQUACY_REQUIRED_FIELDS_BY_ARTIFACT.update(
    {
        "bill_of_materials.json": (
            "manufacturer",
            "mpn",
            "datasheet_url",
            "quantity",
            "unit_cost",
            "electrical_rating",
            "validation_fixture_ref",
            "linked_risk_control_ref",
        ),
        "prototype_milestones.json": (
            "entry_criteria",
            "exit_criteria",
            "measurement_method",
            "pass_fail_threshold",
            "validation_fixture_ref",
            "linked_risk_control_ref",
        ),
        "prototype_assembly_plan.json": (
            "assembly_step",
            "tools",
            "fixture_ref",
            "inspection_method",
            "go_no_go_trace",
            "linked_bom_ref",
            "linked_risk_control_ref",
        ),
    }
)
TECHNICAL_DEPTH_PLACEHOLDER_MARKERS = (
    "operator-approved supplier required",
    "operator approved supplier required",
    "operator/source quote required",
    "trusted-source-or-operator-supplied-datasheet-required",
    "operator-approved measurable spec required",
    "operator threshold required",
    "threshold to be provided by operator",
    "review_required_before_numeric",
    "manufacturer_candidate",
    "source_backed_candidate",
    "source_ref:",
    "support-pack:",
    "exact volts require operator-approved datasheet",
    "fixture-defined; must be recorded",
    "must match electrical_interface_spec.json limits",
    "tbd",
    "to be determined",
    "placeholder",
)
RESIDENT_WAKE_POLL_SECONDS_DEFAULT = 5.0
RESIDENT_WAKE_POLL_SECONDS_MIN = 1.0
RESIDENT_WAKE_POLL_SECONDS_MAX = 30.0
_MOUNT_FAULT_ERRNOS = {
    errno.EIO,
    getattr(errno, "ESTALE", 116),
    getattr(errno, "ENOTCONN", 107),
}


class ConveyorMountFaultError(RuntimeError):
    def __init__(self, mount_kind: str, path: Path, original: OSError) -> None:
        self.mount_kind = str(mount_kind or "unknown")
        self.path = Path(path)
        self.original = original
        message = f"Docker bind-mount I/O fault while accessing {self.mount_kind}: {self.path}"
        super().__init__(message)


def _is_mount_fault_error(exc: OSError) -> bool:
    return int(getattr(exc, "errno", 0) or 0) in _MOUNT_FAULT_ERRNOS


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clamped_resident_wake_poll_seconds(checkout: Mapping[str, Any]) -> float:
    try:
        value = float(
            checkout.get("resident_wake_poll_seconds", RESIDENT_WAKE_POLL_SECONDS_DEFAULT)
            or RESIDENT_WAKE_POLL_SECONDS_DEFAULT
        )
    except (TypeError, ValueError):
        value = RESIDENT_WAKE_POLL_SECONDS_DEFAULT
    return max(RESIDENT_WAKE_POLL_SECONDS_MIN, min(value, RESIDENT_WAKE_POLL_SECONDS_MAX))


def _wake_sequence(inbox_payload: Mapping[str, Any] | None) -> int:
    try:
        return max(0, int(dict(inbox_payload or {}).get("wake_sequence", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _wake_request_from_inbox(inbox_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(inbox_payload or {})
    sequence = _wake_sequence(payload)
    work_order_id = str(payload.get("wake_work_order_id", "") or "").strip()
    if sequence <= 0 or not work_order_id:
        return {}
    return {
        "wake_requested_at": str(payload.get("wake_requested_at", "") or ""),
        "wake_reason": str(payload.get("wake_reason", "") or ""),
        "wake_work_order_id": work_order_id,
        "wake_priority": str(payload.get("wake_priority", "") or ""),
        "wake_sequence": sequence,
        "wake_ack_timeout_seconds": int(float(payload.get("wake_ack_timeout_seconds", 0) or 0)),
    }


def _wake_token_is_fresh(inbox_payload: Mapping[str, Any] | None, processed_wake_sequences: set[int]) -> bool:
    request = _wake_request_from_inbox(inbox_payload)
    if not request:
        return False
    sequence = int(request.get("wake_sequence", 0) or 0)
    if sequence in processed_wake_sequences:
        return False
    work_order = _latest_work_order(dict(inbox_payload or {}))
    if str(work_order.get("work_order_id", "") or "") != str(request.get("wake_work_order_id", "") or ""):
        return False
    return True


def _wake_latency_seconds(requested_at: Any, observed_at: Any) -> float | None:
    requested = _parse_time(requested_at)
    observed = _parse_time(observed_at) or datetime.now(timezone.utc)
    if not requested:
        return None
    return max(0.0, (observed - requested).total_seconds())


def _read_checkout(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _directive_title(directive_text: str) -> str:
    match = re.search(r"^\s*(?:\*\*)?\s*DIRECTIVE\s*:\s*(.+?)(?:\*\*)?\s*$", directive_text, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).strip(" *")
    first_line = next((line.strip(" #*") for line in directive_text.splitlines() if line.strip()), "")
    return first_line[:96] or "Untitled directive"


def _section_lines(directive_text: str, section_name: str) -> list[str]:
    lines = directive_text.splitlines()
    header = re.compile(rf"^\s*(?:\*\*)?\s*{re.escape(section_name)}\s*:\s*(.*?)(?:\*\*)?\s*$", re.IGNORECASE)
    next_header = re.compile(r"^\s*(?:\*\*)?\s*[A-Z][A-Za-z0-9 /&()-]{2,}\s*:\s*", re.IGNORECASE)
    collected: list[str] = []
    in_section = False
    for line in lines:
        header_match = header.match(line)
        if header_match:
            in_section = True
            first = header_match.group(1).strip(" *")
            if first:
                collected.append(first)
            continue
        if in_section and next_header.match(line):
            break
        if in_section and line.strip():
            collected.append(line.strip())
    return collected


def _clean_list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            items.append(cleaned)
    return items


def _build_directive_deliverables(checkout: dict[str, Any], directive_text: str) -> dict[str, Any] | None:
    if "deliverables" not in directive_text.lower():
        return None
    objectives = _clean_list_items(_section_lines(directive_text, "Objectives"))
    deliverables = _clean_list_items(_section_lines(directive_text, "Deliverables"))
    success_criteria = _clean_list_items(_section_lines(directive_text, "Success Criteria"))
    stop_conditions = _clean_list_items(_section_lines(directive_text, "Stop Conditions"))
    librarian_refs = [
        ref for ref in checkout.get("librarian_pack_refs", []) if isinstance(ref, dict)
    ]
    missing_capability_requests = []
    if not librarian_refs:
        missing_capability_requests.append(
            {
                "request_type": "knowledge_checkout",
                "capability": "directive_domain_research_pack",
                "reason": "No reusable librarian pack refs were checked out for this child directive.",
                "kernel_channel": str(
                    checkout.get(
                        "missing_capability_request_channel",
                        "child_return_packet.missing_capability_requests",
                    )
                    or "child_return_packet.missing_capability_requests"
                ),
            }
        )
    return {
        "schema_name": "ConveyorChildDirectiveDeliverables",
        "schema_version": "conveyor_child_directive_deliverables_v1",
        "directive_title": _directive_title(directive_text),
        "objectives": objectives,
        "deliverables": deliverables,
        "success_criteria": success_criteria,
        "stop_conditions": stop_conditions,
        "librarian_pack_refs": librarian_refs,
        "missing_capability_requests": missing_capability_requests,
    }


def _resident_deliverable_payload(checkout: dict[str, Any], directive_text: str) -> dict[str, Any]:
    payload = _build_directive_deliverables(checkout, directive_text)
    if payload:
        return payload
    objectives = _clean_list_items(_section_lines(directive_text, "Objectives"))
    deliverables = _clean_list_items(_section_lines(directive_text, "Deliverables"))
    success_criteria = _clean_list_items(_section_lines(directive_text, "Success Criteria"))
    stop_conditions = _clean_list_items(_section_lines(directive_text, "Stop Conditions"))
    title = _directive_title(directive_text)
    if not deliverables:
        deliverables = [f"Build-grade technical documentation for {title}"]
    return {
        "schema_name": "ConveyorChildDirectiveDeliverables",
        "schema_version": "conveyor_child_directive_deliverables_v1",
        "directive_title": title,
        "objectives": objectives or [f"Deepen {title} into reviewable engineering artifacts."],
        "deliverables": deliverables,
        "success_criteria": success_criteria or ["Each resident cycle produces a concrete artifact delta or a specific blocker."],
        "stop_conditions": stop_conditions or ["Escalate unsafe, unsupported, or ambiguous implementation authority."],
        "librarian_pack_refs": [ref for ref in checkout.get("librarian_pack_refs", []) if isinstance(ref, dict)],
        "missing_capability_requests": [],
    }


def _write_directive_blueprint(path: Path, deliverable_payload: dict[str, Any]) -> None:
    title = str(deliverable_payload.get("directive_title", "") or "Untitled directive")
    lines = [f"# {title}", "", "## Objectives"]
    for item in deliverable_payload.get("objectives", []) or ["No objectives parsed from directive."]:
        lines.append(f"- {item}")
    lines.extend(["", "## Deliverables"])
    for item in deliverable_payload.get("deliverables", []) or ["No deliverables parsed from directive."]:
        lines.append(f"- {item}")
    lines.extend(["", "## Success Criteria"])
    for item in deliverable_payload.get("success_criteria", []) or ["No success criteria parsed from directive."]:
        lines.append(f"- {item}")
    lines.extend(["", "## Stop Conditions"])
    for item in deliverable_payload.get("stop_conditions", []) or ["No stop conditions parsed from directive."]:
        lines.append(f"- {item}")
    lines.extend(["", "## Kernel Support Requests"])
    requests = deliverable_payload.get("missing_capability_requests", []) or []
    if requests:
        for request in requests:
            if isinstance(request, dict):
                lines.append(f"- {request.get('capability', 'unspecified_capability')}: {request.get('reason', '')}")
    else:
        lines.append("- No additional support requested from checked-out bundle.")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _should_build_technical_documentation(checkout: dict[str, Any]) -> bool:
    feedback = str(checkout.get("operator_feedback", "") or "").lower()
    try:
        requeue_count = int(checkout.get("requeue_count", 0) or 0)
    except (TypeError, ValueError):
        requeue_count = 0
    return (
        requeue_count > 0
        or bool(str(checkout.get("previous_return_packet_id", "") or ""))
        or "full technical documentation" in feedback
        or "build-grade" in feedback
        or "subsystem requirements" in feedback
    )


def _write_technical_documentation(
    path: Path,
    *,
    checkout: dict[str, Any],
    deliverable_payload: dict[str, Any],
) -> None:
    title = str(deliverable_payload.get("directive_title", "") or "Untitled directive")
    objectives = list(deliverable_payload.get("objectives", []) or [])
    deliverables = list(deliverable_payload.get("deliverables", []) or [])
    stop_conditions = list(deliverable_payload.get("stop_conditions", []) or [])
    previous_artifacts = [str(item) for item in list(checkout.get("previous_artifacts", []) or [])]
    lines = [
        f"# Technical Documentation: {title}",
        "",
        "## Purpose",
        "This packet develops the directive into reviewable engineering documentation for operator evaluation. It is a bounded child output and does not grant implementation authority.",
        "",
        "## Prior Work Context",
        f"- Previous return packet: {str(checkout.get('previous_return_packet_id', '') or 'none')}",
        f"- Previous artifacts: {', '.join(previous_artifacts) if previous_artifacts else 'none checked out'}",
        "",
        "## System Objectives",
    ]
    for item in objectives or ["No objectives were parsed from the directive."]:
        lines.append(f"- {item}")
    lines.extend(["", "## Deliverable Work Packages"])
    for index, item in enumerate(deliverables or ["No deliverables were parsed from the directive."], start=1):
        lines.extend(
            [
                f"### {index}. {item}",
                "- Intended result: a reviewable specification package for this deliverable.",
                "- Subsystem requirements: define inputs, outputs, operators, dependencies, evidence needs, and review gates.",
                "- Interface contract: record upstream assumptions, downstream consumers, expected data/control boundaries, and isolation constraints.",
                "- Validation strategy: define simulation, tabletop review, non-harmful prototype checks, and acceptance evidence before any real-world deployment.",
                "- Open gaps: request kernel knowledge or skill checkout for domain-specific claims that exceed the current bundle.",
                "",
            ]
        )
    lines.extend(
        [
            "## Architecture and Interfaces",
            f"- Preserve the {title} authority boundary: the child writes only workspace artifacts and returns review packets.",
            "- Treat generated specifications as proposals until operator review accepts them.",
            "- Maintain provenance for every referenced knowledge bundle and every child-produced artifact.",
            "- Interface contract detail: every prototype module records typed inputs, typed outputs, failure modes, validation hooks, and a stop condition before integration.",
            "",
            "## Subsystem decomposition",
            f"- Decompose {title} into named work packages with responsibility owners, dependency ownership, interface surfaces, validation evidence, and escalation gates.",
            "- Keep high-impact biomedical, clinical, cybersecurity, privacy, or physical-world subsystems at architecture and review level until trusted-source support is checked out.",
            "- Track cross-subsystem coupling so future child passes can deepen one subsystem without mutating core state or bypassing operator review.",
            "",
            "## Dependencies and Knowledge Gaps",
            f"- {title} claims that touch biomedical, clinical, security, or safety-critical domains stay review-only until supported by checked-out evidence packs.",
            "- Missing knowledge should be requested through the return packet rather than bypassing network or checkout policy.",
            "",
            "## Prototype build sequence",
            f"- Build step 1: instantiate the {title} canonical artifact baseline, verify support pack refs, and freeze a test environment manifest.",
            f"- Build step 2: assemble the highest-priority subsystem module with named inputs, module output contract, and integration dependency list.",
            f"- Build step 3: connect the module to typed interface fixtures and record pass/fail traces, acceptance thresholds, and failure modes.",
            f"- Build step 4: update the claim/evidence register with artifact impact, confidence, unresolved risks, and evidence refs before requesting promotion.",
            f"- {title} phase 1: produce non-executing architecture and requirement artifacts for operator review.",
            f"- {title} phase 2: develop harmless simulation, mock, or tabletop prototypes that validate interfaces without real-world deployment authority.",
            f"- {title} phase 3: promote only reviewed, reversible, well-scoped prototype plans with explicit dependency map, validation strategy, and safety governance gates.",
            f"- {title} phase 4: stop and request operator/trusted-source review before any invasive, clinical, biological, security-sensitive, or materially risky implementation step.",
            "",
            "## Validation strategy",
            "- Test environment assumptions: resident child container is offline, canonical artifacts are read-only, drafts are writable, and support packs are immutable evidence refs.",
            "- Acceptance threshold: each target artifact must add at least one concrete module, contract, fixture, build step, or evidence-backed claim that changes prototype build decisions.",
            "- Failure modes: missing evidence refs, generic integration rows, unsupported claims, and unsafe execution requests are blocked for kernel/operator review.",
            "",
            "## Safety and governance gates",
            "- Do not include procedural instructions for human or animal experimentation, clinical deployment, invasive systems, or unsafe real-world testing without explicit operator approval and trusted-source review.",
            "- Separate conceptual architecture, feasibility analysis, prototype planning, and implementation authority.",
            "- Escalate when the directive crosses biological, medical, cybersecurity, weapons, privacy, or societal-risk boundaries.",
            "",
            "## Stop Conditions",
        ]
    )
    for item in stop_conditions or ["Escalate if scope becomes unsafe or unsupported."]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _hardware_interface_doc_requested(work_order_context: str, directive_text: str) -> bool:
    text = f"{work_order_context}\n{directive_text}".lower()
    return (
        "hardware interface" in text
        and (
            "full-dive" in text
            or "full dive" in text
            or "unaugmented human" in text
            or "unaugmented-human" in text
            or "neural" in text
            or "bci" in text
        )
    )


def _append_hardware_interface_feasibility_sections(path: Path, *, work_order_id: str) -> None:
    lines = [
        "",
        "## Hardware Interface Feasibility Matrix",
        "| Interface slice | Prototype status | Hardware boundary | Evidence status | Operator decision impact |",
        "| --- | --- | --- | --- | --- |",
        "| Simulation-only embodiment loop | currently buildable simulation/bench prototype | software runtime, synthetic input replay, no human device IO | supported by existing simulation fixtures; still needs executable test traces | safe first prototype slice |",
        "| Non-invasive human-sensing adapter | research-limited bench prototype only | read-only sensor ingestion, isolation barrier, no stimulation, no actuation | requires trusted-source evidence for modality, sampling, SNR, latency, and calibration assumptions | can be specified for review, not deployed |",
        "| Bidirectional sensory or motor full-dive link | not-currently-feasible for an unaugmented human in this packet | no invasive BCI, no neural stimulation, no clinical procedure, no real-world actuation | unsupported until trusted clinical, regulatory, and safety evidence exists | must remain a research gap |",
        "| Human-subject or clinical pathway | not authorized | human-subject use, clinical claims, invasive implants, and stimulation are outside child authority | requires IRB/clinical/regulatory review outside this conveyor return | block from prototype execution |",
        "",
        "## Review-Safe Hardware Schematics",
        "- System block diagram: synthetic signal fixture -> non-invasive read-only HAL adapter -> safety/governance gate -> simulation runtime core -> evidence logger.",
        "- Signal/data-flow boundary: all biological or human-origin signals are represented by synthetic fixtures until trusted-source review authorizes a non-invasive sensing study.",
        "- Isolation boundary: no stimulation channel, actuator channel, implant path, clinical control path, or external device output is connected in this prototype packet.",
        "- Connector/interface map: `synthetic_signal_fixture.v1` feeds `bounded_control_intent.v1`; the HAL adapter emits only typed, read-only intent events to the simulation.",
        "- Power/data safety note: bench fixtures must be offline, isolated, and non-human; grants_execution_authority=false remains mandatory.",
        "- Non-human bench wiring: fixture file -> parser -> schema validator -> latency recorder -> go/no-go trace writer; no electrodes, implants, or live physiology are required.",
        "",
        "## Hardware Specification Unknowns",
        "| Field | Required next value | Current disposition |",
        "| --- | --- | --- |",
        "| sensing modality | EEG/EMG/eye-tracking/other non-invasive modality must be selected with trusted-source support | unresolved |",
        "| channel assumptions | channel count, placement abstraction, and sampling plan | unresolved; do not infer from the simulation HAL |",
        "| sampling and latency budget | sampling rate, end-to-end p95 latency, jitter tolerance, drop behavior | unresolved; current <=20 ms target is a simulation contract only |",
        "| SNR/noise assumptions | signal quality threshold, filtering assumptions, artifact rejection limits | unresolved |",
        "| bandwidth limits | read bandwidth, write/stimulation feasibility, sensory substitution limits | unsupported for full-dive claims |",
        "| calibration requirements | calibration flow, operator review point, fixture acceptance thresholds | unresolved |",
        "| test equipment | synthetic replay harness, latency trace recorder, schema validator, no-human bench fixture | review-safe candidate only |",
        "",
        "## Research Support Matrix",
        "| Claim | Status | Required support before stronger claim |",
        "| --- | --- | --- |",
        "| Simulation prototype can exercise typed embodiment/control contracts | supported as software prototype | executable fixture traces and schema coverage |",
        "| Non-invasive sensing can drive limited control intents | plausible but unsupported here | trusted-source modality review and non-human bench validation |",
        "| Unaugmented-human full-dive bidirectional link is build-ready | unsupported and not-currently-feasible in this return | clinical/regulatory literature, safety case, and operator authorization |",
        "| Neural write/stimulation path is available | unsupported and prohibited in this child packet | trusted clinical pathway; outside current authority |",
        "| unaugmented-human compatibility | unresolved | evidence-backed feasibility limits and explicit unknowns |",
        "",
        "## Child-Side Return Criteria For This Work Order",
        f"- Work order `{work_order_id or 'kernel_context'}` must return only when the artifact distinguishes buildable simulation/bench work from unsupported full-dive hardware claims.",
        "- Required evidence refs must identify whether claims are supported, unsupported, or blocked pending trusted-source review.",
        "- The return remains operator-review-only: grants_execution_authority=false, no human-subject deployment, no clinical use, no invasive BCI, no neural stimulation, and no real-world actuation.",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")


def _build_readiness_review(
    *,
    checkout: dict[str, Any],
    deliverable_payload: dict[str, Any],
) -> dict[str, Any]:
    support_requests = list(deliverable_payload.get("missing_capability_requests", []) or [])
    title = str(deliverable_payload.get("directive_title", "") or "Untitled directive")
    title_lower = title.lower()
    pack_refs = _pack_ids(checkout)
    if "full dive" in title_lower or "virtual simulation" in title_lower:
        prototype_boundary = "software_simulation_only"
        build_steps = [
            {
                "step": "Prepare the offline simulation runtime skeleton",
                "output": "versioned runtime configuration, module registry, and deterministic launch command",
                "evidence_refs": pack_refs,
            },
            {
                "step": "Implement replayable input/control-loop fixtures",
                "output": "typed input schema, control-loop event stream, and replay harness contract",
                "evidence_refs": pack_refs,
            },
            {
                "step": "Run simulation-only validation gates",
                "output": "fixture metrics, failure-mode traces, and operator review packet",
                "evidence_refs": pack_refs,
            },
        ]
        test_environment_assumptions = [
            {
                "name": "offline_child_execution",
                "assumption": "child container has network deny-all and receives only immutable checkout/support refs",
            },
            {
                "name": "simulation_only_inputs",
                "assumption": "prototype evaluation uses synthetic or mock control data, not human-subject telemetry",
            },
        ]
        acceptance_thresholds = [
            {"metric": "fixture_pass_rate", "threshold": "100% of required simulation fixtures pass"},
            {"metric": "typed_contract_coverage", "threshold": "every runtime/control-loop boundary has inputs, outputs, failure modes, and validation hooks"},
        ]
        unresolved_risks = [
            {
                "risk": "simulation fidelity may not predict real-world interaction quality",
                "mitigation": "keep outputs marked simulation-only until operator approves external validation scope",
            }
        ]
    elif "grin" in title_lower or "human advancement" in title_lower:
        prototype_boundary = "non_invasive_synthetic_data_only"
        build_steps = [
            {
                "step": "Define non-invasive synthetic signal and feature contracts",
                "output": "synthetic trace schema, feature extraction boundary, and validation fixture manifest",
                "evidence_refs": pack_refs,
            },
            {
                "step": "Build architecture-only prototype harness",
                "output": "offline replay harness, synthetic-data generator contract, and governance gate map",
                "evidence_refs": pack_refs,
            },
            {
                "step": "Evaluate non-clinical readiness gates",
                "output": "fixture metrics, unsupported claim list, and operator-gated next-step register",
                "evidence_refs": pack_refs,
            },
        ]
        test_environment_assumptions = [
            {
                "name": "synthetic_non_clinical_data",
                "assumption": "no human-subject, clinical, invasive, or biological execution data is used by child workers",
            },
            {
                "name": "offline_child_execution",
                "assumption": "child container remains credential-free and network-denied",
            },
        ]
        acceptance_thresholds = [
            {"metric": "synthetic_fixture_pass_rate", "threshold": "100% of required synthetic replay fixtures pass"},
            {"metric": "execution_gate_coverage", "threshold": "all invasive, clinical, or human-subject steps are operator-gated"},
        ]
        unresolved_risks = [
            {
                "risk": "human-subject or clinical applicability cannot be inferred from synthetic architecture artifacts",
                "mitigation": "require explicit operator and trusted-source governance approval before any real-world execution step",
            }
        ]
    else:
        prototype_boundary = "prototype_execution_gated"
        build_steps = [
            {
                "step": "Assemble offline prototype build package",
                "output": "build steps, typed interfaces, validation fixtures, and review packet",
                "evidence_refs": pack_refs,
            },
            {
                "step": "Run bounded validation harness",
                "output": "pass/fail metrics and unresolved risk register",
                "evidence_refs": pack_refs,
            },
        ]
        test_environment_assumptions = [
            {
                "name": "offline_child_execution",
                "assumption": "child container remains network-denied and cannot mutate core framework state",
            }
        ]
        acceptance_thresholds = [
            {"metric": "required_gate_coverage", "threshold": "all required readiness gates have explicit pass/fail evidence"}
        ]
        unresolved_risks = [
            {"risk": "domain details may need trusted-source review", "mitigation": "kernel-mediated support pack required"}
        ]
    return {
        "schema_name": "ConveyorChildImplementationReadinessReview",
        "schema_version": "conveyor_child_implementation_readiness_review_v1",
        "directive_title": title,
        "previous_return_packet_id": str(checkout.get("previous_return_packet_id", "") or ""),
        "previous_artifacts": [str(item) for item in list(checkout.get("previous_artifacts", []) or [])],
        "readiness_state": "prototype_candidate_review",
        "prototype_boundary": prototype_boundary,
        "implementation_authority": "not_granted_by_child_return",
        "support_request_count": len(support_requests),
        "build_steps": build_steps,
        "go_no_go_criteria": [
            {
                "gate": "all_required_artifacts_promoted",
                "decision": "go only when canonical artifacts have passing quality-depth gates",
            },
            {
                "gate": "unsupported_or_high_risk_claims_present",
                "decision": "no_go until trusted-source evidence or operator clarification is staged",
            },
            {
                "gate": "real_world_execution_requested",
                "decision": "no_go_without_operator_approval",
            },
        ],
        "test_environment_assumptions": test_environment_assumptions,
        "acceptance_thresholds": acceptance_thresholds,
        "unresolved_risks": unresolved_risks,
        "evidence_coverage": [
            {
                "claim_area": "prototype readiness package",
                "evidence_refs": pack_refs,
                "coverage_state": "support_pack_refs_available" if pack_refs else "trusted_source_support_needed",
            }
        ],
        "prototype_execution_gates": [
            {
                "gate": "real_world_test_execution",
                "status": "execution_gated_by_operator_approval",
                "authority": "kernel_operator_review_required",
            },
            {
                "gate": "deployment_or_human_subject_use",
                "status": "execution_gated_by_operator_approval",
                "authority": "kernel_operator_review_required",
            },
        ],
        "review_gates": [
            "operator_acceptance",
            "trusted_knowledge_checkout_for_domain_claims",
            "safety_and_governance_review_before_real_world_use",
            "prototype_execution_gated",
        ],
    }


def _pack_ids(checkout: dict[str, Any]) -> list[str]:
    refs = []
    for ref in list(checkout.get("librarian_pack_refs", []) or []):
        if isinstance(ref, dict) and str(ref.get("pack_id", "") or "").strip():
            refs.append(str(ref.get("pack_id", "")).strip())
    for ref in list(checkout.get("support_request_refs", []) or []):
        if isinstance(ref, dict) and str(ref.get("pack_id", "") or "").strip():
            pack_id = str(ref.get("pack_id", "")).strip()
            if pack_id not in refs:
                refs.append(pack_id)
    return refs


def _read_child_support_manifest(checkout: Mapping[str, Any]) -> dict[str, Any]:
    def _hydrate_pack_rows(payload: dict[str, Any], root: Path) -> dict[str, Any]:
        packs = []
        for pack in list(payload.get("packs", []) or []):
            if not isinstance(pack, Mapping):
                continue
            updated_pack = dict(pack)
            relative_path = str(updated_pack.get("relative_path", "") or "").strip()
            if relative_path:
                pack_path = (root / relative_path).resolve()
                try:
                    root_resolved = root.resolve()
                except OSError:
                    root_resolved = root
                if root_resolved in pack_path.parents or pack_path == root_resolved:
                    try:
                        pack_payload = json.loads(pack_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        pack_payload = {}
                    if isinstance(pack_payload, Mapping):
                        pack_rows = [
                            dict(row)
                            for row in list(pack_payload.get("rows", []) or [])
                            if isinstance(row, Mapping)
                        ]
                        if pack_rows:
                            updated_pack["rows"] = pack_rows
                        for key in (
                            "support_evidence_field_coverage",
                            "support_pack_consumability_state",
                            "non_consumable_support_reasons",
                        ):
                            if key in pack_payload:
                                updated_pack[key] = pack_payload.get(key)
            packs.append(updated_pack)
        payload["packs"] = packs
        return payload

    candidates = [
        str(checkout.get("support_pack_mount_path", "") or ""),
        str(checkout.get("support_pack_checkout_path", "") or ""),
        str(checkout.get("host_support_pack_checkout_path", "") or ""),
    ]
    for value in candidates:
        if not value:
            continue
        root = Path(value)
        manifest_path = root / "manifest.json" if root.suffix != ".json" else root
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return _hydrate_pack_rows(payload, manifest_path.parent)
    manifest = checkout.get("support_pack_manifest", {})
    return dict(manifest) if isinstance(manifest, Mapping) else {}


def _support_manifest_row_count(manifest: Mapping[str, Any]) -> int:
    try:
        total = int(manifest.get("total_row_count", 0) or 0)
    except (TypeError, ValueError):
        total = 0
    if total > 0:
        return total
    count = 0
    for pack in list(manifest.get("packs", []) or []):
        if not isinstance(pack, Mapping):
            continue
        try:
            count += int(pack.get("row_count", 0) or 0)
        except (TypeError, ValueError):
            pass
        rows = pack.get("rows", [])
        if isinstance(rows, list):
            count = max(count, len(rows))
    return count


def _support_manifest_int(manifest: Mapping[str, Any], key: str) -> int:
    try:
        return max(0, int(manifest.get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def _support_manifest_pack_ids(manifest: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for pack in list(manifest.get("packs", []) or []):
        if isinstance(pack, Mapping) and str(pack.get("pack_id", "") or "").strip():
            pack_id = str(pack.get("pack_id", "")).strip()
            if pack_id not in ids:
                ids.append(pack_id)
    return ids


def _support_manifest_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pack in list(manifest.get("packs", []) or []):
        if not isinstance(pack, Mapping):
            continue
        pack_id = str(pack.get("pack_id", "") or "").strip()
        for row in list(pack.get("rows", []) or []):
            if not isinstance(row, Mapping):
                continue
            payload = dict(row)
            if pack_id and not str(payload.get("support_pack_id", "") or "").strip():
                payload["support_pack_id"] = pack_id
            rows.append(payload)
    return rows


def _technology_design_rows_from_support_manifest(
    manifest: Mapping[str, Any],
    *,
    target_artifact: str,
) -> list[dict[str, Any]]:
    target = str(target_artifact or "").strip()
    design_rows: list[dict[str, Any]] = []
    for row in _support_manifest_rows(manifest):
        row_target = str(row.get("target_artifact", "") or "").strip()
        if target and row_target and row_target != target:
            continue
        provenance = " ".join(
            str(row.get(key, "") or "")
            for key in (
                "support_row_kind",
                "obligation_kind",
                "source_url",
                "citation_ref",
                "evidence_ref",
                "r_and_d_design_brief_id",
            )
        ).lower()
        covered_fields = [
            str(item).strip()
            for item in list(row.get("covered_fields", []) or row.get("field_coverage", []) or [])
            if str(item).strip()
        ]
        has_source = bool(
            str(row.get("source_url", "") or row.get("citation_ref", "") or row.get("evidence_ref", "") or "").strip()
        )
        has_specs = bool(row.get("spec_values") or row.get("concrete_spec_values")) or any(
            str(row.get(field, "") or "").strip()
            for field in FULL_DIVE_HARDWARE_REQUIRED_FIELDS["interface_specifications.json"]["fields"]
        )
        generic_interface_support = (
            target == "interface_specifications.json"
            and row_target == "interface_specifications.json"
            and bool(covered_fields)
            and has_source
            and has_specs
        )
        if (
            "technology_design_obligation" in provenance
            or "r_and_d_design_brief" in provenance
            or generic_interface_support
        ):
            design_rows.append(row)
    return design_rows


def _technology_design_obligations_from_context(
    work_order: Mapping[str, Any],
    design_rows: list[dict[str, Any]],
    *,
    target_artifact: str,
) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_obligation(value: Mapping[str, Any]) -> None:
        obligation_id = str(
            value.get("technology_design_obligation_id")
            or value.get("obligation_id")
            or value.get("row_id")
            or value.get("evidence_ref")
            or ""
        ).strip()
        fields = [
            str(item).strip()
            for item in list(value.get("covered_fields", []) or value.get("missing_fields", []) or [])
            if str(item).strip()
        ]
        field = str(value.get("field", "") or "").strip()
        if field and field not in fields:
            fields.append(field)
        key = obligation_id or "|".join([target_artifact, ",".join(fields), str(value.get("claim", "") or "")])
        if not key or key in seen:
            return
        seen.add(key)
        obligations.append(
            {
                "technology_design_obligation_id": obligation_id,
                "target_artifact": str(value.get("target_artifact", "") or target_artifact),
                "fields": fields,
                "field": field or (fields[0] if fields else ""),
                "gap_kind": str(value.get("gap_kind", "") or "technology_design_needed"),
                "claim": str(value.get("claim", "") or ""),
                "evidence_ref": str(value.get("evidence_ref", "") or ""),
                "source_url": str(value.get("source_url", "") or value.get("citation_ref", "") or ""),
                "grants_execution_authority": False,
            }
        )

    for obligation in list(work_order.get("technology_design_obligations", []) or []):
        if isinstance(obligation, Mapping):
            add_obligation(obligation)
    for row in design_rows:
        add_obligation(row)
    return obligations


def _support_row_spec_values(row: Mapping[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    raw_values = row.get("spec_values", row.get("concrete_spec_values", []))
    aliases = {
        "latency": "latency_budget",
        "isolation": "electrical_isolation",
        "safety": "safety_limit",
        "safety_boundary": "safety_limit",
        "fail_state": "failure_behavior",
        "failure": "failure_behavior",
        "validation": "validation_hooks",
        "validation_hook": "validation_hooks",
        "hal": "hardware_abstraction_layer_id",
        "hal_id": "hardware_abstraction_layer_id",
        "hardware_abstraction_layer": "hardware_abstraction_layer_id",
        "manifest": "device_capability_manifest_ref",
        "device_manifest": "device_capability_manifest_ref",
        "device_manifest_ref": "device_capability_manifest_ref",
        "capability_manifest": "device_capability_manifest_ref",
        "bom": "bom_ref",
        "bom_refs": "bom_ref",
        "fixture": "validation_fixture_ref",
        "fixture_ref": "validation_fixture_ref",
        "fixture_refs": "validation_fixture_ref",
        "wiring": "fixture_wiring",
        "calibration": "calibration_steps",
        "calibration_step": "calibration_steps",
        "measurement": "measurement_method",
        "measurement_methods": "measurement_method",
        "pass_fail": "pass_fail_thresholds",
        "pass_fail_threshold": "pass_fail_thresholds",
        "risk_control_refs": "linked_risk_control_refs",
        "risk_control_ref": "linked_risk_control_refs",
        "risk": "linked_risk_control_ref",
        "risk_ref": "linked_risk_control_ref",
        "risk_refs": "linked_risk_control_ref",
    }

    def add_pair(raw_key: Any, raw_value: Any) -> None:
        clean_key = re.sub(r"[^a-z0-9]+", "_", str(raw_key or "").strip().lower()).strip("_")
        clean_key = aliases.get(clean_key, clean_key)
        clean_value = str(raw_value or "").strip()
        if clean_key and clean_value:
            values[clean_key] = clean_value

    def add_mapping(mapping: Mapping[str, Any]) -> None:
        for key, value in mapping.items():
            if isinstance(value, (dict, list, tuple, set)):
                continue
            add_pair(key, value)

    if isinstance(raw_values, Mapping):
        add_mapping(raw_values)
    elif isinstance(raw_values, (list, tuple, set)):
        for item in list(raw_values or []):
            if isinstance(item, Mapping):
                add_mapping(item)
                continue
            text = str(item or "").strip()
            if not text or ("=" not in text and ":" not in text):
                continue
            separator = "=" if "=" in text else ":"
            key, value = text.split(separator, 1)
            add_pair(key, value)
    elif isinstance(raw_values, str):
        for part in re.split(r"[\n;]+", raw_values):
            text = part.strip()
            if not text or ("=" not in text and ":" not in text):
                continue
            separator = "=" if "=" in text else ":"
            key, value = text.split(separator, 1)
            add_pair(key, value)
    top_level_fields = [
        *FULL_DIVE_HARDWARE_REQUIRED_FIELDS["interface_specifications.json"]["fields"],
        "manufacturer",
        "supplier",
        "mpn",
        "part_number",
        "datasheet_url",
        "source_url",
        "citation_ref",
        "quantity",
        "qty",
        "unit_cost",
        "cost_basis",
        "cost",
        "electrical_rating",
        "rating",
        "measurable_spec",
        "standards_assumption",
        "standards_assumptions",
        "compliance_notes",
        "go_no_go_trace",
        "go_no_go_ref",
        "validation_hooks",
        "validation_hook",
        "hardware_abstraction_layer_id",
        "hal",
        "hal_id",
        "device_capability_manifest_ref",
        "manifest",
        "device_manifest",
        "device_manifest_ref",
        "bom_ref",
        "bom_refs",
        "bom",
        "validation_fixture_ref",
        "fixture",
        "fixture_ref",
        "fixture_id",
        "equipment",
        "fixture_wiring",
        "calibration_steps",
        "measurement_method",
        "pass_fail_thresholds",
        "linked_bom_refs",
        "linked_bom_ref",
        "linked_risk_control_refs",
        "linked_risk_control_ref",
        "execution_gate",
        "linked_risk_control_ref",
        "risk",
        "risk_ref",
    ]
    for field in top_level_fields:
        if str(row.get(field, "") or "").strip():
            add_pair(field, row.get(field))
    return values


def _first_support_value(
    specs: Mapping[str, str],
    *keys: str,
) -> str:
    for key in keys:
        normalized = re.sub(r"[^a-z0-9]+", "_", str(key or "").lower()).strip("_")
        if normalized and str(specs.get(normalized, "") or "").strip():
            return str(specs.get(normalized, "")).strip()
    return ""


def _interface_row_from_design_support(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    specs = _support_row_spec_values(row)
    row_id = str(row.get("row_id", "") or row.get("support_row_id", "") or f"technology_design_obligation_{index}")
    target_row_id = str(
        row.get("target_row_id", "")
        or row.get("target_interface_id", "")
        or row.get("interface_id", "")
        or row.get("target_interface_group", "")
        or row.get("interface_group", "")
        or ""
    ).strip()
    evidence_ref = str(row.get("evidence_ref", "") or "")
    source_ref = str(row.get("source_url", "") or row.get("citation_ref", "") or "")
    citation_ref = str(row.get("citation_ref", "") or "")
    datasheet_ref = str(row.get("datasheet_url", "") or row.get("source_url", "") or citation_ref or "")
    support_pack_id = str(row.get("support_pack_id", "") or "")
    support_refs = [item for item in (support_pack_id, row_id) if item]
    evidence_refs = [item for item in (evidence_ref, source_ref) if item]
    interface_id_source = target_row_id or "support_completed_interface_contract"
    interface_id = re.sub(r"[^a-z0-9]+", "_", interface_id_source.lower()).strip("_") or f"technology_design_interface_{index}"
    interface = {
        "interface_id": interface_id,
        "name": str(row.get("claim", "") or f"Technology design interface obligation {index}")[:160],
        "connector": _first_support_value(specs, "connector", "boundary", "interface_boundary"),
        "pinout": _first_support_value(specs, "pinout", "channel_map", "channels"),
        "protocol": _first_support_value(specs, "protocol", "transport"),
        "signal_level": _first_support_value(specs, "signal_level", "signal_levels", "logic_level"),
        "sample_rate": _first_support_value(specs, "sample_rate", "sample_rate_hz"),
        "bandwidth": _first_support_value(specs, "bandwidth", "passband"),
        "latency_budget": _first_support_value(specs, "latency_budget", "latency"),
        "electrical_isolation": _first_support_value(specs, "electrical_isolation", "isolation"),
        "safety_limit": _first_support_value(specs, "safety_limit", "safety_boundary"),
        "failure_behavior": _first_support_value(specs, "failure_behavior", "fail_state"),
        "validation_hooks": _first_support_value(specs, "validation_hooks", "validation_hook", "fixture_hook", "validation"),
        "hardware_abstraction_layer_id": _first_support_value(
            specs,
            "hardware_abstraction_layer_id",
            "hal_id",
        ),
        "device_capability_manifest_ref": _first_support_value(
            specs,
            "device_capability_manifest_ref",
            "device_manifest_ref",
            "capability_manifest_ref",
        ),
        "bom_ref": _first_support_value(specs, "bom_ref", "bom_refs"),
        "validation_fixture_ref": _first_support_value(specs, "fixture_ref", "validation_fixture_ref", "fixture"),
        "linked_risk_control_ref": _first_support_value(specs, "risk_ref", "linked_risk_control_ref", "risk"),
        "covered_fields": [str(item) for item in list(row.get("covered_fields", []) or []) if str(item).strip()],
        "support_row_ids": support_refs,
        "evidence_refs": evidence_refs,
        "source_url": source_ref,
        "datasheet_url": datasheet_ref,
        "citation_ref": citation_ref,
        "readiness_state": "research_design_only",
        "grants_execution_authority": False,
    }
    interface["bom_refs"] = [
        value
        for value in (
            str(interface.get("bom_ref", "") or ""),
            str(row.get("bom_ref", "") or ""),
        )
        if value
    ]
    interface["validation_fixture_refs"] = [
        value
        for value in (
            str(interface.get("validation_fixture_ref", "") or ""),
            str(row.get("validation_fixture_ref", "") or row.get("fixture_ref", "") or ""),
        )
        if value
    ]
    interface["risk_refs"] = [
        value
        for value in (
            str(interface.get("linked_risk_control_ref", "") or ""),
            str(row.get("risk_ref", "") or row.get("linked_risk_control_ref", "") or ""),
        )
        if value
    ]
    return interface


def _merge_interface_support_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    list_fields = {
        "covered_fields",
        "support_row_ids",
        "evidence_refs",
        "bom_refs",
        "validation_fixture_refs",
        "risk_refs",
    }
    for row in rows:
        interface_id = str(row.get("interface_id", "") or row.get("row_id", "") or "").strip()
        if not interface_id:
            continue
        if interface_id not in merged_by_id:
            merged_by_id[interface_id] = dict(row)
            order.append(interface_id)
            continue
        merged = merged_by_id[interface_id]
        for key, value in row.items():
            if value in ("", [], {}, None):
                continue
            if key in list_fields:
                existing = [str(item) for item in list(merged.get(key, []) or []) if str(item).strip()]
                for item in list(value or []):
                    text = str(item or "").strip()
                    if text and text not in existing:
                        existing.append(text)
                merged[key] = existing
            elif not str(merged.get(key, "") or "").strip():
                merged[key] = value
        for singular, plural in (
            ("bom_ref", "bom_refs"),
            ("validation_fixture_ref", "validation_fixture_refs"),
            ("linked_risk_control_ref", "risk_refs"),
        ):
            value = str(merged.get(singular, "") or row.get(singular, "") or "").strip()
            if value:
                values = [str(item) for item in list(merged.get(plural, []) or []) if str(item).strip()]
                if value not in values:
                    values.append(value)
                merged[plural] = values
    return [merged_by_id[interface_id] for interface_id in order]


def _artifact_design_row_key(target_artifact: str, payload: Mapping[str, Any]) -> str:
    configured = str(
        dict(FULL_DIVE_HARDWARE_REQUIRED_FIELDS.get(target_artifact, {}) or {}).get("row_key", "")
        or ""
    ).strip()
    candidates = {
        "bill_of_materials.json": ("items", "components", "rows"),
        "validation_fixtures.json": ("fixtures", "rows", "items"),
        "risk_controls.json": ("controls", "risks", "rows", "items"),
    }.get(target_artifact, ("rows", "items"))
    if configured:
        candidates = (configured, *tuple(item for item in candidates if item != configured))
    for key in candidates:
        if isinstance(payload.get(key), list):
            return key
    return candidates[0]


def _slug(value: Any, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")
    return text or fallback


def _support_row_refs(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    support_refs = [
        str(item)
        for item in (
            row.get("support_pack_id", ""),
            row.get("row_id", ""),
            row.get("support_row_id", ""),
            row.get("technology_design_obligation_id", ""),
        )
        if str(item).strip()
    ]
    evidence_refs = [
        str(item)
        for item in (
            row.get("evidence_ref", ""),
            row.get("source_url", ""),
            row.get("citation_ref", ""),
        )
        if str(item).strip()
    ]
    return list(dict.fromkeys(support_refs)), list(dict.fromkeys(evidence_refs))


def _design_obligation_source_row(
    obligation: Mapping[str, Any],
    design_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    obligation_id = str(obligation.get("technology_design_obligation_id", "") or "").strip()
    evidence_ref = str(obligation.get("evidence_ref", "") or "").strip()
    for row in design_rows:
        if obligation_id and obligation_id in {
            str(row.get("technology_design_obligation_id", "") or ""),
            str(row.get("row_id", "") or ""),
            str(row.get("support_row_id", "") or ""),
        }:
            return dict(row)
        if evidence_ref and evidence_ref == str(row.get("evidence_ref", "") or ""):
            return dict(row)
    return dict(obligation)


def _first_design_value(
    specs: Mapping[str, str],
    row: Mapping[str, Any],
    *keys: str,
    default: str = "",
) -> str:
    value = _first_support_value(specs, *keys)
    if value:
        return value
    for key in keys:
        if str(row.get(key, "") or "").strip():
            return str(row.get(key, "")).strip()
        normalized = normalize_support_field_name(key)
        if normalized and str(row.get(normalized, "") or "").strip():
            return str(row.get(normalized, "")).strip()
    return default


def _design_list_value(specs: Mapping[str, str], row: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw_values: list[Any]
        if key in row:
            raw = row.get(key)
            raw_values = list(raw) if isinstance(raw, (list, tuple, set)) else [raw]
        else:
            raw_values = []
        for item in raw_values:
            text = str(item or "").strip()
            if text and text not in values:
                values.append(text)
        spec = _first_support_value(specs, key)
        if spec and spec not in values:
            values.append(spec)
    return values


def _design_row_for_artifact(
    *,
    target_artifact: str,
    obligation: Mapping[str, Any],
    source_row: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    specs = _support_row_spec_values(source_row)
    obligation_id = str(
        obligation.get("technology_design_obligation_id", "")
        or source_row.get("technology_design_obligation_id", "")
        or source_row.get("row_id", "")
        or f"technology_design_obligation_{index}"
    ).strip()
    fields = [
        normalize_support_field_name(item)
        for item in list(obligation.get("fields", []) or source_row.get("covered_fields", []) or [])
        if normalize_support_field_name(item)
    ]
    row_base = _slug(obligation_id, f"technology_design_obligation_{index}")
    claim = str(source_row.get("claim", "") or obligation.get("claim", "") or "").strip()
    support_refs, evidence_refs = _support_row_refs(source_row)
    source_search_need = _first_design_value(
        specs,
        source_row,
        "source_search_need",
        "source_search_needs",
        "commercial_component_search",
        default="source-backed commercial component selection required after design reduction",
    )
    common = {
        "technology_design_obligation_id": obligation_id,
        "target_fields": fields,
        "claim": claim or "Technology design obligation requires review-only reduction before build evidence.",
        "proposed_subsystem_requirement": _first_design_value(
            specs,
            source_row,
            "proposed_subsystem_requirement",
            "subsystem_requirement",
            "requirement",
            "claim",
            default=claim or "Define subsystem requirements before selecting build parts.",
        ),
        "design_parameter_targets": _first_design_value(
            specs,
            source_row,
            "design_parameter_targets",
            "parameter_targets",
            "constraints",
            "covered_fields",
            default=", ".join(fields) or "field obligations to reduce before build evidence",
        ),
        "commercial_component_source_required": True,
        "unavailable_source_reason": _first_design_value(
            specs,
            source_row,
            "unavailable_source_reason",
            "source_gap_reason",
            default="technology_design_obligation_not_yet_reduced_to_source_backed_component",
        ),
        "source_search_needs": _design_list_value(
            specs,
            source_row,
            "source_search_needs",
            "source_search_need",
            "commercial_component_search",
        )
        or [source_search_need],
        "support_row_ids": support_refs,
        "evidence_refs": evidence_refs,
        "execution_gate": "review_only_design_reduction_no_build_authority",
        "grants_execution_authority": False,
    }
    if target_artifact == "bill_of_materials.json":
        return {
            "item_id": _slug(source_row.get("target_row_id", "") or row_base, f"technology_design_bom_{index}"),
            "name": _first_design_value(
                specs,
                source_row,
                "name",
                "component_name",
                default=f"{row_base.replace('_', ' ')} design reduction",
            ),
            "category": _first_design_value(specs, source_row, "category", default="technology_design_reduction"),
            "required_for": _first_design_value(
                specs,
                source_row,
                "required_for",
                "subsystem",
                default="full_dive_review_only_bom_reduction",
            ),
            "validation_fixture_ref": _first_design_value(
                specs,
                source_row,
                "validation_fixture_ref",
                "fixture_ref",
                "fixture",
                default=f"validation_fixtures.json#{row_base}_fixture",
            ),
            "linked_risk_control_ref": _first_design_value(
                specs,
                source_row,
                "linked_risk_control_ref",
                "risk_ref",
                "risk",
                default=f"risk_controls.json#{row_base}_risk",
            ),
            **common,
        }
    if target_artifact == "validation_fixtures.json":
        return {
            "fixture_id": _slug(source_row.get("target_row_id", "") or row_base, f"technology_design_fixture_{index}"),
            "name": _first_design_value(specs, source_row, "name", default=f"{row_base.replace('_', ' ')} fixture design"),
            "equipment": _first_design_value(
                specs,
                source_row,
                "equipment",
                default="synthetic bench fixture design to be source-backed before build",
            ),
            "fixture_wiring": _first_design_value(
                specs,
                source_row,
                "fixture_wiring",
                default="review-only fixture wiring boundary to be specified",
            ),
            "measurement_method": _first_design_value(
                specs,
                source_row,
                "measurement_method",
                default="synthetic bench measurement method to be reduced",
            ),
            "pass_fail_thresholds": _first_design_value(
                specs,
                source_row,
                "pass_fail_thresholds",
                "go_no_go_trace",
                default="operator-reviewed go/no-go thresholds required",
            ),
            "linked_bom_refs": _design_list_value(specs, source_row, "linked_bom_refs", "linked_bom_ref", "bom_ref")
            or [f"bill_of_materials.json#{row_base}"],
            "linked_risk_control_refs": _design_list_value(
                specs,
                source_row,
                "linked_risk_control_refs",
                "linked_risk_control_ref",
                "risk_ref",
            )
            or [f"risk_controls.json#{row_base}_risk"],
            **common,
        }
    if target_artifact == "risk_controls.json":
        return {
            "control_id": _slug(source_row.get("target_row_id", "") or row_base, f"technology_design_risk_{index}"),
            "hazard_id": _first_design_value(specs, source_row, "hazard_id", default=f"hazard_{row_base}"),
            "failure_mode": _first_design_value(
                specs,
                source_row,
                "failure_mode",
                default="design obligation remains unreduced to source-backed build evidence",
            ),
            "effect": _first_design_value(
                specs,
                source_row,
                "effect",
                default="cannot claim build readiness until linked evidence is reduced",
            ),
            "severity": _first_design_value(
                specs,
                source_row,
                "severity",
                default="unknown_until_operator_review",
            ),
            "occurrence": _first_design_value(
                specs,
                source_row,
                "occurrence",
                default="unknown_until_fixture_validation",
            ),
            "detectability": _first_design_value(
                specs,
                source_row,
                "detectability",
                default="requires_validation_fixture_before_build_readiness",
            ),
            "mitigation": _first_design_value(
                specs,
                source_row,
                "mitigation",
                default="create linked BOM and fixture evidence before operator review",
            ),
            "linked_bom_ref": _first_design_value(
                specs,
                source_row,
                "linked_bom_ref",
                "bom_ref",
                default=f"bill_of_materials.json#{row_base}",
            ),
            "verification_fixture_ref": _first_design_value(
                specs,
                source_row,
                "verification_fixture_ref",
                "validation_fixture_ref",
                "fixture_ref",
                default=f"validation_fixtures.json#{row_base}_fixture",
            ),
            "go_no_go_criteria": _first_design_value(
                specs,
                source_row,
                "go_no_go_criteria",
                "go_no_go_trace",
                "pass_fail_thresholds",
                default="operator-reviewed go/no-go criteria required before build readiness",
            ),
            **common,
        }
    return {
        "row_id": row_base,
        "name": _first_design_value(specs, source_row, "name", default=f"{row_base.replace('_', ' ')} design reduction"),
        **common,
    }


def _merge_design_rows(
    existing_rows: list[dict[str, Any]],
    incoming_rows: list[dict[str, Any]],
    *,
    target_artifact: str,
) -> tuple[list[dict[str, Any]], bool]:
    id_fields = {
        "bill_of_materials.json": ("item_id", "row_id", "id", "name"),
        "validation_fixtures.json": ("fixture_id", "row_id", "id", "name"),
        "risk_controls.json": ("control_id", "hazard_id", "row_id", "id", "name"),
    }.get(target_artifact, ("row_id", "id", "name"))

    def row_id(row: Mapping[str, Any]) -> str:
        for field in id_fields:
            text = str(row.get(field, "") or "").strip()
            if text:
                return _slug(text, "")
        return ""

    merged_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    changed = False
    for row in existing_rows:
        key = row_id(row)
        if not key:
            key = f"existing_{len(order)}"
        merged_by_id[key] = dict(row)
        order.append(key)
    for row in incoming_rows:
        key = row_id(row) or f"incoming_{len(order)}"
        current = dict(merged_by_id.get(key, {}))
        merged = {**current, **{field: value for field, value in row.items() if value not in ("", [], {}, None)}}
        if key not in merged_by_id:
            order.append(key)
            changed = True
        elif merged != current:
            changed = True
        merged_by_id[key] = merged
    return [merged_by_id[key] for key in order], changed


def _materialize_technology_design_rows_for_target_artifact(
    payload: dict[str, Any],
    design_rows: list[dict[str, Any]],
    obligations: list[dict[str, Any]],
    *,
    target_artifact: str,
) -> dict[str, Any]:
    if target_artifact == "interface_specifications.json" or not obligations:
        return {"materialized_count": 0, "materialized_rows": [], "required_field_delta": False}
    row_key = _artifact_design_row_key(target_artifact, payload)
    existing_rows = [dict(row) for row in list(payload.get(row_key, []) or []) if isinstance(row, Mapping)]
    incoming: list[dict[str, Any]] = []
    for index, obligation in enumerate(obligations, start=1):
        if str(obligation.get("target_artifact", "") or target_artifact) != target_artifact:
            continue
        source_row = _design_obligation_source_row(obligation, design_rows)
        incoming.append(
            _design_row_for_artifact(
                target_artifact=target_artifact,
                obligation=obligation,
                source_row=source_row,
                index=index,
            )
        )
    if not incoming:
        return {"materialized_count": 0, "materialized_rows": [], "required_field_delta": False}
    merged_rows, changed = _merge_design_rows(existing_rows, incoming, target_artifact=target_artifact)
    payload[row_key] = merged_rows
    materialized_ids = [
        str(row.get("item_id", "") or row.get("fixture_id", "") or row.get("control_id", "") or row.get("row_id", "") or "")
        for row in incoming
        if str(row.get("item_id", "") or row.get("fixture_id", "") or row.get("control_id", "") or row.get("row_id", "") or "")
    ]
    payload["technology_design_materialized_rows"] = list(dict.fromkeys(materialized_ids))
    payload["technology_design_materialized_artifact"] = target_artifact
    payload["research_design_readiness_state"] = "research_design_ready"
    payload["hardware_build_ready"] = False
    payload["grants_execution_authority"] = False
    return {
        "materialized_count": len(incoming),
        "materialized_rows": list(dict.fromkeys(materialized_ids)),
        "materialized_artifact": target_artifact,
        "required_field_delta": changed,
    }


def _merge_existing_interface_artifact_rows(
    payload: dict[str, Any],
    artifact_path: Path,
) -> None:
    if not artifact_path.exists():
        return
    try:
        existing_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(existing_payload, Mapping):
        return
    existing_rows = [
        dict(row)
        for row in list(existing_payload.get("interfaces", []) or existing_payload.get("rows", []) or [])
        if isinstance(row, Mapping)
    ]
    if not existing_rows:
        return
    current_rows = [
        dict(row)
        for row in list(payload.get("interfaces", []) or [])
        if isinstance(row, Mapping)
    ]
    current_ids = {
        str(row.get("interface_id", "") or row.get("row_id", "") or "").strip()
        for row in current_rows
    }
    for row in existing_rows:
        row_id = str(row.get("interface_id", "") or row.get("row_id", "") or "").strip()
        if row_id and row_id not in current_ids:
            current_rows.append(row)
            current_ids.add(row_id)
    payload["interfaces"] = current_rows


def _merge_existing_json_artifact_rows(
    payload: dict[str, Any],
    artifact_path: Path,
    *,
    artifact_name: str,
) -> None:
    if not artifact_path.exists():
        return
    try:
        existing_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(existing_payload, Mapping):
        return
    row_key = _artifact_design_row_key(artifact_name, payload)
    existing_row_key = _artifact_design_row_key(artifact_name, existing_payload)
    existing_rows = [
        dict(row)
        for row in list(existing_payload.get(existing_row_key, []) or [])
        if isinstance(row, Mapping)
    ]
    if not existing_rows:
        return
    current_rows = [
        dict(row)
        for row in list(payload.get(row_key, []) or [])
        if isinstance(row, Mapping)
    ]
    current_identities: set[str] = set()
    for row in current_rows:
        current_identities.update(_row_identity_candidates(row))
    for row in existing_rows:
        row_identities = _row_identity_candidates(row)
        if row_identities and any(identity in current_identities for identity in row_identities):
            continue
        current_rows.append(row)
        current_identities.update(row_identities)
    payload[row_key] = current_rows


def _normalized_interface_field(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    aliases = {
        "latency": "latency_budget",
        "isolation": "electrical_isolation",
        "fixture": "validation_fixture_ref",
        "fixture_ref": "validation_fixture_ref",
        "risk": "linked_risk_control_ref",
        "risk_ref": "linked_risk_control_ref",
        "manifest": "device_capability_manifest_ref",
        "hal": "hardware_abstraction_layer_id",
        "validation": "validation_hooks",
        "validation_hook": "validation_hooks",
        "bom": "bom_ref",
        "bom_refs": "bom_ref",
    }
    return aliases.get(text, text)


def _interface_missing_row_targets_from_context(
    *,
    work_order: Mapping[str, Any],
    target_artifact: str,
    existing_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []

    def add_target(row_id: Any, fields: Any) -> None:
        target_id = re.sub(r"[^a-z0-9]+", "_", str(row_id or "").lower()).strip("_")
        if not target_id:
            return
        missing_fields = [
            _normalized_interface_field(field)
            for field in list(fields or [])
            if _normalized_interface_field(field)
        ]
        if any(str(item.get("row_id", "") or "") == target_id for item in targets):
            for item in targets:
                if str(item.get("row_id", "") or "") == target_id:
                    existing = list(item.get("missing_fields", []) or [])
                    for field in missing_fields:
                        if field not in existing:
                            existing.append(field)
                    item["missing_fields"] = existing
            return
        targets.append({"row_id": target_id, "missing_fields": missing_fields})

    for item in list(work_order.get("depth_missing_fields", []) or []):
        if not isinstance(item, Mapping):
            continue
        artifact = str(item.get("artifact", "") or item.get("artifact_name", "") or target_artifact)
        if artifact != target_artifact:
            continue
        add_target(
            item.get("row_id", "")
            or item.get("interface_id", "")
            or item.get("target_row_id", ""),
            item.get("missing_fields", []) or item.get("fields", []),
        )
    gaps = work_order.get("operator_feedback_obligation_gaps", {})
    if isinstance(gaps, Mapping):
        gap_rows = list(gaps.get(target_artifact, []) or [])
    else:
        gap_rows = list(gaps or [])
    for gap in gap_rows:
        if not isinstance(gap, Mapping):
            continue
        artifact = str(gap.get("artifact_name", "") or gap.get("artifact", "") or target_artifact)
        if artifact != target_artifact:
            continue
        add_target(
            gap.get("row_id", "") or gap.get("target_row_id", "") or gap.get("interface_id", ""),
            [gap.get("field", "")],
        )
    for row in existing_rows:
        if not isinstance(row, Mapping):
            continue
        row_id = str(row.get("interface_id", "") or row.get("row_id", "") or "").strip()
        if not row_id:
            continue
        missing_fields = [
            field
            for field in INTERFACE_MATERIALIZED_REQUIRED_FIELDS
            if not str(row.get(field, "") or "").strip()
        ]
        if missing_fields and (
            row_id.startswith("non_invasive_hal_")
            or row_id.endswith("_contract")
            or "contract" in row_id
        ):
            add_target(row_id, missing_fields)
    return targets


def _interface_target_ids_for_support_row(
    row: Mapping[str, Any],
    *,
    interface: Mapping[str, Any],
    existing_by_id: Mapping[str, Mapping[str, Any]],
    missing_targets: list[dict[str, Any]],
    design_row_count: int,
) -> list[str]:
    explicit = str(
        row.get("target_row_id", "")
        or row.get("target_interface_id", "")
        or row.get("interface_id", "")
        or row.get("target_interface_group", "")
        or row.get("interface_group", "")
        or ""
    ).strip()
    if explicit:
        return [re.sub(r"[^a-z0-9]+", "_", explicit.lower()).strip("_")]
    row_id = str(row.get("row_id", "") or row.get("support_row_id", "") or "").strip()
    normalized_row_id = re.sub(r"[^a-z0-9]+", "_", row_id.lower()).strip("_")
    if normalized_row_id and normalized_row_id in existing_by_id:
        return [normalized_row_id]
    covered_fields = {
        _normalized_interface_field(field)
        for field in list(row.get("covered_fields", []) or [])
        if _normalized_interface_field(field)
    }
    for field in INTERFACE_MATERIALIZED_REQUIRED_FIELDS:
        if str(interface.get(field, "") or "").strip():
            covered_fields.add(_normalized_interface_field(field))
    matching_targets: list[str] = []
    for target in missing_targets:
        target_id = str(target.get("row_id", "") or "").strip()
        missing_fields = {
            _normalized_interface_field(field)
            for field in list(target.get("missing_fields", []) or [])
            if _normalized_interface_field(field)
        }
        if target_id and (not missing_fields or covered_fields.intersection(missing_fields)):
            matching_targets.append(target_id)
    if matching_targets:
        return list(dict.fromkeys(matching_targets))
    if normalized_row_id and design_row_count == 1 and not missing_targets:
        return [normalized_row_id]
    current_id = str(interface.get("interface_id", "") or "").strip()
    return [current_id] if current_id else ["support_completed_interface_contract"]


def _materialize_technology_design_interface_rows(
    payload: dict[str, Any],
    design_rows: list[dict[str, Any]],
    *,
    target_artifact: str,
    work_order: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if target_artifact != "interface_specifications.json" or not design_rows:
        return {"materialized_count": 0, "materialized_fields": []}
    concrete_rows: list[dict[str, Any]] = []
    materialized_fields: list[str] = []
    materialized_required_fields: list[str] = []
    changed_required_fields: list[str] = []
    required_field_set = set(INTERFACE_MATERIALIZED_REQUIRED_FIELDS)
    existing = [row for row in list(payload.get("interfaces", []) or []) if isinstance(row, Mapping)]
    existing_by_id = {
        str(row.get("interface_id", "") or row.get("row_id", "") or "").strip(): dict(row)
        for row in existing
        if str(row.get("interface_id", "") or row.get("row_id", "") or "").strip()
    }
    missing_targets = _interface_missing_row_targets_from_context(
        work_order=work_order or {},
        target_artifact=target_artifact,
        existing_rows=existing,
    )
    missing_target_ids = {
        str(item.get("row_id", "") or "").strip()
        for item in missing_targets
        if str(item.get("row_id", "") or "").strip()
    }
    resolved_target_ids: set[str] = set()
    for index, row in enumerate(design_rows, start=1):
        interface = _interface_row_from_design_support(row, index)
        row_id = str(row.get("row_id", "") or row.get("support_row_id", "") or "").strip()
        target_ids = _interface_target_ids_for_support_row(
            row,
            interface=interface,
            existing_by_id=existing_by_id,
            missing_targets=missing_targets,
            design_row_count=len(design_rows),
        )
        if (
            str(interface.get("interface_id", "") or "") == "support_completed_interface_contract"
            and row_id
            and not missing_targets
            and (row_id in existing_by_id or len(design_rows) == 1)
        ):
            interface["interface_id"] = row_id
        populated = [
            field
            for field in INTERFACE_MATERIALIZED_REQUIRED_FIELDS
            if str(interface.get(field, "") or "").strip()
        ]
        if not populated:
            continue
        materialized_fields.extend(populated)
        materialized_required_fields.extend(field for field in populated if field in required_field_set)
        for target_id in target_ids:
            targeted = dict(interface)
            targeted["interface_id"] = target_id
            if target_id in missing_target_ids:
                resolved_target_ids.add(target_id)
            concrete_rows.append(targeted)
    if not concrete_rows:
        return {"materialized_count": 0, "materialized_fields": []}
    concrete_rows = _merge_interface_support_rows(concrete_rows)
    materialized_fields = [
        field
        for row in concrete_rows
        for field in INTERFACE_MATERIALIZED_REQUIRED_FIELDS
        if str(row.get(field, "") or "").strip()
    ]
    materialized_required_fields = [field for field in materialized_fields if field in required_field_set]
    merged_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for concrete in concrete_rows:
        interface_id = str(concrete.get("interface_id", "") or "")
        base = existing_by_id.get(interface_id, {})
        for field in INTERFACE_MATERIALIZED_REQUIRED_FIELDS:
            new_value = concrete.get(field, "")
            if str(new_value or "").strip() and new_value != base.get(field):
                changed_required_fields.append(field)
        merged = {**base, **{key: value for key, value in concrete.items() if value not in ("", [], {})}}
        merged_rows.append(merged)
        seen.add(interface_id)
    for row in existing:
        interface_id = str(row.get("interface_id", "") or row.get("row_id", "") or "").strip()
        if interface_id not in seen:
            has_required_field = any(
                str(row.get(field, "") or "").strip()
                for field in INTERFACE_MATERIALIZED_REQUIRED_FIELDS
            )
            if has_required_field:
                merged_rows.append(dict(row))
    payload["interfaces"] = merged_rows
    payload["technology_design_materialized_interface_rows"] = len(concrete_rows)
    payload["technology_design_materialized_fields"] = sorted(set(materialized_fields))
    missing_required = [
        field
        for field in INTERFACE_MATERIALIZED_REQUIRED_FIELDS
        if field not in set(materialized_required_fields)
    ]
    unresolved_target_ids = sorted(missing_target_ids.difference(resolved_target_ids))
    payload["technology_design_materialized_required_fields"] = sorted(set(materialized_required_fields))
    payload["technology_design_materialized_missing_fields"] = missing_required
    payload["support_target_row_resolution_state"] = (
        "resolved" if missing_target_ids and not unresolved_target_ids else "unresolved" if unresolved_target_ids else "not_applicable"
    )
    payload["support_resolved_target_row_ids"] = sorted(resolved_target_ids)
    payload["support_unresolved_target_row_ids"] = unresolved_target_ids
    return {
        "materialized_count": len(concrete_rows),
        "materialized_fields": sorted(set(materialized_fields)),
        "materialized_required_fields": sorted(set(materialized_required_fields)),
        "materialized_missing_fields": missing_required,
        "support_completed_required_fields": sorted(set(materialized_required_fields)),
        "support_still_missing_required_fields": missing_required,
        "support_row_completion_state": "complete" if not missing_required else "partial",
        "required_field_delta": bool(changed_required_fields),
        "changed_required_fields": sorted(set(changed_required_fields)),
        "support_target_row_resolution_state": payload["support_target_row_resolution_state"],
        "support_resolved_target_row_ids": sorted(resolved_target_ids),
        "support_unresolved_target_row_ids": unresolved_target_ids,
    }


def _apply_technology_design_obligation_artifact(
    payload: dict[str, Any],
    *,
    target_artifact: str,
    work_order: Mapping[str, Any],
    support_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    design_rows = _technology_design_rows_from_support_manifest(
        support_manifest,
        target_artifact=target_artifact,
    )
    design_mode = str(work_order.get("technology_design_mode", "") or "").strip()
    if not design_mode and not design_rows:
        return {}
    obligations = _technology_design_obligations_from_context(
        work_order,
        design_rows,
        target_artifact=target_artifact,
    )
    if not obligations:
        return {}
    materialized_interface = _materialize_technology_design_interface_rows(
        payload,
        design_rows,
        target_artifact=target_artifact,
        work_order=work_order,
    )
    materialized_design_rows = _materialize_technology_design_rows_for_target_artifact(
        payload,
        design_rows,
        obligations,
        target_artifact=target_artifact,
    )
    brief = dict(work_order.get("r_and_d_design_brief", {}) or {})
    brief_id = str(
        brief.get("r_and_d_design_brief_id", "")
        or next((row.get("r_and_d_design_brief_id", "") for row in design_rows if row.get("r_and_d_design_brief_id")), "")
        or ""
    )
    hypotheses = []
    validation_plan = []
    for index, obligation in enumerate(obligations, start=1):
        fields = [str(item) for item in list(obligation.get("fields", []) or []) if str(item).strip()]
        field_label = ", ".join(fields) or str(obligation.get("field", "") or f"design_field_{index}")
        evidence_ref = str(obligation.get("evidence_ref", "") or f"technology_design_obligation:{index}")
        hypotheses.append(
            {
                "hypothesis_id": f"design_hypothesis_{index}",
                "technology_design_obligation_id": str(
                    obligation.get("technology_design_obligation_id", "") or ""
                ),
                "target_fields": fields,
                "claim": (
                    str(obligation.get("claim", "") or "")
                    or f"{field_label} requires an explicit R&D design before it can become build evidence."
                ),
                "proposed_design_path": (
                    "Define architecture, constraints, measurable interfaces, validation hooks, and failure "
                    "criteria before selecting build parts."
                ),
                "evidence_ref": evidence_ref,
                "source_url": str(obligation.get("source_url", "") or ""),
                "grants_execution_authority": False,
            }
        )
        validation_plan.append(
            {
                "validation_id": f"design_validation_{index}",
                "target_fields": fields,
                "method": "simulation or synthetic bench review before hardware build claims",
                "acceptance_threshold": "field obligation reduced to source-backed part/spec/fixture/risk evidence",
                "blocks_hardware_build_ready": True,
                "evidence_ref": evidence_ref,
                "grants_execution_authority": False,
            }
        )
    payload["technology_design_obligations"] = obligations
    payload["engineering_hypotheses"] = hypotheses
    payload["technology_design_validation_plan"] = validation_plan
    payload["research_design_readiness_state"] = "research_design_ready"
    payload["r_and_d_design_brief_id"] = brief_id
    payload["hardware_build_ready"] = False
    payload["grants_execution_authority"] = False
    return {
        "technology_design_obligation_active": True,
        "technology_design_obligation_ids": [
            str(item.get("technology_design_obligation_id", "") or "")
            for item in obligations
            if str(item.get("technology_design_obligation_id", "") or "").strip()
        ],
        "r_and_d_design_brief_id": brief_id,
        "research_design_readiness_state": "research_design_ready",
        "hardware_build_ready_blocked_by_design_obligation": True,
        "hardware_build_packet_ready_candidate": False,
        "technical_depth_contract_passed": False,
        "strict_hardware_contract_passed": False,
        "technology_design_materialized_interface_rows": int(
            materialized_interface.get("materialized_count", 0) or 0
        ),
        "technology_design_materialized_artifact_rows": int(
            materialized_design_rows.get("materialized_count", 0) or 0
        ),
        "technology_design_materialized_artifact": str(
            materialized_design_rows.get("materialized_artifact", "") or ""
        ),
        "technology_design_materialized_rows": list(
            materialized_design_rows.get("materialized_rows", []) or []
        ),
        "technology_design_materialized_fields": list(
            materialized_interface.get("materialized_fields", []) or []
        ),
        "support_materialized_interface_row_count": int(
            materialized_interface.get("materialized_count", 0) or 0
        ),
        "support_completed_interface_row_count": int(
            materialized_interface.get("materialized_count", 0) or 0
        ),
        "support_materialized_interface_fields": list(
            materialized_interface.get("materialized_fields", []) or []
        ),
        "support_materialized_interface_required_field_count": len(
            list(materialized_interface.get("materialized_required_fields", []) or [])
        ),
        "support_materialized_interface_missing_fields": list(
            materialized_interface.get("materialized_missing_fields", []) or []
        ),
        "support_completed_required_fields": list(
            materialized_interface.get("support_completed_required_fields", []) or []
        ),
        "support_still_missing_required_fields": list(
            materialized_interface.get("support_still_missing_required_fields", []) or []
        ),
        "support_row_completion_state": str(
            materialized_interface.get("support_row_completion_state", "")
            or "no_matching_rows"
        ),
        "support_target_row_resolution_state": str(
            materialized_interface.get("support_target_row_resolution_state", "")
            or "not_applicable"
        ),
        "support_resolved_target_row_ids": list(
            materialized_interface.get("support_resolved_target_row_ids", []) or []
        ),
        "support_unresolved_target_row_ids": list(
            materialized_interface.get("support_unresolved_target_row_ids", []) or []
        ),
        "support_to_artifact_required_field_delta": bool(
            materialized_interface.get("required_field_delta", False)
            or materialized_design_rows.get("required_field_delta", False)
        ),
        "support_to_artifact_delta": bool(
            materialized_interface.get("required_field_delta", False)
            or materialized_design_rows.get("required_field_delta", False)
        ),
        "remaining_failed_gates": ["technology_design_obligation_not_reduced_to_build_evidence"],
        "hardware_readiness_blockers": ["technology_design_obligation_not_reduced_to_build_evidence"],
    }


def _depth_missing_fields_for_target(
    *,
    checkout: Mapping[str, Any],
    work_order: Mapping[str, Any],
    metrics: Mapping[str, Any],
    target_artifact: str,
) -> list[str]:
    target = str(target_artifact or "").strip()
    fields: list[str] = []

    def _add(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                _add(item)
            return
        text = str(value or "").strip()
        if text and text not in fields:
            fields.append(text)

    def _consume_gap(gap: Any) -> None:
        if not isinstance(gap, Mapping):
            return
        artifact = str(gap.get("artifact") or gap.get("artifact_name") or gap.get("target_artifact") or "").strip()
        if target and artifact and artifact != target:
            return
        _add(gap.get("missing_fields") or gap.get("fields"))
        _add(gap.get("field"))

    for source in (work_order, checkout):
        for key in ("depth_missing_fields", "missing_field_coverage", "support_uncovered_missing_fields"):
            for gap in list(source.get(key, []) or []):
                if isinstance(gap, Mapping):
                    _consume_gap(gap)
                else:
                    _add(gap)
        _add(source.get("missing_fields"))
        _add(source.get("required_fields"))
    for gap in list(metrics.get("operator_feedback_obligation_gaps", []) or []):
        if isinstance(gap, Mapping):
            artifact = str(gap.get("artifact_name") or gap.get("artifact") or "").strip()
            if target and artifact and artifact != target:
                continue
            if str(gap.get("gap_kind", "") or "").endswith("_missing") or gap.get("field"):
                _add(gap.get("field"))
    for gap in list(metrics.get("hardware_readiness_blockers", []) or []):
        if isinstance(gap, Mapping):
            _consume_gap(gap)
    if not fields:
        for field in SUPPORT_ADEQUACY_REQUIRED_FIELDS_BY_ARTIFACT.get(target, ()):
            _add(field)
    return fields


def _artifact_row_lists(payload: Any) -> list[list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        return []
    lists: list[list[dict[str, Any]]] = []
    for key in (
        "items",
        "components",
        "rows",
        "interfaces",
        "fixtures",
        "controls",
        "dependencies",
        "assembly_steps",
        "milestones",
        "protocols",
        "claims",
        "subsystems",
    ):
        values = payload.get(key, [])
        if isinstance(values, list):
            dict_rows = [item for item in values if isinstance(item, dict)]
            if dict_rows:
                lists.append(dict_rows)
    return lists


def _annotate_artifact_with_support_refs(
    path: Path,
    *,
    support_manifest: Mapping[str, Any],
    pass_count: int,
) -> dict[str, int]:
    pack_ids = _support_manifest_pack_ids(support_manifest)
    if not pack_ids or not path.exists() or path.suffix.lower() != ".json":
        return {"artifact_rows_generated": 0, "artifact_rows_revised": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"artifact_rows_generated": 0, "artifact_rows_revised": 0}
    row_lists = _artifact_row_lists(payload)
    revised = 0
    row_index = 0
    for row_list in row_lists:
        for row in row_list:
            row_index += 1
            existing_refs = [str(item) for item in list(row.get("support_pack_refs_used", []) or []) if str(item).strip()]
            if not existing_refs:
                row["support_pack_refs_used"] = pack_ids[:3]
                row["support_pack_row_refs"] = [f"{pack_ids[0]}#row_{row_index}"]
                revised += 1
    if revised:
        payload["child_local_depth_worker"] = {
            "compute_pass_count": int(pass_count),
            "support_pack_refs_used": pack_ids[:3],
            "row_level_support_refs_applied": revised,
            "grants_execution_authority": False,
        }
        _write_json_artifact(path, payload)
    generated = row_index if row_index and revised == row_index else 0
    return {"artifact_rows_generated": generated, "artifact_rows_revised": revised}


def _local_child_compute_policy(checkout: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(checkout.get("child_compute_mode", "") or "single_pass").strip() or "single_pass"
    try:
        budget_seconds = max(1.0, min(float(checkout.get("child_compute_budget_seconds", 45) or 45), 300.0))
    except (TypeError, ValueError):
        budget_seconds = 45.0
    try:
        max_passes = max(1, min(int(checkout.get("child_compute_max_passes", 1) or 1), 8))
    except (TypeError, ValueError):
        max_passes = 1
    return {
        "child_compute_mode": mode,
        "child_compute_budget_seconds": budget_seconds,
        "child_compute_max_passes": max_passes,
        "child_compute_sleep_when_blocked": bool(checkout.get("child_compute_sleep_when_blocked", True)),
    }


def _log_child_compute_phase(child_run_id: str, phase: str, **fields: Any) -> None:
    if os.environ.get("NOVALI_CONVEYOR_CHILD") != "1":
        return
    payload = {
        "event": "child_compute_phase",
        "child_run_id": child_run_id,
        "phase": phase,
        **fields,
    }
    print(json.dumps(payload, sort_keys=True, default=str), flush=True)


def _write_child_phase_heartbeat(
    progress_root: Path,
    *,
    child_run_id: str,
    directive_id: str,
    cycle_index: int,
    target_artifact: str,
    phase: str,
    phase_event: str,
) -> None:
    generated_at = _utc_now()
    _write_json_artifact(
        progress_root / "progress_phase_heartbeat.json",
        {
            "schema_name": "ConveyorResidentChildPhaseHeartbeat",
            "schema_version": "conveyor_resident_child_phase_heartbeat_v1",
            "generated_at": generated_at,
            "last_heartbeat_at": generated_at,
            "child_run_id": child_run_id,
            "directive_id": directive_id,
            "cycle_index": int(cycle_index),
            "target_artifact": target_artifact,
            "last_compute_phase": phase,
            "phase_event": phase_event,
            "progress_checkpoint": "progress_latest.json",
            "grants_execution_authority": False,
        },
    )


def _write_resident_startup_progress_checkpoint(
    progress_root: Path,
    *,
    child_run_id: str,
    directive_id: str,
    cycle_index: int,
    target_artifact: str,
    phase: str,
) -> dict[str, Any]:
    generated_at = _utc_now()
    checkpoint = {
        "schema_name": "ConveyorResidentChildProgressCheckpoint",
        "schema_version": "conveyor_resident_child_progress_checkpoint_v2",
        "generated_at": generated_at,
        "child_run_id": child_run_id,
        "directive_id": directive_id,
        "child_execution_mode": "resident_campaign",
        "progress_state": "working",
        "cycle_index": int(cycle_index),
        "cycle_outcome": "synthesis_in_progress",
        "target_artifact": target_artifact,
        "current_step": "revise_" + re.sub(r"[^a-z0-9]+", "_", target_artifact.lower()).strip("_"),
        "last_compute_phase": phase,
        "compute_phase_sequence": [phase],
        "artifact_deltas": [],
        "artifact_delta_count": 0,
        "artifact_delta_names": [],
        "meaningful_delta": False,
        "support_to_artifact_delta": False,
        "support_to_artifact_required_field_delta": False,
        "compute_budget_exhausted": False,
        "resident_self_final_return_eligible": False,
        "hardware_build_packet_ready_candidate": False,
        "technical_depth_contract_passed": False,
        "strict_hardware_contract_passed": False,
        "remaining_failed_gates": ["artifact_synthesis_in_progress"],
        "child_activity_state": "generating",
        "grants_execution_authority": False,
    }
    _write_json_artifact(progress_root / "progress_latest.json", checkpoint)
    _write_json_artifact(
        progress_root / "progress_heartbeat.json",
        {
            "schema_name": "ConveyorResidentChildProgressHeartbeat",
            "schema_version": "conveyor_resident_child_progress_heartbeat_v1",
            "generated_at": generated_at,
            "last_progress_at": generated_at,
            "last_heartbeat_at": generated_at,
            "child_run_id": child_run_id,
            "directive_id": directive_id,
            "cycle_index": int(cycle_index),
            "target_artifact": target_artifact,
            "progress_checkpoint": "progress_latest.json",
            "progress_checkpoint_hash": _checkpoint_hash(checkpoint),
            "compute_budget_exhausted": False,
            "meaningful_delta": False,
            "support_to_artifact_required_field_delta": False,
            "grants_execution_authority": False,
        },
    )
    return checkpoint


def _write_json_artifact(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload if payload.endswith("\n") else payload + "\n", encoding="utf-8")
        return
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _checkpoint_hash(payload: Mapping[str, Any]) -> str:
    body = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _apply_schema_resonance_followup_contract(
    payload: dict[str, Any],
    work_order: dict[str, Any],
) -> dict[str, Any]:
    if not (
        bool(work_order.get("schema_resonance_followup_required", False))
        or bool(work_order.get("persistent_schema_contract_required", False))
    ):
        return {}
    required_fields = [
        str(item).strip()
        for item in list(work_order.get("required_top_level_fields", []) or work_order.get("missing_top_level_fields", []) or [])
        if str(item).strip()
    ]
    skeleton = work_order.get("artifact_top_level_schema_skeleton", {})
    if not required_fields or not isinstance(skeleton, dict):
        return {
            "schema_followup_contract_materialized": False,
            "schema_followup_materialized_top_level_fields": [],
            "schema_followup_missing_top_level_fields_after_write": required_fields,
            "closed_failed_gates": [],
            "remaining_failed_gates": ["schema_resonance_followup_top_level_fields_missing"] if required_fields else [],
        }
    materialized: list[str] = []
    for field in required_fields:
        if field not in payload and field in skeleton:
            payload[field] = skeleton[field]
            materialized.append(field)
    missing_after = [field for field in required_fields if field not in payload]
    satisfied = bool(required_fields and not missing_after)
    if satisfied:
        payload["schema_followup_contract_materialized"] = True
        payload["schema_followup_materialized_top_level_fields"] = required_fields
        payload["schema_followup_missing_top_level_fields_after_write"] = []
    return {
        "schema_followup_contract_materialized": satisfied,
        "schema_followup_materialized_top_level_fields": [
            field for field in required_fields if field not in missing_after
        ],
        "schema_followup_missing_top_level_fields_after_write": missing_after,
        "closed_failed_gates": ["schema_resonance_followup_top_level_fields_missing"] if satisfied else [],
        "remaining_failed_gates": ["schema_resonance_followup_top_level_fields_missing"] if not satisfied else [],
    }


def _apply_field_level_output_contract(
    artifacts: dict[str, dict[str, Any]],
    *,
    title: str,
    work_order: dict[str, Any],
) -> dict[str, Any]:
    contract = work_order.get("field_level_output_contract", {})
    if not isinstance(contract, dict) or not contract:
        return {}
    skeleton = contract.get("skeleton", {})
    if not isinstance(skeleton, dict):
        return {}
    skeleton_id = str(work_order.get("schema_skeleton_id", "") or "")
    target_artifact = str(work_order.get("target_artifact", "") or contract.get("target_artifact", "") or "")
    required_gates = [
        str(gate)
        for gate in list(work_order.get("required_gate_closures", []) or [])
        if str(gate).strip()
    ]
    def indexed_ref(refs: list[Any], index: int, fallback: str) -> str:
        if refs:
            return str(refs[(index - 1) % len(refs)] or fallback)
        return fallback
    def artifact_row_id(ref: Any) -> str:
        return str(ref or "").replace(":", "_")
    def fixture_row_id(ref: Any) -> str:
        return str(ref or "").split(":", 1)[-1]

    if skeleton_id == "full_dive_hardware_interface_cluster_v1":
        hal_id = str(skeleton.get("hardware_abstraction_layer_id", "") or "non_invasive_hal_v1")
        boundary = str(skeleton.get("non_invasive_boundary", "") or "non-invasive read-only hardware abstraction")
        manifest_ref = str(
            skeleton.get("device_capability_manifest_ref", "")
            or f"device_capability_manifest:{hal_id}"
        )
        thresholds = list(skeleton.get("acceptance_thresholds", []) or [])
        dependency_refs = list(skeleton.get("dependency_refs", []) or [])
        bom_refs = list(skeleton.get("bom_refs", []) or [])
        risk_refs = list(skeleton.get("risk_gate_refs", []) or [])
        fixture_refs = list(skeleton.get("validation_fixture_refs", []) or [])
        artifacts["interface_specifications.json"] = {
            "schema_name": "ConveyorInterfaceSpecifications",
            "directive_title": title,
            "interfaces": [
                {
                    "interface_id": "non_invasive_hal_input_contract",
                    "name": "Non-invasive Hardware Abstraction Input Contract",
                    "hardware_abstraction_layer_id": hal_id,
                    "non_invasive_boundary": boundary,
                    "device_capability_manifest_ref": manifest_ref,
                    "producer": "non_invasive_device_adapter",
                    "consumer": "simulation_runtime_core",
                    "inputs": {"device_capability_manifest.v1": ["device_class", "non_invasive", "declared_channels"]},
                    "outputs": {"bounded_control_intent.v1": ["intent_id", "normalized_axes", "safety_stop"]},
                    "failure_modes": ["invasive_capability_declared", "latency_budget_exceeded", "manifest_missing"],
                    "validation_hooks": fixture_refs,
                    "dependency_refs": dependency_refs,
                    "bom_refs": bom_refs,
                    "risk_gate_refs": risk_refs,
                    "acceptance_thresholds": thresholds,
                    "execution_gate": "operator_review_required_before_real_world_use",
                },
                {
                    "interface_id": "non_invasive_hal_safety_gate_contract",
                    "name": "Non-invasive HAL Safety Gate Contract",
                    "hardware_abstraction_layer_id": hal_id,
                    "non_invasive_boundary": boundary,
                    "device_capability_manifest_ref": manifest_ref,
                    "producer": "hardware_interface_guard",
                    "consumer": "operator_review_gate",
                    "inputs": {"hardware_capability_request.v1": ["capability_id", "invasive", "stimulation", "actuation"]},
                    "outputs": {"governance_gate_record.v1": ["allowed", "blocked_reason", "threshold_result"]},
                    "failure_modes": ["unsafe_capability_requested", "operator_gate_missing"],
                    "validation_hooks": fixture_refs,
                    "dependency_refs": dependency_refs,
                    "bom_refs": bom_refs,
                    "risk_gate_refs": risk_refs,
                    "acceptance_thresholds": thresholds,
                    "execution_gate": "operator_review_required_before_real_world_use",
                },
            ],
            "field_level_contract_applied": True,
            "schema_skeleton_id": skeleton_id,
        }
        artifacts["dependency_matrix.json"] = {
            "schema_name": "ConveyorDependencyMatrix",
            "directive_title": title,
            "dependencies": [
                {
                    "dependency_id": ref.replace(":", "_"),
                    "name": ref,
                    "hardware_abstraction_layer_id": hal_id,
                    "needed_for": "non-invasive HAL prototype closure",
                    "source": "kernel field-level plateau recovery contract",
                    "risk_if_missing": "hardware/interface cluster cannot be validated against the same HAL boundary",
                    "device_capability_manifest_ref": manifest_ref,
                    "acceptance_thresholds": thresholds,
                }
                for ref in dependency_refs
            ],
            "field_level_contract_applied": True,
            "schema_skeleton_id": skeleton_id,
        }
        artifacts["bill_of_materials.json"] = {
            "schema_name": "ConveyorBillOfMaterials",
            "directive_title": title,
            "items": [
                {
                    "item_id": str(ref).replace(":", "_"),
                    "name": ref,
                    "category": "non_invasive_interface_fixture",
                    "quantity": 1,
                    "measurable_spec": {
                        "review_boundary": boundary,
                        "acceptance": "all listed non-invasive HAL thresholds must pass",
                    },
                    "required_for": "non-invasive HAL prototype closure",
                    "hardware_abstraction_layer_id": hal_id,
                    "device_capability_manifest_ref": manifest_ref,
                    "source_assumption": "offline simulation fixture or operator-approved safe adapter",
                    "substitution_allowed": True,
                    "test_equipment": ["synthetic replay harness", "go/no-go trace recorder"],
                    "risk_if_missing": f"{ref} cannot be validated against the non-invasive HAL boundary",
                    "linked_risk_control_ref": artifact_row_id(
                        indexed_ref(risk_refs, index, f"{artifact_row_id(ref)}_risk_control")
                    ),
                    "validation_fixture_ref": fixture_row_id(
                        indexed_ref(fixture_refs, index, f"{artifact_row_id(ref)}_fixture")
                    ),
                    "acceptance_thresholds": thresholds,
                    "execution_gate": "operator_review_required_before_real_world_use",
                }
                for index, ref in enumerate(bom_refs, start=1)
            ],
            "field_level_contract_applied": True,
            "schema_skeleton_id": skeleton_id,
        }
        artifacts["risk_controls.json"] = {
            "schema_name": "ConveyorRiskControls",
            "directive_title": title,
            "controls": [
                {
                    "control_id": ref.replace(":", "_"),
                    "hazard_id": f"{ref.replace(':', '_')}_hazard",
                    "failure_mode": "unsafe or invasive interface request escapes the HAL boundary",
                    "effect": "prototype review could imply real-world authority that has not been approved",
                    "severity": "high",
                    "occurrence": "low_with_operator_gate",
                    "detectability": "high_with_go_no_go_trace",
                    "applies_to": hal_id,
                    "hardware_abstraction_layer_id": hal_id,
                    "risk": "unsafe, invasive, stimulation, actuation, or real-world interface request",
                    "mitigation": boundary,
                    "device_capability_manifest_ref": manifest_ref,
                    "go_no_go_criteria": {"threshold": "100% unsafe requests rejected"},
                    "verification_fixture_ref": fixture_row_id(
                        indexed_ref(fixture_refs, index, f"{ref.replace(':', '_')}_fixture")
                    ),
                    "linked_bom_ref": artifact_row_id(
                        indexed_ref(bom_refs, index, f"{ref.replace(':', '_')}_bom_item")
                    ),
                    "acceptance_thresholds": thresholds,
                    "execution_gate": "operator_review_required_before_real_world_use",
                }
                for index, ref in enumerate(risk_refs, start=1)
            ],
            "field_level_contract_applied": True,
            "schema_skeleton_id": skeleton_id,
        }
        artifacts["validation_fixtures.json"] = {
            "schema_name": "ConveyorValidationFixtures",
            "directive_title": title,
            "fixtures": [
                {
                    "fixture_id": ref.split(":", 1)[-1],
                    "hardware_abstraction_layer_id": hal_id,
                    "purpose": "Validate non-invasive HAL field-level closure",
                    "setup": "Replay synthetic device capability manifests through the HAL guard.",
                    "expected_file": f"fixtures/full_dive/{ref.split(':', 1)[-1]}.json",
                    "expected_files": [f"fixtures/full_dive/{ref.split(':', 1)[-1]}.json"],
                    "expected_outputs": ["governance_gate_record.v1", "bounded_control_intent.v1"],
                    "go_no_go_trace": f"fixtures/full_dive/{ref.split(':', 1)[-1]}_go_no_go_trace.json",
                    "device_capability_manifest_ref": manifest_ref,
                    "linked_bom_refs": [
                        artifact_row_id(indexed_ref(bom_refs, index, f"{ref.split(':', 1)[-1]}_bom_item"))
                    ],
                    "linked_risk_control_refs": [
                        artifact_row_id(indexed_ref(risk_refs, index, f"{ref.split(':', 1)[-1]}_risk_control"))
                    ],
                    "acceptance_thresholds": thresholds,
                    "execution_gate": "operator_review_required_before_real_world_use",
                }
                for index, ref in enumerate(fixture_refs, start=1)
            ],
            "field_level_contract_applied": True,
            "schema_skeleton_id": skeleton_id,
        }
    elif skeleton_id == "grin_robotics_fixture_closure_v1":
        fixtures = [
            dict(item)
            for item in list(skeleton.get("scenario_fixtures", []) or [])
            if isinstance(item, dict)
        ]
        artifacts["prototype_assembly_plan.json"] = {
            "schema_name": "ConveyorPrototypeAssemblyPlan",
            "directive_title": title,
            "assembly_steps": [
                {
                    "step_id": f"assembly_{index}",
                    "name": f"Run {fixture.get('scenario_fixture_id', f'robotics_scenario_{index}')} prototype fixture",
                    "description": "Validate a scenario-specific non-clinical robotics interaction fixture before review.",
                    "build_sequence": index,
                    "validation_fixture": str(fixture.get("scenario_fixture_id", f"robotics_scenario_{index}")),
                    "robotics_interaction_flow": list(fixture.get("robotics_interaction_flow", []) or []),
                    "operator_role": str(fixture.get("operator_role", "")),
                    "customer_role": str(fixture.get("customer_role", "")),
                    "expected_files": list(fixture.get("expected_files", []) or []),
                    "expected_outputs": list(fixture.get("expected_outputs", []) or []),
                    "go_no_go_trace": str(fixture.get("go_no_go_trace", "")),
                    "non_clinical_governance_gate": str(fixture.get("non_clinical_governance_gate", "")),
                    "go_no_go_criteria": [
                        {
                            "criterion": "scenario fixture threshold",
                            "threshold": str(threshold.get("threshold", "100%")),
                            "metric": str(threshold.get("metric", "fixture pass rate")),
                        }
                        for threshold in list(fixture.get("acceptance_thresholds", []) or [])
                        if isinstance(threshold, dict)
                    ],
                    "acceptance_thresholds": list(fixture.get("acceptance_thresholds", []) or []),
                    "execution_gate": "operator_review_required_before_real_world_use",
                }
                for index, fixture in enumerate(fixtures, start=1)
            ],
            "field_level_contract_applied": True,
            "schema_skeleton_id": skeleton_id,
        }
        artifacts["validation_fixtures.json"] = {
            "schema_name": "ConveyorValidationFixtures",
            "directive_title": title,
            "fixtures": [
                {
                    "fixture_id": str(fixture.get("scenario_fixture_id", f"robotics_scenario_{index}")),
                    "purpose": "Scenario-specific robotics interaction validation",
                    "setup": "Replay a non-clinical tabletop interaction scenario.",
                    "robotics_interaction_flow": list(fixture.get("robotics_interaction_flow", []) or []),
                    "operator_role": str(fixture.get("operator_role", "")),
                    "customer_role": str(fixture.get("customer_role", "")),
                    "expected_files": list(fixture.get("expected_files", []) or []),
                    "expected_outputs": list(fixture.get("expected_outputs", []) or []),
                    "go_no_go_trace": str(fixture.get("go_no_go_trace", "")),
                    "non_clinical_governance_gate": str(fixture.get("non_clinical_governance_gate", "")),
                    "acceptance_thresholds": list(fixture.get("acceptance_thresholds", []) or []),
                    "execution_gate": "operator_review_required_before_real_world_use",
                }
                for index, fixture in enumerate(fixtures, start=1)
            ],
            "field_level_contract_applied": True,
            "schema_skeleton_id": skeleton_id,
        }
    else:
        return {}
    return {
        "field_level_contract_applied": bool(artifacts.get(target_artifact, {}).get("field_level_contract_applied")),
        "schema_skeleton_id": skeleton_id,
        "closed_failed_gates": [gate for gate in required_gates if gate != "draft_delta_plateau"],
        "remaining_failed_gates": [],
    }


def _hardware_bench_contract_rows(
    title: str,
    *,
    source_ref: str = "",
    operator_feedback: str = "",
) -> dict[str, list[dict[str, Any]]]:
    lowered = str(title or "").lower()
    source = str(source_ref or "").strip()
    if "magnetic forge" in lowered or "forge" in lowered:
        components = [
            ("forge_enclosure", "thermal chamber / forge envelope", "review-only forge bench boundary"),
            ("ceramic_liner", "ceramic liner and thermal insulation stack", "contain thermal test envelope"),
            ("coil_field_module", "electromagnetic coil / field subsystem", "field generation bench interface"),
            ("cooling_quench_loop", "cooling and quench loop", "thermal runaway and cooldown validation"),
            ("sensor_array", "temperature, current, and field sensor array", "bench telemetry and calibration"),
            ("safety_interlock_controller", "operator stop and interlock controller", "hard stop before energized tests"),
        ]
    else:
        components = [
            ("bench_fixture_frame", "operator-approved hardware bench fixture", "physical bench boundary"),
            ("device_capability_manifest", "device capability manifest and calibration record", "device/HAL contract"),
            ("sensor_adapter", "sensor adapter or read-only input harness", "bounded hardware input"),
            ("power_interlock", "power and operator-stop interlock", "energized-step safety gate"),
        ]
    interfaces = []
    bom_items = []
    fixtures = []
    controls = []

    def selected_bench_source(component_id: str) -> dict[str, Any]:
        component = str(component_id or "")
        if "safety" in component or "interlock" in component or "power_interlock" in component:
            source_row = {
                "manufacturer": "Omron",
                "mpn": "G9SE-201",
                "datasheet_url": "https://assets.omron.eu/downloads/datasheet/en/v6/g9se_safety_relay_unit_datasheet_en.pdf",
                "unit_cost": "budgetary catalog basis 165 USD class",
                "electrical_rating": "24 VDC safety relay module class",
                "compliance_notes": "IEC 61508/SIL supplier claims require operator review before bench execution",
                "connector": "pluggable 24 VDC safety terminal block",
            }
        elif "sensor" in component or "adapter" in component or "interface" in component:
            source_row = {
                "manufacturer": "Texas Instruments",
                "mpn": "DRV5055A1QLPGM",
                "datasheet_url": "https://www.ti.com/lit/ds/symlink/drv5055.pdf",
                "unit_cost": "budgetary catalog basis 45 USD class",
                "electrical_rating": "ratiometric analog Hall-effect magnetic sensor, 3.3/5 V bench interface class",
                "compliance_notes": "magnetic field sensing row only; thermal, current, and coolant sensors require separate source-backed rows before energized bench execution",
                "connector": "3-pin low-voltage isolated bench header",
            }
        elif "coil" in component or "field" in component:
            source_row = {
                "manufacturer": "AEC Magnetics",
                "mpn": "DCA-100-24C",
                "datasheet_url": "https://www.aecmagnetics.com/dca-series",
                "unit_cost": "budgetary catalog basis 75 USD class",
                "electrical_rating": "24 VDC bench electromagnet class, operator-measured current and field strength required",
                "compliance_notes": "bench electromagnet source requires operator validation of field strength, duty cycle, thermal rise, and guarded power switching before energized execution",
                "connector": "Phoenix Contact MC 1,5/4-ST-3,81 pluggable terminal",
            }
        elif "ceramic" in component or "liner" in component or "insulation" in component:
            source_row = {
                "manufacturer": "Cotronics",
                "mpn": "Rescor 960",
                "datasheet_url": "https://www.cotronics.com/catalog/55%20%20960.pdf",
                "unit_cost": "budgetary catalog basis 35 USD class for small machinable alumina stock",
                "electrical_rating": "96% alumina machinable ceramic, high-temperature electrical/thermal insulation stock",
                "compliance_notes": "material safety, machining dust, and supplier certificate require operator review before bench execution",
                "connector": "non-conductive ceramic standoff or mechanically retained liner interface",
            }
        elif "cooling" in component or "quench" in component or "cooldown" in component:
            source_row = {
                "manufacturer": "Koolance",
                "mpn": "PMP-400",
                "datasheet_url": "https://koolance.com/comparison-pumps",
                "unit_cost": "budgetary catalog basis 85 USD class",
                "electrical_rating": "8-13.2 VDC brushless pump, 20 W class, 7.5 L/min maximum flow class",
                "compliance_notes": "coolant compatibility, leak containment, and electrical isolation require operator review before energized bench execution",
                "connector": "3-pin fan/tach lead plus 10 mm ID coolant hose interface",
            }
        else:
            source_row = {
                "manufacturer": "Misumi",
                "mpn": "HFS5-2020-300",
                "datasheet_url": "https://us.misumi-ec.com/vona2/detail/110302684350/",
                "unit_cost": "budgetary catalog basis 8 USD class",
                "electrical_rating": "non-energized mechanical fixture member",
                "compliance_notes": "mechanical fixture material and supplier certificate require operator review",
                "connector": "bolted fixture interface with labeled isolated harness routing",
            }
        rejection = source_rejected_by_operator_feedback(
            operator_feedback,
            component_id=component,
            source_row=source_row,
        )
        if bool(rejection.get("rejected", False)):
            return {
                "manufacturer": "operator-feedback source replacement required",
                "mpn": "operator-feedback replacement required",
                "datasheet_url": "trusted-source-or-operator-supplied-datasheet-required",
                "unit_cost": "operator/source quote required",
                "electrical_rating": "operator-approved measurable spec required",
                "compliance_notes": "source rejected by operator feedback; child must use support pack or core-mediated synthesis before build-ready review",
                "connector": "fixture-defined; must be recorded in electrical_interface_spec.json",
                "operator_feedback_replacement_required": True,
                "operator_feedback_forbidden_terms": list(rejection.get("matched_terms", []) or []),
            }
        return source_row

    for index, (component_id, name, required_for) in enumerate(components, start=1):
        source_row = selected_bench_source(component_id)
        risk_control_ref = f"{component_id}_safety_control"
        fixture_ref = f"{component_id}_bench_fixture"
        interfaces.append(
            {
                "interface_id": f"{component_id}_interface",
                "hardware_or_device_interface_id": component_id,
                "name": f"{name} interface",
                "producer": component_id,
                "consumer": "operator_review_bench_harness",
                "hardware_abstraction_layer_id": "non_human_synthetic_bench_hal_v1",
                "device_capability_manifest_ref": f"device_capability_manifest:{component_id}",
                "connector": source_row["connector"],
                "pinout": {"pin_1": "isolated_signal_or_fixture_input", "pin_2": "isolated_reference", "pin_3": "safety_stop"},
                "protocol": "read_only_fixture_contract_v1",
                "signal_level": "0-3.3 V isolated logic, <=2 mA input current" if source else "low-energy isolated review signal; exact volts require operator-approved datasheet",
                "sample_rate": "1 kS/s logged synthetic/non-human bench stream" if source else "fixture-defined; must be recorded in bench_test_protocol.json",
                "bandwidth": "DC-100 Hz review-only bench signal path" if source else "fixture-defined; must be recorded in electrical_interface_spec.json",
                "latency_budget": "p95 <= 20ms for synthetic/non-human interface replay",
                "electrical_isolation": "medical-grade isolation required before any human-adjacent review",
                "safety_limit": "no stimulation, no invasive path, no ungated actuation",
                "failure_behavior": "fail closed with safety_stop asserted and operator review required",
                "source_ref": source,
                "support_pack_ref": source,
                "inputs": {"bench_state.v1": ["operator_enable", "calibration_state", "safety_stop"]},
                "outputs": {"bench_observation.v1": ["measurement", "status", "go_no_go"]},
                "failure_modes": ["calibration_missing", "operator_stop_asserted", "threshold_exceeded"],
                "validation_hooks": [f"fixtures/hardware/{component_id}_bench_fixture.json"],
                "acceptance_thresholds": [
                    {"metric": "operator-stop response", "threshold": "100% stop requests honored"},
                    {"metric": "calibration manifest coverage", "threshold": "100% required fields present"},
                ],
                "execution_gate": "execution_gated_by_operator_approval",
            }
        )
        bom_items.append(
            {
                "item_id": component_id,
                "name": name,
                "category": "hardware_bench_component",
                "manufacturer": source_row["manufacturer"],
                "mpn": source_row["mpn"],
                "datasheet_url": source_row["datasheet_url"],
                "quantity": 1,
                "unit_cost": source_row["unit_cost"],
                "electrical_rating": source_row["electrical_rating"],
                "compliance_notes": source_row["compliance_notes"],
                "alternatives": ["operator-approved equivalent with matching isolation and safety ratings"],
                "measurable_spec": {
                    "review_boundary": "synthetic/non-human bench interface only; no human subject or ungated actuator path",
                    "acceptance": "all listed go/no-go thresholds must pass",
                },
                "source_ref": source,
                "support_pack_ref": source,
                "required_for": required_for,
                "source_assumption": f"{source_row['manufacturer']} {source_row['mpn']} datasheet and budgetary catalog basis recorded on this row",
                "substitution_allowed": True,
                "test_equipment": ["operator-approved measurement fixture", "go/no-go trace recorder"],
                "risk_if_missing": f"{required_for} cannot be validated for review-gated bench readiness",
                "linked_risk_control_ref": risk_control_ref,
                "validation_fixture_ref": fixture_ref,
                "safety_review_required": True,
                "execution_gate": "execution_gated_by_operator_approval",
                "operator_feedback_replacement_required": bool(
                    source_row.get("operator_feedback_replacement_required", False)
                ),
                "operator_feedback_forbidden_terms": list(
                    source_row.get("operator_feedback_forbidden_terms", []) or []
                ),
            }
        )
        fixtures.append(
            {
                "fixture_id": f"{component_id}_bench_fixture",
                "purpose": f"Validate {name} before any operator-approved real-world bench step.",
                "setup": "Use disconnected or low-energy bench review configuration until operator approval is recorded.",
                "equipment": ["isolated measurement interface", "safety-stop recorder", "calibrated synthetic signal source"],
                "fixture_wiring": "pinout and isolation wiring must match electrical_interface_spec.json",
                "calibration_steps": [
                    "record device capability manifest",
                    "verify isolation boundary",
                    "run synthetic/non-human signal replay",
                ],
                "measurement_method": "capture go/no-go trace and compare all acceptance thresholds",
                "pass_fail_thresholds": ["fixture pass rate 100%", "unsafe bypass count 0"],
                "expected_file": f"fixtures/hardware/{component_id}_bench_fixture.json",
                "expected_files": [
                    f"fixtures/hardware/{component_id}_bench_fixture.json",
                    f"fixtures/hardware/{component_id}_go_no_go_trace.json",
                ],
                "expected_outputs": ["bench_observation.v1", "governance_gate_record.v1"],
                "go_no_go_trace": f"fixtures/hardware/{component_id}_go_no_go_trace.json",
                "linked_bom_refs": [component_id],
                "linked_risk_control_refs": [risk_control_ref],
                "acceptance_thresholds": [
                    {"metric": "fixture pass rate", "threshold": "100%"},
                    {"metric": "unsafe bypass count", "threshold": "0"},
                ],
                "execution_gate": "execution_gated_by_operator_approval",
            }
        )
        controls.append(
            {
                "control_id": f"{component_id}_safety_control",
                "hazard_id": f"{component_id}_hazard",
                "failure_mode": "unsafe, ungated, or uncalibrated bench operation",
                "effect": "operator could not validate review-only bench readiness safely",
                "severity": "high",
                "occurrence": "low_with_operator_gate",
                "detectability": "high_with_fixture_trace",
                "detection": "go/no-go trace plus operator preflight review",
                "rpn": "24",
                "applies_to": component_id,
                "risk": "power, thermal, electrical, privacy, or operator-stop failure during hardware bench evaluation",
                "mitigation": "require operator approval, calibration manifest, low-energy setup where applicable, and stop/interlock trace",
                "residual_risk": "not acceptable for human-subject use without external safety/regulatory review",
                "standard_ref": "IEC 60601 and ISO 14971 applicability review required",
                "verification_method": "bench_test_protocol.json fixture execution and safety_case.json review",
                "go_no_go_criteria": {"threshold": "0 unsafe or ungated bench steps allowed"},
                "verification_fixture_ref": fixture_ref,
                "linked_bom_ref": component_id,
                "source_ref": source,
                "execution_gate": "execution_gated_by_operator_approval",
            }
        )
    return {
        "interfaces": interfaces,
        "bom_items": bom_items,
        "fixtures": fixtures,
        "controls": controls,
        "device_capability_manifest": {
            "schema_name": "ConveyorDeviceCapabilityManifest",
            "directive_title": title,
            "manifest_id": "magnetic_forge_bench_v1" if ("magnetic forge" in lowered or "forge" in lowered) else "review_only_hardware_bench_v1",
            "device_class": "review_only_hardware_bench",
            "declared_channels": ["operator_enable", "calibration_state", "safety_stop", "bench_observation"],
            "calibration_profile": {
                "required": True,
                "method": "operator-approved bench calibration before any physical execution",
            },
            "prohibited_capabilities": [
                "human_subject_use",
                "clinical_use",
                "ungated_energized_operation",
                "real_world_actuation_without_operator_approval",
            ],
            "privacy_class": "non-sensitive synthetic or operator-approved bench telemetry only",
            "execution_gated_by_operator_approval": True,
            "grants_execution_authority": False,
        },
    }


def _normalize_materialized_role(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\brows?\b", "", text)
    text = re.sub(r"\brole\b", "", text)
    normalized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    aliases = {
        "daq": "daq_logging",
        "logging": "daq_logging",
        "data_acquisition": "daq_logging",
        "magnetic_field": "gaussmeter",
        "magnetic_field_gaussmeter": "gaussmeter",
        "hall_sensor": "gaussmeter",
        "field_sensor": "gaussmeter",
        "temperature": "thermal",
        "temperature_sensor": "thermal",
        "thermal_sensor": "thermal",
        "current_sensor": "current",
        "coolant_sensor": "coolant",
        "flow_sensor": "coolant",
    }
    return aliases.get(normalized, normalized)


def _role_tokens_from_support_row(row: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in (
        "target_role",
        "role",
        "required_for",
        "category",
        "function",
        "subsystem",
        "row_id",
        "item_id",
        "name",
        "claim",
    ):
        normalized = _normalize_materialized_role(row.get(field, ""))
        if normalized:
            tokens.add(normalized)
        for part in normalized.split("_"):
            part_normalized = _normalize_materialized_role(part)
            if part_normalized:
                tokens.add(part_normalized)
    return tokens


def _support_row_matches_split_role(
    row: Mapping[str, Any],
    *,
    target_artifact: str,
    role: str,
) -> bool:
    row_target = str(row.get("target_artifact", "") or "").strip()
    if row_target and row_target != target_artifact:
        return False
    normalized_role = _normalize_materialized_role(role)
    return bool(normalized_role and normalized_role in _role_tokens_from_support_row(row))


def _support_row_has_role_split_required_fields(row: Mapping[str, Any]) -> bool:
    specs = _support_row_spec_values(row)

    def has_value(*keys: str) -> bool:
        if _first_support_value(specs, *keys):
            return True
        for key in keys:
            for source in (specs, row):
                value = source.get(key, "") if isinstance(source, Mapping) else ""
                if isinstance(value, (list, tuple, set)) and any(str(item).strip() for item in value):
                    return True
                if isinstance(value, Mapping) and any(str(item).strip() for item in value.values()):
                    return True
                if str(value or "").strip():
                    return True
        return False

    return all(
        (
            has_value("manufacturer", "supplier"),
            has_value("mpn", "part_number"),
            has_value("datasheet_url", "source_url", "citation_ref"),
            has_value("electrical_rating", "rating", "measurable_spec"),
            has_value("quantity", "qty"),
            has_value("unit_cost", "cost_basis", "cost"),
            has_value("validation_fixture_ref", "fixture_ref", "fixture"),
            has_value("linked_risk_control_ref", "risk_ref", "risk"),
            has_value("standards_assumption", "standards", "compliance_notes"),
            has_value("go_no_go_trace", "go_no_go_ref", "pass_fail_trace"),
            has_value("alternatives", "alternate", "substitutes"),
            has_value("measurable_spec", "measurement_spec", "spec"),
            has_value("substitution_allowed", "substitution"),
            has_value("test_equipment", "equipment"),
            has_value("risk_if_missing", "missing_risk"),
        )
    )


def _artifact_row_already_materializes_split_role(
    row: Mapping[str, Any],
    *,
    base_role: str,
    role: str,
) -> bool:
    normalized_base = _normalize_materialized_role(base_role)
    normalized_role = _normalize_materialized_role(role)
    if not normalized_role:
        return False
    identity_text = " ".join(
        str(row.get(field, "") or "")
        for field in ("item_id", "row_id", "id", "name")
    )
    identity = _normalize_materialized_role(identity_text)
    expected = f"{normalized_base}_{normalized_role}" if normalized_base else normalized_role
    if identity == expected or identity.startswith(f"{expected}_"):
        return True
    role_text = " ".join(
        str(row.get(field, "") or "")
        for field in ("role", "required_for", "category", "function", "subsystem")
    )
    normalized_role_text = _normalize_materialized_role(role_text)
    return bool(
        normalized_base
        and normalized_base in identity
        and (
            normalized_role_text == normalized_role
            or normalized_role_text.startswith(f"{normalized_role}_")
        )
    )


def _role_lane_for_artifact_row(row: Mapping[str, Any]) -> str:
    for field in ("target_role", "role", "required_for", "category", "function", "subsystem", "item_id", "row_id", "id", "name"):
        lane = normalize_support_role_lane(row.get(field, ""))
        if lane:
            return lane
    return ""


def _role_lane_for_support_row(row: Mapping[str, Any], *, fallback_role: str = "") -> str:
    for field in ("target_role", "role", "required_for", "category", "function", "subsystem"):
        lane = normalize_support_role_lane(row.get(field, ""))
        if lane:
            return lane
    return normalize_support_role_lane(fallback_role)


def _row_identity_candidates(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for field in (
        "item_id",
        "row_id",
        "id",
        "name",
        "target_row_id",
        "requested_row_id",
        "design_artifact_row_id",
        "closes_target_row_id",
        "closes_requested_row_id",
    ):
        value = _clean_support_row_identity(row.get(field))
        if value:
            values.append(value)
    return list(dict.fromkeys(values))


def _split_role_row_from_support(
    *,
    base_role: str,
    role: str,
    support_row: Mapping[str, Any],
) -> dict[str, Any]:
    specs = _support_row_spec_values(support_row)
    normalized_base = _normalize_materialized_role(base_role) or "role_split"
    normalized_role = _normalize_materialized_role(role) or "role"
    row_id = str(
        support_row.get("target_row_id", "")
        or support_row.get("item_id", "")
        or support_row.get("row_id", "")
        or f"{normalized_base}_{normalized_role}"
    ).strip()
    row_id = re.sub(r"[^a-z0-9_]+", "_", row_id.lower()).strip("_") or f"{normalized_base}_{normalized_role}"
    if normalized_base and normalized_role and normalized_role not in row_id:
        row_id = f"{normalized_base}_{normalized_role}"
    canonical_role = _role_lane_for_support_row(support_row, fallback_role=role)
    source_ref = str(support_row.get("source_url", "") or support_row.get("citation_ref", "") or "").strip()
    evidence_ref = str(support_row.get("evidence_ref", "") or "").strip()
    requested_row_id = _clean_support_row_identity(support_row.get("requested_row_id"))
    target_row_id = _clean_support_row_identity(support_row.get("target_row_id"))
    support_row_id = _clean_support_row_identity(support_row.get("row_id"))
    cost_basis = _first_support_value(specs, "cost_basis", "unit_cost", "cost") or str(
        support_row.get("cost_basis", "") or support_row.get("unit_cost", "") or support_row.get("cost", "") or ""
    ).strip()
    standards_assumption = _first_support_value(specs, "standards_assumption", "standards", "compliance_notes") or str(
        support_row.get("standards_assumption", "")
        or support_row.get("standards", "")
        or support_row.get("compliance_notes", "")
        or "operator review required before bench execution"
    ).strip()
    return {
        "item_id": row_id,
        "name": str(support_row.get("name", "") or f"{normalized_role.replace('_', ' ')} split row"),
        "category": normalized_role,
        "target_role": canonical_role or normalized_role,
        "required_for": f"{normalized_base}_{normalized_role}",
        "manufacturer": _first_support_value(specs, "manufacturer", "supplier")
        or str(support_row.get("manufacturer", "") or support_row.get("supplier", "") or "").strip(),
        "mpn": _first_support_value(specs, "mpn", "part_number")
        or str(support_row.get("mpn", "") or support_row.get("part_number", "") or "").strip(),
        "datasheet_url": _first_support_value(specs, "datasheet_url", "source_url", "citation_ref")
        or str(support_row.get("datasheet_url", "") or source_ref).strip(),
        "quantity": support_row.get("quantity", 1) or 1,
        "unit_cost": _first_support_value(specs, "unit_cost", "cost_basis", "cost")
        or str(support_row.get("unit_cost", "") or support_row.get("cost_basis", "") or "budgetary source basis required"),
        "cost_basis": cost_basis or "budgetary source basis required",
        "electrical_rating": _first_support_value(specs, "electrical_rating", "rating", "measurable_spec")
        or str(support_row.get("electrical_rating", "") or support_row.get("measurable_spec", "") or ""),
        "standards_assumption": standards_assumption,
        "compliance_notes": standards_assumption,
        "connector": _first_support_value(specs, "connector", "interface_connector"),
        "alternatives": _design_list_value(specs, support_row, "alternatives", "alternate", "substitutes"),
        "measurable_spec": _first_support_value(specs, "measurable_spec", "measurement_spec", "spec"),
        "source_assumption": _first_support_value(
            specs,
            "source_assumption",
            "standards_assumption",
            "standards",
            "compliance_notes",
        ),
        "substitution_allowed": _first_support_value(specs, "substitution_allowed", "substitution"),
        "test_equipment": _first_support_value(specs, "test_equipment", "equipment"),
        "risk_if_missing": _first_support_value(specs, "risk_if_missing", "missing_risk"),
        "validation_fixture_ref": _first_support_value(specs, "validation_fixture_ref", "fixture_ref", "fixture"),
        "linked_risk_control_ref": _first_support_value(specs, "linked_risk_control_ref", "risk_ref", "risk"),
        "go_no_go_trace": _first_support_value(specs, "go_no_go_trace", "go_no_go_ref", "pass_fail_trace"),
        "requested_row_id": requested_row_id,
        "target_row_id": target_row_id,
        "closes_requested_row_id": requested_row_id,
        "closes_target_row_id": target_row_id,
        "support_row_ids": [
            str(item)
            for item in (
                support_row.get("support_pack_id", ""),
                support_row_id,
                requested_row_id,
                target_row_id,
            )
            if str(item).strip()
        ],
        "evidence_refs": [item for item in (evidence_ref, source_ref) if item],
        "source_url": source_ref,
        "execution_gate": "execution_gated_by_operator_approval",
        "grants_execution_authority": False,
    }


def _clean_support_row_identity(value: Any) -> str:
    text = str(value or "").strip()
    if not text or "redacted" in text.lower():
        return ""
    return _slug(text, "")


def _bom_row_from_source_support(
    support_row: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    specs = _support_row_spec_values(support_row)
    target_row_id = _clean_support_row_identity(support_row.get("target_row_id"))
    design_artifact_row_id = _clean_support_row_identity(support_row.get("design_artifact_row_id"))
    requested_row_id = _clean_support_row_identity(support_row.get("requested_row_id"))
    support_row_id = _clean_support_row_identity(support_row.get("row_id"))
    row_id = (
        target_row_id
        or design_artifact_row_id
        or requested_row_id
        or support_row_id
        or f"source_backed_bom_support_{index}"
    )
    source_ref = str(support_row.get("source_url", "") or support_row.get("citation_ref", "") or "").strip()
    evidence_ref = str(support_row.get("evidence_ref", "") or "").strip()
    support_refs, evidence_refs = _support_row_refs(support_row)
    if source_ref and source_ref not in evidence_refs:
        evidence_refs.append(source_ref)
    if evidence_ref and evidence_ref not in evidence_refs:
        evidence_refs.append(evidence_ref)
    cost_basis = _first_support_value(specs, "cost_basis", "unit_cost", "cost")
    standards_assumption = _first_support_value(specs, "standards_assumption", "standards", "compliance_notes")
    closure_refs = [
        value
        for value in (requested_row_id, target_row_id, design_artifact_row_id, support_row_id)
        if value
    ]
    row = {
        "item_id": row_id,
        "name": _first_support_value(specs, "name", "component_name")
        or str(support_row.get("claim", "") or f"{row_id.replace('_', ' ')} source-backed BOM row")[:160],
        "category": _first_support_value(specs, "category") or "source_backed_component_evidence",
        "target_role": _role_lane_for_support_row(support_row),
        "required_for": _first_support_value(specs, "required_for", "subsystem")
        or "source_backed_build_depth_reduction",
        "manufacturer": _first_support_value(specs, "manufacturer", "supplier"),
        "mpn": _first_support_value(specs, "mpn", "part_number"),
        "datasheet_url": _first_support_value(specs, "datasheet_url", "source_url", "citation_ref") or source_ref,
        "quantity": _first_support_value(specs, "quantity", "qty") or 1,
        "unit_cost": _first_support_value(specs, "unit_cost", "cost_basis", "cost")
        or "budgetary source basis required",
        "cost_basis": cost_basis or "budgetary source basis required",
        "electrical_rating": _first_support_value(specs, "electrical_rating", "rating", "measurable_spec"),
        "standards_assumption": standards_assumption or "operator-reviewed bench instrumentation boundary",
        "compliance_notes": standards_assumption or "operator-reviewed bench instrumentation boundary",
        "alternatives": _design_list_value(specs, support_row, "alternatives", "alternate", "substitutes"),
        "measurable_spec": _first_support_value(specs, "measurable_spec", "measurement_spec", "spec"),
        "substitution_allowed": _first_support_value(specs, "substitution_allowed", "substitution"),
        "test_equipment": _first_support_value(specs, "test_equipment", "equipment"),
        "risk_if_missing": _first_support_value(specs, "risk_if_missing", "missing_risk"),
        "validation_fixture_ref": _first_support_value(specs, "validation_fixture_ref", "fixture_ref", "fixture"),
        "linked_risk_control_ref": _first_support_value(specs, "linked_risk_control_ref", "risk_ref", "risk"),
        "go_no_go_trace": _first_support_value(specs, "go_no_go_trace", "go_no_go_ref", "pass_fail_trace"),
        "source_url": source_ref,
        "citation_ref": str(support_row.get("citation_ref", "") or ""),
        "support_row_ids": list(dict.fromkeys(support_refs + closure_refs)),
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "requested_row_id": requested_row_id,
        "target_row_id": target_row_id,
        "design_artifact_row_id": design_artifact_row_id,
        "closes_requested_row_id": requested_row_id,
        "closes_target_row_id": target_row_id or design_artifact_row_id,
        "closes_design_artifact_row_id": design_artifact_row_id,
        "source_backed_field_closure": True,
        "execution_gate": "execution_gated_by_operator_approval",
        "grants_execution_authority": False,
    }
    return {key: value for key, value in row.items() if value not in (None, "", [], {})}


def _source_support_row_has_bom_required_fields(row: Mapping[str, Any]) -> bool:
    specs = _support_row_spec_values(row)
    raw_specs = row.get("spec_values", {})
    if not isinstance(raw_specs, Mapping):
        raw_specs = {}

    def has_value(*keys: str) -> bool:
        if _first_support_value(specs, *keys):
            return True
        for key in keys:
            for source in (specs, raw_specs, row):
                value = source.get(key, "") if isinstance(source, Mapping) else ""
                if isinstance(value, (list, tuple, set)) and any(str(item).strip() for item in value):
                    return True
                if isinstance(value, Mapping) and any(str(item).strip() for item in value.values()):
                    return True
                if str(value or "").strip():
                    return True
        return False

    return all(
        (
            has_value("manufacturer", "supplier"),
            has_value("mpn", "part_number"),
            has_value("datasheet_url", "source_url", "citation_ref"),
            has_value("electrical_rating", "rating", "measurable_spec"),
            has_value("quantity", "qty"),
            has_value("unit_cost", "cost_basis", "cost"),
            has_value("validation_fixture_ref", "fixture_ref", "fixture"),
            has_value("linked_risk_control_ref", "risk_ref", "risk"),
            has_value("standards_assumption", "standards", "compliance_notes"),
            has_value("go_no_go_trace", "go_no_go_ref", "pass_fail_trace"),
            has_value("alternatives", "alternate", "substitutes"),
            has_value("measurable_spec", "measurement_spec", "spec"),
            has_value("substitution_allowed", "substitution"),
            has_value("test_equipment", "equipment"),
            has_value("risk_if_missing", "missing_risk"),
        )
    )


def _source_support_row_missing_bom_depth_fields(row: Mapping[str, Any]) -> list[str]:
    specs = _support_row_spec_values(row)
    raw_specs = row.get("spec_values", {})
    if not isinstance(raw_specs, Mapping):
        raw_specs = {}

    def has_value(*keys: str) -> bool:
        if _first_support_value(specs, *keys):
            return True
        for key in keys:
            for source in (specs, raw_specs, row):
                value = source.get(key, "") if isinstance(source, Mapping) else ""
                if isinstance(value, (list, tuple, set)) and any(str(item).strip() for item in value):
                    return True
                if isinstance(value, Mapping) and any(str(item).strip() for item in value.values()):
                    return True
                if str(value or "").strip():
                    return True
        return False

    depth_fields = {
        "alternatives": ("alternatives", "alternate", "substitutes"),
        "measurable_spec": ("measurable_spec", "measurement_spec", "spec"),
        "substitution_allowed": ("substitution_allowed", "substitution"),
        "test_equipment": ("test_equipment", "equipment"),
        "risk_if_missing": ("risk_if_missing", "missing_risk"),
    }
    return [field for field, aliases in depth_fields.items() if not has_value(*aliases)]


def _apply_source_backed_bom_support_materialization(
    artifacts: dict[str, dict[str, Any]],
    *,
    support_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    payload = artifacts.get("bill_of_materials.json")
    if not isinstance(payload, dict):
        return {"source_bom_materialization_state": "not_applicable", "source_bom_materialized_rows": []}
    row_key = _artifact_design_row_key("bill_of_materials.json", payload)
    existing_rows = [dict(row) for row in list(payload.get(row_key, []) or []) if isinstance(row, Mapping)]
    existing_rows_by_identity: dict[str, dict[str, Any]] = {}
    for existing_row in existing_rows:
        for identity in _row_identity_candidates(existing_row):
            existing_rows_by_identity.setdefault(identity, existing_row)
    incoming: list[dict[str, Any]] = []
    requested_row_ids: list[str] = []
    closed_requested_row_ids: list[str] = []
    unresolved_depth_fields: list[dict[str, Any]] = []
    for index, row in enumerate(_support_manifest_rows(support_manifest), start=1):
        if str(row.get("target_artifact", "") or "").strip() != "bill_of_materials.json":
            continue
        requested_row_id = _clean_support_row_identity(row.get("requested_row_id"))
        if requested_row_id:
            requested_row_ids.append(requested_row_id)
        target_row_id = _clean_support_row_identity(row.get("target_row_id"))
        support_lane = _role_lane_for_support_row(row)
        existing_target_row = existing_rows_by_identity.get(target_row_id) if target_row_id else None
        existing_lane = _role_lane_for_artifact_row(existing_target_row or {}) if existing_target_row else ""
        if existing_target_row and support_lane and existing_lane and existing_lane != support_lane:
            continue
        if not _source_support_row_has_bom_required_fields(row):
            continue
        materialized = _bom_row_from_source_support(row, index=index)
        incoming.append(materialized)
        if requested_row_id:
            closed_requested_row_ids.append(requested_row_id)
        missing_depth_fields = _source_support_row_missing_bom_depth_fields(row)
        if missing_depth_fields:
            unresolved_depth_fields.append(
                {
                    "artifact_name": "bill_of_materials.json",
                    "row_id": str(materialized.get("item_id", "") or requested_row_id or "").strip(),
                    "missing_fields": missing_depth_fields,
                }
            )
    if not incoming:
        unclosed = list(dict.fromkeys(requested_row_ids))
        return {
            "source_bom_materialization_state": "no_matching_source_rows",
            "source_bom_materialized_rows": [],
            "bom_field_closure_state": "no_matching_source_rows" if not unclosed else "incomplete",
            "bom_closed_requested_row_ids": [],
            "bom_unclosed_requested_row_ids": unclosed,
            "bom_closed_operator_feedback_gap_count": 0,
            "support_to_artifact_required_field_delta": False,
            "source_bom_unresolved_depth_fields": [],
        }
    merged_rows, changed = _merge_design_rows(existing_rows, incoming, target_artifact="bill_of_materials.json")
    payload[row_key] = merged_rows
    ids = [str(row.get("item_id", "") or "") for row in incoming if str(row.get("item_id", "") or "").strip()]
    closed_ids = list(dict.fromkeys(closed_requested_row_ids))
    unclosed_ids = [
        item
        for item in list(dict.fromkeys(requested_row_ids))
        if item not in set(closed_ids)
    ]
    payload["source_backed_support_materialized_rows"] = list(dict.fromkeys(ids))
    payload["source_backed_support_materialized"] = True
    payload["bom_closed_requested_row_ids"] = closed_ids
    payload["bom_unclosed_requested_row_ids"] = unclosed_ids
    return {
        "source_bom_materialization_state": "materialized",
        "source_bom_materialized_rows": list(dict.fromkeys(ids)),
        "source_bom_materialized_count": len(incoming),
        "source_bom_required_field_delta": changed,
        "bom_field_closure_state": "closed" if not unclosed_ids else "partial",
        "bom_closed_requested_row_ids": closed_ids,
        "bom_unclosed_requested_row_ids": unclosed_ids,
        "bom_closed_operator_feedback_gap_count": len(closed_ids),
        "support_to_artifact_required_field_delta": changed,
        "source_bom_unresolved_depth_fields": unresolved_depth_fields,
    }


def _risk_row_from_source_support(
    support_row: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    specs = _support_row_spec_values(support_row)
    target_row_id = _clean_support_row_identity(support_row.get("target_row_id"))
    requested_row_id = _clean_support_row_identity(support_row.get("requested_row_id"))
    support_row_id = _clean_support_row_identity(support_row.get("row_id"))
    control_id = (
        target_row_id
        or _clean_support_row_identity(_first_support_value(specs, "control_id", "hazard_id"))
        or requested_row_id
        or support_row_id
        or f"source_backed_risk_control_{index}"
    )
    source_ref = str(support_row.get("source_url", "") or support_row.get("citation_ref", "") or "").strip()
    evidence_ref = str(support_row.get("evidence_ref", "") or "").strip()
    support_refs, evidence_refs = _support_row_refs(support_row)
    for ref in (source_ref, evidence_ref, requested_row_id, target_row_id, support_row_id):
        if ref and ref not in evidence_refs:
            evidence_refs.append(ref)
    row = {
        "control_id": control_id,
        "hazard_id": _first_support_value(specs, "hazard_id") or control_id,
        "failure_mode": _first_support_value(specs, "failure_mode"),
        "effect": _first_support_value(specs, "effect"),
        "severity": _first_support_value(specs, "severity"),
        "occurrence": _first_support_value(specs, "occurrence"),
        "detectability": _first_support_value(specs, "detectability"),
        "detection": _first_support_value(specs, "detection", "detectability"),
        "rpn": _first_support_value(specs, "rpn", "risk_priority_number"),
        "mitigation": _first_support_value(specs, "mitigation"),
        "residual_risk": _first_support_value(specs, "residual_risk"),
        "standard_ref": _first_support_value(
            specs,
            "standard_ref",
            "regulatory_reference",
            "standard_regulatory_reference",
        ),
        "verification_method": _first_support_value(
            specs,
            "verification_method",
            "verification_fixture_ref",
            "validation_fixture_ref",
            "fixture_ref",
        ),
        "linked_bom_ref": _first_support_value(specs, "linked_bom_ref", "bom_ref"),
        "verification_fixture_ref": _first_support_value(
            specs,
            "verification_fixture_ref",
            "validation_fixture_ref",
            "fixture_ref",
        ),
        "go_no_go_criteria": _first_support_value(
            specs,
            "go_no_go_criteria",
            "go_no_go_trace",
            "pass_fail_thresholds",
        ),
        "source_url": source_ref,
        "citation_ref": str(support_row.get("citation_ref", "") or ""),
        "requested_row_id": requested_row_id,
        "target_row_id": target_row_id,
        "closes_requested_row_id": requested_row_id,
        "closes_target_row_id": target_row_id,
        "support_row_ids": list(dict.fromkeys(support_refs + [item for item in (requested_row_id, support_row_id) if item])),
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "execution_gate": "execution_gated_by_operator_approval",
        "grants_execution_authority": False,
    }
    return {key: value for key, value in row.items() if value not in (None, "", [], {})}


def _source_support_row_has_risk_required_fields(row: Mapping[str, Any]) -> bool:
    specs = _support_row_spec_values(row)

    def has_value(*keys: str) -> bool:
        if _first_support_value(specs, *keys):
            return True
        return any(str(row.get(key, "") or "").strip() for key in keys)

    return all(
        (
            has_value("hazard_id"),
            has_value("failure_mode"),
            has_value("effect"),
            has_value("severity"),
            has_value("occurrence"),
            has_value("detectability"),
            has_value("detection", "detectability"),
            has_value("rpn", "risk_priority_number"),
            has_value("mitigation"),
            has_value("residual_risk"),
            has_value("standard_ref", "regulatory_reference", "standard_regulatory_reference"),
            has_value("verification_method", "verification_fixture_ref", "validation_fixture_ref", "fixture_ref"),
            has_value("linked_bom_ref", "bom_ref"),
            has_value("verification_fixture_ref", "validation_fixture_ref", "fixture_ref"),
            has_value("go_no_go_criteria", "go_no_go_trace", "pass_fail_thresholds"),
            has_value("execution_gate"),
        )
    )


def _apply_source_backed_risk_support_materialization(
    artifacts: dict[str, dict[str, Any]],
    *,
    support_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    payload = artifacts.get("risk_controls.json")
    if not isinstance(payload, dict):
        return {"risk_control_materialization_state": "not_applicable", "risk_control_materialized_rows": []}
    incoming: list[dict[str, Any]] = []
    requested_row_ids: list[str] = []
    closed_requested_row_ids: list[str] = []
    for index, row in enumerate(_support_manifest_rows(support_manifest), start=1):
        if str(row.get("target_artifact", "") or "").strip() != "risk_controls.json":
            continue
        requested_row_id = _clean_support_row_identity(row.get("requested_row_id"))
        if requested_row_id:
            requested_row_ids.append(requested_row_id)
        if not _source_support_row_has_risk_required_fields(row):
            continue
        incoming.append(_risk_row_from_source_support(row, index=index))
        if requested_row_id:
            closed_requested_row_ids.append(requested_row_id)
    if not incoming:
        return {
            "risk_control_materialization_state": "no_matching_source_rows"
            if not requested_row_ids
            else "incomplete",
            "risk_control_materialized_rows": [],
            "missing_fmea_row_refs": list(dict.fromkeys(requested_row_ids)),
        }
    row_key = _artifact_design_row_key("risk_controls.json", payload)
    existing_rows = [dict(row) for row in list(payload.get(row_key, []) or []) if isinstance(row, Mapping)]
    merged_rows, changed = _merge_design_rows(existing_rows, incoming, target_artifact="risk_controls.json")
    payload[row_key] = merged_rows
    ids = [
        str(row.get("control_id", "") or row.get("hazard_id", "") or "")
        for row in incoming
        if str(row.get("control_id", "") or row.get("hazard_id", "") or "").strip()
    ]
    closed_ids = list(dict.fromkeys(closed_requested_row_ids))
    unclosed_ids = [
        item
        for item in list(dict.fromkeys(requested_row_ids))
        if item not in set(closed_ids)
    ]
    payload["source_backed_risk_materialized_rows"] = list(dict.fromkeys(ids))
    payload["source_backed_risk_materialized"] = True
    return {
        "risk_control_materialization_state": "materialized" if not unclosed_ids else "partial",
        "risk_control_materialized_rows": list(dict.fromkeys(ids)),
        "risk_control_materialized_count": len(incoming),
        "missing_fmea_row_refs": unclosed_ids,
        "risk_control_required_field_delta": changed,
        "support_to_artifact_required_field_delta": changed,
    }


def _source_support_row_has_validation_fixture_required_fields(row: Mapping[str, Any]) -> bool:
    specs = _support_row_spec_values(row)
    raw_specs = row.get("spec_values", {})
    if not isinstance(raw_specs, Mapping):
        raw_specs = {}

    def has_value(*keys: str) -> bool:
        if _first_support_value(specs, *keys):
            return True
        for key in keys:
            for source in (specs, raw_specs, row):
                value = source.get(key, "") if isinstance(source, Mapping) else ""
                if isinstance(value, (list, tuple, set)) and any(str(item).strip() for item in value):
                    return True
                if isinstance(value, Mapping) and any(str(item).strip() for item in value.values()):
                    return True
                if str(value or "").strip():
                    return True
        return False

    return all(
        (
            has_value("equipment"),
            has_value("fixture_wiring"),
            has_value("calibration_steps"),
            has_value("measurement_method"),
            has_value("pass_fail_thresholds", "go_no_go_criteria", "go_no_go_trace"),
            has_value("linked_bom_refs", "linked_bom_ref", "bom_ref"),
            has_value("linked_risk_control_refs", "linked_risk_control_ref", "risk_ref"),
            has_value("execution_gate"),
        )
    )


def _fixture_ref_tail(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.split("#")[-1].split(":")[-1].strip()
    return _slug(text, "")


def _fixture_list_value(specs: Mapping[str, str], row: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = row.get(key)
        raw_values = raw if isinstance(raw, (list, tuple, set)) else [raw]
        for item in raw_values:
            for part in re.split(r"[,;|]+", str(item or "")):
                text = part.strip()
                if text and text not in values:
                    values.append(text)
        spec = _first_support_value(specs, key)
        for part in re.split(r"[,;|]+", str(spec or "")):
            text = part.strip()
            if text and text not in values:
                values.append(text)
    return values


def _fixture_row_from_source_support(
    support_row: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    specs = _support_row_spec_values(support_row)
    target_row_id = _clean_support_row_identity(support_row.get("target_row_id"))
    target_row_tail = _fixture_ref_tail(support_row.get("target_row_id"))
    requested_row_id = _clean_support_row_identity(support_row.get("requested_row_id"))
    support_row_id = _clean_support_row_identity(support_row.get("row_id"))
    fixture_id = (
        target_row_tail
        or _fixture_ref_tail(_first_support_value(specs, "fixture_id", "validation_fixture_ref", "fixture_ref"))
        or requested_row_id
        or support_row_id
        or f"source_backed_validation_fixture_{index}"
    )
    source_ref = str(support_row.get("source_url", "") or support_row.get("citation_ref", "") or "").strip()
    evidence_ref = str(support_row.get("evidence_ref", "") or "").strip()
    support_refs, evidence_refs = _support_row_refs(support_row)
    for ref in (source_ref, evidence_ref, requested_row_id, target_row_id, support_row_id):
        if ref and ref not in evidence_refs:
            evidence_refs.append(ref)
    linked_bom_refs = _fixture_list_value(specs, support_row, "linked_bom_refs", "linked_bom_ref", "bom_ref")
    linked_risk_refs = _fixture_list_value(
        specs,
        support_row,
        "linked_risk_control_refs",
        "linked_risk_control_ref",
        "risk_ref",
    )
    expected_file = _first_support_value(specs, "expected_file", "fixture_file")
    expected_files = _fixture_list_value(specs, support_row, "expected_files", "expected_file", "fixture_file")
    go_no_go_trace = _first_support_value(specs, "go_no_go_trace", "go_no_go_ref", "pass_fail_trace")
    if not expected_file:
        expected_file = f"fixtures/{fixture_id}.json"
    if not go_no_go_trace:
        go_no_go_trace = f"fixtures/{fixture_id}_go_no_go_trace.json"
    if not expected_files:
        expected_files = [expected_file, go_no_go_trace]
    expected_outputs = _fixture_list_value(specs, support_row, "expected_outputs", "expected_output")
    if not expected_outputs:
        expected_outputs = list(expected_files)
    row = {
        "fixture_id": fixture_id,
        "name": _first_support_value(specs, "name") or fixture_id.replace("_", " "),
        "equipment": _first_support_value(specs, "equipment"),
        "fixture_wiring": _first_support_value(specs, "fixture_wiring"),
        "calibration_steps": _first_support_value(specs, "calibration_steps"),
        "measurement_method": _first_support_value(specs, "measurement_method"),
        "pass_fail_thresholds": _first_support_value(
            specs,
            "pass_fail_thresholds",
            "go_no_go_criteria",
            "go_no_go_trace",
        ),
        "expected_file": expected_file,
        "expected_files": expected_files,
        "expected_outputs": expected_outputs,
        "go_no_go_trace": go_no_go_trace,
        "linked_bom_refs": linked_bom_refs,
        "linked_risk_control_refs": linked_risk_refs,
        "source_url": source_ref,
        "citation_ref": str(support_row.get("citation_ref", "") or ""),
        "requested_row_id": requested_row_id,
        "target_row_id": str(support_row.get("target_row_id", "") or ""),
        "closes_requested_row_id": requested_row_id,
        "closes_target_row_id": str(support_row.get("target_row_id", "") or ""),
        "support_row_ids": list(dict.fromkeys(support_refs + [item for item in (requested_row_id, support_row_id) if item])),
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "execution_gate": _first_support_value(specs, "execution_gate")
        or "execution_gated_by_operator_approval",
        "grants_execution_authority": False,
    }
    return {key: value for key, value in row.items() if value not in (None, "", [], {})}


def _apply_source_backed_validation_fixture_support_materialization(
    artifacts: dict[str, dict[str, Any]],
    *,
    support_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    payload = artifacts.get("validation_fixtures.json")
    if not isinstance(payload, dict):
        return {
            "validation_fixture_materialization_state": "not_applicable",
            "validation_fixture_materialized_rows": [],
        }
    incoming: list[dict[str, Any]] = []
    requested_row_ids: list[str] = []
    closed_requested_row_ids: list[str] = []
    for index, row in enumerate(_support_manifest_rows(support_manifest), start=1):
        if str(row.get("target_artifact", "") or "").strip() != "validation_fixtures.json":
            continue
        requested_row_id = _clean_support_row_identity(row.get("requested_row_id"))
        if requested_row_id:
            requested_row_ids.append(requested_row_id)
        if not _source_support_row_has_validation_fixture_required_fields(row):
            continue
        incoming.append(_fixture_row_from_source_support(row, index=index))
        if requested_row_id:
            closed_requested_row_ids.append(requested_row_id)
    if not incoming:
        return {
            "validation_fixture_materialization_state": "no_matching_source_rows"
            if not requested_row_ids
            else "incomplete",
            "validation_fixture_materialized_rows": [],
            "missing_validation_fixture_requested_row_ids": list(dict.fromkeys(requested_row_ids)),
            "support_to_artifact_required_field_delta": False,
        }
    row_key = _artifact_design_row_key("validation_fixtures.json", payload)
    existing_rows = [dict(row) for row in list(payload.get(row_key, []) or []) if isinstance(row, Mapping)]
    merged_rows, changed = _merge_design_rows(existing_rows, incoming, target_artifact="validation_fixtures.json")
    payload[row_key] = merged_rows
    ids = [
        str(row.get("fixture_id", "") or "")
        for row in incoming
        if str(row.get("fixture_id", "") or "").strip()
    ]
    closed_ids = list(dict.fromkeys(closed_requested_row_ids))
    unclosed_ids = [
        item
        for item in list(dict.fromkeys(requested_row_ids))
        if item not in set(closed_ids)
    ]
    payload["source_backed_validation_fixture_materialized_rows"] = list(dict.fromkeys(ids))
    payload["source_backed_validation_fixture_materialized"] = True
    payload["validation_fixture_closed_requested_row_ids"] = closed_ids
    payload["validation_fixture_unclosed_requested_row_ids"] = unclosed_ids
    return {
        "validation_fixture_materialization_state": "materialized" if not unclosed_ids else "partial",
        "validation_fixture_materialized_rows": list(dict.fromkeys(ids)),
        "validation_fixture_materialized_count": len(incoming),
        "validation_fixture_closed_requested_row_ids": closed_ids,
        "validation_fixture_unclosed_requested_row_ids": unclosed_ids,
        "validation_fixture_required_field_delta": changed,
        "support_to_artifact_required_field_delta": changed,
    }


def _artifact_row_key_for_role_split(artifact_name: str, payload: Mapping[str, Any]) -> str:
    candidates = {
        "bill_of_materials.json": ("items", "components", "rows"),
        "interface_specifications.json": ("interfaces", "rows", "items"),
        "validation_fixtures.json": ("fixtures", "rows", "items"),
        "risk_controls.json": ("controls", "rows", "items"),
    }.get(artifact_name, ("rows", "items"))
    for key in candidates:
        if isinstance(payload.get(key), list):
            return key
    return candidates[0]


def _apply_operator_feedback_role_split_materialization(
    artifacts: dict[str, dict[str, Any]],
    *,
    operator_feedback: str,
    support_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    contract = parse_operator_feedback_obligations(operator_feedback)
    if not contract.required_role_splits:
        return {
            "role_split_materialization_state": "not_required",
            "materialized_role_split_rows": [],
            "role_split_uncovered_roles": [],
            "role_lane_closure_state": "not_required",
            "role_lane_misassignment_count": 0,
            "role_lane_closed_requested_row_ids": [],
            "role_lane_unclosed_requested_row_ids": [],
        }
    support_rows = _support_manifest_rows(support_manifest)
    materialized_ids: list[str] = []
    uncovered_roles: list[str] = []
    closed_requested_row_ids: list[str] = []
    unclosed_requested_row_ids: list[str] = []
    existing_closed_roles: list[str] = []
    misassignment_count = 0
    for split in contract.required_role_splits:
        artifact_name = str(split.artifact_name or "").strip()
        payload = artifacts.get(artifact_name)
        if not isinstance(payload, dict):
            uncovered_roles.extend(str(role) for role in split.required_roles)
            continue
        row_key = _artifact_row_key_for_role_split(artifact_name, payload)
        rows = [row for row in list(payload.get(row_key, []) or []) if isinstance(row, dict)]
        rows_by_identity: dict[str, dict[str, Any]] = {}
        for row in rows:
            for identity in _row_identity_candidates(row):
                rows_by_identity.setdefault(identity, row)
        for role in split.required_roles:
            normalized_role = _normalize_materialized_role(role)
            if not normalized_role:
                continue
            expected_lane = normalize_support_role_lane(role) or normalize_support_role_lane(normalized_role)
            existing_role_row = next(
                (
                    row
                    for row in rows
                    if (
                        (expected_lane and _role_lane_for_artifact_row(row) == expected_lane)
                        or _artifact_row_already_materializes_split_role(
                            row,
                            base_role=split.base_role,
                            role=normalized_role,
                        )
                    )
                ),
                None,
            )
            source_row = None
            incomplete_role_requested_ids: list[str] = []
            for candidate in support_rows:
                if not _support_row_matches_split_role(
                    candidate,
                    target_artifact=artifact_name,
                    role=normalized_role,
                ):
                    continue
                if not _support_row_has_role_split_required_fields(candidate):
                    requested_id = _clean_support_row_identity(candidate.get("requested_row_id"))
                    if requested_id:
                        incomplete_role_requested_ids.append(requested_id)
                    continue
                candidate_lane = _role_lane_for_support_row(candidate, fallback_role=normalized_role)
                if expected_lane and candidate_lane and candidate_lane != expected_lane:
                    continue
                explicit_targets = [
                    _clean_support_row_identity(candidate.get(field))
                    for field in ("target_row_id", "design_artifact_row_id", "item_id")
                    if _clean_support_row_identity(candidate.get(field))
                ]
                conflicting_targets = []
                for target_id in explicit_targets:
                    target_row = rows_by_identity.get(target_id)
                    target_lane = _role_lane_for_artifact_row(target_row or {})
                    target_identity_matches_expected = _artifact_row_already_materializes_split_role(
                        target_row or {},
                        base_role=split.base_role,
                        role=normalized_role,
                    )
                    if (
                        target_row
                        and expected_lane
                        and target_lane
                        and target_lane != expected_lane
                        and not target_identity_matches_expected
                    ):
                        conflicting_targets.append(target_id)
                if conflicting_targets:
                    misassignment_count += 1
                    requested_id = _clean_support_row_identity(candidate.get("requested_row_id"))
                    if requested_id:
                        unclosed_requested_row_ids.append(requested_id)
                    continue
                source_row = candidate
                break
            if not source_row:
                unclosed_requested_row_ids.extend(incomplete_role_requested_ids)
                if existing_role_row is not None:
                    existing_closed_roles.append(normalized_role)
                    continue
                uncovered_roles.append(normalized_role)
                continue
            materialized = _split_role_row_from_support(
                base_role=split.base_role,
                role=normalized_role,
                support_row=source_row,
            )
            requested_id = _clean_support_row_identity(source_row.get("requested_row_id"))
            materialized_id = str(materialized.get("item_id", "") or "").strip()
            existing_row = None
            for row in rows:
                if str(row.get("item_id", "") or row.get("row_id", "") or "") == materialized_id:
                    existing_row = row
                    break
            if existing_row is None and existing_role_row is not None:
                existing_row = existing_role_row
                materialized_id = str(
                    existing_role_row.get("item_id", "")
                    or existing_role_row.get("row_id", "")
                    or materialized_id
                )
                materialized["item_id"] = materialized_id
            if existing_row is not None:
                existing_lane = _role_lane_for_artifact_row(existing_row)
                existing_identity_matches_expected = _artifact_row_already_materializes_split_role(
                    existing_row,
                    base_role=split.base_role,
                    role=normalized_role,
                )
                if (
                    expected_lane
                    and existing_lane
                    and existing_lane != expected_lane
                    and not existing_identity_matches_expected
                ):
                    misassignment_count += 1
                    if requested_id:
                        unclosed_requested_row_ids.append(requested_id)
                    uncovered_roles.append(normalized_role)
                    continue
                before = dict(existing_row)
                existing_row.update({field: value for field, value in materialized.items() if value not in ("", [], {}, None)})
                if existing_row == before:
                    if materialized_id:
                        materialized_ids.append(materialized_id)
                    if requested_id:
                        closed_requested_row_ids.append(requested_id)
                    continue
            else:
                rows.append(materialized)
                for identity in _row_identity_candidates(materialized):
                    rows_by_identity.setdefault(identity, materialized)
            materialized_ids.append(materialized_id)
            if requested_id:
                closed_requested_row_ids.append(requested_id)
        split_role_rows = [
            row
            for row in rows
            if any(
                _artifact_row_already_materializes_split_role(
                    row,
                    base_role=split.base_role,
                    role=_normalize_materialized_role(role),
                )
                for role in split.required_roles
            )
        ]
        split_complete = all(
            any(
                _artifact_row_already_materializes_split_role(
                    row,
                    base_role=split.base_role,
                    role=_normalize_materialized_role(role),
                )
                for row in split_role_rows
            )
            for role in split.required_roles
        )
        if split_complete and split_role_rows:
            split_ids = [
                str(row.get("item_id", "") or row.get("row_id", "") or row.get("name", "") or "")
                for row in split_role_rows
                if str(row.get("item_id", "") or row.get("row_id", "") or row.get("name", "") or "")
            ]
            for row in rows:
                row_id = _normalize_materialized_role(
                    row.get("item_id", "") or row.get("row_id", "") or row.get("name", "")
                )
                if row_id == _normalize_materialized_role(split.base_role):
                    row["superseded_by_role_split_rows"] = True
                    row["superseded_by_role_split_row_ids"] = list(dict.fromkeys(split_ids))
                    row["grants_execution_authority"] = False
        payload[row_key] = rows
        payload["role_split_materialized"] = bool(materialized_ids)
        payload["role_split_materialized_rows"] = list(dict.fromkeys(materialized_ids))
        payload["role_split_uncovered_roles"] = list(dict.fromkeys(uncovered_roles))
    state = "materialized" if (materialized_ids or existing_closed_roles) else "blocked"
    if materialized_ids and uncovered_roles:
        state = "partial"
    elif existing_closed_roles and (uncovered_roles or misassignment_count):
        state = "partial"
    role_lane_state = (
        "closed"
        if (materialized_ids or existing_closed_roles) and not uncovered_roles and not misassignment_count
        else state
    )
    return {
        "role_split_materialization_state": state,
        "materialized_role_split_rows": list(dict.fromkeys(materialized_ids)),
        "role_split_uncovered_roles": list(dict.fromkeys(uncovered_roles)),
        "role_lane_closure_state": role_lane_state,
        "role_lane_misassignment_count": misassignment_count,
        "role_lane_closed_requested_row_ids": list(dict.fromkeys(closed_requested_row_ids)),
        "role_lane_unclosed_requested_row_ids": list(dict.fromkeys(unclosed_requested_row_ids)),
    }


def _is_full_dive_hardware_context(checkout: Mapping[str, Any], work_order: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(checkout.get("directive_text", "") or ""),
            str(checkout.get("operator_feedback", "") or ""),
            str(work_order.get("next_step_context", "") or ""),
            str(work_order.get("schema_skeleton_id", "") or ""),
        ]
    ).lower()
    return "full dive" in text or "full_dive" in text or "bci" in text or "neural" in text


def _full_dive_human_subject_blocked(checkout: Mapping[str, Any], work_order: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(checkout.get("directive_text", "") or ""),
            str(checkout.get("operator_feedback", "") or ""),
            str(work_order.get("next_step_context", "") or ""),
        ]
    ).lower()
    return _text_contains_full_dive_human_subject_claim(text)


def _text_contains_full_dive_human_subject_claim(text: str) -> bool:
    normalized_text = str(text or "").lower()

    def sentence_contains_term(sentence: str, term: str) -> bool:
        if term == "invasive":
            return re.search(r"(?<!non[- ])\binvasive\b", sentence) is not None
        return term in sentence

    blocked_terms = (
        "human subject",
        "human-subject",
        "unaugmented human",
        "full dive link",
        "immersive neural",
        "invasive",
        "implant",
        "stimulation",
    )
    instruction_only_markers = (
        "do not",
        "must not",
        "escalate for operator review",
        "if proposed work requires",
        "not build-ready",
        "not build ready",
        "must be marked blocked",
        "must be marked unsupported",
        "blocked/unsupported",
        "marked blocked",
        "marked unsupported",
        "claims must be",
        "blocked",
        "no human",
        "not human",
        "non-human",
        "non_invasive",
        "non invasive",
        "outside child authority",
        "requires irb",
        "operator-gated",
        "is gated",
        "are gated",
        "denied",
        "prohibited",
        "cannot be inferred",
        "unsupported by this child packet",
        "use remains prohibited",
    )
    bench_scope_markers = (
        "non-human synthetic bench",
        "synthetic bench",
        "bench/synthetic/non-human",
        "non-human bench",
        "bench fixture",
        "bench-prototype",
        "non-invasive hardware plus software",
        "non-invasive hardware and software",
        "hardware plus software interface",
        "hardware and software interface",
    )
    bench_scope_declared = any(marker in normalized_text for marker in bench_scope_markers)
    aspirational_only_terms = ("unaugmented human", "full dive link", "immersive neural")
    hard_execution_terms = (
        "human subject",
        "human-subject",
        "invasive",
        "implant",
        "stimulation",
        "clinical",
        "human experimentation",
        "human testing",
        "test on human",
        "deploy to human",
    )
    for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", normalized_text):
        if not any(sentence_contains_term(sentence, term) for term in blocked_terms):
            continue
        if any(marker in sentence for marker in instruction_only_markers):
            continue
        if (
            bench_scope_declared
            and any(sentence_contains_term(sentence, term) for term in aspirational_only_terms)
            and not any(sentence_contains_term(sentence, term) for term in hard_execution_terms)
        ):
            continue
        return True
    return False


def _full_dive_documentation_payloads(title: str) -> dict[str, Any]:
    return {
        "schematics.md": "\n".join(
            [
                "# Full Dive Non-Human Bench Schematic Pack",
                "",
                "```mermaid",
                "flowchart LR",
                "  SyntheticSignal[synthetic or non-human signal fixture] --> Isolation[isolated read-only adapter]",
                "  Isolation --> SafetyGate[operator safety gate]",
                "  SafetyGate --> Runtime[simulation runtime input contract]",
                "```",
                "",
                "- Boundary: review-only non-human/synthetic bench interface.",
                "- Prohibited: human-subject use, stimulation, invasive BCI, and ungated actuation.",
            ]
        )
        + "\n",
        "electrical_interface_spec.json": {
            "schema_name": "FullDiveElectricalInterfaceSpec",
            "directive_title": title,
            "interfaces": [
                {
                    "interface_id": "isolated_non_human_signal_adapter",
                    "connector": "operator-approved isolated bench connector",
                    "pinout": {"pin_1": "synthetic_signal_input", "pin_2": "isolated_reference", "pin_3": "safety_stop"},
                    "protocol": "read_only_fixture_contract_v1",
                    "signal_level": "low-energy isolated synthetic signal only",
                    "sample_rate": "recorded by bench fixture before review",
                    "bandwidth": "bounded to simulation input contract",
                    "latency_budget": "p95 <= 20ms for replay path",
                    "electrical_isolation": "isolation barrier required; no direct human connection",
                    "safety_limit": "no stimulation, no invasive electrode path, no actuation",
                    "failure_behavior": "fail closed and require operator review",
                }
            ],
            "execution_gated_by_operator_approval": True,
            "grants_execution_authority": False,
        },
        "bench_test_protocol.json": {
            "schema_name": "FullDiveBenchTestProtocol",
            "directive_title": title,
            "protocols": [
                {
                    "protocol_id": "synthetic_signal_replay_go_no_go",
                    "equipment": ["isolated measurement interface", "synthetic signal source", "safety-stop recorder"],
                    "fixture_wiring": "match schematics.md and electrical_interface_spec.json",
                    "calibration_steps": ["verify isolation", "load synthetic signal", "assert safety stop"],
                    "measurement_method": "record bounded_control_intent.v1 and governance_gate_record.v1",
                    "pass_fail_thresholds": ["fixture pass rate 100%", "unsafe bypass count 0"],
                    "operator_review_required": True,
                }
            ],
        },
        "safety_case.json": {
            "schema_name": "FullDiveSafetyCase",
            "directive_title": title,
            "safety_boundary": "non-human/synthetic bench review only",
            "blocked_capabilities": ["human_subject_use", "invasive_bci", "stimulation", "ungated_actuation"],
            "execution_gated_by_operator_approval": True,
            "grants_execution_authority": False,
        },
        "research_evidence_register.json": {
            "schema_name": "FullDiveResearchEvidenceRegister",
            "directive_title": title,
            "claims": [
                {
                    "claim_id": "full_dive_human_link_feasibility",
                    "claim": "Full Dive human-subject neural-link capability is unsupported by this child packet.",
                    "evidence_state": "blocked_until_trusted_sources_and_regulatory_review",
                    "allowed_scope": "simulation and non-human/synthetic bench interface only",
                }
            ],
        },
        "regulatory_assumption_log.json": {
            "schema_name": "FullDiveRegulatoryAssumptionLog",
            "directive_title": title,
            "assumptions": [
                {
                    "assumption_id": "medical_device_review_required",
                    "standard_ref": "IEC 60601 / ISO 14971 applicability review required before human-adjacent hardware",
                    "status": "operator_or_external_expert_review_required",
                }
            ],
            "human_subject_use": "blocked",
            "clinical_use": "blocked",
            "grants_execution_authority": False,
        },
    }


def _row_field_gaps(payloads: Mapping[str, Any], requirements: Mapping[str, Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    gaps: dict[str, list[dict[str, Any]]] = {}
    for artifact_name, contract in requirements.items():
        payload = payloads.get(artifact_name, {})
        if not isinstance(payload, Mapping):
            rows: list[Mapping[str, Any]] = []
        else:
            row_key = str(contract.get("row_key", "") or "")
            rows = [row for row in list(payload.get(row_key, []) or []) if isinstance(row, Mapping)]
        required_fields = [str(field) for field in list(contract.get("fields", []) or []) if str(field)]
        artifact_gaps: list[dict[str, Any]] = []
        if not rows:
            artifact_gaps.append({"row_index": 0, "row_id": "", "missing_fields": required_fields})
        for index, row in enumerate(rows):
            if bool(row.get("superseded_by_role_split_rows", False)):
                continue
            missing = [field for field in required_fields if row.get(field) in ("", None, [])]
            if missing:
                row_id = str(
                    row.get("item_id", "")
                    or row.get("interface_id", "")
                    or row.get("fixture_id", "")
                    or row.get("control_id", "")
                    or row.get("hazard_id", "")
                    or ""
                )
                artifact_gaps.append({"row_index": index, "row_id": row_id, "missing_fields": missing})
        if artifact_gaps:
            gaps[artifact_name] = artifact_gaps
    return gaps


def _technical_depth_value_is_placeholder(value: Any) -> bool:
    if value in ("", None, []):
        return False
    text = json.dumps(value, sort_keys=True, default=str).lower() if isinstance(value, (Mapping, list, tuple)) else str(value).lower()
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return False
    return any(marker in normalized for marker in TECHNICAL_DEPTH_PLACEHOLDER_MARKERS)


def _row_placeholder_gaps(payloads: Mapping[str, Any], requirements: Mapping[str, Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    gaps: dict[str, list[dict[str, Any]]] = {}
    for artifact_name, contract in requirements.items():
        payload = payloads.get(artifact_name, {})
        if not isinstance(payload, Mapping):
            continue
        row_key = str(contract.get("row_key", "") or "")
        rows = [row for row in list(payload.get(row_key, []) or []) if isinstance(row, Mapping)]
        required_fields = [str(field) for field in list(contract.get("fields", []) or []) if str(field)]
        artifact_gaps: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if bool(row.get("superseded_by_role_split_rows", False)):
                continue
            generic = [field for field in required_fields if field in row and _technical_depth_value_is_placeholder(row.get(field))]
            if generic:
                row_id = str(
                    row.get("item_id", "")
                    or row.get("interface_id", "")
                    or row.get("fixture_id", "")
                    or row.get("control_id", "")
                    or row.get("hazard_id", "")
                    or ""
                )
                artifact_gaps.append({"row_index": index, "row_id": row_id, "generic_placeholder_fields": generic})
        if artifact_gaps:
            gaps[artifact_name] = artifact_gaps
    return gaps


def _row_semantic_mismatch_gaps(payloads: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    payload = payloads.get("bill_of_materials.json", {})
    if not isinstance(payload, Mapping):
        return {}
    rows = [row for row in list(payload.get("items", []) or []) if isinstance(row, Mapping)]
    gaps: list[dict[str, Any]] = []

    def row_id(row: Mapping[str, Any]) -> str:
        return str(row.get("item_id", "") or row.get("name", "") or "")

    def add_gap(index: int, row: Mapping[str, Any], reason: str, expected_role: str) -> None:
        gaps.append(
            {
                "artifact_name": "bill_of_materials.json",
                "row_index": index,
                "row_id": row_id(row),
                "semantic_mismatch_reason": reason,
                "expected_role": expected_role,
            }
        )

    for index, original_row in enumerate(rows):
        row = dict(original_row)
        identity_text = " ".join(
            str(row.get(field, "") or "")
            for field in ("item_id", "name", "role", "function", "description", "subsystem")
        ).lower()
        source_text = json.dumps(
            {
                key: value
                for key, value in row.items()
                if key
                in {
                    "manufacturer",
                    "mpn",
                    "part_number",
                    "datasheet_url",
                    "source_url",
                    "source_assumption",
                    "measurable_spec",
                    "electrical_rating",
                    "mechanical_rating",
                    "compliance_notes",
                }
            },
            sort_keys=True,
            default=str,
        ).lower()
        combined = f"{identity_text} {source_text}"
        is_misumi_extrusion = bool(
            "misumi" in combined
            and (
                "hfs" in combined
                or "aluminum extrusion" in combined
                or "aluminium extrusion" in combined
                or "t-slot" in combined
            )
        )
        if any(token in identity_text for token in ("ceramic", "liner", "insulation", "insulator")) and is_misumi_extrusion:
            add_gap(index, row, "role_component_mismatch", "ceramic_or_high_temperature_insulating_liner")
        if any(token in identity_text for token in ("cooling", "quench", "pump", "flow", "heat exchanger")) and is_misumi_extrusion:
            add_gap(index, row, "role_component_mismatch", "active_cooling_or_quench_fluid_component")
        field_coil_role = "coil" in identity_text and any(
            token in identity_text for token in ("field", "electromagnet", "magnet", "winding")
        )
        small_inductor_source = any(
            token in source_text
            for token in ("tdk", "b82477", "smd inductor", "power inductor", "470 uh")
        )
        if field_coil_role and small_inductor_source:
            add_gap(index, row, "role_component_mismatch", "bench_electromagnet_or_coil_winding_subsystem")
        field_or_thermal_sensor_role = "sensor" in identity_text and any(
            token in identity_text
            for token in ("temperature", "thermal", "current", "field", "hall", "gauss", "coolant")
        )
        biopotential_source = any(
            token in source_text
            for token in ("ads1299", "biopotential", "eeg", "ecg", "electrode")
        )
        if field_or_thermal_sensor_role and biopotential_source:
            add_gap(index, row, "role_component_mismatch", "temperature_field_current_or_coolant_sensor_subsystem")

    return {"bill_of_materials.json": gaps} if gaps else {}


def _full_dive_hardware_readiness_metrics(
    *,
    checkout: Mapping[str, Any],
    work_order: Mapping[str, Any],
    workspace: Path,
    payloads: Mapping[str, Any],
) -> dict[str, Any]:
    if not _is_full_dive_hardware_context(checkout, work_order):
        return {}
    docs_present = all((workspace / artifact).is_file() for artifact in FULL_DIVE_HARDWARE_DOCUMENTATION_ARTIFACTS)
    field_gaps = _row_field_gaps(payloads, FULL_DIVE_HARDWARE_REQUIRED_FIELDS)
    placeholder_gaps = _row_placeholder_gaps(payloads, FULL_DIVE_HARDWARE_REQUIRED_FIELDS)
    human_blocked = _full_dive_human_subject_blocked(checkout, work_order)
    blockers: list[str] = []
    if field_gaps:
        blockers.append("missing_full_dive_hardware_depth_fields")
    if placeholder_gaps:
        blockers.append("generic_full_dive_hardware_depth_fields")
    if not docs_present:
        blockers.append("missing_full_dive_hardware_documentation_artifacts")
    if human_blocked:
        blockers.append("full_dive_human_subject_scope_blocked")
    strict_passed = bool(not field_gaps and not placeholder_gaps and docs_present and not human_blocked)
    if strict_passed:
        tier = "bench_electronics_ready"
    elif human_blocked:
        tier = "human_subject_blocked"
    elif not field_gaps:
        tier = "simulation_interface_ready"
    else:
        tier = "simulation_interface_ready"
    return {
        "hardware_readiness_tier": tier,
        "hardware_readiness_blockers": blockers,
        "strict_hardware_contract_passed": strict_passed,
        "full_dive_human_subject_blocked": human_blocked,
        "required_hardware_artifacts_present": docs_present,
        "full_dive_field_gaps_by_artifact": field_gaps,
        "generic_placeholder_gaps": placeholder_gaps,
        "generic_placeholder_gap_count": sum(len(rows) for rows in placeholder_gaps.values()),
        "technical_depth_contract_passed": bool(not field_gaps and not placeholder_gaps),
        "hardware_build_packet_ready_candidate": strict_passed,
        "remaining_failed_gates": list(dict.fromkeys(blockers)),
    }


def _apply_hardware_prototype_readiness_contract(
    artifacts: dict[str, Any],
    *,
    title: str,
    work_order: dict[str, Any],
    operator_feedback: str = "",
    support_manifest: Mapping[str, Any] | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    contract = work_order.get("hardware_prototype_readiness_contract", {})
    if not isinstance(contract, dict) or not contract:
        return {}
    source_ref = next(
        (
            str(ref.get("pack_id", "") or ref.get("support_request_id", "") or "")
            for ref in list(work_order.get("allowed_pack_refs", []) or [])
            if isinstance(ref, Mapping)
            and str(ref.get("pack_id", "") or ref.get("support_request_id", "") or "").strip()
        ),
        "",
    )
    rows = _hardware_bench_contract_rows(
        title,
        source_ref=source_ref,
        operator_feedback=operator_feedback,
    )
    artifacts["device_capability_manifest.json"] = dict(rows["device_capability_manifest"])
    if _is_full_dive_hardware_context({"directive_text": title}, work_order):
        artifacts.update(_full_dive_documentation_payloads(title))
    if "interface_specifications.json" in artifacts:
        artifacts["interface_specifications.json"]["interfaces"] = rows["interfaces"]
        artifacts["interface_specifications.json"]["hardware_prototype_contract_applied"] = True
    if "bill_of_materials.json" in artifacts:
        artifacts["bill_of_materials.json"]["items"] = rows["bom_items"]
        artifacts["bill_of_materials.json"]["hardware_prototype_contract_applied"] = True
        if workspace is not None:
            _merge_existing_json_artifact_rows(
                artifacts["bill_of_materials.json"],
                workspace / "bill_of_materials.json",
                artifact_name="bill_of_materials.json",
            )
    if "validation_fixtures.json" in artifacts:
        artifacts["validation_fixtures.json"]["fixtures"] = rows["fixtures"]
        artifacts["validation_fixtures.json"]["hardware_prototype_contract_applied"] = True
    if "risk_controls.json" in artifacts:
        artifacts["risk_controls.json"]["controls"] = rows["controls"]
        artifacts["risk_controls.json"]["hardware_prototype_contract_applied"] = True
    if "implementation_readiness_review.json" in artifacts:
        artifacts["implementation_readiness_review.json"]["execution_gated_by_operator_approval"] = True
        artifacts["implementation_readiness_review.json"]["grants_execution_authority"] = False
        artifacts["implementation_readiness_review.json"]["hardware_prototype_contract"] = {
            "contract_kind": str(contract.get("contract_kind", "review_only_hardware_prototype_readiness")),
            "execution_gated_by_operator_approval": True,
            "grants_execution_authority": False,
            "required_artifacts": list(contract.get("required_artifacts", []) or []),
        }
    role_split_metrics = _apply_operator_feedback_role_split_materialization(
        artifacts,
        operator_feedback=operator_feedback,
        support_manifest=support_manifest or {},
    )
    source_bom_metrics = _apply_source_backed_bom_support_materialization(
        artifacts,
        support_manifest=support_manifest or {},
    )
    source_risk_metrics = _apply_source_backed_risk_support_materialization(
        artifacts,
        support_manifest=support_manifest or {},
    )
    source_fixture_metrics = _apply_source_backed_validation_fixture_support_materialization(
        artifacts,
        support_manifest=support_manifest or {},
    )
    placeholder_gaps = _row_placeholder_gaps(artifacts, FULL_DIVE_HARDWARE_REQUIRED_FIELDS)
    semantic_mismatch_gaps = _row_semantic_mismatch_gaps(artifacts)
    feedback_assessment = assess_operator_feedback_obligations(
        operator_feedback,
        payloads=artifacts,
    )
    feedback_gap_count = int(feedback_assessment.get("operator_feedback_obligation_gap_count", 0) or 0)
    remaining_failed_gates = ["technical_depth_contract_generic_placeholders"] if placeholder_gaps else []
    if semantic_mismatch_gaps:
        remaining_failed_gates.append("technical_depth_contract_semantic_mismatch")
    if feedback_gap_count:
        remaining_failed_gates.append("operator_feedback_obligation_unresolved")
    technical_depth_passed = bool(not placeholder_gaps and not semantic_mismatch_gaps and not feedback_gap_count)
    return {
        "hardware_prototype_contract_applied": True,
        "hardware_build_packet_contract_applied": True,
        "closed_failed_gates": ["hardware_prototype_readiness_contract_required"] if technical_depth_passed else [],
        "remaining_failed_gates": remaining_failed_gates,
        "generic_placeholder_gaps": placeholder_gaps,
        "generic_placeholder_gap_count": sum(len(rows) for rows in placeholder_gaps.values()),
        "semantic_mismatch_gaps": semantic_mismatch_gaps,
        "semantic_mismatch_gap_count": sum(len(rows) for rows in semantic_mismatch_gaps.values()),
        "technical_depth_contract_passed": technical_depth_passed,
        "hardware_build_packet_ready_candidate": technical_depth_passed,
        **feedback_assessment,
        **role_split_metrics,
        **source_bom_metrics,
        **source_risk_metrics,
        **source_fixture_metrics,
    }


def _collect_hardware_expected_file_refs(payloads: Mapping[str, dict[str, Any]]) -> list[str]:
    refs: list[str] = []

    def append_ref(value: Any) -> None:
        text = str(value or "").strip().replace("\\", "/")
        if not text or text.startswith("/") or ".." in Path(text).parts:
            return
        if text not in refs:
            refs.append(text)

    for artifact_name in ("validation_fixtures.json", "prototype_assembly_plan.json"):
        payload = dict(payloads.get(artifact_name, {}) or {})
        rows: list[Mapping[str, Any]] = []
        for key in ("fixtures", "validation_fixtures", "assembly_steps", "steps", "items", "rows"):
            for row in list(payload.get(key, []) or []):
                if isinstance(row, Mapping):
                    rows.append(row)
        for row in rows:
            for item in list(row.get("expected_files", []) or []):
                append_ref(item)
            append_ref(row.get("expected_file", ""))
            append_ref(row.get("go_no_go_trace", ""))
            append_ref(row.get("pass_fail_trace", ""))
    return refs


def _materialize_hardware_build_packet_files(
    workspace: Path,
    *,
    payloads: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    materialized: list[str] = []
    missing: list[str] = []
    for relative_path in _collect_hardware_expected_file_refs(payloads):
        destination = workspace / relative_path
        try:
            destination.relative_to(workspace)
        except ValueError:
            missing.append(relative_path)
            continue
        payload = {
            "schema_name": "ConveyorMaterializedHardwareFixture",
            "relative_path": relative_path,
            "execution_gated_by_operator_approval": True,
            "grants_execution_authority": False,
            "review_only": True,
        }
        if "go_no_go" in relative_path or "trace" in relative_path:
            payload["go_no_go"] = {
                "allowed": False,
                "operator_review_required": True,
                "unsafe_bypass_count": 0,
            }
        _write_json_artifact(destination, payload)
        materialized.append(relative_path)
    for relative_path in materialized:
        if not (workspace / relative_path).is_file():
            missing.append(relative_path)
    return {
        "materialized_expected_files": materialized,
        "missing_materialized_expected_files_after_write": list(dict.fromkeys(missing)),
        "hardware_build_packet_ready_candidate": not missing,
    }


def _build_grade_rows(deliverable_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    title = str(deliverable_payload.get("directive_title", "") or "Untitled directive")
    objectives = [str(item) for item in list(deliverable_payload.get("objectives", []) or [])]
    deliverables = [str(item) for item in list(deliverable_payload.get("deliverables", []) or [])]
    seeds = deliverables or objectives or [title]
    subsystems = []
    interfaces = []
    dependencies = []
    validations = []
    milestones = []
    for index, seed in enumerate(seeds[:8], start=1):
        slug = re.sub(r"[^a-z0-9]+", "_", seed.lower()).strip("_")[:48] or f"work_package_{index}"
        subsystems.append(
            {
                "subsystem_id": f"subsystem_{index}",
                "name": seed,
                "directive_specific": True,
                "responsibility": f"Own the {seed} work package for {title}.",
                "inputs": ["operator clarification", "checked-out knowledge packs"],
                "outputs": [f"{slug}_specification", f"{slug}_review_evidence"],
                "escalation_gate": "operator_review_before_real_world_use",
            }
        )
        interfaces.append(
            {
                "interface_id": f"interface_{index}",
                "name": f"{seed} review interface",
                "directive_specific": True,
                "producer": f"subsystem_{index}",
                "consumer": "operator_review_packet",
                "contract": "structured JSON artifact plus human-readable technical documentation",
                "boundary": "no direct core-state writes and no child network access",
            }
        )
        dependencies.append(
            {
                "dependency_id": f"dependency_{index}",
                "name": f"{seed} evidence dependency",
                "directive_specific": True,
                "needed_for": seed,
                "source": "librarian_or_operator_clarification",
                "risk_if_missing": "claim remains review-only and cannot be treated as actionable",
            }
        )
        validations.append(
            {
                "validation_id": f"validation_{index}",
                "name": f"{seed} non-deployment validation",
                "directive_specific": True,
                "method": "tabletop review, simulation, or mock interface test",
                "acceptance_evidence": f"{slug}_validation_record",
                "stop_condition": "clinical, invasive, unsafe, or deployment-sensitive work requires operator approval",
            }
        )
        milestones.append(
            {
                "milestone_id": f"milestone_{index}",
                "name": f"{seed} prototype-readiness milestone",
                "directive_specific": True,
                "prototype_level": "reviewable plan or harmless mock",
                "exit_criteria": "operator can decide whether to accept, clarify, split, or requeue",
            }
        )
    return {
        "subsystems": subsystems,
        "interfaces": interfaces,
        "dependencies": dependencies,
        "protocols": validations,
        "milestones": milestones,
    }


def _directive_depth_profile(title: str) -> str:
    lowered = str(title or "").lower()
    if "full dive" in lowered or "virtual simulation" in lowered:
        return "full_dive_simulation"
    if "grin" in lowered or "human advancement" in lowered:
        return "grin_non_clinical_architecture"
    return "generic_build_package"


def _domain_build_package_rows(title: str) -> dict[str, list[dict[str, Any]]]:
    profile = _directive_depth_profile(title)
    if profile == "full_dive_simulation":
        return {
            "subsystems": [
                {
                    "subsystem_id": "simulation_runtime_core",
                    "name": "Simulation Runtime Core",
                    "directive_specific": True,
                    "responsibility": "Own deterministic world-step scheduling, scene lifecycle, and module orchestration for the virtual simulation prototype.",
                    "inputs": ["simulation_config.v1", "operator_session_control.v1", "runtime_asset_manifest.v1"],
                    "outputs": ["simulation_frame_state.v1", "runtime_event_log.v1", "module_health_report.v1"],
                    "escalation_gate": "operator_review_before_real_world_use",
                },
                {
                    "subsystem_id": "control_loop_adapter",
                    "name": "Input and Control Loop Adapter",
                    "directive_specific": True,
                    "responsibility": "Translate bounded operator/device inputs into simulation intents with latency, safety-stop, and replay constraints.",
                    "inputs": ["input_sample_stream.v1", "calibration_profile.v1"],
                    "outputs": ["bounded_control_intent.v1", "input_latency_trace.v1"],
                    "escalation_gate": "operator_review_before_real_world_use",
                },
                {
                    "subsystem_id": "physics_render_bridge",
                    "name": "Physics and Rendering Bridge",
                    "directive_specific": True,
                    "responsibility": "Connect fixed-step simulation state to visual rendering and collision/contact observations for prototype evaluation.",
                    "inputs": ["simulation_frame_state.v1", "scene_asset_bundle.v1"],
                    "outputs": ["render_frame_contract.v1", "collision_observation_log.v1"],
                    "escalation_gate": "operator_review_before_real_world_use",
                },
            ],
            "interfaces": [
                {
                    "interface_id": "runtime_config_contract",
                    "name": "Simulation Runtime Configuration Contract",
                    "directive_specific": True,
                    "producer": "operator_configuration_panel",
                    "consumer": "simulation_runtime_core",
                    "inputs": {"simulation_config.v1": ["tick_rate_hz:int", "scene_id:string", "enabled_modules:list[string]"]},
                    "outputs": {"runtime_ack.v1": ["accepted:bool", "rejected_fields:list[string]", "config_hash:string"]},
                    "failure_modes": ["unsupported_tick_rate", "missing_scene_asset", "module_dependency_conflict"],
                    "validation_hooks": ["config_schema_validation", "cold_start_smoke_fixture", "module_dependency_fixture"],
                    "boundary": "software simulation prototype only; no deployment authority",
                },
                {
                    "interface_id": "bounded_control_intent_contract",
                    "name": "Bounded Control Intent Contract",
                    "directive_specific": True,
                    "producer": "control_loop_adapter",
                    "consumer": "simulation_runtime_core",
                    "inputs": {"input_sample_stream.v1": ["timestamp_ns:int", "source_id:string", "axis_values:map[string,float]"]},
                    "outputs": {"bounded_control_intent.v1": ["intent_id:string", "normalized_axes:map[string,float]", "safety_stop:bool"]},
                    "failure_modes": ["input_timestamp_gap", "axis_out_of_bounds", "calibration_profile_missing"],
                    "validation_hooks": ["replay_trace_fixture", "latency_budget_fixture", "safety_stop_fixture"],
                    "boundary": "operator-reviewed simulation controls; external device integration remains gated",
                },
            ],
            "dependencies": [
                {
                    "dependency_id": "simulation_engine_runtime",
                    "name": "Fixed-step simulation engine runtime",
                    "directive_specific": True,
                    "needed_for": "Simulation Runtime Core",
                    "source": "trusted-source engine documentation or local runtime decision",
                    "version_constraint": "supports deterministic fixed-step update loop and headless test execution",
                    "risk_if_missing": "prototype cannot reproduce evaluation traces or compare simulation outcomes",
                },
                {
                    "dependency_id": "render_physics_integration",
                    "name": "Rendering and physics integration layer",
                    "directive_specific": True,
                    "needed_for": "Physics and Rendering Bridge",
                    "source": "trusted-source runtime module documentation",
                    "version_constraint": "supports collision/contact observation export and frame-state interpolation",
                    "risk_if_missing": "visual output cannot be validated against physics state",
                },
            ],
            "fixtures": [
                {
                    "fixture_id": "simulation_config_cold_start_fixture",
                    "purpose": "Verify a minimal scene boots with deterministic tick configuration and produces a frame-state log.",
                    "setup": "Start runtime with a one-room scene, fixed 60 Hz tick, and only runtime/core/render modules enabled.",
                    "test_data_shape": {"simulation_config.v1": ["tick_rate_hz", "scene_id", "enabled_modules"]},
                    "pass_fail_criteria": ["runtime_ack.accepted == true", "100 consecutive frame_state records emitted", "no module_health_report errors"],
                    "instrumentation": ["runtime_event_log.v1", "module_health_report.v1"],
                    "replay_harness": "Headless cold-start replay runs the same scene/config hash three times and compares frame-state counts.",
                    "evaluation_harness": "Evaluate deterministic boot, module health, and frame-state emission without external devices or deployment authority.",
                    "execution_gate": "software_simulation_only",
                },
                {
                    "fixture_id": "bounded_input_replay_fixture",
                    "purpose": "Validate that recorded input samples convert to bounded intents within latency and range constraints.",
                    "setup": "Replay a 30-second synthetic input trace through the control loop adapter at fixed timestamps.",
                    "test_data_shape": {"input_sample_stream.v1": ["timestamp_ns", "source_id", "axis_values"]},
                    "pass_fail_criteria": ["p95 adapter latency <= configured budget", "no normalized_axes outside [-1.0, 1.0]", "safety_stop toggles on invalid trace"],
                    "instrumentation": ["input_latency_trace.v1", "bounded_control_intent.v1"],
                    "replay_harness": "Timestamped trace replay feeds identical synthetic samples through the adapter at fixed wall-clock-independent intervals.",
                    "evaluation_harness": "Evaluate latency budget, bounded output ranges, and safety-stop behavior against recorded intent traces.",
                    "execution_gate": "software_simulation_only",
                },
            ],
        }
    if profile == "grin_non_clinical_architecture":
        return {
            "subsystems": [
                {
                    "subsystem_id": "non_invasive_signal_model",
                    "name": "Non-invasive Signal Model",
                    "directive_specific": True,
                    "responsibility": "Define reviewable signal categories, data boundaries, and simulation-only analysis assumptions without clinical claims.",
                    "inputs": ["public_research_feature_catalog.v1", "synthetic_signal_trace.v1"],
                    "outputs": ["feature_contract.v1", "simulation_analysis_report.v1"],
                    "escalation_gate": "execution_gated_by_operator_approval",
                },
                {
                    "subsystem_id": "external_interface_gateway",
                    "name": "External Non-invasive Interface Gateway",
                    "directive_specific": True,
                    "responsibility": "Specify safe external interface boundaries, consent/governance metadata, and prototype adapter contracts.",
                    "inputs": ["device_capability_manifest.v1", "operator_governance_profile.v1"],
                    "outputs": ["bounded_interface_event.v1", "governance_gate_record.v1"],
                    "escalation_gate": "execution_gated_by_operator_approval",
                },
                {
                    "subsystem_id": "evaluation_governance_harness",
                    "name": "Evaluation and Governance Harness",
                    "directive_specific": True,
                    "responsibility": "Validate architecture-level claims against synthetic/non-human data and stop before clinical or human-subject execution.",
                    "inputs": ["synthetic_signal_trace.v1", "claim_evidence_register.v1"],
                    "outputs": ["validation_result.v1", "operator_gate_request.v1"],
                    "escalation_gate": "execution_gated_by_operator_approval",
                },
            ],
            "interfaces": [
                {
                    "interface_id": "synthetic_signal_feature_contract",
                    "name": "Synthetic Signal Feature Contract",
                    "directive_specific": True,
                    "producer": "non_invasive_signal_model",
                    "consumer": "evaluation_governance_harness",
                    "inputs": {"synthetic_signal_trace.v1": ["sample_rate_hz:int", "channels:list[string]", "samples:array[float]"]},
                    "outputs": {"feature_contract.v1": ["feature_id:string", "window_ms:int", "confidence:float", "evidence_ref:string"]},
                    "failure_modes": ["sample_rate_unknown", "channel_semantics_missing", "confidence_without_evidence"],
                    "validation_hooks": ["synthetic_trace_fixture", "feature_schema_fixture", "evidence_ref_fixture"],
                    "boundary": "non-clinical synthetic-data architecture; human-subject execution is gated",
                },
                {
                    "interface_id": "external_gateway_event_contract",
                    "name": "External Gateway Event Contract",
                    "directive_specific": True,
                    "producer": "external_interface_gateway",
                    "consumer": "evaluation_governance_harness",
                    "inputs": {"device_capability_manifest.v1": ["device_class:string", "non_invasive:bool", "declared_channels:list[string]"]},
                    "outputs": {"bounded_interface_event.v1": ["event_id:string", "allowed:bool", "blocked_reason:string", "governance_gate:string"]},
                    "failure_modes": ["invasive_capability_declared", "missing_consent_metadata", "unsupported_channel_claim"],
                    "validation_hooks": ["capability_manifest_fixture", "governance_gate_fixture", "blocked_event_fixture"],
                    "boundary": "architecture specification only; device connection and human testing require operator approval",
                },
            ],
            "dependencies": [
                {
                    "dependency_id": "synthetic_signal_dataset_generator",
                    "name": "Synthetic non-human signal dataset generator",
                    "directive_specific": True,
                    "needed_for": "Non-invasive Signal Model",
                    "source": "kernel-mediated research pack or local synthetic fixture",
                    "version_constraint": "emits channel metadata, sample rate, and trace provenance",
                    "risk_if_missing": "analysis claims cannot be evaluated without touching human-subject data",
                },
                {
                    "dependency_id": "governance_gate_policy_table",
                    "name": "Governance gate policy table",
                    "directive_specific": True,
                    "needed_for": "Evaluation and Governance Harness",
                    "source": "operator-approved governance requirements",
                    "version_constraint": "identifies clinical, invasive, human-subject, and deployment-sensitive blockers",
                    "risk_if_missing": "prototype plan may blur architecture review with execution authority",
                },
            ],
            "fixtures": [
                {
                    "fixture_id": "synthetic_trace_feature_fixture",
                    "purpose": "Verify feature extraction contracts on synthetic, non-human traces without clinical interpretation.",
                    "setup": "Generate a 60-second synthetic multi-channel trace with declared sample rate and channel labels.",
                    "test_data_shape": {"synthetic_signal_trace.v1": ["sample_rate_hz", "channels", "samples", "provenance"]},
                    "pass_fail_criteria": ["all feature_contract records include evidence_ref", "confidence values remain bounded [0,1]", "no human-subject data fields are present"],
                    "instrumentation": ["feature_contract.v1", "validation_result.v1"],
                    "replay_harness": "Synthetic trace replay uses fixed generated traces and provenance hashes; no human-subject data is loaded.",
                    "evaluation_harness": "Evaluate feature schema, bounded confidence, evidence references, and non-clinical interpretation boundaries.",
                    "execution_gate": "execution_gated_by_operator_approval",
                },
                {
                    "fixture_id": "governance_block_fixture",
                    "purpose": "Verify that invasive, clinical, or human-subject capability declarations stop at operator approval.",
                    "setup": "Feed gateway manifests with safe external, unknown, and explicitly invasive capability flags.",
                    "test_data_shape": {"device_capability_manifest.v1": ["device_class", "non_invasive", "declared_channels"]},
                    "pass_fail_criteria": ["invasive manifests emit allowed == false", "blocked_reason is explicit", "operator_gate_request is generated"],
                    "instrumentation": ["bounded_interface_event.v1", "operator_gate_request.v1"],
                    "replay_harness": "Replay safe, unknown, and blocked capability manifests through the gateway with fixed expected gate outcomes.",
                    "evaluation_harness": "Evaluate governance gate classification, blocked reasons, and operator gate request generation.",
                    "execution_gate": "execution_gated_by_operator_approval",
                },
            ],
        }
    return {}


def _domain_bom_items(
    title: str,
    rows: dict[str, list[dict[str, Any]]],
    domain_rows: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    profile = _directive_depth_profile(title)
    if profile == "full_dive_simulation":
        return [
            {
                "item_id": "simulation_engine_runtime",
                "name": "Fixed-step simulation engine runtime",
                "category": "software_runtime",
                "required_for": "Simulation Runtime Core",
                "version_constraint": "deterministic fixed-step update loop with headless test execution",
                "source_assumption": "kernel-mediated trusted-source pack or local engine selection",
                "substitution_allowed": True,
                "execution_gate": "software_simulation_only",
            },
            {
                "item_id": "input_replay_harness",
                "name": "Synthetic input replay harness",
                "category": "test_fixture_software",
                "required_for": "Input and Control Loop Adapter",
                "version_constraint": "timestamped input trace replay with latency instrumentation",
                "source_assumption": "local prototype fixture implementation",
                "substitution_allowed": True,
                "execution_gate": "software_simulation_only",
            },
            {
                "item_id": "physics_render_bridge_module",
                "name": "Physics/render bridge module",
                "category": "software_library",
                "required_for": "Physics and Rendering Bridge",
                "version_constraint": "exports collision/contact observations and render frame contracts",
                "source_assumption": "trusted-source runtime module documentation",
                "substitution_allowed": True,
                "execution_gate": "software_simulation_only",
            },
        ]
    if profile == "grin_non_clinical_architecture":
        return [
            {
                "item_id": "synthetic_signal_generator",
                "name": "Synthetic non-human signal generator",
                "category": "test_fixture_software",
                "required_for": "Non-invasive Signal Model",
                "version_constraint": "emits sample rate, channel metadata, trace provenance, and synthetic sample arrays",
                "source_assumption": "local synthetic fixture or kernel-mediated research pack",
                "substitution_allowed": True,
                "execution_gate": "execution_gated_by_operator_approval",
            },
            {
                "item_id": "governance_policy_table",
                "name": "Governance gate policy table",
                "category": "review_control_data",
                "required_for": "Evaluation and Governance Harness",
                "version_constraint": "covers clinical, invasive, human-subject, privacy, and deployment-sensitive blockers",
                "source_assumption": "operator-approved policy context",
                "substitution_allowed": False,
                "execution_gate": "execution_gated_by_operator_approval",
            },
            {
                "item_id": "external_gateway_manifest_schema",
                "name": "External interface capability manifest schema",
                "category": "software_contract",
                "required_for": "External Non-invasive Interface Gateway",
                "version_constraint": "declares device class, non-invasive flag, channels, and consent metadata",
                "source_assumption": "kernel work order and operator clarification",
                "substitution_allowed": True,
                "execution_gate": "execution_gated_by_operator_approval",
            },
        ]
    return [
        {
            "item_id": f"bom_{index}",
            "name": f"{row['name']} prototype dependency",
            "category": "hardware_or_software_dependency",
            "required_for": row["name"],
            "source_assumption": "operator_or_trusted_source_to_confirm",
            "substitution_allowed": True,
            "execution_gate": "execution_gated_by_operator_approval",
        }
        for index, row in enumerate(rows["subsystems"][:8], start=1)
    ]


def _fallback_validation_fixtures(rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {
            "fixture_id": f"fixture_{index}",
            "purpose": f"Validate {row['name']} with bounded prototype fixtures before real-world testing.",
            "setup": f"Instantiate the {row['name']} subsystem with synthetic inputs and disabled deployment outputs.",
            "test_data_shape": {"inputs": list(row.get("inputs", []) or []), "outputs": list(row.get("outputs", []) or [])},
            "pass_fail_criteria": [
                "input schema validates",
                "output schema validates",
                "failure modes stop at operator review",
            ],
            "instrumentation": [f"fixture_{index}_trace.json", f"fixture_{index}_result.json"],
            "expected_files": [
                f"fixtures/{row['subsystem_id']}_fixture.json",
                f"fixtures/{row['subsystem_id']}_go_no_go_trace.json",
            ],
            "expected_outputs": list(row.get("outputs", []) or []) or [f"{row['subsystem_id']}_validation_result.v1"],
            "acceptance_thresholds": [
                {"metric": "fixture pass rate", "threshold": "100%"},
                {"metric": "unsafe bypass count", "threshold": "0"},
            ],
            "go_no_go_trace": f"fixtures/{row['subsystem_id']}_go_no_go_trace.json",
            "replay_harness": f"Replay synthetic inputs for {row['name']} through the fixture without live deployment outputs.",
            "evaluation_harness": f"Evaluate {row['name']} schema validity, observable outputs, and operator-gated failure stops.",
            "execution_gate": "execution_gated_by_operator_approval",
        }
        for index, row in enumerate(rows["subsystems"][:8], start=1)
    ]


def _validation_fixture_closure_fields(fixture: dict[str, Any], index: int) -> dict[str, Any]:
    fixture_id = str(fixture.get("fixture_id", fixture.get("scenario_fixture_id", f"fixture_{index}")) or f"fixture_{index}")
    expected_outputs = list(fixture.get("expected_outputs", []) or [])
    if not expected_outputs:
        expected_outputs = (
            list(fixture.get("outputs", []) or [])
            or list(fixture.get("instrumentation", []) or [])
            or [f"{fixture_id}_result.v1"]
        )
    expected_files = list(fixture.get("expected_files", []) or [])
    if not expected_files:
        expected_files = [
            f"fixtures/{fixture_id}.json",
            f"fixtures/{fixture_id}_go_no_go_trace.json",
        ]
    thresholds = list(fixture.get("acceptance_thresholds", []) or [])
    if not thresholds:
        thresholds = [
            {"metric": "fixture pass rate", "threshold": "100%"},
            {"metric": "unsafe bypass count", "threshold": "0"},
        ]
    return {
        **fixture,
        "expected_files": expected_files,
        "expected_outputs": expected_outputs,
        "acceptance_thresholds": thresholds,
        "go_no_go_trace": str(
            fixture.get("go_no_go_trace", "")
            or fixture.get("pass_fail_trace", "")
            or f"fixtures/{fixture_id}_go_no_go_trace.json"
        ),
    }


def _build_grade_artifact_payloads(
    *,
    checkout: dict[str, Any],
    deliverable_payload: dict[str, Any],
    work_order: dict[str, Any] | None = None,
    workspace: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    title = str(deliverable_payload.get("directive_title", "") or "Untitled directive")
    support_manifest = _read_child_support_manifest(checkout)
    pack_ids = _pack_ids(checkout)
    work_order_payload = dict(work_order or {})
    for ref in list(work_order_payload.get("allowed_pack_refs", []) or []):
        if isinstance(ref, dict) and str(ref.get("pack_id", "") or "").strip():
            pack_id = str(ref.get("pack_id", "") or "").strip()
            if pack_id not in pack_ids:
                pack_ids.append(pack_id)
    evidence_ref = pack_ids[0] if pack_ids else "operator_review_required"
    rows = _build_grade_rows(deliverable_payload)
    domain_rows = _domain_build_package_rows(title)
    if domain_rows:
        rows["subsystems"] = list(domain_rows.get("subsystems", rows["subsystems"]))
        rows["interfaces"] = list(domain_rows.get("interfaces", rows["interfaces"]))
        rows["dependencies"] = list(domain_rows.get("dependencies", rows["dependencies"]))
        rows["protocols"] = [
            {
                "validation_id": str(item.get("fixture_id", f"validation_{index}")),
                "name": str(item.get("purpose", f"Validation fixture {index}")),
                "directive_specific": True,
                "method": str(item.get("setup", "")),
                "acceptance_evidence": ", ".join(str(value) for value in list(item.get("instrumentation", []) or [])),
                "stop_condition": str(item.get("execution_gate", "operator_review_before_real_world_use")),
            }
            for index, item in enumerate(list(domain_rows.get("fixtures", []) or []), start=1)
        ] or rows["protocols"]
    claims = []
    for index, subsystem in enumerate(rows["subsystems"][:6], start=1):
        risk_level = "review_only" if evidence_ref == "operator_review_required" else "bounded"
        subsystem_name = str(subsystem.get("name", f"Subsystem {index}"))
        output_refs = [str(item) for item in list(subsystem.get("outputs", []) or [])]
        input_refs = [str(item) for item in list(subsystem.get("inputs", []) or [])]
        claims.append(
            {
                "claim_id": f"claim_{index}",
                "claim": (
                    f"{subsystem_name} must expose {', '.join(output_refs[:2]) or 'a named module output'} "
                    f"from {', '.join(input_refs[:2]) or 'bounded prototype inputs'} before {title} can be evaluated."
                ),
                "evidence_refs": [evidence_ref] if evidence_ref != "operator_review_required" else [],
                "confidence": "supported_by_checkout" if evidence_ref != "operator_review_required" else "unsupported",
                "risk_level": risk_level,
                "artifact_impact": "prototype_assembly_plan.json",
                "design_impact": f"Defines the build step and validation handoff for {subsystem_name}.",
                "prototype_impact": (
                    "Blocks prototype-candidate review until the named outputs, validation fixture, "
                    "and evidence ref are present."
                ),
                "unsupported_gap": (
                    "kernel-mediated synthesis pack required"
                    if evidence_ref == "operator_review_required"
                    else ""
                ),
                "authority": "review_only_until_operator_acceptance",
            }
        )
    previous_return = str(checkout.get("previous_return_packet_id", "") or "")
    work_order_id = str(work_order_payload.get("work_order_id", "") or "")
    work_order_context = str(work_order_payload.get("next_step_context", "") or "")
    novelty_items = [
        {
            "item": f"Structured subsystem/interface/dependency rows generated for {title}.",
            "compared_to": previous_return or "no_previous_return",
        },
        {
            "item": "Claims are separated from evidence and authority boundaries.",
            "compared_to": previous_return or "no_previous_return",
        },
    ]
    if work_order_id:
        novelty_items.append(
            {
                "item": f"Kernel work order {work_order_id} incorporated into resident artifact revision.",
                "compared_to": previous_return or "resident_previous_cycle",
            }
        )
    artifacts = {
        "subsystem_matrix.json": {
            "schema_name": "ConveyorSubsystemMatrix",
            "directive_title": title,
            "subsystems": rows["subsystems"],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "interface_specifications.json": {
            "schema_name": "ConveyorInterfaceSpecifications",
            "directive_title": title,
            "interfaces": rows["interfaces"],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "dependency_matrix.json": {
            "schema_name": "ConveyorDependencyMatrix",
            "directive_title": title,
            "dependencies": rows["dependencies"],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "validation_protocols.json": {
            "schema_name": "ConveyorValidationProtocols",
            "directive_title": title,
            "protocols": rows["protocols"],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "prototype_milestones.json": {
            "schema_name": "ConveyorPrototypeMilestones",
            "directive_title": title,
            "milestones": rows["milestones"],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "claim_evidence_register.json": {
            "schema_name": "ConveyorClaimEvidenceRegister",
            "directive_title": title,
            "claims": claims,
            "pack_refs": pack_ids,
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "novelty_delta.json": {
            "schema_name": "ConveyorNoveltyDelta",
            "directive_title": title,
            "previous_return_packet_id": previous_return,
            "novel_items": novelty_items,
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "bill_of_materials.json": {
            "schema_name": "ConveyorBillOfMaterials",
            "directive_title": title,
            "items": _domain_bom_items(title, rows, domain_rows),
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "prototype_assembly_plan.json": {
            "schema_name": "ConveyorPrototypeAssemblyPlan",
            "directive_title": title,
            "assembly_steps": [
                {
                    "step_id": f"assembly_{index}",
                    "name": f"Assemble {row['name']} prototype module",
                    "description": f"Integrate {row['name']} into a reversible prototype package with typed interface fixtures.",
                    "build_sequence": index,
                    "integration_dependencies": list(row.get("inputs", []) or []) + [
                        f"{row['subsystem_id']}_interface_contract",
                        f"{row['subsystem_id']}_validation_fixture",
                    ],
                    "environment_assumptions": [
                        "offline resident child workspace",
                        "read-only canonical baseline",
                        "network_policy_deny_all",
                    ],
                    "inputs": row.get("inputs", []),
                    "named_outputs": row.get("outputs", []),
                    "outputs": row.get("outputs", []),
                    "expected_files": [
                        f"fixtures/{row['subsystem_id']}_assembly_fixture.json",
                        f"fixtures/{row['subsystem_id']}_go_no_go_trace.json",
                    ],
                    "expected_outputs": list(row.get("outputs", []) or []) or [f"{row['subsystem_id']}_prototype_result.v1"],
                    "acceptance_thresholds": [
                        {"metric": "fixture pass rate", "threshold": "100%"},
                        {"metric": "unsafe bypass count", "threshold": "0"},
                    ],
                    "module_output": f"{row['subsystem_id']}_prototype_module",
                    "validation_fixture": f"fixture_{index}",
                    "validation_handoff": f"Run fixture_{index} and attach pass/fail trace before promotion.",
                    "go_no_go_trace": f"fixtures/{row['subsystem_id']}_go_no_go_trace.json",
                    "go_no_go_criteria": [
                        {"criterion": "typed inputs and outputs validate", "threshold": "100% required schema checks pass"},
                        {"criterion": "unsupported material claims", "threshold": "0 build-blocking unsupported claims"},
                    ],
                    "stop_conditions": [
                        "unsafe, clinical, invasive, deployment-sensitive, or unsupported execution request",
                    ],
                    "execution_gate": "execution_gated_by_operator_approval",
                }
                for index, row in enumerate(rows["subsystems"][:8], start=1)
            ],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "validation_fixtures.json": {
            "schema_name": "ConveyorValidationFixtures",
            "directive_title": title,
            "fixtures": [
                _validation_fixture_closure_fields(dict(fixture), index)
                for index, fixture in enumerate(
                    list(domain_rows.get("fixtures", []) or _fallback_validation_fixtures(rows)),
                    start=1,
                )
            ],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "risk_controls.json": {
            "schema_name": "ConveyorRiskControls",
            "directive_title": title,
            "controls": [
                {
                    "control_id": f"risk_control_{index}",
                    "applies_to": row["name"],
                    "risk": "real-world prototype step may require safety, clinical, privacy, or deployment review",
                    "mitigation": "keep specification actionable but mark execution as operator-gated",
                    "execution_gate": "execution_gated_by_operator_approval",
                }
                for index, row in enumerate(rows["subsystems"][:8], start=1)
            ],
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
        "implementation_readiness_review.json": {
            **_build_readiness_review(checkout=checkout, deliverable_payload=deliverable_payload),
            "resident_work_order_id": work_order_id,
            "resident_next_step_context": work_order_context,
        },
    }
    combined_operator_feedback = " ".join(
        part
        for part in (
            str(checkout.get("operator_feedback", "") or ""),
            str(work_order_payload.get("operator_feedback", "") or ""),
            str(work_order_payload.get("next_step_context", "") or ""),
        )
        if part.strip()
    )
    hardware_contract_metrics = _apply_hardware_prototype_readiness_contract(
        artifacts,
        title=title,
        work_order=work_order_payload,
        operator_feedback=combined_operator_feedback,
        support_manifest=support_manifest,
        workspace=workspace,
    )
    field_metrics = _apply_field_level_output_contract(
        artifacts,
        title=title,
        work_order=work_order_payload,
    )
    post_field_support_metrics: dict[str, Any] = {}
    if hardware_contract_metrics:
        post_field_support_metrics.update(
            _apply_operator_feedback_role_split_materialization(
                artifacts,
                operator_feedback=combined_operator_feedback,
                support_manifest=support_manifest,
            )
        )
        post_field_support_metrics.update(
            _apply_source_backed_bom_support_materialization(
                artifacts,
                support_manifest=support_manifest,
            )
        )
        post_field_support_metrics.update(
            _apply_source_backed_risk_support_materialization(
                artifacts,
                support_manifest=support_manifest,
            )
        )
        post_field_support_metrics.update(
            _apply_source_backed_validation_fixture_support_materialization(
                artifacts,
                support_manifest=support_manifest,
            )
        )
    schema_followup_metrics: dict[str, Any] = {}
    target_artifact = str(work_order_payload.get("target_artifact", "") or "")
    if target_artifact and target_artifact in artifacts:
        schema_followup_metrics = _apply_schema_resonance_followup_contract(
            artifacts[target_artifact],
            work_order_payload,
        )
    metrics = {
        "artifact_names": list(artifacts.keys()),
        "claim_count": len(claims),
        "supported_claim_count": sum(1 for item in claims if item["evidence_refs"]),
        "novelty_count": len(novelty_items),
        "directive_specific_row_count": sum(len(rows[key]) for key in rows),
    }
    if hardware_contract_metrics:
        metrics.update(hardware_contract_metrics)
    metrics.update(field_metrics)
    metrics.update(post_field_support_metrics)
    if hardware_contract_metrics and post_field_support_metrics:
        for key in (
            "source_bom_required_field_delta",
            "risk_control_required_field_delta",
            "support_to_artifact_required_field_delta",
            "support_to_artifact_delta",
        ):
            metrics[key] = bool(
                hardware_contract_metrics.get(key, False)
                or post_field_support_metrics.get(key, False)
                or metrics.get(key, False)
            )
        for key in (
            "source_bom_materialized_rows",
            "bom_closed_requested_row_ids",
            "bom_unclosed_requested_row_ids",
            "risk_control_materialized_rows",
            "missing_fmea_row_refs",
        ):
            combined: list[Any] = []
            for source in (hardware_contract_metrics, post_field_support_metrics, metrics):
                for item in list(source.get(key, []) or []):
                    if item not in combined:
                        combined.append(item)
            if combined:
                metrics[key] = combined
        combined_depth_gaps: list[Any] = []
        for source in (hardware_contract_metrics, post_field_support_metrics, metrics):
            for item in list(source.get("source_bom_unresolved_depth_fields", []) or []):
                if item not in combined_depth_gaps:
                    combined_depth_gaps.append(item)
        if combined_depth_gaps:
            metrics["source_bom_unresolved_depth_fields"] = combined_depth_gaps
    if schema_followup_metrics:
        metrics["schema_followup_contract_materialized"] = bool(
            schema_followup_metrics.get("schema_followup_contract_materialized", False)
        )
        metrics["schema_followup_materialized_top_level_fields"] = list(
            schema_followup_metrics.get("schema_followup_materialized_top_level_fields", []) or []
        )
        metrics["schema_followup_missing_top_level_fields_after_write"] = list(
            schema_followup_metrics.get("schema_followup_missing_top_level_fields_after_write", []) or []
        )
        metrics["closed_failed_gates"] = list(
            dict.fromkeys(
                list(metrics.get("closed_failed_gates", []) or [])
                + list(schema_followup_metrics.get("closed_failed_gates", []) or [])
            )
        )
        metrics["remaining_failed_gates"] = list(
            dict.fromkeys(
                list(metrics.get("remaining_failed_gates", []) or [])
                + list(schema_followup_metrics.get("remaining_failed_gates", []) or [])
            )
        )
    return artifacts, metrics


def _write_build_grade_artifacts(
    workspace: Path,
    *,
    checkout: dict[str, Any],
    deliverable_payload: dict[str, Any],
) -> dict[str, Any]:
    artifacts, metrics = _build_grade_artifact_payloads(checkout=checkout, deliverable_payload=deliverable_payload)
    for name, payload in artifacts.items():
        _write_json_artifact(workspace / name, payload)
    return metrics


def _artifact_hashes(workspace: Path, artifacts: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for artifact in artifacts:
        path = workspace / artifact
        if not path.exists() or not path.is_file():
            continue
        hashes[artifact] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _read_inbox(path: Path) -> dict[str, Any]:
    try:
        inbox_path = path / "inbox.json" if path.is_dir() else path
    except OSError as exc:
        if _is_mount_fault_error(exc):
            raise ConveyorMountFaultError("inbox", path, exc) from exc
        return {}
    try:
        payload = json.loads(inbox_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except OSError as exc:
        if _is_mount_fault_error(exc):
            raise ConveyorMountFaultError("inbox", inbox_path, exc) from exc
        return {}
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_work_order(inbox_payload: dict[str, Any]) -> dict[str, Any]:
    messages = list(inbox_payload.get("messages", []) or [])
    for message in reversed(messages):
        if isinstance(message, dict) and str(message.get("kind", "") or "") == "kernel_work_order":
            return message
    return {}


def _resident_sleep_until_wake(
    *,
    checkout: Mapping[str, Any],
    inbox: Path,
    sleep_seconds: float,
    processed_wake_sequences: set[int],
) -> dict[str, Any]:
    remaining = max(0.0, float(sleep_seconds or 0.0))
    poll_seconds = _clamped_resident_wake_poll_seconds(checkout)
    while remaining > 0:
        chunk = min(poll_seconds, remaining)
        time.sleep(chunk)
        remaining -= chunk
        inbox_payload = _read_inbox(inbox) if str(inbox) else {}
        if bool(inbox_payload.get("stop_requested", False)) or bool(inbox_payload.get("request_final_return", False)):
            return inbox_payload
        if _wake_token_is_fresh(inbox_payload, processed_wake_sequences):
            return inbox_payload
    return {}


def _checkout_recovered_work_order(checkout: dict[str, Any]) -> dict[str, Any]:
    target = str(checkout.get("initial_work_order_target_artifact", "") or "").strip()
    if target not in RESIDENT_ARTIFACT_ORDER:
        return {}
    return {
        "kind": "kernel_work_order",
        "schema_name": "ConveyorChildWorkOrder",
        "work_order_id": str(checkout.get("initial_work_order_id", "") or "checkout_recovered_work_order"),
        "child_run_id": str(checkout.get("child_run_id", "") or ""),
        "directive_id": str(checkout.get("directive_id", "") or ""),
        "capability": str(checkout.get("initial_work_order_capability", "") or "directive_build_grade_synthesis_pack"),
        "target_artifact": target,
        "next_step_context": str(
            checkout.get("initial_work_order_context", "")
            or "Recover the kernel-selected structured target from checkout metadata and continue the prototype delta."
        ),
        "previous_return_packet_id": str(checkout.get("initial_work_order_source_return_packet_id", "") or ""),
        "target_selection_reason": "checkout_structured_target_recovery",
        "initial_work_order_recovered_from_campaign_metadata": bool(
            checkout.get("initial_work_order_recovered_from_campaign_metadata", False)
        ),
        "child_output_contract": {
            "requires_evidence_refs": True,
            "requires_acceptance_tests": True,
            "requires_expected_files": True,
            "requires_go_no_go_gates": True,
            "protected_root_write_allowed": False,
            "grants_execution_authority": False,
        },
        "grants_execution_authority": False,
        "network_policy": "deny_all",
        "kernel_mediated_only": True,
    }


def _resident_required_artifacts(checkout: dict[str, Any]) -> list[str]:
    contract = checkout.get("build_grade_contract", {})
    required = []
    if isinstance(contract, dict):
        required = [str(item) for item in list(contract.get("required_artifacts", []) or [])]
    ordered = [artifact for artifact in RESIDENT_ARTIFACT_ORDER if artifact in set(required)]
    for artifact in RESIDENT_ARTIFACT_ORDER:
        if artifact not in ordered and (not required or artifact in required):
            ordered.append(artifact)
    return ordered or list(RESIDENT_ARTIFACT_ORDER)


def _resident_missing_required_return_artifacts(checkout: dict[str, Any], artifact_root: Path) -> list[str]:
    return [
        artifact
        for artifact in _resident_required_artifacts(checkout)
        if not (artifact_root / artifact).exists()
    ]


def _select_resident_target_artifact(
    *,
    checkout: dict[str, Any],
    workspace: Path,
    cycle_index: int,
    work_order: dict[str, Any],
) -> str:
    requested = str(work_order.get("target_artifact", "") or "").strip()
    if requested in RESIDENT_ARTIFACT_ORDER:
        return requested
    required = _resident_required_artifacts(checkout)
    for artifact in required:
        if not (workspace / artifact).exists():
            return artifact
    return required[(max(1, int(cycle_index)) - 1) % len(required)]


def _file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _campaign_workspace(checkout: dict[str, Any]) -> dict[str, Any]:
    workspace = checkout.get("campaign_workspace", {})
    return dict(workspace) if isinstance(workspace, dict) else {}


def _resident_artifact_root(checkout: dict[str, Any], fallback_workspace: Path) -> Path:
    campaign = _campaign_workspace(checkout)
    draft_path = str(campaign.get("draft_path", "") or "").strip()
    if draft_path:
        return Path(draft_path)
    return fallback_workspace


def _artifact_path_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if path.exists():
        try:
            with path.open("r+b"):
                return True
        except OSError:
            return False
    probe = path.parent / f".novali-write-probe-{os.getpid()}-{int(time.time() * 1000)}"
    try:
        probe.write_text("ok", encoding="utf-8")
        return True
    except OSError:
        return False
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def _canonical_artifact_hash(checkout: dict[str, Any], artifact_name: str) -> str:
    campaign = _campaign_workspace(checkout)
    artifacts = campaign.get("canonical_artifacts", {})
    if isinstance(artifacts, dict):
        artifact = artifacts.get(artifact_name, {})
        if isinstance(artifact, dict) and str(artifact.get("sha256", "") or "").strip():
            return str(artifact.get("sha256", "")).strip()
    canonical_path = str(campaign.get("canonical_path", "") or "").strip()
    if canonical_path:
        return _file_hash(Path(canonical_path) / artifact_name)
    return ""


def _work_order_with_checkout_depth_context(
    work_order: Mapping[str, Any],
    checkout: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(work_order or {})
    for key in (
        "depth_missing_fields",
        "missing_field_coverage",
        "support_covered_missing_fields",
        "support_uncovered_missing_fields",
        "operator_feedback_obligation_gaps",
        "operator_feedback",
    ):
        if key not in merged or merged.get(key) in ("", [], {}, None):
            value = checkout.get(key)
            if value not in ("", [], {}, None):
                merged[key] = value
    return merged


def _fixture_support_fast_path_metrics(
    *,
    checkout: dict[str, Any],
    workspace: Path,
    target_artifact: str,
    deliverable_payload: Mapping[str, Any],
    work_order: Mapping[str, Any],
) -> dict[str, Any] | None:
    if target_artifact != "validation_fixtures.json":
        return None
    support_manifest = _read_child_support_manifest(checkout)
    fixture_support_rows = [
        row
        for row in _support_manifest_rows(support_manifest)
        if isinstance(row, Mapping)
        and str(row.get("target_artifact", "") or "").strip() == "validation_fixtures.json"
    ]
    if not any(_source_support_row_has_validation_fixture_required_fields(row) for row in fixture_support_rows):
        return None

    artifact_path = workspace / target_artifact
    payload: dict[str, Any] = {}
    if artifact_path.is_file():
        try:
            existing_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_payload = {}
        if isinstance(existing_payload, Mapping):
            payload = dict(existing_payload)
    if not payload:
        payload = {
            "schema_name": "ConveyorValidationFixtures",
            "directive_title": str(deliverable_payload.get("directive_title", "") or ""),
            "fixtures": [],
        }
    payload.setdefault("schema_name", "ConveyorValidationFixtures")
    payload.setdefault("directive_title", str(deliverable_payload.get("directive_title", "") or ""))
    payload.setdefault("resident_work_order_id", str(work_order.get("work_order_id", "") or ""))
    payload.setdefault("resident_next_step_context", str(work_order.get("next_step_context", "") or ""))
    payload.setdefault("fixtures", [])

    metrics = _apply_source_backed_validation_fixture_support_materialization(
        {target_artifact: payload},
        support_manifest=support_manifest,
    )
    state = str(metrics.get("validation_fixture_materialization_state", "") or "")
    if state not in {"materialized", "partial"}:
        return None
    _write_json_artifact(artifact_path, payload)
    fixture_rows = [row for row in list(payload.get("fixtures", []) or []) if isinstance(row, Mapping)]
    feedback_assessment = assess_operator_feedback_obligations(
        " ".join(
            part
            for part in (
                str(checkout.get("operator_feedback", "") or ""),
                str(work_order.get("operator_feedback", "") or ""),
                str(work_order.get("next_step_context", "") or ""),
            )
            if part.strip()
        ),
        payloads={target_artifact: payload},
    )
    remaining_failed_gates = ["linked_hardware_dossier_not_complete"]
    if int(feedback_assessment.get("operator_feedback_obligation_gap_count", 0) or 0):
        remaining_failed_gates.append("operator_feedback_obligation_unresolved")
    return {
        "claim_count": 0,
        "novelty_count": 0,
        "directive_specific_row_count": len(fixture_rows),
        "support_pack_refs_used": _pack_ids(checkout),
        "hardware_prototype_contract_applied": True,
        "hardware_build_packet_contract_applied": True,
        "hardware_build_packet_ready_candidate": False,
        "technical_depth_contract_passed": False,
        "strict_hardware_contract_passed": False,
        "required_hardware_artifacts_present": False,
        "remaining_failed_gates": remaining_failed_gates,
        "hardware_readiness_blockers": ["validation_fixture_closure_review_only"],
        "validation_fixture_fast_path_used": True,
        **feedback_assessment,
        **metrics,
    }


def _implementation_readiness_visible_dossier_fast_path_metrics(
    *,
    checkout: dict[str, Any],
    workspace: Path,
    target_artifact: str,
    deliverable_payload: Mapping[str, Any],
    work_order: Mapping[str, Any],
) -> dict[str, Any] | None:
    if target_artifact != "implementation_readiness_review.json":
        return None

    artifact_row_keys = {
        "interface_specifications.json": ("interfaces",),
        "bill_of_materials.json": ("items",),
        "risk_controls.json": ("controls", "risk_controls"),
        "validation_fixtures.json": ("fixtures",),
        "device_capability_manifest.json": ("capabilities", "declared_channels"),
        "prototype_assembly_plan.json": ("assembly_steps", "steps"),
    }
    required = [
        "interface_specifications.json",
        "bill_of_materials.json",
        "risk_controls.json",
        "validation_fixtures.json",
    ]
    optional = ["device_capability_manifest.json", "prototype_assembly_plan.json"]

    def _read_visible_payload(artifact_name: str) -> dict[str, Any]:
        path = workspace / artifact_name
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _visible_row_count(artifact_name: str, payload: Mapping[str, Any]) -> int:
        for key in artifact_row_keys.get(artifact_name, ()):
            value = payload.get(key)
            if isinstance(value, list):
                return len([row for row in value if isinstance(row, Mapping)])
        return 1 if payload else 0

    visible_payloads = {
        artifact: payload
        for artifact in [*required, *optional]
        if (payload := _read_visible_payload(artifact))
    }
    if not any(artifact in visible_payloads for artifact in required):
        return None
    used = [artifact for artifact in [*required, *optional] if artifact in visible_payloads]
    missing = [artifact for artifact in required if artifact not in visible_payloads]
    row_counts = {
        artifact: _visible_row_count(artifact, payload)
        for artifact, payload in visible_payloads.items()
    }
    incomplete = [
        artifact
        for artifact in required
        if artifact in visible_payloads and row_counts.get(artifact, 0) <= 0
    ]
    closure_state = (
        "visible_closure_reviewable"
        if not missing and not incomplete
        else "visible_closure_incomplete"
    )
    gate_summary = {
        "required_artifacts_present": not missing,
        "visible_artifact_count": len(used),
        "visible_required_artifact_count": len([artifact for artifact in required if artifact in visible_payloads]),
        "visible_row_counts": row_counts,
        "missing_required_artifacts": missing,
        "incomplete_required_artifacts": incomplete,
    }
    review_payload = {
        **_build_readiness_review(checkout=checkout, deliverable_payload=dict(deliverable_payload)),
        "resident_work_order_id": str(work_order.get("work_order_id", "") or ""),
        "resident_next_step_context": str(work_order.get("next_step_context", "") or ""),
        "implementation_readiness_fast_path_used": True,
        "visible_dossier_artifacts_used": used,
        "visible_dossier_missing_artifacts": missing,
        "visible_dossier_incomplete_artifacts": incomplete,
        "visible_dossier_closure_state": closure_state,
        "visible_dossier_gate_summary": gate_summary,
        "execution_gated_by_operator_approval": True,
        "grants_execution_authority": False,
        "implementation_authority": "not_granted_by_child_return",
        "hardware_build_packet_ready_candidate": False,
        "hardware_prototype_contract": {
            "contract_kind": "review_only_hardware_prototype_readiness",
            "execution_gated_by_operator_approval": True,
            "grants_execution_authority": False,
            "required_artifacts": required,
            "review_mode": "visible_dossier_incremental_review",
        },
    }
    _write_json_artifact(workspace / target_artifact, review_payload)
    remaining_failed_gates = ["operator_review_required", "implementation_readiness_review_only"]
    if missing or incomplete:
        remaining_failed_gates.append("linked_hardware_dossier_not_complete")
    return {
        "claim_count": 0,
        "novelty_count": 0,
        "directive_specific_row_count": sum(row_counts.values()),
        "support_pack_refs_used": _pack_ids(checkout),
        "hardware_prototype_contract_applied": True,
        "hardware_build_packet_contract_applied": True,
        "hardware_build_packet_ready_candidate": False,
        "technical_depth_contract_passed": False,
        "strict_hardware_contract_passed": False,
        "required_hardware_artifacts_present": bool(not missing and not incomplete),
        "remaining_failed_gates": remaining_failed_gates,
        "hardware_readiness_blockers": remaining_failed_gates,
        "implementation_readiness_fast_path_used": True,
        "implementation_readiness_visible_dossier_artifacts_used": used,
        "implementation_readiness_visible_dossier_missing_artifacts": missing,
        "implementation_readiness_visible_dossier_incomplete_artifacts": incomplete,
        "visible_dossier_closure_state": closure_state,
        "visible_dossier_gate_summary": gate_summary,
    }


def _write_resident_artifact(
    *,
    checkout: dict[str, Any],
    workspace: Path,
    target_artifact: str,
    work_order: dict[str, Any],
) -> dict[str, Any]:
    from .directive_candidates import materialize_checkout
    try:
        revision = materialize_checkout(checkout, workspace, target_artifact)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return {'claim_count': 0, 'novelty_count': 0, 'technical_depth_contract_passed': False,
                'remaining_failed_gates': ['reviewed_child_revision_requires_reassessment:' + str(exc)]}
    if revision is not None:
        return revision
    directive_text = str(checkout.get("directive_text", "") or "")
    deliverable_payload = _resident_deliverable_payload(checkout, directive_text)
    work_order_context = str(work_order.get("next_step_context", "") or "")
    hardware_contract = work_order.get("hardware_prototype_readiness_contract", {})
    hardware_contract_present = isinstance(hardware_contract, dict) and bool(hardware_contract)
    if target_artifact == "technical_documentation.md":
        _write_technical_documentation(
            workspace / target_artifact,
            checkout=checkout,
            deliverable_payload=deliverable_payload,
        )
        hardware_interface_requested = _hardware_interface_doc_requested(work_order_context, directive_text)
        if hardware_interface_requested:
            _append_hardware_interface_feasibility_sections(
                workspace / target_artifact,
                work_order_id=str(work_order.get("work_order_id", "") or ""),
            )
        if work_order_context and not hardware_interface_requested:
            with (workspace / target_artifact).open("a", encoding="utf-8") as handle:
                handle.write("\n## Kernel Work Order Context\n")
                handle.write(f"- Work order: {str(work_order.get('work_order_id', '') or 'kernel_context')}\n")
                handle.write(f"- Requested next step: {work_order_context}\n")
        return {"claim_count": 0, "novelty_count": 0, "support_pack_refs_used": _pack_ids(checkout)}
    if target_artifact == "directive_deliverables.json":
        _write_json_artifact(workspace / target_artifact, deliverable_payload)
        return {"claim_count": 0, "novelty_count": 0, "support_pack_refs_used": _pack_ids(checkout)}
    if target_artifact == "directive_blueprint.md":
        _write_directive_blueprint(workspace / target_artifact, deliverable_payload)
        return {"claim_count": 0, "novelty_count": 0, "support_pack_refs_used": _pack_ids(checkout)}
    if target_artifact == "implementation_readiness_review.json" and not hardware_contract_present:
        _write_json_artifact(
            workspace / target_artifact,
            _build_readiness_review(checkout=checkout, deliverable_payload=deliverable_payload),
        )
        return {"claim_count": 0, "novelty_count": 0, "support_pack_refs_used": _pack_ids(checkout)}
    fast_fixture_metrics = _fixture_support_fast_path_metrics(
        checkout=checkout,
        workspace=workspace,
        target_artifact=target_artifact,
        deliverable_payload=deliverable_payload,
        work_order=work_order,
    )
    if fast_fixture_metrics is not None:
        return fast_fixture_metrics
    readiness_fast_path_metrics = _implementation_readiness_visible_dossier_fast_path_metrics(
        checkout=checkout,
        workspace=workspace,
        target_artifact=target_artifact,
        deliverable_payload=deliverable_payload,
        work_order=work_order,
    )
    if readiness_fast_path_metrics is not None:
        return readiness_fast_path_metrics
    payloads, metrics = _build_grade_artifact_payloads(
        checkout=checkout,
        deliverable_payload=deliverable_payload,
        work_order=work_order,
        workspace=workspace,
    )
    payload = payloads.get(target_artifact)
    if payload is None:
        payload = {
            "schema_name": "ConveyorResidentArtifactRevision",
            "directive_title": deliverable_payload.get("directive_title", ""),
            "target_artifact": target_artifact,
            "work_order_id": str(work_order.get("work_order_id", "") or ""),
            "next_step_context": work_order_context,
        }
    if target_artifact == "interface_specifications.json":
        _merge_existing_interface_artifact_rows(payload, workspace / target_artifact)
    if target_artifact == "bill_of_materials.json":
        _merge_existing_json_artifact_rows(
            payload,
            workspace / target_artifact,
            artifact_name=target_artifact,
        )
    if hardware_contract_present:
        for artifact_name in [
            "device_capability_manifest.json",
            "bill_of_materials.json",
            "validation_fixtures.json",
            "risk_controls.json",
            "implementation_readiness_review.json",
            "prototype_assembly_plan.json",
            "interface_specifications.json",
            *FULL_DIVE_HARDWARE_DOCUMENTATION_ARTIFACTS,
        ]:
            artifact_payload = payloads.get(artifact_name)
            if artifact_payload is not None:
                _write_json_artifact(workspace / artifact_name, artifact_payload)
        metrics.update(_materialize_hardware_build_packet_files(workspace, payloads=payloads))
        if not bool(metrics.get("technical_depth_contract_passed", True)):
            metrics["hardware_build_packet_ready_candidate"] = False
            metrics["remaining_failed_gates"] = list(
                dict.fromkeys(
                    [
                        *list(metrics.get("remaining_failed_gates", []) or []),
                        "technical_depth_contract_generic_placeholders",
                    ]
                )
            )
    else:
        _write_json_artifact(workspace / target_artifact, payload)
    metrics.update(
        _full_dive_hardware_readiness_metrics(
            checkout=checkout,
            work_order=work_order,
            workspace=workspace,
            payloads=payloads,
        )
    )
    support_manifest = _read_child_support_manifest(checkout)
    design_work_order = _work_order_with_checkout_depth_context(work_order, checkout)
    design_metrics = _apply_technology_design_obligation_artifact(
        payload,
        target_artifact=target_artifact,
        work_order=design_work_order,
        support_manifest=support_manifest,
    )
    if design_metrics:
        existing_failed = list(metrics.get("remaining_failed_gates", []) or [])
        incoming_failed = list(design_metrics.get("remaining_failed_gates", []) or [])
        existing_blockers = list(metrics.get("hardware_readiness_blockers", []) or [])
        incoming_blockers = list(design_metrics.get("hardware_readiness_blockers", []) or [])
        metrics.update(design_metrics)
        metrics["remaining_failed_gates"] = list(dict.fromkeys([*existing_failed, *incoming_failed]))
        metrics["hardware_readiness_blockers"] = list(dict.fromkeys([*existing_blockers, *incoming_blockers]))
        metrics["hardware_build_packet_ready_candidate"] = False
        metrics["technical_depth_contract_passed"] = False
        metrics["strict_hardware_contract_passed"] = False
        _write_json_artifact(workspace / target_artifact, payload)
    feedback_assessment = assess_operator_feedback_obligations(
        " ".join(
            part
            for part in (
                str(checkout.get("operator_feedback", "") or ""),
                str(work_order.get("operator_feedback", "") or ""),
                str(work_order_context or ""),
            )
            if part.strip()
        ),
        payloads=payloads,
    )
    if int(feedback_assessment.get("operator_feedback_obligation_gap_count", 0) or 0):
        metrics.update(feedback_assessment)
        metrics["hardware_build_packet_ready_candidate"] = False
        metrics["technical_depth_contract_passed"] = False
        metrics["remaining_failed_gates"] = list(
            dict.fromkeys(
                [
                    *list(metrics.get("remaining_failed_gates", []) or []),
                    "operator_feedback_obligation_unresolved",
                ]
            )
        )
    elif "operator_feedback_obligation_passed" not in metrics:
        metrics.update(feedback_assessment)
    metrics["support_pack_refs_used"] = _pack_ids(checkout)
    return metrics


def _write_resident_progress_checkpoint(
    *,
    checkout: dict[str, Any],
    workspace: Path,
    progress_root: Path,
    cycle_index: int,
    progress_state: str = "working",
    inbox_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    generated_at = _utc_now()
    workspace.mkdir(parents=True, exist_ok=True)
    progress_root.mkdir(parents=True, exist_ok=True)
    artifact_root = _resident_artifact_root(checkout, workspace)
    artifact_root.mkdir(parents=True, exist_ok=True)
    child_run_id = str(checkout.get("child_run_id", "") or "unknown-child")
    directive_id = str(checkout.get("directive_id", "") or "")
    directive_text = str(checkout.get("directive_text", "") or "")
    work_order = _latest_work_order(dict(inbox_payload or {}))
    work_order_missing_recovered = False
    if not work_order:
        work_order = _checkout_recovered_work_order(checkout)
        work_order_missing_recovered = bool(work_order)
    wake_request = _wake_request_from_inbox(inbox_payload or {})
    wake_token_observed = bool(
        wake_request
        and str(wake_request.get("wake_work_order_id", "") or "") == str(work_order.get("work_order_id", "") or "")
    )
    wake_latency = (
        _wake_latency_seconds(wake_request.get("wake_requested_at", ""), generated_at)
        if wake_token_observed
        else None
    )
    target_artifact = _select_resident_target_artifact(
        checkout=checkout,
        workspace=artifact_root,
        cycle_index=cycle_index,
        work_order=work_order,
    )
    requested_artifact_root = artifact_root
    requested_artifact_path = requested_artifact_root / target_artifact
    artifact_root_fallback: dict[str, Any] = {}
    if requested_artifact_root != workspace and not _artifact_path_writable(requested_artifact_path):
        fallback_artifact_path = workspace / target_artifact
        fallback_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if requested_artifact_path.exists() and requested_artifact_path.is_file() and not fallback_artifact_path.exists():
            try:
                shutil.copy2(requested_artifact_path, fallback_artifact_path)
            except OSError:
                pass
        artifact_root = workspace
        artifact_root_fallback = {
            "resident_artifact_root_fallback": True,
            "resident_artifact_root_fallback_reason": "campaign_draft_target_not_writable",
            "resident_requested_artifact_root": str(requested_artifact_root),
            "resident_effective_artifact_root": str(artifact_root),
        }
    _write_child_phase_heartbeat(
        progress_root,
        child_run_id=child_run_id,
        directive_id=directive_id,
        cycle_index=cycle_index,
        target_artifact=target_artifact,
        phase="startup",
        phase_event="begin",
    )
    artifact_path = artifact_root / target_artifact
    before_hash = _file_hash(artifact_path)
    canonical_before_hash = _canonical_artifact_hash(checkout, target_artifact)
    metrics: dict[str, Any] = {}
    blocked_reason = ""
    compute_policy = _local_child_compute_policy(checkout)
    child_compute_mode = str(compute_policy.get("child_compute_mode", "") or "single_pass")
    support_manifest = _read_child_support_manifest(checkout)
    support_pack_rows_read = _support_manifest_row_count(support_manifest)
    support_pack_consumable_count = _support_manifest_int(support_manifest, "support_pack_consumable_count")
    support_pack_non_consumable_count = _support_manifest_int(support_manifest, "support_pack_non_consumable_count")
    compute_pass_count = 0
    artifact_rows_generated = 0
    artifact_rows_revised = 0
    compute_budget_exhausted = False
    child_activity_state = "blocked" if progress_state != "working" else "generating"
    compute_phase_sequence: list[str] = []
    if progress_state == "working":
        for phase in ("load_support", "parse_feedback_obligations", "plan_artifact_delta"):
            compute_phase_sequence.append(phase)
            _log_child_compute_phase(child_run_id, phase, target_artifact=target_artifact)
            _write_child_phase_heartbeat(
                progress_root,
                child_run_id=child_run_id,
                directive_id=directive_id,
                cycle_index=cycle_index,
                target_artifact=target_artifact,
                phase=phase,
                phase_event="begin",
            )
            _write_child_phase_heartbeat(
                progress_root,
                child_run_id=child_run_id,
                directive_id=directive_id,
                cycle_index=cycle_index,
                target_artifact=target_artifact,
                phase=phase,
                phase_event="end",
            )
        phase = "synthesize_rows"
        compute_phase_sequence.append(phase)
        _log_child_compute_phase(child_run_id, phase, target_artifact=target_artifact)
        _write_child_phase_heartbeat(
            progress_root,
            child_run_id=child_run_id,
            directive_id=directive_id,
            cycle_index=cycle_index,
            target_artifact=target_artifact,
            phase=phase,
            phase_event="begin",
        )
        _write_resident_startup_progress_checkpoint(
            progress_root,
            child_run_id=child_run_id,
            directive_id=directive_id,
            cycle_index=cycle_index,
            target_artifact=target_artifact,
            phase=phase,
        )
        metrics = _write_resident_artifact(
            checkout=checkout,
            workspace=artifact_root,
            target_artifact=target_artifact,
            work_order=work_order,
        )
        metrics.update(artifact_root_fallback)
        _write_child_phase_heartbeat(
            progress_root,
            child_run_id=child_run_id,
            directive_id=directive_id,
            cycle_index=cycle_index,
            target_artifact=target_artifact,
            phase=phase,
            phase_event="end",
        )
        compute_pass_count = 1
        if child_compute_mode == "local_depth_worker" and not metrics.get('reviewed_child_revision_consumed'):
            requested_passes = int(compute_policy.get("child_compute_max_passes", 1) or 1)
            unresolved = bool(
                metrics.get("remaining_failed_gates")
                or not bool(metrics.get("technical_depth_contract_passed", True))
                or not bool(metrics.get("operator_feedback_obligation_passed", True))
            )
            if support_pack_rows_read or unresolved:
                compute_pass_count = min(requested_passes, max(2, compute_pass_count))
            annotations = _annotate_artifact_with_support_refs(
                artifact_path,
                support_manifest=support_manifest,
                pass_count=compute_pass_count,
            )
            artifact_rows_generated = int(annotations.get("artifact_rows_generated", 0) or 0)
            artifact_rows_revised = int(annotations.get("artifact_rows_revised", 0) or 0)
        else:
            artifact_rows_generated = int(metrics.get("directive_specific_row_count", 0) or 0)
        for phase in ("validate_contracts", "write_artifacts"):
            compute_phase_sequence.append(phase)
            _log_child_compute_phase(child_run_id, phase, target_artifact=target_artifact)
            _write_child_phase_heartbeat(
                progress_root,
                child_run_id=child_run_id,
                directive_id=directive_id,
                cycle_index=cycle_index,
                target_artifact=target_artifact,
                phase=phase,
                phase_event="begin",
            )
            _write_child_phase_heartbeat(
                progress_root,
                child_run_id=child_run_id,
                directive_id=directive_id,
                cycle_index=cycle_index,
                target_artifact=target_artifact,
                phase=phase,
                phase_event="end",
            )
    else:
        blocked_reason = progress_state
    after_hash = _file_hash(artifact_path)
    cycle_wall_seconds = max(0.0, time.perf_counter() - wall_start)
    cycle_process_cpu_seconds = max(0.0, time.process_time() - cpu_start)
    if cycle_wall_seconds >= float(compute_policy.get("child_compute_budget_seconds", 45.0) or 45.0):
        compute_budget_exhausted = True
    draft_changed_this_cycle = bool(after_hash and ((not before_hash) or before_hash != after_hash))
    draft_differs_from_canonical = bool(canonical_before_hash and after_hash and after_hash != canonical_before_hash)
    if not draft_changed_this_cycle:
        delta_kind = "unchanged_blocked"
    elif before_hash:
        delta_kind = "revised"
    elif after_hash:
        delta_kind = "created"
    else:
        delta_kind = "unchanged_blocked"
    if canonical_before_hash:
        canonical_delta_kind = "differs_from_canonical" if draft_differs_from_canonical else "matches_canonical"
    else:
        canonical_delta_kind = "no_canonical_baseline"
    meaningful_delta = draft_changed_this_cycle
    if not meaningful_delta and not blocked_reason:
        blocked_reason = "no_artifact_delta"
    artifact_delta_count = 1 if meaningful_delta else 0
    artifact_delta_names = [target_artifact] if meaningful_delta else []
    current_step = "revise_" + re.sub(r"[^a-z0-9]+", "_", target_artifact.lower()).strip("_")
    try:
        next_wake_seconds = int(float(checkout.get("resident_cycle_sleep_seconds", 0) or 0))
    except (TypeError, ValueError):
        next_wake_seconds = 0
    if cycle_index <= 1:
        try:
            first_wake = int(float(checkout.get("resident_first_cycle_sleep_seconds", 0) or 0))
        except (TypeError, ValueError):
            first_wake = 0
        if first_wake > 0:
            next_wake_seconds = first_wake
    artifact_delta = {
        "artifact_name": target_artifact,
        "delta_kind": delta_kind,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "canonical_before_hash": canonical_before_hash,
        "canonical_delta_kind": canonical_delta_kind,
        "draft_changed_this_cycle": draft_changed_this_cycle,
        "draft_differs_from_canonical": draft_differs_from_canonical,
        "draft_path": target_artifact,
        "claim_count": int(metrics.get("claim_count", 0) or 0),
        "novelty_count": int(metrics.get("novelty_count", 0) or 0),
    }
    remaining_failed_gates = list(metrics.get("remaining_failed_gates", []) or [])
    missing_materialized = list(metrics.get("missing_materialized_expected_files_after_write", []) or [])
    missing_required_return_artifacts = _resident_missing_required_return_artifacts(checkout, artifact_root)
    return_policy = dict(checkout.get("return_policy", {}) or {})
    self_final_blockers: list[str] = []
    hardware_build_packet_ready = bool(metrics.get("hardware_build_packet_ready_candidate", False))
    full_dive_context = _is_full_dive_hardware_context(checkout, work_order)
    depth_obligation_id = str(work_order.get("depth_obligation_id", "") or checkout.get("depth_obligation_id", "") or "")
    target_delta_required = bool(
        work_order.get("target_delta_required", False)
        or checkout.get("target_delta_required", False)
        or depth_obligation_id
    )
    depth_target_artifact = str(
        work_order.get("depth_target_artifact", "")
        or checkout.get("depth_target_artifact", "")
        or target_artifact
    )
    hardware_readiness_tier = str(metrics.get("hardware_readiness_tier", "") or "")
    hardware_readiness_blockers = [
        str(item)
        for item in list(metrics.get("hardware_readiness_blockers", []) or [])
        if str(item).strip()
    ]
    strict_hardware_contract_passed = bool(metrics.get("strict_hardware_contract_passed", hardware_build_packet_ready))
    required_hardware_artifacts_present = bool(metrics.get("required_hardware_artifacts_present", hardware_build_packet_ready))
    technical_depth_contract_passed = bool(metrics.get("technical_depth_contract_passed", hardware_build_packet_ready))
    full_dive_human_subject_blocked = bool(metrics.get("full_dive_human_subject_blocked", False))
    operator_feedback_obligation_passed = bool(
        metrics.get("operator_feedback_obligation_passed", True)
    )
    technology_design_obligation_active = bool(
        metrics.get("technology_design_obligation_active", False)
        or work_order.get("technology_design_mode", "")
    )
    technology_design_obligation_ids = [
        str(item)
        for item in list(metrics.get("technology_design_obligation_ids", []) or [])
        if str(item).strip()
    ]
    if technology_design_obligation_active:
        hardware_build_packet_ready = False
        technical_depth_contract_passed = False
        strict_hardware_contract_passed = False
        if "technology_design_obligation_not_reduced_to_build_evidence" not in remaining_failed_gates:
            remaining_failed_gates.append("technology_design_obligation_not_reduced_to_build_evidence")
    required_artifacts_for_readiness = {
        str(item)
        for item in list(dict(checkout.get("build_grade_contract", {}) or {}).get("required_artifacts", []) or [])
        if str(item).strip()
    }
    linked_hardware_dossier_artifacts = {
        "interface_specifications.json",
        "bill_of_materials.json",
        "validation_fixtures.json",
        "risk_controls.json",
    }
    if (
        target_artifact == "risk_controls.json"
        and str(metrics.get("risk_control_materialization_state", "") or "") == "materialized"
        and not linked_hardware_dossier_artifacts.issubset(required_artifacts_for_readiness)
    ):
        hardware_build_packet_ready = False
        strict_hardware_contract_passed = False
        technical_depth_contract_passed = False
        if "linked_hardware_dossier_not_complete" not in remaining_failed_gates:
            remaining_failed_gates.append("linked_hardware_dossier_not_complete")
    support_required_missing_fields = _depth_missing_fields_for_target(
        checkout=checkout,
        work_order=work_order,
        metrics=metrics,
        target_artifact=target_artifact,
    )
    support_adequacy = assess_support_field_coverage(
        support_manifest,
        target_artifact=target_artifact,
        required_fields=support_required_missing_fields,
    )
    if (
        target_artifact == "validation_fixtures.json"
        and str(metrics.get("validation_fixture_materialization_state", "") or "") == "materialized"
    ):
        derived_fixture_fields = {"expected_file", "expected_outputs", "go_no_go_trace"}
        uncovered = {
            str(item)
            for item in list(support_adequacy.get("support_uncovered_missing_fields", []) or [])
            if str(item).strip()
        }
        if uncovered and uncovered.issubset(derived_fixture_fields):
            covered = list(support_adequacy.get("support_covered_missing_fields", []) or [])
            support_adequacy = {
                **dict(support_adequacy),
                "support_adequacy_state": "adequate",
                "support_covered_missing_fields": list(
                    dict.fromkeys([*covered, *sorted(uncovered)])
                ),
                "support_uncovered_missing_fields": [],
                "validation_fixture_derived_fields_closed": sorted(uncovered),
            }
    support_adequacy_state = str(support_adequacy.get("support_adequacy_state", "") or "")
    support_uncovered_missing_fields = [
        str(item)
        for item in list(support_adequacy.get("support_uncovered_missing_fields", []) or [])
        if str(item).strip()
    ]
    operator_feedback_text = str(checkout.get("operator_feedback", "") or "").lower()
    feedback_forbids_return = "do not return" in operator_feedback_text or "must not return" in operator_feedback_text
    operator_requires_concrete_delta = bool(
        (feedback_forbids_return and "delta" in operator_feedback_text)
        or "concrete hardware-depth delta" in operator_feedback_text
        or "concrete build-grade delta" in operator_feedback_text
        or (feedback_forbids_return and "generic hardware packet" in operator_feedback_text)
        or (feedback_forbids_return and "generic build-readiness" in operator_feedback_text)
        or (feedback_forbids_return and "generic build readiness" in operator_feedback_text)
        or (feedback_forbids_return and "no meaningful" in operator_feedback_text)
        or ("return only when" in operator_feedback_text and "prototyped safely today" in operator_feedback_text)
    )
    if str(return_policy.get("operator_review_gate", "") or "") != "review_worthy_milestone":
        self_final_blockers.append("return_policy_not_review_worthy_milestone")
    if progress_state != "working":
        self_final_blockers.append("progress_state_not_working")
    if blocked_reason and not (
        str(blocked_reason) == "no_artifact_delta"
        and hardware_build_packet_ready
        and not operator_requires_concrete_delta
    ):
        self_final_blockers.append(str(blocked_reason))
    if operator_requires_concrete_delta and not meaningful_delta:
        self_final_blockers.append("operator_feedback_requires_concrete_delta")
    if target_delta_required and (not meaningful_delta or depth_target_artifact != target_artifact):
        self_final_blockers.append("depth_obligation_requires_post_obligation_target_delta")
    if full_dive_context and not meaningful_delta:
        self_final_blockers.append("full_dive_requires_post_feedback_delta")
    if full_dive_context and not strict_hardware_contract_passed:
        self_final_blockers.append("strict_full_dive_hardware_contract_not_passed")
    if not technical_depth_contract_passed:
        self_final_blockers.append("technical_depth_contract_generic_placeholders")
    if not operator_feedback_obligation_passed:
        self_final_blockers.append("operator_feedback_obligation_unresolved")
    if support_adequacy_state == "insufficient_field_coverage":
        self_final_blockers.append("support_adequacy_insufficient_field_coverage")
    if technology_design_obligation_active:
        self_final_blockers.append("technology_design_obligation_not_reduced_to_build_evidence")
    if full_dive_context and not required_hardware_artifacts_present:
        self_final_blockers.append("missing_full_dive_hardware_documentation_artifacts")
    if full_dive_human_subject_blocked:
        self_final_blockers.append("full_dive_human_subject_scope_blocked")
    if not hardware_build_packet_ready:
        self_final_blockers.append("hardware_build_packet_not_ready")
    if remaining_failed_gates:
        self_final_blockers.append("remaining_failed_gates")
    if missing_materialized:
        self_final_blockers.append("missing_materialized_expected_files")
    if missing_required_return_artifacts:
        self_final_blockers.append("missing_required_return_artifacts")
    resident_self_final_return_eligible = not self_final_blockers
    if resident_self_final_return_eligible:
        sleep_reason = "final_return_ready"
        child_activity_state = "returning"
    elif support_adequacy_state == "insufficient_field_coverage" and child_compute_mode == "local_depth_worker":
        sleep_reason = "waiting_for_field_covering_support_evidence"
        child_activity_state = "sleeping"
    elif not bool(support_pack_rows_read) and child_compute_mode == "local_depth_worker":
        sleep_reason = "waiting_for_support_pack_evidence"
        child_activity_state = "sleeping"
    elif self_final_blockers:
        sleep_reason = "blocked_by_gates"
        child_activity_state = "sleeping"
    elif compute_budget_exhausted:
        sleep_reason = "compute_budget_exhausted"
        child_activity_state = "sleeping"
    else:
        sleep_reason = "waiting_for_next_resident_wake"
        child_activity_state = "sleeping"
    support_request_candidate: dict[str, Any] = {}
    if child_compute_mode == "local_depth_worker" and (
        self_final_blockers or not operator_feedback_obligation_passed
    ):
        if support_adequacy_state == "insufficient_field_coverage":
            support_request_candidate = {
                "request_type": "knowledge_checkout",
                "capability": str(work_order.get("capability", "") or checkout.get("initial_work_order_capability", "") or "directive_build_grade_synthesis_pack"),
                "target_artifact": target_artifact,
                "reason": "mounted_support_missing_required_field_coverage",
                "missing_field_coverage": list(support_uncovered_missing_fields),
                "support_covered_missing_fields": list(support_adequacy.get("support_covered_missing_fields", []) or []),
                "grants_execution_authority": False,
            }
        elif not support_pack_rows_read:
            support_request_candidate = {
                "request_type": "knowledge_checkout",
                "capability": str(work_order.get("capability", "") or checkout.get("initial_work_order_capability", "") or "directive_build_grade_synthesis_pack"),
                "target_artifact": target_artifact,
                "reason": f"Local child compute found no consumable source-backed support rows for {target_artifact}.",
                "grants_execution_authority": False,
            }
        elif not operator_feedback_obligation_passed:
            feedback_gaps = metrics.get("operator_feedback_obligation_gaps", {})
            if isinstance(feedback_gaps, Mapping):
                artifact_order = [
                    artifact
                    for artifact in feedback_gaps
                    if str(artifact or "").strip() and str(artifact or "").strip() != target_artifact
                ]
                if target_artifact in feedback_gaps:
                    artifact_order.append(target_artifact)
                selected_artifact = artifact_order[0] if artifact_order else ""
                selected_gaps = [
                    dict(item)
                    for item in list(feedback_gaps.get(selected_artifact, []) or [])
                    if isinstance(item, Mapping)
                ] if selected_artifact else []
                missing_fields = [
                    normalize_support_field_name(gap.get("field", ""))
                    for gap in selected_gaps
                    if normalize_support_field_name(gap.get("field", ""))
                ]
                missing_rows = [
                    str(gap.get("row_id", "") or gap.get("target_row_id", "") or "").strip()
                    for gap in selected_gaps
                    if str(gap.get("row_id", "") or gap.get("target_row_id", "") or "").strip()
                ]
                if selected_artifact and missing_fields:
                    support_request_candidate = {
                        "request_type": "knowledge_checkout",
                        "capability": str(work_order.get("capability", "") or checkout.get("initial_work_order_capability", "") or "directive_build_grade_synthesis_pack"),
                        "target_artifact": selected_artifact,
                        "reason": "operator_feedback_obligation_missing_field_coverage",
                        "missing_field_coverage": list(dict.fromkeys(missing_fields)),
                        "missing_target_row_ids": list(dict.fromkeys(missing_rows)),
                        "operator_feedback_gap_count": len(selected_gaps),
                        "grants_execution_authority": False,
                    }
    checkpoint = {
        "schema_name": "ConveyorResidentChildProgressCheckpoint",
        "reviewed_child_revision_consumed": metrics.get('reviewed_child_revision_consumed'),
        "schema_version": "conveyor_resident_child_progress_checkpoint_v2",
        "generated_at": generated_at,
        "child_run_id": child_run_id,
        "directive_id": str(checkout.get("directive_id", "") or ""),
        "directive_title": _directive_title(directive_text),
        "child_execution_mode": "resident_campaign",
        "progress_state": progress_state,
        "cycle_index": int(cycle_index),
        "cycle_outcome": "artifact_delta" if meaningful_delta else "blocked",
        "target_artifact": target_artifact,
        "artifact_deltas": [artifact_delta],
        "artifact_delta_count": artifact_delta_count,
        "artifact_delta_names": artifact_delta_names,
        "meaningful_delta": meaningful_delta,
        "draft_changed_this_cycle": draft_changed_this_cycle,
        "draft_differs_from_canonical": draft_differs_from_canonical,
        "canonical_delta_kind": canonical_delta_kind,
        "blocked_reason": blocked_reason,
        "current_step": current_step,
        "child_activity_state": child_activity_state,
        "child_compute_mode": child_compute_mode,
        "resident_artifact_root_fallback": bool(
            artifact_root_fallback.get("resident_artifact_root_fallback", False)
        ),
        "resident_artifact_root_fallback_reason": str(
            artifact_root_fallback.get("resident_artifact_root_fallback_reason", "") or ""
        ),
        "resident_requested_artifact_root": str(
            artifact_root_fallback.get("resident_requested_artifact_root", "") or ""
        ),
        "resident_effective_artifact_root": str(
            artifact_root_fallback.get("resident_effective_artifact_root", "") or str(artifact_root)
        ),
        "cycle_wall_seconds": cycle_wall_seconds,
        "cycle_process_cpu_seconds": cycle_process_cpu_seconds,
        "compute_pass_count": int(compute_pass_count),
        "compute_budget_exhausted": bool(compute_budget_exhausted),
        "compute_phase_sequence": compute_phase_sequence,
        "support_pack_rows_read": int(support_pack_rows_read),
        "support_pack_consumable_count": int(support_pack_consumable_count),
        "support_pack_non_consumable_count": int(support_pack_non_consumable_count),
        "support_adequacy_state": support_adequacy_state,
        "support_covered_missing_fields": list(support_adequacy.get("support_covered_missing_fields", []) or []),
        "support_uncovered_missing_fields": support_uncovered_missing_fields,
        "artifact_rows_generated": int(artifact_rows_generated),
        "artifact_rows_revised": int(artifact_rows_revised),
        "sleep_reason": sleep_reason,
        "support_request_candidate": support_request_candidate,
        "message": (
            f"Revised {target_artifact} and produced {artifact_delta_count} artifact delta(s)."
            if meaningful_delta
            else f"Checked {target_artifact} without a meaningful artifact delta."
        ),
        "next_wake_seconds": next_wake_seconds,
        "work_order_target_reason": str(work_order.get("target_selection_reason", "") or ""),
        "work_order_id": str(work_order.get("work_order_id", "") or ""),
        "work_order_missing_recovered": work_order_missing_recovered,
        "wake_token_observed": wake_token_observed,
        "wake_work_order_id": str(wake_request.get("wake_work_order_id", "") or ""),
        "wake_reason": str(wake_request.get("wake_reason", "") or ""),
        "wake_latency_seconds": wake_latency,
        "wake_sequence": int(wake_request.get("wake_sequence", 0) or 0),
        "field_level_contract_applied": bool(metrics.get("field_level_contract_applied", False)),
        "hardware_prototype_contract_applied": bool(metrics.get("hardware_prototype_contract_applied", False)),
        "hardware_build_packet_contract_applied": bool(
            metrics.get("hardware_build_packet_contract_applied", False)
        ),
        "materialized_expected_files": list(metrics.get("materialized_expected_files", []) or []),
        "missing_materialized_expected_files_after_write": list(
            missing_materialized
        ),
        "missing_required_return_artifacts_after_write": list(missing_required_return_artifacts),
        "hardware_build_packet_ready_candidate": hardware_build_packet_ready,
        "plateau_intervention_stage": str(
            work_order.get("plateau_intervention_stage", "") or checkout.get("plateau_intervention_stage", "") or ""
        ),
        "depth_obligation_id": depth_obligation_id,
        "depth_target_artifact": depth_target_artifact if depth_obligation_id or target_delta_required else "",
        "depth_missing_fields": [
            dict(item)
            for item in list(
                work_order.get("depth_missing_fields", []) or checkout.get("depth_missing_fields", []) or []
            )
            if isinstance(item, dict)
        ],
        "depth_source_coverage_state": str(
            work_order.get("depth_source_coverage_state", "")
            or checkout.get("depth_source_coverage_state", "")
            or ""
        ),
        "depth_required_evidence_refs": [
            str(item)
            for item in list(
                work_order.get("depth_required_evidence_refs", [])
                or checkout.get("depth_required_evidence_refs", [])
                or []
            )
            if str(item).strip()
        ],
        "target_delta_required": bool(target_delta_required),
        "depth_obligation_result": {
            "depth_obligation_id": depth_obligation_id,
            "target_artifact": depth_target_artifact if depth_obligation_id or target_delta_required else "",
            "target_delta_required": bool(target_delta_required),
            "target_delta_observed": bool(meaningful_delta and depth_target_artifact == target_artifact),
        },
        "hardware_readiness_tier": hardware_readiness_tier,
        "hardware_readiness_blockers": list(dict.fromkeys(hardware_readiness_blockers)),
        "strict_hardware_contract_passed": strict_hardware_contract_passed,
        "technical_depth_contract_passed": technical_depth_contract_passed,
        "technology_design_obligation_active": technology_design_obligation_active,
        "technology_design_obligation_ids": technology_design_obligation_ids,
        "support_materialized_interface_row_count": int(
            metrics.get("support_materialized_interface_row_count", 0) or 0
        ),
        "support_completed_interface_row_count": int(
            metrics.get(
                "support_completed_interface_row_count",
                metrics.get("support_materialized_interface_row_count", 0),
            )
            or 0
        ),
        "support_materialized_interface_fields": list(
            metrics.get("support_materialized_interface_fields", []) or []
        ),
        "support_materialized_interface_required_field_count": int(
            metrics.get("support_materialized_interface_required_field_count", 0) or 0
        ),
        "support_materialized_interface_missing_fields": list(
            metrics.get("support_materialized_interface_missing_fields", []) or []
        ),
        "support_completed_required_fields": list(
            metrics.get("support_completed_required_fields", []) or []
        ),
        "support_still_missing_required_fields": list(
            metrics.get("support_still_missing_required_fields", []) or []
        ),
        "support_row_completion_state": str(
            metrics.get("support_row_completion_state", "") or ""
        ),
        "support_target_row_resolution_state": str(
            metrics.get("support_target_row_resolution_state", "") or ""
        ),
        "support_resolved_target_row_ids": list(
            metrics.get("support_resolved_target_row_ids", []) or []
        ),
        "support_unresolved_target_row_ids": list(
            metrics.get("support_unresolved_target_row_ids", []) or []
        ),
        "support_to_artifact_required_field_delta": bool(
            metrics.get("support_to_artifact_required_field_delta", False)
            or metrics.get("source_bom_required_field_delta", False)
            or metrics.get("risk_control_required_field_delta", False)
            or metrics.get("validation_fixture_required_field_delta", False)
        ),
        "support_to_artifact_delta": bool(
            metrics.get("support_to_artifact_delta", False)
            or metrics.get("source_bom_required_field_delta", False)
            or metrics.get("risk_control_required_field_delta", False)
            or metrics.get("validation_fixture_required_field_delta", False)
        ),
        "source_bom_materialization_state": str(
            metrics.get("source_bom_materialization_state", "") or ""
        ),
        "source_bom_materialized_rows": list(metrics.get("source_bom_materialized_rows", []) or []),
        "source_bom_materialized_count": int(metrics.get("source_bom_materialized_count", 0) or 0),
        "source_bom_required_field_delta": bool(metrics.get("source_bom_required_field_delta", False)),
        "bom_field_closure_state": str(metrics.get("bom_field_closure_state", "") or ""),
        "bom_closed_requested_row_ids": list(metrics.get("bom_closed_requested_row_ids", []) or []),
        "bom_unclosed_requested_row_ids": list(metrics.get("bom_unclosed_requested_row_ids", []) or []),
        "bom_closed_operator_feedback_gap_count": int(
            metrics.get("bom_closed_operator_feedback_gap_count", 0) or 0
        ),
        "source_bom_unresolved_depth_fields": list(
            metrics.get("source_bom_unresolved_depth_fields", []) or []
        ),
        "risk_control_materialization_state": str(
            metrics.get("risk_control_materialization_state", "") or ""
        ),
        "risk_control_materialized_rows": list(
            metrics.get("risk_control_materialized_rows", []) or []
        ),
        "risk_control_materialized_count": int(
            metrics.get("risk_control_materialized_count", 0) or 0
        ),
        "missing_fmea_row_refs": list(metrics.get("missing_fmea_row_refs", []) or []),
        "risk_control_required_field_delta": bool(
            metrics.get("risk_control_required_field_delta", False)
        ),
        "validation_fixture_materialization_state": str(
            metrics.get("validation_fixture_materialization_state", "") or ""
        ),
        "validation_fixture_materialized_rows": list(
            metrics.get("validation_fixture_materialized_rows", []) or []
        ),
        "validation_fixture_materialized_count": int(
            metrics.get("validation_fixture_materialized_count", 0) or 0
        ),
        "validation_fixture_closed_requested_row_ids": list(
            metrics.get("validation_fixture_closed_requested_row_ids", []) or []
        ),
        "validation_fixture_unclosed_requested_row_ids": list(
            metrics.get("validation_fixture_unclosed_requested_row_ids", []) or []
        ),
        "validation_fixture_required_field_delta": bool(
            metrics.get("validation_fixture_required_field_delta", False)
        ),
        "implementation_readiness_fast_path_used": bool(
            metrics.get("implementation_readiness_fast_path_used", False)
        ),
        "implementation_readiness_visible_dossier_artifacts_used": list(
            metrics.get("implementation_readiness_visible_dossier_artifacts_used", []) or []
        ),
        "implementation_readiness_visible_dossier_missing_artifacts": list(
            metrics.get("implementation_readiness_visible_dossier_missing_artifacts", []) or []
        ),
        "implementation_readiness_visible_dossier_incomplete_artifacts": list(
            metrics.get("implementation_readiness_visible_dossier_incomplete_artifacts", []) or []
        ),
        "visible_dossier_closure_state": str(metrics.get("visible_dossier_closure_state", "") or ""),
        "visible_dossier_gate_summary": dict(metrics.get("visible_dossier_gate_summary", {}) or {}),
        "role_split_materialization_state": str(
            metrics.get("role_split_materialization_state", "") or ""
        ),
        "materialized_role_split_rows": list(
            metrics.get("materialized_role_split_rows", []) or []
        ),
        "role_split_uncovered_roles": list(metrics.get("role_split_uncovered_roles", []) or []),
        "role_lane_closure_state": str(metrics.get("role_lane_closure_state", "") or ""),
        "role_lane_misassignment_count": int(metrics.get("role_lane_misassignment_count", 0) or 0),
        "role_lane_closed_requested_row_ids": list(
            metrics.get("role_lane_closed_requested_row_ids", []) or []
        ),
        "role_lane_unclosed_requested_row_ids": list(
            metrics.get("role_lane_unclosed_requested_row_ids", []) or []
        ),
        "r_and_d_design_brief_id": str(metrics.get("r_and_d_design_brief_id", "") or ""),
        "research_design_readiness_state": str(
            metrics.get("research_design_readiness_state", "")
            or ("research_design_ready" if technology_design_obligation_active else "")
        ),
        "hardware_build_ready_blocked_by_design_obligation": bool(
            metrics.get("hardware_build_ready_blocked_by_design_obligation", False)
            or technology_design_obligation_active
        ),
        "operator_feedback_obligation_passed": operator_feedback_obligation_passed,
        "operator_feedback_obligation_gaps": dict(
            metrics.get("operator_feedback_obligation_gaps", {}) or {}
        ),
        "operator_feedback_obligation_gap_count": int(
            metrics.get("operator_feedback_obligation_gap_count", 0) or 0
        ),
        "row_scoped_operator_feedback_obligations": list(
            metrics.get("row_scoped_operator_feedback_obligations", []) or []
        ),
        "closed_operator_feedback_obligation_ids": list(
            metrics.get("closed_operator_feedback_obligation_ids", []) or []
        ),
        "operator_feedback_self_finalization_blocked": bool(
            metrics.get("operator_feedback_self_finalization_blocked", False)
        ),
        "generic_placeholder_gaps": dict(metrics.get("generic_placeholder_gaps", {}) or {}),
        "generic_placeholder_gap_count": int(metrics.get("generic_placeholder_gap_count", 0) or 0),
        "full_dive_human_subject_blocked": full_dive_human_subject_blocked,
        "required_hardware_artifacts_present": required_hardware_artifacts_present,
        "selected_return_artifact_source_verified": bool(
            resident_self_final_return_eligible and hardware_build_packet_ready
        ),
        "full_dive_field_gaps_by_artifact": dict(metrics.get("full_dive_field_gaps_by_artifact", {}) or {}),
        "schema_followup_contract_materialized": bool(
            metrics.get("schema_followup_contract_materialized", False)
        ),
        "schema_followup_materialized_top_level_fields": list(
            metrics.get("schema_followup_materialized_top_level_fields", []) or []
        ),
        "schema_followup_missing_top_level_fields_after_write": list(
            metrics.get("schema_followup_missing_top_level_fields_after_write", []) or []
        ),
        "closed_failed_gates": list(metrics.get("closed_failed_gates", []) or []),
        "remaining_failed_gates": remaining_failed_gates,
        "resident_self_final_return_eligible": resident_self_final_return_eligible,
        "resident_self_final_return_reason": (
            "hardware_build_packet_ready_candidate" if resident_self_final_return_eligible else ""
        ),
        "resident_self_final_return_blockers": list(dict.fromkeys(self_final_blockers)),
        "final_return_trigger_source": (
            "child_review_worthy_checkpoint" if resident_self_final_return_eligible else ""
        ),
        "schema_skeleton_id": str(metrics.get("schema_skeleton_id", "") or work_order.get("schema_skeleton_id", "") or ""),
        "network_policy": str(checkout.get("network_policy", "") or "deny_all"),
        "return_policy": return_policy,
        "current_focus": "deepening directive artifacts inside isolated workspace",
        "next_step_context": (
            str(work_order.get("next_step_context", "") or "")
            or "Continue expanding directive-specific subsystem, interface, dependency, "
            "validation, milestone, claim-evidence, and novelty artifacts until a review-worthy milestone is reached."
        ),
        "support_pack_count": len(list(checkout.get("librarian_pack_refs", []) or [])),
        "support_pack_refs_used": list(metrics.get("support_pack_refs_used", []) or []),
        "operator_feedback": str(checkout.get("operator_feedback", "") or ""),
    }
    _write_json_artifact(progress_root / f"progress_{cycle_index:06d}.json", checkpoint)
    _write_json_artifact(progress_root / "progress_latest.json", checkpoint)
    _write_json_artifact(
        progress_root / "progress_heartbeat.json",
        {
            "schema_name": "ConveyorResidentChildProgressHeartbeat",
            "schema_version": "conveyor_resident_child_progress_heartbeat_v1",
            "generated_at": generated_at,
            "last_progress_at": generated_at,
            "last_heartbeat_at": generated_at,
            "child_run_id": child_run_id,
            "directive_id": str(checkout.get("directive_id", "") or ""),
            "cycle_index": int(cycle_index),
            "target_artifact": target_artifact,
            "progress_checkpoint": "progress_latest.json",
            "progress_checkpoint_hash": _checkpoint_hash(checkpoint),
            "compute_budget_exhausted": bool(compute_budget_exhausted),
            "meaningful_delta": bool(meaningful_delta),
            "support_to_artifact_required_field_delta": bool(
                checkpoint.get("support_to_artifact_required_field_delta", False)
            ),
            "grants_execution_authority": False,
        },
    )
    _write_json_artifact(workspace / "resident_progress_summary.json", checkpoint)
    return checkpoint


def _write_mount_fault_progress_checkpoint(
    *,
    checkout: dict[str, Any],
    workspace: Path,
    progress_root: Path,
    cycle_index: int,
    fault: ConveyorMountFaultError,
) -> dict[str, Any]:
    generated_at = _utc_now()
    checkpoint = {
        "schema_name": "ConveyorResidentChildProgressCheckpoint",
        "schema_version": "conveyor_resident_child_progress_checkpoint_v2",
        "generated_at": generated_at,
        "child_run_id": str(checkout.get("child_run_id", "") or "unknown-child"),
        "directive_id": str(checkout.get("directive_id", "") or ""),
        "directive_title": _directive_title(str(checkout.get("directive_text", "") or "")),
        "child_execution_mode": "resident_campaign",
        "progress_state": "infrastructure_fault",
        "cycle_index": int(cycle_index),
        "cycle_outcome": "infrastructure_fault",
        "target_artifact": "",
        "artifact_deltas": [],
        "meaningful_delta": False,
        "blocked_reason": "docker_mount_fault",
        "infrastructure_fault": True,
        "mount_fault_source": fault.mount_kind,
        "mount_fault_path": str(fault.path),
        "mount_fault_errno": int(getattr(fault.original, "errno", 0) or 0),
        "work_order_id": "",
        "wake_token_observed": False,
        "wake_work_order_id": "",
        "wake_reason": "",
        "wake_latency_seconds": None,
        "wake_sequence": 0,
        "network_policy": str(checkout.get("network_policy", "") or "deny_all"),
        "return_policy": dict(checkout.get("return_policy", {}) or {}),
        "current_focus": "waiting for kernel recovery from Docker bind-mount I/O fault",
        "next_step_context": (
            "Kernel should classify this as infrastructure, recover Docker bind mounts, "
            "and requeue from the latest campaign baseline."
        ),
        "support_pack_count": len(list(checkout.get("librarian_pack_refs", []) or [])),
        "support_pack_refs_used": [],
        "operator_feedback": str(checkout.get("operator_feedback", "") or ""),
    }
    for path in (
        progress_root / f"progress_{cycle_index:06d}.json",
        progress_root / "progress_latest.json",
        workspace / "resident_progress_summary.json",
    ):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_json_artifact(path, checkpoint)
        except OSError:
            continue
    return checkpoint


def run_resident_child_once_for_test(
    *,
    checkout_path: str | Path,
    workspace_root: str | Path,
    outbox_root: str | Path,
    inbox_root: str | Path = "",
) -> int:
    checkout = _read_checkout(Path(checkout_path))
    workspace = Path(workspace_root)
    outbox = Path(outbox_root)
    outbox.mkdir(parents=True, exist_ok=True)
    progress_root = Path(str(checkout.get("progress_path", "") or outbox / "progress"))
    inbox_payload = _read_inbox(Path(inbox_root)) if str(inbox_root or "") else {}
    _write_resident_progress_checkpoint(
        checkout=checkout,
        workspace=workspace,
        progress_root=progress_root,
        cycle_index=1,
        progress_state="working",
        inbox_payload=inbox_payload,
    )
    return 0


def _resident_checkpoint_allows_requested_final_return(checkpoint: Mapping[str, Any]) -> bool:
    gated_final_return = bool(
        checkpoint.get("hardware_prototype_contract_applied", False)
        or checkpoint.get("hardware_build_packet_contract_applied", False)
        or checkpoint.get("field_level_contract_applied", False)
        or checkpoint.get("remaining_failed_gates", [])
        or not checkpoint.get("operator_feedback_obligation_passed", True)
    )
    return bool(checkpoint.get("resident_self_final_return_eligible", False)) or not gated_final_return


def run_child_resident(
    *,
    checkout_path: str | Path,
    workspace_root: str | Path,
    outbox_root: str | Path,
    inbox_root: str | Path = "",
    progress_root: str | Path = "",
) -> int:
    checkout = _read_checkout(Path(checkout_path))
    workspace = Path(workspace_root)
    outbox = Path(outbox_root)
    inbox = Path(str(inbox_root or checkout.get("inbox_path", "") or ""))
    progress = Path(str(progress_root or checkout.get("progress_path", "") or outbox / "progress"))
    try:
        sleep_seconds = max(1.0, min(float(checkout.get("resident_cycle_sleep_seconds", 30) or 30), 1800.0))
    except (TypeError, ValueError):
        sleep_seconds = 30.0
    try:
        first_sleep_seconds = max(
            1.0,
            min(float(checkout.get("resident_first_cycle_sleep_seconds", 0) or 0), 1800.0),
        )
    except (TypeError, ValueError):
        first_sleep_seconds = 0.0
    cycle_index = 1
    next_inbox_payload: dict[str, Any] | None = None
    processed_wake_sequences: set[int] = set()
    while True:
        try:
            if next_inbox_payload is not None:
                inbox_payload = next_inbox_payload
                next_inbox_payload = None
            else:
                inbox_payload = _read_inbox(inbox) if str(inbox) else {}
            if bool(inbox_payload.get("stop_requested", False)):
                _write_resident_progress_checkpoint(
                    checkout=checkout,
                    workspace=workspace,
                    progress_root=progress,
                    cycle_index=cycle_index,
                    progress_state="stopped_by_kernel",
                    inbox_payload=inbox_payload,
                )
                return 0
            if bool(inbox_payload.get("request_final_return", False)):
                checkpoint = _write_resident_progress_checkpoint(
                    checkout=checkout,
                    workspace=workspace,
                    progress_root=progress,
                    cycle_index=cycle_index,
                    progress_state="working",
                    inbox_payload=inbox_payload,
                )
                if _resident_checkpoint_allows_requested_final_return(checkpoint):
                    return run_child_once(
                        checkout_path=checkout_path,
                        workspace_root=workspace_root,
                        outbox_root=outbox_root,
                    )
                wake_sequence = _wake_sequence(inbox_payload)
                if wake_sequence > 0:
                    processed_wake_sequences.add(wake_sequence)
            checkpoint = _write_resident_progress_checkpoint(
                checkout=checkout,
                workspace=workspace,
                progress_root=progress,
                cycle_index=cycle_index,
                progress_state="working",
                inbox_payload=inbox_payload,
            )
            if bool(checkpoint.get("resident_self_final_return_eligible", False)):
                return run_child_once(
                    checkout_path=checkout_path,
                    workspace_root=workspace_root,
                    outbox_root=outbox_root,
                )
            wake_sequence = _wake_sequence(inbox_payload)
            if wake_sequence > 0:
                processed_wake_sequences.add(wake_sequence)
        except ConveyorMountFaultError as exc:
            _write_mount_fault_progress_checkpoint(
                checkout=checkout,
                workspace=workspace,
                progress_root=progress,
                cycle_index=cycle_index,
                fault=exc,
            )
            return MOUNT_FAULT_EXIT_CODE
        except OSError as exc:
            if not _is_mount_fault_error(exc):
                raise
            fault = ConveyorMountFaultError("resident_workspace", workspace, exc)
            _write_mount_fault_progress_checkpoint(
                checkout=checkout,
                workspace=workspace,
                progress_root=progress,
                cycle_index=cycle_index,
                fault=fault,
            )
            return MOUNT_FAULT_EXIT_CODE
        cycle_index += 1
        current_sleep = first_sleep_seconds if cycle_index == 2 and first_sleep_seconds > 0 else sleep_seconds
        next_inbox_payload = _resident_sleep_until_wake(
            checkout=checkout,
            inbox=inbox,
            sleep_seconds=current_sleep,
            processed_wake_sequences=processed_wake_sequences,
        ) or None


def run_child_once(*, checkout_path: str | Path, workspace_root: str | Path, outbox_root: str | Path) -> int:
    checkout = _read_checkout(Path(checkout_path))
    workspace = Path(workspace_root)
    outbox = Path(outbox_root)
    workspace.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    child_run_id = str(checkout.get("child_run_id", "") or "unknown-child")
    directive_id = str(checkout.get("directive_id", "") or "")
    directive_text = str(checkout.get("directive_text", "") or "").strip()
    try:
        smoke_sleep_seconds = max(0.0, min(float(checkout.get("smoke_sleep_seconds", 0) or 0), 900.0))
    except (TypeError, ValueError):
        smoke_sleep_seconds = 0.0
    if smoke_sleep_seconds > 0:
        time.sleep(smoke_sleep_seconds)
    generated_at = _utc_now()
    workspace_summary = {
        "schema_name": "ConveyorChildWorkspaceSummary",
        "schema_version": "conveyor_child_workspace_summary_v1",
        "generated_at": generated_at,
        "child_run_id": child_run_id,
        "directive_id": directive_id,
        "network_policy": str(checkout.get("network_policy", "deny_all") or "deny_all"),
        "summary": "Conveyor child entrypoint completed the bounded startup contract.",
    }
    summary_path = workspace / "child_result_summary.json"
    summary_path.write_text(json.dumps(workspace_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifacts = [str(summary_path.name)]
    verification_evidence = [
        "conveyor_child_entrypoint_completed",
        *(["conveyor_child_smoke_sleep_completed"] if smoke_sleep_seconds > 0 else []),
    ]
    missing_capability_requests: list[dict[str, Any]] = []
    deliverable_payload = _build_directive_deliverables(checkout, directive_text)
    built_technical_documentation = False
    build_grade_metrics: dict[str, Any] = {
        "artifact_names": [],
        "claim_count": 0,
        "supported_claim_count": 0,
        "novelty_count": 0,
        "directive_specific_row_count": 0,
    }
    if deliverable_payload:
        deliverables_path = workspace / "directive_deliverables.json"
        blueprint_path = workspace / "directive_blueprint.md"
        deliverables_path.write_text(
            json.dumps(deliverable_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_directive_blueprint(blueprint_path, deliverable_payload)
        artifacts.extend([str(deliverables_path.name), str(blueprint_path.name)])
        verification_evidence.append("conveyor_child_deliverables_built")
        missing_capability_requests = list(deliverable_payload.get("missing_capability_requests", []) or [])
        if _should_build_technical_documentation(checkout):
            technical_docs_path = workspace / "technical_documentation.md"
            readiness_path = workspace / "implementation_readiness_review.json"
            _write_technical_documentation(
                technical_docs_path,
                checkout=checkout,
                deliverable_payload=deliverable_payload,
            )
            readiness_path.write_text(
                json.dumps(
                    _build_readiness_review(checkout=checkout, deliverable_payload=deliverable_payload),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            artifacts.extend([str(technical_docs_path.name), str(readiness_path.name)])
            verification_evidence.append("conveyor_child_technical_documentation_built")
            build_grade_metrics = _write_build_grade_artifacts(
                workspace,
                checkout=checkout,
                deliverable_payload=deliverable_payload,
            )
            artifacts.extend([name for name in build_grade_metrics["artifact_names"] if name not in artifacts])
            verification_evidence.append("conveyor_child_build_grade_artifacts_built")
            built_technical_documentation = True
    deliverable_count = 0
    if deliverable_payload:
        deliverable_count = len(deliverable_payload.get("deliverables", []) or [])
    if deliverable_count:
        if built_technical_documentation:
            outcome_summary = (
                f"Conveyor child expanded {deliverable_count} deliverable(s) for "
                f"{deliverable_payload.get('directive_title', 'the directive')} into technical documentation "
                "and returned implementation-readiness artifacts."
            )
        else:
            outcome_summary = (
                f"Conveyor child built {deliverable_count} deliverable scaffold(s) for "
                f"{deliverable_payload.get('directive_title', 'the directive')} and returned review artifacts."
            )
    else:
        outcome_summary = (
            f"Conveyor child completed bounded entrypoint work for directive: {directive_text}"
            if directive_text
            else "Conveyor child completed bounded entrypoint work."
        )
    return_packet = {
        "schema_name": "ConveyorChildOutboxReturnPacket",
        "schema_version": "conveyor_child_outbox_return_packet_v1",
        "generated_at": generated_at,
        "child_run_id": child_run_id,
        "directive_id": directive_id,
        "outcome_summary": outcome_summary,
        "artifacts": artifacts,
        "verification_evidence": verification_evidence,
        "artifact_hashes": _artifact_hashes(workspace, artifacts),
        "build_grade_scores": {
            "directive_specific_row_count": int(build_grade_metrics.get("directive_specific_row_count", 0) or 0),
            "supported_claim_count": int(build_grade_metrics.get("supported_claim_count", 0) or 0),
            "novelty_count": int(build_grade_metrics.get("novelty_count", 0) or 0),
        },
        "claim_count": int(build_grade_metrics.get("claim_count", 0) or 0),
        "novelty_count": int(build_grade_metrics.get("novelty_count", 0) or 0),
        "requested_operator_clarifications": [],
        "risks": (
            ["operator_review_required_before_real_world_use"]
            if built_technical_documentation
            else []
        ),
        "requested_follow_up": (
            "operator_review_build_grade_documentation"
            if built_technical_documentation
            else "operator_review_return_packet"
        ),
        "missing_capability_requests": missing_capability_requests,
    }
    (outbox / "return_packet.json").write_text(
        json.dumps(return_packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a bounded Novali conveyor child task.")
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--outbox", required=True)
    parser.add_argument("--inbox", default="")
    parser.add_argument("--progress", default="")
    parser.add_argument("--resident", action="store_true")
    args = parser.parse_args(argv)
    if args.resident:
        return run_child_resident(
            checkout_path=args.checkout,
            workspace_root=args.workspace,
            outbox_root=args.outbox,
            inbox_root=args.inbox,
            progress_root=args.progress,
        )
    return run_child_once(
        checkout_path=args.checkout,
        workspace_root=args.workspace,
        outbox_root=args.outbox,
    )


if __name__ == "__main__":
    raise SystemExit(main())
