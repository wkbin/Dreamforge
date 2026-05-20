function syncTopbar() {
  if (!modelSettings.configured) {
    setText("topbar-title", "让故事先拥有声音");
    return;
  }
  if (newRunFlowOpen) {
    setText("topbar-title", "把新故事放上书架");
    return;
  }
  if (runCreationPending) {
    setText("topbar-title", currentRun ? `《${runNovelTitle(currentRun)}》正在慢慢成形` : "人物正在慢慢成形");
    return;
  }
  if (currentRun) {
    setText("topbar-title", `《${runNovelTitle(currentRun)}》`);
    return;
  }
  setText("topbar-title", "从书架挑一卷继续往下走");
}

function applyModelSettingsView() {
  ensureConnectionDetailsVisible();
  setValue("model-provider", modelSettings.provider || "openai-compatible");
  setValue("model-name", modelSettings.model || "");
  setValue("model-base-url", modelSettings.base_url || "");
  setValue("model-api-key", "");
  setValue("model-max-tokens", modelSettings.max_tokens > 0 ? modelSettings.max_tokens : "");
  const apiKeyInput = el("model-api-key");
  if (apiKeyInput) {
    apiKeyInput.placeholder = modelSettings.api_key_configured
      ? "当前密钥已保存，如需更换再填写"
      : "把密钥放在这里，故事才会真正开口";
  }
  setText(
    "model-api-key-hint",
    modelSettings.api_key_configured ? "当前密钥已经保存，留空提交时会继续沿用。" : "留空时会沿用已经保存的密钥。",
    ""
  );
  const maxTokensInput = el("model-max-tokens");
  if (maxTokensInput) {
    maxTokensInput.placeholder =
      modelSettings.max_tokens > 0 ? String(modelSettings.max_tokens) : "留空或填 0，则沿用推荐值";
  }
  setText(
    "model-max-tokens-hint",
    modelSettings.max_tokens > 0
      ? `当前单次输出上限为 ${modelSettings.max_tokens}，留空或填 0 会改回默认值。`
      : "当前未另设单次输出上限，会沿用默认值。",
    ""
  );
  setText(
    "sidebar-status",
    modelSettings.configured
      ? "故事声源已接通"
      : "故事声源尚未接通"
  );
  setText("model-provider-view", humanizeProvider(modelSettings.provider));
  toggle("model-summary", modelSettings.configured);
  syncChoiceGroup("model-provider-options", "model-provider");
  syncTopbar();
  if (typeof window.__ZAOMENG_UI_BRIDGE_TOOLS__?.syncLegacyUiState === "function") {
    window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("model-settings-view", { modelSettings });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("model-settings-view");
  }
}

function buildWorkflowVisibilityState() {
  const configured = Boolean(modelSettings.configured);
  const hasRun = Boolean(currentRunId && currentRun);
  const hasCharacters = Boolean(currentRun?.artifact_index?.characters?.length);
  const hasSession = Boolean(currentDialogueSessionId) || sessionBooting;
  const failed = currentRun?.status === "failed";

  const showModel = !configured;
  const showBookshelf = configured && !newRunFlowOpen && !hasRun && !hasSession && !sessionBooting;
  const showDistill = configured && newRunFlowOpen && !hasRun && !hasSession && !sessionBooting;
  const showCharacterOverview = configured && hasRun && characterOverviewOpen && !hasSession && !sessionBooting;
  const showProgress = configured && hasRun && !chatModePickerOpen && !showCharacterOverview && !hasSession && !sessionBooting;
  const showChatSetup = configured && hasCharacters && chatModePickerOpen && !hasSession && !sessionBooting;
  return {
    configured,
    hasRun,
    hasCharacters,
    hasSession,
    failed,
    workflowBootPending: Boolean(workflowBootPending),
    showModel,
    showBookshelf,
    showDistill,
    showCharacterOverview,
    showProgress,
    showChatSetup,
    sessionBooting: Boolean(sessionBooting),
    newRunFlowOpen: Boolean(newRunFlowOpen),
    chatModePickerOpen: Boolean(chatModePickerOpen),
    characterOverviewOpen: Boolean(characterOverviewOpen),
    redistillPanelOpen: Boolean(redistillPanelOpen),
  };
}

function updateWorkflowState() {
  const state = buildWorkflowVisibilityState();

  toggle("step-model", state.showModel);
  toggle("bookshelf-section", state.showBookshelf);
  toggle("step-distill", state.showDistill);
  toggle("step-progress", state.showProgress);
  toggle("step-character-overview", state.showCharacterOverview);
  toggle("redistill-panel", state.showProgress && state.redistillPanelOpen);
  toggle("step-chat-setup", state.showChatSetup);
  toggle("turn-stage", state.configured && state.hasSession && !state.sessionBooting);
  toggle("dialogue-empty", !state.hasSession);
  toggle("dialogue-detail", state.hasSession);
  toggle("workflow-strip", !state.workflowBootPending && !(state.hasSession || state.sessionBooting));

  const workflowStrip = el("workflow-strip");
  if (workflowStrip) {
    const visibleCount = ["bookshelf-section", "step-model", "step-distill", "step-progress", "step-character-overview", "step-chat-setup"].filter(
      (id) => !el(id)?.classList.contains("hidden")
    ).length;
    const showSingleStage = visibleCount <= 1;
    workflowStrip.classList.toggle("single-stage", showSingleStage);
    state.visibleStageCount = visibleCount;
    state.showSingleStage = showSingleStage;
  }

  const experienceShell = el("experience-shell");
  if (experienceShell) {
    experienceShell.classList.toggle("dialogue-layout", state.hasSession || state.sessionBooting);
  }

  window.__ZAOMENG_WORKFLOW_STATE__ = state;
  syncTopbar();
  if (typeof window.__ZAOMENG_UI_BRIDGE_TOOLS__?.syncLegacyUiState === "function") {
    window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("workflow-update", { workflow: state });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("workflow-update", { workflow: state });
  }
}

