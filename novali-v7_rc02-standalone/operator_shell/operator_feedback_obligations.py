from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

OPERATOR_FEEDBACK_OBLIGATION_SCHEMA_VERSION = "operator_feedback_obligations.v2"

FEEDBACK_BLOCKING_MARKERS = (
    "do not self-finalize",
    "do not self finalize",
    "must not self-finalize",
    "must not self finalize",
    "must not come back",
    "do not come back",
    "must not return",
    "do not return",
    "not operator-review-ready",
    "not operator review ready",
    "until these exact",
    "until the exact",
)

ROW_KEYS_BY_ARTIFACT = {
    "bill_of_materials.json": ("items", "components", "materials", "dependencies", "rows"),
    "interface_specifications.json": ("interfaces", "rows", "items"),
    "validation_fixtures.json": ("fixtures", "validation_fixtures", "rows", "items"),
    "risk_controls.json": ("controls", "risk_controls", "rows", "items"),
    "prototype_assembly_plan.json": ("assembly_steps", "steps", "rows", "items"),
}

IDENTITY_FIELDS = (
    "item_id",
    "interface_id",
    "fixture_id",
    "control_id",
    "hazard_id",
    "step_id",
    "name",
    "role",
    "required_for",
    "function",
    "description",
    "subsystem",
    "component_id",
    "category",
)

SOURCE_FIELDS = (
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
    "connector",
    "protocol",
)

TOKEN_STOPWORDS = {
    "about",
    "after",
    "all",
    "and",
    "assigned",
    "assumption",
    "before",
    "bench",
    "boundary",
    "build",
    "build-ready",
    "child",
    "class",
    "com",
    "connector",
    "come",
    "complete",
    "exact",
    "execution",
    "feedback",
    "field",
    "first",
    "fixture",
    "hardware",
    "interface",
    "json",
    "must",
    "only",
    "operator",
    "packet",
    "pack",
    "pass",
    "rating",
    "ready",
    "remain",
    "remains",
    "return",
    "review",
    "role",
    "roles",
    "source",
    "substitutions",
    "system",
    "these",
    "until",
    "while",
    "with",
}

FIELD_ALIASES_BY_REQUIRED_FIELD = {
    "manufacturer": ("manufacturer", "supplier"),
    "mpn": ("mpn", "part number", "part_number"),
    "datasheet_url": ("datasheet/source url", "datasheet url", "source url", "datasheet", "source"),
    "quantity": ("quantity", "quantities"),
    "unit_cost": ("unit cost", "cost basis", "cost"),
    "electrical_rating": ("electrical rating", "electrical ratings", "rating", "ratings"),
    "compliance_notes": ("compliance notes", "standards assumption", "standards assumptions"),
    "validation_fixture_ref": ("validation fixture", "fixture link", "fixture links", "linked fixture"),
    "linked_risk_control_ref": ("risk link", "risk links", "risk control", "risk controls"),
    "go_no_go_trace": ("go/no-go trace", "go no-go trace", "go/no-go", "go no go"),
    "acceptance_thresholds": ("acceptance threshold", "acceptance thresholds", "pass/fail threshold", "pass/fail thresholds"),
}

ROW_FIELD_ALTERNATIVES = {
    "manufacturer": ("manufacturer", "supplier"),
    "mpn": ("mpn", "part_number"),
    "datasheet_url": ("datasheet_url", "source_url", "citation_ref"),
    "quantity": ("quantity",),
    "unit_cost": ("unit_cost", "cost_basis"),
    "electrical_rating": ("electrical_rating", "mechanical_rating", "ratings", "measurable_spec"),
    "compliance_notes": ("compliance_notes", "standards_assumption", "standards_assumptions", "source_assumption"),
    "validation_fixture_ref": ("validation_fixture_ref", "validation_fixture", "fixture_ref", "linked_fixture_ref"),
    "linked_risk_control_ref": ("linked_risk_control_ref", "linked_risk_ref", "risk_control_ref"),
    "go_no_go_trace": ("go_no_go_trace", "go_no_go_criteria", "go_no_go_ref"),
    "acceptance_thresholds": ("acceptance_thresholds", "pass_fail_thresholds", "measurable_spec", "go_no_go_criteria"),
}

BENIGN_FORBIDDEN_WORDS = {
    "acceptance",
    "basis",
    "required",
    "row",
    "rows",
    "spec",
    "specs",
    "support",
    "threshold",
    "thresholds",
    "this",
}


@dataclass(frozen=True)
class OperatorFeedbackForbiddenAssignment:
    obligation_id: str
    role: str
    forbidden_value: str
    forbidden_terms: tuple[str, ...] = ()
    source_phrase: str = ""


@dataclass(frozen=True)
class OperatorFeedbackRoleSplit:
    obligation_id: str
    artifact_name: str
    base_role: str
    required_roles: tuple[str, ...] = ()
    source_phrase: str = ""


@dataclass(frozen=True)
class OperatorFeedbackRowScopedRequiredField:
    obligation_id: str
    artifact_name: str
    row_id: str
    role: str = ""
    required_fields: tuple[str, ...] = ()
    requested_row_id: str = ""
    target_row_id: str = ""
    source_phrase: str = ""


