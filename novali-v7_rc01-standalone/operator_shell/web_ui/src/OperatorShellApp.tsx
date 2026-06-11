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
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  Wand2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  approveAutonomyOperation,
  continueLongRun,
  emergencyStopAutonomy,
  executeReviewAction,
  fetchAutonomyGoals,
  fetchAutonomyStatus,
  fetchCurrentDirective,
  fetchInterventionState,
  fetchLibrarianSearch,
  fetchLibrarianStatus,
  fetchLLMHistory,
  fetchLLMPendingDirectives,
  fetchLLMStatus,
  fetchLongRunState,
  fetchObservabilityStatus,
  fetchOperatorState,
  pauseAutonomy,
  pauseLongRun,
  reviewAutonomyBoard,
  resumeLongRun,
  sendLLMChat,
  startAutonomy,
  startGoverned,
  stopLongRun,
  type AutonomyStatusPayload,
  type CurrentDirectiveStatus,
  type LLMHistoryPayload,
  type LLMMode,
  type LLMStatusPayload,
  type LibrarianSearchPayload,
  type LibrarianStatusPayload,
  type LongRunStatePayload,
  type OperatorState,
  type ReviewPayload,
} from "./lib/api";
import {
  buildAttentionQueue,
  buildCommandOverview,
  buildDirectiveWorkSummary,
  buildRuntimeSummary,
  OPERATOR_ARCANE_THEME,
} from "./lib/operatorShellView.js";

type LoadState = {
  operatorState: OperatorState | null;
  longRun: LongRunStatePayload | null;
  autonomy: AutonomyStatusPayload | null;
  observability: Record<string, unknown> | null;
  intervention: ReviewPayload | null;
  directive: CurrentDirectiveStatus | null;
  llmStatus: LLMStatusPayload | null;
  llmHistory: LLMHistoryPayload | null;
  autonomyGoals: Record<string, unknown> | null;
  llmPending: Record<string, unknown> | null;
  librarianStatus: LibrarianStatusPayload | null;
  librarianSearch: LibrarianSearchPayload | null;
};

type Toast = { tone: "success" | "warning" | "danger"; message: string };

