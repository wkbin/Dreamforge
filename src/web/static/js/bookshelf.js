function syncBookshelfSelection() {
  window.__ZAOMENG_BOOKSHELF_LEGACY_RENDER__?.syncBookshelfSelection?.();
}

const WORK_OVERVIEW_STATE = window.__ZAOMENG_WORK_OVERVIEW_STATE__ || {};

function buildRunStatusBannerState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildRunStatusBannerState === "function") {
    return WORK_OVERVIEW_STATE.buildRunStatusBannerState(run);
  }
  return { visible: false, kicker: "", stage: "", description: "" };
}

function buildWorkActionState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkActionState === "function") {
    return WORK_OVERVIEW_STATE.buildWorkActionState(run);
  }
  return {
    primaryVisible: false,
    secondaryVisible: false,
    softenSecondary: false,
    actionNoteVisible: false,
    actionNote: "",
    primaryButtons: [],
    secondaryButtons: [],
  };
}

function buildWorkTopOverviewState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkTopOverviewState === "function") {
    return WORK_OVERVIEW_STATE.buildWorkTopOverviewState(run);
  }
  return {
    title: run ? `《${runNovelTitle(run)}》` : "人物与关系正在慢慢浮现",
    progressCopy: String(run?.progress?.message || "").trim() || "人物与关系会依次浮现。",
    nextStep: "这一卷的下一步会在这里告诉你。",
    banner: buildRunStatusBannerState(run),
    heroMetrics: [],
    progressMetrics: [],
    actions: buildWorkActionState(run),
  };
}

window.__ZAOMENG_BUILD_WORK_TOP_STATE__ = buildWorkTopOverviewState;

const BOOKSHELF_BRIDGE_TOOLS = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};

function runDetailActions() {
  if (typeof BOOKSHELF_BRIDGE_TOOLS.readLegacyActionBridge === "function") {
    return BOOKSHELF_BRIDGE_TOOLS.readLegacyActionBridge("__ZAOMENG_RUN_DETAIL_ACTIONS__");
  }
  return window.__ZAOMENG_RUN_DETAIL_ACTIONS__ || {};
}

function renderRunFallbackFromBookshelf(run) {
  if (!run || typeof run !== "object") {
    throw new Error("这卷的详情数据暂时不可用。");
  }
  if (typeof setWorkOverviewLoading === "function") {
    setWorkOverviewLoading(false);
  }
  setStatus("bookshelf-status", "");
  currentRunId = String(run.run_id || "").trim();
  currentRun = run;
  newRunFlowOpen = false;
  chatModePickerOpen = false;
  characterOverviewOpen = false;
  currentCharacterOverview = null;
  redistillPanelOpen = false;
  sourceHistoryExpanded = false;
  characterReadinessExpanded = false;
  workSessionPreviewExpanded = false;
  runCreationPending = run.status === "running" && run.summary?.status_text !== "workflow_complete";
  if (typeof resetDialogueView === "function") {
    resetDialogueView();
  }
  renderBookshelfDetail(run);
  syncBookshelfSelection();
  if (typeof updateWorkflowState === "function") {
    updateWorkflowState();
  }
  if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("run-rendered-fallback");
  }
  return run;
}