@dataclass(frozen=True)
class OperatorFeedbackObligationContract:
    schema_version: str = OPERATOR_FEEDBACK_OBLIGATION_SCHEMA_VERSION
    required_target_artifacts: tuple[str, ...] = ()
    required_fields_by_artifact: dict[str, tuple[str, ...]] = field(default_factory=dict)
    forbidden_assignments: tuple[OperatorFeedbackForbiddenAssignment, ...] = ()
    required_role_splits: tuple[OperatorFeedbackRoleSplit, ...] = ()
    row_scoped_required_fields: tuple[OperatorFeedbackRowScopedRequiredField, ...] = ()
    role_split_quality_requirements: tuple[str, ...] = ()
    self_finalization_blockers: tuple[str, ...] = ()
    parse_warnings: tuple[str, ...] = ()


def normalize_feedback_text(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def feedback_blocks_self_finalization(feedback: Any) -> bool:
    normalized = normalize_feedback_text(feedback)
    return bool(normalized and any(marker in normalized for marker in FEEDBACK_BLOCKING_MARKERS))


def _contract_dict(contract: OperatorFeedbackObligationContract) -> dict[str, Any]:
    payload = asdict(contract)
    payload["required_target_artifacts"] = list(contract.required_target_artifacts)
    payload["required_fields_by_artifact"] = {
        artifact: list(fields)
        for artifact, fields in contract.required_fields_by_artifact.items()
    }
    payload["forbidden_assignments"] = [
        {
            **asdict(assignment),
            "forbidden_terms": list(assignment.forbidden_terms),
        }
        for assignment in contract.forbidden_assignments
    ]
    payload["required_role_splits"] = [
        {
            **asdict(split),
            "required_roles": list(split.required_roles),
        }
        for split in contract.required_role_splits
    ]
    payload["row_scoped_required_fields"] = [
        {
            **asdict(obligation),
            "required_fields": list(obligation.required_fields),
        }
        for obligation in contract.row_scoped_required_fields
    ]
    payload["role_split_quality_requirements"] = list(contract.role_split_quality_requirements)
    payload["self_finalization_blockers"] = list(contract.self_finalization_blockers)
    payload["parse_warnings"] = list(contract.parse_warnings)
    return payload


def _tokens(value: Any, *, minimum: int = 3) -> set[str]:
    text = json.dumps(value, sort_keys=True, default=str).lower() if isinstance(value, (Mapping, list, tuple)) else str(value or "").lower()
    tokens = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_\-/.]*", text)
        if len(token) >= minimum and token not in TOKEN_STOPWORDS
    }
    expanded: set[str] = set(tokens)
    for token in list(tokens):
        for part in re.split(r"[_\-/.]+", token):
            if len(part) >= minimum and part not in TOKEN_STOPWORDS:
                expanded.add(part)
    return expanded


def _artifact_mentions(normalized_feedback: str) -> tuple[str, ...]:
    artifacts = {
        match.group(0).strip().replace("\\", "/")
        for match in re.finditer(r"\b[a-z0-9_\-/]+\.(?:json|md)\b", normalized_feedback)
    }
    return tuple(sorted(artifacts))


def _primary_artifact(normalized_feedback: str, artifacts: Iterable[str]) -> str:
    artifact_list = list(artifacts)
    for artifact in artifact_list:
        if (
            f"continue on {artifact}" in normalized_feedback
            or f"target {artifact}" in normalized_feedback
            or f"force target {artifact}" in normalized_feedback
        ):
            return artifact
    return artifact_list[0] if artifact_list else "bill_of_materials.json"


def _required_fields_by_artifact(normalized_feedback: str, artifact: str) -> dict[str, tuple[str, ...]]:
    fields: list[str] = []
    for field_name, aliases in FIELD_ALIASES_BY_REQUIRED_FIELD.items():
        if any(alias in normalized_feedback for alias in aliases):
            fields.append(field_name)
    if not fields:
        return {}
    return {artifact: tuple(dict.fromkeys(fields))}


def _normalize_required_field(value: Any) -> str:
    normalized = _normalize_role(value)
    if not normalized:
        return ""
    for canonical, aliases in FIELD_ALIASES_BY_REQUIRED_FIELD.items():
        if normalized == canonical:
            return canonical
        for alias in aliases:
            if normalized == _normalize_role(alias):
                return canonical
    return normalized


def _clean_clause_prefix(value: str) -> str:
    text = normalize_feedback_text(value)
    for marker in (" while ", " until ", ". "):
        if marker in text:
            text = text.rsplit(marker, 1)[-1]
    return re.sub(r"^(?:the|a|an)\s+", "", text).strip(" .,:;")


def _split_conjoined_values(value: str) -> list[str]:
    normalized = normalize_feedback_text(value)
    normalized = re.sub(r"^(?:the|a|an)\s+", "", normalized)
    parts = [
        part.strip(" .,:;")
        for part in re.split(r"\s+and\s+|,\s*", normalized)
        if part.strip(" .,:;")
    ]
    return parts or ([normalized] if normalized else [])