const emptyState: LoadState = {
  operatorState: null,
  longRun: null,
  autonomy: null,
  observability: null,
  intervention: null,
  directive: null,
  llmStatus: null,
  llmHistory: null,
  autonomyGoals: null,
  llmPending: null,
  librarianStatus: null,
  librarianSearch: null,
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

async function loadShellState(): Promise<LoadState> {
  const [
    operatorState,
    longRun,
    autonomy,
    observability,
    intervention,
    directive,
    llmStatus,
    llmHistory,
    autonomyGoals,
    llmPending,
    librarianStatus,
    librarianSearch,
  ] = await Promise.all([
    fetchOperatorState().catch(() => null),
    fetchLongRunState().catch(() => null),
    fetchAutonomyStatus().catch(() => null),
    fetchObservabilityStatus().catch(() => null),
    fetchInterventionState().catch(() => null),
    fetchCurrentDirective().catch(() => null),
    fetchLLMStatus().catch(() => null),
    fetchLLMHistory().catch(() => null),
    fetchAutonomyGoals().catch(() => null),
    fetchLLMPendingDirectives().catch(() => null),
    fetchLibrarianStatus().catch(() => null),
    fetchLibrarianSearch({ limit: 8 }).catch(() => null),
  ]);
  return {
    operatorState,
    longRun,
    autonomy,
    observability,
    intervention,
    directive,
    llmStatus,
    llmHistory,
    autonomyGoals,
    llmPending,
    librarianStatus,
    librarianSearch,
  };
}

export function OperatorShellApp() {
  const [state, setState] = useState<LoadState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [toast, setToast] = useState<Toast | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "queue" | "directive" | "runtime" | "librarian">(
    isWorkspaceRoute() ? "queue" : "overview",
  );
  const [llmPrompt, setLlmPrompt] = useState("");
  const [llmMode, setLlmMode] = useState<LLMMode>("explain_state");
  const [askOpen, setAskOpen] = useState(false);
  const [librarianQuery, setLibrarianQuery] = useState("");

  async function refresh(soft = false) {
    if (!soft) setLoading(true);
    try {
      setState(await loadShellState());
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

  const overview = useMemo(
    () =>
      buildCommandOverview({
        longRun: state.longRun,
        autonomy: state.autonomy,
        observability: state.observability,
        operatorState: state.operatorState,
      }),
    [state],
  );
  const queue = useMemo(
    () => buildAttentionQueue({ operatorState: state.operatorState }),
    [state.operatorState],
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

  async function runAction(actionId: string, action: () => Promise<unknown>) {
    setBusyAction(actionId);
    setToast(null);
    try {
      const result = asRecord(await action());
      setToast({
        tone: Boolean(result.ok ?? true) ? "success" : "warning",
        message: text(result.message, `${formatKind(actionId)} completed.`),
      });
      await refresh(true);
    } catch (error) {
      setToast({ tone: "danger", message: `${formatKind(actionId)} failed: ${String(error)}` });
    } finally {
      setBusyAction("");
    }
  }

  const longRunPayload = asRecord(asRecord(state.longRun).long_run || state.longRun);
  const latestOperation = asRecord(
    asRecord(state.autonomy).latest_operation ||
      asRecord(state.autonomy).latest_proposed_operation ||
      asRecord(state.autonomy).proposed_operation,
  );
  const operationId = text(latestOperation.operation_id, latestOperation.id);
  const firstReviewOption = asArray(asRecord(state.intervention).options)[0];

  async function askNovali() {
    if (!llmPrompt.trim()) {
      setToast({ tone: "warning", message: "Ask Novali needs a prompt first." });
      return;
    }
    await runAction("ask_novali", () => sendLLMChat({ message: llmPrompt, mode: llmMode }));
    setLlmPrompt("");
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

  const librarianStatus = asRecord(state.librarianStatus);
  const librarianResults = asArray(asRecord(state.librarianSearch).results);

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
          <button className="icon-btn" title="Refresh operator state" onClick={() => refresh()} disabled={loading}>
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

      <section className={`safety-rune ${statusToneClass(overview.safetyTone)}`} data-testid="command-overview">
        <div className="status-orb">
          {overview.safetyTone === "danger" ? <ShieldAlert /> : <ShieldCheck />}
        </div>
        <div className="safety-copy">
          <p className="eyebrow">Current truth</p>
          <h2>{overview.headline}</h2>
          <p>{overview.nextAction}</p>
        </div>
        <div className="primary-action">
          <button
            className="primary-btn"
            data-testid="primary-safe-action"
            disabled={!overview.primaryAction.enabled || busyAction === "continue"}
            onClick={() => runAction("continue", () => continueLongRun())}
          >
            <Play size={18} />
            <span>{overview.primaryAction.label}</span>
          </button>
          <button className="secondary-btn" onClick={() => setAskOpen(true)}>
            <Bot size={18} />
            <span>Ask Novali</span>
          </button>
        </div>
      </section>

      <section className="metric-strip" aria-label="Core state metrics">
        <Metric label="Lifecycle" value={overview.lifecycle} />
        <Metric label="Lease" value={overview.leaseState} />
        <Metric label="Checkpoints" value={String(overview.checkpointCount)} />
        <Metric label="Autonomy" value={overview.runtimeState} />
        <Metric label="Memory" value={`${overview.memoryState} / ${overview.oomState}`} />
        <Metric label="Telemetry" value={overview.observabilityState} />
      </section>

      <nav className="tab-bar" aria-label="Operator shell sections">
        {[
          ["overview", "Overview", Compass],
          ["queue", "Attention Queue", AlertTriangle],
          ["directive", "Directive Work", Layers3],
          ["runtime", "Autonomy + Runtime", BrainCircuit],
          ["librarian", "Librarian", BookOpen],
        ].map(([id, label, Icon]) => (
          <button
            key={String(id)}
            className={activeTab === id ? "active" : ""}
            onClick={() => setActiveTab(id as typeof activeTab)}
          >
            <Icon size={17} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {activeTab === "overview" ? (
        <section className="dashboard-grid">
          <Panel title="Next safe operation" icon={<Compass />}>
            <p className="large-state">{overview.primaryAction.label}</p>
            <p>{overview.nextAction}</p>
            <div className="action-row">
              <button className="primary-btn" onClick={() => runAction("continue", () => continueLongRun())}>
                <Play size={16} />
                Continue
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
            <button className="secondary-btn" onClick={() => setActiveTab("queue")}>
              Review queue
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
          <QueueColumn title="Needs operator" items={queue.blockers} tone="danger" />
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

      {activeTab === "directive" ? (
        <section className="dashboard-grid wide" data-testid="directive-work">
          <Panel title="Loaded directive" icon={<Gem />}>
            <p className="large-state">{directive.directiveTitle}</p>
            <p>{directive.directiveSummary}</p>
            <dl className="detail-list">
              <dt>Loaded</dt>
              <dd>{directive.directiveLoaded ? "yes" : "no"}</dd>
              <dt>Directive file label</dt>
              <dd>{directive.directiveFileStatus}</dd>
              <dt>Current execution gate</dt>
              <dd>{directive.executionGate}</dd>
              <dt>Directive ref</dt>
              <dd>{directive.directiveId}</dd>
            </dl>
          </Panel>
          <Panel title="Directive track" icon={<Layers3 />}>
            <p className="large-state">{formatKind(directive.deliverableKind)}</p>
            <dl className="detail-list">
              <dt>Material delta</dt>
              <dd>{directive.materialDelta ? "yes" : "no"}</dd>
              <dt>Depth</dt>
              <dd>{directive.artifactDepth}</dd>
              <dt>Focus</dt>
              <dd>{directive.focusId}</dd>
              <dt>Layer</dt>
              <dd>{directive.layerId}</dd>
              <dt>Artifact</dt>
              <dd>{directive.artifactPath || "not recorded"}</dd>
            </dl>
          </Panel>
          <Panel title="Meaningful work" icon={<Sparkles />}>
            <div className={directive.meaningfulDelta ? "score-ring active" : "score-ring"}>
              {directive.meaningfulDelta ? "Delta" : "No delta"}
            </div>
            <p className="large-state">{directive.meaningfulCreditLabel}</p>
            <dl className="detail-list compact">
              <dt>Score</dt>
              <dd>{Math.round(directive.score * 100)}%</dd>
              <dt>Credit source</dt>
              <dd>{formatKind(directive.meaningfulCreditKind)}</dd>
              <dt>Track credit</dt>
              <dd>{directive.deltaCredited ? "credited" : "not credited"}</dd>
              <dt>Depth iteration</dt>
              <dd>{directive.depthIteration || "not recorded"}</dd>
              <dt>Weak area</dt>
              <dd>{directive.weakArea}</dd>
              <dt>Delta signature</dt>
              <dd>{directive.deltaSignature || "not recorded"}</dd>
              <dt>Progress time</dt>
              <dd>{directive.progressGeneratedAt || "not recorded"}</dd>
              <dt>Dossier</dt>
              <dd>{directive.dossierState}</dd>
              <dt>Dossier delta</dt>
              <dd>{directive.dossierMaterialDelta ? "material" : "not material"}</dd>
              <dt>Source coverage</dt>
              <dd>{directive.sourceCoverageState}</dd>
              <dt>Librarian reuse</dt>
              <dd>{directive.librarianGapReuseDecision}</dd>
              <dt>Trusted retrieval</dt>
              <dd>{directive.trustedSourceRetrievalValidationState}</dd>
              <dt>Latest dossier</dt>
              <dd>{directive.latestDossierRef || "not recorded"}</dd>
            </dl>
            <p>Promotion packet state: {directive.promotionState}</p>
            <p>Meaningful rejection: {directive.meaningfulRejectionReason}</p>
            <p>Track rejection: {directive.rejectionReason}</p>
            <p>Dossier rejection: {directive.dossierRejectionReason}</p>
          </Panel>
          <Panel title="Directive actions" icon={<Compass />}>
            <p>
              Track advancement remains local evidence creation. High-impact adoption is still policy-gated.
            </p>
            <button className="primary-btn" onClick={() => runAction("start_governed", () => startGoverned({}))}>
              Start governed continuation
            </button>
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

      <aside className={askOpen ? "ask-drawer open" : "ask-drawer"} data-testid="ask-novali-panel">
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
          Explanatory and drafting only. This panel cannot launch, approve, continue, pause, stop, or mutate directives.
        </p>
        <div className="status-pill">
          {text(asRecord(state.llmStatus).provider, "ollama")} · {text(asRecord(state.llmStatus).status, "unknown")}
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
        <div className="drawer-history">
          {asArray(asRecord(state.llmHistory).records).slice(0, 4).map((record) => (
            <article key={text(record.id, record.created_at, record.prompt)}>
              <strong>{text(record.mode, "chat")}</strong>
              <p>{text(record.response_preview, record.response, record.error, "No response stored.").slice(0, 220)}</p>
            </article>
          ))}
          {asArray(asRecord(state.llmPending).pending_directives).length ? (
            <p className="muted">
              Pending directive drafts: {asArray(asRecord(state.llmPending).pending_directives).length}
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
}: {
  title: string;
  items: ReturnType<typeof buildAttentionQueue>["blockers"];
  tone: "danger" | "healthy" | "neutral";
}) {
  return (
    <section className={`queue-column ${tone}`}>
      <h2>{title}</h2>
      {items.length ? (
        items.slice(0, 6).map((item) => (
          <article key={`${item.bucket}-${item.id}`} className="queue-item">
            <strong>{item.title}</strong>
            <p>{item.detail}</p>
            <span>{item.actionLabel}</span>
          </article>
        ))
      ) : (
        <p className="muted">No items in this lane.</p>
      )}
    </section>
  );
}
