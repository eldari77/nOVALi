import {
  AlertTriangle,
  BookOpen,
  Bot,
  BrainCircuit,
  ChevronRight,
  CirclePause,
  Compass,
  Gem,
  Hexagon,
  Layers3,
  Play,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  Wand2,
} from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";

import {
  approveAutonomyOperation,
  continueLongRun,
  createConveyorDirective,
  decideConveyorReturn,
  decideConveyorSupportRequest,
  emergencyStopAutonomy,
  executeExternalAdapterReviewDisposition,
  executeExternalAdapterReviewDispositionAll,
  executeReviewAction,
  fetchAutonomyGoals,
  fetchConveyorOvernightReadiness,
  fetchConveyorSummary,
  fetchConveyorStatus,
  fetchConveyorSupportRequests,
  fetchConveyorReturnArtifact,
  fetchAutonomyStatus,
  fetchCurrentDirective,
  fetchGovernedProcesses,
  fetchInterventionState,
  fetchLibrarianSearch,
  fetchLibrarianStatus,
  fetchLLMHistory,
  fetchLLMPendingDirectives,
  fetchLLMStatus,
  fetchLongRunState,
  fetchObservabilityStatus,
  fetchOperatorState,
  fetchOperatorShellSettings,
  pauseAutonomy,
  pauseLongRun,
  patchOperatorShellSettings,
  patchTrustedSource,
  reviewAutonomyBoard,
  resumeLongRun,
  sendLLMChat,
  startDispatchFromConveyorQueue,
  startAutonomy,
  startGoverned,
  stopLongRun,
  fetchTrustedSourceSettings,
  upsertTrustedSource,
  validateTrustedSourceSetting,
  type AutonomyStatusPayload,
  type ConveyorStatusPayload,
  type ConveyorReturnArtifactPayload,
  type ConveyorSummaryPayload,
  type CurrentDirectiveStatus,
  type GovernedProcessLifecyclePayload,
  type LLMHistoryPayload,
  type LLMMode,
  type LLMStatusPayload,
  type LibrarianSearchPayload,
  type LibrarianStatusPayload,
  type LongRunStatePayload,
  type OperatorState,
  type OperatorShellSettingsPayload,
  type ReviewPayload,
  type TrustedSourceSettingsPayload,
} from "./lib/api";
import {
  buildArtifactPreviewModel,
  buildConveyorBatchReturnActions,
  buildConveyorWorkbench,
  buildReturnsWorkbench,
  mergeShellStateAfterAction,
  mergeShellStateAfterRefresh,
} from "./lib/conveyorReview.js";
import {
  buildLLMProgressModel,
  buildConveyorPayloadFromDraft,
  buildDirectiveRevisionPrompt,
  directiveDraftCompleteness,
  selectLatestDirectiveDraft,
  selectLatestDirectiveDraftAttempt,
} from "./lib/llmDirectiveReview.js";
import {
  askDrawerAccessibilityProps,
  buildAttentionQueue,
  buildCommandOverview,
  buildDirectiveWorkSummary,
  buildOperatorActivitySnapshot,
  buildOperatorToolbarItems,
  buildOperatorTruthSummary,
  buildRuntimeSummary,
  formatFrameworkTimestamp,
  formatFrameworkTimestampsInText,
  OPERATOR_ARCANE_THEME,
  resolvePrimarySafeAction,
} from "./lib/operatorShellView.js";

type LoadState = {
  operatorState: OperatorState | null;
  longRun: LongRunStatePayload | null;
  processLifecycle: GovernedProcessLifecyclePayload | null;
  autonomy: AutonomyStatusPayload | null;
  observability: Record<string, unknown> | null;
  intervention: ReviewPayload | null;
  directive: CurrentDirectiveStatus | null;
  llmStatus: LLMStatusPayload | null;
  llmHistory: LLMHistoryPayload | null;
  autonomyGoals: Record<string, unknown> | null;
  llmPending: Record<string, unknown> | null;
  conveyorSummary: ConveyorSummaryPayload | null;
  conveyorStatus: ConveyorStatusPayload | null;
  conveyorOvernightReadiness: Record<string, unknown> | null;
  conveyorSupportRequests: Record<string, unknown> | null;
  librarianStatus: LibrarianStatusPayload | null;
  librarianSearch: LibrarianSearchPayload | null;
  operatorSettings: OperatorShellSettingsPayload | null;
  trustedSourceSettings: TrustedSourceSettingsPayload | null;
  refreshMeta?: Record<string, unknown>;
};

type ActiveTab = "overview" | "queue" | "conveyor" | "returns" | "growth" | "runtime" | "librarian" | "settings";

type Toast = { tone: "success" | "warning" | "danger"; message: string };

const emptyState: LoadState = {
  operatorState: null,
  longRun: null,
  processLifecycle: null,
  autonomy: null,
  observability: null,
  intervention: null,
  directive: null,
  llmStatus: null,
  llmHistory: null,
  autonomyGoals: null,
  llmPending: null,
  conveyorSummary: null,
  conveyorStatus: null,
  conveyorOvernightReadiness: null,
  conveyorSupportRequests: null,
  librarianStatus: null,
  librarianSearch: null,
  operatorSettings: null,
  trustedSourceSettings: null,
  refreshMeta: {},
};

const text = (...values: unknown[]) => {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const next = String(value).trim();
    if (next) return next;
  }
  return "";
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : {};

const asArray = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];