def _split_roles(value: str) -> list[str]:
    normalized = normalize_feedback_text(value)
    normalized = re.sub(r"\s+roles?$", "", normalized)
    roles = [
        _normalize_split_role(part)
        for part in re.split(r"\s+and\s+|,\s*|/", normalized)
        if _normalize_split_role(part)
    ]
    return list(dict.fromkeys(roles))


ROLE_SPLIT_QUALITY_TERMS = {
    "concrete",
    "source_backed",
    "source-backed",
    "evidence_backed",
    "evidence-backed",
    "review_ready",
    "review-ready",
    "operator_gated",
    "operator-gated",
    "build_ready",
    "build-ready",
    "source_backed_rows",
    "concrete_source_backed",
    "concrete_source_backed_rows",
}


ROLE_SPLIT_STOP_RE = re.compile(
    r"\s+(?:with|where|each|including|using|that|and\s+each)\b"
)


def _normalize_role(value: Any) -> str:
    text = normalize_feedback_text(value)
    text = re.sub(r"\brows?\b", "", text)
    text = re.sub(r"\brole\b", "", text)
    text = text.strip(" .,:;")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _normalize_split_role(value: Any) -> str:
    normalized = _normalize_role(value)
    normalized = re.sub(r"^(?:and_)+", "", normalized)
    aliases = {
        "daq": "daq_logging",
        "logging": "daq_logging",
        "daq_logging": "daq_logging",
        "data_acquisition": "daq_logging",
        "magnetic_field": "gaussmeter",
        "magnetic_field_gaussmeter": "gaussmeter",
        "magnetic_field_sensor_or_gaussmeter": "gaussmeter",
        "field_sensor": "gaussmeter",
        "hall_sensor": "gaussmeter",
        "thermal_sensor": "thermal",
        "thermal_sensor_interface": "thermal",
        "separate_thermal_sensor_interface": "thermal",
        "separate_thermal_sensor": "thermal",
        "separate_thermal": "thermal",
        "temperature": "thermal",
        "temperature_sensor": "thermal",
        "current_sensor": "current",
        "current_sensor_interface": "current",
        "coolant_sensor": "coolant",
        "flow_sensor": "coolant",
        "coolant_flow_or_temperature_sensor": "coolant",
        "daq_logger_or_microcontroller_interface": "daq_logging",
        "logger_or_microcontroller_interface": "daq_logging",
        "daq_logger_microcontroller_interface": "daq_logging",
    }
    return aliases.get(normalized, normalized)


def _role_split_quality_token(value: Any) -> str:
    normalized = _normalize_role(value)
    normalized = normalized.replace("-", "_")
    if normalized in ROLE_SPLIT_QUALITY_TERMS:
        return normalized
    if normalized.endswith("_rows"):
        trimmed = normalized.removesuffix("_rows")
        if trimmed in ROLE_SPLIT_QUALITY_TERMS:
            return trimmed
    return ""


def _split_role_clause_parts(raw_roles: str) -> tuple[str, list[str], list[str]]:
    text = normalize_feedback_text(raw_roles)
    qualities: list[str] = []
    warnings: list[str] = []
    rows_for = re.match(
        r"(?P<quality>.+?)\s+rows?\s+for\s+(?P<roles>.+)$",
        text,
    )
    if rows_for:
        quality_text = rows_for.group("quality")
        for token in re.split(r"\s+and\s+|,\s*|/", quality_text):
            quality = _role_split_quality_token(token)
            if quality:
                qualities.append(quality)
        text = rows_for.group("roles")
    stop_match = ROLE_SPLIT_STOP_RE.search(text)
    if stop_match:
        text = text[: stop_match.start()]
    text = re.sub(r"\s+rows?\b.*$", "", text).strip(" .,:;")
    roles: list[str] = []
    for part in re.split(r"\s+and\s+|,\s*|/", text):
        quality = _role_split_quality_token(part)
        if quality:
            qualities.append(quality)
            warnings.append(f"role_split_quality_term_ignored:{quality}")
            continue
        role = _normalize_split_role(part)
        if role and not _role_split_quality_token(role):
            roles.append(role)
    return text, list(dict.fromkeys(roles)), list(dict.fromkeys(qualities + warnings))


def _explicit_forbidden_terms(value: str) -> tuple[str, ...]:
    terms = [
        token
        for token in sorted(_tokens(value, minimum=2))
        if token not in BENIGN_FORBIDDEN_WORDS
    ]
    return tuple(dict.fromkeys(terms))