function applyRunViewFallback(run, options = {}) {
  if (!run || typeof run !== "object") {
    return null;
  }
  currentRunId = String(run.run_id || currentRunId || "").trim();
  currentRun = run;
  newRunFlowOpen = false;
  chatModePickerOpen = false;
  characterOverviewOpen = false;
  currentCharacterOverview = null;
  redistillPanelOpen = false;
  sourceHistoryExpanded = false;
  characterReadinessExpanded = false;
  workSessionPreviewExpanded = false;
  runCreationPending = run.status === "running" && !isRunWorkflowComplete(run);
  if (!options.preserveDialogue) {
    resetDialogueView();
  }
  if (typeof renderBookshelfDetail === "function") {
    renderBookshelfDetail(run);
  }
  if (typeof syncBookshelfSelection === "function") {
    syncBookshelfSelection();
  }
  updateWorkflowState();
  if (typeof window.__ZAOMENG_UI_BRIDGE_TOOLS__?.syncLegacyUiState === "function") {
    window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("run-rendered-workflow-fallback", {
      currentRunId,
      currentRun: run,
      currentCharacterOverview: null,
      workflow: window.__ZAOMENG_WORKFLOW_STATE__ || {},
    });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("run-rendered-workflow-fallback");
  }
  return run;
}

function applyRunView(run, options = {}) {
  const actions = window.__ZAOMENG_RUN_DETAIL_ACTIONS__ || {};
  if (typeof actions.renderRunView === "function") {
    actions.renderRunView(run, options);
    return true;
  }
  if (typeof window.renderRun === "function") {
    window.renderRun(run, options);
    return true;
  }
  applyRunViewFallback(run, options);
  return false;
}

window.__ZAOMENG_APPLY_RUN_VIEW__ = applyRunView;

async function openNewDialogueSession() {
  let run = currentRun;
  if (!run || !run.run_id) {
    run = await loadLatestRun().catch((error) => {
      console.warn("loadLatestRun failed", error);
      return null;
    });
    if (run?.run_id) {
      applyRunView(run);
    }
  }
  if (!run?.run_id) {
    startNewRunFlow();
    setStatus("form-status", "先挑一本书，把人物请出来，才能开始这一幕。");
    return;
  }
  if (!run?.artifact_index?.characters?.length) {
    applyRunView(run);
    setStatus("redistill-status", "这一卷还没有可入场的人物，等人物先整理出来。");
    return;
  }

  resetDialogueView();
  chatModePickerOpen = true;
  characterOverviewOpen = false;
  maybePrefillChatSetup(run);
  updateWorkflowState();
  if (typeof publishChatSetupState === "function") {
    publishChatSetupState("chat-setup-opened");
  }
  el("chat-setup-vue-root")?.focus();
}

async function loadModelSettings() {
  modelSettings = await apiJson("/api/web/settings/model");
  applyModelSettingsView();
  updateWorkflowState();
  if (!modelSettings.configured) {
    openSettingsModal();
  }
  if (typeof window.__ZAOMENG_UI_BRIDGE_TOOLS__?.syncLegacyUiState === "function") {
    window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("model-settings-loaded", { modelSettings });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("model-settings-loaded");
  }
}

function resetDialogueView() {
  currentDialogueSessionId = "";
  currentDialogueSession = null;
  sessionBooting = false;
  chatModePickerOpen = false;
  characterOverviewOpen = false;
  currentCharacterOverview = null;
  setSessionBadge("未启幕");
  if (el("dialogue-transcript")) el("dialogue-transcript").innerHTML = "";
  const memoryRoot = el("dialogue-memory");
  if (memoryRoot) {
    memoryRoot.classList.add("is-collapsed");
  }
  toggle("dialogue-memory", false);
  if (el("dialogue-message")) el("dialogue-message").value = "";
  if (typeof syncSuggestButtonVisibility === "function") syncSuggestButtonVisibility(null);
  if (typeof window.syncDialogueMessageKindVisibility === "function") {
    window.syncDialogueMessageKindVisibility(null);
  }
  if (typeof renderObserveQuickReplies === "function") renderObserveQuickReplies(null);
  resizeComposer();
  setComposerEnabled(false);
  const workflowState = typeof buildWorkflowVisibilityState === "function"
    ? buildWorkflowVisibilityState()
    : (window.__ZAOMENG_WORKFLOW_STATE__ || {});
  window.__ZAOMENG_WORKFLOW_STATE__ = workflowState;
  if (typeof window.__ZAOMENG_UI_BRIDGE_TOOLS__?.syncLegacyUiState === "function") {
    window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("dialogue-reset", {
      currentDialogueSessionId: "",
      currentDialogueSession: null,
      currentCharacterOverview: null,
      workflow: workflowState,
    });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("dialogue-reset");
  }
}