function renderBookshelfDetail(run) {
  const topState = buildWorkTopOverviewState(run);
  const actionState = topState.actions;
  setText("run-stage-title", topState.title, "");
  setText("progress-copy", topState.progressCopy, "");
  setText("work-overview-next-step", topState.nextStep, "");
  renderRunStatusBanner(run);

  const graphRoot = el("graph-links");
  if (graphRoot && !run) {
    graphRoot.innerHTML = "";
    graphRoot.classList.add("hidden");
  }
  toggle("graph-empty-note", !run);

  const profilesRoot = el("bookshelf-character-links");
  if (profilesRoot) {
    profilesRoot.innerHTML = "";
    if (run) {
      (run.artifact_index?.characters || []).forEach((item) => {
        const url = run.file_urls?.[`character_${item.name}`];
        if (!url) return;
        const link = document.createElement("a");
        link.href = url;
        link.textContent = item.name;
        link.target = "_blank";
        link.rel = "noreferrer";
        profilesRoot.appendChild(link);
      });
    }
    profilesRoot.classList.toggle("hidden", profilesRoot.childElementCount === 0);
    toggle("character-empty-note", profilesRoot.childElementCount === 0);
  }

  const eventsRoot = el("events");
  if (eventsRoot) {
    eventsRoot.classList.toggle("hidden", !run || !(run.events || []).length);
    toggle("timeline-empty-note", !run || !(run.events || []).length);
  }

  const chatButton = el("detail-start-chat-button");
  if (chatButton) {
    const item = actionState.primaryButtons.find((entry) => entry.key === "chat");
    chatButton.disabled = Boolean(item?.disabled);
    chatButton.classList.toggle("hidden", Boolean(item?.hidden));
  }
  const redistillButton = el("detail-redistill-button");
  if (redistillButton) {
    const item = actionState.primaryButtons.find((entry) => entry.key === "redistill");
    redistillButton.disabled = Boolean(item?.disabled);
    redistillButton.classList.toggle("hidden", Boolean(item?.hidden));
    redistillButton.textContent = item?.label || "继续蒸馏";
  }
  const stopButton = el("detail-stop-run-button");
  if (stopButton) {
    const item = actionState.primaryButtons.find((entry) => entry.key === "stop");
    stopButton.disabled = Boolean(item?.disabled);
    stopButton.classList.toggle("hidden", Boolean(item?.hidden));
    stopButton.textContent = item?.label || "停止蒸馏";
  }
  const reviewButton = el("open-persona-review-button");
  const detailActions = el("detail-primary-actions");
  if (detailActions) {
    detailActions.classList.toggle("hidden", !actionState.primaryVisible);
  }
  if (reviewButton) {
    const item = actionState.primaryButtons.find((entry) => entry.key === "review");
    reviewButton.classList.remove("hidden");
    reviewButton.disabled = Boolean(item?.disabled);
  }
  const relationButton = el("open-relation-details-button");
  const hasRelation = Boolean(run?.artifact_index?.relation_graph?.relations_file);
  if (relationButton) {
    relationButton.classList.remove("hidden");
    relationButton.disabled = !hasRelation;
  }
  const exportButton = el("detail-export-summary-button");
  let hasExport = false;
  if (exportButton) {
    hasExport = !actionState.secondaryButtons.find((entry) => entry.key === "export")?.disabled;
    exportButton.classList.remove("hidden");
    exportButton.disabled = !hasExport;
  }
  const graphButton = el("detail-view-graph-button");
  let hasGraphLink = false;
  if (graphButton) {
    hasGraphLink = !actionState.secondaryButtons.find((entry) => entry.key === "graph")?.disabled;
    graphButton.classList.remove("hidden");
    graphButton.disabled = !hasGraphLink;
    graphButton.onclick = () => {
      const target = run?.file_urls?.graph_html || run?.file_urls?.graph_svg || "";
      if (!target) return;
      window.open(target, "_blank", "noopener,noreferrer");
    };
  }
  toggle("detail-secondary-actions-shell", actionState.secondaryVisible);
  const secondaryActions = el("detail-secondary-actions");
  if (secondaryActions) {
    secondaryActions.classList.toggle("is-softened", actionState.softenSecondary);
  }
  toggle("detail-action-note", actionState.actionNoteVisible);
  setText("detail-action-note", actionState.actionNote, "");
}

function renderRunStatusBanner(run) {
  const state = buildRunStatusBannerState(run);
  toggle("run-status-banner", state.visible);
  if (!state.visible) return;
  setText("run-status-kicker", state.kicker, "");
  setText("run-status-stage", state.stage, "");
  setText("run-status-description", state.description, "");
}

function renderBookshelf(runs) {
  window.__ZAOMENG_BOOKSHELF_LEGACY_RENDER__?.renderBookshelf?.(runs);
}