def _extract_forbidden_assignments(normalized_feedback: str) -> tuple[OperatorFeedbackForbiddenAssignment, ...]:
    assignments: list[OperatorFeedbackForbiddenAssignment] = []

    def add_assignment(role: str, forbidden_value: str, phrase: str) -> None:
        normalized_role = _normalize_role(role)
        cleaned_value = _clean_clause_prefix(forbidden_value)
        terms = _explicit_forbidden_terms(cleaned_value)
        if not normalized_role or not cleaned_value or not terms:
            return
        key = (normalized_role, cleaned_value)
        existing = {
            (assignment.role, assignment.forbidden_value)
            for assignment in assignments
        }
        if key in existing:
            return
        assignments.append(
            OperatorFeedbackForbiddenAssignment(
                obligation_id=f"forbidden_assignment:{normalized_role}:{len(assignments) + 1}",
                role=normalized_role,
                forbidden_value=cleaned_value,
                forbidden_terms=terms,
                source_phrase=phrase.strip(" .,:;"),
            )
        )

    for match in re.finditer(
        r"(?:do not|must not|cannot|can not|should not)\s+(?:use|select|assign)\s+(?P<value>.+?)\s+for\s+(?:the\s+)?(?P<role>[a-z0-9_\-]+)",
        normalized_feedback,
    ):
        add_assignment(match.group("role"), match.group("value"), match.group(0))

    for match in re.finditer(
        r"(?P<role>[a-z0-9_\-]+)\s+(?:must not|cannot|can not|should not)\s+(?:use|select|be assigned|map to)\s+(?P<value>.+?)(?:[.;]|$)",
        normalized_feedback,
    ):
        add_assignment(match.group("role"), match.group("value"), match.group(0))

    for match in re.finditer(
        r"(?P<values>.+?)\s+(?:must not\s+|cannot\s+|can not\s+|should not\s+)?(?:remain\s+|remains\s+)?assigned to\s+(?:the\s+)?(?P<roles>[a-z0-9_\-\s/,]+?)\s+roles?(?:[.;]|$)",
        normalized_feedback,
    ):
        values = _split_conjoined_values(match.group("values"))
        roles = _split_roles(match.group("roles"))
        if len(values) == len(roles):
            for value, role in zip(values, roles):
                add_assignment(role, value, match.group(0))
        else:
            for role in roles:
                for value in values:
                    add_assignment(role, value, match.group(0))
    return tuple(assignments)


def _extract_role_splits(normalized_feedback: str, artifact: str) -> tuple[OperatorFeedbackRoleSplit, ...]:
    splits: list[OperatorFeedbackRoleSplit] = []
    for match in re.finditer(
        r"split\s+(?P<base_role>[a-z0-9_\-]+)\s+into\s+(?P<roles>.+?)(?:[.;]|$)",
        normalized_feedback,
    ):
        _, roles, _ = _split_role_clause_parts(match.group("roles"))
        if not roles:
            continue
        splits.append(
            OperatorFeedbackRoleSplit(
                obligation_id=f"required_role_split:{_normalize_role(match.group('base_role'))}:{len(splits) + 1}",
                artifact_name=artifact,
                base_role=_normalize_role(match.group("base_role")),
                required_roles=tuple(dict.fromkeys(roles)),
                source_phrase=match.group(0).strip(" .,:;"),
            )
        )
    return tuple(splits)


def _extract_role_split_quality_requirements(normalized_feedback: str) -> tuple[str, ...]:
    requirements: list[str] = []
    for match in re.finditer(
        r"split\s+(?P<base_role>[a-z0-9_\-]+)\s+into\s+(?P<roles>.+?)(?:[.;]|$)",
        normalized_feedback,
    ):
        _, _, qualities = _split_role_clause_parts(match.group("roles"))
        for quality in qualities:
            if quality.startswith("role_split_quality_term_ignored:"):
                continue
            requirements.append(quality)
    return tuple(dict.fromkeys(requirements))


