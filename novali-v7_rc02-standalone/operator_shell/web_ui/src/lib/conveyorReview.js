const text = (...values) => {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const next = String(value).trim();
    if (next) return next;
  }
  return "";
};

const array = (value) => (Array.isArray(value) ? value : []);
const record = (value) => (value && typeof value === "object" ? value : {});

const BUILD_GRADE_ARTIFACTS = [
  "directive_deliverables.json",
  "directive_blueprint.md",
  "technical_documentation.md",
  "implementation_readiness_review.json",
  "bill_of_materials.json",
  "subsystem_matrix.json",
  "interface_specifications.json",
  "dependency_matrix.json",
  "validation_protocols.json",
  "validation_fixtures.json",
  "prototype_milestones.json",
  "prototype_assembly_plan.json",
  "risk_controls.json",
  "claim_evidence_register.json",
  "novelty_delta.json",
];

const BUILD_GRADE_EVIDENCE = [
  "conveyor_child_deliverables_built",
  "conveyor_child_technical_documentation_built",
  "conveyor_child_build_grade_artifacts_built",
];

const ARTIFACT_TABLE_COLLECTIONS = {
  "subsystem_matrix.json": ["subsystems", "rows", "items"],
  "interface_specifications.json": ["interfaces", "rows", "items"],
  "dependency_matrix.json": ["dependencies", "rows", "items"],
  "validation_protocols.json": ["protocols", "validations", "rows", "items"],
  "validation_fixtures.json": ["fixtures", "validation_fixtures", "rows", "items"],
  "prototype_milestones.json": ["milestones", "rows", "items"],
  "prototype_assembly_plan.json": ["assembly_steps", "steps", "rows", "items"],
  "bill_of_materials.json": ["components", "materials", "dependencies", "rows", "items"],
  "risk_controls.json": ["risk_controls", "controls", "rows", "items"],
  "claim_evidence_register.json": ["claims", "claim_evidence", "rows", "items"],
  "novelty_delta.json": ["novel_items", "novelty", "rows", "items"],
  "directive_deliverables.json": ["deliverables", "rows", "items"],
  "implementation_readiness_review.json": ["gates", "readiness_gates", "rows", "items"],
};

const ARTIFACT_PURPOSES = {
  "bill_of_materials.json": "Bill of materials: components, materials, quantities, procurement notes, and build dependencies.",
  "claim_evidence_register.json": "Claim evidence register: claims, support references, evidence quality, and unresolved proof gaps.",
  "dependency_matrix.json": "Dependency matrix: subsystem prerequisites, runtime dependencies, evidence constraints, and risks if missing.",
  "directive_blueprint.md": "Directive blueprint: scope, target architecture, deliverable plan, and review boundary.",
  "directive_deliverables.json": "Directive deliverables: expected artifact set, completion criteria, and package coverage.",
  "implementation_readiness_review.json": "Implementation readiness review: gate verdicts, go/no-go conditions, and operator approval boundaries.",
  "interface_specifications.json": "Interface specifications: inputs, outputs, contracts, safety boundaries, and integration events.",
  "novelty_delta.json": "Novelty delta: new design claims, deltas from prior work, and material change evidence.",
  "prototype_assembly_plan.json": "Prototype assembly plan: build sequence, expected files, fixtures, and validation steps.",
  "prototype_milestones.json": "Prototype milestones: staged build checkpoints, acceptance targets, and delivery order.",
  "risk_controls.json": "Risk controls: hazards, mitigations, acceptance thresholds, and execution gates.",
  "subsystem_matrix.json": "Subsystem matrix: subsystem inventory, responsibilities, boundaries, and interactions.",
  "technical_documentation.md": "Technical documentation: narrative implementation details, subsystem behavior, and operator handoff context.",
  "validation_fixtures.json": "Validation fixtures: concrete test fixtures, sample inputs, expected outputs, and evidence hooks.",
  "validation_protocols.json": "Validation protocols: test procedures, measurements, acceptance thresholds, and evidence capture.",
};

export const CORE_GROWTH_DIRECTIVE_TITLE = "Develop Novali framework and support child agents";
export const CORE_GROWTH_DIRECTIVE_SUMMARY =
  "Built-in kernel mission: improve Novali as an agent framework, support child agent directives with reusable knowledge and skill capabilities, satisfy checkout/support requests, and optimize child-agent designs for future conveyor work.";

function titleFromOutcome(outcome) {
  const source = text(outcome);
  const directive = source.match(/DIRECTIVE\s*:\s*([^*\n]+)/i);
  if (directive) return directive[1].trim();
  const builtFor = source.match(/built\s+\d+\s+deliverable scaffold\(s\)\s+for\s+(.+?)\s+and returned/i);
  if (builtFor) return builtFor[1].trim();
  const expandedFor = source.match(/expanded\s+\d+\s+deliverable\(s\)\s+for\s+(.+?)\s+into technical documentation/i);
  if (expandedFor) return expandedFor[1].trim();
  return source.slice(0, 80) || "Returned conveyor work";
}

function countLabel(count, singular, plural = `${singular}s`) {
  return count === 1 ? `1 ${singular}` : `${count} ${plural}`;
}

