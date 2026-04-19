<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    fetchGovernedStatus,
    fetchLongRunState,
    fetchOperatorState,
    openRuntimeEventStream,
    prepareGovernedExecution,
    selectDirective,
    startBootstrap,
    startGoverned,
    uploadDirective,
    validateTrustedSource,
    type LaunchStatusSnapshot,
    type LongRunStatePayload,
    type OperatorState,
    type RuntimeEventPayload,
  } from "$lib/api";
  import {
    buildHandoffMemoryEntry,
    createEmptyAttentionMemory,
    loadAttentionMemory,
    serializeAttentionMemory,
    upsertHandoffMemory,
  } from "$lib/attentionMemory.js";
  import {
    buildPortfolioNavigationTarget,
    buildSessionPortfolio,
  } from "$lib/sessionPortfolio.js";
  import {
    applyPortfolioLifecycleAction,
    buildManagedSessionPortfolio,
    createEmptyPortfolioLifecycleMemory,
    loadPortfolioLifecycleMemory,
    serializePortfolioLifecycleMemory,
  } from "$lib/portfolioLifecycle.js";
  import {
    PORTFOLIO_BATCH_SELECTION_LIMIT,
    applyPortfolioShortcutMemoryAction,
    buildPortfolioActionView,
    createEmptyPortfolioShortcutMemory,
    loadPortfolioShortcutMemory,
    serializePortfolioShortcutMemory,
  } from "$lib/portfolioShortcuts.js";
  import {
    PORTFOLIO_MANAGER_FILTERS,
    buildPortfolioManagerDashboard,
    filterPortfolioSections,
  } from "$lib/portfolioDashboard.js";
  import { buildExternalAdapterStatusView } from "$lib/externalAdapterStatus.js";
  import { buildExternalAdapterReviewStatusView } from "$lib/externalAdapterReviewStatus.js";
  import { buildControllerIsolationStatusView } from "$lib/controllerIsolationStatus.js";
  import { buildReadOnlyAdapterStatusView } from "$lib/readOnlyAdapterStatus.js";
  import { buildOperatorAlertsStatusView } from "$lib/operatorAlertsStatus.js";
  import {
    buildDeferredResponseAnchorState,
    buildPortfolioDeferredWorkloadDigest,
    buildPortfolioManagerAgenda,
    buildPortfolioManagerDigest,
    buildPortfolioOperatorQueue,
    createEmptyPortfolioDigestMemory,
    deferPortfolioManagerItem,
    loadPortfolioDigestMemory,
    recordDeferredResponseAnchor,
    recordPortfolioDigestTouch,
    reopenPortfolioManagerItem,
    serializePortfolioDigestMemory,
  } from "$lib/portfolioDigest.js";
  import { buildObservabilityStatusView } from "$lib/observabilityStatus.js";

  type FeedTone = "info" | "success" | "warning";
  type FeedEntry = { id: string; tone: FeedTone; label: string; detail: string; at: string };
  type SessionPortfolioCard = {
    session_id?: string;
    session_handle?: string;
    entry_key?: string;
    lifecycle_state?: string;
    state_label?: string;
    stop_reason?: string;
    current_blocker?: string;
    next_action_label?: string;
    next_action_detail?: string;
    current_cycle?: number;
    max_cycles?: number;
    checkpoint_count?: number;
    checkpoint_id?: string;
    checkpoint_at?: string;
    policy_headroom_summary?: string;
    settings_summary?: string;
    next_stop_boundary_label?: string;
    next_stop_boundary_summary?: string;
    what_changed_summary?: string;
    attention_state_label?: string;
    attention_state_tone?: string;
    queue_bucket?: string;
    queue_bucket_label?: string;
    current_session?: boolean;
    current_or_recent_label?: string;
    [key: string]: unknown;
  };
  type PortfolioRecommendation = {
    label?: string;
    detail?: string;
    navigation?: {
      route?: string;
      url?: string;
      label?: string;
    };
    shortlist?: SessionPortfolioCard[];
    target_entry_key?: string;
    [key: string]: unknown;
  } | null;
  type PortfolioSection = {
    key?: string;
    label?: string;
    detail?: string;
    cards?: SessionPortfolioCard[];
    [key: string]: unknown;
  };
  type PortfolioBatchSummary = {
    selection_count?: number;
    selection_summary?: string;
    max_selection?: number;
    ready_counts?: Record<string, number>;
    actions?: Record<string, { label?: string; allowed?: boolean; blocked_reason?: string; detail?: string }>;
    safe_batch_shortcuts?: Array<{ key?: string; label?: string; eligible_count?: number; detail?: string }>;
    [key: string]: unknown;
  } | null;
  type PortfolioActionRule = {
    key?: string;
    label?: string;
    detail?: string;
    [key: string]: unknown;
  };
  type PortfolioDigestCounter = {
    key?: string;
    label?: string;
    count?: number;
    detail?: string;
    [key: string]: unknown;
  };
  type PortfolioDigestSummary = {
    anchor?: {
      basis_key?: string;
      basis_label?: string;
      recorded_at?: string;
      detail?: string;
      has_comparison?: boolean;
    };
    headline?: string;
    detail?: string;
    currentSnapshot?: {
      recorded_at?: string;
      recommendation_label?: string;
      sessions?: SessionPortfolioCard[];
      [key: string]: unknown;
    };
    counts?: Record<string, number>;
    counters?: PortfolioDigestCounter[];
    topBlockers?: SessionPortfolioCard[];
    pendingOperatorItems?: SessionPortfolioCard[];
    progressingWithoutOperator?: SessionPortfolioCard[];
    advancedSessions?: SessionPortfolioCard[];
    meaningfulProgressSummary?: string;
    unresolvedGovernanceItems?: string[];
    recommendedNextAction?: {
      label?: string;
      detail?: string;
      targetSessionId?: string;
      targetCardKey?: string;
    } | null;
    nextBestActions?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  } | null;
  type PortfolioManagerAgenda = {
    anchor?: {
      basis_key?: string;
      basis_label?: string;
      recorded_at?: string;
    };
    checked_at?: string;
    currentItem?: SessionPortfolioCard | null;
    nextItem?: SessionPortfolioCard | null;
    pendingItems?: SessionPortfolioCard[];
    newItems?: SessionPortfolioCard[];
    reviewedPendingItems?: SessionPortfolioCard[];
    overdueItems?: SessionPortfolioCard[];
    dueItems?: SessionPortfolioCard[];
    deferredItems?: SessionPortfolioCard[];
    reopenedItems?: SessionPortfolioCard[];
    completedItems?: Array<{
      session_id?: string;
      session_handle?: string;
      next_action_label?: string;
      agenda_state_key?: string;
      agenda_state_label?: string;
      agenda_state_detail?: string;
      completion_outcome_label?: string;
      completion_outcome_detail?: string;
      resulting_state_label?: string;
      [key: string]: unknown;
    }>;
    justCompletedItem?: {
      session_id?: string;
      session_handle?: string;
      completion_outcome_label?: string;
      completion_outcome_detail?: string;
      resulting_state_label?: string;
      [key: string]: unknown;
    } | null;
    clearedItems?: Array<{
      session_id?: string;
      session_handle?: string;
      summary?: string;
    }>;
    itemStateBySessionId?: Record<string, { key?: string; label?: string; detail?: string }>;
    counts?: Record<string, number>;
    currentAgendaSummary?: string;
    nextAgendaSummary?: string;
    completedAgendaSummary?: string;
    overdueAgendaSummary?: string;
    dueAgendaSummary?: string;
    deferredAgendaSummary?: string;
    reopenedAgendaSummary?: string;
    throughput?: {
      headline?: string;
      detail?: string;
      current_item_summary?: string;
      next_item_summary?: string;
      completed_item_summary?: string;
      due_item_summary?: string;
      deferred_item_summary?: string;
      completed_since_last_check?: number;
      still_pending_from_before_check?: number;
      new_since_last_check?: number;
      overdue_manager_items?: number;
      overdue_after_return?: number;
      due_now?: number;
      reopened_items?: number;
      deferred_items?: number;
      deferred_since_last_check?: number;
      due_returned_since_last_check?: number;
      returned_from_snooze_since_last_check?: number;
      reopened_since_last_check?: number;
      actionable_now?: number;
      [key: string]: unknown;
    } | null;
    rationale?: string;
    [key: string]: unknown;
  } | null;
  type PortfolioDeferredWorkloadDigest = {
    anchor?: {
      basis_key?: string;
      basis_label?: string;
      recorded_at?: string;
      detail?: string;
      has_comparison?: boolean;
    };
    headline?: string;
    detail?: string;
    currentReason?: string;
    pressureBand?: {
      key?: string;
      label?: string;
      detail?: string;
      trendKey?: string;
      trendLabel?: string;
    };
    responsePolicy?: {
      primary?: {
        key?: string;
        label?: string;
        detail?: string;
      } | null;
      shortlist?: Array<{
        key?: string;
        label?: string;
        detail?: string;
      }>;
      detail?: string;
    };
    responseOutcome?: {
      key?: string;
      label?: string;
      detail?: string;
      basisKey?: string;
      basisLabel?: string;
      actedSinceAnchor?: boolean;
      actionDetail?: string;
      previousBandKey?: string;
      previousBandLabel?: string;
      currentBandKey?: string;
      currentBandLabel?: string;
      previousResponseKey?: string;
      previousResponseLabel?: string;
      currentResponseKey?: string;
      currentResponseLabel?: string;
    };
    counts?: Record<string, number>;
    counters?: PortfolioDigestCounter[];
    returnBasisSummary?: Array<{
      key?: string;
      label?: string;
      count?: number;
      detail?: string;
    }>;
    deferredItems?: SessionPortfolioCard[];
    dueItems?: SessionPortfolioCard[];
    reopenedItems?: SessionPortfolioCard[];
    overdueAfterReturnItems?: SessionPortfolioCard[];
    [key: string]: unknown;
  } | null;
  type OperatorQueueSection = {
    key?: string;
    label?: string;
    tone?: string;
    detail?: string;
    count?: number;
    cards?: SessionPortfolioCard[];
    [key: string]: unknown;
  };
  type PortfolioOperatorQueue = {
    sections?: OperatorQueueSection[];
    groupedCounts?: Array<{
      key?: string;
      label?: string;
      tone?: string;
      count?: number;
    }>;
    counts?: Record<string, number>;
    dominantAction?: {
      label?: string;
      detail?: string;
      targetSessionId?: string;
      targetCardKey?: string;
    } | null;
    shortlist?: SessionPortfolioCard[];
    [key: string]: unknown;
  } | null;

  let state: OperatorState | null = null;
  let longRun: LongRunStatePayload | null = null;
  let loadIssue = "";
  let loadIssueTone: "danger" | "warning" = "danger";
  let actionMessage = "";
  let loading = true;
  let directiveBusy = false;
  let trustedSourceBusy = false;
  let bootstrapBusy = false;
  let governedPrepBusy = false;
  let governedBusy = false;
  let refreshTimer: ReturnType<typeof setInterval> | null = null;
  let closeRuntimeStream: (() => void) | null = null;
  let streamLive = false;
  let lastHeartbeatAt = "";
  let startupFeed: FeedEntry[] = [];
  let showDirectiveModal = false;
  let directivePathInput = "";
  let secretProviderId = "openai_api";
  let secretProviderBaseUrl = "https://api.openai.com/v1";
  let secretCredential = "";
  let validationNotice = "";
  let uploadNotice = "";
  let selectedFile: File | null = null;
  const ATTENTION_MEMORY_STORAGE_KEY = "novali.workspace.attentionMemory";
  const PORTFOLIO_LIFECYCLE_STORAGE_KEY = "novali.workspace.portfolioLifecycle";
  const PORTFOLIO_SHORTCUT_STORAGE_KEY = "novali.workspace.portfolioShortcuts";
  const PORTFOLIO_DIGEST_STORAGE_KEY = "novali.workspace.portfolioDigest";
  let attentionMemory = createEmptyAttentionMemory() as {
    schema_version: number;
    sessions: Record<string, unknown>;
  };
  let portfolioLifecycleMemory = createEmptyPortfolioLifecycleMemory() as {
    schema_version: number;
    sessions: Record<string, unknown>;
  };
  let portfolioShortcutMemory = createEmptyPortfolioShortcutMemory() as {
    schema_version: number;
    sessions: Record<string, unknown>;
  };
  let portfolioDigestMemory = createEmptyPortfolioDigestMemory() as {
    schema_version: number;
    last_manager_check_at?: string;
    last_manager_check_snapshot?: Record<string, unknown> | null;
    last_manager_touch_at?: string;
    last_manager_touch_snapshot?: Record<string, unknown> | null;
    last_deferred_response_anchor?: Record<string, unknown> | null;
    manager_items?: Record<string, unknown>;
    manager_item_events?: Array<Record<string, unknown>>;
  };
  let portfolioCards: SessionPortfolioCard[] = [];
  let portfolioAllCards: SessionPortfolioCard[] = [];
  let portfolioRecommendation: PortfolioRecommendation = null;
  let portfolioBucketCounts: Record<string, number> = {};
  let portfolioSections: PortfolioSection[] = [];
  let portfolioAllSections: PortfolioSection[] = [];
  let portfolioLifecycleCounts: Record<string, number> = {};
  let portfolioBatchSummary: PortfolioBatchSummary = null;
  let portfolioActionRules: PortfolioActionRule[] = [];
  let portfolioGroupCounts = [] as Array<{
    key: string;
    label: string;
    description: string;
    count: number;
    overlay?: boolean;
  }>;
  let portfolioManagerSummary = null as {
    title?: string;
    detail?: string;
    recommendationLabel?: string;
    recommendationDetail?: string;
    dominantAction?: {
      key?: string;
      label?: string;
      detail?: string;
      mode?: string;
      filterKey?: string;
      targetCardKey?: string;
      targetSessionId?: string;
      targetCardKeys?: string[];
      batchAction?: string;
    } | null;
    followupActions?: Array<Record<string, unknown>>;
    housekeepingActions?: Array<Record<string, unknown>>;
  } | null;
  let portfolioSummaryActions = [] as Array<{
    key?: string;
    label?: string;
    detail?: string;
    mode?: string;
    filterKey?: string;
    targetCardKey?: string;
    targetSessionId?: string;
    targetCardKeys?: string[];
    batchAction?: string;
  }>;
  let portfolioManagerDigest = null as PortfolioDigestSummary;
  let portfolioManagerAgenda = null as PortfolioManagerAgenda;
  let portfolioDeferredWorkloadDigest = null as PortfolioDeferredWorkloadDigest;
  let portfolioOperatorQueue = null as PortfolioOperatorQueue;
  let portfolioGroupFilter = "all";
  let portfolioBatchSelection: string[] = [];
  let selectedPortfolioEntryKey = "";
  let portfolioNotice = "";
  let portfolioDigestNotice = "";
  let portfolioLifecycleNotice = "";
  let portfolioLifecycleError = "";
  let portfolioBatchNotice = "";
  let portfolioBatchError = "";

  const textValue = (value: unknown, fallback = "n/a") => String(value ?? "").trim() || fallback;
  const relativeTime = (value: string) => {
    const when = Date.parse(value || "");
    if (Number.isNaN(when)) return value || "just now";
    const delta = Math.max(0, Math.round((Date.now() - when) / 1000));
    if (delta < 10) return "just now";
    if (delta < 60) return `${delta}s ago`;
    if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
    return `${Math.round(delta / 3600)}h ago`;
  };
  const pushFeedEntry = (label: string, detail = "", tone: FeedTone = "info", at = "") => {
    const eventTime = at || new Date().toISOString();
    const id = `${eventTime}|${label}|${detail}`;
    startupFeed = [{ id, tone, label, detail, at: eventTime }, ...startupFeed.filter((item) => item.id !== id)].slice(0, 8);
  };
  const formatRecordedAt = (value: unknown) => {
    const raw = String(value || "").trim();
    if (!raw) return "n/a";
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return raw;
    return parsed.toLocaleString();
  };
  const readStoredAttentionMemory = () => {
    if (typeof window === "undefined") return createEmptyAttentionMemory() as { schema_version: number; sessions: Record<string, unknown> };
    try {
      return loadAttentionMemory(window.localStorage.getItem(ATTENTION_MEMORY_STORAGE_KEY)) as {
        schema_version: number;
        sessions: Record<string, unknown>;
      };
    } catch {
      return createEmptyAttentionMemory() as { schema_version: number; sessions: Record<string, unknown> };
    }
  };
  const persistAttentionMemory = (memory: { schema_version: number; sessions: Record<string, unknown> }) => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(ATTENTION_MEMORY_STORAGE_KEY, serializeAttentionMemory(memory));
    } catch {
      // Keep the shell usable even if local storage is unavailable.
    }
  };
  const readStoredPortfolioLifecycleMemory = () => {
    if (typeof window === "undefined") {
      return createEmptyPortfolioLifecycleMemory() as {
        schema_version: number;
        sessions: Record<string, unknown>;
      };
    }
    try {
      return loadPortfolioLifecycleMemory(
        window.localStorage.getItem(PORTFOLIO_LIFECYCLE_STORAGE_KEY),
      ) as {
        schema_version: number;
        sessions: Record<string, unknown>;
      };
    } catch {
      return createEmptyPortfolioLifecycleMemory() as {
        schema_version: number;
        sessions: Record<string, unknown>;
      };
    }
  };
  const persistPortfolioLifecycleMemory = (memory: {
    schema_version: number;
    sessions: Record<string, unknown>;
  }) => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        PORTFOLIO_LIFECYCLE_STORAGE_KEY,
        serializePortfolioLifecycleMemory(memory),
      );
    } catch {
      // Keep the shell usable even if local storage is unavailable.
    }
  };
  const readStoredPortfolioShortcutMemory = () => {
    if (typeof window === "undefined") {
      return createEmptyPortfolioShortcutMemory() as {
        schema_version: number;
        sessions: Record<string, unknown>;
      };
    }
    try {
      return loadPortfolioShortcutMemory(
        window.localStorage.getItem(PORTFOLIO_SHORTCUT_STORAGE_KEY),
      ) as {
        schema_version: number;
        sessions: Record<string, unknown>;
      };
    } catch {
      return createEmptyPortfolioShortcutMemory() as {
        schema_version: number;
        sessions: Record<string, unknown>;
      };
    }
  };
  const persistPortfolioShortcutMemory = (memory: {
    schema_version: number;
    sessions: Record<string, unknown>;
  }) => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        PORTFOLIO_SHORTCUT_STORAGE_KEY,
        serializePortfolioShortcutMemory(memory),
      );
    } catch {
      // Keep the shell usable even if local storage is unavailable.
    }
  };
  const readStoredPortfolioDigestMemory = () => {
    if (typeof window === "undefined") {
      return createEmptyPortfolioDigestMemory() as {
        schema_version: number;
        last_manager_check_at?: string;
        last_manager_check_snapshot?: Record<string, unknown> | null;
        last_manager_touch_at?: string;
        last_manager_touch_snapshot?: Record<string, unknown> | null;
      };
    }
    try {
      return loadPortfolioDigestMemory(
        window.localStorage.getItem(PORTFOLIO_DIGEST_STORAGE_KEY),
      ) as {
        schema_version: number;
        last_manager_check_at?: string;
        last_manager_check_snapshot?: Record<string, unknown> | null;
        last_manager_touch_at?: string;
        last_manager_touch_snapshot?: Record<string, unknown> | null;
        manager_items?: Record<string, unknown>;
        manager_item_events?: Array<Record<string, unknown>>;
      };
    } catch {
      return createEmptyPortfolioDigestMemory() as {
        schema_version: number;
        last_manager_check_at?: string;
        last_manager_check_snapshot?: Record<string, unknown> | null;
        last_manager_touch_at?: string;
        last_manager_touch_snapshot?: Record<string, unknown> | null;
      };
    }
  };
  const persistPortfolioDigestMemory = (memory: {
    schema_version: number;
    last_manager_check_at?: string;
    last_manager_check_snapshot?: Record<string, unknown> | null;
    last_manager_touch_at?: string;
    last_manager_touch_snapshot?: Record<string, unknown> | null;
    manager_items?: Record<string, unknown>;
    manager_item_events?: Array<Record<string, unknown>>;
  }) => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        PORTFOLIO_DIGEST_STORAGE_KEY,
        serializePortfolioDigestMemory(memory),
      );
    } catch {
      // Keep the shell usable even if local storage is unavailable.
    }
  };
  const recordPortfolioManagerTouch = (
    notice = "Manager digest checked. Future shell summaries now compare against this manager check.",
  ) => {
    if (!portfolioManagerDigest?.currentSnapshot) {
      return;
    }
    portfolioDigestMemory = recordPortfolioDigestTouch(
      portfolioDigestMemory,
      {
        ...(portfolioManagerDigest.currentSnapshot as {
          recorded_at?: string;
          recommendation_label?: string;
          sessions?: SessionPortfolioCard[];
        }),
        deferred_state: buildDeferredResponseAnchorState(portfolioDeferredWorkloadDigest, {
          recordedAt: new Date().toISOString(),
          source: "manager_check",
        }),
      },
      {
        recordedAt: new Date().toISOString(),
      },
    ) as {
      schema_version: number;
      last_manager_check_at?: string;
      last_manager_check_snapshot?: Record<string, unknown> | null;
      last_manager_touch_at?: string;
      last_manager_touch_snapshot?: Record<string, unknown> | null;
      last_deferred_response_anchor?: Record<string, unknown> | null;
    };
    persistPortfolioDigestMemory(portfolioDigestMemory);
    portfolioDigestNotice = notice;
    refreshPortfolioQueue();
  };
  const maybeRecordDeferredResponseAnchor = (card: SessionPortfolioCard | null | undefined) => {
    const sessionId = String(card?.session_id || "").trim();
    const currentSessionId = String(portfolioManagerAgenda?.currentItem?.session_id || "").trim();
    if (!sessionId || !currentSessionId || sessionId !== currentSessionId || !portfolioDeferredWorkloadDigest) {
      return;
    }
    portfolioDigestMemory = recordDeferredResponseAnchor(
      portfolioDigestMemory,
      portfolioDeferredWorkloadDigest,
      {
        recordedAt: new Date().toISOString(),
        source: "shell_action",
        targetSessionId: sessionId,
        actionLabel: textValue(card?.shortcut_action_label || card?.next_action_label, "Open current item"),
      },
    ) as {
      schema_version: number;
      last_manager_check_at?: string;
      last_manager_check_snapshot?: Record<string, unknown> | null;
      last_manager_touch_at?: string;
      last_manager_touch_snapshot?: Record<string, unknown> | null;
      last_deferred_response_anchor?: Record<string, unknown> | null;
      manager_items?: Record<string, unknown>;
      manager_item_events?: Array<Record<string, unknown>>;
    };
    persistPortfolioDigestMemory(portfolioDigestMemory);
  };
  const portfolioManagerAgendaStateKey = (card: SessionPortfolioCard | null | undefined) => {
    const sessionId = String(card?.session_id || "").trim();
    if (!sessionId || !portfolioManagerAgenda) {
      return "";
    }
    const itemState = (portfolioManagerAgenda.itemStateBySessionId || {})[sessionId] as {
      key?: string;
    } | null;
    return textValue(itemState?.key, "");
  };
  const portfolioSelectionKey = (card: SessionPortfolioCard | null | undefined) =>
    String(card?.entry_key || card?.session_id || "").trim();
  const isPortfolioCardSelected = (card: SessionPortfolioCard | null | undefined) =>
    portfolioBatchSelection.includes(portfolioSelectionKey(card));
  const portfolioManagerAgendaState = (card: SessionPortfolioCard | null | undefined) => {
    const sessionId = String(card?.session_id || "").trim();
    if (!sessionId || !portfolioManagerAgenda) {
      return "";
    }
    const itemState = (portfolioManagerAgenda.itemStateBySessionId || {})[sessionId] as {
      label?: string;
    } | null;
    return textValue(itemState?.label, "");
  };
  const canDeferManagerItem = (card: SessionPortfolioCard | null | undefined) =>
    [
      "new_since_last_check",
      "reviewed_still_pending",
      "overdue_manager_item",
      "due_return_now",
      "overdue_after_return",
      "reopened_after_defer",
    ].includes(portfolioManagerAgendaStateKey(card));
  const canReopenManagerItem = (card: SessionPortfolioCard | null | undefined) =>
    ["deferred_until_next_manager_check", "deferred_until_reopen"].includes(
      portfolioManagerAgendaStateKey(card),
    );
  const handlePortfolioManagerDefer = (
    card: SessionPortfolioCard | null | undefined,
    basis: "next_manager_check" | "until_reopen" = "next_manager_check",
  ) => {
    const result = deferPortfolioManagerItem(portfolioDigestMemory, card || {}, {
      deferredAt: new Date().toISOString(),
      deferBasisKey: basis,
      deferBasisLabel:
        basis === "until_reopen"
          ? "Deferred until reopened"
          : "Snoozed until next manager check",
    }) as {
      memory: {
        schema_version: number;
        last_manager_check_at?: string;
        last_manager_check_snapshot?: Record<string, unknown> | null;
        last_manager_touch_at?: string;
        last_manager_touch_snapshot?: Record<string, unknown> | null;
        manager_items?: Record<string, unknown>;
        manager_item_events?: Array<Record<string, unknown>>;
      };
      changed?: boolean;
      blocked_reason?: string;
      notice?: string;
    };
    portfolioDigestMemory = result.memory;
    persistPortfolioDigestMemory(portfolioDigestMemory);
    portfolioDigestNotice = textValue(
      result.blocked_reason,
      textValue(
        result.notice,
        basis === "until_reopen"
          ? "Manager item deferred until explicit reopen."
          : "Manager item snoozed until the next manager check.",
      ),
    );
    refreshPortfolioQueue();
  };
  const handlePortfolioManagerReopen = (card: SessionPortfolioCard | null | undefined) => {
    const result = reopenPortfolioManagerItem(portfolioDigestMemory, card || {}, {
      reopenedAt: new Date().toISOString(),
    }) as {
      memory: {
        schema_version: number;
        last_manager_check_at?: string;
        last_manager_check_snapshot?: Record<string, unknown> | null;
        last_manager_touch_at?: string;
        last_manager_touch_snapshot?: Record<string, unknown> | null;
        manager_items?: Record<string, unknown>;
        manager_item_events?: Array<Record<string, unknown>>;
      };
      changed?: boolean;
      blocked_reason?: string;
      notice?: string;
    };
    portfolioDigestMemory = result.memory;
    persistPortfolioDigestMemory(portfolioDigestMemory);
    portfolioDigestNotice = textValue(
      result.blocked_reason,
      textValue(result.notice, "Deferred manager item returned to the active agenda."),
    );
    refreshPortfolioQueue();
  };
  const portfolioCardId = (card: SessionPortfolioCard | null | undefined) =>
    `session-portfolio-card-${String(card?.entry_key || card?.session_id || "unknown").trim() || "unknown"}`;
  const selectPortfolioCard = (card: SessionPortfolioCard | null | undefined) => {
    selectedPortfolioEntryKey = String(card?.entry_key || "").trim();
    portfolioNotice = "";
    portfolioLifecycleNotice = "";
    portfolioLifecycleError = "";
    portfolioBatchNotice = "";
    portfolioBatchError = "";
  };
  const portfolioCardActionLabel = (card: SessionPortfolioCard | null | undefined) =>
    String(card?.shortcut_action_label || buildPortfolioNavigationTarget(card || {}).label || "Open session");
  const portfolioLifecycleActionLabel = (card: SessionPortfolioCard | null | undefined) =>
    String(card?.archive_action_label || "Archive session");
  const portfolioPinActionLabel = (card: SessionPortfolioCard | null | undefined) =>
    String(card?.pin_action_label || "Pin session");
  const portfolioShortcutActionLabel = (card: SessionPortfolioCard | null | undefined) =>
    String(card?.shortcut_action_label || portfolioCardActionLabel(card));
  const togglePortfolioBatchSelection = (card: SessionPortfolioCard | null | undefined) => {
    const key = portfolioSelectionKey(card);
    if (!key) return;
    portfolioBatchNotice = "";
    portfolioBatchError = "";
    if (portfolioBatchSelection.includes(key)) {
      portfolioBatchSelection = portfolioBatchSelection.filter((value) => value !== key);
      refreshPortfolioQueue();
      return;
    }
    if (portfolioBatchSelection.length >= PORTFOLIO_BATCH_SELECTION_LIMIT) {
      portfolioBatchError = `Batch selection stays bounded to ${PORTFOLIO_BATCH_SELECTION_LIMIT} sessions at a time.`;
      return;
    }
    portfolioBatchSelection = [...portfolioBatchSelection, key];
    refreshPortfolioQueue();
  };
  const clearPortfolioBatchSelection = () => {
    portfolioBatchSelection = [];
  };
  const syncPortfolioSelectionFromLocation = () => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const entryKey = String(params.get("portfolio_entry_key") || "").trim();
    if (entryKey && portfolioCards.some((card) => String(card.entry_key || "").trim() === entryKey)) {
      selectedPortfolioEntryKey = entryKey;
    }
  };
  const handlePortfolioCardAction = (card: SessionPortfolioCard | null | undefined) => {
    const shortcutKey = String(card?.shortcut_action_key || "").trim();
    if (shortcutKey === "restore") {
      handlePortfolioLifecycleAction(card, "restore");
      return;
    }
    if (shortcutKey === "archive") {
      handlePortfolioLifecycleAction(card, "archive");
      return;
    }
    const navigation = buildPortfolioNavigationTarget(card || {});
    if (navigation.route === "/shell") {
      selectPortfolioCard(card);
      portfolioNotice = "Showing the selected recent session summary from the cross-session queue.";
      if (typeof window !== "undefined") {
        window.requestAnimationFrame(() => {
          document.getElementById("session-portfolio-detail")?.scrollIntoView({ behavior: "smooth", block: "center" });
        });
      }
      return;
    }
    if (navigation.url) {
      maybeRecordDeferredResponseAnchor(card);
      window.location.href = navigation.url;
    }
  };
  const handlePortfolioShortlistAction = (
    cards: Array<SessionPortfolioCard | null | undefined>,
    action: "shortlist" | "clear_shortlist",
  ) => {
    const result = applyPortfolioShortcutMemoryAction(
      portfolioShortcutMemory,
      cards.filter(Boolean) as SessionPortfolioCard[],
      action,
    ) as {
      memory: { schema_version: number; sessions: Record<string, unknown> };
      changed?: boolean;
      blocked_reason?: string;
      notice?: string;
    };
    portfolioShortcutMemory = result.memory;
    persistPortfolioShortcutMemory(portfolioShortcutMemory);
    portfolioBatchError = String(result.blocked_reason || "").trim();
    portfolioBatchNotice = portfolioBatchError ? "" : String(result.notice || "").trim();
    if (result.changed) {
      portfolioNotice = "";
      refreshPortfolioQueue();
    }
  };
  const handlePortfolioLifecycleAction = (
    card: SessionPortfolioCard | null | undefined,
    action: "pin" | "unpin" | "archive" | "restore",
  ) => {
    const result = applyPortfolioLifecycleAction(portfolioLifecycleMemory, card || {}, action) as {
      memory: { schema_version: number; sessions: Record<string, unknown> };
      changed?: boolean;
      blocked_reason?: string;
      notice?: string;
    };
    portfolioLifecycleMemory = result.memory;
    persistPortfolioLifecycleMemory(portfolioLifecycleMemory);
    portfolioLifecycleError = String(result.blocked_reason || "").trim();
    portfolioLifecycleNotice = portfolioLifecycleError
      ? ""
      : String(result.notice || "").trim();
    if (result.changed) {
      portfolioNotice = "";
    }
    refreshPortfolioQueue();
  };
  const handlePortfolioBatchAction = (
    action:
      | "pin_selected"
      | "unpin_selected"
      | "archive_selected"
      | "restore_selected"
      | "shortlist_selected"
      | "clear_shortlist_selected",
  ) => {
    const selectedCards = portfolioCards.filter((card) =>
      portfolioBatchSelection.includes(portfolioSelectionKey(card)),
    );
    const actionState = (portfolioBatchSummary?.actions || {})[action] as {
      allowed?: boolean;
      blocked_reason?: string;
      detail?: string;
    };
    portfolioBatchNotice = "";
    portfolioBatchError = "";
    if (!actionState?.allowed) {
      portfolioBatchError = String(actionState?.blocked_reason || "That batch action is not available for the current selection.").trim();
      return;
    }
    if (action === "shortlist_selected" || action === "clear_shortlist_selected") {
      handlePortfolioShortlistAction(
        selectedCards,
        action === "shortlist_selected" ? "shortlist" : "clear_shortlist",
      );
      clearPortfolioBatchSelection();
      refreshPortfolioQueue();
      return;
    }
    const lifecycleAction =
      action === "pin_selected"
        ? "pin"
        : action === "unpin_selected"
          ? "unpin"
          : action === "archive_selected"
            ? "archive"
            : "restore";
    let nextMemory = portfolioLifecycleMemory;
    let changed = false;
    let blockedReason = "";
    const notices: string[] = [];
    for (const card of selectedCards) {
      const result = applyPortfolioLifecycleAction(nextMemory, card || {}, lifecycleAction) as {
        memory: { schema_version: number; sessions: Record<string, unknown> };
        changed?: boolean;
        blocked_reason?: string;
        notice?: string;
      };
      nextMemory = result.memory;
      changed = changed || Boolean(result.changed);
      if (result.notice) {
        notices.push(String(result.notice).trim());
      }
      if (result.blocked_reason) {
        blockedReason = String(result.blocked_reason).trim();
        break;
      }
    }
    portfolioLifecycleMemory = nextMemory;
    persistPortfolioLifecycleMemory(portfolioLifecycleMemory);
    portfolioBatchError = blockedReason;
    portfolioBatchNotice =
      blockedReason || !changed
        ? ""
        : notices[notices.length - 1] ||
          `${selectedCards.length} session${selectedCards.length === 1 ? "" : "s"} updated from the portfolio.`;
    clearPortfolioBatchSelection();
    refreshPortfolioQueue();
  };
  const applyCurrentPortfolioFilter = () => {
    const filtered = filterPortfolioSections(
      portfolioAllSections,
      portfolioGroupFilter,
    ) as {
      sections?: PortfolioSection[];
      cards?: SessionPortfolioCard[];
    };
    portfolioSections = Array.isArray(filtered.sections) ? filtered.sections : [];
    portfolioCards = Array.isArray(filtered.cards) ? filtered.cards : [];
    const selectedEntryKey = String(selectedPortfolioEntryKey || "").trim();
    if (
      selectedEntryKey &&
      portfolioCards.some(
        (card) => String(card.entry_key || "").trim() === selectedEntryKey,
      )
    ) {
      return;
    }
    selectedPortfolioEntryKey = String(
      portfolioCards[0]?.entry_key || portfolioAllCards[0]?.entry_key || "",
    ).trim();
  };
  const setPortfolioGroupFilter = (nextFilter: string) => {
    const allowed = PORTFOLIO_MANAGER_FILTERS.some(
      (group) => group.key === nextFilter,
    );
    portfolioGroupFilter = allowed ? nextFilter : "all";
    clearPortfolioBatchSelection();
    refreshPortfolioQueue();
  };
  const handlePortfolioManagerAction = (action: {
    key?: string;
    label?: string;
    detail?: string;
    mode?: string;
    filterKey?: string;
    targetCardKey?: string;
    targetCardKeys?: string[];
    batchAction?:
      | "pin_selected"
      | "unpin_selected"
      | "archive_selected"
      | "restore_selected"
      | "shortlist_selected"
      | "clear_shortlist_selected";
  } | null) => {
    if (!action) {
      return;
    }
    if (action.filterKey) {
      setPortfolioGroupFilter(String(action.filterKey || "all"));
    }
    if (action.mode === "focus_group") {
      portfolioBatchError = "";
      portfolioBatchNotice = String(action.detail || "").trim();
      return;
    }
    if (action.mode === "portfolio_batch" && action.batchAction) {
      portfolioBatchSelection = Array.isArray(action.targetCardKeys)
        ? action.targetCardKeys
            .map((value) => String(value || "").trim())
            .filter(Boolean)
            .slice(0, PORTFOLIO_BATCH_SELECTION_LIMIT)
        : [];
      if (!portfolioBatchSelection.length) {
        portfolioBatchError = "No matching sessions are available for that summary action right now.";
        portfolioBatchNotice = "";
        return;
      }
      refreshPortfolioQueue();
      handlePortfolioBatchAction(action.batchAction);
      return;
    }
    if (action.mode === "open_session") {
      const targetKey = String(action.targetCardKey || "").trim();
      const targetCard =
        portfolioAllCards.find(
          (card) => String(card.entry_key || "").trim() === targetKey,
        ) ||
        portfolioCards.find(
          (card) => String(card.entry_key || "").trim() === targetKey,
        ) ||
        null;
      if (!targetCard) {
        portfolioBatchError = "The recommended session is no longer visible in the current portfolio state.";
        portfolioBatchNotice = "";
        return;
      }
      selectedPortfolioEntryKey = String(targetCard.entry_key || "").trim();
      handlePortfolioCardAction(targetCard);
    }
  };
  const refreshPortfolioQueue = () => {
    let nextMemory = readStoredAttentionMemory();
    const currentEntry = buildHandoffMemoryEntry({
      longRunState: longRun,
      attentionSignal: longRun?.operator_guidance?.attention_signal,
      campaignHandoff: longRun?.operator_guidance?.campaign_handoff_summary,
      deltaSinceLastResume: longRun?.operator_guidance?.delta_since_last_resume,
    });
    if (currentEntry) {
      nextMemory = upsertHandoffMemory(nextMemory, currentEntry, {
        notificationSupport: { supported: false, permission: "default" },
      }).memory as { schema_version: number; sessions: Record<string, unknown> };
      persistAttentionMemory(nextMemory);
    }
    attentionMemory = nextMemory;
    const nextLifecycleMemory = readStoredPortfolioLifecycleMemory();
    portfolioLifecycleMemory = nextLifecycleMemory;
    const portfolio = buildSessionPortfolio(nextMemory, {
      currentSessionId: String(longRun?.long_run?.session_id || ""),
    }) as {
      cards?: SessionPortfolioCard[];
      bucket_counts?: Record<string, number>;
      recommendation?: PortfolioRecommendation;
    };
    const managedPortfolio = buildManagedSessionPortfolio(
      Array.isArray(portfolio.cards) ? portfolio.cards : [],
      portfolio.recommendation || null,
      nextLifecycleMemory,
      {
        currentSessionId: String(longRun?.long_run?.session_id || ""),
      },
    ) as {
      all_visible_cards?: SessionPortfolioCard[];
      sections?: PortfolioSection[];
      bucket_counts?: Record<string, number>;
      counts?: Record<string, number>;
      recommendation?: PortfolioRecommendation;
    };
    const nextShortcutMemory = readStoredPortfolioShortcutMemory();
    portfolioShortcutMemory = nextShortcutMemory;
    const nextDigestMemory = readStoredPortfolioDigestMemory();
    portfolioDigestMemory = nextDigestMemory;
    const actionView = buildPortfolioActionView(
      Array.isArray(managedPortfolio.sections) ? managedPortfolio.sections : [],
      managedPortfolio.recommendation || null,
      nextShortcutMemory,
      portfolioBatchSelection,
    ) as {
      cards?: SessionPortfolioCard[];
      sections?: PortfolioSection[];
      recommendation?: PortfolioRecommendation;
      batch?: PortfolioBatchSummary;
      action_rules?: PortfolioActionRule[];
    };
    portfolioAllCards = Array.isArray(actionView.cards) ? actionView.cards : [];
    portfolioAllSections = Array.isArray(actionView.sections) ? actionView.sections : [];
    portfolioBucketCounts = managedPortfolio.bucket_counts || {};
    portfolioLifecycleCounts = managedPortfolio.counts || {};
    portfolioRecommendation = actionView.recommendation || managedPortfolio.recommendation || null;
    portfolioBatchSummary = actionView.batch || null;
    portfolioActionRules = Array.isArray(actionView.action_rules) ? actionView.action_rules : [];
    const managerView = buildPortfolioManagerDashboard(
      portfolioAllCards,
      portfolioRecommendation,
      {
        batchLimit: PORTFOLIO_BATCH_SELECTION_LIMIT,
      },
    ) as {
      groupedCounts?: Array<{
        key: string;
        label: string;
        description: string;
        count: number;
        overlay?: boolean;
      }>;
      dashboardSummary?: typeof portfolioManagerSummary;
      summaryActions?: typeof portfolioSummaryActions;
    };
    portfolioGroupCounts = Array.isArray(managerView.groupedCounts)
      ? managerView.groupedCounts
      : [];
    portfolioManagerSummary = managerView.dashboardSummary || null;
    portfolioSummaryActions = Array.isArray(managerView.summaryActions)
      ? managerView.summaryActions
      : [];
    portfolioOperatorQueue = buildPortfolioOperatorQueue(
      portfolioAllCards,
      portfolioRecommendation,
    ) as PortfolioOperatorQueue;
    portfolioManagerDigest = buildPortfolioManagerDigest(
      portfolioAllCards,
      portfolioRecommendation,
      nextDigestMemory,
      {
        nowIso: new Date().toISOString(),
      },
    ) as PortfolioDigestSummary;
    portfolioManagerAgenda = buildPortfolioManagerAgenda(
      portfolioAllCards,
      portfolioRecommendation,
      nextDigestMemory,
      {
        nowIso: new Date().toISOString(),
      },
    ) as PortfolioManagerAgenda;
    portfolioDeferredWorkloadDigest = buildPortfolioDeferredWorkloadDigest(
      portfolioAllCards,
      portfolioRecommendation,
      nextDigestMemory,
      {
        nowIso: new Date().toISOString(),
      },
    ) as PortfolioDeferredWorkloadDigest;
    portfolioBatchSelection = portfolioBatchSelection.filter((value) =>
      portfolioAllCards.some(
        (card) => portfolioSelectionKey(card) === String(value || "").trim(),
      ),
    );
    applyCurrentPortfolioFilter();
    syncPortfolioSelectionFromLocation();
    if (
      !selectedPortfolioEntryKey ||
      !portfolioCards.some(
        (card) =>
          String(card.entry_key || "").trim() ===
          String(selectedPortfolioEntryKey || "").trim(),
      )
    ) {
      selectedPortfolioEntryKey = String(
        portfolioRecommendation?.target_entry_key ||
        portfolioCards[0]?.entry_key ||
        portfolioAllCards[0]?.entry_key ||
        "",
      ).trim();
    }
  };
  const governedReadinessMessage = (status: LaunchStatusSnapshot | null | undefined) => {
    const blockingReason = Array.isArray(status?.blocking_reasons) ? String(status?.blocking_reasons?.[0] || "").trim() : "";
    const detail = String(status?.operator_next_action_detail || "").trim();
    const currentProfile = textValue(status?.selected_execution_profile, "unknown");
    const expectedProfile = textValue(status?.expected_execution_profile, "bounded_active_workspace_coding");
    return [blockingReason || detail || "Governed execution is not ready.", `Saved profile: ${currentProfile}.`, `Expected profile: ${expectedProfile}.`].join(" ");
  };

  async function refreshState(soft = false) {
    try {
      state = await fetchOperatorState();
      if (!directivePathInput && state.directive?.path) directivePathInput = state.directive.path;
      loadIssue = "";
    } catch (err) {
      loadIssueTone = soft && state ? "warning" : "danger";
      loadIssue = soft && state
        ? "Live status is catching up. Showing the last confirmed snapshot."
        : `Status load failed: ${String((err as Error).message)}`;
    } finally {
      loading = false;
      refreshPortfolioQueue();
    }
  }

  async function refreshLongRunState(soft = false) {
    try {
      longRun = await fetchLongRunState();
    } catch (err) {
      if (!soft || !longRun) {
        loadIssueTone = soft && state ? "warning" : "danger";
        loadIssue = soft && state
          ? "Long-run status is catching up. Showing the last confirmed continuation snapshot."
          : `Long-run status failed: ${String((err as Error).message)}`;
      }
    } finally {
      refreshPortfolioQueue();
    }
  }

  onMount(async () => {
    await refreshState();
    await refreshLongRunState(true);
    closeRuntimeStream = openRuntimeEventStream({
      onOpen: () => (streamLive = true),
      onHeartbeat: (event) => (lastHeartbeatAt = event.generated_at || ""),
      onEvent: (event: RuntimeEventPayload) => {
        const label = textValue(event.message || event.event_type, "Runtime event");
        const detail = `${textValue(event.phase, "runtime")} · ${textValue(event.event_type, "event")}`;
        const raw = `${label} ${detail}`.toLowerCase();
        const tone: FeedTone = raw.includes("checkpoint") || raw.includes("accepted") || raw.includes("validated") ? "success" : raw.includes("review") || raw.includes("intervention") || raw.includes("pause") || raw.includes("halt") || raw.includes("error") ? "warning" : "info";
        pushFeedEntry(label, detail, tone, event.timestamp || event.generated_at || "");
      },
      onError: () => (streamLive = false),
    });
    refreshTimer = setInterval(async () => { await refreshState(true); await refreshLongRunState(true); }, 4000);
  });

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer);
    closeRuntimeStream?.();
  });

  const clearActionNotices = () => { actionMessage = ""; uploadNotice = ""; };
  const handleWorkspaceJump = () => (window.location.href = "/shell/workspace");

  async function handleDirectiveSelect() {
    if (!directivePathInput.trim()) return void (actionMessage = "Please provide a directive path before starting.");
    directiveBusy = true; clearActionNotices(); pushFeedEntry("Directive selection requested", directivePathInput.trim());
    try {
      const response = await selectDirective(directivePathInput.trim());
      actionMessage = response.message || "Directive updated from browser flow.";
      state = response.state || state;
      await refreshState(true);
      pushFeedEntry("Directive selected", textValue(response.state?.directive?.path || directivePathInput.trim()), "success");
    } catch (err) {
      actionMessage = `Directive selection failed: ${(err as Error).message}`;
      pushFeedEntry("Directive selection blocked", actionMessage, "warning");
    } finally { directiveBusy = false; }
  }

  async function handleDirectiveUpload() {
    if (!selectedFile) return void (uploadNotice = "No file selected.");
    directiveBusy = true; clearActionNotices(); pushFeedEntry("Directive upload requested", selectedFile.name);
    try {
      const response = await uploadDirective({ directive_upload: selectedFile });
      uploadNotice = response.ok ? `Uploaded: ${response.path}` : response.message;
      if (response.ok) { directivePathInput = response.path; selectedFile = null; pushFeedEntry("Directive uploaded", response.path, "success"); await refreshState(true); }
    } catch (err) {
      uploadNotice = `Upload failed: ${(err as Error).message}`;
      pushFeedEntry("Directive upload failed", uploadNotice, "warning");
    } finally { directiveBusy = false; }
  }

  async function handleValidateTrustedSource() {
    if (!secretProviderId.trim() && !secretCredential.trim()) return void (validationNotice = "Add at least a provider id or session credential to validate.");
    trustedSourceBusy = true; clearActionNotices(); pushFeedEntry("Trusted-source validation requested", textValue(secretProviderId.trim(), "openai_api"));
    try {
      const result = await validateTrustedSource({ provider_id: secretProviderId.trim(), provider_base_url: secretProviderBaseUrl.trim(), credential_value: secretCredential.trim(), credential_file: "" }) as { ok?: boolean; headline?: unknown; message?: unknown; status?: unknown; details?: unknown };
      const firstDetail = Array.isArray(result.details) ? String(result.details[0] || "").trim() : "";
      const failedHeadline = String(result.headline || result.message || result.status || "").trim();
      validationNotice = result.ok === true
        ? String(result.headline || "Trusted-source validation recorded for this session only.")
        : [failedHeadline, firstDetail].filter(Boolean).join(" ") || "Validation recorded.";
      pushFeedEntry(result.ok === true ? "Trusted-source validation accepted" : "Trusted-source validation recorded", validationNotice, result.ok === true ? "success" : "warning");
    } catch (err) {
      validationNotice = `Validation failed: ${(err as Error).message}`;
      pushFeedEntry("Trusted-source validation failed", validationNotice, "warning");
    } finally { secretCredential = ""; trustedSourceBusy = false; }
  }

  async function handleBootstrapStart() {
    if (!state?.operator_state?.directive_loaded && !directivePathInput.trim()) return void (actionMessage = "Load a directive before bootstrap initialization.");
    bootstrapBusy = true; clearActionNotices(); pushFeedEntry("Bootstrap requested", directivePathInput.trim() || state?.directive?.path || "");
    try {
      const response = await startBootstrap({ directive_path: directivePathInput.trim() || state?.directive?.path || "", state_root: "" });
      actionMessage = String(response.message || response.headline || "Bootstrap start attempted.");
      pushFeedEntry(response.ok ? "Bootstrap launch accepted" : "Bootstrap launch blocked", actionMessage, response.ok ? "success" : "warning");
      void refreshState(true);
      void refreshLongRunState(true);
    } catch (err) {
      actionMessage = `Bootstrap failed: ${(err as Error).message}`;
      pushFeedEntry("Bootstrap launch failed", actionMessage, "warning");
    } finally { bootstrapBusy = false; }
  }

  async function handleGovernedPrepare() {
    if (!state?.operator_state?.directive_loaded && !directivePathInput.trim()) return void (actionMessage = "Load a directive before preparing governed execution.");
    governedPrepBusy = true; clearActionNotices(); pushFeedEntry("Governed runtime preparation requested", directivePathInput.trim() || state?.directive?.path || "");
    try {
      const response = await prepareGovernedExecution({ directive_path: directivePathInput.trim() || state?.directive?.path || "" }) as { ok?: boolean; state?: OperatorState; governed?: LaunchStatusSnapshot; message?: unknown; headline?: unknown; details?: unknown };
      actionMessage = String(response.message || response.headline || "Governed runtime preparation attempted.");
      pushFeedEntry(response.ok ? "Governed runtime prepared" : "Governed runtime preparation blocked", actionMessage, response.ok ? "success" : "warning");
      if (response.state && typeof response.state === "object") state = response.state;
      void refreshState(true);
      void refreshLongRunState(true);
    } catch (err) {
      actionMessage = `Governed runtime preparation failed: ${(err as Error).message}`;
      pushFeedEntry("Governed runtime preparation failed", actionMessage, "warning");
    } finally { governedPrepBusy = false; }
  }

  async function handleGovernedStart() {
    governedBusy = true; clearActionNotices();
    try {
      const latestGoverned = await fetchGovernedStatus();
      if (!latestGoverned?.can_launch) {
        actionMessage = governedReadinessMessage(latestGoverned);
        pushFeedEntry("Governed launch blocked", actionMessage, "warning");
        await refreshState(true);
        return;
      }
      pushFeedEntry("Governed launch requested", directivePathInput.trim() || state?.directive?.path || "");
      const response = await startGoverned({ directive_path: directivePathInput.trim() || state?.directive?.path || "", state_root: "" });
      actionMessage = response.ok
        ? String(response.message || response.headline || "Governed launch accepted. Opening workspace.")
        : String(response.message || response.headline || "Governed execution attempted.");
      pushFeedEntry(response.ok ? "Governed launch accepted" : "Governed launch blocked", actionMessage, response.ok ? "success" : "warning");
      if (response.ok && response.next_path) return void (window.location.href = String(response.next_path));
      await refreshState(true);
    } catch (err) {
      actionMessage = `Governed execution failed: ${(err as Error).message}`;
      pushFeedEntry("Governed launch failed", actionMessage, "warning");
    } finally { governedBusy = false; }
  }

  $: operatorState = state?.operator_state || {};
  $: bootstrapStatus = state?.launch_readiness?.bootstrap || null;
  $: governedStatus = state?.launch_readiness?.governed || null;
  $: longRunSession = longRun?.long_run || null;
  $: selectedPortfolioCard =
    portfolioCards.find((card) => String(card.entry_key || "").trim() === String(selectedPortfolioEntryKey || "").trim()) ||
    portfolioCards[0] ||
    null;
  $: selectedPortfolioNavigation = selectedPortfolioCard
    ? buildPortfolioNavigationTarget(selectedPortfolioCard)
    : null;
  $: readyText = operatorState?.directive_loaded ? "Directive present" : "Directive missing";
  $: streamStatus = streamLive ? "Live startup feed connected" : lastHeartbeatAt ? "Heartbeat observed" : "Connecting to live startup feed";
  $: trustedSourceGuidance = operatorState?.directive_loaded ? "Directive is already loaded. Session-only external validation remains available until launch begins, or you can leave this slice local-only." : "You may validate a session-only external provider before or after selecting the directive. If you are staying local-only, you can skip this section.";
  $: governedPrepRecommended = Boolean(state?.operator_state?.directive_loaded && governedStatus && !governedStatus.can_launch && !governedStatus.profile_matches_selected_action);
  $: governedWorkspaceMaterialized = Boolean(state?.artifacts?.workspace_id && state?.artifacts?.workspace_root);
  $: externalAdapterView = buildExternalAdapterStatusView(state?.external_adapter);
  $: externalAdapterReviewView = buildExternalAdapterReviewStatusView(state?.external_adapter_review);
  $: controllerIsolationView = buildControllerIsolationStatusView(state?.controller_isolation);
  $: readOnlyAdapterView = buildReadOnlyAdapterStatusView(state?.read_only_adapter);
  $: operatorAlertsView = buildOperatorAlertsStatusView(state?.operator_alerts);
  $: observabilityView = buildObservabilityStatusView(state?.observability);
