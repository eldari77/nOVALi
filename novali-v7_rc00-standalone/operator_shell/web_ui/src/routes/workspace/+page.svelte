<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    continueLongRun,
    executeReviewAction,
    fetchInterventionState,
    fetchLongRunState,
    fetchOperatorState,
    openRuntimeEventStream,
    pauseLongRun,
    resumeLongRun,
    saveLongRunPolicy,
    stopLongRun,
    type InterventionOption,
    type LongRunStatePayload,
    type OperatorState,
    type ReviewPayload,
    type RuntimeEventPayload,
  } from "$lib/api";
  import {
    buildHandoffMemoryEntry,
    buildSafeNotificationContent,
    classifyAttentionArchiveState,
    createEmptyAttentionMemory,
    loadAttentionMemory,
    markHandoffEntryState,
    pickAttentionFocusTarget,
    serializeAttentionMemory,
    summarizeCurrentSessionMemory,
    upsertHandoffMemory,
  } from "$lib/attentionMemory.js";

  let state: OperatorState | null = null;
  let intervention: ReviewPayload | null = null;
  let longRun: LongRunStatePayload | null = null;
  let events: RuntimeEventPayload[] = [];
  let lastHeartbeat = "";
  let loadError = "";
  let refreshTimer: ReturnType<typeof setInterval> | null = null;
  let closeStream: (() => void) | null = null;
  let streamLive = false;
  let controlBusy = false;
  let reviewTransitionPending = false;
  let controlNotice = "";
  let controlError = "";
  let policyBusy = false;
  let policyDirty = false;
  let policyNotice = "";
  let policyError = "";
  let policyStrategy = "single_step";
  let policyMaxTotalCycles = "1";
  let policyMaxCyclesPerInvocation = "1";
  let lastAppliedPolicySignature = "";
  const OPERATOR_TOUCH_STORAGE_KEY = "novali.workspace.lastOperatorTouch";
  const ATTENTION_MEMORY_STORAGE_KEY = "novali.workspace.attentionMemory";

  type OperatorTouchMarker = {
    session_id: string;
    checkpoint_count: number;
    current_cycle: number;
    blocking_count: number;
    informational_count: number;
    next_stop_boundary_label: string;
    primary_action_id: string;
    recorded_at: string;
  };

  let lastOperatorTouchMarker: OperatorTouchMarker | null = null;

  type LocalAttentionHistoryEntry = {
    entry_key?: string;
    session_id?: string;
    session_handle?: string;
    checkpoint_id?: string;
    checkpoint_at?: string;
    lifecycle_state?: string;
    state_label?: string;
    stop_reason?: string;
    next_action_label?: string;
    next_action_detail?: string;
    what_changed_summary?: string;
    current_blocker?: string;
    next_stop_boundary_label?: string;
    attention_blocking_count?: number;
    attention_informational_count?: number;
    severity?: string;
    packet_id?: string;
    local_state?: string;
    handoff_label?: string;
    summary_signature?: string;
    created_at?: string;
    updated_at?: string;
    seen_at?: string;
    acknowledged_at?: string;
    snoozed_until?: string;
    resolved_at?: string;
    active?: boolean;
    [key: string]: unknown;
  };

  type LocalAttentionMemory = {
    schema_version: number;
    sessions: Record<
      string,
      {
        current_entry_key?: string;
        history?: LocalAttentionHistoryEntry[];
      }
    >;
  };

  let attentionMemory: LocalAttentionMemory = createEmptyAttentionMemory() as LocalAttentionMemory;
  let currentHandoffEntry: LocalAttentionHistoryEntry | null = null;
  let durableHandoffHistory: LocalAttentionHistoryEntry[] = [];
  let latestResolvedHandoffEntry: LocalAttentionHistoryEntry | null = null;
  let unreadBlockingAttentionCount = 0;
  let seenBlockingAttentionCount = 0;
  let acknowledgedBlockingAttentionCount = 0;
  let staleEscalatedBlockingCount = 0;
  let unresolvedBlockingAttentionCount = 0;
  let resolvedHandoffCount = 0;
  let archiveTriageFilter = "all";
  let localAttentionNotice = "";
  let localAttentionError = "";
  let notificationsSupported = false;
  let notificationPermissionState = "unsupported";
  let localAttentionDeliveryMode = "in_app_only";
  let localAttentionDeliveryDetail =
    "Blocking attention still appears in the workspace banner and inbox even when browser notifications are unavailable.";
  let lastAttentionProjectionSignature = "";
  let lastDeliveredNotificationKey = "";
  let attentionNavigationNotice = "";
  let attentionNavigationError = "";
  let archiveSelectionKey = "";
  let focusedAttentionTargetId = "";
  let portfolioIntentSessionId = "";
  let portfolioIntentFocus = "";
  let portfolioIntentEntryKey = "";
  let portfolioIntentHandled = false;
  let filteredHandoffHistory: LocalAttentionHistoryEntry[] = [];
  const staleAttentionThresholdMs = 15 * 1000;
  const staleAttentionRuleDetail =
    "Acknowledged unresolved blockers escalate locally after 15 seconds without resolution in this browser.";

  function readStoredAttentionMemory(): LocalAttentionMemory {
    if (typeof window === "undefined") {
      return createEmptyAttentionMemory() as LocalAttentionMemory;
    }
    try {
      return loadAttentionMemory(window.localStorage.getItem(ATTENTION_MEMORY_STORAGE_KEY)) as LocalAttentionMemory;
    } catch {
      return createEmptyAttentionMemory() as LocalAttentionMemory;
    }
  }

  function persistAttentionMemory(memory: LocalAttentionMemory) {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(ATTENTION_MEMORY_STORAGE_KEY, serializeAttentionMemory(memory));
    } catch {
      // Preserve the operator flow if local storage is unavailable.
    }
  }

  function syncNotificationSupport() {
    if (typeof window === "undefined") {
      notificationsSupported = false;
      notificationPermissionState = "unsupported";
      localAttentionDeliveryMode = "in_app_only";
      localAttentionDeliveryDetail =
        "Browser notifications are unavailable in this runtime, so attention delivery remains inside the workspace.";
      return;
    }
    notificationsSupported = typeof window.Notification !== "undefined";
    notificationPermissionState = notificationsSupported ? window.Notification.permission : "unsupported";
    localAttentionDeliveryMode =
      notificationsSupported && notificationPermissionState === "granted" ? "browser" : "in_app_only";
    if (!notificationsSupported) {
      localAttentionDeliveryDetail =
        "Browser notifications are unavailable here, so attention delivery remains inside the workspace banner, badge, and inbox.";
    } else if (notificationPermissionState === "granted") {
      localAttentionDeliveryDetail =
        "Blocking attention can raise a local browser notification plus the in-app badge/banner for this active session.";
    } else if (notificationPermissionState === "denied") {
      localAttentionDeliveryDetail =
        "Browser notifications are denied for this origin, so attention delivery stays in-app only until permission is changed in the browser.";
    } else {
      localAttentionDeliveryDetail =
        "Browser notifications are available but not yet allowed. The workspace still shows all blocking attention in-app until you enable them.";
    }
  }

  async function requestLocalNotificationPermission() {
    localAttentionError = "";
    localAttentionNotice = "";
    if (typeof window === "undefined" || typeof window.Notification === "undefined") {
      syncNotificationSupport();
      return;
    }
    try {
      const permission = await window.Notification.requestPermission();
      syncNotificationSupport();
      localAttentionNotice =
        permission === "granted"
          ? "Local browser notifications are enabled for new blocking attention packets in this session."
          : "Local browser notifications were not enabled. The in-app badge/banner remains authoritative for blocking attention.";
    } catch (err) {
      syncNotificationSupport();
      localAttentionError = String((err as Error).message);
    }
  }

  function localAttentionStateLabel(stateValue: unknown): string {
    const value = String(stateValue || "").trim();
    if (value === "acknowledged") {
      return "Acknowledged";
    }
    if (value === "seen") {
      return "Seen";
    }
    if (value === "snoozed") {
      return "Snoozed";
    }
    if (value === "resolved") {
      return "Resolved";
    }
    return "New";
  }

  function localAttentionStateTone(stateValue: unknown): string {
    const value = String(stateValue || "").trim();
    if (value === "acknowledged") {
      return "success";
    }
    if (value === "seen") {
      return "info";
    }
    if (value === "snoozed") {
      return "phase";
    }
    if (value === "resolved") {
      return "success";
    }
    return "warning";
  }

  function formatRecordedAt(value: unknown): string {
    const raw = String(value || "").trim();
    if (!raw) {
      return "n/a";
    }
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) {
      return raw;
    }
    return parsed.toLocaleString();
  }

  function refreshAttentionMemorySummary(sessionId: string) {
    const summary = summarizeCurrentSessionMemory(attentionMemory, sessionId) as {
      currentEntry: LocalAttentionHistoryEntry | null;
      history: LocalAttentionHistoryEntry[];
      latestResolved: LocalAttentionHistoryEntry | null;
      unreadBlockingCount: number;
      seenBlockingCount: number;
      acknowledgedBlockingCount: number;
      staleBlockingCount: number;
      unresolvedBlockingCount: number;
      resolvedCount: number;
    };
    currentHandoffEntry = summary.currentEntry;
    durableHandoffHistory = summary.history || [];
    latestResolvedHandoffEntry = summary.latestResolved || null;
    unreadBlockingAttentionCount = Number(summary.unreadBlockingCount || 0);
    seenBlockingAttentionCount = Number(summary.seenBlockingCount || 0);
    acknowledgedBlockingAttentionCount = Number(summary.acknowledgedBlockingCount || 0);
    staleEscalatedBlockingCount = Number(summary.staleBlockingCount || 0);
    unresolvedBlockingAttentionCount = Number(summary.unresolvedBlockingCount || 0);
    resolvedHandoffCount = Number(summary.resolvedCount || 0);
    if (
      !archiveSelectionKey ||
      !durableHandoffHistory.some((item) => String(item.entry_key || "") === String(archiveSelectionKey || ""))
    ) {
      archiveSelectionKey = String(
        summary.currentEntry?.entry_key || summary.latestResolved?.entry_key || "",
      ).trim();
    }
  }

  function deliverLocalAttention(entry: LocalAttentionHistoryEntry | null) {
    if (!entry) {
      return;
    }
    const notification = buildSafeNotificationContent(entry) as { title?: string; body?: string };
    const entryKey = String(entry.entry_key || "");
    if (
      typeof window !== "undefined" &&
      notificationsSupported &&
      notificationPermissionState === "granted" &&
      typeof window.Notification !== "undefined" &&
      entryKey &&
      lastDeliveredNotificationKey !== entryKey
    ) {
      try {
        const delivery = new window.Notification(String(notification.title || "NOVALI attention"), {
          body: String(notification.body || ""),
          tag: entryKey,
          renotify: false,
        });
        delivery.onclick = () => {
          window.focus();
        };
        lastDeliveredNotificationKey = entryKey;
        localAttentionNotice = `Local browser notification sent for ${textValue(entry.session_handle, "the active session")}.`;
        return;
      } catch (err) {
        localAttentionError = String((err as Error).message);
      }
    }
    localAttentionNotice =
      "Blocking attention is active for the current session. This browser is using the in-app badge/banner delivery path.";
  }

  function applyLocalAttentionState(nextState: "seen" | "acknowledged" | "snoozed") {
    const sessionId = String(currentHandoffEntry?.session_id || "").trim();
    const entryKey = String(currentHandoffEntry?.entry_key || "").trim();
    if (!sessionId || !entryKey) {
      return;
    }
    const result = markHandoffEntryState(attentionMemory, sessionId, entryKey, nextState) as {
      memory: LocalAttentionMemory;
    };
    attentionMemory = result.memory;
    persistAttentionMemory(attentionMemory);
    refreshAttentionMemorySummary(sessionId);
    localAttentionError = "";
    localAttentionNotice =
      nextState === "acknowledged"
        ? "Local acknowledgment saved for this blocking handoff. Backend blocking truth is unchanged until the review/intervention packet is actually resolved."
        : nextState === "snoozed"
          ? "Local re-notification is snoozed for this handoff packet. The blocking badge/banner remains visible while backend truth still requires action."
          : "This blocking handoff is marked seen in this browser. Backend blocking truth remains active until the packet is resolved.";
  }

  function archiveEntryTargetId(entryKey: unknown): string {
    const key = String(entryKey || "").trim();
    return `handoff-archive-entry-${key || "unknown"}`;
  }

  function blockingItemTargetId(item: Record<string, unknown> | null | undefined): string {
    const reviewItemId = String(item?.review_item_id || item?.review_id || "").trim();
    return `attention-review-item-${reviewItemId || "unknown"}`;
  }

  function attentionPacketTargetId(): string {
    const packetId = String(
      attentionPacket?.packet_id || attentionPacket?.review_packet_id || attentionPacket?.id || "",
    ).trim();
    return packetId ? `attention-packet-${packetId}` : "attention-packet-current";
  }

  function archiveAttentionStateKey(entry: LocalAttentionHistoryEntry | null | undefined): string {
    const helperState = String(classifyAttentionArchiveState(entry) || "clear").trim();
    if (helperState !== "acknowledged_unresolved_blocking") {
      return helperState;
    }
    const currentEntryKey = String(currentHandoffEntry?.entry_key || "").trim();
    const entryKey = String(entry?.entry_key || "").trim();
    if (!entryKey || entryKey !== currentEntryKey) {
      return helperState;
    }
    const recordedAt = String(lastOperatorTouchMarker?.recorded_at || "").trim();
    const recordedMs = recordedAt ? Date.parse(recordedAt) : Number.NaN;
    if (Number.isFinite(recordedMs) && Date.now() - recordedMs >= staleAttentionThresholdMs) {
      return "stale_escalated_blocking";
    }
    return helperState;
  }

  function archiveAttentionStateLabel(entry: LocalAttentionHistoryEntry | null | undefined): string {
    const stateKey = archiveAttentionStateKey(entry);
    if (stateKey === "new_blocking") {
      return "New blocking";
    }
    if (stateKey === "stale_escalated_blocking") {
      return "Stale escalated";
    }
    if (stateKey === "seen_unresolved_blocking") {
      return "Seen unresolved";
    }
    if (stateKey === "acknowledged_unresolved_blocking") {
      return "Acknowledged unresolved";
    }
    if (stateKey === "resolved_history") {
      return "Resolved history";
    }
    if (stateKey === "informational_history") {
      return "Informational history";
    }
    return "Clear";
  }

  function archiveAttentionStateTone(entry: LocalAttentionHistoryEntry | null | undefined): string {
    const stateKey = archiveAttentionStateKey(entry);
    if (stateKey === "new_blocking") {
      return "warning";
    }
    if (stateKey === "stale_escalated_blocking") {
      return "danger";
    }
    if (stateKey === "seen_unresolved_blocking") {
      return "info";
    }
    if (stateKey === "acknowledged_unresolved_blocking") {
      return "success";
    }
    if (stateKey === "resolved_history") {
      return "success";
    }
    if (stateKey === "informational_history") {
      return "phase";
    }
    return "info";
  }

  function isCurrentArchiveEntry(entry: LocalAttentionHistoryEntry | null | undefined): boolean {
    return (
      String(entry?.entry_key || "").trim() !== "" &&
      String(entry?.entry_key || "").trim() === String(currentHandoffEntry?.entry_key || "").trim()
    );
  }

  function belongsToCurrentSessionLineage(entry: LocalAttentionHistoryEntry | null | undefined): boolean {
    const sessionId = String(entry?.session_id || "").trim();
    const activeSessionId = String(longRunSession?.session_id || "").trim();
    return !sessionId || !activeSessionId || sessionId === activeSessionId;
  }

  function isUnresolvedArchiveEntry(entry: LocalAttentionHistoryEntry | null | undefined): boolean {
    const stateKey = archiveAttentionStateKey(entry);
    return (
      stateKey === "new_blocking" ||
      stateKey === "seen_unresolved_blocking" ||
      stateKey === "acknowledged_unresolved_blocking" ||
      stateKey === "stale_escalated_blocking"
    );
  }

  function archiveFilterCount(filterKey: string): number {
    if (filterKey === "all") {
      return durableHandoffHistory.length;
    }
    return durableHandoffHistory.filter((entry) => {
      const stateKey = archiveAttentionStateKey(entry);
      if (filterKey === "current") {
        return isCurrentArchiveEntry(entry);
      }
      if (filterKey === "unresolved") {
        return isUnresolvedArchiveEntry(entry);
      }
      if (filterKey === "stale") {
        return stateKey === "stale_escalated_blocking";
      }
      if (filterKey === "resolved") {
        return stateKey === "resolved_history";
      }
      if (filterKey === "informational") {
        return stateKey === "informational_history";
      }
      return true;
    }).length;
  }

  function archiveMatchesFilter(entry: LocalAttentionHistoryEntry | null | undefined): boolean {
    const stateKey = archiveAttentionStateKey(entry);
    if (archiveTriageFilter === "current") {
      return isCurrentArchiveEntry(entry);
    }
    if (archiveTriageFilter === "unresolved") {
      return isUnresolvedArchiveEntry(entry);
    }
    if (archiveTriageFilter === "stale") {
      return stateKey === "stale_escalated_blocking";
    }
    if (archiveTriageFilter === "resolved") {
      return stateKey === "resolved_history";
    }
    if (archiveTriageFilter === "informational") {
      return stateKey === "informational_history";
    }
    return true;
  }

  function setArchiveTriageFilter(filterKey: string) {
    archiveTriageFilter = filterKey;
    attentionNavigationError = "";
    attentionNavigationNotice =
      filterKey === "all"
        ? "Showing the full bounded handoff archive for this session."
        : `Showing ${filterKey} handoff entries for this session.`;
  }

  $: filteredHandoffHistory = durableHandoffHistory.filter((entry) => archiveMatchesFilter(entry));

  function focusAttentionTarget(targetId: string, notice: string): boolean {
    attentionNavigationError = "";
    attentionNavigationNotice = "";
    if (typeof window === "undefined") {
      attentionNavigationError = "This runtime cannot focus the selected attention target.";
      return false;
    }
    const target = document.getElementById(targetId);
    if (!target) {
      focusedAttentionTargetId = "";
      attentionNavigationError =
        "The requested blocking packet is not currently rendered. Use the live attention inbox below to inspect the active packet.";
      return false;
    }
    focusedAttentionTargetId = targetId;
    window.requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      if (typeof (target as HTMLElement).focus === "function") {
        (target as HTMLElement).focus({ preventScroll: true });
      }
    });
    attentionNavigationNotice = notice;
    return true;
  }

  function openCurrentAttentionTarget(sourceLabel = "attention signal"): boolean {
    const target = pickAttentionFocusTarget({
      currentPrimaryReviewItemId: interventionSummary?.current_primary_review_item_id,
      attentionPacket,
      blockingItems: attentionBlockingItems,
    }) as {
      kind: string;
      target_id: string;
    };
    if (!target.target_id) {
      attentionNavigationError =
        "No active blocking packet is currently available to focus. The summary is still truthful, but there is nothing actionable to scroll to yet.";
      attentionNavigationNotice = "";
      return false;
    }
    archiveSelectionKey = String(currentHandoffEntry?.entry_key || "").trim();
    const targetLabel =
      target.kind === "blocking_item"
        ? "current blocking item"
        : target.kind === "packet"
          ? "current blocking packet"
          : "attention item picker";
    return focusAttentionTarget(target.target_id, `Focused the ${targetLabel} from the ${sourceLabel}.`);
  }

  function readPortfolioIntentFromLocation() {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    portfolioIntentSessionId = String(params.get("portfolio_session") || "").trim();
    portfolioIntentFocus = String(params.get("portfolio_focus") || "").trim();
    portfolioIntentEntryKey = String(params.get("portfolio_entry_key") || "").trim();
    portfolioIntentHandled = false;
  }

  function clearPortfolioIntentFromLocation() {
    if (typeof window === "undefined") {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.delete("portfolio_session");
    url.searchParams.delete("portfolio_focus");
    url.searchParams.delete("portfolio_entry_key");
    const nextQuery = url.searchParams.toString();
    window.history.replaceState({}, "", `${url.pathname}${nextQuery ? `?${nextQuery}` : ""}`);
  }

  function applyPortfolioIntentIfReady() {
    if (portfolioIntentHandled || typeof window === "undefined" || !portfolioIntentFocus) {
      return;
    }
    if (portfolioIntentEntryKey && archiveSelectionKey !== portfolioIntentEntryKey) {
      archiveSelectionKey = portfolioIntentEntryKey;
    }
    const currentSessionId = String(longRunSession?.session_id || "").trim();
    const intentTargetsHistoricalEntry =
      portfolioIntentFocus === "portfolio_history" ||
      (portfolioIntentSessionId && currentSessionId && portfolioIntentSessionId !== currentSessionId);
    if (intentTargetsHistoricalEntry) {
      if (
        portfolioIntentEntryKey &&
        focusAttentionTarget(
          archiveEntryTargetId(portfolioIntentEntryKey),
          "Focused the selected recent session history entry from the session portfolio queue.",
        )
      ) {
        portfolioIntentHandled = true;
        clearPortfolioIntentFromLocation();
      }
      return;
    }
    if (portfolioIntentSessionId && currentSessionId && portfolioIntentSessionId !== currentSessionId) {
      return;
    }
    if (portfolioIntentFocus === "current_blocker") {
      if (openCurrentAttentionTarget("session portfolio queue")) {
        portfolioIntentHandled = true;
        clearPortfolioIntentFromLocation();
      }
      return;
    }
    if (portfolioIntentFocus === "continuation_controls") {
      if (
        focusAttentionTarget(
          "bounded-continuation",
          "Focused the continuation controls from the session portfolio queue.",
        )
      ) {
        portfolioIntentHandled = true;
        clearPortfolioIntentFromLocation();
      }
      return;
    }
    if (portfolioIntentFocus === "campaign_handoff") {
      if (
        focusAttentionTarget(
          "bounded-continuation",
          "Focused the current session summary from the session portfolio queue.",
        )
      ) {
        portfolioIntentHandled = true;
        clearPortfolioIntentFromLocation();
      }
    }
  }

  function openArchiveEntry(entry: LocalAttentionHistoryEntry | null | undefined) {
    const entryKey = String(entry?.entry_key || "").trim();
    if (!entryKey) {
      attentionNavigationError = "No durable handoff entry is available to navigate.";
      attentionNavigationNotice = "";
      return;
    }
    archiveSelectionKey = entryKey;
    if (isCurrentArchiveEntry(entry) && Number(entry?.attention_blocking_count || 0) > 0) {
      openCurrentAttentionTarget("handoff archive");
      return;
    }
    const targetId = archiveEntryTargetId(entryKey);
    focusAttentionTarget(
      targetId,
      isCurrentArchiveEntry(entry)
        ? "Focused the current handoff entry in the bounded archive."
        : "Focused a historical handoff entry. Live blocking truth still comes from the active session state above.",
    );
  }

  async function refreshAuthoritativeState() {
    const [latest, latestIntervention, latestLongRun] = await Promise.all([
      fetchOperatorState(),
      fetchInterventionState().catch(() => null),
      fetchLongRunState().catch(() => null),
    ]);
    state = latest;
    intervention = latestIntervention;
    longRun = latestLongRun;
    loadError = "";
    return {
      latest,
      latestIntervention,
      latestLongRun,
    };
  }

  async function refresh() {
    try {
      await refreshAuthoritativeState();
    } catch (err) {
      loadError = String((err as Error).message);
    }
  }

  function textValue(value: unknown, fallback = "n/a"): string {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function eventTone(event: RuntimeEventPayload): string {
    const raw = `${event.event_type || ""} ${event.phase || ""} ${event.message || ""}`.toLowerCase();
    if (raw.includes("error") || raw.includes("fail") || raw.includes("block")) {
      return "danger";
    }
    if (raw.includes("review") || raw.includes("intervention") || raw.includes("pause")) {
      return "warning";
    }
    if (raw.includes("artifact") || raw.includes("complete") || raw.includes("ready")) {
      return "success";
    }
    return "info";
  }

  async function performLongRunControl(action: "pause" | "resume" | "stop" | "continue") {
    return action === "continue"
      ? await continueLongRun()
      : action === "pause"
      ? await pauseLongRun()
      : action === "resume"
        ? await resumeLongRun()
        : await stopLongRun();
  }

  async function runLongRunControl(action: "pause" | "resume" | "stop" | "continue") {
    controlBusy = true;
    controlError = "";
    controlNotice = "";
    try {
      const result = await performLongRunControl(action);
      controlNotice = String(result?.message || `${action} request recorded.`);
      await refresh();
      storeOperatorTouchMarker(longRun);
    } catch (err) {
      controlError = String((err as Error).message);
    } finally {
      controlBusy = false;
    }
  }

  function policySignature(policy: LongRunStatePayload["effective_policy"] | null | undefined): string {
    return JSON.stringify([
      String(policy?.continuation_strategy || ""),
      String(policy?.max_total_cycles ?? ""),
      String(policy?.max_cycles_per_invocation ?? ""),
    ]);
  }

  function applyPolicyForm(policy: LongRunStatePayload["effective_policy"] | null | undefined) {
    if (!policy) {
      return;
    }
    policyStrategy = String(policy.continuation_strategy || "single_step").trim() || "single_step";
    policyMaxTotalCycles = String(policy.max_total_cycles ?? "1");
    policyMaxCyclesPerInvocation = String(policy.max_cycles_per_invocation ?? "1");
    lastAppliedPolicySignature = policySignature(policy);
  }

  function numericValue(value: unknown, fallback = 0): number {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function buildOperatorTouchMarker(
    payload: LongRunStatePayload | null | undefined,
  ): OperatorTouchMarker | null {
    const sessionId = String(payload?.long_run?.session_id || "").trim();
    if (!sessionId) {
      return null;
    }
    return {
      session_id: sessionId,
      checkpoint_count: numericValue(payload?.long_run?.checkpoint_count, 0),
      current_cycle: numericValue(payload?.long_run?.current_cycle, 0),
      blocking_count: numericValue(payload?.operator_guidance?.attention_inbox?.blocking_count, 0),
      informational_count: numericValue(payload?.operator_guidance?.attention_inbox?.informational_count, 0),
      next_stop_boundary_label: String(payload?.operator_guidance?.next_stop_boundary_label || "").trim(),
      primary_action_id: String(payload?.operator_guidance?.primary_cta?.action_id || "").trim(),
      recorded_at: new Date().toISOString(),
    };
  }

  function readStoredOperatorTouchMarker(): OperatorTouchMarker | null {
    if (typeof window === "undefined") {
      return null;
    }
    try {
      const raw = window.localStorage.getItem(OPERATOR_TOUCH_STORAGE_KEY);
      return raw ? (JSON.parse(raw) as OperatorTouchMarker) : null;
    } catch {
      return null;
    }
  }

  function storeOperatorTouchMarker(payload: LongRunStatePayload | null | undefined) {
    const marker = buildOperatorTouchMarker(payload);
    if (!marker || typeof window === "undefined") {
      return;
    }
    lastOperatorTouchMarker = marker;
    try {
      window.localStorage.setItem(OPERATOR_TOUCH_STORAGE_KEY, JSON.stringify(marker));
    } catch {
      // Preserve the operator flow if local storage is unavailable.
    }
  }

  function buildSinceLastTouchSummary(
    payload: LongRunStatePayload | null | undefined,
    marker: OperatorTouchMarker | null,
  ) {
    const sessionId = String(payload?.long_run?.session_id || "").trim();
    const checkpointCount = numericValue(payload?.long_run?.checkpoint_count, 0);
    const currentCycle = numericValue(payload?.long_run?.current_cycle, 0);
    const blockingCount = numericValue(payload?.operator_guidance?.attention_inbox?.blocking_count, 0);
    const informationalCount = numericValue(
      payload?.operator_guidance?.attention_inbox?.informational_count,
      0,
    );
    const nextStopBoundaryLabel = String(payload?.operator_guidance?.next_stop_boundary_label || "").trim();
    const primaryActionId = String(payload?.operator_guidance?.primary_cta?.action_id || "").trim();
    const primaryActionLabel = String(payload?.operator_guidance?.primary_cta?.label || "").trim();
    if (!sessionId) {
      return {
        status_label: "No active session",
        detail: "No long-run session is materialized yet, so no local operator-touch delta is available.",
      };
    }
    if (!marker) {
      return {
        status_label: "No stored touch",
        detail:
          "No prior operator touch for this session is stored in this browser yet. Use the backend-derived Since last resume summary below for the durable campaign delta.",
      };
    }
    if (marker.session_id !== sessionId) {
      return {
        status_label: "Different session",
        detail:
          "The workspace is showing a different session than the last operator action stored in this browser, so the local re-entry delta starts fresh here.",
      };
    }
    const checkpointsAdded = Math.max(checkpointCount - numericValue(marker.checkpoint_count, 0), 0);
    const cyclesCompleted = Math.max(currentCycle - numericValue(marker.current_cycle, 0), 0);
    const blockingChanged = blockingCount !== numericValue(marker.blocking_count, 0);
    const informationalChanged =
      informationalCount !== numericValue(marker.informational_count, 0);
    const boundaryChanged =
      nextStopBoundaryLabel &&
      nextStopBoundaryLabel !== String(marker.next_stop_boundary_label || "").trim();
    const actionChanged =
      primaryActionId && primaryActionId !== String(marker.primary_action_id || "").trim();
    const detailParts: string[] = [];
    if (checkpointsAdded) {
      detailParts.push(`${checkpointsAdded} checkpoint(s) added`);
    }
    if (cyclesCompleted) {
      detailParts.push(`${cyclesCompleted} cycle(s) completed`);
    }
    if (blockingChanged) {
      detailParts.push(
        blockingCount
          ? `${blockingCount} blocking attention item(s) now require review`
          : "the blocking attention queue cleared",
      );
    }
    if (informationalChanged && informationalCount) {
      detailParts.push(`${informationalCount} informational update(s) are now visible`);
    }
    if (boundaryChanged) {
      detailParts.push(`next stop is now ${nextStopBoundaryLabel}`);
    }
    if (actionChanged && primaryActionLabel) {
      detailParts.push(`next action is now ${primaryActionLabel}`);
    }
    return {
      status_label: detailParts.length ? "Changed since last touch" : "No material change",
      detail: detailParts.length
        ? `${detailParts.join("; ")}. Last recorded touch: ${String(marker.recorded_at || "unknown")}.`
        : `No material change is recorded since the last operator action stored in this browser (${String(marker.recorded_at || "unknown")}).`,
    };
  }

  onMount(() => {
    lastOperatorTouchMarker = readStoredOperatorTouchMarker();
    attentionMemory = readStoredAttentionMemory();
    syncNotificationSupport();
    readPortfolioIntentFromLocation();
    const sessionId = String(longRun?.long_run?.session_id || "").trim();
    if (sessionId) {
      refreshAttentionMemorySummary(sessionId);
    }
    if (typeof window === "undefined") {
      return undefined;
    }
    const handleFocus = () => {
      syncNotificationSupport();
    };
    window.addEventListener("focus", handleFocus);
    return () => {
      window.removeEventListener("focus", handleFocus);
    };
  });

  async function runSaveLongRunPolicy() {
    policyBusy = true;
    policyError = "";
    policyNotice = "";
    try {
      const result = await saveLongRunPolicy({
        continuation_strategy: policyStrategy,
        max_total_cycles: policyMaxTotalCycles,
        max_cycles_per_invocation: policyMaxCyclesPerInvocation,
      });
      policyDirty = false;
      policyNotice = String(
        result?.message || result?.headline || "Long-run policy saved for future continuation launches.",
      );
      if (result?.state) {
        longRun = result.state;
      }
      await refresh();
      storeOperatorTouchMarker(longRun);
    } catch (err) {
      policyError = String((err as Error).message);
    } finally {
      policyBusy = false;
    }
  }

  function continuationBlockedByReviewState(review: ReviewPayload | null): boolean {
    const reviewRequired = Boolean(review?.review_required || review?.intervention?.required);
    const blockingCount = Number(review?.intervention?.blocking_review_count || 0);
    const pendingCount = Number(review?.intervention?.pending_review_count || 0);
    const blockingCards = Array.isArray(review?.intervention?.queue_items)
      ? review.intervention.queue_items.filter((item) => Boolean(item?.blocks_continuation))
      : [];
    return Boolean(reviewRequired || blockingCount || pendingCount || blockingCards.length);
  }

  function delay(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function waitForContinuationReadyAfterReview(timeoutMs = 8000) {
    const startedAt = Date.now();
    let latestObservedLongRun = longRun;
    while (Date.now() - startedAt < timeoutMs) {
      try {
        const { latestIntervention, latestLongRun } = await refreshAuthoritativeState();
        latestObservedLongRun = latestLongRun;
        const latestPrimaryAction = String(
          latestLongRun?.operator_guidance?.primary_cta?.action_id || "",
        ).trim();
        const latestReviewBlocked = continuationBlockedByReviewState(latestIntervention);
        if (
          latestPrimaryAction === "continue" ||
          (latestLongRun?.long_run?.resume_available && !latestReviewBlocked)
        ) {
          return latestLongRun;
        }
      } catch {
        // Keep polling; transient refresh failures should not cancel the combined continue path.
      }
      await delay(400);
    }
    return latestObservedLongRun;
  }

  function navigateToTarget(target: string) {
    const resolved = String(target || "").trim();
    if (!resolved) {
      return;
    }
    if (resolved.startsWith("#")) {
      const element = document.getElementById(resolved.slice(1));
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      return;
    }
    window.location.href = resolved;
  }

  function findSecondaryControl(actionId: string) {
    return secondaryControls.find((item) => String(item?.action_id || "").trim() === actionId) || null;
  }

  async function runApproveAndContinue() {
    const preferredActionId = String(
      longRun?.operator_guidance?.primary_cta?.preferred_review_action_id || "",
    ).trim();
    const preferredReviewItemId = String(
      longRun?.operator_guidance?.primary_cta?.preferred_review_item_id || "",
    ).trim();
    const option =
      blockingReviewOptions.find(
        (item) =>
          String(item?.action_id || "").trim() === preferredActionId &&
          String(item?.review_item_id || "").trim() === preferredReviewItemId,
      ) ||
      blockingReviewOptions.find((item) =>
        /\bapprove\b|\bcontinue\b|\ballow\b|\bresume\b/i.test(
          `${String(item?.action_id || "")} ${String(item?.label || "")} ${String(item?.description || "")}`,
        ) && !/review evidence first/i.test(
          `${String(item?.action_id || "")} ${String(item?.label || "")} ${String(item?.description || "")}`,
        ),
      ) ||
      blockingReviewOptions.find((item) => !!item?.recommended) ||
      blockingReviewOptions[0];
    const actionId = String(option?.action_id || preferredActionId || "").trim();
    if (!actionId) {
      controlError = "No bounded review action is available to unblock continuation.";
      return;
    }
    controlBusy = true;
    controlError = "";
    controlNotice = "";
    try {
      const reviewResult = await executeReviewAction({
        action_id: actionId,
        review_item_id: String(option?.review_item_id || preferredReviewItemId || "").trim(),
        operator_note: "",
      });
      const notices = [
        String(
          reviewResult?.headline ||
            reviewResult?.message ||
            `${textValue(option?.label || option?.action_label || actionId, "Review action")} recorded.`,
        ),
      ];
      let continuationStarted = false;
      let continueError = "";
      for (const settleTimeoutMs of [0, 6000]) {
        if (settleTimeoutMs > 0) {
          await waitForContinuationReadyAfterReview(settleTimeoutMs);
        } else {
          await refresh();
        }
        try {
          const continueResult = await performLongRunControl("continue");
          notices.push(String(continueResult?.message || "Continuation requested."));
          continuationStarted = true;
          await refresh();
          break;
        } catch (err) {
          continueError = String((err as Error).message);
        }
      }
      if (!continuationStarted) {
        await refresh();
        if (continueError) {
          notices.push(`Continuation remains blocked after approval. ${continueError}`);
        }
      }
      controlNotice = notices.filter(Boolean).join(" ");
      storeOperatorTouchMarker(longRun);
    } catch (err) {
      controlError = String((err as Error).message);
    } finally {
      controlBusy = false;
    }
  }

  async function runPrimaryCta() {
    const actionId = String(primaryCta?.action_id || "").trim();
    if (!actionId) {
      return;
    }
    if (actionId === "approve_and_continue") {
      await runApproveAndContinue();
      return;
    }
    if (actionId === "approve_review_item") {
      const preferredActionId = String(primaryCta?.preferred_review_action_id || "").trim();
      const preferredReviewItemId = String(primaryCta?.preferred_review_item_id || "").trim();
      const option =
        blockingReviewOptions.find(
          (item) =>
            String(item?.action_id || "").trim() === preferredActionId &&
            String(item?.review_item_id || "").trim() === preferredReviewItemId,
        ) ||
        blockingReviewOptions.find((item) =>
          /\bapprove\b|\bcontinue\b|\ballow\b|\bresume\b/i.test(
            `${String(item?.action_id || "")} ${String(item?.label || "")} ${String(item?.description || "")}`,
          ) && !/review evidence first/i.test(
            `${String(item?.action_id || "")} ${String(item?.label || "")} ${String(item?.description || "")}`,
          ),
        ) ||
        blockingReviewOptions.find((item) => !!item?.recommended) ||
        blockingReviewOptions[0];
      if (option) {
        await runReviewAction(option);
      }
      return;
    }
    if (actionId === "continue" || actionId === "pause" || actionId === "resume" || actionId === "stop") {
      await runLongRunControl(actionId);
      return;
    }
    navigateToTarget(String(primaryCta?.target || ""));
  }

  async function runReviewAction(option: InterventionOption) {
    const actionId = String(option?.action_id || "").trim();
    const reviewItemId = String(option?.review_item_id || "").trim();
    if (!actionId) {
      controlError = "No bounded review action is available for this intervention item.";
      return;
    }
    controlBusy = true;
    reviewTransitionPending = false;
    controlError = "";
    controlNotice = "";
    try {
      const result = await executeReviewAction({
        action_id: actionId,
        review_item_id: reviewItemId,
        operator_note: "",
      });
      controlNotice = String(
        result?.headline || result?.message || `${textValue(option.label || option.action_label || actionId, "Review action")} recorded.`,
      );
      await refresh();
      storeOperatorTouchMarker(longRun);
      if (/approve|resume|allow|continue/i.test(actionId)) {
        reviewTransitionPending = true;
        controlBusy = false;
        controlNotice = `${controlNotice} Refreshing continuation readiness in this panel.`;
        const settledLongRun = await waitForContinuationReadyAfterReview(12000);
        await refresh();
        storeOperatorTouchMarker(settledLongRun || longRun);
        const settledPrimaryAction = String(
          settledLongRun?.operator_guidance?.primary_cta?.action_id || longRun?.operator_guidance?.primary_cta?.action_id || "",
        ).trim();
        const settledResumeAvailable = Boolean(settledLongRun?.long_run?.resume_available || longRun?.long_run?.resume_available);
        const settledReviewBlocked = continuationBlockedByReviewState(intervention);
        if ((settledPrimaryAction === "continue" || settledPrimaryAction === "resume") || (settledResumeAvailable && !settledReviewBlocked)) {
          controlNotice = `${textValue(
            option.label || option.action_label || actionId,
            "Review action",
          )} recorded. ${textValue(
            settledLongRun?.operator_guidance?.primary_cta?.label,
            "Continue bounded session",
          )} is now available in this panel.`;
          if (typeof window !== "undefined") {
            window.location.reload();
            return;
          }
        } else {
          const refreshedIntervention = intervention?.intervention || {};
          const remainingBlocking = Number(refreshedIntervention.blocking_review_count || 0);
          const resolvedCount = Number(refreshedIntervention.resolved_review_item_count || 0);
          const totalCount = Number(
            refreshedIntervention.total_review_item_count || refreshedIntervention.pending_review_count || 0,
          );
          const nextTitle = textValue(
            refreshedIntervention.current_primary_review_title ||
              settledLongRun?.operator_guidance?.intervention_guidance?.primary_title,
            "the next intervention item",
          );
          controlNotice = `${textValue(
            option.label || option.action_label || actionId,
            "Review action",
          )} recorded. ${resolvedCount} of ${Math.max(totalCount, resolvedCount)} review item(s) in this intervention loop are resolved. ${remainingBlocking} blocking review item(s) remain. Next: ${nextTitle}.`;
        }
      }
    } catch (err) {
      controlError = String((err as Error).message);
    } finally {
      reviewTransitionPending = false;
      controlBusy = false;
    }
  }

  onMount(async () => {
    lastOperatorTouchMarker = readStoredOperatorTouchMarker();
    await refresh();
    const stream = openRuntimeEventStream({
      onOpen() {
        streamLive = true;
      },
      onEvent(event) {
        streamLive = true;
        events = [event, ...events].slice(0, 80);
      },
      onHeartbeat(payload) {
        streamLive = true;
        lastHeartbeat = payload.generated_at;
      },
      onError() {
        streamLive = false;
      },
    });
    closeStream = stream;
    refreshTimer = setInterval(async () => {
      await refresh();
    }, 2500);
  });

  onDestroy(() => {
    if (refreshTimer) {
      clearInterval(refreshTimer);
    }
    if (closeStream) {
      closeStream();
    }
  });

  $: operatorState = state?.operator_state || {};
  $: interventionSummary = intervention?.intervention || state?.intervention || {};
  $: interventionCards = Array.isArray(interventionSummary?.queue_items)
    ? interventionSummary.queue_items
    : [];
  $: reviewNeeded = Boolean(intervention?.intervention_required);
  $: reviewRequired = Boolean(intervention?.review_required);
  $: confirmation = intervention?.review_source || state?.review_sources || {};
  $: reviewConfirmation = confirmation?.review_confirmation || {};
  $: decisionSource = confirmation?.review_decision_source || {};
  $: confirmedOutcome = confirmation?.promotion_outcome_confirmed || {};
  $: confirmationGap = confirmation?.confirmation_gap || {};
  $: runningStatus = state?.runtime?.run_status || "unknown";
  $: longRunSession = longRun?.long_run || null;
  $: longRunCheckpoint = longRunSession?.latest_checkpoint || null;
  $: streamStatus = streamLive ? "Live stream connected" : lastHeartbeat ? "Heartbeat received" : "Connecting";
  $: liveFeedEmptyMessage = lastHeartbeat
    ? "SSE is live. Waiting for the next non-heartbeat runtime event."
    : "No events yet.";
  $: latestMeaningfulEvent = events.length ? events[0] : null;
  $: meaningfulEventCount = events.length;
  $: reviewOptions = Array.isArray(interventionSummary?.options)
    ? interventionSummary.options.filter((item) => String(item?.route || "").trim() === "/review/action")
    : [];
  $: blockingReviewCount = Number(interventionSummary?.blocking_review_count || 0);
  $: pendingReviewCount = Number(interventionSummary?.pending_review_count || 0);
  $: blockingInterventionCards = interventionCards.filter((item) => Boolean(item?.blocks_continuation));
  $: activeContinuationReviewGate = Boolean(
    reviewRequired || blockingReviewCount || pendingReviewCount || blockingInterventionCards.length,
  );
  $: blockingReviewOptions = reviewOptions.filter(
    (item) => String(item?.review_item_id || "").trim() || item?.available !== false,
  );
  $: continueBlockedByReview = activeContinuationReviewGate;
  $: longRunGuidance = longRun?.operator_guidance || null;
  $: interventionGuidance = longRunGuidance?.intervention_guidance || null;
  $: attentionInbox = longRunGuidance?.attention_inbox || intervention?.attention_inbox || null;
  $: attentionBlockingItems = Array.isArray(attentionInbox?.blocking_items)
    ? attentionInbox.blocking_items
    : blockingInterventionCards;
  $: attentionInformationalItems = Array.isArray(attentionInbox?.informational_items)
    ? attentionInbox.informational_items
    : interventionCards.filter((item) => !item?.blocks_continuation);
  $: attentionBlockingCount = Number(
    attentionInbox?.blocking_count ?? interventionRemainingBlockingCount,
  );
  $: attentionInformationalCount = Number(
    attentionInbox?.informational_count ?? attentionInformationalItems.length,
  );
  $: attentionPacket = attentionInbox?.current_packet || null;
  $: attentionEmptyStateLabel = textValue(attentionInbox?.empty_state_label, "No blocking attention items");
  $: attentionEmptyStateDetail = textValue(
    attentionInbox?.empty_state_detail,
    "This session has no blocking attention items right now.",
  );
  $: attentionSignal = longRunGuidance?.attention_signal || null;
  $: campaignHandoff = longRunGuidance?.campaign_handoff_summary || null;
  $: sinceLastResume = longRunGuidance?.delta_since_last_resume || null;
  $: sinceLastTouch = buildSinceLastTouchSummary(longRun, lastOperatorTouchMarker);
  $: nextStopBoundaryLabel = textValue(longRunGuidance?.next_stop_boundary_label, "bounded stop");
  $: nextStopBoundarySummary = textValue(
    longRunGuidance?.next_stop_boundary_summary,
    "The next truthful bounded stop boundary will be projected here from backend state.",
  );
  $: effectivePolicy = longRun?.effective_policy || null;
  $: if (effectivePolicy && !policyDirty && policySignature(effectivePolicy) !== lastAppliedPolicySignature) {
    applyPolicyForm(effectivePolicy);
  }
  $: primaryCta = longRunGuidance?.primary_cta || null;
  $: secondaryControls = Array.isArray(longRunGuidance?.secondary_controls)
    ? longRunGuidance.secondary_controls
    : [];
  $: primaryActionId = String(primaryCta?.action_id || "").trim();
  $: continuationBlockingReason = String(primaryCta?.blocked_reason || longRunGuidance?.blocking_reason || "").trim();
  $: primaryCtaAvailable = primaryCta?.available !== false;
  $: primaryCtaDisabled =
    controlBusy ||
    !primaryCtaAvailable ||
    (reviewTransitionPending && (primaryActionId === "approve_review_item" || primaryActionId === "approve_and_continue"));
  $: primaryCalloutSuccess = primaryCtaAvailable && !continuationBlockingReason;
  $: latestCheckpointLabel = textValue(longRunCheckpoint?.checkpoint_id || longRunSession?.latest_checkpoint_id, "n/a");
  $: effectiveMaxTotalCycles = textValue(
    effectivePolicy?.max_total_cycles ?? longRunSession?.max_cycles,
    "0",
  );
  $: effectiveMaxCyclesPerInvocation = textValue(
    effectivePolicy?.max_cycles_per_invocation ?? longRunSession?.max_cycles_per_invocation,
    "0",
  );
  $: effectiveCyclesRemaining = textValue(
    effectivePolicy?.cycles_remaining ?? longRunSession?.budget_remaining?.remaining_cycles,
    "0",
  );
  $: effectiveRestartHeadroom = textValue(
    effectivePolicy?.remaining_restart_attempts ?? longRunSession?.budget_remaining?.remaining_restart_attempts,
    "0",
  );
  $: effectiveMaxRestartAttempts = textValue(
    effectivePolicy?.max_restart_attempts ?? longRunSession?.max_restart_attempts,
    "0",
  );
  $: lowTouchPolicyEnabled = String(effectivePolicy?.continuation_strategy || "").trim() === "until_bounded_stop";
  $: policySaveDisabled =
    policyBusy ||
    controlBusy ||
    !effectivePolicy ||
    !policyDirty;
  $: currentExecutionProfile = textValue(
    longRunGuidance?.current_execution_profile || state?.runtime?.execution_profile,
    "unknown",
  );
  $: interventionWorkspaceLabel = textValue(
    interventionSummary?.review_workspace_label || interventionGuidance?.workspace_label,
    "No pending review",
  );
  $: interventionPrimaryTitle = textValue(
    interventionGuidance?.primary_title || interventionSummary?.current_primary_review_title,
    "Current intervention item",
  );
  $: interventionPrimaryReasonClass = textValue(
    interventionGuidance?.primary_reason_class || interventionSummary?.primary_reason_class,
    "n/a",
  );
  $: interventionResolvedCount = Number(
    interventionGuidance?.resolved_review_item_count || interventionSummary?.resolved_review_item_count || 0,
  );
  $: interventionTotalCount = Number(
    interventionGuidance?.total_review_item_count || interventionSummary?.total_review_item_count || pendingReviewCount,
  );
  $: interventionRemainingBlockingCount = Number(
    interventionGuidance?.remaining_blocking_review_count || interventionSummary?.blocking_review_count || 0,
  );
  $: interventionLatestResolutionSummary = textValue(
    interventionGuidance?.latest_resolution_summary || interventionSummary?.latest_resolution_summary,
    "",
  );
  $: interventionResumeReadyDetail = textValue(
    interventionGuidance?.resume_ready_after_review_clear_detail,
    "The workspace will surface the next truthful same-session continuation action when the remaining blocking review items clear.",
  );
  $: expectedExecutionProfile = textValue(
    longRunGuidance?.expected_execution_profile || state?.launch_readiness?.governed?.expected_execution_profile,
    "bounded_active_workspace_coding",
  );
  $: workspaceMaterialized = Boolean(
    longRunGuidance?.workspace_materialized || state?.artifacts?.workspace_id || state?.artifacts?.workspace_root,
  );
  $: continueControl = findSecondaryControl("continue");
  $: pauseControl = findSecondaryControl("pause");
  $: resumeControl = findSecondaryControl("resume");
  $: stopControl = findSecondaryControl("stop");
  $: continuationHighlights = events
    .filter((event) => {
      const raw = `${event.event_type || ""} ${event.phase || ""} ${event.message || ""}`.toLowerCase();
      return /(session|checkpoint|resume|continu|review|lease|pause|stop|intervention|budget)/.test(raw);
    })
    .slice(0, 5);
  $: {
    const sessionId = String(longRun?.long_run?.session_id || "").trim();
    const entry = buildHandoffMemoryEntry({
      longRunState: longRun,
      attentionSignal: longRun?.operator_guidance?.attention_signal || null,
      campaignHandoff: longRun?.operator_guidance?.campaign_handoff_summary || null,
      deltaSinceLastResume: longRun?.operator_guidance?.delta_since_last_resume || null,
    }) as LocalAttentionHistoryEntry | null;
    const projectionSignature = entry
      ? `${String(entry.entry_key || "")}|${String(entry.summary_signature || "")}`
      : "";
    if (entry && sessionId && projectionSignature !== lastAttentionProjectionSignature) {
      lastAttentionProjectionSignature = projectionSignature;
      const result = upsertHandoffMemory(attentionMemory, entry, {
        notificationSupport: {
          supported: notificationsSupported,
          permission: notificationPermissionState,
        },
      }) as {
        memory: LocalAttentionMemory;
        currentEntry: LocalAttentionHistoryEntry | null;
        shouldNotify: boolean;
      };
      attentionMemory = result.memory;
      persistAttentionMemory(attentionMemory);
      refreshAttentionMemorySummary(sessionId);
      if (result.shouldNotify) {
        deliverLocalAttention(result.currentEntry);
      }
    } else if (sessionId) {
      refreshAttentionMemorySummary(sessionId);
    }
  }
  $: if (
    portfolioIntentFocus ||
    portfolioIntentEntryKey ||
    String(longRunSession?.session_id || "").trim() ||
    attentionBlockingItems.length ||
    attentionPacket ||
    currentHandoffEntry ||
    filteredHandoffHistory.length
  ) {
    applyPortfolioIntentIfReady();
  }
</script>

<main class="workspace-shell">
  <header class="workspace-hero">
    <div>
      <div class="eyebrow">Truthful live workspace</div>
      <h1>Operator Workspace</h1>
      <p class="muted">Live run state, review posture, and intervention visibility projected directly from persisted backend/controller artifacts.</p>
    </div>
    <div class="toolbar">
      <a class="btn secondary" href="/shell#session-portfolio">Portfolio</a>
      <a class="btn secondary" href="/shell">Landing</a>
      <a class="btn secondary" href="/shell/workspace">Workspace</a>
      <a class="btn secondary" href="/observability">Observability</a>
    </div>
  </header>

  {#if loadError}
    <p class="notice danger">Unable to refresh workspace: {loadError}</p>
  {/if}

  {#if state}
    <section class="summary-grid">
      <article class="summary-card">
        <span>Run state</span>
        <strong>{textValue(runningStatus, "unknown")}</strong>
        <p>{textValue(state.session.session_state, "unknown")} · {textValue(state.runtime.execution_profile, "unknown")}</p>
      </article>
      <article class="summary-card">
        <span>Workflow phase</span>
        <strong>{textValue(state.session.workflow_stage, "unknown")}</strong>
        <p>{textValue(state.session.next_action, "Waiting for next bounded action")}</p>
      </article>
      <article class="summary-card">
        <span>Review lane</span>
        <strong>{textValue(reviewConfirmation.review_confirmation_label || confirmedOutcome.confirmed_outcome_label, "Review gate preserved")}</strong>
        <p>{textValue(confirmationGap.confirmation_gap_label || confirmationGap.confirmation_gap_state, "No confirmation-gap data recorded")}</p>
      </article>
      <article class="summary-card">
        <span>Intervention</span>
        <strong>{reviewNeeded || reviewRequired ? "Operator action required" : "No active intervention"}</strong>
        <p>{textValue(intervention?.intervention?.recommended_action || state.intervention.recommended_action, "Stay in bounded review posture")}</p>
      </article>
      <article class="summary-card">
        <span>Long-run continuation</span>
        <strong>{textValue(longRunSession?.lifecycle_state, "not_started")}</strong>
        <p>
          cycle {textValue(longRunSession?.current_cycle, "0")}/{textValue(longRunSession?.max_cycles, "0")}
          · checkpoints {textValue(longRunSession?.checkpoint_count, "0")}
        </p>
        <p>lease {textValue(longRunSession?.lease_state, "not_started")}</p>
      </article>
    </section>

    {#if campaignHandoff}
      <section class="panel" id="campaign-handoff">
        <div class="section-header">
          <div>
            <div class="eyebrow">Campaign handoff summary</div>
            <h2>What changed, what is blocked, and what resumes the same session</h2>
            <p class="muted">This compact re-entry packet summarizes the active bounded session before you need to reread the full activity trail.</p>
          </div>
          <div
            class:attention-badge-blocking={attentionSignal?.severity === "blocking"}
            class:attention-badge-info={attentionSignal?.severity === "informational"}
            class:live-badge={attentionSignal?.severity === "clear"}
            class="stream-badge attention-badge attention-action-signal"
            data-testid="attention-required-badge"
            role="button"
            tabindex={attentionSignal?.severity === "blocking" ? 0 : -1}
            on:click={() => attentionSignal?.severity === "blocking" && openCurrentAttentionTarget("attention badge")}
            on:keydown={(event) =>
              attentionSignal?.severity === "blocking" &&
              (event.key === "Enter" || event.key === " ")
                ? (event.preventDefault(), openCurrentAttentionTarget("attention badge"))
                : null}
          >
            {textValue(attentionSignal?.label, "No blocking attention")}
          </div>
        </div>
        {#if attentionSignal}
          <div
            class:warning-panel={attentionSignal?.severity === "blocking"}
            class:success-panel={attentionSignal?.severity === "clear"}
            class="status-callout attention-signal-banner attention-action-signal"
            data-testid="attention-signal-banner"
            role="button"
            tabindex={attentionSignal?.severity === "blocking" ? 0 : -1}
            on:click={() => attentionSignal?.severity === "blocking" && openCurrentAttentionTarget("attention banner")}
            on:keydown={(event) =>
              attentionSignal?.severity === "blocking" &&
              (event.key === "Enter" || event.key === " ")
                ? (event.preventDefault(), openCurrentAttentionTarget("attention banner"))
                : null}
          >
            <div class="event-topline">
              <strong>{textValue(attentionSignal?.label, "Attention status")}</strong>
              <span class={`event-chip ${attentionSignal?.severity === "blocking" ? "warning" : attentionSignal?.severity === "informational" ? "info" : "success"}`}>
                {textValue(attentionSignal?.severity, "clear")}
              </span>
            </div>
            <p>{textValue(attentionSignal?.detail, "No attention signal is recorded for this bounded session.")}</p>
            <p><strong>Counts:</strong> blocking {textValue(attentionSignal?.blocking_count, attentionBlockingCount)} · informational {textValue(attentionSignal?.informational_count, attentionInformationalCount)}</p>
            {#if attentionSignal?.severity === "blocking"}
              <p class="muted"><strong>Direct path:</strong> Click here to jump straight to the exact blocking packet or current review item below.</p>
            {/if}
          </div>
        {/if}
        <div class="summary-grid continuation-grid" data-testid="campaign-handoff-summary">
          <article class="summary-card">
            <span>Session handoff</span>
            <strong>{textValue(campaignHandoff?.session_handle, "not-started")}</strong>
            <p>{textValue(campaignHandoff?.state_label, "not_started")} · cycle {textValue(campaignHandoff?.current_cycle, "0")}/{textValue(campaignHandoff?.max_cycles, effectiveMaxTotalCycles)}</p>
          </article>
          <article class="summary-card">
            <span>Last checkpoint</span>
            <strong>{textValue(campaignHandoff?.last_checkpoint_id, latestCheckpointLabel)}</strong>
            <p>{textValue(campaignHandoff?.last_checkpoint_at, "No checkpoint timestamp recorded yet.")}</p>
          </article>
          <article class="summary-card">
            <span>Since last resume</span>
            <strong>{textValue(sinceLastResume?.summary_label, "Since last resume")}</strong>
            <p>{textValue(campaignHandoff?.what_changed_summary || sinceLastResume?.summary, "No fresh bounded delta is recorded yet.")}</p>
          </article>
          <article class="summary-card" data-testid="since-last-touch-summary">
            <span>Since last operator touch</span>
            <strong>{textValue(sinceLastTouch?.status_label, "No stored touch")}</strong>
            <p>{textValue(sinceLastTouch?.detail, "No local operator-touch comparison is available yet.")}</p>
          </article>
          <article class="summary-card">
            <span>Current blocker</span>
            <strong>{textValue(campaignHandoff?.current_blocker_label, "No blocker")}</strong>
            <p>{textValue(campaignHandoff?.current_blocker, "No blocking reason is currently recorded for this bounded session.")}</p>
          </article>
          <article class="summary-card">
            <span>Next action</span>
            <strong>{textValue(campaignHandoff?.recommended_next_action_label, textValue(primaryCta?.label, "Start governed execution"))}</strong>
            <p>{textValue(campaignHandoff?.recommended_next_action_detail, textValue(primaryCta?.detail, "No next action detail is recorded."))}</p>
          </article>
          <article class="summary-card">
            <span>Next likely stop</span>
            <strong>{textValue(campaignHandoff?.next_stop_boundary_label, nextStopBoundaryLabel)}</strong>
            <p>{textValue(campaignHandoff?.next_stop_boundary_summary, nextStopBoundarySummary)}</p>
          </article>
          <article class="summary-card">
            <span>Policy / headroom</span>
            <strong>{textValue(campaignHandoff?.policy_headroom_label, "Policy snapshot")}</strong>
            <p>{textValue(campaignHandoff?.policy_headroom_summary, textValue(longRunGuidance?.headroom_summary, "Headroom becomes visible after the first checkpoint."))}</p>
          </article>
          <article class="summary-card">
            <span>Attention counts</span>
            <strong>{textValue(campaignHandoff?.attention_blocking_count, attentionBlockingCount)} blocking</strong>
            <p>{textValue(campaignHandoff?.attention_informational_count, attentionInformationalCount)} informational · {campaignHandoff?.resume_ready_after_next_action ? "resume should be available after the next operator step" : "another bounded blocker still remains after the next operator step"}</p>
          </article>
        </div>
        {#if attentionSignal?.severity === "blocking" || currentHandoffEntry}
          <div class="toolbar">
            <button
              class="btn"
              type="button"
              disabled={attentionSignal?.severity !== "blocking" && !currentHandoffEntry}
              on:click={() => openCurrentAttentionTarget("campaign handoff summary")}
              data-testid="open-current-blocking-packet"
            >
              Open current blocking packet
            </button>
          </div>
        {/if}
        {#if attentionNavigationNotice}
          <p class="notice" data-testid="attention-navigation-note">{attentionNavigationNotice}</p>
        {/if}
        {#if attentionNavigationError}
          <p class="notice danger" data-testid="attention-navigation-error">{attentionNavigationError}</p>
        {/if}
      </section>
    {/if}

    <section class="panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">Run / session status</div>
          <h2>Current bounded run snapshot</h2>
        </div>
      </div>
      <div class="grid">
        <div><strong>Session state:</strong> {state.session.session_state || "unknown"}</div>
        <div><strong>Execution profile:</strong> {state.runtime.execution_profile || "unknown"}</div>
        <div><strong>Run status:</strong> {runningStatus}</div>
        <div><strong>Stop reason:</strong> {state.runtime.stop_reason || "none"}</div>
        <div><strong>Workspace:</strong> {state.artifacts.workspace_id || "none"}</div>
        <div><strong>Workflow stage:</strong> {state.session.workflow_stage || "unknown"}</div>
        <div><strong>Paused:</strong> {String(!!operatorState?.paused)}</div>
        <div><strong>Completed:</strong> {String(!!operatorState?.completed)}</div>
      </div>
      <p><strong>Next:</strong> {state.session.next_action || "n/a"} — {state.session.next_action_detail || ""}</p>
    </section>

    <section class="panel" id="bounded-continuation">
      <div class="section-header">
        <div>
          <div class="eyebrow">Bounded continuation pilot</div>
          <h2>Long-run session, checkpoints, and next action</h2>
          <p class="muted">This workspace panel is the operator home for approve, continue, pause, resume, and stop decisions after the first governed seed.</p>
        </div>
        <div class="toolbar">
          <button
            class="btn primary-action"
            data-testid="long-run-primary-cta"
            type="button"
            disabled={primaryCtaDisabled}
            on:click={runPrimaryCta}
          >
            {textValue(primaryCta?.label, "Start governed execution")}
          </button>
          <button class="btn secondary" type="button" disabled={controlBusy || !longRunSession || pauseControl?.available === false} on:click={() => runLongRunControl("pause")}>Pause</button>
          <button class="btn secondary" type="button" disabled={controlBusy || !longRunSession || resumeControl?.available === false} on:click={() => runLongRunControl("resume")}>Resume</button>
          <button class="btn secondary" type="button" disabled={controlBusy || !longRunSession || stopControl?.available === false} on:click={() => runLongRunControl("stop")}>Stop</button>
        </div>
      </div>
      {#if controlNotice}
        <p class="notice">{controlNotice}</p>
      {/if}
      {#if controlError}
        <p class="notice danger">{controlError}</p>
      {/if}
      <div class:warning-panel={!primaryCalloutSuccess} class:success-panel={primaryCalloutSuccess} class="status-callout primary-cta-callout">
        <p><strong>Primary next action:</strong> {textValue(primaryCta?.label, "Start governed execution")}</p>
        <p>{textValue(primaryCta?.detail || longRunSession?.recommended_next_action, "Start governed execution to seed the first bounded checkpoint.")}</p>
        {#if continuationBlockingReason}
          <p><strong>Blocking reason:</strong> {continuationBlockingReason}</p>
        {/if}
        <p><strong>Same-session continuity:</strong> {textValue(longRunGuidance?.same_session_summary, "The first governed execution seeds the long-run session; later continuation reuses that same session without reseeding.")}</p>
        <p><strong>Controls location:</strong> {textValue(longRunGuidance?.controls_location, "Use this workspace panel for review, continuation, pause, resume, and stop decisions.")}</p>
        {#if effectivePolicy}
          <p><strong>Effective continuation policy:</strong> {textValue(effectivePolicy?.continuation_strategy_label, "Continue one bounded step")} · total-cycle cap {effectiveMaxTotalCycles} · per-invocation cap {effectiveMaxCyclesPerInvocation}</p>
        {/if}
      </div>

      <div class="summary-grid continuation-grid">
        {#if continueControl}
          <article class="summary-card">
            <span>{textValue(continueControl.label, "Continue bounded session")}</span>
            <strong>{continueControl.available ? "Available now" : "Blocked"}</strong>
            <p>{textValue(continueControl.available ? continueControl.detail : continueControl.blocked_reason || continueControl.detail, "Continuation guidance is not available yet.")}</p>
          </article>
        {/if}
        {#if pauseControl}
          <article class="summary-card">
            <span>{textValue(pauseControl.label, "Pause")}</span>
            <strong>{pauseControl.available ? "Available now" : "Not needed now"}</strong>
            <p>{textValue(pauseControl.available ? pauseControl.detail : pauseControl.blocked_reason || pauseControl.detail, "Pause guidance is not available yet.")}</p>
          </article>
        {/if}
        {#if resumeControl}
          <article class="summary-card">
            <span>{textValue(resumeControl.label, "Resume session")}</span>
            <strong>{resumeControl.available ? "Available now" : "Blocked"}</strong>
            <p>{textValue(resumeControl.available ? resumeControl.detail : resumeControl.blocked_reason || resumeControl.detail, "Resume guidance is not available yet.")}</p>
          </article>
        {/if}
        {#if stopControl}
          <article class="summary-card">
            <span>{textValue(stopControl.label, "Stop")}</span>
            <strong>{stopControl.available ? "Available now" : "Not needed now"}</strong>
            <p>{textValue(stopControl.available ? stopControl.detail : stopControl.blocked_reason || stopControl.detail, "Stop guidance is not available yet.")}</p>
          </article>
        {/if}
      </div>

      <div class="summary-grid continuation-grid">
        <article class="summary-card">
          <span>Session</span>
          <strong>{textValue(longRunGuidance?.session_handle, "not-started")}</strong>
          <p>{textValue(longRunSession?.session_id, "No long-run session id yet.")}</p>
        </article>
        <article class="summary-card">
          <span>Lifecycle</span>
          <strong>{textValue(longRunGuidance?.state_label || longRunSession?.lifecycle_state, "not_started")}</strong>
          <p>lease {textValue(longRunSession?.lease_state, "not_started")} · watchdog {textValue(longRunSession?.watchdog_state, "healthy")}</p>
        </article>
        <article class="summary-card">
          <span>Checkpoint / cycle</span>
          <strong>{textValue(longRunSession?.checkpoint_count, "0")} checkpoint(s)</strong>
          <p>cycle {textValue(longRunSession?.current_cycle, "0")}/{effectiveMaxTotalCycles} · latest {latestCheckpointLabel}</p>
        </article>
        <article class="summary-card">
          <span>Headroom</span>
          <strong>{effectiveCyclesRemaining} cycle(s) left</strong>
          <p>{textValue(longRunGuidance?.headroom_summary, "Headroom becomes visible after the first checkpoint.")}</p>
        </article>
        <article class="summary-card">
          <span>Latest checkpoint</span>
          <strong>{latestCheckpointLabel}</strong>
          <p>{textValue(longRunSession?.last_checkpoint_at, "No checkpoint timestamp recorded yet.")}</p>
        </article>
        <article class="summary-card">
          <span>Profiles</span>
          <strong>{currentExecutionProfile}</strong>
          <p>expected {expectedExecutionProfile} · workspace {workspaceMaterialized ? "materialized" : "not materialized"}</p>
        </article>
        <article class="summary-card">
          <span>Supervisor / recovery</span>
          <strong>{textValue(longRunSession?.lease_state, "not_started")}</strong>
          <p>owner {textValue(longRunSession?.lease_owner_id, "none")} · restart headroom {effectiveRestartHeadroom}/{effectiveMaxRestartAttempts}</p>
        </article>
        <article class="summary-card">
          <span>Stop / completion</span>
          <strong>{textValue(longRunSession?.halt_reason || longRunSession?.completion_state, "in progress")}</strong>
          <p>{textValue(longRunSession?.recommended_next_action, "The next operator action appears here as the bounded session changes state.")}</p>
        </article>
      </div>

      <div class="status-callout info-panel" id="policy-and-headroom">
        <p><strong>Policy and headroom:</strong> Supported long-run policy fields can be edited here and apply to the next governed continuation launch for this same session.</p>
        <p>{textValue(effectivePolicy?.apply_scope_summary, "Saved policy applies to future governed continuation launches for this same bounded session.")}</p>
        <p>{textValue(effectivePolicy?.stop_boundary_summary, "Each continuation request advances within the currently saved bounded policy.")}</p>
      </div>
      {#if policyNotice}
        <p class="notice">{policyNotice}</p>
      {/if}
      {#if policyError}
        <p class="notice danger">{policyError}</p>
      {/if}
      <div class="summary-grid continuation-grid">
        <article class="summary-card">
          <span>Policy and headroom</span>
          <strong>{textValue(effectivePolicy?.continuation_strategy_label, "Continue one bounded step")}</strong>
          <p>total-cycle cap {effectiveMaxTotalCycles} · per-invocation cap {effectiveMaxCyclesPerInvocation}</p>
        </article>
        <article class="summary-card">
          <span>Supervisor</span>
          <strong>{effectivePolicy?.supervisor_enabled === false ? "Disabled" : "Enabled"}</strong>
          <p>{textValue(effectivePolicy?.read_only_notes?.supervisor_enabled, "Supervisor ownership and lease behavior stay governed and read-only in this surface.")}</p>
        </article>
        <article class="summary-card">
          <span>Restart budget</span>
          <strong>{effectiveRestartHeadroom}/{effectiveMaxRestartAttempts}</strong>
          <p>{textValue(effectivePolicy?.read_only_notes?.max_restart_attempts, "Restart attempt budget is displayed from session truth and is not editable from this surface yet.")}</p>
        </article>
      </div>
      <div class="card">
        <div class="section-header">
          <div>
            <div class="eyebrow">Policy and headroom</div>
            <h3>Operator-configurable long-run policy</h3>
            <p class="muted">This affects future same-session continuation launches. Review approval, pause, resume, stop, and supervisor ownership remain governed separately.</p>
          </div>
        </div>
        <div class="grid">
          <label>
            <strong>Continuation strategy</strong>
            <select
              aria-label="Continuation strategy"
              bind:value={policyStrategy}
              data-testid="continuation-strategy"
              disabled={policyBusy}
              on:change={() => (policyDirty = true)}
            >
              <option value="single_step">Single step</option>
              <option value="until_bounded_stop">Until next bounded stop</option>
            </select>
          </label>
          <label>
            <strong>Max total cycles</strong>
            <input
              aria-label="Max total cycles"
              bind:value={policyMaxTotalCycles}
              data-testid="policy-max-total-cycles"
              disabled={policyBusy}
              inputmode="numeric"
              min="1"
              on:input={() => (policyDirty = true)}
              type="number"
            />
          </label>
          <label>
            <strong>Max cycles per invocation</strong>
            <input
              aria-label="Max cycles per invocation"
              bind:value={policyMaxCyclesPerInvocation}
              data-testid="policy-max-cycles-per-invocation"
              disabled={policyBusy}
              inputmode="numeric"
              min="1"
              on:input={() => (policyDirty = true)}
              type="number"
            />
          </label>
        </div>
        <div class="toolbar wrap">
          <button
            class="btn secondary"
            data-testid="save-long-run-policy"
            type="button"
            disabled={policySaveDisabled}
            on:click={runSaveLongRunPolicy}
          >
            Save long-run policy
          </button>
        </div>
        <p><strong>Editable now:</strong> continuation strategy, max total cycles, and max cycles per invocation.</p>
        <p><strong>Read-only now:</strong> supervisor enabled = {String(effectivePolicy?.supervisor_enabled !== false)} · max restart attempts = {effectiveMaxRestartAttempts}</p>
        {#if lowTouchPolicyEnabled}
          <p class="muted">Low-touch mode is active: once review gates are clear, Continue will run this same session until the next bounded stop under the saved policy.</p>
        {:else}
          <p class="muted">Single-step mode is active: each Continue request advances one bounded step before returning to operator control.</p>
        {/if}
      </div>

      <p><strong>Operator summary:</strong> {textValue(longRunSession?.operator_summary, "No long-run session summary is available yet.")}</p>
      <p><strong>Recommended action:</strong> {textValue(longRunSession?.recommended_next_action, "Start or resume governed execution when the bounded lane is ready.")}</p>
      <p><strong>Bounded settings:</strong> {textValue(longRunGuidance?.settings_summary, "Bounded settings are not exposed in this surface yet.")}</p>
      {#if activeContinuationReviewGate}
        <div class="status-callout warning-panel" id="continuation-review-gate">
          <p><strong>Continuation review gate:</strong> A bounded review decision is still required before this session can continue from checkpoint {latestCheckpointLabel}.</p>
          <p><strong>Why:</strong> {textValue(intervention?.intervention?.reason || state?.intervention?.reason, "Review evidence first before continuing.")}</p>
          <p><strong>Next:</strong> {textValue(intervention?.intervention?.recommended_action_detail || state?.intervention?.recommended_action_detail, "Resolve the review item, then continue from the latest checkpoint.")}</p>
          {#if primaryCta?.action_id === "approve_and_continue" || primaryCta?.action_id === "approve_review_item"}
            <p class="muted">The primary action above is mapped from this exact gate so the operator does not have to infer whether approval or continuation comes first.</p>
          {/if}
          <div class="toolbar wrap">
            {#if primaryCta?.action_id === "approve_and_continue"}
              <button
                class="btn primary-action"
                data-testid="approve-and-continue"
                type="button"
                disabled={controlBusy || !primaryCtaAvailable}
                on:click={runPrimaryCta}
              >
                {textValue(primaryCta?.label, "Approve and continue")}
              </button>
            {/if}
            {#each blockingReviewOptions as option}
              {#if !(
                primaryCta?.action_id === "approve_review_item" &&
                String(option?.action_id || "").trim() === String(primaryCta?.preferred_review_action_id || "").trim() &&
                String(option?.review_item_id || "").trim() === String(primaryCta?.preferred_review_item_id || "").trim()
              )}
                <button
                  class:recommended-action={!!option?.recommended}
                  class="btn secondary"
                  type="button"
                  disabled={controlBusy || reviewTransitionPending || option?.available === false}
                  on:click={() => runReviewAction(option)}
                >
                  {textValue(option?.label || option?.action_label || option?.action_id, "Review action")}
                </button>
              {/if}
            {/each}
          </div>
        </div>
      {/if}
      {#if longRunSession?.duplicate_launch_blocked}
        <p class="notice danger">
          Duplicate launch blocked: {textValue(longRunSession?.duplicate_launch_reason, "active supervisor owner still holds the session lease")}
        </p>
      {/if}
      {#if longRunSession?.resume_blocked}
        <p class="notice danger">
          Resume is blocked: {textValue(longRunSession?.resume_blocked_reason, "checkpoint_invalid")}
        </p>
      {/if}
      <details class="details-panel">
        <summary>Technical continuation detail</summary>
        <div class="grid">
          <div><strong>Lifecycle:</strong> {textValue(longRunSession?.lifecycle_state, "not_started")}</div>
          <div><strong>Supervisor enabled:</strong> {String(!!longRunSession?.supervisor_enabled)}</div>
          <div><strong>Lease state:</strong> {textValue(longRunSession?.lease_state, "not_started")}</div>
          <div><strong>Lease owner:</strong> {textValue(longRunSession?.lease_owner_id, "none")}</div>
          <div><strong>Resume available:</strong> {String(!!longRunSession?.resume_available)}</div>
          <div><strong>Stale recovery:</strong> {String(!!longRunSession?.stale_recovery_available)}</div>
          <div><strong>Pause requested:</strong> {String(!!longRunSession?.operator_pause_requested)}</div>
          <div><strong>Stop requested:</strong> {String(!!longRunSession?.operator_stop_requested)}</div>
          <div><strong>Last checkpoint:</strong> {textValue(longRunSession?.last_checkpoint_at, "not yet checkpointed")}</div>
          <div><strong>Last heartbeat:</strong> {textValue(longRunSession?.last_heartbeat_at, "n/a")}</div>
          <div><strong>Lease acquired:</strong> {textValue(longRunSession?.lease_acquired_at, "n/a")}</div>
          <div><strong>Lease expires:</strong> {textValue(longRunSession?.lease_expires_at, "n/a")}</div>
          <div><strong>Next eligible:</strong> {textValue(longRunSession?.next_eligible_at, "n/a")}</div>
          <div><strong>Latest checkpoint id:</strong> {latestCheckpointLabel}</div>
          <div><strong>Resume from:</strong> {textValue(longRunSession?.resume_from_checkpoint_id, "fresh start")}</div>
          <div><strong>Halt reason:</strong> {textValue(longRunSession?.halt_reason, "none")}</div>
          <div><strong>Completion state:</strong> {textValue(longRunSession?.completion_state, "in_progress")}</div>
          <div><strong>Remaining wall clock:</strong> {textValue(longRunSession?.budget_remaining?.remaining_wall_clock_seconds, "0")}s</div>
        </div>
      </details>
    </section>

    <section class="panel" id="intervention-visibility">
      <div class="section-header">
        <div>
          <div class="eyebrow">Attention inbox</div>
          <h2>Active session attention and review queue</h2>
        </div>
      </div>
      <div class="summary-grid attention-delivery-grid" data-testid="attention-delivery-panel">
        <article class="summary-card">
          <span>Local attention delivery</span>
          <strong>{localAttentionDeliveryMode === "browser" ? "Browser + in-app" : "In-app only"}</strong>
          <p>{localAttentionDeliveryDetail}</p>
          <p><strong>Notification permission:</strong> {notificationPermissionState}</p>
          {#if notificationsSupported && notificationPermissionState !== "granted"}
            <button
              class="btn"
              type="button"
              on:click={requestLocalNotificationPermission}
              data-testid="enable-browser-notifications"
            >
              Enable local notifications
            </button>
          {/if}
        </article>
        <article class="summary-card">
          <span>Current local state</span>
          <strong data-testid="current-attention-local-state">{localAttentionStateLabel(currentHandoffEntry?.local_state)}</strong>
          <p>{textValue(currentHandoffEntry?.what_changed_summary, "No durable handoff packet is stored for this session in this browser yet.")}</p>
          <p><strong>Current blocker:</strong> {textValue(currentHandoffEntry?.current_blocker, "No active blocker is stored locally.")}</p>
          <p><strong>Next action:</strong> {textValue(currentHandoffEntry?.next_action_label, "Observe the current bounded state")}</p>
          <p><strong>Archive state:</strong> {archiveAttentionStateLabel(currentHandoffEntry)}</p>
          <p><strong>Stale rule:</strong> {staleAttentionRuleDetail}</p>
        </article>
        <article class="summary-card">
          <span>Attention memory</span>
          <strong>{unreadBlockingAttentionCount} new / {seenBlockingAttentionCount} seen</strong>
          <p>{acknowledgedBlockingAttentionCount} acknowledged unresolved · {staleEscalatedBlockingCount} stale escalated · {resolvedHandoffCount} resolved handoff packet(s) kept in bounded local history.</p>
          <p><strong>Latest resolved:</strong> {textValue(latestResolvedHandoffEntry?.checkpoint_id, "none")}</p>
          <p><strong>Active unresolved backlog:</strong> {unresolvedBlockingAttentionCount}</p>
        </article>
      </div>

      {#if archiveAttentionStateKey(currentHandoffEntry) === "stale_escalated_blocking"}
        <div class="status-callout warning-panel" data-testid="stale-attention-banner">
          <div class="event-topline">
            <strong>Stale unresolved blocker</strong>
            <span class="event-chip danger">stale escalated</span>
          </div>
          <p>This blocker was already acknowledged locally, but it still remains unresolved and is now escalated in the local workspace triage layer.</p>
          <p><strong>Next action:</strong> {textValue(currentHandoffEntry?.next_action_label, "Resolve the current blocking packet")}</p>
          <p><strong>Rule:</strong> {staleAttentionRuleDetail}</p>
          <div class="toolbar">
            <button
              class="btn"
              type="button"
              on:click={() => openCurrentAttentionTarget("stale attention banner")}
              data-testid="open-stale-blocking-packet"
            >
              Open stale blocker
            </button>
          </div>
        </div>
      {/if}

      <div class="toolbar wrap">
        <button
          class="btn"
          type="button"
          disabled={
            !currentHandoffEntry ||
            ["seen", "acknowledged", "resolved"].includes(String(currentHandoffEntry?.local_state || "").trim())
          }
          on:click={() => applyLocalAttentionState("seen")}
          data-testid="mark-attention-seen"
        >
          Mark attention seen
        </button>
        <button
          class="btn"
          type="button"
          disabled={
            !currentHandoffEntry ||
            ["acknowledged", "resolved"].includes(String(currentHandoffEntry?.local_state || "").trim())
          }
          on:click={() => applyLocalAttentionState("acknowledged")}
          data-testid="acknowledge-attention"
        >
          Acknowledge locally
        </button>
        <button
          class="btn"
          type="button"
          disabled={!currentHandoffEntry}
          on:click={() => applyLocalAttentionState("snoozed")}
          data-testid="snooze-attention"
        >
          Snooze local re-notify
        </button>
      </div>

      {#if localAttentionNotice}
        <p class="notice" data-testid="local-attention-notice">{localAttentionNotice}</p>
      {/if}
      {#if localAttentionError}
        <p class="notice danger" data-testid="local-attention-error">{localAttentionError}</p>
      {/if}

      {#if durableHandoffHistory.length}
        <div class="card intervention-card" data-testid="durable-handoff-history">
          <div class="event-topline">
            <strong>Durable handoff memory</strong>
            <span class="event-chip info">{durableHandoffHistory.length} recent packet(s)</span>
          </div>
          <p>
            Recent session handoff packets stay in this browser so refresh/reopen does not erase what changed, what was already seen, or what was resolved. Backend blocking truth still comes from the live workspace state above.
          </p>
          <div class="toolbar wrap" data-testid="archive-triage-toolbar">
            <button class:btn-primary={archiveTriageFilter === "all"} class="btn" type="button" on:click={() => setArchiveTriageFilter("all")} data-testid="archive-filter-all">All ({archiveFilterCount("all")})</button>
            <button class:btn-primary={archiveTriageFilter === "current"} class="btn" type="button" on:click={() => setArchiveTriageFilter("current")} data-testid="archive-filter-current">Current ({archiveFilterCount("current")})</button>
            <button class:btn-primary={archiveTriageFilter === "unresolved"} class="btn" type="button" on:click={() => setArchiveTriageFilter("unresolved")} data-testid="archive-filter-unresolved">Unresolved ({archiveFilterCount("unresolved")})</button>
            <button class:btn-primary={archiveTriageFilter === "stale"} class="btn" type="button" on:click={() => setArchiveTriageFilter("stale")} data-testid="archive-filter-stale">Stale escalated ({archiveFilterCount("stale")})</button>
            <button class:btn-primary={archiveTriageFilter === "resolved"} class="btn" type="button" on:click={() => setArchiveTriageFilter("resolved")} data-testid="archive-filter-resolved">Resolved ({archiveFilterCount("resolved")})</button>
            <button class:btn-primary={archiveTriageFilter === "informational"} class="btn" type="button" on:click={() => setArchiveTriageFilter("informational")} data-testid="archive-filter-informational">Informational ({archiveFilterCount("informational")})</button>
          </div>
          <p class="muted" data-testid="archive-triage-summary">
            Showing {filteredHandoffHistory.length} of {durableHandoffHistory.length} bounded handoff entries for the active session.
          </p>
          {#if filteredHandoffHistory.length === 0}
            <div class="card">
              <strong>No entries in this triage bucket</strong>
              <p class="muted">The active session archive does not currently have any entries in the selected category.</p>
            </div>
          {/if}
          {#each filteredHandoffHistory as item}
            <div
              class:active-intervention-card={isCurrentArchiveEntry(item)}
              class="card intervention-card"
              data-testid="handoff-archive-entry"
              data-archive-entry-state={archiveAttentionStateKey(item)}
              data-current-entry={isCurrentArchiveEntry(item) ? "true" : "false"}
              data-selected-entry={String(item.entry_key || "").trim() === String(archiveSelectionKey || "").trim() ? "true" : "false"}
              data-focused-target={focusedAttentionTargetId === archiveEntryTargetId(item.entry_key) ? "true" : undefined}
              id={archiveEntryTargetId(item.entry_key)}
              tabindex="-1"
            >
              <div class="event-topline">
                <strong>{textValue(item.handoff_label, "Campaign handoff packet")}</strong>
                <span class={`event-chip ${archiveAttentionStateTone(item)}`}>{archiveAttentionStateLabel(item)}</span>
                {#if isCurrentArchiveEntry(item)}
                  <span class="event-chip warning">Current entry</span>
                {:else if archiveAttentionStateKey(item) === "stale_escalated_blocking"}
                  <span class="event-chip danger">Historical stale blocker</span>
                {:else if item.active && Number(item.attention_blocking_count || 0) > 0}
                  <span class="event-chip info">Unresolved history</span>
                {:else if item.continuation_resumed_after_packet}
                  <span class="event-chip success">Continuation resumed</span>
                {/if}
                {#if item.active && Number(item.attention_blocking_count || 0) > 0}
                  <span class="event-chip warning">Blocking</span>
                {:else if Number(item.attention_informational_count || 0) > 0}
                  <span class="event-chip info">Informational</span>
                {:else}
                  <span class="event-chip success">Resolved</span>
                {/if}
              </div>
              <p><strong>Session:</strong> {textValue(item.session_handle || item.session_id, "n/a")} · checkpoint {textValue(item.checkpoint_id, "n/a")}</p>
              <p><strong>State:</strong> {textValue(item.state_label || item.lifecycle_state, "n/a")} · stop reason {textValue(item.stop_reason, "n/a")}</p>
              <p><strong>Packet lineage:</strong> {textValue(item.packet_id, "packet:none")} · belongs to current session lineage {String(belongsToCurrentSessionLineage(item))}</p>
              <p><strong>What changed:</strong> {textValue(item.what_changed_summary, "No compact delta summary was stored for this packet.")}</p>
              <p><strong>Next action then:</strong> {textValue(item.next_action_label, "Observe workspace")} · {textValue(item.next_action_detail, "No bounded detail was stored.")}</p>
              <p><strong>Next stop boundary:</strong> {textValue(item.next_stop_boundary_label, "n/a")} · recorded {formatRecordedAt(item.updated_at || item.created_at)}</p>
              <p><strong>Continuation resumed afterward:</strong> {String(!!item.continuation_resumed_after_packet)}</p>
              <div class="toolbar">
                <button
                  class="btn"
                  type="button"
                  on:click={() => openArchiveEntry(item)}
                  data-testid="open-handoff-archive-entry"
                >
                  {isCurrentArchiveEntry(item) && Number(item.attention_blocking_count || 0) > 0
                    ? "Open live packet"
                    : "Open archive entry"}
                </button>
              </div>
            </div>
          {/each}
        </div>
      {/if}

      <div
        class:warning-panel={reviewNeeded || reviewRequired}
        class:success-panel={!reviewNeeded && !reviewRequired}
        class="status-callout"
        data-testid="attention-inbox"
      >
        <p><strong>Blocking inbox items:</strong> {attentionBlockingCount}</p>
        <p><strong>Informational inbox items:</strong> {attentionInformationalCount}</p>
        <p><strong>Intervention required:</strong> {String(reviewNeeded || reviewRequired)}</p>
        <p><strong>Workspace state:</strong> {interventionWorkspaceLabel}</p>
        <p><strong>Active blocker:</strong> {interventionPrimaryTitle}</p>
        <p><strong>Intervention class:</strong> {interventionPrimaryReasonClass}</p>
        <p><strong>Why:</strong> {textValue(interventionSummary?.reason || state.intervention.reason, "No active intervention reason is recorded.")}</p>
        <p><strong>Recommended action:</strong> {textValue(interventionSummary?.recommended_action || state.intervention.recommended_action, "Stay in bounded review posture")}</p>
        <p><strong>Recommended detail:</strong> {textValue(interventionSummary?.recommended_action_detail || state.intervention.recommended_action_detail, "Persisted controller truth does not require a richer intervention surface yet.")}</p>
        <p><strong>After resolution:</strong> {textValue(interventionSummary?.next_state_after_review, "The next truthful state will be projected here after the current intervention item is resolved.")}</p>
        <p><strong>Next likely stop boundary:</strong> {nextStopBoundarySummary}</p>
        <p><strong>Resume outlook:</strong> {interventionResumeReadyDetail}</p>
        {#if activeContinuationReviewGate}
          <p class="muted">Use the dominant action in Continuation controls above. The same session will stay in this workspace; the panel refreshes after each recorded review action.</p>
        {/if}
      </div>

      <div class="summary-grid">
        <article class="summary-card">
          <span>Review loop progress</span>
          <strong>{interventionResolvedCount}/{Math.max(interventionTotalCount, interventionResolvedCount || 0)}</strong>
          <p>{textValue(interventionGuidance?.review_progress_summary, "No resolved intervention items are recorded yet in this loop.")}</p>
        </article>
        <article class="summary-card">
          <span>Blocking inbox items</span>
          <strong data-testid="attention-blocking-count">{attentionBlockingCount}</strong>
          <p>{textValue(primaryCta?.detail, "The next truthful review or continuation action will be projected here from backend state.")}</p>
        </article>
        <article class="summary-card">
          <span>Informational items</span>
          <strong>{attentionInformationalCount}</strong>
          <p>{attentionInformationalCount ? "These items stay visible for operator awareness but do not block continuation by themselves." : attentionEmptyStateDetail}</p>
        </article>
        <article class="summary-card">
          <span>Current packet</span>
          <strong>{textValue(attentionPacket?.label, attentionBlockingCount ? "Packet context pending" : "No active packet")}</strong>
          <p>{textValue(attentionPacket?.packet_summary || attentionPacket?.action_summary, attentionBlockingCount ? "Items stay grouped by their bounded review context." : "No blocking review packet is currently active.")}</p>
        </article>
        <article class="summary-card">
          <span>Same-session resume</span>
          <strong>{String(!!interventionGuidance?.resume_ready_after_review_clear)}</strong>
          <p>{interventionResumeReadyDetail}</p>
        </article>
        <article class="summary-card">
          <span>Current bounded state</span>
          <strong>{textValue(longRunSession?.lifecycle_state, "not_started")}</strong>
          <p>session {textValue(longRunSession?.session_id, "n/a")} · cycle {textValue(longRunSession?.current_cycle, "0")}/{effectiveMaxTotalCycles} · checkpoints {textValue(longRunSession?.checkpoint_count, "0")}</p>
        </article>
        <article class="summary-card">
          <span>Next likely stop</span>
          <strong>{nextStopBoundaryLabel}</strong>
          <p>{nextStopBoundarySummary}</p>
        </article>
      </div>

      {#if interventionLatestResolutionSummary}
        <p class="notice">
          Latest intervention resolution: {interventionLatestResolutionSummary}
          {#if interventionSummary?.latest_resolution_generated_at}
            {" "}({interventionSummary.latest_resolution_generated_at})
          {/if}
        </p>
      {/if}

      <div class="benchmark-grid">
        <article class="benchmark-card">
          <span>Review confirmation</span>
          <strong>{textValue(reviewConfirmation.review_confirmation_label || reviewConfirmation.review_confirmation_state, "n/a")}</strong>
          <p>{textValue(reviewConfirmation.next_operator_action_label || reviewConfirmation.next_operator_action, "Review gate preserved")}</p>
        </article>
        <article class="benchmark-card">
          <span>Decision source</span>
          <strong>{textValue(decisionSource.decision_source_label || decisionSource.decision_source_state, "n/a")}</strong>
          <p>{textValue(decisionSource.decision_source_kind, "No source-kind recorded")}</p>
        </article>
        <article class="benchmark-card">
          <span>Confirmed outcome</span>
          <strong>{textValue(confirmedOutcome.confirmed_outcome_label || confirmedOutcome.confirmed_outcome_state, "n/a")}</strong>
          <p>{textValue(reviewConfirmation.review_confirmation_recorded_at, "Recorded-at timestamp not surfaced in this payload")}</p>
        </article>
        <article class="benchmark-card">
          <span>Confirmation gap</span>
          <strong>{textValue(confirmationGap.confirmation_gap_label || confirmationGap.confirmation_gap_state, "n/a")}</strong>
          <p>{textValue(confirmationGap.exact_missing_confirmation_fields_summary, "No missing confirmation fields are currently recorded.")}</p>
        </article>
      </div>

      {#if attentionPacket}
        <div
          class:active-intervention-card={focusedAttentionTargetId === attentionPacketTargetId()}
          class="card intervention-card"
          data-testid="attention-packet"
          data-focused-target={focusedAttentionTargetId === attentionPacketTargetId() ? "true" : undefined}
          id={attentionPacketTargetId()}
          tabindex="-1"
        >
          <div class="event-topline">
            <strong>{textValue(attentionPacket?.label, "Current attention packet")}</strong>
            {#if attentionPacket?.batch_safe}
              <span class="event-chip success">Batch-safe packet</span>
            {:else}
              <span class="event-chip warning">Review one item at a time</span>
            {/if}
          </div>
          <p><strong>Packet size:</strong> {textValue(attentionPacket?.item_count, "0")} item(s)</p>
          <p><strong>Blocking items:</strong> {textValue(attentionPacket?.blocking_item_count, "0")} · informational items: {textValue(attentionPacket?.informational_item_count, "0")}</p>
          <p><strong>Audit lineage:</strong> session {textValue(attentionPacket?.session_handle || attentionPacket?.session_id, "n/a")} · checkpoint {textValue(attentionPacket?.checkpoint_id, "n/a")} · workspace {textValue(attentionPacket?.workspace_id, "n/a")}</p>
          <p><strong>What approving this packet does:</strong> {textValue(attentionPacket?.action_summary, "The next bounded review action is projected here from backend state.")}</p>
          <p><strong>What remains afterward:</strong> {textValue(attentionPacket?.remaining_after_packet_summary, "The next truthful remaining-state summary will appear here after this packet is resolved.")}</p>
        </div>
      {/if}

      {#if attentionBlockingItems.length}
        <div id="attention-blocking-list">
        <h3>Blocking attention items</h3>
        {#each attentionBlockingItems as item}
          <div
            class:active-intervention-card={String(item.review_item_id || "") === String(interventionSummary?.current_primary_review_item_id || "") || focusedAttentionTargetId === blockingItemTargetId(item)}
            class="card intervention-card"
            data-testid="blocking-attention-item"
            data-review-item-id={String(item.review_item_id || item.review_id || "")}
            data-focused-target={focusedAttentionTargetId === blockingItemTargetId(item) ? "true" : undefined}
            id={blockingItemTargetId(item)}
            tabindex="-1"
          >
            <div class="event-topline">
              <strong>{item.title || item.reason_summary || item.reason || item.review_id || "Intervention item"}</strong>
              {#if String(item.review_item_id || "") === String(interventionSummary?.current_primary_review_item_id || "")}
                <span class="event-chip warning">Current blocker</span>
              {/if}
            </div>
            <p><strong>Reason class:</strong> {textValue(item.reason_class, "n/a")}</p>
            <p><strong>Blocking reason:</strong> {textValue(item.reason_summary || item.reason, "No bounded reason summary was recorded.")}</p>
            <p><strong>Recommended action:</strong> {item.recommended_action || item.action_needed || "No action metadata found."}</p>
            <p><strong>Clears with:</strong> {textValue(item.action_label, "The dominant review action in this panel")}</p>
            <p><strong>Blocks continuation:</strong> {String(!!item.blocks_continuation)}</p>
            <p><strong>Resolvable now:</strong> {String(item.actionable_now !== false)}</p>
            <p><strong>Belongs to this session:</strong> {String(item.belongs_to_current_session_lineage !== false)}</p>
            <p><strong>Audit lineage:</strong> {textValue(item.lineage_summary, `session ${textValue(longRunSession?.session_id, "n/a")} · checkpoint ${latestCheckpointLabel}`)}</p>
            <p><strong>Surface hint:</strong> {textValue(item.surface_hint, "/shell/workspace")}</p>
          </div>
        {/each}
        </div>
      {:else}
        <p class="muted"><strong>{attentionEmptyStateLabel}.</strong> {attentionEmptyStateDetail}</p>
      {/if}

      {#if attentionInformationalItems.length}
        <h3>Informational attention items</h3>
        {#each attentionInformationalItems as item}
          <div class="card intervention-card">
            <div class="event-topline">
              <strong>{item.title || item.reason_summary || item.reason || item.review_id || "Informational attention item"}</strong>
              <span class="event-chip phase">Informational</span>
            </div>
            <p><strong>Reason class:</strong> {textValue(item.reason_class, "n/a")}</p>
            <p><strong>Why it is visible:</strong> {textValue(item.reason_summary || item.reason, "No informational attention summary was recorded.")}</p>
            <p><strong>Recommended action:</strong> {textValue(item.recommended_action || item.action_label, "Monitor the current bounded state")}</p>
            <p><strong>Belongs to this session:</strong> {String(item.belongs_to_current_session_lineage !== false)}</p>
            <p><strong>Audit lineage:</strong> {textValue(item.lineage_summary, `session ${textValue(longRunSession?.session_id, "n/a")} · checkpoint ${latestCheckpointLabel}`)}</p>
          </div>
        {/each}
      {/if}
    </section>
  {/if}

  <section class="panel">
    <div class="section-header">
      <div>
        <div class="eyebrow">Live runtime event stream</div>
        <h2>Operator-safe activity feed</h2>
      </div>
      <div class:live-badge={streamLive || !!lastHeartbeat} class="stream-badge">
        {streamStatus}
      </div>
    </div>
    <p class="muted">Heartbeat frames stay in the stream badge so meaningful runtime events remain easier to scan.</p>
    <p class="muted">Last heartbeat: {lastHeartbeat || "waiting"}</p>
    <div class="live-summary-grid">
      <article class="summary-card">
        <span>Meaningful events captured</span>
        <strong>{meaningfulEventCount}</strong>
        <p>{streamStatus}</p>
      </article>
      <article class="summary-card">
        <span>Latest meaningful event</span>
        <strong>{textValue(latestMeaningfulEvent?.event_type, "Waiting for runtime activity")}</strong>
        <p>{textValue(latestMeaningfulEvent?.message, "Heartbeat-only mode so far.")}</p>
      </article>
    </div>
    {#if continuationHighlights.length}
      <h3>Recent continuation milestones</h3>
      <div class="milestone-grid">
        {#each continuationHighlights as item}
          <article class="card milestone-card">
            <div class="event-topline">
              <span class={`event-chip ${eventTone(item)}`}>{item.event_type || "event"}</span>
              <span class="event-chip phase">{item.phase || "phase"}</span>
            </div>
            <strong>{textValue(item.message, "Continuation activity recorded.")}</strong>
            <p class="muted">{textValue(item.timestamp, "timestamp unavailable")}</p>
          </article>
        {/each}
      </div>
    {/if}
    {#if events.length === 0}
      <p class="muted">{liveFeedEmptyMessage}</p>
    {:else}
      <div class="stream">
        {#each events as item}
          <div class="event-row">
            <div class="event-topline">
              <strong>{item.timestamp}</strong>
              <span class={`event-chip ${eventTone(item)}`}>{item.event_type || "event"}</span>
              <span class="event-chip phase">{item.phase || "phase"}</span>
            </div>
            <p>{item.message}</p>
            {#if item.artifact_path}
              <small>artifact: {item.artifact_path}</small>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </section>

  {#if state}
    <section class="panel" id="runtime-artifacts">
      <div class="section-header">
        <div>
          <div class="eyebrow">Runtime artifacts</div>
          <h2>Current bounded outputs</h2>
        </div>
      </div>
      <div class="grid">
        <div><strong>Workspace root:</strong> {state.artifacts.workspace_root || "n/a"}</div>
        <div><strong>Session artifact index:</strong> {state.artifacts.latest_artifact_index_path || "n/a"}</div>
        <div><strong>Event log:</strong> {state.artifacts.runtime_event_log_path || "n/a"}</div>
      </div>
      <h3>Recent outputs</h3>
      {#if state.artifacts.output_artifact_paths?.length}
        <ul>
          {#each state.artifacts.output_artifact_paths as item}
            <li>{item}</li>
          {/each}
        </ul>
      {:else}
        <p class="muted">No runtime output artifacts yet.</p>
      {/if}
    </section>
  {/if}
</main>

<style>
  .workspace-shell {
    max-width: 980px;
    margin: 0 auto;
    padding: 1rem;
    font-family: "Segoe UI Variable Text", "Aptos", "Trebuchet MS", sans-serif;
  }
  .workspace-hero {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    margin-bottom: 1rem;
    padding: 1rem;
    border-radius: 14px;
    border: 1px solid #253c5d;
    background: linear-gradient(120deg, #0d1830, #112544 58%, #0e1627);
  }
  .toolbar {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .toolbar.wrap {
    display: grid;
    width: 100%;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  }
  .btn {
    border: 1px solid #2d4668;
    background: #2b4265;
    color: #e8edf4;
    text-decoration: none;
    padding: 0.45rem 0.75rem;
    border-radius: 7px;
  }
  .btn.primary-action {
    border-color: rgba(42, 184, 152, 0.72);
    background: linear-gradient(135deg, #177364, #1e8d79 62%, #2ba59d);
    color: #f4fffb;
    box-shadow: 0 10px 24px rgba(16, 69, 61, 0.26);
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .panel {
    background: #111b2b;
    border: 1px solid #23324c;
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1rem;
  }
  .summary-grid,
  .benchmark-grid,
  .live-summary-grid {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    margin-bottom: 1rem;
  }
  .summary-card,
  .benchmark-card {
    border: 1px solid #2b415f;
    border-radius: 12px;
    padding: 0.9rem;
    background: linear-gradient(180deg, rgba(18, 28, 44, 0.98), rgba(16, 25, 40, 0.98));
    display: grid;
    gap: 0.25rem;
  }
  .summary-card span,
  .benchmark-card span,
  .eyebrow {
    color: #8aa4c8;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.74rem;
  }
  .summary-card strong,
  .benchmark-card strong {
    font-size: 1rem;
  }
  .section-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
    flex-wrap: wrap;
    margin-bottom: 0.9rem;
  }
  .grid {
    display: grid;
    gap: 0.35rem;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    margin-bottom: 0.4rem;
  }
  .muted {
    color: #8fa1bd;
  }
  .status-callout {
    border-radius: 12px;
    padding: 0.95rem;
    border: 1px solid #2b415f;
    margin-bottom: 1rem;
  }
  .primary-cta-callout {
    background: linear-gradient(135deg, rgba(16, 69, 61, 0.18), rgba(17, 31, 49, 0.92));
  }
  .warning-panel {
    background: rgba(94, 55, 13, 0.34);
    border-color: rgba(234, 143, 0, 0.38);
  }
  .success-panel {
    background: rgba(16, 69, 61, 0.26);
    border-color: rgba(42, 184, 152, 0.34);
  }
  .recommended-action {
    border-color: rgba(42, 184, 152, 0.55);
    box-shadow: inset 0 0 0 1px rgba(42, 184, 152, 0.28);
  }
  .notice {
    padding: 0.5rem 0.7rem;
    border: 1px solid #3a4d69;
    border-radius: 8px;
    background: #1b2d44;
  }
  .notice.danger {
    background: #3d1d23;
    border-color: #a33f50;
  }
  .card {
    border: 1px solid #2b415f;
    padding: 0.5rem;
    margin-bottom: 0.4rem;
    border-radius: 8px;
    background: #151f31;
  }
  .intervention-card {
    display: grid;
    gap: 0.2rem;
  }
  .active-intervention-card {
    border-color: rgba(234, 143, 0, 0.52);
    box-shadow: inset 0 0 0 1px rgba(234, 143, 0, 0.18);
    background: linear-gradient(180deg, rgba(61, 40, 11, 0.62), rgba(21, 31, 49, 0.96));
  }
  [data-focused-target="true"] {
    border-color: rgba(42, 184, 152, 0.62);
    box-shadow: 0 0 0 1px rgba(42, 184, 152, 0.28), 0 0 0 4px rgba(42, 184, 152, 0.08);
  }
  .stream-badge {
    border: 1px solid #2b415f;
    border-radius: 999px;
    padding: 0.4rem 0.75rem;
    color: #9bb0cd;
    background: rgba(17, 31, 49, 0.88);
  }
  .stream-badge.live-badge {
    color: #a7f3d0;
    border-color: rgba(42, 184, 152, 0.42);
    background: rgba(16, 69, 61, 0.24);
  }
  .attention-action-signal {
    cursor: pointer;
  }
  .attention-action-signal:focus-visible {
    outline: 2px solid rgba(42, 184, 152, 0.72);
    outline-offset: 2px;
  }
  .attention-badge-blocking {
    color: #ffd37a;
    border-color: rgba(234, 143, 0, 0.42);
    background: rgba(94, 55, 13, 0.4);
  }
  .attention-badge-info {
    color: #d6e8ff;
    border-color: rgba(93, 141, 209, 0.42);
    background: rgba(19, 47, 88, 0.34);
  }
  .stream {
    max-height: 380px;
    overflow: auto;
    border: 1px solid #253c5d;
    border-radius: 8px;
    padding: 0.6rem;
  }
  .event-row {
    margin-bottom: 0.7rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid #253a5c;
  }
  .event-topline {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem;
    margin-bottom: 0.35rem;
  }
  .event-chip {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.18rem 0.5rem;
    font-size: 0.72rem;
    border: 1px solid #355072;
    background: rgba(27, 45, 68, 0.82);
    color: #d7e4f7;
  }
  .event-chip.phase {
    border-color: #4b6184;
    color: #a5bddc;
  }
  .event-chip.info {
    border-color: rgba(93, 141, 209, 0.45);
  }
  .event-chip.success {
    border-color: rgba(42, 184, 152, 0.45);
    color: #a7f3d0;
  }
  .event-chip.warning {
    border-color: rgba(234, 143, 0, 0.45);
    color: #ffd37a;
  }
  .event-chip.danger {
    border-color: rgba(214, 98, 98, 0.45);
    color: #ffb4b4;
  }
  .event-row small {
    color: #9eb5d5;
  }
  .continuation-grid {
    margin-top: 0.8rem;
  }
  .details-panel {
    margin-top: 0.8rem;
    border: 1px solid #253c5d;
    border-radius: 10px;
    padding: 0.8rem 0.9rem;
    background: rgba(17, 27, 43, 0.66);
  }
  .details-panel summary {
    cursor: pointer;
    font-weight: 600;
    margin-bottom: 0.75rem;
  }
  .milestone-grid {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    margin-bottom: 1rem;
  }
  .milestone-card {
    display: grid;
    gap: 0.35rem;
    padding: 0.75rem;
    border-radius: 12px;
  }
  @media (max-width: 720px) {
    .workspace-hero {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