function formatKind(value) {
  return text(value, "unknown")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function buildConveyorReturnReviewItems(status) {
  return array(status?.returned_packets)
    .filter((packet) => text(packet?.review_state, "pending_operator_review") === "pending_operator_review")
    .sort((left, right) => {
      const leftTime = Date.parse(text(left?.generated_at, left?.reviewed_at));
      const rightTime = Date.parse(text(right?.generated_at, right?.reviewed_at));
      return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
    })
    .map((packet) => {
      const artifacts = array(packet?.artifacts).map((item) => text(item)).filter(Boolean);
      const evidence = array(packet?.verification_evidence).map((item) => text(item)).filter(Boolean);
      const supportRequests = array(packet?.missing_capability_requests);
      return {
        returnPacketId: text(packet?.return_packet_id),
        directiveId: text(packet?.directive_id),
        childRunId: text(packet?.child_run_id),
        title: text(packet?.directive_title, packet?.directive_display_title, packet?.title, titleFromOutcome(packet?.outcome_summary)),
        outcomeSummary: text(packet?.outcome_summary, "No outcome summary returned."),
        artifactLabel: countLabel(artifacts.length, "artifact"),
        evidenceLabel: evidence.join(", ") || "No verification evidence returned.",
        supportLabel: countLabel(supportRequests.length, "support request"),
        artifacts,
        supportRequests,
        requestedFollowUp: text(packet?.requested_follow_up, "operator_review_return_packet"),
      };
    });
}

export function buildConveyorSupportRequestItems(status) {
  return array(status?.support_requests)
    .filter((request) => text(request?.support_state) === "pending_operator_review")
    .sort((left, right) => {
      const leftTime = Date.parse(text(left?.updated_at, left?.generated_at));
      const rightTime = Date.parse(text(right?.updated_at, right?.generated_at));
      return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
    })
    .map((request) => ({
      supportRequestId: text(request?.support_request_id),
      directiveId: text(request?.directive_id),
      directiveTitle: text(request?.directive_title, request?.directive_display_title),
      returnPacketId: text(request?.return_packet_id),
      capability: text(request?.capability),
      capabilityLabel: formatKind(request?.capability),
      stateLabel: formatKind(request?.support_state),
      providerLabel: text(request?.trusted_source_provider_id, "trusted source"),
      requestedPackFamily: text(request?.requested_pack_family),
      reason: text(request?.reason, "Child requested kernel-mediated knowledge checkout."),
    }));
}

function packetBuildGradeReady(packet) {
  const artifacts = new Set(array(packet?.artifacts).map((item) => text(item)));
  const evidence = new Set(array(packet?.verification_evidence).map((item) => text(item)));
  return (
    BUILD_GRADE_ARTIFACTS.every((item) => artifacts.has(item)) &&
    BUILD_GRADE_EVIDENCE.every((item) => evidence.has(item))
  );
}

function buildCampaignManifestIndex(status) {
  const byDirective = new Map();
  for (const manifest of [...array(status?.campaigns), ...array(status?.campaign_manifests)]) {
    const row = record(manifest);
    const directiveId = text(row.directive_id);
    if (directiveId) byDirective.set(directiveId, row);
  }
  for (const directive of array(status?.directive_catalog)) {
    const row = record(directive);
    const directiveId = text(row.directive_id);
    const manifest = record(row.campaign_manifest);
    if (directiveId && Object.keys(manifest).length && !byDirective.has(directiveId)) {
      byDirective.set(directiveId, manifest);
    }
  }
  return byDirective;
}

function artifactQualityClean(manifest, artifactName) {
  const artifact = record(record(manifest?.canonical_artifacts)[artifactName]);
  if (!Object.keys(artifact).length) return false;
  const failed = array(artifact.failed_quality_gates).map((item) => text(item)).filter(Boolean);
  return failed.length === 0 && Number(artifact.quality_depth_score || 0) >= 0.99;
}

function artifactPurpose(name) {
  return text(ARTIFACT_PURPOSES[name], `${formatKind(name.replace(/\.[^.]+$/, ""))}: returned artifact content.`);
}

function sentenceLabel(value) {
  const formatted = text(value).replace(/_/g, " ");
  return formatted ? formatted.charAt(0).toUpperCase() + formatted.slice(1).toLowerCase() : "";
}

function lowerLabel(value) {
  return text(value).replace(/_/g, " ").toLowerCase();
}

function summarizeCanonicalArtifact(name, row) {
  const failed = array(row.failed_quality_gates).map((item) => text(item)).filter(Boolean);
  const parts = [artifactPurpose(name)];
  if (failed.length) parts.push(`Quality needs attention: ${failed.map(lowerLabel).join(", ")}.`);
  if (row.execution_gated_by_operator_approval) parts.push("Operator approval gates execution.");
  const qualityState = text(row.quality_state);
  if (!failed.length && qualityState) parts.push(`Quality state: ${formatKind(qualityState)}.`);
  return parts.join(" ");
}

function buildCanonicalArtifactRows(manifest) {
  return Object.entries(record(manifest?.canonical_artifacts))
    .map(([artifactName, artifact]) => {
      const row = record(artifact);
      const compiled = record(row.compiled_documentation);
      return {
        artifactName: text(artifactName),
        version: Number(row.version || 0),
        hash: text(row.hash, row.sha256),
        sizeBytes: Number(row.size_bytes || 0),
        updatedAt: text(row.mtime_utc, row.updated_at),
        depthScore: Number(row.quality_depth_score || row.depth_score || row.build_package_depth_score || 0),
        qualityDepthScore: Number(row.quality_depth_score || row.depth_score || row.build_package_depth_score || 0),
        qualityState: text(row.quality_state),
        failedQualityGates: array(row.failed_quality_gates).map((item) => text(item)).filter(Boolean),
        executionGated: Boolean(row.execution_gated_by_operator_approval),
        summary: summarizeCanonicalArtifact(text(artifactName), row),
        compiledDocumentation: Object.keys(compiled).length
          ? {
              artifactName: text(compiled.artifact_name),
              sourceArtifact: text(compiled.source_artifact),
              originalSha256: text(compiled.original_sha256),
              compiledSha256: text(compiled.compiled_sha256),
              compiledAt: text(compiled.compiled_at),
              authorityBoundary: text(compiled.authority_boundary),
            }
          : null,
      };
    })
    .sort((left, right) => left.artifactName.localeCompare(right.artifactName));
}

function artifactSourceLabel(source) {
  const value = text(source);
  if (value === "campaign_canonical_latest") return "Campaign canonical artifacts";
  if (value === "child_workspace_latest") return "Child workspace artifacts";
  return value ? formatKind(value) : "";
}

function buildImplementationHandoffSummary(handoff) {
  const row = record(handoff);
  if (!Object.keys(row).length) return {};
  const chosenPrototypeSlice = record(row.chosen_prototype_slice);
  return {
    schemaName: text(row.schema_name),
    chosenPrototypeSlice: {
      name: text(chosenPrototypeSlice.name),
      stepId: text(chosenPrototypeSlice.step_id),
      moduleOutput: text(chosenPrototypeSlice.module_output),
      interfaces: array(chosenPrototypeSlice.interfaces).map((item) => text(item)).filter(Boolean),
    },
    buildSteps: array(row.build_steps).map((item) => text(item)).filter(Boolean),
    fixtures: array(row.fixtures).map((item) => record(item)),
    expectedFiles: array(row.expected_files).map((item) => text(item)).filter(Boolean),
    acceptanceTests: array(row.acceptance_tests).map((item) => text(item)).filter(Boolean),
    safetyGates: array(row.safety_gates).map((item) => record(item)),
    evidenceRefs: array(row.evidence_refs).map((item) => text(item)).filter(Boolean),
    authorityBoundary: text(row.authority_boundary),
  };
}

function supportPackRefsForDirective(supportRequests, directiveId) {
  return supportRequests
    .filter((request) => text(request?.directive_id) === directiveId && text(request?.support_state) === "satisfied")
    .map((request) => text(request?.satisfied_pack_ref, request?.support_request_id))
    .filter(Boolean);
}

function formatListLabel(values) {
  return array(values)
    .map((item) => text(item))
    .filter(Boolean)
    .map(formatKind)
    .join(", ");
}

function valueLabel(value) {
  if (Array.isArray(value)) return value.map((item) => text(item)).filter(Boolean).join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return text(value);
}

function pickArtifactRows(name, parsed) {
  if (Array.isArray(parsed)) return parsed.filter((item) => item && typeof item === "object");
  const source = record(parsed);
  const collectionNames = ARTIFACT_TABLE_COLLECTIONS[name] || ["rows", "items"];
  for (const collectionName of collectionNames) {
    const rows = array(source[collectionName]).filter((item) => item && typeof item === "object");
    if (rows.length) return rows;
  }
  return [];
}

function columnsForRows(rows) {
  const columns = [];
  for (const row of rows) {
    for (const key of Object.keys(record(row))) {
      if (!columns.includes(key)) columns.push(key);
    }
  }
  return columns;
}

function previewUnitForArtifact(name) {
  if (name === "claim_evidence_register.json") return "claim";
  if (name === "interface_specifications.json") return "interface";
  if (name === "validation_protocols.json") return "protocol";
  if (name === "validation_fixtures.json") return "fixture";
  if (name === "prototype_milestones.json") return "milestone";
  if (name === "prototype_assembly_plan.json") return "step";
  if (name === "bill_of_materials.json") return "component";
  if (name === "risk_controls.json") return "control";
  if (name === "directive_deliverables.json") return "deliverable";
  if (name === "implementation_readiness_review.json") return "gate";
  if (name === "novelty_delta.json") return "item";
  return "subsystem_matrix.json" === name ? "subsystem" : "row";
}

function summarizeArtifactPreview(name, rows, parsed) {
  const displayName = sentenceLabel(name.replace(/\.[^.]+$/, ""));
  if (rows.length) {
    const unit = previewUnitForArtifact(name);
    const columns = columnsForRows(rows).slice(0, 3);
    return `${displayName} with ${rows.length} ${unit}${rows.length === 1 ? "" : "s"}${
      columns.length ? `; fields: ${columns.join(", ")}` : ""
    }.`;
  }
  const keys = Object.keys(record(parsed)).slice(0, 5);
  return `${displayName}${keys.length ? ` with top-level fields: ${keys.join(", ")}` : ""}.`;
}

export function buildArtifactPreviewModel(preview = {}) {
  const artifactName = text(preview.artifact_name, preview.name, preview.artifactName, "artifact");
  const rawContent = text(preview.content, preview.text, preview.rawContent);
  if (!rawContent) {
    return {
      viewKind: "empty",
      artifactName,
      title: artifactName,
      columns: [],
      rows: [],
      summary: "No artifact content returned.",
      rowCount: 0,
      rawContent: "",
    };
  }
  try {
    const parsed = JSON.parse(rawContent);
    const rows = pickArtifactRows(artifactName, parsed);
    if (rows.length) {
      const columns = columnsForRows(rows);
      return {
        viewKind: "table",
        artifactName,
        title: artifactName.replace(/_/g, " "),
        columns,
        rows: rows.map((row) => {
          const next = {};
          for (const column of columns) next[column] = valueLabel(record(row)[column]);
          return next;
        }),
        summary: summarizeArtifactPreview(artifactName, rows, parsed),
        rowCount: rows.length,
        rawContent,
      };
    }
    if (parsed && typeof parsed === "object") {
      const columns = ["field", "value"];
      const rows = Object.entries(record(parsed)).map(([field, value]) => ({ field, value: valueLabel(value) }));
      return {
        viewKind: rows.length ? "table" : "json",
        artifactName,
        title: artifactName.replace(/_/g, " "),
        columns,
        rows,
        summary: summarizeArtifactPreview(artifactName, [], parsed),
        rowCount: rows.length,
        rawContent,
      };
    }
  } catch {
    // Plain text and markdown artifacts fall through to the text renderer.
  }
  return {
    viewKind: "text",
    artifactName,
    title: artifactName.replace(/_/g, " "),
    columns: [],
    rows: [],
    summary: artifactPurpose(artifactName),
    rowCount: 0,
    rawContent,
  };
}

export function buildConveyorBatchReturnActions({ returnPacketIds, feedback, supportRequiredReturnIds = [] } = {}) {
  const note = text(feedback, "Request a deeper build-grade pass with expanded engineering detail and evidence.");
  const supportRequired = new Set(array(supportRequiredReturnIds).map((item) => text(item)).filter(Boolean));
  return array(returnPacketIds)
    .map((returnPacketId) => text(returnPacketId))
    .filter(Boolean)
    .map((returnPacketId) => ({
      returnPacketId,
      action: "requeue",
      payload: {
        feedback: note,
        operator_note: note,
        ...(supportRequired.has(returnPacketId) ? { approve_support_before_requeue: true } : {}),
      },
    }));
}

export function buildReturnsWorkbench({ conveyorStatus, conveyorSupportRequests, conveyorSummary } = {}) {
  const status = record(conveyorStatus);
  const supportPayload = Object.keys(record(conveyorSupportRequests)).length
    ? record(conveyorSupportRequests)
    : status;
  const summary = record(conveyorSummary);
  const statusPendingReturns = buildConveyorReturnReviewItems(status);
  const summaryPendingReturnItems = buildConveyorReturnReviewItems(summary);
  const statusReturnCounts = record(status.return_counts_by_review_state);
  const statusHasReturnTruth = Boolean(
    Array.isArray(status.returned_packets)
      || Object.prototype.hasOwnProperty.call(status, "pending_return_count")
      || Object.prototype.hasOwnProperty.call(statusReturnCounts, "pending_operator_review")
      || text(status.return_truth_source)
      || text(status.current_return_truth_source)
      || text(status.lightweight_return_truth_source),
  );
  const statusPendingReturnCount = Number(
    status.pending_return_count
      ?? statusReturnCounts.pending_operator_review
      ?? statusPendingReturns.length
      ?? 0,
  );
  const statusSaysFreshZeroPending = Boolean(
    statusHasReturnTruth
      && statusPendingReturnCount === 0
      && statusPendingReturns.length === 0
      && (
        status.counts_current === true
        || text(status.return_truth_source).includes("file")
        || text(status.current_return_truth_source).includes("file")
        || text(status.lightweight_return_truth_source).includes("file")
      ),
  );
  const pendingReturns = statusPendingReturns.length
    ? statusPendingReturns
    : statusSaysFreshZeroPending
      ? []
      : summaryPendingReturnItems;
  const supportGates = buildConveyorSupportRequestItems(supportPayload);
  const returnCounts = {
    ...record(summary.return_counts_by_review_state),
    ...record(status.return_counts_by_review_state),
  };
  const summaryPendingReturns = Number(
    statusSaysFreshZeroPending
      ? 0
      : summary.pending_return_count
        || record(summary.return_counts_by_review_state).pending_operator_review
        || summaryPendingReturnItems.length
        || 0,
  );
  const summaryPendingSupport = Number(summary.pending_support_request_count || 0);
  const badgeCount = Math.max(pendingReturns.length, summaryPendingReturns) + Math.max(supportGates.length, summaryPendingSupport);
  return {
    badgeCount,
    pendingReturns,
    supportGates,
    selectedReturn: pendingReturns[0] || {},
    history: {
      accepted: Number(returnCounts.accepted || 0),
      requeued: Number(returnCounts.requeued || 0),
      rejected: Number(returnCounts.rejected || 0),
      split: Number(returnCounts.split || returnCounts.split_requested || 0),
    },
    summary: {
      pendingReturnCount: Math.max(pendingReturns.length, summaryPendingReturns),
      pendingSupportCount: Math.max(supportGates.length, summaryPendingSupport),
      activeChildCount: Number(summary.active_child_count || 0),
      latestReturnAt: text(summary.latest_return_at),
      generatedAt: text(summary.generated_at),
    },
    emptyStateLabel: pendingReturns.length
      ? ""
      : badgeCount
        ? `${summaryPendingReturns} returned packet${summaryPendingReturns === 1 ? "" : "s"} are queued; packet details are still loading from conveyor state.`
        : "No returned directive work is waiting for operator review.",
  };
}

export function mergeShellStateAfterRefresh(previous = {}, next = {}, now = new Date().toISOString()) {
  const hasNextField = (field) => Object.prototype.hasOwnProperty.call(next, field);
  const refreshMeta = {
    ...record(previous.refreshMeta),
    ...record(next.refreshMeta),
    lastRefreshedAt: now,
  };
  const merged = {
    ...previous,
    ...next,
    refreshMeta,
  };
  if (hasNextField("conveyorStatus")) {
    if (next.conveyorStatus) {
      if (next.conveyorStatus.deep_status_cached) {
        refreshMeta.conveyorLastRefreshedAt = text(refreshMeta.conveyorLastRefreshedAt, next.conveyorStatus.generated_at);
        refreshMeta.conveyorStatusStale = true;
      } else {
        refreshMeta.conveyorLastRefreshedAt = now;
        refreshMeta.conveyorStatusStale = false;
      }
    } else {
      if (previous.conveyorStatus) merged.conveyorStatus = previous.conveyorStatus;
      refreshMeta.conveyorStatusStale = true;
    }
  }
  if (hasNextField("conveyorSummary")) {
    if (next.conveyorSummary) {
      refreshMeta.conveyorSummaryLastRefreshedAt = now;
      refreshMeta.conveyorSummaryStale = false;
      refreshMeta.conveyorSummaryWarning = "";
    } else {
      if (previous.conveyorSummary) merged.conveyorSummary = previous.conveyorSummary;
      refreshMeta.conveyorSummaryStale = true;
      refreshMeta.conveyorSummaryWarning = `Conveyor summary refresh failed; showing cached data from ${text(
        refreshMeta.conveyorSummaryLastRefreshedAt,
        "an earlier refresh",
      )}.`;
    }
  }
  if (hasNextField("conveyorOvernightReadiness")) {
    if (next.conveyorOvernightReadiness) {
      if (next.conveyorOvernightReadiness.deep_status_cached) {
        refreshMeta.conveyorOvernightReadinessLastRefreshedAt = text(
          refreshMeta.conveyorOvernightReadinessLastRefreshedAt,
          next.conveyorOvernightReadiness.generated_at,
        );
        refreshMeta.conveyorOvernightReadinessStale = true;
      } else {
        refreshMeta.conveyorOvernightReadinessLastRefreshedAt = now;
        refreshMeta.conveyorOvernightReadinessStale = false;
      }
    } else {
      if (previous.conveyorOvernightReadiness) merged.conveyorOvernightReadiness = previous.conveyorOvernightReadiness;
      refreshMeta.conveyorOvernightReadinessStale = true;
    }
  }
  if (hasNextField("conveyorSupportRequests")) {
    if (next.conveyorSupportRequests) {
      if (next.conveyorSupportRequests.deep_status_cached) {
        refreshMeta.conveyorSupportRequestsLastRefreshedAt = text(
          refreshMeta.conveyorSupportRequestsLastRefreshedAt,
          next.conveyorSupportRequests.generated_at,
        );
        refreshMeta.conveyorSupportRequestsStale = true;
      } else {
        refreshMeta.conveyorSupportRequestsLastRefreshedAt = now;
        refreshMeta.conveyorSupportRequestsStale = false;
      }
    } else {
      if (previous.conveyorSupportRequests) merged.conveyorSupportRequests = previous.conveyorSupportRequests;
      refreshMeta.conveyorSupportRequestsStale = true;
    }
  }
  if (
    refreshMeta.conveyorStatusStale ||
    refreshMeta.conveyorSupportRequestsStale ||
    refreshMeta.conveyorOvernightReadinessStale
  ) {
    const currentSummary =
      merged.conveyorSummary &&
      !refreshMeta.conveyorSummaryStale &&
      merged.conveyorSummary.counts_current !== false &&
      !merged.conveyorSummary.summary_unavailable;
    const lastDeepRefresh = text(
      refreshMeta.conveyorLastRefreshedAt,
      refreshMeta.conveyorSupportRequestsLastRefreshedAt,
      refreshMeta.conveyorOvernightReadinessLastRefreshedAt,
      "an earlier refresh",
    );
    refreshMeta.conveyorRefreshWarning = currentSummary
      ? `Deep conveyor details are cached from ${lastDeepRefresh}; current counts are live from the fast summary.`
      : `Conveyor refresh failed; showing last successful data from ${lastDeepRefresh}.`;
  } else {
    refreshMeta.conveyorRefreshWarning = "";
  }
  return merged;
}

export function mergeShellStateAfterAction(previous = {}, actionResult = {}, now = new Date().toISOString()) {
  const result = record(actionResult);
  const refreshMeta = {
    ...record(previous.refreshMeta),
    lastRefreshedAt: now,
  };
  const merged = {
    ...previous,
    refreshMeta,
  };
  if (result.status) {
    merged.conveyorStatus = result.status;
    refreshMeta.conveyorLastRefreshedAt = now;
    refreshMeta.conveyorStatusStale = false;
  }
  if (result.overnight_readiness) {
    merged.conveyorOvernightReadiness = result.overnight_readiness;
    refreshMeta.conveyorOvernightReadinessLastRefreshedAt = now;
    refreshMeta.conveyorOvernightReadinessStale = false;
  }
  if (result.support_requests) {
    merged.conveyorSupportRequests = result.support_requests;
    refreshMeta.conveyorSupportRequestsLastRefreshedAt = now;
    refreshMeta.conveyorSupportRequestsStale = false;
  } else if (result.status?.support_requests) {
    merged.conveyorSupportRequests = {
      schema_name: "ConveyorSupportRequestList",
      generated_at: text(result.status.generated_at, now),
      support_requests: array(result.status.support_requests),
      support_request_counts_by_state: record(result.status.support_request_counts_by_state),
    };
    refreshMeta.conveyorSupportRequestsLastRefreshedAt = now;
    refreshMeta.conveyorSupportRequestsStale = false;
  }
  if (!refreshMeta.conveyorStatusStale && !refreshMeta.conveyorSupportRequestsStale) {
    refreshMeta.conveyorRefreshWarning = "";
  }
  return merged;
}

export function buildConveyorWorkbench({
  conveyorStatus,
  conveyorSummary,
  conveyorOvernightReadiness,
  autonomyStatus,
  longRun,
  currentDirective,
} = {}) {
  const status = record(conveyorStatus);
  const summaryPayload = record(conveyorSummary);
  const statusReturnedPackets = array(status.returned_packets);
  const summaryReturnedPackets = array(summaryPayload.returned_packets);
  const packetStatus = statusReturnedPackets.length
    ? status
    : summaryReturnedPackets.length
      ? {
          ...status,
          returned_packets: summaryReturnedPackets,
          return_counts_by_review_state: {
            ...record(status.return_counts_by_review_state),
            ...record(summaryPayload.return_counts_by_review_state),
          },
        }
      : status;
  const overnightReadiness = record(conveyorOvernightReadiness);
  const autonomy = record(autonomyStatus);
  const longRunPayload = record(record(longRun).long_run || longRun);
  const directive = record(currentDirective);
  const growth = record(autonomy.autonomous_growth);
  const supportRequests = array(status.support_requests);
  const continuousCampaignStatus = record(status.continuous_campaign);
  const scheduler = record(status.scheduler);
  const campaignManifestByDirective = buildCampaignManifestIndex(
    Object.keys(status).length ? status : summaryPayload,
  );
  const continuousCampaignPolicy = record(
    continuousCampaignStatus.policy || scheduler.continuous_campaign_policy,
  );
  const continuousCampaignEnabled =
    Boolean(continuousCampaignStatus.enabled) || Boolean(scheduler.continuous_campaign_mode);
  const overnightReadinessUnavailable = Boolean(overnightReadiness.deep_status_unavailable);
  const overnightReady = !overnightReadinessUnavailable && Boolean(overnightReadiness.ready);
  const overnightReadyLabel = overnightReadinessUnavailable
    ? "Readiness refreshing"
    : overnightReady
      ? "Overnight ready"
      : "Not overnight ready";
  const overnightBlockers = array(overnightReadiness.blockers).map((item) => text(item)).filter(Boolean);
  const overnightWarnings = array(overnightReadiness.warnings).map((item) => text(item)).filter(Boolean);
  const overnightRecommendedActions = array(overnightReadiness.recommended_actions)
    .map((item) => text(item))
    .filter(Boolean);
  const overnightDirectiveStatuses = array(overnightReadiness.directive_statuses).map((item) => record(item));
  const packets = buildConveyorReturnReviewItems(packetStatus).map((item) => {
    const rawPacket = array(packetStatus.returned_packets).find(
      (packet) => text(packet?.return_packet_id) === item.returnPacketId,
    );
    const campaignManifest = record(campaignManifestByDirective.get(item.directiveId));
    const canonicalArtifactRows = buildCanonicalArtifactRows(campaignManifest);
    const executionGatedArtifacts = canonicalArtifactRows
      .filter((artifact) => artifact.executionGated)
      .map((artifact) => artifact.artifactName);
    const buildGradeReady = packetBuildGradeReady(rawPacket);
    const kernelEvaluation = record(rawPacket?.kernel_evaluation);
    const continuousCampaign = record(rawPacket?.continuous_campaign);
    const continuousLatestState = text(continuousCampaign.latest_state);
    const campaignState = record(kernelEvaluation.campaign_state);
    const prototypeClusterClosure = record(
      kernelEvaluation.prototype_cluster_closure || campaignState.prototype_cluster_closure,
    );
    const handoffAssessment = record(campaignState.build_grade_handoff_assessment);
    const campaignReadinessLevel = text(campaignState.readiness_level);
    const campaignBuildReady = campaignReadinessLevel === "build_ready_review";
    const missingBuildReadinessGates = array(campaignState.missing_build_readiness_gates)
      .map((item) => text(item))
      .filter(Boolean);
    const campaignDecision = text(kernelEvaluation.decision);
    const autoReengagementBlockers = array(kernelEvaluation.auto_reengagement_blockers)
      .map((item) => text(item))
      .filter(Boolean);
    const prototypeReadyGateFailures = array(kernelEvaluation.prototype_ready_gate_failures)
      .map((item) => text(item))
      .filter(Boolean);
    const requestedOperatorClarifications = array(rawPacket?.requested_operator_clarifications)
      .map((clarification) => record(clarification))
      .filter((clarification) => text(clarification.clarification_id, clarification.question));
    const isSmokeTest = /conveyor concurrency smoke/i.test(text(item.outcomeSummary, item.title));
    const supportPackRefs = supportPackRefsForDirective(supportRequests, item.directiveId);
    const relatedPendingSupportRequests = supportRequests.filter((request) => {
      const requestRecord = record(request);
      if (text(requestRecord.support_state) !== "pending_operator_review") return false;
      if (text(requestRecord.directive_id) !== item.directiveId) return false;
      const requestReturnId = text(requestRecord.return_packet_id);
      return (
        requestReturnId === item.returnPacketId ||
        requestReturnId === `resident-progress-${item.childRunId}` ||
        text(requestRecord.child_run_id) === item.childRunId
      );
    });
    const workspaceArtifactAttached = Boolean(rawPacket?.workspace_artifact_attached);
    const infrastructureFault =
      Boolean(rawPacket?.infrastructure_fault) ||
      array(rawPacket?.risks).map((risk) => text(risk)).includes("docker_mount_fault");
    const stalledWithArtifacts =
      workspaceArtifactAttached &&
      array(item.artifacts).length > 0 &&
      array(rawPacket?.risks).map((risk) => text(risk)).includes("resident_worker_stalled");
    const supportNeeded =
      relatedPendingSupportRequests.length > 0 || Number(kernelEvaluation.support_unresolved_count || 0) > 0;
    const supportRequiredBeforeContinue = Boolean(rawPacket?.support_required_before_continue) || supportNeeded;
    const packetFailedGates = array(rawPacket?.failed_gates).map((item) => text(item)).filter(Boolean);
    const blockedRequirements = array(rawPacket?.blocked_requirements).map((item) => text(item)).filter(Boolean);
    const targetArtifact = text(rawPacket?.target_artifact);
    const artifactSource = text(rawPacket?.artifact_source);
    const implementationHandoff = buildImplementationHandoffSummary(rawPacket?.implementation_handoff);
    const compiledDocumentation = record(
      rawPacket?.compiled_documentation ||
        canonicalArtifactRows.find((artifact) => artifact.artifactName === "technical_documentation.md")
          ?.compiledDocumentation,
    );
    const directionItems = [
      ...requestedOperatorClarifications.map((clarification) => ({
        kind: "clarification",
        clarificationId: text(clarification.clarification_id),
        question: text(clarification.question, "Novali needs operator direction before continuing."),
        blockedGate: text(clarification.blocked_gate, clarification.blocked_requirement),
        targetArtifact: text(clarification.target_artifact),
        clarificationOptions: array(clarification.clarification_options)
          .map((option) => record(option))
          .map((option) => ({
            optionId: text(option.option_id),
            label: text(option.label),
            description: text(option.description),
          }))
          .filter((option) => option.optionId || option.label || option.description),
      })),
      ...relatedPendingSupportRequests.map((request) => {
        const requestRecord = record(request);
        const matchingPack = supportPackRefs.find((packRef) => text(packRef).includes(text(requestRecord.capability)));
        return {
          kind: "support_request",
          supportRequestId: text(requestRecord.support_request_id),
          capability: text(requestRecord.capability),
          reason: text(requestRecord.reason, "Kernel-mediated support is pending."),
          targetArtifact: text(requestRecord.target_artifact),
          supportPackAvailable: Boolean(matchingPack),
        };
      }),
    ];
    const directionNeeded = directionItems.length > 0;
    return {
      ...item,
      buildGradeReady,
      campaignReadinessLevel,
      campaignDecision,
      prototypeReadyStopCondition: Boolean(kernelEvaluation.prototype_ready_stop_condition),
      autoReengagementEligible: Boolean(kernelEvaluation.auto_reengagement_eligible),
      autoReengagementBlockers,
      prototypeReadyGateFailures,
      latestProgressGateClosureConsumed: Boolean(kernelEvaluation.latest_progress_gate_closure_consumed),
      supersededStaleClarifications: array(kernelEvaluation.superseded_stale_clarifications)
        .map((item) => record(item))
        .filter((item) => text(item.clarification_id, item.question)),
      nextUnresolvedGateArtifact: text(kernelEvaluation.next_unresolved_gate_artifact),
      prototypeClusterClosure: {
        clusterFamily: text(prototypeClusterClosure.cluster_family),
        clusterClosed: Boolean(prototypeClusterClosure.cluster_closed),
        missingClusterGates: array(prototypeClusterClosure.missing_cluster_gates)
          .map((item) => text(item))
          .filter(Boolean),
        nextUnresolvedArtifact: text(prototypeClusterClosure.next_unresolved_artifact),
        artifactGateMap: record(prototypeClusterClosure.artifact_gate_map),
      },
      missingBuildReadinessGates,
      missingBuildReadinessGateLabel: formatListLabel(missingBuildReadinessGates) || "No missing gates recorded",
      readinessLabel: campaignReadinessLevel
        ? formatKind(campaignReadinessLevel)
        : buildGradeReady
          ? "Build-grade ready"
          : "Needs depth",
      isSmokeTest,
      categoryLabel: isSmokeTest
        ? "Smoke test"
        : infrastructureFault
          ? "Infrastructure fault"
        : stalledWithArtifacts
          ? "Stalled with artifacts"
        : campaignReadinessLevel && !campaignBuildReady
          ? "Campaign depth review"
          : buildGradeReady
            ? "Deliverable return"
            : "Depth review",
      campaignActionLabel:
        campaignDecision === "continue_campaign" || (campaignReadinessLevel && !campaignBuildReady)
          ? "Continue campaign"
          : "Request deeper pass",
      artifactOpenLabel: `Open ${array(item.artifacts).length} ${array(item.artifacts).length === 1 ? "deliverable" : "deliverables"}`,
      artifactSource,
      artifactSourceLabel: artifactSourceLabel(artifactSource),
      implementationHandoff,
      compiledDocumentation: Object.keys(compiledDocumentation).length
        ? {
            artifactName: text(compiledDocumentation.artifact_name, compiledDocumentation.artifactName),
            sourceArtifact: text(compiledDocumentation.source_artifact, compiledDocumentation.sourceArtifact),
            originalSha256: text(compiledDocumentation.original_sha256, compiledDocumentation.originalSha256),
            compiledSha256: text(compiledDocumentation.compiled_sha256, compiledDocumentation.compiledSha256),
            compiledAt: text(compiledDocumentation.compiled_at, compiledDocumentation.compiledAt),
            authorityBoundary: text(compiledDocumentation.authority_boundary, compiledDocumentation.authorityBoundary),
          }
        : null,
      handoffReadiness: {
        ready: Boolean(handoffAssessment.handoff_ready),
        satisfiedGates: array(handoffAssessment.satisfied_handoff_gates).map((item) => text(item)).filter(Boolean),
        missingGates: array(handoffAssessment.missing_handoff_gates).map((item) => text(item)).filter(Boolean),
      },
      supportPackRefs,
      campaignManifest,
      campaignWorkspaceState: text(campaignManifest.readiness_state, campaignManifest.status, "campaign ledger not initialized"),
      qualityDepthScore: Number(campaignManifest.quality_depth_score || campaignManifest.build_package_depth_score || 0),
      artifactPresenceScore: Number(campaignManifest.artifact_presence_score || 0),
      qualityDepthLabel: `Quality depth ${Math.round(Number(campaignManifest.quality_depth_score || campaignManifest.build_package_depth_score || 0) * 100)}%`,
      artifactPresenceLabel: `Artifact presence ${Math.round(Number(campaignManifest.artifact_presence_score || 0) * 100)}%`,
      qualityFailedArtifacts: array(campaignManifest.quality_failed_artifacts).map((artifact) => text(artifact)).filter(Boolean),
      failedQualityGates: array(campaignManifest.failed_quality_gates).map((gate) => text(gate)).filter(Boolean),
      latestQualityRejectionReason: text(campaignManifest.latest_quality_rejection_reason),
      latestQualityRejectedArtifact: text(campaignManifest.latest_quality_rejected_artifact),
      canonicalArtifactRows,
      canonicalArtifactCount: canonicalArtifactRows.length,
      canonicalVersionLabel: canonicalArtifactRows.length
        ? `${canonicalArtifactRows.length} canonical ${canonicalArtifactRows.length === 1 ? "artifact" : "artifacts"}`
        : "No canonical artifacts yet",
      executionGatedArtifacts,
      executionGatedLabel: executionGatedArtifacts.length
        ? `${executionGatedArtifacts.length} execution-gated ${executionGatedArtifacts.length === 1 ? "artifact" : "artifacts"}`
        : "No execution-gated artifacts recorded",
      continuousCampaign,
      continuousCampaignEnabled: Boolean(continuousCampaign.enabled),
      continuousCampaignLatestState: continuousLatestState,
      continuousCampaignLatestReason: text(continuousCampaign.latest_reason),
      continuousCampaignLatestAction: text(continuousCampaign.latest_action),
      continuousCampaignLatestTargetArtifact: text(continuousCampaign.latest_target_artifact),
      continuousCampaignDepthRemaining: Number(continuousCampaign.auto_continue_depth_pass_remaining || 0),
      continuousCampaignSupportRemaining: Number(continuousCampaign.auto_support_approval_remaining || 0),
      supportNeeded,
      supportRequiredBeforeContinue,
      supportRequiredTitle: supportRequiredBeforeContinue ? "Support required before continuing" : "",
      relatedPendingSupportRequests,
      directionNeeded,
      directionItems,
      operatorDirectionPrompt: directionNeeded
        ? "Typed direction will answer the visible blocker(s) and send this directive back to the conveyor."
        : infrastructureFault
          ? "Recover Docker bind mounts, then continue from the latest campaign baseline."
        : "Typed direction will guide the next conveyor pass.",
      workspaceArtifactAttached,
      infrastructureFault,
      supportPackLabel: supportPackRefs.length
        ? countLabel(supportPackRefs.length, "support pack")
        : supportNeeded
          ? "Support request pending"
          : "No support packs used",
      risks: array(rawPacket?.risks).map((risk) => text(risk)).filter(Boolean),
      kernelFeedback: text(kernelEvaluation.feedback),
      requestedOperatorClarifications,
      clarificationLabel: requestedOperatorClarifications.length
        ? countLabel(requestedOperatorClarifications.length, "clarification")
        : "No clarification requested",
      requestedFollowUp: text(rawPacket?.requested_follow_up, item.requestedFollowUp),
      generatedAt: text(rawPacket?.generated_at),
      networkPolicy: text(rawPacket?.network_policy, rawPacket?.child_network_policy, "deny_all"),
      gateSummary: {
        readinessLevel: campaignReadinessLevel || (buildGradeReady ? "build_grade_contract_present" : "needs_depth"),
        decision: campaignDecision || "operator_review_required",
        failedGates: packetFailedGates.length ? packetFailedGates : missingBuildReadinessGates,
        nextUnresolvedGateArtifact: text(kernelEvaluation.next_unresolved_gate_artifact),
        latestProgressGateClosureConsumed: Boolean(kernelEvaluation.latest_progress_gate_closure_consumed),
        blockedRequirements,
        claimCount: Number(campaignState.claim_count || rawPacket?.claim_count || 0),
        evidenceCount: array(rawPacket?.verification_evidence).length,
        noveltyCount: Number(campaignState.novelty_count || rawPacket?.novelty_count || 0),
        supportPackRefs,
        risks: array(rawPacket?.risks).map((risk) => text(risk)).filter(Boolean),
        networkPolicy: text(rawPacket?.network_policy, rawPacket?.child_network_policy, "deny_all"),
        feedback: text(kernelEvaluation.feedback),
      },
      targetArtifact,
      statusChips: [
        infrastructureFault ? "docker mount fault" : "",
        continuousLatestState === "auto_requeued" ? "auto-continuing" : "",
        continuousLatestState === "cap_exhausted" ? "cap exhausted" : "",
        continuousLatestState === "no_progress_escalated" ? "no progress escalated" : "",
        stalledWithArtifacts
          ? "stalled with artifacts"
          : campaignReadinessLevel === "build_ready_review" || buildGradeReady
            ? "review ready"
            : "needs depth",
        supportNeeded ? "support needed" : "",
        supportPackRefs.length ? "support used" : "",
        Boolean(kernelEvaluation.latest_progress_gate_closure_consumed) ? "progress closure consumed" : "",
        array(kernelEvaluation.superseded_stale_clarifications).length ? "stale clarification superseded" : "",
        requestedOperatorClarifications.length ? "blocked" : "",
        text(rawPacket?.review_state) === "accepted" ? "accepted" : "",
      ].filter(Boolean),
      primaryAction: {
        id: "requeue",
        label: infrastructureFault
          ? "Recover + continue campaign"
          : supportRequiredBeforeContinue
          ? "Approve support + continue deeper"
          : directionNeeded
            ? "Answer + deeper pass"
            : "Request deeper pass",
        confirmationLabel: infrastructureFault
          ? "recover Docker mount state and continue the campaign"
          : supportRequiredBeforeContinue
          ? "approve support and continue deeper"
          : directionNeeded
            ? "answer blockers and request a deeper pass"
            : "request a deeper pass",
        approveSupportBeforeRequeue: supportRequiredBeforeContinue,
      },
      secondaryActions: [
        { id: "clarify", label: "Clarify + requeue" },
        { id: "accept", label: "Accept final", requiresConfirmation: true },
        { id: "split", label: "Split" },
        { id: "reject", label: "Reject" },
      ],
    };
  });
  const groupsByDirective = new Map();
  for (const packet of packets) {
    const key = text(packet.directiveId, packet.title, "unknown-directive");
    if (!groupsByDirective.has(key)) {
      groupsByDirective.set(key, {
        directiveId: packet.directiveId,
        title: text(packet.title, packet.directiveId, "Returned conveyor work"),
        packets: [],
      });
    }
    groupsByDirective.get(key).packets.push(packet);
  }
  const activeWorkerDetails = array(status.active_children).map((child) => {
    const progress = record(child.latest_progress);
    const continuousCampaign = record(child.continuous_campaign);
    const artifactDeltas = array(progress.artifact_deltas);
    const latestDelta = record(artifactDeltas[artifactDeltas.length - 1]);
    const directiveId = text(child.directive_id);
    const campaignManifest = record(campaignManifestByDirective.get(directiveId));
    const canonicalArtifactRows = buildCanonicalArtifactRows(campaignManifest);
    const latestWorkOrder = record(child.latest_work_order);
    const prototypeDeltaTarget = record(latestWorkOrder.prototype_delta_target);
    const roleResearchAdapterRef = record(latestWorkOrder.role_research_adapter_ref);
    const draftDeltaQuality = record(child.draft_delta_quality || campaignManifest.draft_delta_quality);
    const intentContinuity = record(child.intent_continuity);
    const latestWakeRequest = record(child.latest_wake_request);
    const latestWakeAck = record(child.latest_wake_ack);
    const activePrototypeClusterClosure = record(campaignManifest.prototype_cluster_closure);
    const targetCorrectGateClosure = record(child.target_correct_gate_closure);
    return {
      childRunId: text(child.child_run_id),
      directiveId,
      state: text(child.state, "running"),
      spawnState: text(child.spawn_state),
      executionMode: text(child.child_execution_mode, "oneshot_return"),
      progressState: text(child.progress_state, progress.progress_state, "starting"),
      residentWorkerState: text(child.resident_worker_state),
      progressAt: text(child.latest_progress_at, progress.generated_at),
      currentStep: text(progress.current_step),
      message: text(progress.message),
      currentFocus: text(progress.current_focus, "Working inside isolated directive workspace."),
      nextStepContext: text(progress.next_step_context),
      targetArtifact: text(child.latest_target_artifact, progress.target_artifact),
      cycleOutcome: text(progress.cycle_outcome),
      meaningfulDelta: Boolean(progress.meaningful_delta),
      latestArtifactDelta: {
        artifactName: text(latestDelta.artifact_name),
        deltaKind: text(latestDelta.delta_kind),
        beforeHash: text(latestDelta.before_hash),
        afterHash: text(latestDelta.after_hash),
      },
      artifactDeltaCount: Number(child.latest_artifact_delta_count || artifactDeltas.length || 0),
      artifactDeltaNames: array(progress.artifact_delta_names).map((item) => text(item)).filter(Boolean),
      nextWakeSeconds: Number(progress.next_wake_seconds || 0),
      workOrderTargetReason: text(progress.work_order_target_reason),
      consecutiveNoDeltaCycles: Number(child.consecutive_no_delta_cycles || 0),
      supportInjectionCount: Number(child.support_injection_count || 0),
      latestWorkOrderId: text(child.latest_work_order_id, progress.work_order_id),
      latestWorkOrderTargetArtifact: text(child.latest_work_order_target_artifact),
      latestWorkOrder: {
        targetSelectionReason: text(latestWorkOrder.target_selection_reason),
        cleanArtifactsSkipped: array(latestWorkOrder.clean_artifacts_skipped).map((item) => text(item)).filter(Boolean),
        artifactLevelFailedGateTarget: Boolean(latestWorkOrder.artifact_level_failed_gate_target),
        sourceFailedQualityGates: array(latestWorkOrder.source_failed_quality_gates)
          .map((item) => text(item))
          .filter(Boolean),
        prototypeClusterRequirements: record(latestWorkOrder.prototype_cluster_requirements),
        schemaSkeletonId: text(latestWorkOrder.schema_skeleton_id),
        plateauRecoveryReason: text(latestWorkOrder.plateau_recovery_reason),
        requiredGateClosures: array(latestWorkOrder.required_gate_closures).map((item) => text(item)).filter(Boolean),
        fieldLevelOutputContract: record(latestWorkOrder.field_level_output_contract),
        prototypeDeltaTarget: {
          repoPath: text(prototypeDeltaTarget.repo_path),
          prototypeFamily: text(prototypeDeltaTarget.prototype_family),
          executionBoundary: text(prototypeDeltaTarget.execution_boundary),
        },
        roleResearchAdapterRef: {
          roleSpecificResearchAdapterId: text(roleResearchAdapterRef.role_specific_research_adapter_id),
          status: text(roleResearchAdapterRef.status),
          authorityBoundary: text(roleResearchAdapterRef.authority_boundary),
        },
      },
      intentContinuity: {
        sourceReturnPacketId: text(intentContinuity.source_return_packet_id),
        intendedTargetArtifact: text(intentContinuity.intended_target_artifact),
        spawnedTargetArtifact: text(intentContinuity.spawned_target_artifact),
        inboxWorkOrderPresent: Boolean(intentContinuity.inbox_work_order_present),
        roleAdapterRefPresent: Boolean(intentContinuity.role_adapter_ref_present),
        requirementContractPresent: Boolean(intentContinuity.requirement_contract_present),
        recoveredFromCampaignMetadata: Boolean(intentContinuity.recovered_from_campaign_metadata),
        preserved: Boolean(intentContinuity.preserved),
        failedGates: array(intentContinuity.failed_gates).map((item) => text(item)).filter(Boolean),
      },
      draftDeltaQuality: {
        targetArtifact: text(draftDeltaQuality.target_artifact),
        draftChangedFromCanonical: Boolean(draftDeltaQuality.draft_changed_from_canonical),
        draftChangedSinceLastReview: Boolean(draftDeltaQuality.draft_changed_since_last_review),
        draftPlateau: Boolean(draftDeltaQuality.draft_plateau),
        draftPlateauCount: Number(draftDeltaQuality.draft_plateau_count || 0),
        gateClosureSinceLastCycle: Boolean(draftDeltaQuality.gate_closure_since_last_cycle),
        closedFailedGates: array(draftDeltaQuality.closed_failed_gates).map((item) => text(item)).filter(Boolean),
        unchangedFailedGates: array(draftDeltaQuality.unchanged_failed_gates).map((item) => text(item)).filter(Boolean),
        plateauRecoveryAttemptCount: Number(draftDeltaQuality.plateau_recovery_attempt_count || 0),
        qualityDepthScore: Number(draftDeltaQuality.quality_depth_score || 0),
        failedGates: array(draftDeltaQuality.failed_gates).map((item) => text(item)).filter(Boolean),
        operatorFollowupDeltaSatisfied: Boolean(draftDeltaQuality.operator_followup_delta_satisfied),
      },
      fieldLevelContractApplied: Boolean(child.field_level_contract_applied || progress.field_level_contract_applied),
      latestGateClosureSummary: record(child.latest_gate_closure_summary),
      targetCorrectGateClosure: {
        targetArtifact: text(targetCorrectGateClosure.target_artifact),
        targetCorrect: Boolean(targetCorrectGateClosure.target_correct),
        closedFailedGates: array(targetCorrectGateClosure.closed_failed_gates).map((item) => text(item)).filter(Boolean),
        nextActionAfterClosure: text(targetCorrectGateClosure.next_action_after_closure),
      },
      prototypeClusterClosure: {
        clusterFamily: text(activePrototypeClusterClosure.cluster_family),
        clusterClosed: Boolean(activePrototypeClusterClosure.cluster_closed),
        missingClusterGates: array(activePrototypeClusterClosure.missing_cluster_gates)
          .map((item) => text(item))
          .filter(Boolean),
        nextUnresolvedArtifact: text(activePrototypeClusterClosure.next_unresolved_artifact),
        artifactGateMap: record(activePrototypeClusterClosure.artifact_gate_map),
      },
      draftPlateauCount: Number(child.draft_plateau_count || draftDeltaQuality.draft_plateau_count || 0),
      latestDraftDeltaGateFailures: array(
        child.latest_draft_delta_gate_failures || draftDeltaQuality.failed_gates,
      ).map((item) => text(item)).filter(Boolean),
      latestQualityTarget: text(child.latest_quality_target, campaignManifest.latest_quality_target),
      lastQualityPromotionAt: text(child.last_quality_promotion_at, campaignManifest.last_quality_promotion_at),
      qualityNoProgressCount: Number(child.quality_no_progress_count || campaignManifest.quality_no_progress_count || 0),
      latestQualityRetargetReason: text(child.latest_quality_retarget_reason, campaignManifest.latest_quality_retarget_reason),
      weakestFailedArtifact: text(child.weakest_failed_artifact, campaignManifest.weakest_failed_artifact),
      productiveQuiescenceEligible: Boolean(child.productive_quiescence_eligible),
      returnRequestedAfterCleanDelta: Boolean(child.return_requested_after_clean_delta),
      followupCompletionReason: text(child.followup_completion_reason),
      residentWorkOrderDuplicateSuppressedCount: Number(
        child.resident_work_order_duplicate_suppressed_count || 0,
      ),
      inboxCompactionSummary: record(child.inbox_compaction_summary),
      residentFirstCycleSleepSeconds: Number(child.resident_first_cycle_sleep_seconds || 0),
      wakePending: Boolean(child.wake_pending),
      wakeStale: Boolean(child.wake_stale),
      latestWakeRequest: {
        wakeRequestedAt: text(latestWakeRequest.wake_requested_at),
        wakeReason: text(latestWakeRequest.wake_reason),
        wakeWorkOrderId: text(latestWakeRequest.wake_work_order_id),
        wakePriority: text(latestWakeRequest.wake_priority),
        wakeSequence: Number(latestWakeRequest.wake_sequence || 0),
        wakeAckTimeoutSeconds: Number(latestWakeRequest.wake_ack_timeout_seconds || 0),
      },
      latestWakeAck: {
        wakeAcknowledgedAt: text(latestWakeAck.wake_acknowledged_at),
        wakeReason: text(latestWakeAck.wake_reason),
        wakeWorkOrderId: text(latestWakeAck.wake_work_order_id),
        wakeSequence: Number(latestWakeAck.wake_sequence || 0),
        wakeLatencySeconds: Number(latestWakeAck.wake_latency_seconds || 0),
      },
      wakeLatencySeconds: Number(child.wake_latency_seconds || latestWakeAck.wake_latency_seconds || 0),
      wakeFallbackRestartCount: Number(child.wake_fallback_restart_count || 0),
      omittedSupportPackRefCount: Number(child.omitted_support_pack_ref_count || 0),
      supportPackRankSummary: array(child.support_pack_rank_summary).map((item) => record(item)),
      networkPolicy: text(child.network_policy, progress.network_policy, "deny_all"),
      campaignManifest,
      canonicalArtifactRows,
      canonicalArtifactCount: canonicalArtifactRows.length,
      campaignWorkspaceState: text(campaignManifest.readiness_state, campaignManifest.status),
      continuousCampaign,
      continuousCampaignLatestState: text(continuousCampaign.latest_state),
      continuousCampaignDepthRemaining: Number(continuousCampaign.auto_continue_depth_pass_remaining || 0),
      continuousCampaignSupportRemaining: Number(continuousCampaign.auto_support_approval_remaining || 0),
    };
  });
  const activeChildren = activeWorkerDetails.length;
  const queuedDirectives = array(status.queued_directives).length;
  const pendingReturns = Math.max(
    Number(record(status.return_counts_by_review_state).pending_operator_review || 0),
    Number(record(summaryPayload.return_counts_by_review_state).pending_operator_review || 0),
    Number(summaryPayload.pending_return_count || 0),
    packets.length,
  );
  const packetDetailsMissing = pendingReturns > packets.length;
  const staleReturnDirectiveCount = Number(status.stale_return_directive_count || 0);
  const dataWarnings = [];
  if (packetDetailsMissing) {
    dataWarnings.push(
      `${pendingReturns} returns exist, but packet details failed to load. Refresh will keep retrying without hiding this count.`,
    );
  }
  if (staleReturnDirectiveCount > 0) {
    dataWarnings.push(
      `${staleReturnDirectiveCount} return packet(s) reference missing directive records and need operator cleanup.`,
    );
  }
  const cleanDocumentationWorkerCount = activeWorkerDetails.filter(
    (worker) =>
      worker.targetArtifact === "technical_documentation.md" &&
      !worker.latestWorkOrder.targetSelectionReason &&
      artifactQualityClean(worker.campaignManifest, "technical_documentation.md"),
  ).length;
  if (cleanDocumentationWorkerCount > 0) {
    dataWarnings.push(
      `${cleanDocumentationWorkerCount} active worker(s) are targeting clean technical_documentation.md without a structured work order.`,
    );
  }
  const draftPlateauWorkerCount = activeWorkerDetails.filter(
    (worker) => worker.draftDeltaQuality.draftPlateau || worker.latestDraftDeltaGateFailures.includes("draft_delta_plateau"),
  ).length;
  if (draftPlateauWorkerCount > 0) {
    dataWarnings.push(
      `${draftPlateauWorkerCount} active worker(s) show draft delta plateau or missing follow-up depth.`,
    );
  }
  const unresolvedSkeletonWorkerCount = activeWorkerDetails.filter(
    (worker) =>
      worker.draftDeltaQuality.draftPlateau &&
      worker.latestWorkOrder.schemaSkeletonId &&
      !worker.fieldLevelContractApplied,
  ).length;
  if (unresolvedSkeletonWorkerCount > 0) {
    dataWarnings.push(
      `${unresolvedSkeletonWorkerCount} active worker(s) have plateau recovery skeletons that have not yet appeared in progress.`,
    );
  }
  const staleWakeWorkerCount = activeWorkerDetails.filter((worker) => worker.wakePending && worker.wakeStale).length;
  if (staleWakeWorkerCount > 0) {
    dataWarnings.push(`${staleWakeWorkerCount} active worker(s) have stale unacknowledged wake requests.`);
  }
  const lostIntentWorkerCount = activeWorkerDetails.filter(
    (worker) => worker.intentContinuity.intendedTargetArtifact && !worker.intentContinuity.preserved,
  ).length;
  if (lostIntentWorkerCount > 0) {
    dataWarnings.push(
      `${lostIntentWorkerCount} active worker(s) lost structured requeue intent before spawn.`,
    );
  }
  const productiveQuiescenceWorkerCount = activeWorkerDetails.filter(
    (worker) => worker.productiveQuiescenceEligible || worker.returnRequestedAfterCleanDelta,
  ).length;
  if (productiveQuiescenceWorkerCount > 0) {
    dataWarnings.push(
      `${productiveQuiescenceWorkerCount} active worker(s) satisfied follow-up depth and are packaging final returns.`,
    );
  }
  const compactedInboxWorkerCount = activeWorkerDetails.filter(
    (worker) =>
      Boolean(worker.inboxCompactionSummary.compacted) ||
      Number(worker.inboxCompactionSummary.omitted_work_order_count || 0) > 0 ||
      worker.residentWorkOrderDuplicateSuppressedCount > 0,
  ).length;
  if (compactedInboxWorkerCount > 0) {
    dataWarnings.push(
      `${compactedInboxWorkerCount} active worker(s) have compacted resident inbox churn.`,
    );
  }
  const dataWarning = dataWarnings.join(" ");
  const packetDetailsWarning = packetDetailsMissing
    ? `${pendingReturns} returns exist, but packet details failed to load. Refresh will keep retrying without hiding this count.`
    : "";
  const supportSatisfied = Number(record(status.support_request_counts_by_state).satisfied || 0);
  const coreGrowthActive = Boolean(autonomy.active) || text(autonomy.runtime_state) === "running";
  const coreGrowthState = coreGrowthActive ? "running" : text(autonomy.runtime_state, "paused");
  const executionState = text(longRunPayload.lifecycle_state, longRunPayload.state, "not_started");
  const executionActive = Boolean(longRunPayload.owner_alive || Number(longRunPayload.active_process_id || 0) > 0);
  const seededSession = Boolean(
    text(longRunPayload.session_id) ||
      text(longRunPayload.latest_checkpoint_id) ||
      Number(longRunPayload.checkpoint_count || 0) > 0,
  );
  const primaryAction = coreGrowthActive
    ? { id: "start_autonomy", label: "Core growth running", enabled: false }
    : { id: "start_autonomy", label: "Run growth lane", enabled: true };
  const autonomyAction = coreGrowthActive
    ? { id: "start_autonomy", label: "Core growth running" }
    : { id: "start_autonomy", label: "Enable core growth" };
  return {
    summary: {
      activeChildren,
      pendingReturns,
      queuedDirectives,
      supportSatisfied,
      coreGrowthState,
      continuousCampaignEnabled,
      continuousAutoContinuing: Number(continuousCampaignStatus.auto_continuing_count || 0),
      continuousCapExhausted: Number(continuousCampaignStatus.cap_exhausted_count || 0),
      continuousNoProgressEscalated: Number(continuousCampaignStatus.no_progress_escalated_count || 0),
      continuousDepthPassCap: Number(continuousCampaignPolicy.auto_continue_depth_pass_cap || 0),
      continuousSupportApprovalCap: Number(continuousCampaignPolicy.auto_support_approval_cap || 0),
      overnightReady,
      overnightReadyLabel,
      overnightBlockers,
      overnightWarnings,
      overnightRecommendedActions,
      overnightActiveChildCount: Number(overnightReadiness.active_child_count || activeChildren || 0),
      overnightExpectedActiveChildCount: Number(
        overnightReadiness.expected_active_child_count ?? activeChildren ?? 0,
      ),
      overnightSupportGatedReturnCount: Number(overnightReadiness.support_gated_return_count || 0),
      staleReturnDirectiveCount,
      packetDetailsMissing,
      dataWarning: dataWarning || packetDetailsWarning,
      statusLine: `${activeChildren} child agents running · ${pendingReturns} returns awaiting review · ${queuedDirectives} queued · Core growth ${coreGrowthState}`,
    },
    directiveGroups: [...groupsByDirective.values()],
    missionControl: {
      queue: packets,
      selectedReturnId: text(packets[0]?.returnPacketId),
      selectedPacket: packets[0] || null,
      batchEligibleReturnIds: packets.map((packet) => packet.returnPacketId).filter(Boolean),
      artifactTabs: [
        "Summary",
        "Technical Doc",
        "Subsystems",
        "Interfaces",
        "Dependencies",
        "Validation",
        "Milestones",
        "Claims",
        "Novelty",
        "Raw",
      ],
      defaultArtifactTab: "Summary",
      activeWorkers: activeWorkerDetails,
      continuousCampaign: {
        enabled: continuousCampaignEnabled,
        policy: continuousCampaignPolicy,
        autoContinuingCount: Number(continuousCampaignStatus.auto_continuing_count || 0),
        capExhaustedCount: Number(continuousCampaignStatus.cap_exhausted_count || 0),
        noProgressEscalatedCount: Number(continuousCampaignStatus.no_progress_escalated_count || 0),
        directives: array(continuousCampaignStatus.directives),
      },
      roleAdapterConsumption: {
        capabilityKind: text(record(autonomy.role_adapter_consumption_summary).capability_kind),
        decisionChangedByCapability: Boolean(
          record(autonomy.role_adapter_consumption_summary).decision_changed_by_capability,
        ),
        runtimeCapabilityAdapterBehaviors: array(
          record(autonomy.role_adapter_consumption_summary).runtime_capability_adapter_behaviors,
        ).map((item) => text(item)).filter(Boolean),
      },
      overnightReadiness: {
        ready: overnightReady,
        label: overnightReadyLabel,
        blockers: overnightBlockers,
        warnings: overnightWarnings,
        recommendedActions: overnightRecommendedActions,
        activeChildCount: Number(overnightReadiness.active_child_count || activeChildren || 0),
        expectedActiveChildCount: Number(overnightReadiness.expected_active_child_count ?? activeChildren ?? 0),
        supportGatedReturnCount: Number(overnightReadiness.support_gated_return_count || 0),
        pendingSupportRequestCount: Number(overnightReadiness.pending_support_request_count || 0),
        directiveStatuses: overnightDirectiveStatuses,
      },
      idleLaneGrowth: {
        recommended: Boolean(record(status.idle_lane_growth).recommended),
        reason: text(record(status.idle_lane_growth).reason),
        directiveText: text(record(status.idle_lane_growth).directive_text),
        signature: text(record(status.idle_lane_growth).signature),
      },
      campaigns: [...campaignManifestByDirective.entries()].map(([directiveId, manifest]) => {
        const canonicalArtifactRows = buildCanonicalArtifactRows(manifest);
        const prototypeClusterClosure = record(manifest.prototype_cluster_closure);
        return {
          directiveId,
          readinessState: text(manifest.readiness_state, manifest.status),
          qualityDepthScore: Number(manifest.quality_depth_score || manifest.build_package_depth_score || 0),
          artifactPresenceScore: Number(manifest.artifact_presence_score || 0),
          qualityFailedArtifacts: array(manifest.quality_failed_artifacts).map((artifact) => text(artifact)).filter(Boolean),
          failedQualityGates: array(manifest.failed_quality_gates).map((gate) => text(gate)).filter(Boolean),
          latestQualityRejectionReason: text(manifest.latest_quality_rejection_reason),
          latestQualityTarget: text(manifest.latest_quality_target),
          lastQualityPromotionAt: text(manifest.last_quality_promotion_at),
          qualityNoProgressCount: Number(manifest.quality_no_progress_count || 0),
          latestQualityRetargetReason: text(manifest.latest_quality_retarget_reason),
          weakestFailedArtifact: text(manifest.weakest_failed_artifact),
          nextUnresolvedGateArtifact: text(manifest.next_unresolved_gate_artifact),
          prototypeClusterClosure: {
            clusterFamily: text(prototypeClusterClosure.cluster_family),
            clusterClosed: Boolean(prototypeClusterClosure.cluster_closed),
            missingClusterGates: array(prototypeClusterClosure.missing_cluster_gates)
              .map((gate) => text(gate))
              .filter(Boolean),
            nextUnresolvedArtifact: text(prototypeClusterClosure.next_unresolved_artifact),
            artifactGateMap: record(prototypeClusterClosure.artifact_gate_map),
          },
          draftDeltaQuality: {
            targetArtifact: text(record(manifest.draft_delta_quality).target_artifact),
            draftPlateau: Boolean(record(manifest.draft_delta_quality).draft_plateau),
            draftPlateauCount: Number(record(manifest.draft_delta_quality).draft_plateau_count || 0),
            failedGates: array(record(manifest.draft_delta_quality).failed_gates).map((gate) => text(gate)).filter(Boolean),
            operatorFollowupDeltaSatisfied: Boolean(
              record(manifest.draft_delta_quality).operator_followup_delta_satisfied,
            ),
          },
          activeChildRunId: text(manifest.active_child_run_id),
          pendingReturnCount: Number(manifest.pending_return_count || 0),
          pendingSupportCount: Number(manifest.pending_support_count || 0),
          canonicalArtifactRows,
          canonicalArtifactCount: canonicalArtifactRows.length,
          executionGatedArtifactCount: canonicalArtifactRows.filter((artifact) => artifact.executionGated).length,
        };
      }),
    },
    coreGrowth: {
      state: coreGrowthState,
      growthPolicyState: coreGrowthState,
      executionState,
      executionActive,
      builtInDirectiveTitle: CORE_GROWTH_DIRECTIVE_TITLE,
      builtInDirectiveSummary: CORE_GROWTH_DIRECTIVE_SUMMARY,
      primaryAction,
      autonomyAction,
      active: coreGrowthActive,
      objective: text(
        growth.active_capability_growth_objective,
        growth.next_capability_gap_proposal,
        "No active growth objective recorded.",
      ),
      latestHumanGate: text(growth.latest_human_approval_required_reason),
      nextAction: text(growth.nine_d_next_maturity_action, growth.next_maturity_action, "No next growth action recorded."),
    },
  };
}