</script>

<main class="page-shell">
  <header class="hero"><h1>nOVALi Core</h1><p>Truth-aligned shell for directive load, bootstrap, governed execution, and bounded continuation.</p></header>
  <section class="chips">
    <div><span>Directive</span><strong>{readyText}</strong></div>
    <div><span>Workflow</span><strong>{state?.session?.workflow_stage || "unknown"}</strong></div>
    <div><span>Runtime</span><strong>{state?.runtime?.run_status || "unknown"}</strong></div>
    <div><span>Long-run</span><strong>{textValue(longRunSession?.lifecycle_state, "not_started")}</strong></div>
  </section>
  {#if loadIssue}<div class={`notice ${loadIssueTone}`}>{loadIssue}</div>{/if}
  {#if actionMessage}<div class="notice">{actionMessage}</div>{/if}
  {#if loading}<div class="notice">Loading current operator truth...</div>{/if}

  <section class="panel" id="session-portfolio" data-testid="session-portfolio-section">
    <div class="row">
      <div>
        <h2>Session portfolio queue</h2>
        <p class="muted">Recent session cards are assembled from persisted backend-derived handoff packets plus live current-session truth. Use this queue to decide what to open next before dropping into a specific workspace.</p>
      </div>
      <span class="pill">{portfolioCards.length} recent session{portfolioCards.length === 1 ? "" : "s"}</span>
    </div>
    {#if portfolioRecommendation}
      <div class="callout portfolio-recommendation" data-testid="session-portfolio-recommendation">
        <div class="row">
          <div>
            <strong>{textValue(portfolioRecommendation?.label, "Open the next truthful session")}</strong>
            <p class="muted">{textValue(portfolioRecommendation?.detail, "The queue is ranked from persisted session handoffs and the live current session.")}</p>
          </div>
          {#if portfolioRecommendation?.navigation?.route === "/shell/workspace"}
            <button
              class="btn warning"
              type="button"
              data-testid="session-portfolio-recommendation-open"
              on:click={() => handlePortfolioCardAction(portfolioRecommendation?.shortlist?.[0] || selectedPortfolioCard)}
            >
              {textValue(portfolioRecommendation?.navigation?.label, "Open next session")}
            </button>
          {/if}
        </div>
        {#if portfolioRecommendation?.shortlist?.length > 1}
          <p class="muted">Shortlist: {portfolioRecommendation.shortlist.map((card) => textValue(card.session_handle, "session")).join(" · ")}</p>
        {/if}
      </div>
    {/if}
    {#if portfolioNotice}
      <div class="notice">{portfolioNotice}</div>
    {/if}
    {#if portfolioLifecycleError}
      <div class="notice warning">{portfolioLifecycleError}</div>
    {/if}
    {#if portfolioLifecycleNotice}
      <div class="notice">{portfolioLifecycleNotice}</div>
    {/if}
    {#if portfolioBatchError}
      <div class="notice warning">{portfolioBatchError}</div>
    {/if}
    {#if portfolioBatchNotice}
      <div class="notice">{portfolioBatchNotice}</div>
    {/if}
    {#if portfolioDigestNotice}
      <div class="notice">{portfolioDigestNotice}</div>
    {/if}
    <div class="callout portfolio-digest" data-testid="observability-status-panel">
      <div class="row">
        <div>
          <strong>Observability</strong>
          <p class="muted" data-testid="observability-status-headline">
            {observabilityView.label}
          </p>
      <p class="muted" data-testid="observability-status-detail">
        {observabilityView.detail}
      </p>
      <p class="muted" data-testid="observability-live-probe-label">
        {observabilityView.liveProbeLabel}
      </p>
      <p class="muted" data-testid="observability-live-probe-detail">
        {observabilityView.liveProbeDetail}
      </p>
      <p class="muted" data-testid="observability-visibility-probe-label">
        {observabilityView.visibilityProbeLabel}
      </p>
      <p class="muted" data-testid="observability-visibility-probe-detail">
        {observabilityView.visibilityProbeDetail}
      </p>
      <p class="muted" data-testid="observability-dockerized-probe-label">
        {observabilityView.dockerizedProbeLabel}
      </p>
      <p class="muted" data-testid="observability-dockerized-probe-detail">
        {observabilityView.dockerizedProbeDetail}
      </p>
      <p class="muted" data-testid="observability-portal-confirmation">
        {observabilityView.portalConfirmationLabel}
      </p>
        </div>
        <span class={`pill deferred-pressure-band ${observabilityView.statusKey}`}>
          {observabilityView.label}
        </span>
      </div>
      <p class="muted" data-testid="observability-service-name">
        Service: {observabilityView.serviceName}
      </p>
      <p class="muted" data-testid="observability-endpoint-hint">
        Endpoint hint: {observabilityView.endpointHint}
      </p>
      <p class="muted" data-testid="observability-redaction-mode">
        Redaction: {observabilityView.redactionMode}
      </p>
      <p class="muted" data-testid="observability-active-protocol">
        Protocol: {observabilityView.activeProtocol}
      </p>
      <p class="muted" data-testid="observability-dockerized-protocol">
        Dockerized protocol: {observabilityView.dockerizedProtocol}
      </p>
      <p class="muted" data-testid="observability-dockerized-endpoint-mode">
        Dockerized endpoint mode: {observabilityView.dockerizedEndpointMode}
      </p>
      <p class="muted" data-testid="observability-dockerized-runtime">
        Dockerized runtime proven: {observabilityView.dockerizedRuntimeProven ? "yes" : "no"}
      </p>
      <p class="muted" data-testid="observability-dockerized-mapping">
        Dockerized mapping: {observabilityView.dockerizedMappingComplete ? "complete" : "incomplete"}
      </p>
      <p class="muted" data-testid="observability-service-name-safe">
        LogicMonitor-safe service name: {observabilityView.serviceNameLmSafe ? "yes" : "no"}
      </p>
      {#if observabilityView.serviceNameWarning}
        <p class="muted" data-testid="observability-service-name-warning">
          {observabilityView.serviceNameWarning}
        </p>
      {/if}
      <p class="muted" data-testid="observability-lm-mapping">
        LogicMonitor mapping: {observabilityView.lmMappingComplete ? "complete" : "incomplete"}
        {#if !observabilityView.lmMappingComplete}
          {" "}({observabilityView.lmMappingMissing.join(", ") || "missing host.name, ip, or resource.type"})
        {/if}
      </p>
      {#if observabilityView.visibilityProbeId}
        <p class="muted" data-testid="observability-visibility-probe-id">
          Trace visibility proof id: {observabilityView.visibilityProbeId}
        </p>
      {/if}
      {#if observabilityView.dockerizedProbeId}
        <p class="muted" data-testid="observability-dockerized-probe-id">
          Dockerized trace proof id: {observabilityView.dockerizedProbeId}
        </p>
      {/if}
      <p class="muted" data-testid="observability-portal-confirmation-detail">
        {observabilityView.portalConfirmationDetail}
      </p>
      {#if observabilityView.alertCandidates?.length}
        {#each observabilityView.alertCandidates as alertCandidate}
          <p class="muted" data-testid={`observability-alert-${textValue(alertCandidate.alert_key, "candidate")}`}>
            Alert candidate: {textValue(alertCandidate.label, "Unnamed alert")} · {textValue(alertCandidate.detail, "")}
          </p>
        {/each}
      {/if}
      {#each observabilityView.policyNotes as policyNote}
        <p class="muted">{policyNote}</p>
      {/each}
      {#if observabilityView.lastErrorType}
        <p class="muted" data-testid="observability-last-error">
          Last error type: {observabilityView.lastErrorType}
        </p>
      {/if}
      {#if observabilityView.lastShutdownResult && observabilityView.lastShutdownResult !== "unknown"}
        <p class="muted" data-testid="observability-last-shutdown">
          Last shutdown result: {observabilityView.lastShutdownResult} · timeouts recorded{" "}
          {observabilityView.lastShutdownTimeoutCount}
          {#if observabilityView.lastShutdownErrorType}
            {" "}· error type {observabilityView.lastShutdownErrorType}
          {/if}
        </p>
      {/if}
      {#if observabilityView.expectedTimeoutTracebackSuppressed}
        <p class="muted" data-testid="observability-timeout-suppressed">
          Expected timeout traceback was suppressed and preserved as bounded evidence.
        </p>
      {/if}
    </div>
    <div class="callout portfolio-digest" data-testid="external-adapter-status-panel">
      <div class="row">
        <div>
          <strong>External adapter membrane</strong>
          <p class="muted" data-testid="external-adapter-status-headline">
            {externalAdapterView.label}
          </p>
          <p class="muted" data-testid="external-adapter-proof-label">
            {externalAdapterView.proofLabel}
          </p>
          <p class="muted" data-testid="external-adapter-status-detail">
            {externalAdapterView.detail}
          </p>
        </div>
        <span class={`pill deferred-pressure-band ${externalAdapterView.statusKey}`}>
          {externalAdapterView.label}
        </span>
      </div>
      <p class="muted" data-testid="external-adapter-name">
        Adapter: {externalAdapterView.adapterName} ({externalAdapterView.adapterKind})
      </p>
      <p class="muted" data-testid="external-adapter-mode">
        Mode: {externalAdapterView.mode}
      </p>
      <p class="muted" data-testid="external-adapter-schema">
        Schema: {externalAdapterView.schemaVersion}
      </p>
      <p class="muted" data-testid="external-adapter-last-action">
        Last action status: {externalAdapterView.lastActionStatus}
      </p>
      <p class="muted" data-testid="external-adapter-replay-count">
        Replay packets: {externalAdapterView.replayPacketCount}
      </p>
      <p class="muted" data-testid="external-adapter-kill-switch">
        Kill switch state: {externalAdapterView.killSwitchState}
      </p>
      <p class="muted" data-testid="external-adapter-telemetry-enabled">
        Telemetry enabled during latest status snapshot: {externalAdapterView.telemetryEnabled ? "yes" : "no"}
      </p>
      <p class="muted" data-testid="external-adapter-portal-confirmation">
        {externalAdapterView.portalConfirmationLabel}
      </p>
      {#if externalAdapterView.lastReplayPacketId}
        <p class="muted" data-testid="external-adapter-last-replay-id">
          Last replay packet id: {externalAdapterView.lastReplayPacketId}
        </p>
      {/if}
      {#if externalAdapterView.lastReviewRequired}
        <p class="muted" data-testid="external-adapter-review-required">
          Review reasons: {externalAdapterView.reviewReasons.join(", ") || "review required"}
        </p>
      {/if}
      {#each externalAdapterView.policyNotes as policyNote}
        <p class="muted">{policyNote}</p>
      {/each}
    </div>
    <div class="callout portfolio-digest" data-testid="external-adapter-review-status-panel">
      <div class="row">
        <div>
          <strong>External adapter review</strong>
          <p class="muted" data-testid="external-adapter-review-headline">
            {externalAdapterReviewView.label}
          </p>
          <p class="muted" data-testid="external-adapter-review-detail">
            {externalAdapterReviewView.detail}
          </p>
        </div>
        <span class={`pill deferred-pressure-band ${externalAdapterReviewView.statusKey}`}>
          {externalAdapterReviewView.label}
        </span>
      </div>
      <p class="muted" data-testid="external-adapter-review-counts">
        Pending: {externalAdapterReviewView.pendingCount} · Escalated: {externalAdapterReviewView.escalatedCount} · Evidence missing: {externalAdapterReviewView.evidenceMissingCount}
      </p>
      <p class="muted" data-testid="external-adapter-review-rollback">
        Rollback possible: {externalAdapterReviewView.rollbackPossible ? "yes" : "no"} · Rollback candidate: {externalAdapterReviewView.rollbackCandidate ? "yes" : "no"} · Checkpoint available: {externalAdapterReviewView.checkpointAvailable ? "yes" : "no"}
      </p>
      <p class="muted" data-testid="external-adapter-review-restore">
        Restore allowed: {externalAdapterReviewView.restoreAllowed ? "yes" : "no"} · Restore performed: {externalAdapterReviewView.restorePerformed ? "yes" : "no"} · Ambiguity: {externalAdapterReviewView.ambiguityLevel}
      </p>
      {#if externalAdapterReviewView.lastReviewItemId}
        <p class="muted" data-testid="external-adapter-review-last-item">
          Last review item: {externalAdapterReviewView.lastReviewItemId}
        </p>
      {/if}
      {#if externalAdapterReviewView.lastReplayPacketId}
        <p class="muted" data-testid="external-adapter-review-last-replay">
          Replay packet hint: {externalAdapterReviewView.lastReplayPacketId}
        </p>
      {/if}
      {#if externalAdapterReviewView.lastRollbackAnalysisId}
        <p class="muted" data-testid="external-adapter-review-last-rollback">
          Rollback analysis hint: {externalAdapterReviewView.lastRollbackAnalysisId}
        </p>
      {/if}
      {#if externalAdapterReviewView.lastCheckpointRef}
        <p class="muted" data-testid="external-adapter-review-checkpoint">
          Checkpoint reference: {externalAdapterReviewView.lastCheckpointRef}
        </p>
      {/if}
      {#if externalAdapterReviewView.lastOperatorActionRequired}
        <p class="muted" data-testid="external-adapter-review-operator-action">
          Operator action required: {externalAdapterReviewView.lastOperatorActionRequired}
        </p>
      {/if}
      {#if externalAdapterReviewView.lastReviewItem}
        <p class="muted" data-testid="external-adapter-review-last-reasons">
          Review reasons: {(externalAdapterReviewView.lastReviewItem.review_reasons || []).join(", ") || "review required"}
        </p>
      {/if}
      {#each externalAdapterReviewView.advisoryCopy as policyNote}
        <p class="muted">{policyNote}</p>
      {/each}
    </div>
    <div class="callout portfolio-digest" data-testid="controller-isolation-status-panel">
      <div class="row">
        <div>
          <strong>Controller isolation</strong>
          <p class="muted" data-testid="controller-isolation-headline">
            {controllerIsolationView.label}
          </p>
          <p class="muted" data-testid="controller-isolation-detail">
            {controllerIsolationView.detail}
          </p>
        </div>
        <span class={`pill deferred-pressure-band ${controllerIsolationView.statusKey}`}>
          {controllerIsolationView.label}
        </span>
      </div>
      <p class="muted" data-testid="controller-isolation-lanes">
        Lanes: {controllerIsolationView.laneCount} · Roles: {controllerIsolationView.laneRoles.join(", ") || "director, sovereign_good, sovereign_dark"}
      </p>
      <p class="muted" data-testid="controller-isolation-checks">
        Namespace separation: {controllerIsolationView.namespaceSeparationLabel} · Hidden scratchpad: {controllerIsolationView.hiddenScratchpadLabel} · Director channel: {controllerIsolationView.directorChannelLabel} · Telemetry identity: {controllerIsolationView.telemetryIdentityLabel}
      </p>
      <p class="muted" data-testid="controller-isolation-findings">
        Identity bleed findings: {controllerIsolationView.findingCount} · High: {controllerIsolationView.highCount} · Critical: {controllerIsolationView.criticalCount}
      </p>
      <p class="muted" data-testid="controller-isolation-messages">
        Cross-lane messages: proposed {controllerIsolationView.proposedCount} · approved {controllerIsolationView.approvedCount} · blocked {controllerIsolationView.blockedCount} · unauthorized {controllerIsolationView.unauthorizedCount}
      </p>
      <p class="muted" data-testid="controller-isolation-portal-confirmation">
        {controllerIsolationView.portalConfirmationLabel}
      </p>
      {#if controllerIsolationView.latestReviewTicketId}
        <p class="muted" data-testid="controller-isolation-latest-review-ticket">
          Latest review ticket: {controllerIsolationView.latestReviewTicketId}
        </p>
      {/if}
      {#if controllerIsolationView.latestFindingId}
        <p class="muted" data-testid="controller-isolation-latest-finding">
          Latest finding: {controllerIsolationView.latestFindingId}
        </p>
      {/if}
      {#if controllerIsolationView.latestMessageId}
        <p class="muted" data-testid="controller-isolation-latest-message">
          Latest cross-lane message: {controllerIsolationView.latestMessageId}
        </p>
      {/if}
      {#if controllerIsolationView.latestReplayPacketId}
        <p class="muted" data-testid="controller-isolation-latest-replay">
          Latest replay packet: {controllerIsolationView.latestReplayPacketId}
        </p>
      {/if}
      {#if controllerIsolationView.latestReviewTicket}
        <p class="muted" data-testid="controller-isolation-review-reasons">
          Review reasons: {(controllerIsolationView.latestReviewTicket.review_reasons || []).join(", ") || "review required"}
        </p>
      {/if}
      {#each controllerIsolationView.policyNotes as policyNote}
        <p class="muted">{policyNote}</p>
      {/each}
    </div>
    <div class="callout portfolio-digest" data-testid="read-only-adapter-status-panel">
      <div class="row">
        <div>
          <strong>Read-only adapter</strong>
          <p class="muted" data-testid="read-only-adapter-headline">
            {readOnlyAdapterView.label}
          </p>
          <p class="muted" data-testid="read-only-adapter-detail">
            {readOnlyAdapterView.detail}
          </p>
        </div>
        <span class={`pill deferred-pressure-band ${readOnlyAdapterView.statusKey}`}>
          {readOnlyAdapterView.label}
        </span>
      </div>
      <p class="muted" data-testid="read-only-adapter-identity">
        Adapter: {readOnlyAdapterView.adapterName} ({readOnlyAdapterView.adapterKind}) - mode {readOnlyAdapterView.mode}
      </p>
      <p class="muted" data-testid="read-only-adapter-latest">
        Latest snapshot: {readOnlyAdapterView.latestSnapshotId || "n/a"} - replay {readOnlyAdapterView.latestReplayPacketId || "n/a"} - review {readOnlyAdapterView.latestReviewTicketId || "n/a"}
      </p>
      <p class="muted" data-testid="read-only-adapter-validation">
        Validation: {readOnlyAdapterView.validationStatus} - integrity: {readOnlyAdapterView.integrityStatus} - lane attribution: {readOnlyAdapterView.laneAttributionStatus}
      </p>
      <p class="muted" data-testid="read-only-adapter-counts">
        Observations: {readOnlyAdapterView.observationCount} - bad snapshots: {readOnlyAdapterView.badSnapshotCount} - stale: {readOnlyAdapterView.staleSnapshotCount} - conflicts: {readOnlyAdapterView.conflictingObservationCount}
      </p>
      <p class="muted" data-testid="read-only-adapter-mutation">
        Mutation refused count: {readOnlyAdapterView.mutationRefusedCount} - mutation allowed: no
      </p>
      <p class="muted" data-testid="read-only-adapter-portal-confirmation">
        {readOnlyAdapterView.portalConfirmationLabel}
      </p>
      {#if readOnlyAdapterView.latestRollbackAnalysisId}
        <p class="muted" data-testid="read-only-adapter-last-rollback">
          Rollback analysis hint: {readOnlyAdapterView.latestRollbackAnalysisId}
        </p>
      {/if}
      {#if readOnlyAdapterView.latestMutationRefusalId}
        <p class="muted" data-testid="read-only-adapter-last-refusal">
          Latest mutation refusal: {readOnlyAdapterView.latestMutationRefusalId}
        </p>
      {/if}
      {#if readOnlyAdapterView.reviewRequired}
        <p class="muted" data-testid="read-only-adapter-review-reasons">
          Review reasons: {readOnlyAdapterView.reviewReasons.join(", ") || "review required"}
        </p>
      {/if}
      {#each readOnlyAdapterView.policyNotes as policyNote}
        <p class="muted">{policyNote}</p>
      {/each}
    </div>
    <div class="callout portfolio-digest" data-testid="operator-alerts-status-panel">
      <div class="row">
        <div>
          <strong>Operator alerts</strong>
          <p class="muted" data-testid="operator-alerts-headline">
            {operatorAlertsView.label}
          </p>
          <p class="muted" data-testid="operator-alerts-detail">
            {operatorAlertsView.detail}
          </p>
        </div>
        <span class={`pill deferred-pressure-band ${operatorAlertsView.statusKey}`}>
          {operatorAlertsView.label}
        </span>
      </div>
      <p class="muted" data-testid="operator-alerts-counts">
        Total: {operatorAlertsView.alertCount} · Raised: {operatorAlertsView.raisedCount} · Blocked: {operatorAlertsView.blockedCount} · Critical: {operatorAlertsView.criticalCount}
      </p>
      <p class="muted" data-testid="operator-alerts-severity-counts">
        High: {operatorAlertsView.highCount} · Warning: {operatorAlertsView.warningCount} · Acknowledged: {operatorAlertsView.acknowledgedCount} · Reviewed: {operatorAlertsView.reviewedCount}
      </p>
      <p class="muted" data-testid="operator-alerts-source-counts">
        Read-only alerts: {operatorAlertsView.readOnlyAlertCount} · Telemetry candidates: {operatorAlertsView.telemetryAlertCandidateCount} · Identity bleed alerts: {operatorAlertsView.identityBleedAlertCount}
      </p>
      <p class="muted" data-testid="operator-alerts-telemetry-shutdown">
        Telemetry shutdown alerts: {operatorAlertsView.telemetryShutdownAlertCount}
        {#if operatorAlertsView.latestTelemetryShutdownAlertId}
          {" "}· latest {operatorAlertsView.latestTelemetryShutdownAlertId}
        {/if}
      </p>
      <p class="muted" data-testid="operator-alerts-portal-confirmation">
        {operatorAlertsView.portalConfirmationLabel}
      </p>
      {#if operatorAlertsView.latestAlertId}
        <p class="muted" data-testid="operator-alerts-latest">
          Latest alert: {operatorAlertsView.latestAlertId} · type {operatorAlertsView.latestAlertType || "n/a"} · severity {operatorAlertsView.latestSeverity || "n/a"} · status {operatorAlertsView.latestStatus || "n/a"}
        </p>
      {/if}
      {#if operatorAlertsView.latestEvidenceBundleId}
        <p class="muted" data-testid="operator-alerts-latest-evidence">
          Evidence bundle hint: {operatorAlertsView.latestEvidenceBundleId}
        </p>
      {/if}
      {#if operatorAlertsView.latestOperatorActionRequired}
        <p class="muted" data-testid="operator-alerts-operator-action">
          Operator action required: {operatorAlertsView.latestOperatorActionRequired}
        </p>
      {/if}
      {#if operatorAlertsView.latestAcknowledgedAt}
        <p class="muted" data-testid="operator-alerts-acknowledged-at">
          Latest acknowledgement: {formatRecordedAt(operatorAlertsView.latestAcknowledgedAt)}
        </p>
      {/if}
      {#if operatorAlertsView.latestReviewedAt}
        <p class="muted" data-testid="operator-alerts-reviewed-at">
          Latest review: {formatRecordedAt(operatorAlertsView.latestReviewedAt)}
        </p>
      {/if}
      {#if operatorAlertsView.availableActions.length}
        <p class="muted" data-testid="operator-alerts-available-actions">
          Local evidence actions: {operatorAlertsView.availableActions.map((action) => action.label || action.action_id || "action").join(", ")}
        </p>
      {/if}
      {#if operatorAlertsView.latestAlert?.summary_redacted}
        <p class="muted" data-testid="operator-alerts-summary">
          Latest alert summary: {operatorAlertsView.latestAlert.summary_redacted}
        </p>
      {/if}
      {#each operatorAlertsView.policyNotes as policyNote}
        <p class="muted">{policyNote}</p>
      {/each}
    </div>
    {#if portfolioManagerDigest}
      <div class="callout portfolio-digest" data-testid="manager-digest-panel">
        <div class="row">
          <div>
            <strong>Manager digest</strong>
            <p class="muted" data-testid="manager-digest-headline">
              {textValue(
                portfolioManagerDigest.headline,
                "Manager digest anchor is ready for future shell comparisons.",
              )}
            </p>
            <p class="muted" data-testid="manager-digest-anchor">
              {textValue(portfolioManagerDigest.anchor?.basis_label, "Digest anchor")} ·
              {textValue(
                portfolioManagerDigest.anchor?.detail,
                "Mark the digest checked to store the next manager-check comparison anchor for future shell summaries.",
              )}
            </p>
          </div>
          <button
            class="btn secondary"
            type="button"
            data-testid="manager-digest-mark-checked"
            on:click={() => recordPortfolioManagerTouch()}
          >
            Mark digest checked
          </button>
        </div>
        <p>
          <strong data-testid="manager-digest-recommended-action">
            {textValue(
              portfolioManagerDigest.recommendedNextAction?.label,
              textValue(
                portfolioManagerSummary?.recommendationLabel,
                "Review the current operator queue leader",
              ),
            )}
          </strong>
          ·
          {textValue(
            portfolioManagerDigest.recommendedNextAction?.detail,
            textValue(
              portfolioManagerSummary?.recommendationDetail,
              "Open the strongest truthful next session before lower-priority portfolio work.",
            ),
          )}
        </p>
        <p class="muted">
          {textValue(
            portfolioManagerDigest.meaningfulProgressSummary,
            "No new cross-session progress markers are visible beyond the current digest anchor.",
          )}
        </p>
        {#if portfolioManagerDigest.counters?.length}
          <div class="chips compact">
            {#each portfolioManagerDigest.counters as counter}
              <div data-testid={"manager-digest-counter-" + textValue(counter.key, "counter")}>
                <span>{textValue(counter.label, "Counter")}</span>
                <strong>{textValue(counter.count, "0")}</strong>
                <p class="muted">{textValue(counter.detail, "No bounded detail is recorded for this counter.")}</p>
              </div>
            {/each}
          </div>
        {/if}
        {#if portfolioManagerDigest.advancedSessions?.length}
          <p class="muted"><strong>Progress since the digest anchor:</strong></p>
          <div class="toolbar">
            {#each portfolioManagerDigest.advancedSessions.slice(0, 3) as card}
              <button
                class="btn secondary"
                type="button"
                data-testid="manager-digest-progress-item"
                data-session-id={textValue(card.session_id, "")}
                on:click={() => handlePortfolioCardAction(card)}
              >
                {textValue(card.session_handle, "session")} · {textValue(card.next_action_label, "Open session")}
              </button>
            {/each}
          </div>
        {/if}
        {#if portfolioManagerDigest.unresolvedGovernanceItems?.length}
          <p class="muted">
            <strong>Unresolved governance / stop items:</strong>
            {portfolioManagerDigest.unresolvedGovernanceItems.join(" · ")}
          </p>
        {/if}
      </div>
    {/if}
    {#if portfolioDeferredWorkloadDigest}
      <div class="callout portfolio-digest" data-testid="deferred-workload-digest-panel">
        <div class="row">
          <div>
            <strong>Deferred workload digest</strong>
            <p class="muted" data-testid="deferred-workload-digest-headline">
              {textValue(
                portfolioDeferredWorkloadDigest.headline,
                "Deferred workload is currently clear.",
              )}
            </p>
            <p class="muted" data-testid="deferred-workload-digest-anchor">
              {textValue(
                portfolioDeferredWorkloadDigest.anchor?.basis_label,
                "Since last manager check",
              )} ·
              {textValue(
                portfolioDeferredWorkloadDigest.anchor?.detail,
                "Deferred workload changes are compared against the current manager-check anchor.",
              )}
            </p>
            {#if portfolioDeferredWorkloadDigest.pressureBand}
              <div class="row">
                <span
                  class={`pill deferred-pressure-band ${textValue(
                    portfolioDeferredWorkloadDigest.pressureBand.key,
                    "low",
                  )}`}
                  data-testid="deferred-workload-pressure-band"
                >
                  {textValue(
                    portfolioDeferredWorkloadDigest.pressureBand.label,
                    "Low deferred pressure",
                  )}
                </span>
                <span class="muted" data-testid="deferred-workload-pressure-trend">
                  {textValue(
                    portfolioDeferredWorkloadDigest.pressureBand.trendLabel,
                    "Pressure stable",
                  )}
                </span>
              </div>
              <p class="muted" data-testid="deferred-workload-pressure-band-detail">
                {textValue(
                  portfolioDeferredWorkloadDigest.pressureBand.detail,
                  "No deferred-pressure band detail is recorded yet.",
                )}
              </p>
            {/if}
            {#if portfolioDeferredWorkloadDigest.responsePolicy?.primary}
              <div class="callout" data-testid="deferred-workload-response-primary">
                <strong>
                  {textValue(
                    portfolioDeferredWorkloadDigest.responsePolicy.primary?.label,
                    "No deferred response is recommended yet.",
                  )}
                </strong>
                <p class="muted">
                  {textValue(
                    portfolioDeferredWorkloadDigest.responsePolicy.primary?.detail,
                    "No deferred-response detail is recorded yet.",
                  )}
                </p>
              </div>
            {/if}
            {#if portfolioDeferredWorkloadDigest.responsePolicy?.detail}
              <p class="muted" data-testid="deferred-workload-response-detail">
                {textValue(
                  portfolioDeferredWorkloadDigest.responsePolicy?.detail,
                  "No deferred-response mix detail is recorded yet.",
                )}
              </p>
            {/if}
            {#if portfolioDeferredWorkloadDigest.responseOutcome}
              <div class="callout" data-testid="deferred-workload-response-outcome">
                <strong>
                  {textValue(
                    portfolioDeferredWorkloadDigest.responseOutcome.label,
                    "No deferred response outcome is recorded yet.",
                  )}
                </strong>
                <p class="muted" data-testid="deferred-workload-response-outcome-detail">
                  {textValue(
                    portfolioDeferredWorkloadDigest.responseOutcome.detail,
                    "No deferred response outcome detail is recorded yet.",
                  )}
                </p>
                <p class="muted" data-testid="deferred-workload-response-outcome-basis">
                  Compared {textValue(
                    portfolioDeferredWorkloadDigest.responseOutcome.basisLabel,
                    "since the last manager check",
                  ).toLowerCase()}.
                </p>
                <p class="muted" data-testid="deferred-workload-response-outcome-prior-band">
                  Prior pressure: {textValue(
                    portfolioDeferredWorkloadDigest.responseOutcome.previousBandLabel,
                    "Unknown",
                  )}
                </p>
                <p class="muted" data-testid="deferred-workload-response-outcome-current-band">
                  Current pressure: {textValue(
                    portfolioDeferredWorkloadDigest.responseOutcome.currentBandLabel,
                    "Unknown",
                  )}
                </p>
                <p class="muted" data-testid="deferred-workload-response-outcome-prior-response">
                  Prior response: {textValue(
                    portfolioDeferredWorkloadDigest.responseOutcome.previousResponseLabel,
                    "No prior response recorded",
                  )}
                </p>
              </div>
            {/if}
          </div>
          <span class="pill">
            {textValue(portfolioDeferredWorkloadDigest.counts?.total_deferred_items, "0")} deferred workload
          </span>
        </div>
        <p class="muted" data-testid="deferred-workload-digest-pressure">
          {textValue(
            portfolioDeferredWorkloadDigest.detail,
            "No deferred workload pressure change is recorded yet.",
          )}
        </p>
        <p class="muted" data-testid="deferred-workload-digest-current">
          {textValue(
            portfolioDeferredWorkloadDigest.currentReason,
            "No deferred-return item currently explains the active agenda ordering.",
          )}
        </p>
        {#if portfolioDeferredWorkloadDigest.returnBasisSummary?.length}
          <div class="chips compact">
            {#each portfolioDeferredWorkloadDigest.returnBasisSummary as item}
              <div
                data-testid="deferred-workload-return-basis-item"
                data-basis-key={textValue(item.key, "")}
              >
                <span>{textValue(item.label, "Return basis")}</span>
                <strong>{textValue(item.count, "0")}</strong>
                <p class="muted">{textValue(item.detail, "No bounded detail is recorded for this return basis.")}</p>
              </div>
            {/each}
          </div>
        {/if}
        {#if portfolioDeferredWorkloadDigest.responsePolicy?.shortlist?.length}
          <div class="chips compact">
            {#each portfolioDeferredWorkloadDigest.responsePolicy.shortlist as item}
              <div
                data-testid="deferred-workload-response-item"
                data-response-key={textValue(item.key, "")}
              >
                <span>{textValue(item.label, "Deferred response")}</span>
                <p class="muted">{textValue(item.detail, "No bounded response detail is stored yet.")}</p>
              </div>
            {/each}
          </div>
        {/if}
        {#if portfolioDeferredWorkloadDigest.counters?.length}
          <div class="chips compact">
            {#each portfolioDeferredWorkloadDigest.counters as counter}
              <div data-testid={"deferred-workload-counter-" + textValue(counter.key, "counter")}>
                <span>{textValue(counter.label, "Counter")}</span>
                <strong>{textValue(counter.count, "0")}</strong>
                <p class="muted">{textValue(counter.detail, "No bounded detail is recorded for this deferred counter.")}</p>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
    {#if portfolioManagerAgenda}
      <div class="callout portfolio-digest" data-testid="manager-agenda-panel">
        <div class="row">
          <div>
            <strong>Manager agenda</strong>
            <p class="muted" data-testid="manager-agenda-anchor">
              {textValue(portfolioManagerAgenda.anchor?.basis_label, "Since last manager check")} ·
              {#if portfolioManagerAgenda.checked_at}
                Manager check recorded {relativeTime(textValue(portfolioManagerAgenda.checked_at, ""))}
              {:else}
                No manager check recorded yet for this browser.
              {/if}
            </p>
          </div>
          <span class="pill">
            {textValue(portfolioManagerAgenda.counts?.actionable_now, "0")} actionable now
          </span>
        </div>
        <p class="muted" data-testid="manager-agenda-throughput">
          {textValue(
            portfolioManagerAgenda.throughput?.headline,
            "No manager throughput delta is recorded yet.",
          )} · {textValue(
            portfolioManagerAgenda.throughput?.detail,
            "Handle, defer, or reopen one manager item and return here to see what changed.",
          )}
        </p>
        <div class="portfolio-grid">
          <article class="portfolio-card" data-testid="manager-agenda-current">
            <p class="muted">Current item</p>
            <strong>{textValue(portfolioManagerAgenda.currentAgendaSummary, "No current manager agenda item is pending.")}</strong>
            {#if portfolioManagerAgenda.currentItem}
              <p class="path muted">{textValue(portfolioManagerAgenda.currentItem.session_id, "n/a")}</p>
              <p>{textValue(portfolioManagerAgenda.currentItem.current_blocker, "No blocker summary stored.")}</p>
              <button
                class="btn warning"
                type="button"
                data-testid="manager-agenda-current-action"
                on:click={() => handlePortfolioCardAction(portfolioManagerAgenda.currentItem)}
              >
                {portfolioShortcutActionLabel(portfolioManagerAgenda.currentItem)}
              </button>
              {#if canDeferManagerItem(portfolioManagerAgenda.currentItem)}
                <div class="toolbar">
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="manager-agenda-current-defer-next-check"
                    on:click={() => handlePortfolioManagerDefer(portfolioManagerAgenda.currentItem, "next_manager_check")}
                  >
                    Snooze until next manager check
                  </button>
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="manager-agenda-current-defer-until-reopen"
                    on:click={() => handlePortfolioManagerDefer(portfolioManagerAgenda.currentItem, "until_reopen")}
                  >
                    Defer until reopened
                  </button>
                </div>
              {/if}
            {:else}
              <p class="muted">Nothing currently requires a queue-first manager action.</p>
            {/if}
          </article>
          <article class="portfolio-card" data-testid="manager-agenda-next">
            <p class="muted">Next up</p>
            <strong>{textValue(portfolioManagerAgenda.nextAgendaSummary, "No next-up manager item is queued yet.")}</strong>
            {#if portfolioManagerAgenda.nextItem}
              <p class="path muted">{textValue(portfolioManagerAgenda.nextItem.session_id, "n/a")}</p>
              <p>{textValue(portfolioManagerAgenda.nextItem.current_blocker, "No blocker summary stored.")}</p>
              <button
                class="btn secondary"
                type="button"
                data-testid="manager-agenda-next-action"
                on:click={() => handlePortfolioCardAction(portfolioManagerAgenda.nextItem)}
              >
                {portfolioShortcutActionLabel(portfolioManagerAgenda.nextItem)}
              </button>
              {#if canDeferManagerItem(portfolioManagerAgenda.nextItem)}
                <div class="toolbar">
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="manager-agenda-next-defer-next-check"
                    on:click={() => handlePortfolioManagerDefer(portfolioManagerAgenda.nextItem, "next_manager_check")}
                  >
                    Snooze until next manager check
                  </button>
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="manager-agenda-next-defer-until-reopen"
                    on:click={() => handlePortfolioManagerDefer(portfolioManagerAgenda.nextItem, "until_reopen")}
                  >
                    Defer until reopened
                  </button>
                </div>
              {/if}
            {:else}
              <p class="muted">No second agenda item is queued behind the current leader.</p>
            {/if}
          </article>
          <article class="portfolio-card" data-testid="manager-agenda-completed">
            <p class="muted">Completed since last check</p>
            <strong>{textValue(portfolioManagerAgenda.completedAgendaSummary, "No agenda item has been completed since the last manager check yet.")}</strong>
            {#if portfolioManagerAgenda.justCompletedItem}
              <p class="path muted">{textValue(portfolioManagerAgenda.justCompletedItem.session_id, "n/a")}</p>
              <p>
                {textValue(
                  portfolioManagerAgenda.justCompletedItem.completion_outcome_detail,
                  "This handled item no longer leads the current agenda.",
                )}
              </p>
              <p>
                <strong>Now:</strong>
                {textValue(
                  portfolioManagerAgenda.justCompletedItem.resulting_state_label,
                  "No resulting bounded session state was summarized.",
                )}
              </p>
            {:else}
              <p class="muted">Handle one agenda item and return here to see it move into bounded completed history.</p>
            {/if}
          </article>
          <article class="portfolio-card" data-testid="manager-agenda-overdue">
            <p class="muted">Overdue / stale</p>
            <strong>{textValue(portfolioManagerAgenda.overdueAgendaSummary, "No overdue manager item is currently queued.")}</strong>
            {#if portfolioManagerAgenda.overdueItems?.length}
              <p class="path muted">{textValue(portfolioManagerAgenda.overdueItems[0].session_id, "n/a")}</p>
              <p>{textValue(portfolioManagerAgenda.overdueItems[0].current_blocker, "No blocker summary stored.")}</p>
              <p class="muted">{textValue(portfolioManagerAgenda.overdueItems[0].agenda_state_detail, "This overdue item remains unresolved in the active agenda.")}</p>
            {:else}
              <p class="muted">No previously reviewed item has aged into overdue manager prominence.</p>
            {/if}
          </article>
          <article class="portfolio-card" data-testid="manager-agenda-due">
            <p class="muted">Due to return now</p>
            <strong>{textValue(portfolioManagerAgenda.dueAgendaSummary, "No deferred item is due to return right now.")}</strong>
            {#if portfolioManagerAgenda.dueItems?.length}
              {#each portfolioManagerAgenda.dueItems as item}
                <div
                  class="callout"
                  data-testid="manager-due-queue-item"
                  data-session-id={textValue(item.session_id, "n/a")}
                >
                  <p class="path muted">{textValue(item.session_id, "n/a")}</p>
                  <p><strong>{textValue(item.session_handle, "session")}</strong> · {textValue(item.current_blocker, "No blocker summary stored.")}</p>
                  <p class="muted">{textValue(item.manager_return_reason_label, textValue(item.agenda_state_detail, "Returned item is active again."))}</p>
                </div>
              {/each}
            {:else}
              <p class="muted">Deferred work only competes with the active agenda after its return trigger is actually met.</p>
            {/if}
          </article>
          <article class="portfolio-card" data-testid="manager-agenda-deferred">
            <p class="muted">Deferred queue</p>
            <strong>{textValue(portfolioManagerAgenda.deferredAgendaSummary, "No deferred manager item is currently parked out of the active agenda.")}</strong>
            {#if portfolioManagerAgenda.deferredItems?.length}
              {#each portfolioManagerAgenda.deferredItems as item}
                <div
                  class="callout"
                  data-testid="manager-deferred-queue-item"
                  data-session-id={textValue(item.session_id, "n/a")}
                >
                  <p class="path muted">{textValue(item.session_id, "n/a")}</p>
                  <p><strong>{textValue(item.session_handle, "session")}</strong> · {textValue(item.current_blocker, "No blocker summary stored.")}</p>
                  <p class="muted">{textValue(item.manager_defer_basis_label, "Deferred")}</p>
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="manager-agenda-deferred-reopen"
                    on:click={() => handlePortfolioManagerReopen(item)}
                  >
                    Reopen now
                  </button>
                </div>
              {/each}
            {:else}
              <p class="muted">Deferred manager items stay reviewable here and only return when their explicit bounded policy says they should.</p>
            {/if}
          </article>
          <article class="portfolio-card" data-testid="manager-agenda-reopened">
            <p class="muted">Reopened manually</p>
            <strong>{textValue(portfolioManagerAgenda.reopenedAgendaSummary, "No deferred item has been reopened manually since the current manager check.")}</strong>
            {#if portfolioManagerAgenda.reopenedItems?.length}
              {#each portfolioManagerAgenda.reopenedItems as item}
                <div
                  class="callout"
                  data-testid="manager-reopened-queue-item"
                  data-session-id={textValue(item.session_id, "n/a")}
                >
                  <p class="path muted">{textValue(item.session_id, "n/a")}</p>
                  <p><strong>{textValue(item.session_handle, "session")}</strong> · {textValue(item.current_blocker, "No blocker summary stored.")}</p>
                  <p class="muted">{textValue(item.agenda_state_detail, "Returned to the active agenda manually.")}</p>
                </div>
              {/each}
            {:else}
              <p class="muted">Manually reopened items are called out here so they do not masquerade as brand-new blockers.</p>
            {/if}
          </article>
        </div>
        <div class="chips compact">
          <div data-testid="manager-agenda-count-completed_since_last_check">
            <span>Completed since last check</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.completed_since_last_check, "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-still_pending_from_before_last_check">
            <span>Still pending from before last check</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.still_pending_from_before_check, "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-new_since_last_check">
            <span>New since last check</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.new_since_last_check, "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-overdue_manager_items">
            <span>Overdue manager items</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.overdue_manager_items, "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-due_now">
            <span>Due now from deferred queue</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.due_now, "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-reopened_items">
            <span>Reopened manually</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.reopened_items, "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-deferred_items">
            <span>Deferred items</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.deferred_items, "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-due_returned_since_last_check">
            <span>Due returned since last check</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.due_returned_since_last_check, portfolioManagerAgenda.counts?.returned_from_snooze_since_last_check || "0")}</strong>
          </div>
          <div data-testid="manager-agenda-count-reopened_since_last_check">
            <span>Reopened since last check</span>
            <strong>{textValue(portfolioManagerAgenda.counts?.reopened_since_last_check, "0")}</strong>
          </div>
        </div>
        <p class="muted">{textValue(portfolioManagerAgenda.rationale, "The agenda keeps the current and next manager item visible above the full queue.")}</p>
      </div>
    {/if}
    {#if portfolioOperatorQueue?.sections?.length}
      <div class="callout" data-testid="operator-queue-panel">
        <div class="row">
          <div>
            <strong>Operator queue</strong>
            <p class="muted">
              Blocking review/intervention work, stale unresolved items, resumable sessions, and safe-to-ignore history are separated here so the shell can answer what needs you now.
            </p>
          </div>
          <span class="pill">{textValue(portfolioOperatorQueue.counts?.actionable_now, "0")} actionable now</span>
        </div>
        {#if portfolioOperatorQueue.groupedCounts?.length}
          <p class="muted">
            {portfolioOperatorQueue.groupedCounts
              .map((group) => `${textValue(group.label, "Queue")}: ${textValue(group.count, "0")}`)
              .join(" · ")}
          </p>
        {/if}
        {#each portfolioOperatorQueue.sections as section}
          <div
            class="portfolio-group operator-queue-group"
            data-testid="operator-queue-section"
            data-queue-group={textValue(section.key, "queue")}
          >
            <div class="row">
              <div>
                <strong>{textValue(section.label, "Queue section")}</strong>
                <p class="muted">{textValue(section.detail, "This queue section groups the same operator-facing state.")}</p>
              </div>
              <span class="pill">{textValue(section.count, "0")}</span>
            </div>
            <div class="portfolio-grid">
              {#each section.cards || [] as card}
                <article
                  class="portfolio-card operator-queue-card"
                  data-testid="operator-queue-card"
                  data-session-id={textValue(card.session_id, "")}
                  data-queue-group={textValue(section.key, "queue")}
                >
                  <div class="event-topline">
                    <strong>{textValue(card.session_handle, "session")}</strong>
                    <span class={`event-chip ${textValue(card.attention_state_tone, "info")}`}>{textValue(card.attention_state_label, "Clear")}</span>
                    <span class={`event-chip ${textValue(card.operator_queue_tone, "info")}`}>{textValue(card.operator_queue_label, textValue(section.label, "Queue"))}</span>
                    <span class={`event-chip ${textValue(card.lifecycle_section_tone, "info")}`}>{textValue(card.lifecycle_section_label, "Recent")}</span>
                  </div>
                  <p class="path muted">{textValue(card.session_id, "n/a")}</p>
                  <p><strong>Blocker:</strong> {textValue(card.current_blocker, "No current blocker recorded.")}</p>
                  <p><strong>Next action:</strong> {textValue(card.next_action_label, "Open session")} · {textValue(card.next_action_detail, "No bounded next-action detail is stored for this session yet.")}</p>
                  <p><strong>Cycle / checkpoints:</strong> {textValue(card.current_cycle, "0")}/{textValue(card.max_cycles, "0")} · checkpoints {textValue(card.checkpoint_count, "0")}</p>
                  <p><strong>Headroom:</strong> {textValue(card.policy_headroom_summary, textValue(card.settings_summary, "No policy/headroom summary stored for this session yet."))}</p>
                  <p><strong>Since last touch:</strong> {textValue(card.what_changed_summary, "No compact delta is stored for this session yet.")}</p>
                  {#if portfolioManagerAgendaState(card)}
                    <p><strong>Manager status:</strong> {portfolioManagerAgendaState(card)}</p>
                  {/if}
                  <div class="toolbar">
                    <button
                      class={card.shortcut_action_mode === "open_session" ? "btn warning" : "btn secondary"}
                      type="button"
                      data-testid="operator-queue-card-action"
                      on:click={() => handlePortfolioCardAction(card)}
                    >
                      {portfolioShortcutActionLabel(card)}
                    </button>
                    <button
                      class="btn secondary"
                      type="button"
                      on:click={() => selectPortfolioCard(card)}
                    >
                      Inspect summary
                    </button>
                  </div>
                </article>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {/if}
    {#if portfolioAllCards.length}
      <div class="chips portfolio-chips">
        <div><span>Action queue</span><strong>{portfolioLifecycleCounts.active || 0}</strong></div>
        <div><span>Pinned</span><strong>{portfolioLifecycleCounts.pinned || 0}</strong></div>
        <div><span>Recent</span><strong>{portfolioLifecycleCounts.recent || 0}</strong></div>
        <div><span>Archived</span><strong>{portfolioLifecycleCounts.archived || 0}</strong></div>
      </div>
      <div class="callout" data-testid="session-portfolio-manager-dashboard">
        <div class="row">
          <div>
            <strong>Cross-session manager dashboard</strong>
            <p class="muted">
              {textValue(
                portfolioManagerSummary?.detail,
                "Use this manager summary to see what needs attention now, what can be handled safely here in the portfolio, and what still requires opening the selected session.",
              )}
            </p>
          </div>
          <span class="pill">
            Filter:
            {textValue(
              PORTFOLIO_MANAGER_FILTERS.find((group) => group.key === portfolioGroupFilter)?.label,
              "All visible",
            )}
          </span>
        </div>
        <p data-testid="session-portfolio-manager-headline">
              <strong>{textValue(portfolioManagerSummary?.title, "No immediate blocking action is required.")}</strong>
        </p>
        {#if portfolioManagerSummary?.dominantAction}
          <div class="row" data-testid="session-portfolio-manager-dominant-action">
            <div>
              <strong>{textValue(portfolioManagerSummary?.recommendationLabel || portfolioManagerSummary?.dominantAction?.label, "Next action")}</strong>
              <p class="muted">
                {textValue(
                  portfolioManagerSummary?.recommendationDetail || portfolioManagerSummary?.dominantAction?.detail,
                  "This is the strongest truthful next move across the current portfolio state.",
                )}
              </p>
            </div>
            <button
              class="btn warning"
              type="button"
              data-testid={"session-portfolio-summary-action-" + textValue(portfolioManagerSummary?.dominantAction?.key, "dominant")}
              on:click={() => handlePortfolioManagerAction(portfolioManagerSummary?.dominantAction || null)}
            >
              {textValue(portfolioManagerSummary?.dominantAction?.label, "Open next")}
            </button>
          </div>
        {/if}
        <div class="toolbar">
          <button
            class={portfolioGroupFilter === "all" ? "btn warning" : "btn secondary"}
            type="button"
            data-testid="session-portfolio-group-filter-all"
            on:click={() => setPortfolioGroupFilter("all")}
          >
            All visible ({portfolioAllCards.length})
          </button>
          {#each portfolioGroupCounts as group}
            <button
              class={portfolioGroupFilter === group.key ? "btn warning" : "btn secondary"}
              type="button"
              data-testid={"session-portfolio-group-filter-" + textValue(group.key, "group")}
              title={textValue(group.description, "Filter the portfolio to this grouped bucket.")}
              on:click={() => setPortfolioGroupFilter(textValue(group.key, "all"))}
            >
              {textValue(group.label, "Group")} ({textValue(group.count, "0")})
            </button>
          {/each}
        </div>
        <p class="muted" data-testid="session-portfolio-grouped-counts-summary">
          {portfolioGroupCounts
            .map((group) => `${textValue(group.label, "Group")}: ${textValue(group.count, "0")}`)
            .join(" · ")}
        </p>
        {#if portfolioManagerSummary?.followupActions?.length}
          <p class="muted"><strong>Follow-up candidates:</strong> Open or focus these next after the dominant action if they still matter.</p>
          <div class="toolbar">
            {#each portfolioManagerSummary.followupActions as action}
              <button
                class="btn secondary"
                type="button"
                data-testid={"session-portfolio-summary-action-" + textValue(action.key, "followup")}
                on:click={() => handlePortfolioManagerAction(action)}
              >
                {textValue(action.label, "Open next")}
              </button>
            {/each}
          </div>
        {/if}
        {#if portfolioManagerSummary?.housekeepingActions?.length}
          <p class="muted"><strong>Safe portfolio actions:</strong> These stay bounded to shell-level housekeeping and never approve review-gated continuation for you.</p>
          <div class="toolbar">
            {#each portfolioManagerSummary.housekeepingActions as action}
              <button
                class="btn secondary"
                type="button"
                data-testid={"session-portfolio-summary-action-" + textValue(action.key, "housekeeping")}
                on:click={() => handlePortfolioManagerAction(action)}
              >
                {textValue(action.label, "Portfolio action")}
              </button>
            {/each}
          </div>
        {/if}
        {#if portfolioSummaryActions.length}
          <p class="muted">
            Summary action palette:
            {portfolioSummaryActions
              .map((action) => textValue(action.label, "Action"))
              .join(" · ")}
          </p>
        {/if}
      </div>
      <div class="callout">
        Portfolio hygiene stays local to this browser. Pinning improves findability, archiving demotes non-actionable sessions from the primary queue, and current blocking/resumable sessions remain discoverable until backend truth changes.
      </div>
      {#if portfolioBatchSummary}
        <div class="callout" data-testid="session-portfolio-action-summary">
          <div class="row">
            <div>
              <strong>Portfolio shortcuts and bounded batch triage</strong>
              <p class="muted">Safe here in the portfolio: pin, unpin, archive, restore, and shortlist. Still requires opening the session: review-gated approvals, intervention resolution, and same-session continuation.</p>
            </div>
            <span class="pill">{textValue(portfolioBatchSummary.selection_count, "0")} selected</span>
          </div>
          {#if portfolioBatchSummary?.safe_batch_shortcuts?.length}
            <p class="muted">
              Batch-ready housekeeping:
              {portfolioBatchSummary.safe_batch_shortcuts
                .map((shortcut) => `${textValue(shortcut.label, "Action")} (${textValue(shortcut.eligible_count, "0")})`)
                .join(" · ")}
            </p>
          {/if}
          {#if portfolioActionRules.length}
            <div class="toolbar">
              {#each portfolioActionRules as rule}
                <span class="pill" title={textValue(rule.detail, "Portfolio action rule.")}>{textValue(rule.label, "Rule")}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
      {#if (portfolioBatchSummary?.selection_count || 0) > 0}
        <div class="callout" data-testid="session-portfolio-batch-toolbar">
          <div class="row">
            <div>
              <strong>Batch triage selection</strong>
              <p class="muted">
                {textValue(portfolioBatchSummary?.selection_count, "0")} session{Number(portfolioBatchSummary?.selection_count || 0) === 1 ? "" : "s"} selected
                {#if portfolioBatchSummary?.selection_summary}
                  : {portfolioBatchSummary.selection_summary}
                {/if}
              </p>
            </div>
            <button class="btn subtle" type="button" data-testid="session-portfolio-batch-clear" on:click={clearPortfolioBatchSelection}>
              Clear selection
            </button>
          </div>
          <div class="toolbar">
            <button
              class="btn secondary"
              type="button"
              data-testid="session-portfolio-batch-pin"
              disabled={!portfolioBatchSummary?.actions?.pin_selected?.allowed}
              title={textValue(portfolioBatchSummary?.actions?.pin_selected?.blocked_reason, "Pin the selected sessions.")}
              on:click={() => handlePortfolioBatchAction("pin_selected")}
            >
              {textValue(portfolioBatchSummary?.actions?.pin_selected?.label, "Pin selected")}
            </button>
            <button
              class="btn secondary"
              type="button"
              data-testid="session-portfolio-batch-unpin"
              disabled={!portfolioBatchSummary?.actions?.unpin_selected?.allowed}
              title={textValue(portfolioBatchSummary?.actions?.unpin_selected?.blocked_reason, "Unpin the selected sessions.")}
              on:click={() => handlePortfolioBatchAction("unpin_selected")}
            >
              {textValue(portfolioBatchSummary?.actions?.unpin_selected?.label, "Unpin selected")}
            </button>
            <button
              class="btn secondary"
              type="button"
              data-testid="session-portfolio-batch-archive"
              disabled={!portfolioBatchSummary?.actions?.archive_selected?.allowed}
              title={textValue(portfolioBatchSummary?.actions?.archive_selected?.blocked_reason, "Archive completed or historical sessions from the queue.")}
              on:click={() => handlePortfolioBatchAction("archive_selected")}
            >
              {textValue(portfolioBatchSummary?.actions?.archive_selected?.label, "Archive selected")}
            </button>
            <button
              class="btn secondary"
              type="button"
              data-testid="session-portfolio-batch-restore"
              disabled={!portfolioBatchSummary?.actions?.restore_selected?.allowed}
              title={textValue(portfolioBatchSummary?.actions?.restore_selected?.blocked_reason, "Restore archived sessions to the queue.")}
              on:click={() => handlePortfolioBatchAction("restore_selected")}
            >
              {textValue(portfolioBatchSummary?.actions?.restore_selected?.label, "Restore selected")}
            </button>
            <button
              class="btn secondary"
              type="button"
              data-testid="session-portfolio-batch-shortlist"
              disabled={!portfolioBatchSummary?.actions?.shortlist_selected?.allowed}
              title={textValue(portfolioBatchSummary?.actions?.shortlist_selected?.blocked_reason, "Shortlist the selected sessions for review next.")}
              on:click={() => handlePortfolioBatchAction("shortlist_selected")}
            >
              {textValue(portfolioBatchSummary?.actions?.shortlist_selected?.label, "Shortlist selected")}
            </button>
            <button
              class="btn secondary"
              type="button"
              data-testid="session-portfolio-batch-clear-shortlist"
              disabled={!portfolioBatchSummary?.actions?.clear_shortlist_selected?.allowed}
              title={textValue(portfolioBatchSummary?.actions?.clear_shortlist_selected?.blocked_reason, "Remove shortlist state from the selected sessions.")}
              on:click={() => handlePortfolioBatchAction("clear_shortlist_selected")}
            >
              {textValue(portfolioBatchSummary?.actions?.clear_shortlist_selected?.label, "Clear shortlist")}
            </button>
          </div>
          <p class="muted">
            Batch actions stay bounded to {textValue(portfolioBatchSummary?.max_selection, String(PORTFOLIO_BATCH_SELECTION_LIMIT))} sessions at a time. Review approvals and intervention resolutions never batch here.
          </p>
        </div>
      {/if}
      {#if !portfolioSections.length}
        <div class="callout">
          No sessions match the current grouped filter. Choose another dashboard bucket or return to <strong>All visible</strong>.
        </div>
      {/if}
      {#each portfolioSections as section}
        <div
          class="portfolio-group"
          data-testid="session-portfolio-lifecycle-section"
          data-portfolio-section={textValue(section.key, "recent")}
        >
          <div class="row">
            <div>
              <h3>{textValue(section.label, "Portfolio section")}</h3>
              <p class="muted">{textValue(section.detail, "Sessions in this section share the same portfolio lifecycle role.")}</p>
            </div>
            <span class="pill">{section.cards?.length || 0}</span>
          </div>
          <div class="portfolio-grid">
            {#each section.cards || [] as card}
              <article
                class:selected-portfolio-card={String(card.entry_key || "").trim() === String(selectedPortfolioEntryKey || "").trim()}
                class="portfolio-card"
                data-testid="session-portfolio-card"
                data-session-id={textValue(card.session_id, "")}
                data-queue-bucket={textValue(card.queue_bucket, "clear")}
                data-lifecycle-section={textValue(card.lifecycle_section, "recent")}
                data-pinned={card.pinned ? "true" : "false"}
                data-archived={card.archived ? "true" : "false"}
                data-shortlisted={card.shortlisted ? "true" : "false"}
                data-batch-selected={isPortfolioCardSelected(card) ? "true" : "false"}
                data-shortcut-mode={textValue(card.shortcut_action_mode, "open_session")}
                data-shortcut-key={textValue(card.shortcut_action_key, "")}
                data-current-session={card.current_session ? "true" : "false"}
                id={portfolioCardId(card)}
              >
                <div class="event-topline">
                  <strong>{textValue(card.session_handle, "session")}</strong>
                  <span class={`event-chip ${textValue(card.attention_state_tone, "info")}`}>{textValue(card.attention_state_label, "Clear")}</span>
                  <span class="event-chip phase">{textValue(card.current_or_recent_label, "Recent session")}</span>
                  {#if card.pinned}
                    <span class="event-chip info">Pinned</span>
                  {/if}
                  {#if card.shortlisted}
                    <span class="event-chip info">Review next</span>
                  {/if}
                  <span class={`event-chip ${textValue(card.lifecycle_section_tone, "info")}`}>{textValue(card.lifecycle_section_label, "Recent")}</span>
                </div>
                <p class="path muted">{textValue(card.session_id, "n/a")}</p>
                <p><strong>Lifecycle:</strong> {textValue(card.state_label, "Unknown")} · stop {textValue(card.stop_reason, "none")}</p>
                <p><strong>Portfolio state:</strong> {textValue(card.lifecycle_section_label, "Recent")} · bucket {textValue(card.queue_bucket_label, "Clear")}</p>
                <p><strong>Blocker:</strong> {textValue(card.current_blocker, "No current blocker recorded.")}</p>
                <p><strong>Next action:</strong> {textValue(card.next_action_label, "Open session")} · {textValue(card.next_action_detail, "No bounded next-action detail is stored for this session yet.")}</p>
                <p><strong>Shortcut:</strong> {portfolioShortcutActionLabel(card)} · {textValue(card.shortcut_action_detail, "Use the session link for the next truthful step.")}</p>
                <p><strong>Cycle / checkpoints:</strong> {textValue(card.current_cycle, "0")}/{textValue(card.max_cycles, "0")} · checkpoints {textValue(card.checkpoint_count, "0")}</p>
                <p><strong>Checkpoint:</strong> {textValue(card.checkpoint_id, "n/a")} · {formatRecordedAt(card.checkpoint_at)}</p>
                <p><strong>Headroom:</strong> {textValue(card.policy_headroom_summary, textValue(card.settings_summary, "No policy/headroom summary stored for this session yet."))}</p>
                <p><strong>Since last touch:</strong> {textValue(card.what_changed_summary, "No compact delta is stored for this session yet.")}</p>
                <div class="toolbar">
                  <button
                    class="btn subtle"
                    type="button"
                    data-testid="session-portfolio-card-select"
                    on:click|stopPropagation={() => togglePortfolioBatchSelection(card)}
                  >
                    {isPortfolioCardSelected(card) ? "Deselect" : "Select for batch"}
                  </button>
                  <button
                    class="btn subtle"
                    type="button"
                    on:click|stopPropagation={() => selectPortfolioCard(card)}
                  >
                    Inspect summary
                  </button>
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="session-portfolio-card-pin"
                    disabled={!card.can_pin}
                    on:click|stopPropagation={() => handlePortfolioLifecycleAction(card, card.pinned ? "unpin" : "pin")}
                  >
                    {portfolioPinActionLabel(card)}
                  </button>
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="session-portfolio-card-archive"
                    disabled={!card.archived && !card.can_archive}
                    title={textValue(card.lifecycle_blocked_reason, "Move this session into the archive section.")}
                    on:click|stopPropagation={() => handlePortfolioLifecycleAction(card, card.archived ? "restore" : "archive")}
                  >
                    {portfolioLifecycleActionLabel(card)}
                  </button>
                  <button
                    class="btn secondary"
                    type="button"
                    data-testid="session-portfolio-card-shortlist"
                    disabled={card.archived}
                    title={card.archived ? "Restore archived sessions before changing shortlist state." : textValue(card.shortcut_action_detail, "Shortlist this session for review next.")}
                    on:click|stopPropagation={() => handlePortfolioShortlistAction([card], card.shortlisted ? "clear_shortlist" : "shortlist")}
                  >
                    {textValue(card.shortlist_action_label, "Shortlist for review next")}
                  </button>
                  <button
                    class={card.shortcut_action_mode === "open_session" ? "btn warning" : "btn secondary"}
                    type="button"
                    data-testid="session-portfolio-card-open"
                    on:click|stopPropagation={() => handlePortfolioCardAction(card)}
                  >
                    {portfolioShortcutActionLabel(card)}
                  </button>
                </div>
              </article>
            {/each}
          </div>
        </div>
      {/each}
      {#if selectedPortfolioCard}
        <div class="details-panel" id="session-portfolio-detail" data-testid="session-portfolio-detail">
          <summary>Selected session handoff</summary>
          <p><strong>Session:</strong> {textValue(selectedPortfolioCard.session_handle, "session")} · {textValue(selectedPortfolioCard.session_id, "n/a")}</p>
          <p><strong>Queue bucket:</strong> {textValue(selectedPortfolioCard.queue_bucket_label, "Clear")} · {textValue(selectedPortfolioCard.current_or_recent_label, "Recent session")}</p>
          <p><strong>Portfolio lifecycle:</strong> {textValue(selectedPortfolioCard.lifecycle_section_label, "Recent")} · pinned {String(!!selectedPortfolioCard.pinned)} · archived {String(!!selectedPortfolioCard.archived)}</p>
          <p><strong>Current blocker:</strong> {textValue(selectedPortfolioCard.current_blocker, "No current blocker recorded.")}</p>
          <p><strong>Portfolio shortcut:</strong> {portfolioShortcutActionLabel(selectedPortfolioCard)} · {textValue(selectedPortfolioCard.shortcut_action_detail, "Use the next truthful session surface for this action.")}</p>
          <p><strong>Next likely stop:</strong> {textValue(selectedPortfolioCard.next_stop_boundary_label, "n/a")} · {textValue(selectedPortfolioCard.next_stop_boundary_summary, "No bounded next-stop detail is stored for this session yet.")}</p>
          <p><strong>Resume outlook:</strong> {String(!!selectedPortfolioCard.resume_ready_after_next_action)}</p>
          <p><strong>Recent delta:</strong> {textValue(selectedPortfolioCard.what_changed_summary, "No recent delta is stored for this session yet.")}</p>
          <div class="toolbar">
            <button
              class="btn secondary"
              type="button"
              disabled={!selectedPortfolioCard.can_pin}
              on:click={() => handlePortfolioLifecycleAction(selectedPortfolioCard, selectedPortfolioCard.pinned ? "unpin" : "pin")}
            >
              {portfolioPinActionLabel(selectedPortfolioCard)}
            </button>
            <button
              class="btn secondary"
              type="button"
              disabled={!selectedPortfolioCard.archived && !selectedPortfolioCard.can_archive}
              title={textValue(selectedPortfolioCard.lifecycle_blocked_reason, "Move this session into the archive section.")}
              on:click={() => handlePortfolioLifecycleAction(selectedPortfolioCard, selectedPortfolioCard.archived ? "restore" : "archive")}
            >
              {portfolioLifecycleActionLabel(selectedPortfolioCard)}
            </button>
            <button
              class="btn secondary"
              type="button"
              disabled={selectedPortfolioCard.archived}
              title={selectedPortfolioCard.archived ? "Restore archived sessions before changing shortlist state." : textValue(selectedPortfolioCard.shortcut_action_detail, "Shortlist this session for review next.")}
              on:click={() => handlePortfolioShortlistAction([selectedPortfolioCard], selectedPortfolioCard.shortlisted ? "clear_shortlist" : "shortlist")}
            >
              {textValue(selectedPortfolioCard.shortlist_action_label, "Shortlist for review next")}
            </button>
          </div>
          <button
            class={selectedPortfolioCard.shortcut_action_mode === "open_session" ? "btn warning" : "btn secondary"}
            type="button"
            on:click={() => handlePortfolioCardAction(selectedPortfolioCard)}
          >
            {portfolioShortcutActionLabel(selectedPortfolioCard)}
          </button>
          {#if selectedPortfolioNavigation?.route !== "/shell/workspace" && selectedPortfolioCard.shortcut_action_mode !== "direct"}
            <p class="muted">This entry is reviewable session history, not the live current workspace. It stays here so you can compare active, recent, pinned, archived, and shortlisted state without opening each session first.</p>
          {/if}
        </div>
      {/if}
    {:else}
      <div class="callout">No recent sessions are stored in this browser yet. After the first governed run reaches the workspace, this queue fills with backend-derived handoff packets for the active and recent sessions.</div>
    {/if}
  </section>

  <section class="panel">
    <h2>Stage-gated operator actions</h2>
    <div class="stage-grid">
      <article><h3>Load Directive</h3><p class="path">{textValue(state?.directive?.path, "No directive selected")}</p><button class="btn secondary" on:click={() => { clearActionNotices(); showDirectiveModal = true; }} disabled={bootstrapBusy || governedBusy}>Load Directive</button></article>
      <article><h3>Bootstrap Initialization</h3><p>{textValue(bootstrapStatus?.operator_next_action_detail, "Directive selection remains the first truthful step.")}</p><button class={!bootstrapStatus?.can_launch ? "btn disabled" : "btn primary"} on:click={handleBootstrapStart} disabled={!bootstrapStatus?.can_launch || bootstrapBusy || governedBusy}>{bootstrapBusy ? "Bootstrap starting..." : "Bootstrap Initialization"}</button></article>
      <article data-testid="governed-readiness-panel">
        <h3>Governed Execution Run</h3>
        <p>{textValue(governedStatus?.operator_next_action_detail, "Governed execution stays blocked until the backend says it is safe.")}</p>
        <div class="stage-grid compact governed-readiness">
          <div><span>Saved profile</span><strong>{textValue(governedStatus?.selected_execution_profile, "unknown")}</strong></div>
          <div><span>Expected profile</span><strong>{textValue(governedStatus?.expected_execution_profile, "bounded_active_workspace_coding")}</strong></div>
          <div><span>Workspace</span><strong>{governedWorkspaceMaterialized ? `${textValue(state?.artifacts?.workspace_id, "materialized")} ready` : "not materialized"}</strong></div>
          <div><span>Next step</span><strong>{textValue(governedStatus?.operator_next_action, "Restore governed runtime profile")}</strong></div>
        </div>
        {#if governedPrepRecommended}
          <div class="callout">Bootstrap and governed execution are separate lanes. Restore the saved runtime policy to <code>{textValue(governedStatus?.expected_execution_profile, "bounded_active_workspace_coding")}</code> after bootstrap before running <code>{textValue(governedStatus?.selected_launch, "resume_existing + governed_execution")}</code>.</div>
          <button class="btn warning" data-testid="governed-prepare-button" on:click={handleGovernedPrepare} disabled={directiveBusy || bootstrapBusy || governedBusy || governedPrepBusy}>{governedPrepBusy ? "Preparing governed runtime..." : "Prepare governed execution"}</button>
        {/if}
        <button class={!governedStatus?.can_launch ? "btn disabled" : "btn accent"} data-testid="governed-start-button" on:click={handleGovernedStart} disabled={!governedStatus?.can_launch || directiveBusy || bootstrapBusy || governedBusy || governedPrepBusy}>{governedBusy ? "Governed launch starting..." : "Governed Execution Run"}</button>
      </article>
    </div>
  </section>

  <section class="panel">
    <div class="row"><h2>Startup confidence feed</h2><span class="pill">{streamStatus}</span></div>
    <p class="muted">Meaningful operator-visible progress is listed here. Heartbeats stay in the connection badge so noise does not dominate the feed.</p>
    {#if startupFeed.length}
      <div class="feed">{#each startupFeed as entry}<article class={`feed-item ${entry.tone}`}><div><strong>{entry.label}</strong><p>{entry.detail}</p></div><span>{relativeTime(entry.at)}</span></article>{/each}</div>
    {:else}
      <div class="callout">No startup events are recorded yet. Directive selection, trusted-source validation, bootstrap, governed launch, and runtime events will appear here as they happen.</div>
    {/if}
  </section>

  <section class="panel">
    <div class="row"><h2>Bounded supervised continuation</h2><button class="btn subtle" on:click={handleWorkspaceJump}>Open Workspace Controls</button></div>
    <p>{longRunSession?.lifecycle_state === "not_started" ? "Bounded long-run supervised continuation begins after the first governed seed. Once the first checkpoint exists, continuation resumes from persisted checkpoints instead of reseeding from zero." : textValue(longRunSession?.operator_summary, "Bounded continuation is available from the latest checkpoint.")}</p>
    <div class="stage-grid compact">
      <div><span>Lifecycle</span><strong>{textValue(longRunSession?.lifecycle_state, "not_started")}</strong></div>
      <div><span>Cycle / budget</span><strong>{textValue(longRunSession?.current_cycle, "0")}/{textValue(longRunSession?.max_cycles, "0")}</strong></div>
      <div><span>Checkpoint count</span><strong>{textValue(longRunSession?.checkpoint_count, "0")}</strong></div>
      <div><span>Lease</span><strong>{textValue(longRunSession?.lease_state, "not_started")}</strong></div>
    </div>
    <div class="callout">Pause, resume, and stop controls live in the workspace. Cycle and budget settings remain governed by persisted policy rather than being edited from this landing page.</div>
  </section>

  {#if showDirectiveModal}
    <section class="modal-backdrop">
      <div class="modal">
        <div class="row"><h2>Directive and trusted-source load</h2><button class="btn secondary" on:click={() => (showDirectiveModal = false)}>Close</button></div>
        <div class="callout">Trusted-source credentials are validated in-session only. They are cleared from this form after validation and are not written into packaged artifacts.</div>
        <p class="muted">{trustedSourceGuidance}</p>
        <div class="stage-grid">
          <article>
            <h3>Directive selection</h3>
            <label>Directive path<input bind:value={directivePathInput} placeholder="/absolute/path/for/your/directive.json" /></label>
            {#if state?.directive_candidates?.length}<div class="chips-inline">{#each state.directive_candidates as candidate}<button class="chip" on:click={() => (directivePathInput = candidate.path)} type="button">{candidate.label || candidate.path}</button>{/each}</div>{/if}
            <div class="row"><button class="btn primary" on:click={handleDirectiveSelect} disabled={directiveBusy || bootstrapBusy || governedBusy || governedPrepBusy}>Select directive</button></div>
            <label>Upload directive file<input type="file" accept=".json,.jsonl" on:change={(event) => { const target = event.currentTarget as HTMLInputElement; selectedFile = target.files && target.files.length ? target.files[0] : null; }} /></label>
            {#if selectedFile}<p class="path">Selected file: {selectedFile.name}</p>{/if}
            <button class="btn subtle" on:click={handleDirectiveUpload} disabled={directiveBusy || bootstrapBusy || governedBusy || governedPrepBusy || !selectedFile}>Upload directive</button>
            {#if uploadNotice}<div class="notice">{uploadNotice}</div>{/if}
          </article>
          <article>
            <h3>Trusted-source validation</h3>
            <label>Provider ID<input bind:value={secretProviderId} placeholder="openai_api" /></label>
            <label>Provider base URL<input bind:value={secretProviderBaseUrl} placeholder="https://api.openai.com/v1" /></label>
            <label>API credential<input bind:value={secretCredential} type="password" placeholder="session-only value only" /></label>
            <div class="callout">External validation is optional in this packaged slice. Keep the default provider for session-only validation, or leave this step untouched for a fully local-only run.</div>
            <button class="btn warning" on:click={handleValidateTrustedSource} disabled={trustedSourceBusy || bootstrapBusy || governedBusy || governedPrepBusy}>Validate Trusted Source</button>
            {#if validationNotice}<div class="notice">{validationNotice}</div>{/if}
          </article>
        </div>
      </div>
    </section>
  {/if}
</main>

<style>
  .page-shell { max-width: 980px; margin: 0 auto; padding: 1.2rem; font-family: "Segoe UI Variable Text", "Aptos", sans-serif; }
  .hero,.panel,.chips>div,.stage-grid article,.feed-item,.callout,.modal { border: 1px solid var(--line); border-radius: 12px; background: var(--card); }
  .hero,.panel,.modal { padding: 1rem; margin-bottom: 1rem; }
  .hero { background: linear-gradient(115deg, #0a1830, #0f2a49 60%, #0a1830); }
  .hero h1,.panel h2,.panel h3 { margin: 0 0 .35rem; }
  .hero p,.muted,.feed-item p,.callout,.notice { color: #a8b7d2; }
  .chips,.stage-grid,.feed { display: grid; gap: .75rem; }
  .portfolio-grid { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); margin: .75rem 0 1rem; }
  .portfolio-card { border: 1px solid #2e405f; border-radius: 12px; background: #122037; padding: .85rem; display: grid; gap: .3rem; cursor: pointer; }
  .selected-portfolio-card { border-color: rgba(42,184,152,.55); box-shadow: 0 0 0 1px rgba(42,184,152,.22), 0 0 0 4px rgba(42,184,152,.08); }
  .portfolio-group { margin-top: 1rem; }
  .portfolio-recommendation { margin-top: .8rem; }
  .portfolio-chips { margin-top: .75rem; }
  .chips,.stage-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-bottom: 1rem; }
  .chips>div,.stage-grid article { padding: .85rem; }
  .compact { margin: .75rem 0; }
  .chips span,.compact span { display: block; font-size: .76rem; text-transform: uppercase; letter-spacing: .12em; color: #8aa2c4; }
  .path { overflow-wrap: anywhere; word-break: break-word; }
  .row { display: flex; gap: .75rem; justify-content: space-between; align-items: center; flex-wrap: wrap; }
  .btn { border: 0; padding: .55rem .82rem; border-radius: 8px; cursor: pointer; }
  .btn:disabled { opacity: .45; cursor: default; }
  .btn.primary { background: #2563eb; color: white; } .btn.accent { background: #14b8a6; color: #07101d; } .btn.secondary { background: #32455f; color: #e9edf1; } .btn.subtle { background: #4c5d77; color: #e9edf1; } .btn.warning { background: #ea8f00; color: #07101d; } .btn.disabled { background: #27344a; color: #93a4bb; }
  .pill { padding: .3rem .7rem; border-radius: 999px; border: 1px solid rgba(93,141,209,.35); background: rgba(12,29,54,.72); }
  .feed { margin-top: .75rem; }
  .feed-item { display: flex; justify-content: space-between; gap: .75rem; padding: .8rem .9rem; }
  .feed-item.success { border-color: rgba(42,184,152,.35); background: rgba(18,74,64,.22); }
  .feed-item.warning { border-color: rgba(234,143,0,.35); background: rgba(95,57,15,.22); }
  .feed-item strong,.feed-item p { margin: 0; }
  .feed-item span { white-space: nowrap; color: #8aa2c4; }
  .notice { padding: .55rem .75rem; border-radius: 8px; border: 1px solid var(--line); background: #132640; margin: .5rem 0; }
  .notice.danger { background: #2b1515; border-color: #8a2d2d; } .notice.warning { background: rgba(95,57,15,.28); border-color: rgba(234,143,0,.4); }
  .callout { padding: .7rem .85rem; background: rgba(22,49,83,.35); }
  .deferred-pressure-band.low { border-color: rgba(42,184,152,.35); background: rgba(18,74,64,.22); }
  .deferred-pressure-band.rising { border-color: rgba(234,143,0,.4); background: rgba(95,57,15,.22); }
  .deferred-pressure-band.high { border-color: rgba(220,70,70,.4); background: rgba(88,24,24,.22); }
  .modal-backdrop { position: fixed; inset: 0; background: rgba(5,11,19,.78); display: grid; place-items: center; padding: 1rem; }
  .modal { width: min(860px, 100%); background: #0d1525; }
  label { display: grid; gap: .3rem; margin-top: .7rem; }
  input { background: #0b1628; color: #e8edf4; border: 1px solid #273a58; border-radius: 8px; padding: .55rem; }
  .chips-inline { display: flex; gap: .45rem; flex-wrap: wrap; margin: .5rem 0; }
  .chip { border: 1px solid #2e405f; background: #1a2b43; color: #e8edf4; border-radius: 999px; padding: .35rem .7rem; }
  @media (max-width: 720px) { .feed-item { flex-direction: column; } .feed-item span { white-space: normal; } }
</style>