const asList = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const formatKind = (value: unknown) =>
  text(value, "unknown")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const formatBytes = (value: unknown) => {
  let next = Number(value || 0);
  if (!Number.isFinite(next) || next <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let unit = 0;
  while (next >= 1024 && unit < units.length - 1) {
    next /= 1024;
    unit += 1;
  }
  return unit === 0 ? `${Math.round(next)} ${units[unit]}` : `${next.toFixed(1)} ${units[unit]}`;
};

const statusToneClass = (tone: string) =>
  tone === "danger" ? "tone-danger" : tone === "attention" ? "tone-attention" : "tone-healthy";

function isWorkspaceRoute() {
  return window.location.pathname.replace(/\/+$/, "") === "/shell/workspace";
}

async function loadFastShellState(): Promise<Partial<LoadState>> {
  const [
    operatorState,
    longRun,
    processLifecycle,
    autonomy,
    intervention,
    directive,
    conveyorSummary,
  ] = await Promise.all([
    fetchOperatorState().catch(() => null),
    fetchLongRunState().catch(() => null),
    fetchGovernedProcesses().catch(() => null),
    fetchAutonomyStatus().catch(() => null),
    fetchInterventionState().catch(() => null),
    fetchCurrentDirective().catch(() => null),
    fetchConveyorSummary().catch(() => null),
  ]);
  return {
    operatorState,
    longRun,
    processLifecycle,
    autonomy,
    intervention,
    directive,
    conveyorSummary,
  };
}

async function loadMediumShellState(): Promise<Partial<LoadState>> {
  const [
    observability,
    llmStatus,
    llmHistory,
    autonomyGoals,
    llmPending,
    conveyorSupportRequests,
    librarianStatus,
    librarianSearch,
    operatorSettings,
    trustedSourceSettings,
  ] = await Promise.all([
    fetchObservabilityStatus().catch(() => null),
    fetchLLMStatus().catch(() => null),
    fetchLLMHistory().catch(() => null),
    fetchAutonomyGoals().catch(() => null),
    fetchLLMPendingDirectives().catch(() => null),
    fetchConveyorSupportRequests().catch(() => null),
    fetchLibrarianStatus().catch(() => null),
    fetchLibrarianSearch({ limit: 8 }).catch(() => null),
    fetchOperatorShellSettings().catch(() => null),
    fetchTrustedSourceSettings().catch(() => null),
  ]);
  return {
    observability,
    llmStatus,
    llmHistory,
    autonomyGoals,
    llmPending,
    conveyorSupportRequests,
    librarianStatus,
    librarianSearch,
    operatorSettings,
    trustedSourceSettings,
  };
}

async function loadSlowShellState(): Promise<Partial<LoadState>> {
  const [conveyorStatus, conveyorOvernightReadiness] = await Promise.all([
    fetchConveyorStatus().catch(() => null),
    fetchConveyorOvernightReadiness().catch(() => null),
  ]);
  return {
    conveyorStatus,
    conveyorOvernightReadiness,
  };
}

export function OperatorShellApp() {
  const [state, setState] = useState<LoadState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [toast, setToast] = useState<Toast | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>(isWorkspaceRoute() ? "queue" : "overview");
  const [toolbarCollapsed, setToolbarCollapsed] = useState(false);
  const [clockNow, setClockNow] = useState(() => Date.now());
  const [llmPrompt, setLlmPrompt] = useState("");
  const [llmMode, setLlmMode] = useState<LLMMode>("explain_state");
  const [askOpen, setAskOpen] = useState(false);
  const [draftFeedback, setDraftFeedback] = useState("");
  const [expandedReturnId, setExpandedReturnId] = useState("");
  const [selectedReturnId, setSelectedReturnId] = useState("");
  const [selectedReturnIds, setSelectedReturnIds] = useState<string[]>([]);
  const [activeArtifactTab, setActiveArtifactTab] = useState("Summary");
  const [artifactPreview, setArtifactPreview] = useState<ConveyorReturnArtifactPayload | null>(null);
  const [librarianQuery, setLibrarianQuery] = useState("");
  const [frameworkTimezoneDraft, setFrameworkTimezoneDraft] = useState("");
  const [trustedSourceDraft, setTrustedSourceDraft] = useState({
    source_id: "",
    source_kind: "mcp_server",
    enabled: true,
    endpoint_base: "",
    credential_strategy: "none",
    credential_ref: "",
    capability_tags: "",
    allowed_directive_queue_ids: "",
    max_requests_per_directive: "3",
    requires_operator_review: true,
  });

  async function refresh(soft = false) {
    if (!soft) setLoading(true);
    try {
      const fastState = await loadFastShellState();
      setState((previous) =>
        (soft
          ? mergeShellStateAfterRefresh(previous, fastState)
          : mergeShellStateAfterRefresh(emptyState, fastState)) as LoadState,
      );
      setLoading(false);
      const [mediumResult, slowResult] = await Promise.allSettled([
        loadMediumShellState(),
        loadSlowShellState(),
      ]);
      const mediumState = mediumResult.status === "fulfilled" ? mediumResult.value : {};
      const slowState = slowResult.status === "fulfilled" ? slowResult.value : {};
      setState(
        (previous) =>
          mergeShellStateAfterRefresh(previous, { ...mediumState, ...slowState }) as LoadState,
      );
      if (!soft) setToast({ tone: "success", message: "Operator state refreshed." });
    } catch (error) {
      setToast({ tone: "danger", message: `Refresh failed: ${String(error)}` });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh(true);
    const timer = window.setInterval(() => refresh(true), 15000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setClockNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const timezone = text(state.operatorSettings?.framework_timezone);
    if (timezone) setFrameworkTimezoneDraft(timezone);
  }, [state.operatorSettings?.framework_timezone]);

  const overview = useMemo(
    () =>
      buildCommandOverview({
        longRun: state.longRun,
        processLifecycle: state.processLifecycle,
        autonomy: state.autonomy,
        observability: state.observability,
        operatorState: state.operatorState,
        currentDirective: state.directive,
        operatorSettings: state.operatorSettings,
        now: clockNow,
      }),
    [state, clockNow],
  );
  const dispatchHealth = asRecord(
    asRecord(state.longRun).dispatch_health ??
      asRecord(state.conveyorOvernightReadiness).dispatch_health,
  );
  const queue = useMemo(
    () =>
      buildAttentionQueue({
        operatorState: state.operatorState,
        conveyorSupportRequests: state.conveyorSupportRequests ?? state.conveyorStatus,
        dispatchHealth,
      }),
    [state.operatorState, state.conveyorSupportRequests, state.conveyorStatus, dispatchHealth],
  );
  const directive = useMemo(
    () =>
      buildDirectiveWorkSummary({
        autonomy: state.autonomy,
        currentDirective: state.directive,
        longRun: state.longRun,
        operatorState: state.operatorState,
      }),
    [state.autonomy, state.directive, state.longRun, state.operatorState],
  );
  const runtime = useMemo(
    () => buildRuntimeSummary({ autonomy: state.autonomy, observability: state.observability }),
    [state.autonomy, state.observability],
  );
  const conveyorWorkbench = useMemo(
    () =>
      buildConveyorWorkbench({
        conveyorStatus: state.conveyorStatus,
        conveyorSummary: state.conveyorSummary,
        conveyorOvernightReadiness: state.conveyorOvernightReadiness,
        autonomyStatus: state.autonomy,
        longRun: state.longRun,
        currentDirective: state.directive,
      }),
    [
      state.conveyorStatus,
      state.conveyorSummary,
      state.conveyorOvernightReadiness,
      state.autonomy,
      state.longRun,
      state.directive,
    ],
  );
  const returnsWorkbench = useMemo(
    () =>
      buildReturnsWorkbench({
        conveyorStatus: state.conveyorStatus,
        conveyorSupportRequests: state.conveyorSupportRequests,
        conveyorSummary: state.conveyorSummary,
      }),
    [state.conveyorStatus, state.conveyorSupportRequests, state.conveyorSummary],
  );
  const operatorTruth = useMemo(
    () =>
      buildOperatorTruthSummary({
        overview,
        conveyorSummary: state.conveyorSummary,
        returnsWorkbench,
        refreshMeta: state.refreshMeta,
        operatorSettings: state.operatorSettings,
        loading,
      }),
    [overview, state.conveyorSummary, returnsWorkbench, state.refreshMeta, state.operatorSettings, loading],
  );
  const toolbarItems = useMemo(
    () =>
      buildOperatorToolbarItems({
        activeTab,
        returnsBadgeCount: Number(returnsWorkbench.badgeCount || 0),
        collapsed: toolbarCollapsed,
      }),
    [activeTab, returnsWorkbench.badgeCount, toolbarCollapsed],
  );
  const activitySnapshot = useMemo(
    () =>
      buildOperatorActivitySnapshot({
        overview,
        operatorTruth,
        conveyorSummary: state.conveyorSummary,
        conveyorWorkbenchSummary: conveyorWorkbench.summary,
        refreshMeta: state.refreshMeta,
        operatorSettings: state.operatorSettings,
      }),
    [overview, operatorTruth, state.conveyorSummary, conveyorWorkbench.summary, state.refreshMeta, state.operatorSettings],
  );
  const toolbarIconById = {
    overview: Compass,
    queue: AlertTriangle,
    conveyor: Layers3,
    returns: BookOpen,
    growth: Sparkles,
    runtime: BrainCircuit,
    librarian: BookOpen,
    settings: Settings,
  } as const;
  const conveyorMission = asRecord(conveyorWorkbench.missionControl);
  const conveyorQueue = asArray(conveyorMission.queue);
  const activeConveyorWorkers = asArray(conveyorMission.activeWorkers);
  const selectedReturn =
    conveyorQueue.find((packet) => text(packet.returnPacketId) === selectedReturnId) ||
    asRecord(conveyorMission.selectedPacket);
  const selectedReturnPacketId = text(selectedReturn.returnPacketId, conveyorMission.selectedReturnId);
  const selectedGateSummary = asRecord(selectedReturn.gateSummary);
  const conveyorRefreshMeta = asRecord(state.refreshMeta);
  const artifactPreviewModel = useMemo(
    () => buildArtifactPreviewModel(artifactPreview || {}),
    [artifactPreview],
  );
  const primarySafeAction = useMemo(
    () => resolvePrimarySafeAction(operatorTruth.primaryAction),
    [operatorTruth.primaryAction],
  );

  useEffect(() => {
    const queueIds = conveyorQueue.map((packet) => text(packet.returnPacketId)).filter(Boolean);
    const defaultReturnId = text(selectedReturnId, conveyorMission.selectedReturnId, queueIds[0]);
    if (defaultReturnId && !queueIds.includes(selectedReturnId)) {
      setSelectedReturnId(defaultReturnId);
    }
    setSelectedReturnIds((existing) => existing.filter((returnId) => queueIds.includes(returnId)));
  }, [conveyorWorkbench, conveyorMission.selectedReturnId, selectedReturnId]);

  async function runAction(actionId: string, action: () => Promise<unknown>) {
    setBusyAction(actionId);
    setToast(null);
    try {
      const result = asRecord(await action());
      setToast({
        tone: Boolean(result.ok ?? true) ? "success" : "warning",
        message: text(result.message, `${formatKind(actionId)} completed.`),
      });
      setState((previous) => mergeShellStateAfterAction(previous, result) as LoadState);
      await refresh(true);
    } catch (error) {
      const message = String(error);
      if (actionId === "ask_novali" && message.toLowerCase().includes("timed out")) {
        setToast({
          tone: "warning",
          message:
            "Ask Novali timed out in the browser. The backend receipt may still finish; refresh Ask Novali history before retrying.",
        });
        await refresh(true);
        return;
      }
      setToast({ tone: "danger", message: `${formatKind(actionId)} failed: ${String(error)}` });
    } finally {
      setBusyAction("");
    }
  }

  function executePrimarySafeAction() {
    const targetTab = text(asRecord(operatorTruth.primaryAction).targetTab) as ActiveTab;
    if (targetTab && ["overview", "queue", "conveyor", "returns", "growth", "runtime", "librarian", "settings"].includes(targetTab)) {
      return setActiveTab(targetTab);
    }
    if (primarySafeAction.request === "start_governed") {
      return runAction(primarySafeAction.actionId, () => startGoverned({}));
    }
    if (primarySafeAction.request === "continue_long_run") {
      return runAction(primarySafeAction.actionId, () => continueLongRun());
    }
    return setActiveTab("queue");
  }

  const longRunPayload = asRecord(asRecord(state.longRun).long_run || state.longRun);
  const latestOperation = asRecord(
    asRecord(state.autonomy).latest_operation ||
      asRecord(state.autonomy).latest_proposed_operation ||
      asRecord(state.autonomy).proposed_operation,
  );
  const operationId = text(latestOperation.operation_id, latestOperation.id);
  const firstReviewOption = asArray(asRecord(state.intervention).options)[0];
  const latestDirectiveDraft = useMemo(
    () => selectLatestDirectiveDraft(asRecord(state.llmHistory)),
    [state.llmHistory],
  );
  const latestDirectiveDraftAttempt = useMemo(
    () => selectLatestDirectiveDraftAttempt(asRecord(state.llmHistory)),
    [state.llmHistory],
  );
  const latestLLMChatAttempt = useMemo(
    () => asRecord(asArray(asRecord(state.llmHistory).records)[0]),
    [state.llmHistory],
  );
  const latestLLMProgress = useMemo(
    () => buildLLMProgressModel(latestLLMChatAttempt),
    [latestLLMChatAttempt],
  );
  const latestDirectiveDraftCompleteness = useMemo(
    () => directiveDraftCompleteness(text(latestDirectiveDraft.directive_text)),
    [latestDirectiveDraft],
  );
  const latestDraftAttemptIsNewer = Boolean(
    text(latestDirectiveDraftAttempt.record_id) &&
      text(latestDirectiveDraftAttempt.record_id) !== text(latestDirectiveDraft.record_id) &&
      ["in_progress", "timeout", "malformed_response", "unavailable", "error"].includes(
        text(latestDirectiveDraftAttempt.status).toLowerCase(),
      ),
  );
  useEffect(() => {
    if (!askOpen || (busyAction !== "ask_novali" && !latestLLMProgress.active)) return;
    let cancelled = false;
    const pollHistory = async () => {
      try {
        const history = await fetchLLMHistory();
        if (!cancelled) {
          setState((previous) => ({ ...previous, llmHistory: history }) as LoadState);
        }
      } catch {
        // Soft polling is advisory; the normal refresh loop remains authoritative.
      }
    };
    pollHistory();
    const timer = window.setInterval(pollHistory, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [askOpen, busyAction, latestLLMProgress.active]);
  async function askNovali() {
    if (!llmPrompt.trim()) {
      setToast({ tone: "warning", message: "Ask Novali needs a prompt first." });
      return;
    }
    await runAction("ask_novali", () => sendLLMChat({ message: llmPrompt, mode: llmMode }));
    setLlmPrompt("");
  }

  async function reviseDirectiveDraft() {
    const draftText = text(latestDirectiveDraft.directive_text);
    if (!draftText) {
      setToast({ tone: "warning", message: "Ask Novali for a directive draft before requesting changes." });
      return;
    }
    if (!draftFeedback.trim()) {
      setToast({ tone: "warning", message: "Add recommended changes before revising the draft." });
      return;
    }
    const prompt = buildDirectiveRevisionPrompt({ draftText, feedback: draftFeedback });
    await runAction("revise_directive_draft", () => sendLLMChat({ message: prompt, mode: "draft_directive" }));
    setDraftFeedback("");
  }

  async function approveDirectiveDraftForConveyor() {
    if (!latestDirectiveDraftCompleteness.complete) {
      setToast({
        tone: "warning",
        message: `Complete the draft before conveyor approval: ${latestDirectiveDraftCompleteness.reasons.join(", ")}`,
      });
      return;
    }
    const payload = buildConveyorPayloadFromDraft(latestDirectiveDraft);
    if (!text(payload.directive_text)) {
      setToast({ tone: "warning", message: "Ask Novali for a directive draft before approving it for the conveyor." });
      return;
    }
    await runAction("approve_draft_for_conveyor", () => createConveyorDirective(payload));
  }

  async function decideReturnedWork(
    returnPacketId: string,
    action: "accept" | "requeue" | "clarify" | "reject" | "split",
    packet: Record<string, unknown> = {},
  ) {
    if (
      action === "accept" &&
      !window.confirm(
        `Accept final deliverables for ${text(packet.title, returnPacketId)}? This marks the return complete instead of sending it back for deeper conveyor work.`,
      )
    ) {
      return;
    }
    const defaultReviewFeedback =
      action === "requeue" || action === "clarify"
        ? "Expand into build-grade real-world technical documentation. Continue from the previous packet and artifacts. For dependency_matrix.json, build a prototype dependency hierarchy with subsystem prerequisites, interface/runtime dependencies, evidence/source constraints, risk if missing, and safe architecture-level boundaries. Use satisfied support packs for claims and mark unsupported claims for operator review."
        : `Operator requested ${action} from conveyor returned-work review.`;
    const feedback =
      action === "accept"
        ? "Accepted from conveyor returned-work review."
        : text(draftFeedback, defaultReviewFeedback);
    const clarifications =
      action === "clarify"
        ? asArray(packet.requestedOperatorClarifications).map((clarification) => ({
            ...asRecord(clarification),
            answer: feedback,
          }))
        : undefined;
    const approveSupportBeforeRequeue =
      action === "requeue" && Boolean(asRecord(packet.primaryAction).approveSupportBeforeRequeue);
    if (
      approveSupportBeforeRequeue &&
      !window.confirm(
        `Approve kernel-mediated support and continue ${text(packet.title, returnPacketId)}?\n\nIf no reusable Librarian pack exists, Novali may use configured trusted-source/OpenAI support before requeueing this directive.`,
      )
    ) {
      return;
    }
    await runAction(`conveyor_return_${action}`, () =>
      decideConveyorReturn(returnPacketId, action, {
        operator_note: feedback,
        feedback,
        ...(clarifications ? { clarifications } : {}),
        ...(approveSupportBeforeRequeue ? { approve_support_before_requeue: true } : {}),
      }),
    );
  }

  function toggleSelectedReturn(returnPacketId: string) {
    setSelectedReturnIds((existing) =>
      existing.includes(returnPacketId)
        ? existing.filter((candidate) => candidate !== returnPacketId)
        : [...existing, returnPacketId],
    );
  }

  async function requestBatchDeeperPass() {
    const selectedPackets = conveyorQueue.filter((packet) => selectedReturnIds.includes(text(packet.returnPacketId)));
    if (!selectedPackets.length) return;
    const feedback = text(
      draftFeedback,
      "Apply a deeper build-grade pass to the selected directives. Continue from prior artifacts, expand subsystem/interface/dependency/validation/prototype detail, and cite support packs for material claims. For dependency_matrix.json, build a prototype dependency hierarchy with subsystem prerequisites, evidence/source constraints, risk if missing, and safe architecture-level boundaries.",
    );
    const confirmationList = selectedPackets.map((packet) => `${text(packet.title)} (${text(packet.returnPacketId)})`).join("\n");
    const supportBlockedPackets = selectedPackets.filter((packet) => Boolean(packet.supportRequiredBeforeContinue));
    const supportNotice = supportBlockedPackets.length
      ? `\n\n${supportBlockedPackets.length} selected return(s) require kernel support first. If no reusable Librarian pack exists, Novali may use configured trusted-source/OpenAI support before requeueing.`
      : "";
    if (!window.confirm(`Request a deeper pass for these returns?\n\n${confirmationList}${supportNotice}`)) return;
    const actions = buildConveyorBatchReturnActions({
      returnPacketIds: selectedPackets.map((packet) => text(packet.returnPacketId)),
      feedback,
      supportRequiredReturnIds: supportBlockedPackets.map((packet) => text(packet.returnPacketId)),
    });
    await runAction("conveyor_return_batch_requeue", () =>
      Promise.all(
        actions.map((item: Record<string, unknown>) =>
          decideConveyorReturn(text(item.returnPacketId), "requeue", asRecord(item.payload)),
        ),
      ),
    );
  }

  async function selectArtifactTab(tabName: string) {
    setActiveArtifactTab(tabName);
    const artifactByTab: Record<string, string> = {
      "Technical Doc": "technical_documentation.md",
      Subsystems: "subsystem_matrix.json",
      Interfaces: "interface_specifications.json",
      Dependencies: "dependency_matrix.json",
      Validation: "validation_protocols.json",
      Milestones: "prototype_milestones.json",
      Claims: "claim_evidence_register.json",
      Novelty: "novelty_delta.json",
    };
    const artifactName = artifactByTab[tabName];
    if (artifactName && selectedReturnPacketId) {
      await openReturnArtifact(selectedReturnPacketId, artifactName);
    }
  }

  async function openCanonicalArtifact(artifactName: string) {
    const safeArtifactName = text(artifactName);
    if (!safeArtifactName || !selectedReturnPacketId) return;
    setActiveArtifactTab(safeArtifactName);
    await openReturnArtifact(selectedReturnPacketId, safeArtifactName);
  }

  async function openReturnArtifact(returnPacketId: string, artifactName: string) {
    setBusyAction(`conveyor_artifact_${returnPacketId}_${artifactName}`);
    setToast(null);
    try {
      const result = await fetchConveyorReturnArtifact(returnPacketId, artifactName);
      setArtifactPreview(result);
      setToast({
        tone: result.ok ? "success" : "warning",
        message: result.ok ? `Opened ${artifactName}.` : text(result.message, "Artifact could not be opened."),
      });
    } catch (error) {
      setToast({ tone: "danger", message: `Artifact open failed: ${String(error)}` });
    } finally {
      setBusyAction("");
    }
  }

  async function decideSupportRequest(supportRequestId: string, action: "approve" | "reject" | "satisfy") {
    await runAction(`conveyor_support_${action}`, () =>
      decideConveyorSupportRequest(supportRequestId, action, {
        operator_note:
          action === "approve"
            ? "Operator approved trusted-source support request from Ask Novali review."
            : action === "satisfy"
              ? "Operator marked support request satisfied from a staged Librarian pack."
            : "Operator rejected trusted-source support request from Ask Novali review.",
      }),
    );
  }

  async function dispositionExternalAdapterReview(reviewItemId: string, dispositionActionId: string) {
    await runAction(`external_adapter_review_${dispositionActionId}`, () =>
      executeExternalAdapterReviewDisposition({
        review_item_id: reviewItemId,
        disposition_action_id: dispositionActionId,
        operator_note:
          "Operator applied conservative external-adapter review disposition from the visible queue. Adapter remains mock-only; no execution authority or real-world action is authorized.",
      }),
    );
  }

  async function dispositionAllExternalAdapterReviews() {
    await runAction("external_adapter_review_disposition_all", () =>
      executeExternalAdapterReviewDispositionAll({
        operator_note:
          "Operator applied conservative audit disposition to all visible external-adapter hard blockers. Adapter remains mock-only; no execution authority or real-world action is authorized.",
      }),
    );
  }

  async function startSeedableConveyorDispatch() {
    await runAction("start_seedable_conveyor_dispatch", () =>
      startDispatchFromConveyorQueue({
        operator_note:
          "Operator started seedable conveyor dispatch from the visible queue. Use bootstrap-only initialization if needed, then governed execution through the existing authority chain.",
      }),
    );
  }

  async function searchLibrarian() {
    setBusyAction("librarian_search");
    setToast(null);
    try {
      const result = await fetchLibrarianSearch({ q: librarianQuery, limit: 12 });
      setState((previous) => ({ ...previous, librarianSearch: result }));
      setToast({ tone: "success", message: `Librarian returned ${result.result_count ?? 0} pack refs.` });
    } catch (error) {
      setToast({ tone: "danger", message: `Librarian search failed: ${String(error)}` });
    } finally {
      setBusyAction("");
    }
  }

  async function saveTrustedSourceDraft() {
    const sourceId = text(trustedSourceDraft.source_id);
    if (!sourceId) {
      setToast({ tone: "warning", message: "Source id is required." });
      return;
    }
    const payload = {
      source_id: sourceId,
      source_kind: trustedSourceDraft.source_kind,
      enabled: trustedSourceDraft.enabled,
      endpoint_base: ["local_path", "local_bundle"].includes(trustedSourceDraft.source_kind)
        ? ""
        : trustedSourceDraft.endpoint_base.trim(),
      path_hint: ["local_path", "local_bundle"].includes(trustedSourceDraft.source_kind)
        ? trustedSourceDraft.endpoint_base.trim()
        : "",
      credential_strategy: trustedSourceDraft.credential_strategy,
      credential_ref: trustedSourceDraft.credential_ref.trim(),
      capability_tags: trustedSourceDraft.capability_tags
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      allowed_directive_queue_ids: trustedSourceDraft.allowed_directive_queue_ids
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      max_requests_per_directive: Number(trustedSourceDraft.max_requests_per_directive || 0),
      requires_operator_review: trustedSourceDraft.requires_operator_review,
    };
    await runAction("save_trusted_source", () => upsertTrustedSource(payload));
  }

  async function saveFrameworkTimezone() {
    const frameworkTimezone = text(frameworkTimezoneDraft);
    if (!frameworkTimezone) {
      setToast({ tone: "warning", message: "Framework timezone is required." });
      return;
    }
    await runAction("save_framework_timezone", () =>
      patchOperatorShellSettings({ framework_timezone: frameworkTimezone }),
    );
  }

  async function validateTrustedSourceRow(sourceId: string) {
    await runAction("validate_trusted_source", () => validateTrustedSourceSetting(sourceId));
  }

  async function toggleTrustedSource(sourceId: string, enabled: boolean) {
    await runAction("toggle_trusted_source", () => patchTrustedSource(sourceId, { enabled }));
  }

  function updateTrustedSourceDraft(field: keyof typeof trustedSourceDraft, value: string | boolean) {
    setTrustedSourceDraft((previous) => ({ ...previous, [field]: value }));
  }

  const librarianStatus = asRecord(state.librarianStatus);
  const librarianResults = asArray(asRecord(state.librarianSearch).results);
  const operatorSettings = asRecord(state.operatorSettings);
  const frameworkClock = asRecord(overview.frameworkClock);
  const formattedConveyorRefreshWarning = formatFrameworkTimestampsInText(
    text(conveyorRefreshMeta.conveyorRefreshWarning),
    { operatorSettings: state.operatorSettings },
  );
  const formattedConveyorLastRefreshedAt = formatFrameworkTimestamp(
    text(conveyorRefreshMeta.conveyorLastRefreshedAt, conveyorRefreshMeta.lastRefreshedAt),
    { operatorSettings: state.operatorSettings },
  );
  const supportedTimezones = (
    (state.operatorSettings?.supported_timezones as string[] | undefined) ?? [
      "UTC",
      "America/New_York",
      "America/Chicago",
      "America/Denver",
      "America/Los_Angeles",
      "Europe/London",
      "Europe/Berlin",
      "Asia/Tokyo",
      "Australia/Sydney",
    ]
  ).filter(Boolean);
  const trustedSourceSettings = asRecord(state.trustedSourceSettings);
  const trustedSources = asArray(trustedSourceSettings.sources);
  const trustedSourceKinds = ((state.trustedSourceSettings?.supported_source_kinds as string[] | undefined) ?? [
    "local_path",
    "local_bundle",
    "network_api",
    "mcp_server",
    "agent_endpoint",
  ]).filter(Boolean);
  const trustedCredentialStrategies = (
    (state.trustedSourceSettings?.supported_credential_strategies as string[] | undefined) ?? [
      "none",
      "env_var",
      "local_secret_store",
    ]
  ).filter(Boolean);
  return (
    <main className="arcane-shell" data-testid="react-operator-shell">
      <header className="top-command">
        <div className="brand-mark" aria-hidden="true">
          <Hexagon />
        </div>
        <div>
          <p className="eyebrow">NOVALI Operator Shell</p>
          <h1>Command Overview</h1>
          <p className="subtitle">
            Task-first control for directive work, governed continuation, autonomy health, and runtime truth.
          </p>
        </div>
        <div className="top-actions">
          <button
            className={loading ? "icon-btn refreshing" : "icon-btn"}
            title="Refresh operator state"
            onClick={() => refresh()}
            disabled={loading}
          >
            <RefreshCw size={18} />
            <span>{loading ? "Refreshing" : "Refresh"}</span>
          </button>
          <button
            className="danger-btn"
            title="Emergency stop autonomy"
            disabled={busyAction === "emergency_stop"}
            onClick={() => runAction("emergency_stop", () => emergencyStopAutonomy("operator_shell_react_ui"))}
          >
            <ShieldAlert size={18} />
            <span>Emergency stop</span>
          </button>
        </div>
      </header>

      {toast ? <div className={`toast ${toast.tone}`}>{toast.message}</div> : null}

      <section
        className={`safety-rune ${statusToneClass(operatorTruth.safetyTone)} ${operatorTruth.freshness}`}
        data-testid="command-overview"
      >
        <div className="status-orb">
          {operatorTruth.safetyTone === "danger" ? <ShieldAlert /> : <ShieldCheck />}
        </div>
        <div className="safety-copy">
          <div className="truth-heading-row">
            <p className="eyebrow">{operatorTruth.label}</p>
            <span className={`freshness-chip ${operatorTruth.freshness}`}>{formatKind(operatorTruth.freshness)}</span>
          </div>
          <h2>{operatorTruth.headline}</h2>
          <p>{operatorTruth.detail}</p>
          {overview.lifecycleWarnings?.length ? (
            <p className="inline-warning">
              <AlertTriangle size={14} />
              <span>{overview.lifecycleWarnings[0]}</span>
            </p>
          ) : null}
        </div>
        <div className="framework-clock" aria-label="Current framework time">
          <span>Framework time</span>
          <strong>{text(frameworkClock.timeLabel, "--:--:--")}</strong>
          <small>
            {text(frameworkClock.dateLabel, "date unavailable")} · {text(frameworkClock.timezoneLabel, frameworkClock.timezone)}
          </small>
        </div>
        <div className="primary-action">
          <button
            className="primary-btn"
            data-testid="primary-safe-action"
            disabled={!operatorTruth.primaryAction.enabled || busyAction === primarySafeAction.actionId}
            onClick={executePrimarySafeAction}
          >
            <Play size={18} />
            <span>{operatorTruth.primaryAction.label}</span>
          </button>
          <button className="secondary-btn" onClick={() => setAskOpen(true)}>
            <Bot size={18} />
            <span>Ask Novali</span>
          </button>
        </div>
      </section>

      <section className={`operator-activity-strip ${operatorTruth.freshness}`} aria-label="Operator activity">
        <div className="activity-flow" aria-hidden="true" />
        <div>
          <span>{activitySnapshot.lane.label}</span>
          <strong>{activitySnapshot.lane.value}</strong>
        </div>
        <div>
          <span>{activitySnapshot.children.label}</span>
          <strong>{activitySnapshot.children.value}</strong>
          {activitySnapshot.children.detail ? <small>{activitySnapshot.children.detail}</small> : null}
        </div>
        <div>
          <span>{activitySnapshot.returns.label}</span>
          <strong>{activitySnapshot.returns.value}</strong>
        </div>
        <div>
          <span>{activitySnapshot.telemetry.label}</span>
          <strong>{activitySnapshot.telemetry.value}</strong>
        </div>
        {activitySnapshot.staleDetail ? <p>{activitySnapshot.staleDetail}</p> : null}
      </section>

      <div className={toolbarCollapsed ? "shell-workspace toolbar-collapsed" : "shell-workspace"}>
        <aside className="side-toolbar" aria-label="Operator shell sections">
          <button
            className="toolbar-toggle"
            type="button"
            aria-label={toolbarCollapsed ? "Expand navigation toolbar" : "Collapse navigation toolbar"}
            aria-expanded={!toolbarCollapsed}
            onClick={() => setToolbarCollapsed((value) => !value)}
          >
            <ChevronRight size={17} aria-hidden="true" />
            <span>{toolbarCollapsed ? "" : "Collapse"}</span>
          </button>
          <nav>
            {toolbarItems.map((item) => {
              const Icon = toolbarIconById[item.id as keyof typeof toolbarIconById] || Compass;
              return (
                <button
                  key={item.id}
                  className={item.active ? "active" : ""}
                  aria-label={item.ariaLabel}
                  title={item.label}
                  onClick={() => setActiveTab(item.id as ActiveTab)}
                >
                  <Icon size={18} aria-hidden="true" />
                  {item.displayLabel ? <span>{item.displayLabel}</span> : null}
                  {item.badge ? <span className="tab-badge">{item.badge}</span> : null}
                </button>
              );
            })}
          </nav>
        </aside>
        <div className="shell-content">

      {activeTab === "overview" ? (
        <section className="dashboard-grid">
          <Panel title="Next safe operation" icon={<Compass />}>
            <p className="large-state">{operatorTruth.primaryAction.label}</p>
            <p>{operatorTruth.detail}</p>
            <div className="action-row">
              <button
                className="primary-btn"
                disabled={!operatorTruth.primaryAction.enabled || busyAction === primarySafeAction.actionId}
                onClick={executePrimarySafeAction}
              >
                <Play size={16} />
                {operatorTruth.primaryAction.label}
              </button>
              <button className="secondary-btn" onClick={() => runAction("pause_long_run", () => pauseLongRun())}>
                <CirclePause size={16} />
                Pause
              </button>
              <button className="secondary-btn" onClick={() => runAction("resume_long_run", () => resumeLongRun())}>
                <Play size={16} />
                Resume
              </button>
            </div>
          </Panel>
          <Panel title="Operator attention" icon={<AlertTriangle />}>
            <div className="count-grid">
              <Metric label="Blockers" value={String(queue.blockers.length)} />
              <Metric label="Resumable" value={String(queue.resumable.length)} />
              <Metric label="Info" value={String(queue.informational.length)} />
            </div>
            <button
              className={returnsWorkbench.badgeCount ? "primary-btn" : "secondary-btn"}
              onClick={() => setActiveTab(returnsWorkbench.badgeCount ? "returns" : "queue")}
            >
              {returnsWorkbench.badgeCount ? "Review returned work" : "Review queue"}
              <ChevronRight size={16} />
            </button>
          </Panel>
          <Panel title="Conveyor state" icon={<Layers3 />}>
            <p className="large-state">
              {activitySnapshot.children.value === "unknown"
                ? "Current child count unavailable"
                : `${activitySnapshot.children.value} child agents active`}
            </p>
            <p>
              {activitySnapshot.returns.value} current returns ·{" "}
              {state.conveyorSummary ? Number(state.conveyorSummary.pending_support_request_count ?? 0) : "unknown"} support gates · Core growth{" "}
              {conveyorWorkbench.summary.coreGrowthState}
            </p>
            {activitySnapshot.children.detail ? <p className="muted">{activitySnapshot.children.detail}</p> : null}
            <button className="secondary-btn" onClick={() => setActiveTab("conveyor")}>
              Open workbench
              <ChevronRight size={16} />
            </button>
          </Panel>
          <Panel title="Directive progress" icon={<Gem />}>
            <p className="large-state">{formatKind(directive.deliverableKind)}</p>
            <p>
              {directive.materialDelta ? "Material directive delta recorded." : "Waiting for fresh material delta."}
            </p>
            <p className="muted">
              Focus {directive.focusId} · layer {directive.layerId}
            </p>
          </Panel>
        </section>
      ) : null}

      {activeTab === "queue" ? (
        <section className="queue-layout" data-testid="attention-queue">
          <QueueColumn
            title="Needs operator"
            items={queue.blockers}
            tone="danger"
            onSupportRequestDecision={decideSupportRequest}
            onExternalAdapterDisposition={dispositionExternalAdapterReview}
            onExternalAdapterDispositionAll={dispositionAllExternalAdapterReviews}
            onSeedableDispatchStart={startSeedableConveyorDispatch}
            supportActionDisabled={busyAction.startsWith("conveyor_support_")}
            externalAdapterActionDisabled={busyAction.startsWith("external_adapter_review_")}
            seedableDispatchActionDisabled={busyAction === "start_seedable_conveyor_dispatch"}
          />
          <QueueColumn title="Ready to continue" items={queue.resumable} tone="healthy" />
          <QueueColumn title="Informational" items={queue.informational} tone="neutral" />
          <Panel title="Review controls" icon={<Wand2 />}>
            <div className="action-row vertical">
              <button className="secondary-btn" onClick={() => runAction("review_board", () => reviewAutonomyBoard())}>
                Board review
              </button>
              <button
                className="secondary-btn"
                disabled={!operationId}
                onClick={() => runAction("approve_operation", () => approveAutonomyOperation(operationId))}
              >
                Approve latest op
              </button>
              <button
                className="secondary-btn"
                disabled={!firstReviewOption}
                onClick={() => runAction("review_action", () => executeReviewAction(firstReviewOption))}
              >
                Resolve first review item
              </button>
            </div>
          </Panel>
        </section>
      ) : null}

      {activeTab === "returns" ? (
        <section className="returns-workspace" data-testid="returns-workbench">
          <Panel title="Return inbox" icon={<BookOpen />}>
            <p className="large-state">
              {returnsWorkbench.badgeCount
                ? `${returnsWorkbench.badgeCount} review item${returnsWorkbench.badgeCount === 1 ? "" : "s"}`
                : "No returned work waiting"}
            </p>
            <div className="count-grid compact">
              <Metric label="Returns" value={String(returnsWorkbench.summary.pendingReturnCount)} />
              <Metric label="Support" value={String(returnsWorkbench.summary.pendingSupportCount)} />
              <Metric label="Accepted" value={String(returnsWorkbench.history.accepted)} />
              <Metric label="Requeued" value={String(returnsWorkbench.history.requeued)} />
            </div>
            {returnsWorkbench.supportGates.length ? (
              <div className="mission-return-list">
                {returnsWorkbench.supportGates.map((item) => (
                  <article className="mission-return-card support-required" key={text(item.supportRequestId)}>
                    <strong>{text(item.capabilityLabel, "Support request")}</strong>
                    <p className="muted">
                      {text(item.supportRequestId)} · {text(item.directiveId, "directive not recorded")}
                    </p>
                    <p>{text(item.reason, "Kernel support is waiting for review.")}</p>
                    <div className="action-row compact-actions">
                      <button
                        className="primary-btn"
                        disabled={busyAction.startsWith("conveyor_support_")}
                        onClick={() => decideSupportRequest(item.supportRequestId, "approve")}
                      >
                        <ShieldCheck size={16} />
                        Approve
                      </button>
                      <button
                        className="secondary-btn"
                        disabled={busyAction.startsWith("conveyor_support_")}
                        onClick={() => decideSupportRequest(item.supportRequestId, "satisfy")}
                      >
                        <BookOpen size={16} />
                        Use pack
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
            {conveyorQueue.length ? (
              <div className="mission-return-list">
                {conveyorQueue.map((packet) => {
                  const returnPacketId = text(packet.returnPacketId);
                  const isSelected = returnPacketId === selectedReturnPacketId;
                  return (
                    <article
                      className={isSelected ? "mission-return-card selected" : "mission-return-card"}
                      key={returnPacketId}
                    >
                      <label className="batch-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedReturnIds.includes(returnPacketId)}
                          onChange={() => toggleSelectedReturn(returnPacketId)}
                        />
                        Select
                      </label>
                      <button
                        className="unstyled-button return-selector"
                        onClick={() => {
                          setSelectedReturnId(returnPacketId);
                          setActiveArtifactTab("Summary");
                          setArtifactPreview(null);
                        }}
                      >
                        <strong>{text(packet.title, "Returned conveyor work")}</strong>
                        <span>{returnPacketId}</span>
                        <span>{text(packet.readinessLabel, "Needs review")}</span>
                      </button>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className="muted">
                {text(dispatchHealth.state) === "blocked_hard_review"
                  ? `Child dispatch is blocked by operator review. ${text(
                      dispatchHealth.recommended_action_id,
                      "Resolve the visible hard-review blocker before children can restart.",
                    )}`
                  : text(returnsWorkbench.emptyStateLabel, "No returned conveyor packets are waiting for operator review.")}
              </p>
            )}
          </Panel>

          <Panel title="Return evidence" icon={<Layers3 />}>
            {selectedReturnPacketId ? (
              <>
                <div className="section-heading compact">
                  <div>
                    <p className="large-state">{text(selectedReturn.title, "Returned conveyor work")}</p>
                    <p className="muted">
                      {selectedReturnPacketId} · {text(selectedReturn.childRunId, "child not recorded")} · generated{" "}
                      {text(selectedReturn.generatedAt, "time not recorded")}
                    </p>
                  </div>
                  <span className={selectedReturn.buildGradeReady ? "state-chip success" : "state-chip warning"}>
                    {text(selectedReturn.readinessLabel, "Needs review")}
                  </span>
                </div>
                <div className="artifact-tabs">
                  {asList(conveyorMission.artifactTabs).map((tab) => {
                    const tabName = text(tab);
                    return (
                      <button
                        key={tabName}
                        className={activeArtifactTab === tabName ? "secondary-btn active" : "secondary-btn"}
                        disabled={busyAction.startsWith("conveyor_artifact_")}
                        onClick={() => selectArtifactTab(tabName)}
                      >
                        {tabName}
                      </button>
                    );
                  })}
                </div>
                {activeArtifactTab === "Summary" ? (
                  <>
                    <p>{text(selectedReturn.outcomeSummary).slice(0, 900)}</p>
                    <dl className="detail-list compact">
                      <dt>Kernel decision</dt>
                      <dd>{formatKind(text(selectedGateSummary.decision, selectedReturn.campaignDecision, "not recorded"))}</dd>
                      <dt>Quality depth</dt>
                      <dd>{text(selectedReturn.qualityDepthLabel, "Quality depth not recorded")}</dd>
                      <dt>Execution gated</dt>
                      <dd>
                        {asList(selectedReturn.executionGatedArtifacts).length
                          ? asList(selectedReturn.executionGatedArtifacts).map((item) => text(item)).join(", ")
                          : text(selectedReturn.executionGatedLabel, "No execution-gated artifacts recorded")}
                      </dd>
                      <dt>Failed gates</dt>
                      <dd>
                        {asList(selectedGateSummary.failedGates).map((item) => text(item)).filter(Boolean).join(", ") ||
                          text(selectedReturn.missingBuildReadinessGateLabel, "No failed gates recorded")}
                      </dd>
                      <dt>Support packs</dt>
                      <dd>{asList(selectedGateSummary.supportPackRefs).map((item) => text(item)).filter(Boolean).join(", ") || "None recorded"}</dd>
                      <dt>Network</dt>
                      <dd>{text(selectedGateSummary.networkPolicy, selectedReturn.networkPolicy, "deny_all")}</dd>
                    </dl>
                    {asList(selectedReturn.canonicalArtifactRows).length ? (
                      <div className="artifact-table-wrap">
                        <table className="artifact-table">
                          <thead>
                            <tr>
                              <th>Canonical artifact</th>
                              <th>Summary</th>
                              <th>Version</th>
                              <th>Quality</th>
                              <th>Gate</th>
                              <th>Preview</th>
                            </tr>
                          </thead>
                          <tbody>
                            {asList(selectedReturn.canonicalArtifactRows).map((artifact) => {
                              const row = asRecord(artifact);
                              return (
                                <tr key={text(row.artifactName)}>
                                  <td>{text(row.artifactName)}</td>
                                  <td>{text(row.summary, "No summary available.")}</td>
                                  <td>{String(Number(row.version || 0))}</td>
                                  <td>{String(Number(row.qualityDepthScore || row.depthScore || 0))}</td>
                                  <td>{row.executionGated ? "Operator gated" : "Draftable"}</td>
                                  <td className="artifact-action-cell">
                                    <button
                                      className="secondary-btn"
                                      disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_artifact_")}
                                      onClick={() => openCanonicalArtifact(text(row.artifactName))}
                                    >
                                      <BookOpen size={14} />
                                      Preview
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                  </>
                ) : activeArtifactTab === "Raw" ? (
                  <pre className="artifact-preview">{JSON.stringify(selectedReturn, null, 2)}</pre>
                ) : artifactPreview && text(artifactPreview.return_packet_id) === selectedReturnPacketId ? (
                  artifactPreviewModel.viewKind === "table" ? (
                    <>
                      <p className="artifact-summary">{text(artifactPreviewModel.summary, "No summary available.")}</p>
                      <div className="artifact-table-wrap">
                        <table className="artifact-table">
                          <thead>
                            <tr>
                              {asList(artifactPreviewModel.columns).map((column) => (
                                <th key={text(column)}>{text(column)}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {asArray(artifactPreviewModel.rows).map((row, index) => (
                              <tr key={index}>
                                {asList(artifactPreviewModel.columns).map((column) => (
                                  <td key={text(column)}>{text(row[text(column)])}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <details className="artifact-json-details">
                        <summary>Raw JSON</summary>
                        <pre className="artifact-preview">{text(artifactPreviewModel.rawContent, "No content returned.")}</pre>
                      </details>
                    </>
                  ) : (
                    <>
                      <p className="artifact-summary">{text(artifactPreviewModel.summary, "No summary available.")}</p>
                      <pre className="artifact-preview">{text(artifactPreviewModel.rawContent, artifactPreview.message, "No content returned.")}</pre>
                    </>
                  )
                ) : (
                  <p className="muted">Select an artifact tab to load its preview.</p>
                )}
              </>
            ) : (
              <p className="muted">Select a returned directive to inspect gates and deliverables.</p>
            )}
          </Panel>

          <Panel title="Decision controls" icon={<Wand2 />}>
            <p>
              Add direction for the next child pass. Accept only when the returned package is final enough to close.
            </p>
            <textarea
              value={draftFeedback}
              onChange={(event) => setDraftFeedback(event.currentTarget.value)}
              placeholder="Target the exact unresolved artifact or gate, then ask for deeper build-grade evidence."
            />
            <div className="action-column">
              <button
                className="primary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "requeue", selectedReturn)}
              >
                <RefreshCw size={16} />
                {text(selectedReturn?.primaryAction?.label, "Request deeper pass")}
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnIds.length || busyAction.startsWith("conveyor_return_")}
                onClick={requestBatchDeeperPass}
              >
                <RefreshCw size={16} />
                Request deeper pass for selected ({selectedReturnIds.length})
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "clarify", selectedReturn)}
              >
                <Wand2 size={16} />
                Clarify + requeue
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "accept", selectedReturn)}
              >
                <ShieldCheck size={16} />
                Accept final
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "split", selectedReturn)}
              >
                <ChevronRight size={16} />
                Split
              </button>
              <button
                className="danger-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "reject", selectedReturn)}
              >
                <Square size={16} />
                Reject
              </button>
            </div>
          </Panel>
        </section>
      ) : null}

      {activeTab === "conveyor" ? (
        <section className="conveyor-mission-control" data-testid="conveyor-workbench">
          <Panel title="Directive queue" icon={<Layers3 />}>
            <p className="large-state">
              {activitySnapshot.countsAreCurrent
                ? `${activitySnapshot.children.value} child agents running · ${activitySnapshot.returns.value} returns awaiting review · ${activitySnapshot.queued.value} queued · Core growth ${conveyorWorkbench.summary.coreGrowthState}`
                : `Current conveyor counts unavailable · Core growth ${conveyorWorkbench.summary.coreGrowthState}`}
            </p>
            {activitySnapshot.staleDetail ? <p className="muted">{activitySnapshot.staleDetail}</p> : null}
            {formattedConveyorRefreshWarning ? (
              <p className="warning-text">
                {formattedConveyorRefreshWarning}
              </p>
            ) : (
              <p className="muted">
                Last refreshed {text(formattedConveyorLastRefreshedAt, "not yet")}.
              </p>
            )}
            {text(conveyorWorkbench.summary.dataWarning) ? (
              <p className="warning-text">{text(conveyorWorkbench.summary.dataWarning)}</p>
            ) : null}
            <div className="count-grid compact">
              <Metric label="Current running" value={activitySnapshot.children.value} />
              <Metric label="Current review" value={activitySnapshot.returns.value} />
              <Metric label="Current queued" value={activitySnapshot.queued.value} />
              <Metric
                label="Current support"
                value={state.conveyorSummary ? String(Number(state.conveyorSummary.pending_support_request_count ?? 0)) : "unknown"}
              />
            </div>
            <div className="operator-direction-box">
              <div className="section-heading compact">
                <strong>Continuous campaign</strong>
                <span className={conveyorWorkbench.summary.continuousCampaignEnabled ? "state-chip success" : "state-chip"}>
                  {conveyorWorkbench.summary.continuousCampaignEnabled ? "Enabled" : "Disabled"}
                </span>
              </div>
              <p className="muted">
                Auto-continuing {String(Number(conveyorWorkbench.summary.continuousAutoContinuing || 0))} directive(s) · depth cap{" "}
                {String(Number(conveyorWorkbench.summary.continuousDepthPassCap || 0))} · support cap{" "}
                {String(Number(conveyorWorkbench.summary.continuousSupportApprovalCap || 0))}
              </p>
              {Number(conveyorWorkbench.summary.continuousCapExhausted || 0) > 0 ||
              Number(conveyorWorkbench.summary.continuousNoProgressEscalated || 0) > 0 ? (
                <p className="warning-text">
                  Cap exhausted {String(Number(conveyorWorkbench.summary.continuousCapExhausted || 0))} · no-progress escalated{" "}
                  {String(Number(conveyorWorkbench.summary.continuousNoProgressEscalated || 0))}
                </p>
              ) : null}
            </div>
            <div className="operator-direction-box">
              <div className="section-heading compact">
                <strong>Overnight readiness</strong>
                <span className={conveyorWorkbench.summary.overnightReady ? "state-chip success" : "state-chip warning"}>
                  {text(conveyorWorkbench.summary.overnightReadyLabel, "Not overnight ready")}
                </span>
              </div>
              <p className="muted">
                Active {String(Number(conveyorWorkbench.summary.overnightActiveChildCount || 0))} /{" "}
                {String(Number(conveyorWorkbench.summary.overnightExpectedActiveChildCount || 2))} resident workers · support-gated{" "}
                {String(Number(conveyorWorkbench.summary.overnightSupportGatedReturnCount || 0))}
              </p>
              {asList(conveyorWorkbench.summary.overnightBlockers).length ? (
                <p className="warning-text">
                  Blockers: {asList(conveyorWorkbench.summary.overnightBlockers).map((item) => formatKind(text(item))).join(", ")}
                </p>
              ) : null}
              {asList(conveyorWorkbench.summary.overnightRecommendedActions).length ? (
                <p className="muted">
                  {asList(conveyorWorkbench.summary.overnightRecommendedActions).map((item) => text(item)).slice(0, 2).join(" ")}
                </p>
              ) : null}
            </div>
            {activeConveyorWorkers.length ? (
              <div className="mission-return-list">
                {activeConveyorWorkers.map((worker) => (
                  <article className="mission-return-card active-worker" key={text(worker.childRunId, worker.directiveId)}>
                    <div className="return-selector">
                      <strong>{text(worker.directiveId, "Active directive campaign")}</strong>
                      <span>{text(worker.childRunId, "child not recorded")}</span>
                      <span>{text(worker.currentFocus, "Working inside isolated directive workspace.")}</span>
                    </div>
                    <div className="chip-row">
                      <span className="state-chip success">{formatKind(text(worker.progressState, worker.state, "running"))}</span>
                      {text(worker.residentWorkerState) ? (
                        <span className="state-chip">{formatKind(text(worker.residentWorkerState))}</span>
                      ) : null}
                      <span className="state-chip">{formatKind(text(worker.executionMode, "resident campaign"))}</span>
                      <span className="state-chip">{text(worker.networkPolicy, "deny_all")}</span>
                      {text(worker.continuousCampaignLatestState) ? (
                        <span className="state-chip">{formatKind(text(worker.continuousCampaignLatestState))}</span>
                      ) : null}
                    </div>
                    {Number(worker.continuousCampaignDepthRemaining || 0) > 0 ||
                    Number(worker.continuousCampaignSupportRemaining || 0) > 0 ? (
                      <p className="muted">
                        Continuous caps remaining: depth {String(Number(worker.continuousCampaignDepthRemaining || 0))} · support{" "}
                        {String(Number(worker.continuousCampaignSupportRemaining || 0))}
                      </p>
                    ) : null}
                    {text(worker.targetArtifact, worker.latestArtifactDelta?.artifactName) ? (
                      <p className="muted">
                        Artifact target {text(worker.targetArtifact, worker.latestArtifactDelta?.artifactName)}
                        {text(worker.latestArtifactDelta?.deltaKind) ? ` · ${formatKind(text(worker.latestArtifactDelta?.deltaKind))}` : ""}
                      </p>
                    ) : null}
                    {text(worker.latestQualityTarget, worker.weakestFailedArtifact) ? (
                      <p className="muted">
                        Quality target {text(worker.latestQualityTarget, worker.weakestFailedArtifact)}
                        {text(worker.latestQualityRetargetReason) ? ` · ${formatKind(text(worker.latestQualityRetargetReason))}` : ""}
                      </p>
                    ) : null}
                    {Number(worker.qualityNoProgressCount || 0) > 0 || text(worker.lastQualityPromotionAt) ? (
                      <p className="muted">
                        Quality no-progress {String(Number(worker.qualityNoProgressCount || 0))}
                        {text(worker.lastQualityPromotionAt) ? ` · last promotion ${text(worker.lastQualityPromotionAt)}` : ""}
                      </p>
                    ) : null}
                    {Number(worker.consecutiveNoDeltaCycles || 0) > 0 || Number(worker.supportInjectionCount || 0) > 0 ? (
                      <p className="muted">
                        No-delta cycles {String(Number(worker.consecutiveNoDeltaCycles || 0))} · support injections{" "}
                        {String(Number(worker.supportInjectionCount || 0))}
                      </p>
                    ) : null}
                    {text(worker.progressAt) ? <p className="muted">Latest progress {text(worker.progressAt)}.</p> : null}
                    {text(worker.nextStepContext) ? <p className="muted">{text(worker.nextStepContext)}</p> : null}
                  </article>
                ))}
              </div>
            ) : null}
            {conveyorQueue.length ? (
              <div className="mission-return-list">
                {conveyorQueue.map((packet) => {
                  const returnPacketId = text(packet.returnPacketId);
                  const isSelected = returnPacketId === selectedReturnPacketId;
                  return (
                    <article
                      className={isSelected ? "mission-return-card selected" : "mission-return-card"}
                      key={returnPacketId}
                    >
                      <label className="batch-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedReturnIds.includes(returnPacketId)}
                          onChange={() => toggleSelectedReturn(returnPacketId)}
                        />
                        Select
                      </label>
                      <button
                        className="unstyled-button return-selector"
                        onClick={() => {
                          setSelectedReturnId(returnPacketId);
                          setActiveArtifactTab("Summary");
                          setArtifactPreview(null);
                        }}
                      >
                        <strong>{text(packet.title, "Returned conveyor work")}</strong>
                        <span>{returnPacketId}</span>
                        <span>{text(packet.childRunId, "child not recorded")}</span>
                      </button>
                      <div className="chip-row">
                        {asList(packet.statusChips).map((chip) => (
                          <span className="state-chip" key={text(chip)}>
                            {text(chip)}
                          </span>
                        ))}
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : text(conveyorWorkbench.summary.dataWarning) ? (
              <p className="warning-text">Returns are pending, but their packet details did not load yet.</p>
            ) : (
              <p className="muted">No returned conveyor packets are waiting for operator review.</p>
            )}
          </Panel>

          <Panel title="Return review" icon={<BookOpen />}>
            {selectedReturnPacketId ? (
              <>
                <div className="section-heading compact">
                  <div>
                    <p className="large-state">{text(selectedReturn.title, "Returned conveyor work")}</p>
                    <p className="muted">
                      {selectedReturnPacketId} · {text(selectedReturn.childRunId, "child not recorded")} · generated{" "}
                      {text(selectedReturn.generatedAt, "time not recorded")}
                    </p>
                  </div>
                  <span className={selectedReturn.buildGradeReady ? "state-chip success" : "state-chip warning"}>
                    {text(selectedReturn.readinessLabel, "Needs review")}
                  </span>
                </div>
                <div className="artifact-tabs">
                  {asList(conveyorMission.artifactTabs).map((tab) => {
                    const tabName = text(tab);
                    return (
                      <button
                        key={tabName}
                        className={activeArtifactTab === tabName ? "secondary-btn active" : "secondary-btn"}
                        disabled={busyAction.startsWith("conveyor_artifact_")}
                        onClick={() => selectArtifactTab(tabName)}
                      >
                        {tabName}
                      </button>
                    );
                  })}
                </div>
                {activeArtifactTab === "Summary" ? (
                  <>
                    <p>{text(selectedReturn.outcomeSummary).slice(0, 900)}</p>
                    <dl className="detail-list compact">
                      <dt>Kernel decision</dt>
                      <dd>{formatKind(text(selectedGateSummary.decision, selectedReturn.campaignDecision))}</dd>
                      <dt>Readiness</dt>
                      <dd>{formatKind(text(selectedGateSummary.readinessLevel, selectedReturn.campaignReadinessLevel))}</dd>
                      <dt>Campaign workspace</dt>
                      <dd>
                        {formatKind(text(selectedReturn.campaignWorkspaceState, "campaign ledger not initialized"))} ·{" "}
                        {text(selectedReturn.canonicalVersionLabel, "No canonical artifacts yet")}
                      </dd>
                      <dt>Quality depth</dt>
                      <dd>
                        {text(selectedReturn.qualityDepthLabel, "Quality depth not recorded")} ·{" "}
                        {text(selectedReturn.artifactPresenceLabel, "Artifact presence not recorded")}
                      </dd>
                      <dt>Quality gates</dt>
                      <dd>
                        {asList(selectedReturn.failedQualityGates).map((item) => formatKind(text(item))).filter(Boolean).join(", ") ||
                          "No failed quality gates recorded"}
                      </dd>
                      {text(selectedReturn.latestQualityRejectionReason) ? (
                        <>
                          <dt>Latest rejection</dt>
                          <dd>
                            {formatKind(text(selectedReturn.latestQualityRejectionReason))}
                            {text(selectedReturn.latestQualityRejectedArtifact)
                              ? ` · ${text(selectedReturn.latestQualityRejectedArtifact)}`
                              : ""}
                          </dd>
                        </>
                      ) : null}
                      <dt>Execution gated</dt>
                      <dd>
                        {asList(selectedReturn.executionGatedArtifacts).length
                          ? asList(selectedReturn.executionGatedArtifacts).map((item) => text(item)).join(", ")
                          : text(selectedReturn.executionGatedLabel, "No execution-gated artifacts recorded")}
                      </dd>
                      <dt>Failed gates</dt>
                      <dd>
                        {asList(selectedGateSummary.failedGates).map((item) => text(item)).filter(Boolean).join(", ") ||
                          text(selectedReturn.missingBuildReadinessGateLabel, "No failed gates recorded")}
                      </dd>
                      <dt>Blocked requirements</dt>
                      <dd>{asList(selectedGateSummary.blockedRequirements).map((item) => text(item)).filter(Boolean).join(", ") || "None recorded"}</dd>
                      <dt>Claims / Evidence / Novelty</dt>
                      <dd>
                        {String(selectedGateSummary.claimCount || 0)} claims · {String(selectedGateSummary.evidenceCount || 0)} evidence refs ·{" "}
                        {String(selectedGateSummary.noveltyCount || 0)} novelty items
                      </dd>
                      <dt>Support packs</dt>
                      <dd>{asList(selectedGateSummary.supportPackRefs).map((item) => text(item)).filter(Boolean).join(", ") || "None recorded"}</dd>
                      <dt>Network</dt>
                      <dd>{text(selectedGateSummary.networkPolicy, selectedReturn.networkPolicy, "deny_all")}</dd>
                      <dt>Risks</dt>
                      <dd>{asList(selectedGateSummary.risks).map((item) => text(item)).filter(Boolean).join(", ") || "None recorded"}</dd>
                      {text(selectedReturn.continuousCampaignLatestState) ? (
                        <>
                          <dt>Continuous campaign</dt>
                          <dd>
                            {formatKind(text(selectedReturn.continuousCampaignLatestState))} · depth remaining{" "}
                            {String(Number(selectedReturn.continuousCampaignDepthRemaining || 0))} · support remaining{" "}
                            {String(Number(selectedReturn.continuousCampaignSupportRemaining || 0))}
                            {text(selectedReturn.continuousCampaignLatestReason)
                              ? ` · ${formatKind(text(selectedReturn.continuousCampaignLatestReason))}`
                              : ""}
                          </dd>
                        </>
                      ) : null}
                    </dl>
                    {asList(selectedReturn.canonicalArtifactRows).length ? (
                      <div className="artifact-table-wrap">
                        <table className="artifact-table">
                          <thead>
                            <tr>
                              <th>Canonical artifact</th>
                              <th>Summary</th>
                              <th>Version</th>
                              <th>Quality</th>
                              <th>State</th>
                              <th>Gate</th>
                              <th>Preview</th>
                            </tr>
                          </thead>
                          <tbody>
                            {asList(selectedReturn.canonicalArtifactRows).map((artifact) => {
                              const row = asRecord(artifact);
                              return (
                                <tr key={text(row.artifactName)}>
                                  <td>{text(row.artifactName)}</td>
                                  <td>{text(row.summary, "No summary available.")}</td>
                                  <td>{String(Number(row.version || 0))}</td>
                                  <td>{String(Number(row.qualityDepthScore || row.depthScore || 0))}</td>
                                  <td>{formatKind(text(row.qualityState, "unknown"))}</td>
                                  <td>{row.executionGated ? "Operator gated" : "Draftable"}</td>
                                  <td className="artifact-action-cell">
                                    <button
                                      className="secondary-btn"
                                      disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_artifact_")}
                                      onClick={() => openCanonicalArtifact(text(row.artifactName))}
                                    >
                                      <BookOpen size={14} />
                                      Preview
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                    {text(selectedGateSummary.feedback, selectedReturn.kernelFeedback) ? (
                      <p className="muted">{text(selectedGateSummary.feedback, selectedReturn.kernelFeedback)}</p>
                    ) : null}
                    {selectedReturn.supportRequiredBeforeContinue ? (
                      <section className="operator-direction-box support-required" aria-label="Support required before continuing">
                        <div className="section-heading compact">
                          <strong>{text(selectedReturn.supportRequiredTitle, "Support required before continuing")}</strong>
                          <span className="state-chip warning">Support gate</span>
                        </div>
                        <dl className="detail-list compact">
                          <dt>Target artifact</dt>
                          <dd>{text(selectedReturn.targetArtifact, "artifact not recorded")}</dd>
                          {asList(selectedReturn.relatedPendingSupportRequests).map((request, index) => {
                            const support = asRecord(request);
                            return (
                              <Fragment key={`${text(support.support_request_id, "support")}-${index}`}>
                                <dt>Support request</dt>
                                <dd>
                                  {text(support.support_request_id, "support request")} · {formatKind(text(support.capability, "support"))} ·{" "}
                                  {text(support.reason, "Kernel-mediated support is pending.")}
                                </dd>
                              </Fragment>
                            );
                          })}
                        </dl>
                      </section>
                    ) : null}
                    {selectedReturn.directionNeeded ? (
                      <section className="operator-direction-box" aria-label="Novali needs direction">
                        <div className="section-heading compact">
                          <strong>Novali needs direction</strong>
                          <span className="state-chip warning">Blocks next pass</span>
                        </div>
                        <p className="muted">{text(selectedReturn.operatorDirectionPrompt)}</p>
                        <dl className="detail-list compact">
                          {asList(selectedReturn.directionItems).map((item, index) => {
                            const direction = asRecord(item);
                            const kind = text(direction.kind);
                            return (
                              <Fragment key={`${kind}-${index}`}>
                                <dt>{kind === "support_request" ? "Support" : "Question"}</dt>
                                <dd>
                                  {kind === "support_request"
                                    ? `${text(direction.supportRequestId, "support request")} · ${formatKind(
                                        text(direction.capability, "support"),
                                      )} · ${text(direction.reason, "kernel support pending")}`
                                    : `${text(direction.question, "Operator direction requested")} · ${text(
                                        direction.targetArtifact,
                                        "artifact not recorded",
                                      )}`}
                                </dd>
                              </Fragment>
                            );
                          })}
                        </dl>
                      </section>
                    ) : null}
                  </>
                ) : activeArtifactTab === "Raw" ? (
                  <pre className="artifact-preview">{JSON.stringify(selectedReturn, null, 2)}</pre>
                ) : artifactPreview && text(artifactPreview.return_packet_id) === selectedReturnPacketId ? (
                  <>
                    <dl className="detail-list compact">
                      <dt>Artifact</dt>
                      <dd>{text(artifactPreview.artifact_name, "not selected")}</dd>
                      <dt>Encoding</dt>
                      <dd>{text(artifactPreview.encoding, "unknown")}</dd>
                    </dl>
                    {artifactPreviewModel.viewKind === "table" ? (
                      <>
                        <p className="artifact-summary">{text(artifactPreviewModel.summary, "No summary available.")}</p>
                        <div className="artifact-table-wrap">
                          <table className="artifact-table">
                            <thead>
                              <tr>
                                {asList(artifactPreviewModel.columns).map((column) => (
                                  <th key={text(column)}>{text(column)}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {asArray(artifactPreviewModel.rows).map((row, index) => (
                                <tr key={index}>
                                  {asList(artifactPreviewModel.columns).map((column) => (
                                    <td key={text(column)}>{text(row[text(column)])}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <details className="artifact-json-details">
                          <summary>Raw JSON</summary>
                          <pre className="artifact-preview">{text(artifactPreviewModel.rawContent, "No content returned.")}</pre>
                        </details>
                      </>
                    ) : (
                      <>
                        <p className="artifact-summary">{text(artifactPreviewModel.summary, "No summary available.")}</p>
                        <pre className="artifact-preview">{text(artifactPreviewModel.rawContent, artifactPreview.message, "No content returned.")}</pre>
                      </>
                    )}
                  </>
                ) : (
                  <p className="muted">Select an artifact tab to load its preview.</p>
                )}
              </>
            ) : (
              <p className="muted">Select a returned directive to inspect gates and deliverables.</p>
            )}
          </Panel>

          <Panel title="Decision panel" icon={<Wand2 />}>
            <p>
              Add direction for the next child pass. Unless you explicitly accept final deliverables, Novali will
              continue pushing the directive toward build-grade technical depth.
            </p>
            {selectedReturn?.directionNeeded ? (
              <p className="warning-text">
                Typed direction will answer the visible blocker(s), clean up matching stale support requests, and send
                the directive back to the conveyor.
              </p>
            ) : null}
            <textarea
              value={draftFeedback}
              onChange={(event) => setDraftFeedback(event.currentTarget.value)}
              placeholder="Example: deepen both directives toward prototype-grade technical documentation; expand subsystem interfaces, validation protocols, dependency matrices, and evidence-backed claims."
            />
            <div className="action-column">
              <button
                className="primary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "requeue", selectedReturn)}
              >
                <RefreshCw size={16} />
                {text(selectedReturn?.primaryAction?.label, "Request deeper pass")}
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnIds.length || busyAction.startsWith("conveyor_return_")}
                onClick={requestBatchDeeperPass}
              >
                <RefreshCw size={16} />
                Request deeper pass for selected ({selectedReturnIds.length})
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "clarify", selectedReturn)}
              >
                <Wand2 size={16} />
                Clarify + requeue
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "accept", selectedReturn)}
              >
                <ShieldCheck size={16} />
                Accept final
              </button>
              <button
                className="secondary-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "split", selectedReturn)}
              >
                <ChevronRight size={16} />
                Split
              </button>
              <button
                className="danger-btn"
                disabled={!selectedReturnPacketId || busyAction.startsWith("conveyor_return_")}
                onClick={() => decideReturnedWork(selectedReturnPacketId, "reject", selectedReturn)}
              >
                <Square size={16} />
                Reject
              </button>
            </div>
            <div className="mission-growth-box">
              <div className="section-heading compact">
                <strong>Core growth lane</strong>
                <span className="state-chip">{formatKind(conveyorWorkbench.coreGrowth.state)}</span>
              </div>
              <dl className="detail-list compact">
                <dt>Built-in directive</dt>
                <dd>{conveyorWorkbench.coreGrowth.builtInDirectiveTitle}</dd>
                <dt>Objective</dt>
                <dd>{conveyorWorkbench.coreGrowth.objective}</dd>
                <dt>Next action</dt>
                <dd>{conveyorWorkbench.coreGrowth.nextAction}</dd>
              </dl>
              <div className="action-row compact-actions">
                <button
                  className="secondary-btn"
                  disabled={conveyorWorkbench.coreGrowth.primaryAction.enabled === false}
                  onClick={() =>
                    runAction(text(conveyorWorkbench.coreGrowth.primaryAction.id, "start_governed"), () =>
                      text(conveyorWorkbench.coreGrowth.primaryAction.id) === "continue"
                        ? continueLongRun()
                        : text(conveyorWorkbench.coreGrowth.primaryAction.id) === "start_autonomy"
                          ? startAutonomy()
                          : startGoverned({}),
                    )
                  }
                >
                  <Play size={16} />
                  {text(conveyorWorkbench.coreGrowth.primaryAction.label, "Run growth lane")}
                </button>
                <button className="secondary-btn" onClick={() => runAction("pause_autonomy", () => pauseAutonomy())}>
                  <CirclePause size={16} />
                  Pause
                </button>
              </div>
            </div>
          </Panel>
        </section>
      ) : null}

      {activeTab === "growth" ? (
        <section className="dashboard-grid wide framework-growth" data-testid="framework-growth">
          <Panel title="Framework growth lane" icon={<Sparkles />}>
            <div className="growth-hero">
              <div className={conveyorWorkbench.coreGrowth.active ? "score-ring active live-pulse" : "score-ring"}>
                {formatKind(conveyorWorkbench.coreGrowth.state)}
              </div>
              <div>
                <p className="large-state">{conveyorWorkbench.coreGrowth.builtInDirectiveTitle}</p>
                <p>{conveyorWorkbench.coreGrowth.builtInDirectiveSummary}</p>
              </div>
            </div>
            <dl className="detail-list">
              <dt>Active objective</dt>
              <dd>{conveyorWorkbench.coreGrowth.objective}</dd>
              <dt>Next maturity action</dt>
              <dd>{text(conveyorWorkbench.coreGrowth.nextAction, runtime.nextMaturityAction)}</dd>
              <dt>Growth policy</dt>
              <dd>{formatKind(conveyorWorkbench.coreGrowth.growthPolicyState)}</dd>
              <dt>Long-run state</dt>
              <dd>{formatKind(conveyorWorkbench.coreGrowth.executionState)}</dd>
              <dt>Human gate</dt>
              <dd>{text(conveyorWorkbench.coreGrowth.latestHumanGate, "none recorded")}</dd>
            </dl>
            <div className="action-row">
              <button
                className="primary-btn"
                disabled={conveyorWorkbench.coreGrowth.primaryAction.enabled === false}
                onClick={() =>
                  runAction(text(conveyorWorkbench.coreGrowth.primaryAction.id, "start_autonomy"), () =>
                    text(conveyorWorkbench.coreGrowth.primaryAction.id) === "continue"
                      ? continueLongRun()
                      : startAutonomy(),
                  )
                }
              >
                <Play size={16} />
                {text(conveyorWorkbench.coreGrowth.primaryAction.label, "Run growth lane")}
              </button>
              <button className="secondary-btn" onClick={() => setActiveTab("returns")}>
                <BookOpen size={16} />
                Review returns
              </button>
            </div>
          </Panel>
          <Panel title="Capability maturity" icon={<BrainCircuit />}>
            <p className="large-state">{formatKind(runtime.maturityBand)}</p>
            <div className="count-grid compact">
              <Metric label="Criticality" value={String(runtime.criticalityScore)} />
              <Metric label="Complexity" value={String(runtime.c1Complexity)} />
              <Metric label="Self model" value={String(runtime.c2SelfModel)} />
              <Metric label="Observer" value={String(runtime.c3ObserverStability)} />
            </div>
            <dl className="detail-list compact">
              <dt>Strict consumption</dt>
              <dd>{runtime.strictConsumptionGatePassed ? "passed" : "blocked"}</dd>
              <dt>Gate reason</dt>
              <dd>{runtime.strictConsumptionGateReason}</dd>
              <dt>Dominance</dt>
              <dd>{formatKind(runtime.continuationDominanceState)}</dd>
              <dt>Ungrounded continuations</dt>
              <dd>
                {runtime.governedContinuationsWithoutStrictUsefulness} / {runtime.continuationDominanceThreshold}
              </dd>
            </dl>
          </Panel>
          <Panel title="Consumed and changed" icon={<Gem />}>
            <p className="large-state">{directive.meaningfulCreditLabel}</p>
            <dl className="detail-list compact">
              <dt>Score</dt>
              <dd>{Math.round(directive.score * 100)}%</dd>
              <dt>Concrete artifact</dt>
              <dd>{directive.deliverableArtifactMaterialDelta ? "material delta" : "not material"}</dd>
              <dt>Dossier delta</dt>
              <dd>{directive.dossierMaterialDelta ? "material" : "not material"}</dd>
              <dt>Track credit</dt>
              <dd>{directive.deltaCredited ? "credited" : "not credited"}</dd>
              <dt>Source coverage</dt>
              <dd>{directive.sourceCoverageState}</dd>
              <dt>Evidence quality</dt>
              <dd>{directive.packSummaryQuality}</dd>
              <dt>Next artifact</dt>
              <dd>{directive.nextConcreteArtifact || "not recorded"}</dd>
              <dt>Promotion packet</dt>
              <dd>{directive.promotionState}</dd>
            </dl>
          </Panel>
          <Panel title="Directive evidence detail" icon={<Layers3 />}>
            <p className="large-state">{formatKind(directive.deliverableKind)}</p>
            <dl className="detail-list">
              <dt>Loaded directive</dt>
              <dd>{directive.directiveTitle}</dd>
              <dt>Execution gate</dt>
              <dd>{directive.executionGate}</dd>
              <dt>Maturity</dt>
              <dd>
                {formatKind(directive.deliverableMaturityState)}
                {" -> "}
                {formatKind(directive.deliverableNextMaturityState)}
              </dd>
              <dt>Focus</dt>
              <dd>{directive.focusId}</dd>
              <dt>Layer</dt>
              <dd>{directive.layerId}</dd>
              <dt>Artifact</dt>
              <dd>{directive.deliverableArtifactPath || directive.artifactPath || "not recorded"}</dd>
              <dt>Missing density</dt>
              <dd>
                {directive.artifactMissingDensityRequirements.length
                  ? directive.artifactMissingDensityRequirements.map(formatKind).join(", ")
                  : "none"}
              </dd>
              <dt>Capability gates</dt>
              <dd>
                {Object.entries(directive.capabilityQualityGateResults)
                  .map(([name, value]) => `${formatKind(name)}=${formatKind(String(value))}`)
                  .join(", ") || "not recorded"}
              </dd>
            </dl>
          </Panel>
        </section>
      ) : null}

      {activeTab === "runtime" ? (
        <section className="dashboard-grid wide" data-testid="autonomy-runtime">
          <Panel title="Autonomy kernel" icon={<BrainCircuit />}>
            <dl className="detail-list">
              <dt>Runtime</dt>
              <dd>{runtime.runtimeState}</dd>
              <dt>Loop</dt>
              <dd>{runtime.loopIteration}</dd>
              <dt>Latest action</dt>
              <dd>{formatKind(runtime.latestAction)}</dd>
              <dt>Latest result</dt>
              <dd>{runtime.latestResult}</dd>
              <dt>Duration</dt>
              <dd>{runtime.latestDurationMs ? `${Math.round(runtime.latestDurationMs)} ms` : "not recorded"}</dd>
              <dt>Board</dt>
              <dd>{runtime.boardState}</dd>
              <dt>High impact</dt>
              <dd>{runtime.highImpactState}</dd>
              <dt>Churn</dt>
              <dd>
                {runtime.churnState}
                {runtime.churnBreaker ? " · breaker active" : ""}
              </dd>
              <dt>Trusted triage</dt>
              <dd>{runtime.trustedTriageState}</dd>
            </dl>
            <div className="action-row">
              <button className="secondary-btn" onClick={() => runAction("start_autonomy", () => startAutonomy())}>
                Start loop
              </button>
              <button className="secondary-btn" onClick={() => runAction("pause_autonomy", () => pauseAutonomy())}>
                Pause
              </button>
            </div>
          </Panel>
          <Panel title="Memory and telemetry" icon={<ShieldCheck />}>
            <dl className="detail-list">
              <dt>Memory</dt>
              <dd>
                {runtime.memoryPercent}% · {runtime.memoryPressure}
              </dd>
              <dt>Smoothing</dt>
              <dd>{runtime.memorySmoothing}</dd>
              <dt>Spill</dt>
              <dd>
                {runtime.spillMode} · {runtime.spillActivityState}
              </dd>
              <dt>Next spill</dt>
              <dd>{runtime.nextSpillDueAt}</dd>
              <dt>Volume use</dt>
              <dd>
                {formatBytes(runtime.spillVolumeBytes)} · {runtime.spillPointerCount} pointers
              </dd>
              <dt>Moved cold data</dt>
              <dd>
                logs {formatBytes(runtime.runtimeLogSpillBytes)} ({runtime.runtimeLogSegmentCount} segments) · bundles{" "}
                {formatBytes(runtime.runtimeLogBundleBytes)} ({runtime.runtimeLogBundleCount} bundles) · artifacts{" "}
                {formatBytes(runtime.coldArtifactSpillBytes)}
              </dd>
              <dt>Small-log backlog</dt>
              <dd>
                {runtime.runtimeLogSmallFileBacklogCount} · {runtime.runtimeLogBundleLatestResult}
              </dd>
              <dt>Active log tail</dt>
              <dd>{formatBytes(runtime.runtimeLogActiveTailBytes)}</dd>
              <dt>Spill backlog</dt>
              <dd>
                {runtime.spillBacklogCount} · {formatBytes(runtime.coldArtifactBacklogBytes)}
              </dd>
              <dt>Spill budget</dt>
              <dd>
                {formatBytes(runtime.spillBudgetUsedBytes)} / {formatBytes(runtime.spillBudgetBytes)}
              </dd>
              <dt>Data at rest</dt>
              <dd>
                {runtime.ledgerIndexState} · {runtime.dataAtRestCatalogState}
              </dd>
              <dt>Librarian</dt>
              <dd>
                {runtime.librarianState} · {runtime.librarianReusableCount}/{runtime.librarianPackCount} reusable
              </dd>
              <dt>OOM guard</dt>
              <dd>{runtime.oomGuard}</dd>
              <dt>OTEL</dt>
              <dd>
                {runtime.otelStatus} · {runtime.refreshState}
              </dd>
            </dl>
          </Panel>
          <Panel title="Loaded goals" icon={<Gem />}>
            <p className="muted">
              Goals and diagnostics are intentionally summarized here so the first viewport stays operator-useful.
            </p>
            <pre>{JSON.stringify(state.autonomyGoals ?? {}, null, 2).slice(0, 900)}</pre>
          </Panel>
        </section>
      ) : null}

      {activeTab === "librarian" ? (
        <section className="dashboard-grid wide" data-testid="librarian-work">
          <Panel title="Pack library" icon={<BookOpen />}>
            <div className="count-grid">
              <Metric label="State" value={text(librarianStatus.librarian_state, "unknown")} />
              <Metric label="Packs" value={text(librarianStatus.librarian_pack_count, "0")} />
              <Metric label="Reusable" value={text(librarianStatus.librarian_reusable_count, "0")} />
            </div>
            <dl className="detail-list">
              <dt>Index age</dt>
              <dd>{Math.round(Number(librarianStatus.librarian_index_age_seconds || 0))}s</dd>
              <dt>Latest action</dt>
              <dd>{text(librarianStatus.latest_librarian_action, "not recorded")}</dd>
              <dt>Latest blocker</dt>
              <dd>{text(librarianStatus.latest_librarian_blocker, "none")}</dd>
            </dl>
          </Panel>
          <Panel title="Search reusable packs" icon={<Search />}>
            <div className="search-row">
              <input
                value={librarianQuery}
                onChange={(event) => setLibrarianQuery(event.currentTarget.value)}
                placeholder="Search pack family, tag, directive, capability"
                aria-label="Search Librarian packs"
              />
              <button
                className="secondary-btn"
                disabled={busyAction === "librarian_search"}
                onClick={searchLibrarian}
              >
                <Search size={16} />
                Search
              </button>
            </div>
            <p className="muted">
              Results are metadata-only refs stored on the Novali spill volume. Packs do not grant execution authority.
            </p>
          </Panel>
          <Panel title="Reusable pack refs" icon={<Layers3 />}>
            <div className="pack-list">
              {librarianResults.length ? (
                librarianResults.map((pack) => (
                  <article className="pack-card" key={text(pack.pack_id, pack.version_ref, pack.family)}>
                    <div>
                      <strong className="pack-title">{text(pack.family, pack.pack_id, "Unnamed pack")}</strong>
                      <p className="muted pack-ref">{text(pack.pack_id, "no pack id")}</p>
                    </div>
                    <dl className="detail-list compact">
                      <dt>Kind</dt>
                      <dd>{formatKind(pack.kind)}</dd>
                      <dt>Quality</dt>
                      <dd>{text(pack.quality_state, "unknown")}</dd>
                      <dt>Reuse</dt>
                      <dd>{text(pack.reuse_state, "unknown")}</dd>
                      <dt>Source</dt>
                      <dd>{text(pack.source_kind, "unknown")}</dd>
                      <dt>Artifact</dt>
                      <dd>{text(pack.source_artifact_relative_path, "volume ref")}</dd>
                    </dl>
                  </article>
                ))
              ) : (
                <p className="muted">No reusable pack refs found in the current Librarian catalog.</p>
              )}
            </div>
          </Panel>
        </section>
      ) : null}

      {activeTab === "settings" ? (
        <section className="dashboard-grid wide" data-testid="trusted-source-settings">
          <Panel title="Framework time" icon={<RefreshCw />}>
            <div className="count-grid">
              <Metric label="Time" value={text(frameworkClock.timeLabel, "--:--:--")} />
              <Metric label="Date" value={text(frameworkClock.dateLabel, "unknown")} />
              <Metric label="Zone" value={text(frameworkClock.timezoneLabel, frameworkClock.timezone, "unknown")} />
            </div>
            <div className="form-grid">
              <label>
                Framework timezone
                <select
                  value={frameworkTimezoneDraft || text(operatorSettings.framework_timezone, "America/Chicago")}
                  onChange={(event) => setFrameworkTimezoneDraft(event.currentTarget.value)}
                >
                  {supportedTimezones.map((timezone) => (
                    <option value={timezone} key={timezone}>
                      {timezone}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <dl className="detail-list">
              <dt>Settings file</dt>
              <dd>{text(operatorSettings.settings_path, "not recorded")}</dd>
              <dt>Last generated</dt>
              <dd>{text(operatorSettings.generated_at, "not recorded")}</dd>
            </dl>
            <div className="action-row">
              <button
                className="primary-btn"
                disabled={
                  busyAction === "save_framework_timezone" ||
                  text(frameworkTimezoneDraft, operatorSettings.framework_timezone) ===
                    text(operatorSettings.framework_timezone)
                }
                onClick={saveFrameworkTimezone}
              >
                <Settings size={16} />
                Save timezone
              </button>
            </div>
          </Panel>

          <Panel title="Trusted sources" icon={<ShieldCheck />}>
            <div className="count-grid">
              <Metric
                label="Ready"
                value={text(asRecord(trustedSourceSettings.availability_summary).ready_count, "0")}
              />
              <Metric
                label="Enabled"
                value={text(asRecord(trustedSourceSettings.availability_summary).enabled_count, "0")}
              />
              <Metric
                label="Issues"
                value={String((state.trustedSourceSettings?.validation_errors ?? []).length)}
              />
            </div>
            <dl className="detail-list">
              <dt>Bindings</dt>
              <dd>{text(trustedSourceSettings.bindings_path, "not recorded")}</dd>
              <dt>Validation</dt>
              <dd>
                {(state.trustedSourceSettings?.validation_errors ?? []).length
                  ? state.trustedSourceSettings?.validation_errors?.join("; ")
                  : "clean"}
              </dd>
            </dl>
          </Panel>

          <Panel title="Add source" icon={<Settings />}>
            <div className="form-grid">
              <label>
                Source id
                <input
                  value={trustedSourceDraft.source_id}
                  onChange={(event) => updateTrustedSourceDraft("source_id", event.currentTarget.value)}
                  placeholder="mcp:research"
                />
              </label>
              <label>
                Kind
                <select
                  value={trustedSourceDraft.source_kind}
                  onChange={(event) => updateTrustedSourceDraft("source_kind", event.currentTarget.value)}
                >
                  {trustedSourceKinds.map((kind) => (
                    <option value={kind} key={kind}>
                      {formatKind(kind)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Endpoint or path
                <input
                  value={trustedSourceDraft.endpoint_base}
                  onChange={(event) => updateTrustedSourceDraft("endpoint_base", event.currentTarget.value)}
                  placeholder="stdio://research-mcp"
                />
              </label>
              <label>
                Credential
                <select
                  value={trustedSourceDraft.credential_strategy}
                  onChange={(event) => updateTrustedSourceDraft("credential_strategy", event.currentTarget.value)}
                >
                  {trustedCredentialStrategies.map((strategy) => (
                    <option value={strategy} key={strategy}>
                      {formatKind(strategy)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Credential ref
                <input
                  value={trustedSourceDraft.credential_ref}
                  onChange={(event) => updateTrustedSourceDraft("credential_ref", event.currentTarget.value)}
                  placeholder="OPENAI_API_KEY"
                />
              </label>
              <label>
                Capability tags
                <input
                  value={trustedSourceDraft.capability_tags}
                  onChange={(event) => updateTrustedSourceDraft("capability_tags", event.currentTarget.value)}
                  placeholder="research, sim"
                />
              </label>
              <label>
                Queue ids
                <input
                  value={trustedSourceDraft.allowed_directive_queue_ids}
                  onChange={(event) =>
                    updateTrustedSourceDraft("allowed_directive_queue_ids", event.currentTarget.value)
                  }
                  placeholder="full-dive"
                />
              </label>
              <label>
                Request cap
                <input
                  type="number"
                  min="0"
                  value={trustedSourceDraft.max_requests_per_directive}
                  onChange={(event) =>
                    updateTrustedSourceDraft("max_requests_per_directive", event.currentTarget.value)
                  }
                />
              </label>
            </div>
            <div className="action-row">
              <label className="inline-toggle">
                <input
                  type="checkbox"
                  checked={trustedSourceDraft.enabled}
                  onChange={(event) => updateTrustedSourceDraft("enabled", event.currentTarget.checked)}
                />
                Enabled
              </label>
              <label className="inline-toggle">
                <input
                  type="checkbox"
                  checked={trustedSourceDraft.requires_operator_review}
                  onChange={(event) =>
                    updateTrustedSourceDraft("requires_operator_review", event.currentTarget.checked)
                  }
                />
                Review
              </label>
              <button
                className="primary-btn"
                disabled={busyAction === "save_trusted_source"}
                onClick={saveTrustedSourceDraft}
              >
                <ShieldCheck size={16} />
                Save source
              </button>
            </div>
          </Panel>

          <Panel title="Configured sources" icon={<Layers3 />}>
            <div className="pack-list">
              {trustedSources.length ? (
                trustedSources.map((source) => {
                  const sourceId = text(source.source_id, "unknown");
                  const tags = Array.isArray(source.capability_tags)
                    ? source.capability_tags.map(String).join(", ")
                    : text(source.capability_tags);
                  const queues = Array.isArray(source.allowed_directive_queue_ids)
                    ? source.allowed_directive_queue_ids.map(String).join(", ")
                    : text(source.allowed_directive_queue_ids);
                  return (
                    <article className="pack-card" key={sourceId}>
                      <div>
                        <strong className="pack-title">{sourceId}</strong>
                        <p className="muted pack-ref">
                          {formatKind(source.source_kind)} · {formatKind(source.availability_class)}
                        </p>
                      </div>
                      <dl className="detail-list compact">
                        <dt>Enabled</dt>
                        <dd>{source.enabled ? "yes" : "no"}</dd>
                        <dt>Ready</dt>
                        <dd>{source.ready_for_launch ? "yes" : "no"}</dd>
                        <dt>Credential</dt>
                        <dd>{source.credential_present ? "present" : formatKind(source.credential_strategy)}</dd>
                        <dt>Endpoint</dt>
                        <dd>{text(source.endpoint_base, source.path_hint, "not configured")}</dd>
                        <dt>Tags</dt>
                        <dd>{tags || "none"}</dd>
                        <dt>Queues</dt>
                        <dd>{queues || "all"}</dd>
                        <dt>Request cap</dt>
                        <dd>{text(source.max_requests_per_directive, "0")}</dd>
                        <dt>Review</dt>
                        <dd>{source.requires_operator_review ? "required" : "standard"}</dd>
                      </dl>
                      <div className="action-row">
                        <button
                          className="secondary-btn"
                          disabled={busyAction === "validate_trusted_source"}
                          onClick={() => validateTrustedSourceRow(sourceId)}
                        >
                          Validate
                        </button>
                        <button
                          className="secondary-btn"
                          disabled={busyAction === "toggle_trusted_source"}
                          onClick={() => toggleTrustedSource(sourceId, !source.enabled)}
                        >
                          {source.enabled ? "Disable" : "Enable"}
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <p className="muted">No trusted sources are configured.</p>
              )}
            </div>
          </Panel>
        </section>
      ) : null}

        </div>
      </div>

      <aside
        className={askOpen ? "ask-drawer open" : "ask-drawer"}
        data-testid="ask-novali-panel"
        {...askDrawerAccessibilityProps(askOpen)}
      >
        <div className="drawer-header">
          <div>
            <p className="eyebrow">Assistant side panel</p>
            <h2>Ask Novali</h2>
          </div>
          <button className="icon-btn" onClick={() => setAskOpen(false)}>
            <Square size={16} />
            Close
          </button>
        </div>
        <p className="muted">
          Drafts stay review-gated here. Approval queues the selected draft into the conveyor; child execution remains
          bounded by scheduler policy.
        </p>
        <div className="status-pill">
          {text(asRecord(state.llmStatus).provider, "ollama")} · {text(asRecord(state.llmStatus).status, "unknown")} ·{" "}
          {text(asRecord(state.llmStatus).model, "qwen3.6:35b-a3b")} ·{" "}
          {text(asRecord(state.llmStatus).model_family, text(asRecord(state.llmStatus).provider_role, "local"))}
        </div>
        <label>
          Mode
          <select value={llmMode} onChange={(event) => setLlmMode(event.currentTarget.value as LLMMode)}>
            <option value="explain_state">Explain state</option>
            <option value="draft_directive">Draft directive</option>
            <option value="draft_plan">Draft plan</option>
          </select>
        </label>
        <label>
          Prompt
          <textarea value={llmPrompt} onChange={(event) => setLlmPrompt(event.currentTarget.value)} />
        </label>
        <button className="primary-btn" onClick={askNovali} disabled={busyAction === "ask_novali"}>
          <Bot size={16} />
          Ask Novali
        </button>
        {busyAction === "ask_novali" || latestLLMProgress.active ? (
          <div className="llm-progress-panel" aria-live="polite">
            <div className="llm-progress-header">
              <span>{text(latestLLMProgress.phaseLabel, "Starting")}</span>
              <span>{Math.round(Number(latestLLMProgress.percent || 0))}%</span>
            </div>
            <div
              className="llm-progress-track"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(Number(latestLLMProgress.percent || 0))}
              aria-label="Ask Novali request progress"
            >
              <span style={{ width: `${Math.round(Number(latestLLMProgress.percent || 0))}%` }} />
            </div>
            <p className="muted">
              {text(latestLLMProgress.detail, "Novali is waiting for the local model.")}
            </p>
          </div>
        ) : null}
        {latestDraftAttemptIsNewer ? (
          <p className="draft-warning">
            Latest draft attempt ({text(latestDirectiveDraftAttempt.status, "unknown")}):{" "}
            {text(latestDirectiveDraftAttempt.attempt_summary, "No response stored yet.").slice(0, 220)}
          </p>
        ) : null}
        {text(latestDirectiveDraft.directive_text) ? (
          <section className="draft-review-panel" aria-label="Directive draft review">
            <div className="panel-title compact">
              <span aria-hidden="true">
                <Wand2 size={16} />
              </span>
              <h3>Directive Draft Preview</h3>
            </div>
            <p className="muted">Source record: {text(latestDirectiveDraft.record_id, "latest draft")}</p>
            {!latestDirectiveDraftCompleteness.complete ? (
              <p className="draft-warning">
                Draft needs revision before conveyor approval: {latestDirectiveDraftCompleteness.reasons.join(", ")}
              </p>
            ) : null}
            <pre className="draft-preview">{text(latestDirectiveDraft.directive_text).slice(0, 2400)}</pre>
            <label>
              Recommend changes
              <textarea
                value={draftFeedback}
                onChange={(event) => setDraftFeedback(event.currentTarget.value)}
                placeholder="Describe what Novali should change before conveyor approval."
              />
            </label>
            <div className="action-row">
              <button
                className="secondary-btn"
                onClick={reviseDirectiveDraft}
                disabled={busyAction === "revise_directive_draft"}
              >
                <RefreshCw size={16} />
                Revise draft
              </button>
              <button
                className="primary-btn"
                onClick={approveDirectiveDraftForConveyor}
                disabled={busyAction === "approve_draft_for_conveyor" || !latestDirectiveDraftCompleteness.complete}
              >
                <ChevronRight size={16} />
                Approve for conveyor
              </button>
            </div>
          </section>
        ) : (
          <p className="muted">Choose Draft directive, ask Novali, then review the generated draft here.</p>
        )}
        <section className="return-review-panel" aria-label="Returned conveyor work shortcut">
          <div className="panel-title compact">
            <span aria-hidden="true">
              <Layers3 size={16} />
            </span>
            <h3>Returned Work</h3>
          </div>
          <p className="muted">
            {returnsWorkbench.badgeCount
              ? `${returnsWorkbench.badgeCount} returned work item${returnsWorkbench.badgeCount === 1 ? "" : "s"} need review in the Returns workbench.`
              : "No returned conveyor packets are waiting for operator review."}
          </p>
          <button
            className={returnsWorkbench.badgeCount ? "primary-btn" : "secondary-btn"}
            onClick={() => {
              setAskOpen(false);
              setActiveTab("returns");
            }}
          >
            <BookOpen size={16} />
            Open Returns
          </button>
        </section>
        <div className="drawer-history">
          {asArray(asRecord(state.llmHistory).records).slice(0, 4).map((record) => (
            <article key={text(record.id, record.created_at, record.prompt)}>
              <strong>{text(record.mode, "chat")}</strong>
              <p>
                {text(
                  record.assistant_response_redacted,
                  record.response_preview,
                  record.response,
                  record.error,
                  "No response stored.",
                ).slice(0, 220)}
              </p>
            </article>
          ))}
          {asArray(asRecord(state.llmPending).records).length ? (
            <p className="muted">
              Pending directive candidates: {asArray(asRecord(state.llmPending).records).length}
            </p>
          ) : null}
        </div>
      </aside>
    </main>
  );
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="arcane-panel">
      <div className="panel-title">
        <span aria-hidden="true">{icon}</span>
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function QueueColumn({
  title,
  items,
  tone,
  onSupportRequestDecision,
  onExternalAdapterDisposition,
  onExternalAdapterDispositionAll,
  onSeedableDispatchStart,
  supportActionDisabled = false,
  externalAdapterActionDisabled = false,
  seedableDispatchActionDisabled = false,
}: {
  title: string;
  items: ReturnType<typeof buildAttentionQueue>["blockers"];
  tone: "danger" | "healthy" | "neutral";
  onSupportRequestDecision?: (supportRequestId: string, action: "approve" | "reject" | "satisfy") => void;
  onExternalAdapterDisposition?: (reviewItemId: string, dispositionActionId: string) => void;
  onExternalAdapterDispositionAll?: () => void;
  onSeedableDispatchStart?: () => void;
  supportActionDisabled?: boolean;
  externalAdapterActionDisabled?: boolean;
  seedableDispatchActionDisabled?: boolean;
}) {
  const adapterBlockers = items
    .map((item) => asRecord(item.raw))
    .filter(
      (raw) =>
        text(raw.queue_item_kind) === "external_adapter_review" &&
        text(raw.review_item_id) &&
        text(raw.available_disposition_action_id),
    );
  const allAdapterBlockersDispositionable =
    adapterBlockers.length > 0 &&
    adapterBlockers.length ===
      items
        .map((item) => asRecord(item.raw))
        .filter((raw) => text(raw.queue_item_kind) === "external_adapter_review").length;
  return (
    <section className={`queue-column ${tone}`}>
      <h2>{title}</h2>
      {onExternalAdapterDispositionAll && allAdapterBlockersDispositionable ? (
        <button
          className="secondary-btn"
          disabled={externalAdapterActionDisabled}
          onClick={() => onExternalAdapterDispositionAll()}
        >
          <ShieldCheck size={16} />
          Apply conservative dispositions
        </button>
      ) : null}
      {items.length ? (
        items.slice(0, 6).map((item) => {
          const raw = asRecord(item.raw);
          const supportRequest = asRecord(raw.support_request);
          const supportRequestId = text(supportRequest.support_request_id);
          const isSupportRequest = text(raw.queue_item_kind) === "conveyor_support_request" && supportRequestId;
          const isExternalAdapterReview =
            text(raw.queue_item_kind) === "external_adapter_review" && text(raw.review_item_id);
          const isSeedableDispatch = text(raw.queue_item_kind) === "seedable_conveyor_dispatch";
          const dispositionActionId = text(raw.available_disposition_action_id);
          const dispositionActionLabel = text(raw.available_disposition_action_label, item.actionLabel);
          return (
            <article key={`${item.bucket}-${item.id}`} className="queue-item">
              <strong>{item.title}</strong>
              <p>{item.detail}</p>
              <span>{item.actionLabel}</span>
              {isSupportRequest && onSupportRequestDecision ? (
                <div className="action-row compact-actions">
                  <button
                    className="primary-btn"
                    disabled={supportActionDisabled}
                    onClick={() => onSupportRequestDecision(supportRequestId, "approve")}
                  >
                    <ShieldCheck size={16} />
                    Approve
                  </button>
                  <button
                    className="secondary-btn"
                    disabled={supportActionDisabled}
                    onClick={() => onSupportRequestDecision(supportRequestId, "satisfy")}
                  >
                    <BookOpen size={16} />
                    Use staged pack
                  </button>
                  <button
                    className="danger-btn"
                    disabled={supportActionDisabled}
                    onClick={() => onSupportRequestDecision(supportRequestId, "reject")}
                  >
                    <Square size={16} />
                    Reject
                  </button>
                </div>
              ) : null}
              {isSeedableDispatch && onSeedableDispatchStart ? (
                <div className="action-row compact-actions">
                  <button
                    className="primary-btn"
                    disabled={seedableDispatchActionDisabled}
                    onClick={() => onSeedableDispatchStart()}
                  >
                    <Play size={16} />
                    Start governed dispatch
                  </button>
                </div>
              ) : null}
              {isExternalAdapterReview && dispositionActionId && onExternalAdapterDisposition ? (
                <div className="action-row compact-actions">
                  <button
                    className="primary-btn"
                    disabled={externalAdapterActionDisabled}
                    onClick={() => onExternalAdapterDisposition(text(raw.review_item_id), dispositionActionId)}
                  >
                    <ShieldCheck size={16} />
                    {dispositionActionLabel}
                  </button>
                </div>
              ) : null}
            </article>
          );
        })
      ) : (
        <p className="muted">No items in this lane.</p>
      )}
    </section>
  );
}