function formatBookshelfDeleteStatus(title, payload) {
  return window.__ZAOMENG_BOOKSHELF_STATE__?.formatBookshelfDeleteStatus?.(title, payload) || "";
}

function getBookshelfCardState(run) {
  return window.__ZAOMENG_BOOKSHELF_STATE__?.getBookshelfCardState?.(run) || { className: "" };
}

async function loadRunsOverview() {
  if (!allRuns.length && typeof setWorkOverviewLoading === "function") {
    setWorkOverviewLoading(true, "正在载入作品列表...");
  }
  const data = await apiJson("/api/web/runs");
  allRuns = Array.isArray(data.items) ? data.items : [];
  renderBookshelf(allRuns);
  if (typeof setWorkOverviewLoading === "function") {
    setWorkOverviewLoading(false);
  }
  if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("runs-overview-loaded");
  }
  return allRuns;
}

async function openBookshelfRun(runId) {
  const target = String(runId || "").trim();
  if (!target) return null;
  if (typeof setWorkOverviewLoading === "function") {
    setWorkOverviewLoading(true, "正在载入这一卷...");
  }
  const freshRun = await apiJson(`/api/web/runs/${target}`);
  const actions = runDetailActions();
  if (typeof actions.renderRunView === "function") {
    actions.renderRunView(freshRun);
  } else if (typeof actions.refreshRunView === "function") {
    await actions.refreshRunView(target);
  } else if (typeof window.renderRun === "function") {
    window.renderRun(freshRun);
  } else {
    renderRunFallbackFromBookshelf(freshRun);
  }
  return freshRun;
}

async function deleteBookshelfRun(runId, title = "") {
  const target = String(runId || "").trim();
  if (!target) return null;
  const deleted = await apiJson(`/api/web/runs/${target}`, { method: "DELETE" }, "删除失败。");
  const currentTitle = String(title || "").trim();
  if (currentTitle && currentRun && typeof runNovelTitle === "function" && runNovelTitle(currentRun) === currentTitle) {
    showBookshelfHome();
  }
  await loadRecentSessions();
  await loadRunsOverview();
  return deleted;
}

function showBookshelfHome() {
  stopRunPolling();
  currentRunId = "";
  currentRun = null;
  newRunFlowOpen = false;
  redistillPanelOpen = false;
  sourceHistoryExpanded = false;
  sidebarCollapsed = false;
  setStatus("bookshelf-status", "");
  if (typeof setWorkOverviewLoading === "function") {
    setWorkOverviewLoading(false);
  }
  resetDialogueView();
  renderBookshelfDetail(null);
  applySidebarState();
  updateWorkflowState();
  syncBookshelfSelection();
}

function startNewRunFlow() {
  stopRunPolling();
  currentRunId = "";
  currentRun = null;
  newRunFlowOpen = true;
  redistillPanelOpen = false;
  sourceHistoryExpanded = false;
  sidebarCollapsed = false;
  setStatus("bookshelf-status", "");
  if (typeof setWorkOverviewLoading === "function") {
    setWorkOverviewLoading(false);
  }
  resetDialogueView();
  renderBookshelfDetail(null);
  applySidebarState();
  updateWorkflowState();
  syncBookshelfSelection();
  el("characters")?.focus();
}

if (typeof BOOKSHELF_BRIDGE_TOOLS.mergeLegacyActionBridge === "function") {
  BOOKSHELF_BRIDGE_TOOLS.mergeLegacyActionBridge("__ZAOMENG_BOOKSHELF_ACTIONS__", {
    deleteRun: deleteBookshelfRun,
    openRun: openBookshelfRun,
  });
} else {
  window.__ZAOMENG_BOOKSHELF_ACTIONS__ = {
    ...(window.__ZAOMENG_BOOKSHELF_ACTIONS__ || {}),
    deleteRun: deleteBookshelfRun,
    openRun: openBookshelfRun,
  };
}