def _json_arrays_from_feedback(value: str) -> list[Any]:
    decoder = json.JSONDecoder()
    arrays: list[Any] = []
    for match in re.finditer(r"\[", value):
        try:
            parsed, _ = decoder.raw_decode(value[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            arrays.append(parsed)
    return arrays


def _row_scoped_obligation_row_id(item: Mapping[str, Any]) -> str:
    for field_name in (
        "row_id",
        "target_row_id",
        "design_artifact_row_id",
        "requested_row_id",
        "item_id",
        "component_id",
        "interface_id",
        "fixture_id",
        "control_id",
        "hazard_id",
        "step_id",
        "id",
        "name",
        "role",
        "required_for",
        "target_role",
    ):
        text = str(item.get(field_name, "") or "").strip()
        if text:
            return text
    return ""


def _extract_row_scoped_required_fields(normalized_feedback: str) -> tuple[OperatorFeedbackRowScopedRequiredField, ...]:
    if "missing row-level fields" not in normalized_feedback and "missing row level fields" not in normalized_feedback:
        return ()
    obligations: list[OperatorFeedbackRowScopedRequiredField] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for parsed in _json_arrays_from_feedback(normalized_feedback):
        for item in parsed:
            if not isinstance(item, Mapping):
                continue
            artifact = str(
                item.get("artifact", "")
                or item.get("artifact_name", "")
                or item.get("target_artifact", "")
                or ""
            ).strip()
            raw_fields = list(item.get("missing_fields", []) or item.get("required_fields", []) or [])
            fields = [
                field
                for field in (_normalize_required_field(field) for field in raw_fields)
                if field
            ]
            row_id = _row_scoped_obligation_row_id(item)
            if not artifact or not fields or not row_id:
                continue
            requested_row_id = str(item.get("requested_row_id", "") or "").strip()
            target_row_id = str(item.get("target_row_id", "") or item.get("design_artifact_row_id", "") or "").strip()
            role = _normalize_role(
                item.get("target_role", "")
                or item.get("role", "")
                or item.get("required_for", "")
                or row_id
            )
            key = (artifact, _normalize_role(row_id), tuple(dict.fromkeys(fields)))
            if key in seen:
                continue
            seen.add(key)
            obligations.append(
                OperatorFeedbackRowScopedRequiredField(
                    obligation_id=f"row_required_field:{artifact}:{_normalize_role(row_id)}:{len(obligations) + 1}",
                    artifact_name=artifact,
                    row_id=row_id,
                    role=role,
                    required_fields=tuple(dict.fromkeys(fields)),
                    requested_row_id=requested_row_id,
                    target_row_id=target_row_id,
                    source_phrase=f"missing row-level fields: {json.dumps(item, sort_keys=True)}"[:500],
                )
            )
    return tuple(obligations)


def parse_operator_feedback_obligations(feedback: Any) -> OperatorFeedbackObligationContract:
    normalized_feedback = normalize_feedback_text(feedback)
    artifacts = _artifact_mentions(normalized_feedback)
    primary_artifact = _primary_artifact(normalized_feedback, artifacts)
    self_finalization_blockers = (
        ("operator_feedback_self_finalization_blocker",)
        if feedback_blocks_self_finalization(normalized_feedback)
        else ()
    )
    return OperatorFeedbackObligationContract(
        required_target_artifacts=artifacts,
        required_fields_by_artifact=_required_fields_by_artifact(normalized_feedback, primary_artifact),
        forbidden_assignments=_extract_forbidden_assignments(normalized_feedback),
        required_role_splits=_extract_role_splits(normalized_feedback, primary_artifact),
        row_scoped_required_fields=_extract_row_scoped_required_fields(normalized_feedback),
        role_split_quality_requirements=_extract_role_split_quality_requirements(normalized_feedback),
        self_finalization_blockers=self_finalization_blockers,
    )


def _row_id(row: Mapping[str, Any]) -> str:
    for field in (
        "row_id",
        "item_id",
        "component_id",
        "interface_id",
        "fixture_id",
        "control_id",
        "hazard_id",
        "step_id",
        "id",
        "name",
    ):
        value = str(row.get(field, "") or "").strip()
        if value:
            return value
    return ""


def _row_identity_tokens(row: Mapping[str, Any]) -> set[str]:
    values = {
        field: row.get(field)
        for field in IDENTITY_FIELDS
        if row.get(field) not in (None, "")
    }
    identity_tokens = _tokens(values, minimum=2)
    row_id = _row_id(row)
    if row_id:
        identity_tokens.add(_normalize_role(row_id))
    return identity_tokens


def _row_source_tokens(row: Mapping[str, Any]) -> set[str]:
    values = {
        field: row.get(field)
        for field in SOURCE_FIELDS
        if row.get(field) not in (None, "")
    }
    return _tokens(values, minimum=2)


def _row_matches_role(row: Mapping[str, Any], role: str) -> bool:
    normalized_role = _normalize_role(role)
    if not normalized_role:
        return False
    if normalized_role in _row_identity_tokens(row):
        return True
    for field_name in IDENTITY_FIELDS:
        value = _normalize_role(row.get(field_name, ""))
        if value and (value == normalized_role or normalized_role in value.split("_")):
            return True
    return False


def _row_has_forbidden_assignment(row: Mapping[str, Any], assignment: OperatorFeedbackForbiddenAssignment) -> bool:
    if not _row_matches_role(row, assignment.role):
        return False
    row_tokens = _row_source_tokens(row) | _row_identity_tokens(row)
    return any(term in row_tokens for term in assignment.forbidden_terms)


def _contract_forbidden_terms(contract: OperatorFeedbackObligationContract) -> set[str]:
    terms: set[str] = set()
    for assignment in contract.forbidden_assignments:
        terms.update(str(term) for term in assignment.forbidden_terms)
    return terms


def _row_field_present(row: Mapping[str, Any], required_field: str) -> bool:
    for field_name in ROW_FIELD_ALTERNATIVES.get(required_field, (required_field,)):
        current: Any = row
        for part in field_name.split("."):
            if not isinstance(current, Mapping) or part not in current:
                current = None
                break
            current = current.get(part)
        if current not in (None, "", [], {}):
            return True
    for spec_key in ("spec_values", "concrete_spec_values"):
        spec_values = row.get(spec_key)
        if isinstance(spec_values, Mapping):
            for field_name in ROW_FIELD_ALTERNATIVES.get(required_field, (required_field,)):
                for candidate in (field_name, _normalize_required_field(field_name), _normalize_role(field_name)):
                    if candidate and spec_values.get(candidate) not in (None, "", [], {}):
                        return True
        elif isinstance(spec_values, list):
            for item in spec_values:
                if isinstance(item, Mapping) and _row_field_present(item, required_field):
                    return True
        elif isinstance(spec_values, str):
            normalized = normalize_feedback_text(spec_values)
            for field_name in ROW_FIELD_ALTERNATIVES.get(required_field, (required_field,)):
                token = _normalize_role(field_name)
                if token and re.search(rf"\b{re.escape(token)}\s*[:=]", normalized):
                    return True
    return False


def _normalized_row_reference_values(row: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for field_name in (
        "row_id",
        "item_id",
        "component_id",
        "interface_id",
        "fixture_id",
        "control_id",
        "hazard_id",
        "step_id",
        "id",
        "name",
        "target_row_id",
        "design_artifact_row_id",
        "requested_row_id",
        "closes_requested_row_id",
        "closes_target_row_id",
        "closes_design_artifact_row_id",
        "closes_row_id",
    ):
        value = row.get(field_name)
        if value not in (None, "", [], {}):
            values.add(_normalize_role(value))
    for field_name in (
        "support_row_ids",
        "support_pack_row_refs",
        "source_acquisition_from_design_row_ids",
        "closed_requested_row_ids",
        "closed_target_row_ids",
    ):
        value = row.get(field_name)
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if item not in (None, ""):
                    values.add(_normalize_role(item))
        elif value not in (None, "", [], {}):
            values.add(_normalize_role(value))
    return {value for value in values if value}


def _row_matches_row_scoped_obligation(
    row: Mapping[str, Any],
    obligation: OperatorFeedbackRowScopedRequiredField,
) -> bool:
    row_refs = _normalized_row_reference_values(row)
    expected_refs = {
        _normalize_role(value)
        for value in (
            obligation.row_id,
            obligation.requested_row_id,
            obligation.target_row_id,
        )
        if str(value or "").strip()
    }
    if row_refs & {value for value in expected_refs if value}:
        return True
    if obligation.role and _row_matches_role(row, obligation.role):
        return True
    if bool(row.get("source_backed_field_closure", False)):
        obligation_tokens = _tokens(
            {
                "row_id": obligation.row_id,
                "role": obligation.role,
                "target_row_id": obligation.target_row_id,
            },
            minimum=4,
        )
        row_tokens = _tokens(
            {
                "item_id": row.get("item_id"),
                "name": row.get("name"),
                "category": row.get("category"),
                "required_for": row.get("required_for"),
                "target_role": row.get("target_role"),
                "claim": row.get("claim"),
                "spec_values": row.get("spec_values"),
            },
            minimum=4,
        )
        ignored = {"source", "backed", "build", "depth", "reduction"}
        overlap = (obligation_tokens - ignored) & (row_tokens - ignored)
        if len(overlap) >= 2:
            return True
    return False


def _row_satisfies_split_role(row: Mapping[str, Any], split_role: str) -> bool:
    normalized_role = _normalize_split_role(split_role)
    identity_blob = " ".join(str(row.get(field, "") or "") for field in IDENTITY_FIELDS)
    normalized_blob = _normalize_role(identity_blob)
    if not normalized_role:
        return False
    if normalized_role in normalized_blob:
        return True
    blob_tokens = {_normalize_split_role(part) for part in normalized_blob.split("_") if part}
    return normalized_role in blob_tokens


def _role_split_supersession_for_artifact(
    *,
    artifact: str,
    row_list: list[dict[str, Any]],
    contract: OperatorFeedbackObligationContract,
) -> dict[str, Any]:
    superseded_ids: list[str] = []
    split_row_ids: list[str] = []
    required_fields = list(contract.required_fields_by_artifact.get(artifact, ()) or [])
    for split in contract.required_role_splits:
        if split.artifact_name != artifact:
            continue
        resolved_rows: list[dict[str, Any]] = []
        for role in split.required_roles:
            matching_row = next(
                (
                    row
                    for row in row_list
                    if _normalize_role(_row_id(row)) != split.base_role
                    and _row_satisfies_split_role(row, role)
                    and all(_row_field_present(row, field_name) for field_name in required_fields)
                ),
                None,
            )
            if matching_row is None:
                resolved_rows = []
                break
            resolved_rows.append(matching_row)
        if not resolved_rows:
            continue
        for row in row_list:
            row_id = _row_id(row)
            if _normalize_role(row_id) == split.base_role and row_id not in superseded_ids:
                superseded_ids.append(row_id)
        for row in resolved_rows:
            row_id = _row_id(row)
            if row_id and row_id not in split_row_ids:
                split_row_ids.append(row_id)
    return {
        "superseded_aggregate_row_ids": superseded_ids,
        "split_lane_rows_used_for_feedback_closure": split_row_ids,
    }


def _row_payloads(payloads: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows_by_artifact: dict[str, list[dict[str, Any]]] = {}
    for artifact_name, payload in payloads.items():
        if not isinstance(payload, Mapping):
            continue
        rows: list[dict[str, Any]] = []
        for row_key in ROW_KEYS_BY_ARTIFACT.get(str(artifact_name), ("rows", "items")):
            for row in list(payload.get(row_key, []) or []):
                if isinstance(row, Mapping):
                    rows.append(dict(row))
        if rows:
            rows_by_artifact[str(artifact_name)] = rows
    return rows_by_artifact


def assess_operator_feedback_obligations(
    feedback: Any,
    *,
    payloads: Mapping[str, Any] | None = None,
    rows_by_artifact: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    normalized_feedback = normalize_feedback_text(feedback)
    contract = parse_operator_feedback_obligations(normalized_feedback)
    contract_payload = _contract_dict(contract)
    blocks_self_finalization = bool(contract.self_finalization_blockers)
    if rows_by_artifact is None:
        rows_by_artifact = _row_payloads(dict(payloads or {}))
    gaps: dict[str, list[dict[str, Any]]] = {}
    explicit_forbidden_terms = _contract_forbidden_terms(contract)
    row_scoped_by_artifact: dict[str, list[OperatorFeedbackRowScopedRequiredField]] = {}
    for obligation in contract.row_scoped_required_fields:
        row_scoped_by_artifact.setdefault(obligation.artifact_name, []).append(obligation)
    closed_obligation_ids: list[str] = []
    superseded_aggregate_row_ids: list[str] = []
    split_lane_rows_used_for_feedback_closure: list[str] = []
    evaluated_artifacts: set[str] = set()

    for artifact_name, rows in rows_by_artifact.items():
        artifact = str(artifact_name)
        evaluated_artifacts.add(artifact)
        row_list = [dict(row) for row in list(rows or []) if isinstance(row, Mapping)]
        supersession = _role_split_supersession_for_artifact(
            artifact=artifact,
            row_list=row_list,
            contract=contract,
        )
        artifact_superseded_ids = set(supersession["superseded_aggregate_row_ids"])
        superseded_aggregate_row_ids.extend(supersession["superseded_aggregate_row_ids"])
        split_lane_rows_used_for_feedback_closure.extend(
            supersession["split_lane_rows_used_for_feedback_closure"]
        )
        for index, row in enumerate(row_list):
            row_id = _row_id(row)
            if row_id in artifact_superseded_ids:
                continue
            replacement_required = bool(row.get("operator_feedback_replacement_required", False))
            if replacement_required:
                gaps.setdefault(artifact, []).append(
                    {
                        "gap_kind": "required_source_replacement_not_selected",
                        "artifact_name": artifact,
                        "row_index": index,
                        "row_id": row_id,
                        "role": _normalize_role(row_id),
                        "field": "",
                        "forbidden_value": "",
                        "obligation_reason": "required_source_replacement_not_selected",
                        "forbidden_terms": [
                            str(term)
                            for term in list(row.get("operator_feedback_forbidden_terms", []) or [])
                            if str(term) in explicit_forbidden_terms
                        ],
                        "expected_resolution": "replace this row/value assignment or mark the source selection unresolved with concrete follow-up evidence",
                        "source_phrase": "",
                        "obligation_id": "compat:operator_feedback_replacement_required",
                    }
                )
            for assignment in contract.forbidden_assignments:
                if not _row_has_forbidden_assignment(row, assignment):
                    continue
                gaps.setdefault(artifact, []).append(
                    {
                        "gap_kind": "forbidden_assignment_present",
                        "artifact_name": artifact,
                        "row_index": index,
                        "row_id": row_id,
                        "role": assignment.role,
                        "field": "source_assignment",
                        "forbidden_value": assignment.forbidden_value,
                        "obligation_reason": "operator_feedback_forbidden_role_value",
                        "forbidden_terms": list(assignment.forbidden_terms),
                        "expected_resolution": "replace this explicit forbidden role/source assignment or mark the role unresolved with source-backed follow-up evidence",
                        "source_phrase": assignment.source_phrase,
                        "obligation_id": assignment.obligation_id,
                    }
                )

        row_scoped = row_scoped_by_artifact.get(artifact, [])
        for obligation in row_scoped:
            matching_rows = [
                (index, row)
                for index, row in enumerate(row_list)
                if _row_matches_row_scoped_obligation(row, obligation)
            ]
            closed_fields = {
                field_name
                for field_name in obligation.required_fields
                if any(_row_field_present(row, field_name) for _index, row in matching_rows)
            }
            if closed_fields == set(obligation.required_fields):
                closed_obligation_ids.append(obligation.obligation_id)
                continue
            missing_fields = [
                field_name
                for field_name in obligation.required_fields
                if field_name not in closed_fields
            ]
            best_index = matching_rows[0][0] if matching_rows else -1
            for field_name in missing_fields:
                gaps.setdefault(artifact, []).append(
                    {
                        "gap_kind": "row_scoped_required_field_missing",
                        "artifact_name": artifact,
                        "row_index": best_index,
                        "row_id": obligation.row_id,
                        "role": obligation.role,
                        "field": field_name,
                        "forbidden_value": "",
                        "obligation_reason": "operator_feedback_row_scoped_required_field_missing",
                        "forbidden_terms": [],
                        "expected_resolution": f"fill {field_name} on {obligation.row_id} or a source-backed closure row referencing the requested/target row id",
                        "source_phrase": obligation.source_phrase,
                        "obligation_id": obligation.obligation_id,
                        "requested_row_id": obligation.requested_row_id,
                        "target_row_id": obligation.target_row_id,
                    }
                )

        required_fields = list(contract.required_fields_by_artifact.get(artifact, ()) or [])
        if row_scoped:
            required_fields = []
        if required_fields and row_list:
            for index, row in enumerate(row_list):
                if _row_id(row) in artifact_superseded_ids:
                    continue
                missing_fields = [
                    field_name
                    for field_name in required_fields
                    if not _row_field_present(row, field_name)
                ]
                for field_name in missing_fields:
                    gaps.setdefault(artifact, []).append(
                        {
                            "gap_kind": "required_field_missing",
                            "artifact_name": artifact,
                            "row_index": index,
                            "row_id": _row_id(row),
                            "role": _normalize_role(_row_id(row)),
                            "field": field_name,
                            "forbidden_value": "",
                            "obligation_reason": "operator_feedback_required_field_missing",
                            "forbidden_terms": [],
                            "expected_resolution": f"fill {field_name} with concrete source-backed evidence requested by operator feedback",
                            "source_phrase": normalized_feedback[:300],
                            "obligation_id": f"required_field:{artifact}:{field_name}",
                        }
                    )

    for artifact, row_scoped in row_scoped_by_artifact.items():
        if artifact in evaluated_artifacts:
            continue
        for obligation in row_scoped:
            for field_name in obligation.required_fields:
                gaps.setdefault(artifact, []).append(
                    {
                        "gap_kind": "row_scoped_required_field_missing",
                        "artifact_name": artifact,
                        "row_index": -1,
                        "row_id": obligation.row_id,
                        "role": obligation.role,
                        "field": field_name,
                        "forbidden_value": "",
                        "obligation_reason": "operator_feedback_row_scoped_required_field_missing",
                        "forbidden_terms": [],
                        "expected_resolution": f"fill {field_name} on {obligation.row_id} or a source-backed closure row referencing the requested/target row id",
                        "source_phrase": obligation.source_phrase,
                        "obligation_id": obligation.obligation_id,
                        "requested_row_id": obligation.requested_row_id,
                        "target_row_id": obligation.target_row_id,
                    }
                )

    for split in contract.required_role_splits:
        artifact = split.artifact_name
        row_list = [
            dict(row)
            for row in list(rows_by_artifact.get(artifact, []) or [])
            if isinstance(row, Mapping)
        ]
        missing_roles = [
            role
            for role in split.required_roles
            if not any(_row_satisfies_split_role(row, role) for row in row_list)
        ]
        if missing_roles:
            gaps.setdefault(artifact, []).append(
                {
                    "gap_kind": "required_role_split_missing",
                    "artifact_name": artifact,
                    "row_index": -1,
                    "row_id": split.base_role,
                    "role": split.base_role,
                    "field": "role_split",
                    "forbidden_value": "",
                    "obligation_reason": "operator_feedback_required_role_split_missing",
                    "forbidden_terms": [],
                    "missing_roles": missing_roles,
                    "expected_resolution": f"split {split.base_role} into concrete rows for {', '.join(missing_roles)}",
                    "source_phrase": split.source_phrase,
                    "obligation_id": split.obligation_id,
                }
            )

    gap_count = sum(len(rows) for rows in gaps.values())
    return {
        "operator_feedback_obligation_schema_version": OPERATOR_FEEDBACK_OBLIGATION_SCHEMA_VERSION,
        "operator_feedback_obligations": contract_payload,
        "operator_feedback_required_artifacts": list(contract.required_target_artifacts),
        "operator_feedback_required_fields_by_artifact": {
            artifact: list(fields)
            for artifact, fields in contract.required_fields_by_artifact.items()
        },
        "operator_feedback_forbidden_assignments": contract_payload["forbidden_assignments"],
        "operator_feedback_required_role_splits": contract_payload["required_role_splits"],
        "row_scoped_operator_feedback_obligations": contract_payload["row_scoped_required_fields"],
        "closed_operator_feedback_obligation_ids": list(dict.fromkeys(closed_obligation_ids)),
        "aggregate_role_row_superseded": bool(superseded_aggregate_row_ids),
        "superseded_aggregate_row_ids": list(dict.fromkeys(superseded_aggregate_row_ids)),
        "split_lane_rows_used_for_feedback_closure": list(
            dict.fromkeys(split_lane_rows_used_for_feedback_closure)
        ),
        "operator_feedback_role_split_quality_requirements": contract_payload["role_split_quality_requirements"],
        "operator_feedback_obligation_parse_warnings": list(contract.parse_warnings),
        "operator_feedback_obligation_passed": gap_count == 0,
        "operator_feedback_obligation_gaps": gaps,
        "operator_feedback_obligation_gap_count": gap_count,
        "operator_feedback_self_finalization_blocked": blocks_self_finalization,
    }


def source_rejected_by_operator_feedback(
    feedback: Any,
    *,
    component_id: str,
    source_row: Mapping[str, Any],
) -> dict[str, Any]:
    contract = parse_operator_feedback_obligations(feedback)
    row = {
        "item_id": component_id,
        "name": component_id.replace("_", " "),
        **dict(source_row),
    }
    for assignment in contract.forbidden_assignments:
        if _row_has_forbidden_assignment(row, assignment):
            return {
                "rejected": True,
                "matched_terms": list(assignment.forbidden_terms),
                "forbidden_assignment": {
                    **asdict(assignment),
                    "forbidden_terms": list(assignment.forbidden_terms),
                },
            }
    return {
        "rejected": False,
        "matched_terms": [],
    }
