(() => {
const existingMainModule = window.__ZAOMENG_MAIN_MODULE__;
if (existingMainModule?.initialized) {
  return;
}
let appUpdateStatus = null;
let appUpdatePollTimer = 0;
let exportRunPackagePendingId = "";

const APP_UPDATE_DISMISS_PREFIX = "zaomeng:update-dismissed:";
const UI_BRIDGE_TOOLS = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};

function applyRunViewSafely(run, options = {}) {
  if (typeof window.__ZAOMENG_APPLY_RUN_VIEW__ === "function") {
    window.__ZAOMENG_APPLY_RUN_VIEW__(run, options);
    return true;
  }
  if (typeof window.renderRun === "function") {
    window.renderRun(run, options);
    return true;
  }
  return false;
}

function readNamedActionBridge(name) {
  if (typeof UI_BRIDGE_TOOLS.readLegacyActionBridge === "function") {
    return UI_BRIDGE_TOOLS.readLegacyActionBridge(name);
  }
  return window[String(name || "").trim()] || {};
}

function characterOverviewActions() {
  return readNamedActionBridge("__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__");
}

function openCharacterOverviewViaBridge(characterName = "") {
  const target = String(characterName || "").trim();
  if (!target) {
    return Promise.resolve(null);
  }
  const actions = characterOverviewActions();
  if (typeof actions.openCharacterOverview === "function") {
    return Promise.resolve(actions.openCharacterOverview(target));
  }
  return Promise.reject(new Error("人物档案暂时没有载入。"));
}

function openCharacterOverviewIncrementalDistillViaBridge() {
  const actions = characterOverviewActions();
  if (typeof actions.openCharacterOverviewIncrementalDistill === "function") {
    actions.openCharacterOverviewIncrementalDistill();
    return true;
  }
  return false;
}

function openCharacterOverviewSessionModeViaBridge(mode) {
  const actions = characterOverviewActions();
  if (typeof actions.openCharacterOverviewSessionMode === "function") {
    return Promise.resolve(actions.openCharacterOverviewSessionMode(mode));
  }
  return Promise.reject(new Error("当前角色暂时无法直接入场。"));
}

function openCurrentCharacterProfileFileViaBridge() {
  const actions = characterOverviewActions();
  if (typeof actions.openCurrentCharacterProfileFile === "function") {
    return Boolean(actions.openCurrentCharacterProfileFile());
  }
  return false;
}

function openWorkSummaryExportFallback() {
  const target =
    currentRun?.file_urls?.manifest ||
    currentRun?.file_urls?.graph_relations_file ||
    currentRun?.file_urls?.graph_html ||
    currentRun?.file_urls?.graph_svg ||
    "";
  if (!target) {
    setStatus("bookshelf-status", "当前没有可导出的摘要文件。");
    return false;
  }
  window.open(target, "_blank", "noopener,noreferrer");
  return true;
}

function openWorkTimelineFallback() {
  el("events")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function currentExportRunPackageId() {
  return String(exportRunPackagePendingId || "").trim();
}

function isRunPackageExportPending(runId = "") {
  const pendingId = currentExportRunPackageId();
  const targetId = String(runId || currentRunId || "").trim();
  return Boolean(pendingId) && Boolean(targetId) && pendingId === targetId;
}

function publishRunPackageExportUiState(source = "run-package-export") {
  if (typeof renderBookshelfDetail === "function") {
    renderBookshelfDetail(currentRun);
  }
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState(source, {});
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState(source, {});
  }
}

function setRunPackageExportPending(runId = "", pending = false) {
  const targetId = String(runId || currentRunId || "").trim();
  exportRunPackagePendingId = pending ? targetId : "";
  publishRunPackageExportUiState(pending ? "run-package-export-started" : "run-package-export-finished");
}

function resolveDownloadFilename(response, fallbackName = "zaomeng-run-package.zip") {
  const header = String(response?.headers?.get("content-disposition") || "").trim();
  if (!header) {
    return fallbackName;
  }
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]).trim() || fallbackName;
    } catch (_) {
      return utf8Match[1].trim() || fallbackName;
    }
  }
  const plainMatch = header.match(/filename="?([^";]+)"?/i);
  if (plainMatch?.[1]) {
    return plainMatch[1].trim() || fallbackName;
  }
  return fallbackName;
}

function downloadBlobFile(blob, filename) {
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => {
    window.URL.revokeObjectURL(objectUrl);
  }, 1500);
}

function buildChatSetupState() {
  const mode = valueOf("dialogue-mode", "observe");
  const isActMode = mode === "act";
  const isInsertMode = mode === "insert";
  return {
    mode,
    participants: String(valueOf("dialogue-participants", "")),
    participantList: charactersOf("dialogue-participants"),
    availableCharacters: getRunCharacterNames(currentRun),
    openingPresetId: selectedOpeningPresetId,
    openingPresets: Array.isArray(openingPresets) ? openingPresets.map((item) => ({
      card_id: item.card_id || "",
      preview: item.preview || {},
      fields: item.fields || {},
    })) : [],
    currentOpeningPreset,
    sceneCardId: selectedSceneCardId,
    currentSceneCard,
    sceneCards: Array.isArray(sceneCards) ? sceneCards.map((item) => ({
      card_id: item.card_id || "",
      preview: item.preview || {},
      fields: item.fields || {},
    })) : [],
    sceneCardRecommendation: currentSceneCardRecommendation,
    controlledCharacter: isActMode ? trimmedValue("dialogue-controlled", "") : "",
    canEditCurrentSceneCard: Boolean(currentSceneCard),
    selfCardId: isInsertMode ? selectedSelfCardId : "",
    currentSelfCard: isInsertMode ? currentSelfCard : null,
    selfCards: isInsertMode ? (Array.isArray(selfCards) ? selfCards.map((item) => ({
      card_id: item.card_id || "",
      preview: item.preview || {},
      fields: item.fields || {},
    })) : []) : [],
    selfName: isInsertMode ? trimmedValue("dialogue-self-name", "") : "",
    selfIdentity: isInsertMode ? trimmedValue("dialogue-self-identity", "") : "",
    selfStyle: isInsertMode ? trimmedValue("dialogue-self-style", "") : "",
    status: String(el("dialogue-session-status")?.textContent || "").trim(),
    canEditCurrentCard: isInsertMode && Boolean(currentSelfCard),
    canEditCurrentOpeningPreset: Boolean(currentOpeningPreset),
  };
}

window.__ZAOMENG_BUILD_CHAT_SETUP_STATE__ = buildChatSetupState;

function publishChatSetupState(source = "chat-setup") {
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState(source, { chatSetup: buildChatSetupState() });
  } else if (typeof UI_BRIDGE_TOOLS.publishLegacyStateSlice === "function") {
    UI_BRIDGE_TOOLS.publishLegacyStateSlice(source, "chatSetup", buildChatSetupState());
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState(source, { chatSetup: buildChatSetupState() });
  }
}

function humanizeChatMode(mode) {
  const value = String(mode || "observe").trim() || "observe";
  if (value === "act") return "化身书中人";
  if (value === "insert") return "以自己入场";
  return "旁观此局";
}

function buildCardSnapshot(card, fallbackCardId = "") {
  if (!card) {
    return {
      card_id: String(fallbackCardId || "").trim(),
      fields: {},
      preview: {},
    };
  }
  return {
    card_id: String(card.card_id || fallbackCardId || "").trim(),
    fields: { ...(card.fields || {}) },
    preview: { ...(card.preview || {}) },
  };
}

function collectOpeningPresetPayload(meta = {}) {
  const mode = valueOf("dialogue-mode", "observe");
  const sceneSnapshot = buildCardSnapshot(currentSceneCard, selectedSceneCardId);
  const selfSnapshot = buildCardSnapshot(currentSelfCard, selectedSelfCardId);
  return {
    title: String(meta.title || "").trim(),
    note: String(meta.note || "").trim(),
    mode,
    participants: charactersOf("dialogue-participants"),
    controlled_character: trimmedValue("dialogue-controlled", ""),
    scene_card_id: selectedSceneCardId,
    scene_card: sceneSnapshot,
    self_card_id: mode === "insert" ? selectedSelfCardId : "",
    self_card: mode === "insert" ? selfSnapshot : {},
    self_name: mode === "insert" ? trimmedValue("dialogue-self-name", "") : "",
    self_identity: mode === "insert" ? trimmedValue("dialogue-self-identity", "") : "",
    self_style: mode === "insert" ? trimmedValue("dialogue-self-style", "") : "",
  };
}

function syncModeFields() {
  const mode = valueOf("dialogue-mode", "observe");
  syncChoiceGroup("dialogue-mode-options", "dialogue-mode");
  if (mode !== "insert") {
    clearChatSetupSelfCardSelection();
  }
  if (el("dialogue-controlled")) el("dialogue-controlled").disabled = mode !== "act";
  if (el("dialogue-self-card")) el("dialogue-self-card").disabled = mode !== "insert";
  if (el("dialogue-self-name")) el("dialogue-self-name").disabled = mode !== "insert";
  if (el("dialogue-self-identity")) el("dialogue-self-identity").disabled = mode !== "insert";
  if (el("dialogue-self-style")) el("dialogue-self-style").disabled = mode !== "insert";
  toggle("controlled-field", mode === "act");
  toggle("self-card-field", mode === "insert");
  toggle("insert-self-fields", mode === "insert");
  toggle("self-card-preview-shell", mode === "insert");
  syncCustomSelect("dialogue-scene-card");
  syncCustomSelect("dialogue-self-card");
  renderSelectedSceneCardPreview(false);
  renderSelectedSelfCardPreview(false);
  publishChatSetupState("chat-setup-mode-updated");
}

function clearChatSetupSelfCardSelection() {
  selectedSelfCardId = "";
  currentSelfCard = null;
  const select = el("dialogue-self-card");
  if (select instanceof HTMLSelectElement) {
    select.value = "";
    syncCustomSelect("dialogue-self-card");
  }
  setValue("dialogue-self-name", "");
  setValue("dialogue-self-identity", "");
  setValue("dialogue-self-style", "");
  renderSelectedSelfCardPreview(false);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("self-card-selection-cleared", {
      selectedSelfCardId,
      currentSelfCard,
    });
  }
}

async function handleModelSettingsSubmit(event) {
  event.preventDefault();
  setStatus("model-settings-status", "正在把故事声源接进来...");
  try {
    modelSettings = await apiJson(
      "/api/web/settings/model",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: valueOf("model-provider", ""),
          model: trimmedValue("model-name", ""),
          base_url: trimmedValue("model-base-url", ""),
          api_key: trimmedValue("model-api-key", ""),
          max_tokens: Math.max(0, numberValue("model-max-tokens", 0) || 0),
        }),
      },
      "保存失败。"
    );
    applyModelSettingsView();
    setStatus("model-settings-status", "故事声源已经接通。");
    closeSettingsModal();
    updateWorkflowState();
  } catch (error) {
    setStatus("model-settings-status", error.message || "这次连接没有成功。");
  }
}

async function handleCreateRunSubmit(event) {
  event.preventDefault();
  if (!modelSettings.configured) {
    openSettingsModal();
    setStatus("form-status", "先把故事声源接进来，再开始这一卷。");
    return;
  }
  const file = el("novel-file")?.files?.[0];
  if (!file) {
    setStatus("form-status", "先放入一本书，故事才会往下走。");
    return;
  }
  const characters = charactersOf("characters");
  if (!characters.length) {
    setStatus("form-status", "至少写下一个你想遇见的人。");
    return;
  }
  runCreationPending = true;
  updateWorkflowState();
  setStatus("form-status", "正在翻检正文，替你把人物请出来...");
  try {
    const run = await apiJson(
      "/api/web/runs",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          novel_name: file.name,
          novel_content_base64: await fileToBase64(file),
          characters,
          max_sentences: numberValue("max-sentences", 120),
          max_chars: numberValue("max-chars", 50000),
          auto_run: true,
        }),
      },
      "蒸馏失败。"
    );
    applyRunViewSafely(run);
    await loadRunsOverview();
    setStatus("form-status", "人物整理已经开始，进度会在这里慢慢往前走。");
  } catch (error) {
    runCreationPending = false;
    stopRunPolling();
    updateWorkflowState();
    setStatus("form-status", error.message || "这一轮人物整理没有成功。");
  }
}

async function handleRedistill() {
  if (!currentRunId) {
    setStatus("redistill-status", "先让这一卷成形，再继续补入人物。");
    return;
  }
  const characters = charactersOf("redistill-characters");
  const file = el("redistill-novel-file")?.files?.[0];
  const selectedSegment = !file ? getSelectedRedistillSegment() : null;
  if (!characters.length) {
    setStatus("redistill-status", "写下想继续补入的人物名字。");
    return;
  }
  runCreationPending = true;
  updateWorkflowState();
  setStatus(
    "redistill-status",
    file
      ? "正在换入新的书段，并继续整理人物..."
      : selectedSegment
        ? "正在切到推荐片段，并继续补稳这一位角色..."
        : "正在沿着这卷书继续往下整理..."
  );
  try {
    const run = await apiJson(
      `/api/web/runs/${currentRunId}/redistill`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          characters,
          novel_name: file?.name || (selectedSegment ? `${String(redistillSuggestionState.character || "redistill").trim()}-推荐片段.txt` : ""),
          novel_content_base64: file ? await fileToBase64(file) : selectedSegment ? textToBase64(selectedSegment.full_text || "") : "",
          max_sentences: numberValue("max-sentences", 120),
          max_chars: numberValue("max-chars", 50000),
        }),
      },
      "继续蒸馏失败。"
    );
    applyRunViewSafely(run);
    await loadRunsOverview();
    if (el("redistill-novel-file")) {
      el("redistill-novel-file").value = "";
    }
    resetRedistillRecommendationState();
    updateRedistillFileView();
    setStatus(
      "redistill-status",
      file
        ? "新的书段已经接入，这一轮增量整理开始了。"
        : selectedSegment
          ? "推荐片段已经接入，这一轮增量整理开始了。"
          : "新的整理已经开始，人物会陆续补进来。"
    );
  } catch (error) {
    runCreationPending = false;
    stopRunPolling();
    updateWorkflowState();
    setStatus("redistill-status", error.message || "这次继续整理没有接上。");
  }
}

async function handleRedistillRecommend() {
  const character = getRedistillRecommendationTarget();
  if (!currentRunId || !character) {
    setStatus("redistill-status", "先只选中一位已有角色，再让我替你找更适合的正文片段。");
    return;
  }
  redistillSuggestionState.loading = true;
  redistillSuggestionState.runId = currentRunId;
  redistillSuggestionState.character = character;
  redistillSuggestionState.items = [];
  redistillSuggestionState.selectedSegmentId = "";
  renderRedistillRecommendationState(character);
  setStatus("redistill-status", `正在替「${character}」翻当前书段，挑适合补稳的正文片段...`);
  try {
    const payload = await apiJson(
      `/api/web/runs/${currentRunId}/redistill/recommend`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character, max_segments: 3 }),
      },
      "推荐片段失败。"
    );
    redistillSuggestionState.loading = false;
    redistillSuggestionState.runId = currentRunId;
    redistillSuggestionState.character = character;
    redistillSuggestionState.sourceName = String(payload?.source_name || "").trim();
    redistillSuggestionState.weakFieldLabels = Array.isArray(payload?.weak_field_labels) ? payload.weak_field_labels : [];
    redistillSuggestionState.items = Array.isArray(payload?.segments) ? payload.segments : [];
    redistillSuggestionState.selectedSegmentId = "";
    renderRedistillRecommendationState(character);
    setStatus(
      "redistill-status",
      redistillSuggestionState.items.length
        ? `已经为「${character}」挑出 ${redistillSuggestionState.items.length} 段更适合补料的正文。`
        : `当前书段里暂时没找到更适合「${character}」的推荐窗口。`
    );
  } catch (error) {
    redistillSuggestionState.loading = false;
    redistillSuggestionState.items = [];
    redistillSuggestionState.selectedSegmentId = "";
    renderRedistillRecommendationState(character);
    setStatus("redistill-status", error.message || "这次推荐片段没有接上。");
  }
}

if (typeof UI_BRIDGE_TOOLS.mergeLegacyActionBridge === "function") {
  UI_BRIDGE_TOOLS.mergeLegacyActionBridge("__ZAOMENG_REDISTILL_ACTIONS__", {
    recommend: () => handleRedistillRecommend(),
  });
} else {
  window.__ZAOMENG_REDISTILL_ACTIONS__ = {
    ...(window.__ZAOMENG_REDISTILL_ACTIONS__ || {}),
    recommend: () => handleRedistillRecommend(),
  };
}

async function handleStopRun() {
  if (!currentRunId || !currentRun || currentRun.status !== "running") {
    return;
  }
  if (!window.confirm(`确定先停下《${runNovelTitle(currentRun)}》这一轮蒸馏吗？`)) {
    return;
  }
  const stopButton = el("detail-stop-run-button");
  if (stopButton) {
    stopButton.disabled = true;
  }
  setText("detail-action-note", "正在收束当前步骤，很快就会停下来。", "");
  toggle("detail-action-note", true);
  try {
    const run = await apiJson(
      `/api/web/runs/${currentRunId}/stop`,
      {
        method: "POST",
      },
      "停止蒸馏失败。"
    );
    applyRunViewSafely(run, { preserveDialogue: true });
  } catch (error) {
    if (stopButton) {
      stopButton.disabled = false;
    }
    setText("detail-action-note", error.message || "这次停止没有成功。", "");
    toggle("detail-action-note", true);
  }
}

function handleRedistillAdd() {
  setValue("redistill-characters", "");
  setStatus("redistill-status", "写下新人物后，就可以继续整理。");
  updateRedistillPillState();
}

function handleRedistillRefresh() {
  setValue("redistill-characters", joinCharacters(getRunCharacterNames(currentRun)));
  setStatus("redistill-status", "当前人物已经带回来了，可以直接重新整理。");
  updateRedistillPillState();
}

async function handleDialogueSessionSubmit(event) {
  event.preventDefault();
  if (!currentRunId) {
    setStatus("dialogue-session-status", "先让人物从书页里走出来，再进入这一幕。");
    publishChatSetupState("chat-setup-submit-blocked");
    return;
  }
  try {
    setDialogueMessageKind("dialogue");
    const mode = valueOf("dialogue-mode", "observe");
    const controlledCharacter = trimmedValue("dialogue-controlled", "");
    let participants = charactersOf("dialogue-participants");
    if (mode === "act") {
      if (!controlledCharacter) {
        setStatus("dialogue-session-status", "先写下此刻由你扮演谁。");
        publishChatSetupState("chat-setup-submit-blocked");
        return;
      }
      participants = uniq([controlledCharacter, ...participants]);
      setValue("dialogue-participants", joinCharacters(participants));
      updateCharacterPillState();
    }
    sessionBooting = true;
    setComposerEnabled(false);
    renderSessionBooting(mode, participants);
    updateWorkflowState();
    setStatus("dialogue-session-status", "正在替你铺开这一幕...");
    publishChatSetupState("chat-setup-submitting");
    await renderDialogueSession(
      await apiJson(
        `/api/web/runs/${currentRunId}/dialogue/sessions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode,
            participants,
            controlled_character: controlledCharacter,
            scene_card_id: selectedSceneCardId,
            scene_profile: currentSceneCard?.fields || {},
            self_card_id: mode === "insert" ? selectedSelfCardId : "",
            self_profile:
              mode === "insert"
                ? {
                    ...(currentSelfCard?.fields || {}),
                    display_name: trimmedValue("dialogue-self-name", ""),
                    scene_identity: trimmedValue("dialogue-self-identity", ""),
                    interaction_style: trimmedValue("dialogue-self-style", ""),
                  }
                : {},
          }),
        },
        "进入聊天失败。"
      )
    );
    setStatus("dialogue-session-status", "这一幕已经铺好，你可以继续说下去。");
    publishChatSetupState("chat-setup-submitted");
  } catch (error) {
    sessionBooting = false;
    setComposerEnabled(Boolean(currentDialogueSessionId));
    updateWorkflowState();
    setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。");
    publishChatSetupState("chat-setup-submit-failed");
  }
}

const EDITOR_SCHEMAS = window.__ZAOMENG_EDITOR_SCHEMAS__ || {};
const SCENE_CARD_FIELD_DEFINITIONS = Array.isArray(EDITOR_SCHEMAS.SCENE_CARD_FIELDS) ? EDITOR_SCHEMAS.SCENE_CARD_FIELDS : [];
const SCENE_CARD_FIELD_MAP = EDITOR_SCHEMAS.SCENE_CARD_FIELD_MAP instanceof Map ? EDITOR_SCHEMAS.SCENE_CARD_FIELD_MAP : new Map();
const SCENE_CARD_FIELD_BINDINGS = SCENE_CARD_FIELD_DEFINITIONS.map((item) => [item.field, `scene-card-${item.field.replaceAll("_", "-")}`]);
const SCENE_CARD_REQUIRED_FIELDS = Array.isArray(EDITOR_SCHEMAS.SCENE_CARD_REQUIRED_FIELDS) ? EDITOR_SCHEMAS.SCENE_CARD_REQUIRED_FIELDS : [];
const SELF_CARD_FIELD_DEFINITIONS = Array.isArray(EDITOR_SCHEMAS.SELF_CARD_ALL_FIELDS) ? EDITOR_SCHEMAS.SELF_CARD_ALL_FIELDS : [];
const SELF_CARD_FIELD_MAP = EDITOR_SCHEMAS.SELF_CARD_FIELD_MAP instanceof Map ? EDITOR_SCHEMAS.SELF_CARD_FIELD_MAP : new Map();
const SELF_CARD_FIELD_BINDINGS = SELF_CARD_FIELD_DEFINITIONS.map((item) => [item.field, `self-card-${item.field.replaceAll("_", "-")}`]);
const SELF_CARD_REQUIRED_FIELDS = Array.isArray(EDITOR_SCHEMAS.SELF_CARD_REQUIRED_FIELDS) ? EDITOR_SCHEMAS.SELF_CARD_REQUIRED_FIELDS : [];

function sceneCardFieldId(field) {
  const item = SCENE_CARD_FIELD_BINDINGS.find(([key]) => key === field);
  return item ? item[1] : "";
}

function collectSceneCardPayload() {
  return Object.fromEntries(SCENE_CARD_FIELD_BINDINGS.map(([field, id]) => [field, trimmedValue(id, "")]));
}

function validateSceneCardPayload(fields) {
  const missing = SCENE_CARD_REQUIRED_FIELDS.filter((field) => !String(fields?.[field] || "").trim());
  if (!missing.length) return "";
  const labels = missing.map((field) => SCENE_CARD_FIELD_MAP.get(field)?.label || field);
  return `请先补全这些必填项：${labels.join("、")}`;
}

function fillSceneCardFields(fields = {}) {
  SCENE_CARD_FIELD_BINDINGS.forEach(([field, id]) => {
    setValue(id, fields?.[field] || "");
  });
}

function buildSceneCardEditorState() {
  return {
    cardId: trimmedValue("scene-card-id", ""),
    status: String(el("scene-card-status")?.textContent || "").trim(),
    deleteVisible: !el("delete-scene-card-button")?.classList.contains("hidden"),
    modalOpen: !el("scene-card-modal")?.classList.contains("hidden"),
    fields: collectSceneCardPayload(),
  };
}

window.__ZAOMENG_BUILD_SCENE_CARD_EDITOR_STATE__ = buildSceneCardEditorState;

function publishSceneCardEditorState(source = "scene-card-editor") {
  currentSceneCardEditor = buildSceneCardEditorState();
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState(source, { currentSceneCardEditor });
  } else if (typeof UI_BRIDGE_TOOLS.publishLegacyStateSlice === "function") {
    UI_BRIDGE_TOOLS.publishLegacyStateSlice(source, "currentSceneCardEditor", currentSceneCardEditor);
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState(source, { currentSceneCardEditor });
  }
}

function updateSceneCardDeleteButton(shouldPublish = true) {
  const hasCard = Boolean(trimmedValue("scene-card-id", ""));
  toggle("delete-scene-card-button", hasCard);
  toggle("duplicate-scene-card-button", hasCard);
  if (shouldPublish) {
    publishSceneCardEditorState("scene-card-delete-visibility-updated");
  }
}

function startSceneCardDraft(fields = {}) {
  currentSceneCard = { card_id: "", fields: { ...fields } };
  setValue("scene-card-id", "");
  fillSceneCardFields(fields);
  updateSceneCardDeleteButton();
}

function openNewSceneCard() {
  startSceneCardDraft({
    title: trimmedValue("scene-card-preview-title", "") || "",
  });
  setStatus("scene-card-status", "你可以手写，也可以让 AI 先随机搭一幕。");
  openSceneCardModal();
  publishSceneCardEditorState("scene-card-new-opened");
}

async function openExistingSceneCard(cardId) {
  if (!cardId) {
    openNewSceneCard();
    return;
  }
  setStatus("scene-card-status", "正在载入场景卡...");
  publishSceneCardEditorState("scene-card-loading");
  try {
    const payload = await apiJson(`/api/web/scene-cards/${encodeURIComponent(cardId)}`, {}, "场景卡载入失败。");
    currentSceneCard = payload;
    setValue("scene-card-id", payload.card_id || "");
    fillSceneCardFields(payload.fields || {});
    updateSceneCardDeleteButton();
    setStatus("scene-card-status", "");
    openSceneCardModal();
    publishSceneCardEditorState("scene-card-loaded");
  } catch (error) {
    setStatus("dialogue-session-status", error.message || "场景卡载入失败。");
    publishSceneCardEditorState("scene-card-load-failed");
  }
}

function renderSceneCardOptions(items = sceneCards) {
  const select = el("dialogue-scene-card");
  if (!(select instanceof HTMLSelectElement)) return;
  const trigger = el("dialogue-scene-card-trigger");
  const hint = el("dialogue-scene-card-hint");
  const previous = select.value || selectedSceneCardId || "";
  select.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = items.length ? "先挑一张场景卡" : "还没有场景卡，先新建一张";
  select.appendChild(blank);
  (items || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.card_id || "";
    const title = item?.preview?.title || item?.fields?.title || item.card_id || "未命名场景卡";
    const location = item?.preview?.location || item?.fields?.location || "";
    option.textContent = location ? `${title} · ${location}` : title;
    select.appendChild(option);
  });
  if ((items || []).some((item) => item.card_id === previous)) {
    select.value = previous;
  } else {
    select.value = "";
  }
  if (trigger instanceof HTMLButtonElement) {
    trigger.disabled = items.length === 0;
  }
  if (hint) {
    hint.textContent = items.length
      ? "不选也能直接开聊，但选卡后会把地点、气氛和推进方向一起带进这一幕。"
      : "你还没有场景卡。先新建一张，后面就能直接把整幕氛围接进来。";
  }
  selectedSceneCardId = select.value;
  syncCustomSelect("dialogue-scene-card");
  syncSelectedSceneCardFromSelect();
}

async function loadSceneCards() {
  const payload = await apiJson("/api/web/scene-cards", {}, "场景卡列表载入失败。");
  sceneCards = Array.isArray(payload?.items) ? payload.items : [];
  renderSceneCardOptions(sceneCards);
  renderDialogueSceneSwitcher(currentDialogueSession);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("scene-cards-loaded", { sceneCards });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("scene-cards-loaded");
  }
  return sceneCards;
}

function syncSelectedSceneCardFromSelect() {
  const select = el("dialogue-scene-card");
  const nextId = select?.value || "";
  selectedSceneCardId = nextId;
  currentSceneCard = sceneCards.find((item) => item.card_id === nextId) || null;
  if (currentSceneCardRecommendation && currentSceneCardRecommendation.recommended_card_id === nextId) {
    currentSceneCardRecommendation = {
      ...currentSceneCardRecommendation,
      applied: true,
    };
  }
  renderSelectedSceneCardPreview(false);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("scene-card-selection-changed", {
      selectedSceneCardId,
      currentSceneCard,
      currentSceneCardRecommendation,
    });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("scene-card-selection-changed");
  }
  publishChatSetupState("chat-setup-scene-card-selection-changed");
}

function renderSelectedSceneCardPreview(shouldPublish = true) {
  const card = currentSceneCard;
  const hasCards = sceneCards.length > 0;
  const title = card?.preview?.title || card?.fields?.title || "";
  const copy =
    card?.preview?.opening_situation || card?.fields?.opening_situation || card?.preview?.scene_drive || "";
  setText("scene-card-preview-title", title || (hasCards ? "还没有选中场景卡" : "你还没有场景卡"), "");
  setText(
    "scene-card-preview-copy",
    card
      ? copy || "这张卡已经接上，会把这一幕的起势和推进方向一起带进聊天。"
      : hasCards
        ? "选一张卡后，这一幕的地点、气氛和推进方向都会先定下来。"
        : "先新建一张场景卡，后面就可以直接把整幕氛围带进场景。",
    ""
  );
  const root = el("scene-card-preview-pills");
  if (!root) return;
  root.innerHTML = "";
  const preview = card?.preview || {};
  [preview.time_hint, preview.location, preview.atmosphere, preview.scene_drive, preview.expected_rhythm]
    .filter(Boolean)
    .slice(0, 5)
    .forEach((value) => {
      const chip = document.createElement("span");
      chip.textContent = value;
      root.appendChild(chip);
    });
  const recommendationNote = el("scene-card-preview-recommendation");
  if (recommendationNote) {
    const top = Array.isArray(currentSceneCardRecommendation?.items) ? currentSceneCardRecommendation.items[0] : null;
    const topId = String(currentSceneCardRecommendation?.recommended_card_id || "").trim();
    const reasons = Array.isArray(top?.recommendation?.reasons) ? top.recommendation.reasons.filter(Boolean).slice(0, 3) : [];
    if (card && topId && card.card_id === topId && reasons.length) {
      recommendationNote.textContent = `推荐理由：${reasons.join("，")}。`;
      recommendationNote.classList.remove("hidden");
    } else {
      recommendationNote.textContent = "";
      recommendationNote.classList.add("hidden");
    }
  }
  const editButton = el("edit-scene-card-button");
  if (editButton) {
    editButton.disabled = !card;
    editButton.classList.toggle("hidden", !card);
  }
  if (shouldPublish) {
    publishChatSetupState("chat-setup-scene-card-preview-rendered");
  }
}

async function handleSceneCardSelectionChange() {
  syncSelectedSceneCardFromSelect();
}

async function handleOpenNewSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  openNewSceneCard();
}

async function handleEditCurrentSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!selectedSceneCardId) {
    openNewSceneCard();
    return;
  }
  await openExistingSceneCard(selectedSceneCardId);
}

async function handleGenerateSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const button = el("generate-scene-card-button");
  if (button) button.disabled = true;
  setStatus("scene-card-status", "正在随机生成一张场景卡...");
  publishSceneCardEditorState("scene-card-generating");
  try {
    const payload = await apiJson(
      "/api/web/scene-cards/generate",
      { method: "POST" },
      "场景卡生成失败。"
    );
    fillSceneCardFields(payload.fields || {});
    setStatus("scene-card-status", "AI 已经把这一幕先搭好了，你可以直接保存，也可以再手修。");
    publishSceneCardEditorState("scene-card-generated");
  } catch (error) {
    setStatus("scene-card-status", error.message || "场景卡生成失败。");
    publishSceneCardEditorState("scene-card-generate-failed");
  } finally {
    if (button) button.disabled = false;
  }
}

async function handleSceneCardSubmit(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const fields = collectSceneCardPayload();
  const validationMessage = validateSceneCardPayload(fields);
  if (validationMessage) {
    setStatus("scene-card-status", validationMessage);
    publishSceneCardEditorState("scene-card-validation-failed");
    return;
  }
  setStatus("scene-card-status", "正在保存场景卡...");
  publishSceneCardEditorState("scene-card-saving");
  try {
    const cardId = trimmedValue("scene-card-id", "");
    const payload = await apiJson(
      cardId ? `/api/web/scene-cards/${encodeURIComponent(cardId)}` : "/api/web/scene-cards",
      {
        method: cardId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      },
      "场景卡保存失败。"
    );
    setValue("scene-card-id", payload.card_id || "");
    await loadSceneCards();
    const select = el("dialogue-scene-card");
    if (select) {
      select.value = payload.card_id || "";
      syncCustomSelect("dialogue-scene-card");
    }
    syncSelectedSceneCardFromSelect();
    setStatus("scene-card-status", "场景卡已保存。");
    publishSceneCardEditorState("scene-card-saved");
    closeSceneCardModal();
  } catch (error) {
    setStatus("scene-card-status", error.message || "场景卡保存失败。");
    publishSceneCardEditorState("scene-card-save-failed");
  }
}

async function handleDeleteSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const cardId = trimmedValue("scene-card-id", "");
  if (!cardId) return;
  if (!window.confirm("确定删除这张场景卡吗？")) return;
  setStatus("scene-card-status", "正在删除场景卡...");
  publishSceneCardEditorState("scene-card-deleting");
  try {
    await apiJson(
      `/api/web/scene-cards/${encodeURIComponent(cardId)}`,
      { method: "DELETE" },
      "场景卡删除失败。"
    );
    if (selectedSceneCardId === cardId) {
      selectedSceneCardId = "";
    }
    await loadSceneCards();
    currentSceneCard = null;
    renderSelectedSceneCardPreview();
    publishSceneCardEditorState("scene-card-deleted");
    closeSceneCardModal();
  } catch (error) {
    setStatus("scene-card-status", error.message || "场景卡删除失败。");
    publishSceneCardEditorState("scene-card-delete-failed");
  }
}

function renderDialogueSceneSwitcher(session = currentDialogueSession) {
  const shell = el("dialogue-scene-switcher");
  const select = el("dialogue-live-scene-card");
  const status = el("dialogue-live-scene-status");
  const context = el("dialogue-live-scene-context");
  const recommendButton = el("dialogue-live-scene-recommend");
  const shiftHint = el("dialogue-live-scene-shift-hint");
  const shiftCopy = el("dialogue-live-scene-shift-copy");
  const shiftRecommendButton = el("dialogue-live-scene-shift-recommend");
  if (!shell || !select) return;
  const hasSession = Boolean(session?.session_id) && Boolean(currentRunId);
  shell.classList.toggle("hidden", !hasSession);
  if (!hasSession) {
    select.innerHTML = "";
    if (status) status.textContent = "";
    if (context) {
      context.textContent = "";
      context.classList.add("hidden");
    }
    if (recommendButton) recommendButton.disabled = true;
    if (shiftHint) shiftHint.classList.add("hidden");
    if (shiftCopy) shiftCopy.textContent = "";
    if (shiftRecommendButton) shiftRecommendButton.disabled = true;
    renderDialogueSceneChainSuggestions([], "");
    return;
  }
  if (recommendButton) recommendButton.disabled = sceneCards.length < 2;
  if (shiftRecommendButton) shiftRecommendButton.disabled = sceneCards.length < 2;
  const currentSceneId = String(session?.session_card?.scene_card_id || "").trim();
  const overview = session?.runtime_state_overview || {};
  const shouldShift = Boolean(overview?.should_offer_scene_shift);
  const shiftReason = String(overview?.scene_shift_reason || "").trim();
  const nextHint = String(overview?.next_hint || "").trim();
  const timeHint = String(overview?.time_hint || "").trim();
  const location = String(overview?.location || "").trim();
  const present = Array.isArray(overview?.present) ? overview.present.filter(Boolean).slice(0, 3) : [];
  const offstage = Array.isArray(overview?.offstage) ? overview.offstage.filter(Boolean).slice(0, 2) : [];
  const previous = select.value || currentSceneId;
  select.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = sceneCards.length ? "先挑一张场景卡" : "还没有可用场景卡";
  select.appendChild(blank);
  (sceneCards || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.card_id || "";
    const title = item?.preview?.title || item?.fields?.title || item.card_id || "未命名场景卡";
    const location = item?.preview?.location || item?.fields?.location || "";
    option.textContent = location ? `${title} · ${location}` : title;
    select.appendChild(option);
  });
  if ((sceneCards || []).some((item) => item.card_id === previous)) {
    select.value = previous;
  } else {
    select.value = currentSceneId;
  }
  if (shiftHint) {
    shiftHint.classList.toggle("hidden", !shouldShift);
  }
  if (shiftCopy) {
    shiftCopy.textContent = shouldShift
      ? (shiftReason || nextHint || "这一拍差不多收住了，可以顺势切到下一幕。")
      : "";
  }
  if (context) {
    const parts = [];
    if (location) parts.push(`地点：${location}`);
    if (timeHint) parts.push(`时间：${timeHint}`);
    if (present.length) parts.push(`在场：${present.join("、")}`);
    if (offstage.length) parts.push(`离场：${offstage.join("、")}`);
    context.textContent = parts.join(" · ");
    context.classList.toggle("hidden", parts.length === 0);
  }
  if (status && !String(status.textContent || "").trim()) {
    if (shouldShift) {
      status.textContent = "这一拍已经接近收束，可以顺势切一张场景卡。";
    } else {
      status.textContent = currentSceneId ? "当前会话已经挂载场景卡，你可以随时切到另一幕。" : "当前会话还没挂场景卡，也可以直接在这里接入一张。";
    }
  }
  renderDialogueSceneChainSuggestions(currentDialogueSceneChainSuggestions, session?.session_id || "");
}

async function handleApplyDialogueSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!currentRunId || !currentDialogueSessionId) return;
  const select = el("dialogue-live-scene-card");
  const transition = trimmedValue("dialogue-live-scene-transition", "");
  const status = el("dialogue-live-scene-status");
  const button = el("dialogue-live-scene-apply");
  const sceneCardId = String(select?.value || "").trim();
  if (!sceneCardId) {
    if (status) status.textContent = "先挑一张要切进去的场景卡。";
    return;
  }
  if (button) button.disabled = true;
  if (status) status.textContent = "正在把这一幕转过去...";
  try {
    const payload = await window.__ZAOMENG_WEBUI_API__.switchDialogueSceneCard(currentRunId, currentDialogueSessionId, {
      scene_card_id: sceneCardId,
      scene_profile: currentSceneCard?.card_id === sceneCardId ? (currentSceneCard?.fields || {}) : {},
      transition_message: transition,
    });
    if (el("dialogue-live-scene-transition")) {
      setValue("dialogue-live-scene-transition", "");
    }
    if (status) status.textContent = "新的场景已经接上了。";
    await renderDialogueSession(payload);
  } catch (error) {
    if (status) status.textContent = error.message || "切换场景失败。";
  } finally {
    if (button) button.disabled = false;
  }
}

async function handleRecommendDialogueSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!currentRunId || !currentDialogueSessionId) return;
  const select = el("dialogue-live-scene-card");
  const status = el("dialogue-live-scene-status");
  const button = el("dialogue-live-scene-recommend");
  if (!sceneCards.length) {
    if (status) status.textContent = "你还没有场景卡，先新建一张再来转场。";
    return;
  }
  if (button) button.disabled = true;
  if (status) status.textContent = "正在按当前局势替你挑下一幕...";
  try {
    const payload = await window.__ZAOMENG_WEBUI_API__.recommendDialogueSceneCard(currentRunId, currentDialogueSessionId);
    const recommendedCardId = String(payload?.recommended_card_id || "").trim();
    const recommendedTransition = String(payload?.recommended_transition_message || "").trim();
    currentDialogueSceneChainSuggestions = Array.isArray(payload?.chain_suggestions) ? payload.chain_suggestions : [];
    currentDialogueSceneChainSessionId = currentDialogueSessionId;
    const topItem = Array.isArray(payload?.items) ? payload.items[0] : null;
    const reasons = Array.isArray(topItem?.recommendation?.reasons) ? topItem.recommendation.reasons.filter(Boolean).slice(0, 3) : [];
    if (!recommendedCardId) {
      if (status) status.textContent = "这一拍暂时没挑出更合适的下一幕。";
      return;
    }
    if (select) {
      select.value = recommendedCardId;
    }
    if (recommendedTransition && el("dialogue-live-scene-transition")) {
      setValue("dialogue-live-scene-transition", recommendedTransition);
    }
    if (status) {
      status.textContent = reasons.length ? `已替你挑好下一幕：${reasons.join("，")}。` : "已替你挑好一张更接戏的场景卡。";
    }
    renderDialogueSceneChainSuggestions(currentDialogueSceneChainSuggestions, currentDialogueSessionId);
  } catch (error) {
    if (status) status.textContent = error.message || "下一幕推荐失败。";
  } finally {
    if (button) button.disabled = sceneCards.length < 2;
  }
}

function renderDialogueSceneChainSuggestions(chains = [], sessionId = "") {
  const root = el("dialogue-scene-chain-suggestions");
  if (!root) return;
  const activeSessionId = String(sessionId || currentDialogueSessionId || "").trim();
  if (!activeSessionId || activeSessionId !== String(currentDialogueSceneChainSessionId || "").trim() || !Array.isArray(chains) || !chains.length) {
    root.innerHTML = "";
    root.classList.add("hidden");
    return;
  }
  root.classList.remove("hidden");
  root.innerHTML = "";
  chains.slice(0, 3).forEach((chain) => {
    const card = document.createElement("article");
    card.className = "dialogue-scene-chain-card";
    const title = document.createElement("strong");
    const firstScene = Array.isArray(chain?.scenes) ? chain.scenes[0] : null;
    const firstTitle = String(firstScene?.title || "").trim() || "下一幕";
    title.textContent = `后续戏路：先接「${firstTitle}」`;
    card.appendChild(title);
    const copy = document.createElement("p");
    copy.textContent = String(chain?.reason || "").trim() || "这条线可以顺着往下接。";
    card.appendChild(copy);
    const tags = document.createElement("div");
    tags.className = "dialogue-scene-chain-tags";
    (Array.isArray(chain?.scenes) ? chain.scenes : []).slice(0, 3).forEach((scene, index) => {
      const chip = document.createElement("span");
      const label = String(scene?.title || "").trim() || `第 ${index + 1} 幕`;
      const location = String(scene?.location || "").trim();
      chip.textContent = location ? `${label} · ${location}` : label;
      tags.appendChild(chip);
    });
    card.appendChild(tags);
    const actions = document.createElement("div");
    actions.className = "dialogue-scene-chain-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "soft-button";
    button.textContent = "接这条线";
    button.addEventListener("click", () => {
      applyDialogueSceneChain(chain);
    });
    actions.appendChild(button);
    card.appendChild(actions);
    root.appendChild(card);
  });
}

function applyDialogueSceneChain(chain = {}) {
  const scenes = Array.isArray(chain?.scenes) ? chain.scenes : [];
  const first = scenes[0] || {};
  const sceneCardId = String(first?.card_id || "").trim();
  const transition = String(first?.transition_message || "").trim();
  const select = el("dialogue-live-scene-card");
  const status = el("dialogue-live-scene-status");
  if (!sceneCardId || !select) return false;
  select.value = sceneCardId;
  if (el("dialogue-live-scene-transition")) {
    setValue("dialogue-live-scene-transition", transition);
  }
  if (status) {
    const tailTitles = scenes.slice(1).map((item) => String(item?.title || "").trim()).filter(Boolean);
    status.textContent = tailTitles.length
      ? `已替你接上这条线，后面还可以顺势转到：${tailTitles.join("、")}。`
      : "已替你接上这条线。";
  }
  return true;
}

function applyDialogueSceneTimelineEntry(entry = {}) {
  const sceneCardId = String(entry?.scene_card_id || "").trim();
  const transitionMessage = String(entry?.transition_message || "").trim();
  const status = el("dialogue-live-scene-status");
  const select = el("dialogue-live-scene-card");
  if (!sceneCardId || !select) return false;
  const matched = sceneCards.find((item) => String(item?.card_id || "").trim() === sceneCardId);
  if (!matched) {
    if (status) status.textContent = "这幕对应的场景卡已经不在卡册里了。";
    return false;
  }
  select.value = sceneCardId;
  if (el("dialogue-live-scene-transition")) {
    setValue("dialogue-live-scene-transition", transitionMessage);
  }
  if (status) {
    const title = matched?.preview?.title || matched?.fields?.title || "这幕";
    status.textContent = transitionMessage ? `已回填「${title}」和当时那句转场提示。` : `已回填「${title}」，你可以再补一句转场提示。`;
  }
  return true;
}

async function branchDialogueSessionFromScene(sceneIndex) {
  const index = Number(sceneIndex);
  if (!currentRunId || !currentDialogueSessionId || !Number.isInteger(index) || index < 0) {
    return;
  }
  setStatus("dialogue-live-scene-status", "正在从这一幕重新岔开一条新会话...");
  try {
    const payload = await window.__ZAOMENG_WEBUI_API__.branchDialogueSession(currentRunId, currentDialogueSessionId, index);
    await renderDialogueSession(payload);
    setStatus("dialogue-session-status", "已经从这幕重新开出一条新分支。");
    setStatus("dialogue-live-scene-status", "新的分支会话已经接上。");
  } catch (error) {
    setStatus("dialogue-live-scene-status", error.message || "分支会话创建失败。");
  }
}

async function handleRecommendSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!sceneCards.length) {
    setStatus("dialogue-session-status", "你还没有场景卡，先新建一张再让我替你挑。");
    return;
  }
  setStatus("dialogue-session-status", "正在按这场的角色和入场方式替你挑更合适的场景卡...");
  try {
    const payload = await window.__ZAOMENG_WEBUI_API__.recommendSceneCards({
      mode: valueOf("dialogue-mode", "observe"),
      participants: charactersOf("dialogue-participants"),
    });
    currentSceneCardRecommendation = payload;
    const recommendedId = String(payload?.recommended_card_id || "").trim();
    if (recommendedId) {
      const select = el("dialogue-scene-card");
      if (select) {
        select.value = recommendedId;
        syncCustomSelect("dialogue-scene-card");
      }
      syncSelectedSceneCardFromSelect();
      const top = Array.isArray(payload?.items) ? payload.items[0] : null;
      const reasons = Array.isArray(top?.recommendation?.reasons) ? top.recommendation.reasons.filter(Boolean).slice(0, 3) : [];
      setStatus("dialogue-session-status", reasons.length ? `已替你挑好场景卡：${reasons.join("，")}。` : "已替你挑好一张更合适的场景卡。");
    } else {
      setStatus("dialogue-session-status", "这一轮没挑出更明确的推荐，你也可以手动选。");
    }
    if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
      UI_BRIDGE_TOOLS.syncLegacyUiState("scene-card-recommended", { currentSceneCardRecommendation });
    }
    publishChatSetupState("chat-setup-scene-card-recommended");
  } catch (error) {
    setStatus("dialogue-session-status", error.message || "场景卡推荐失败。");
  }
}

async function handleDuplicateSceneCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const fields = collectSceneCardPayload();
  startSceneCardDraft(fields);
  setStatus("scene-card-status", "已经按当前内容另起一张新卡。保存后会成为独立场景卡。");
  publishSceneCardEditorState("scene-card-duplicated");
}

function selfCardFieldId(field) {
  const item = SELF_CARD_FIELD_BINDINGS.find(([key]) => key === field);
  return item ? item[1] : "";
}

function collectSelfCardPayload() {
  return Object.fromEntries(SELF_CARD_FIELD_BINDINGS.map(([field, id]) => [field, trimmedValue(id, "")]));
}

function validateSelfCardPayload(fields) {
  const missing = SELF_CARD_REQUIRED_FIELDS.filter((field) => !String(fields?.[field] || "").trim());
  if (!missing.length) return "";
  const labels = missing.map((field) => SELF_CARD_FIELD_MAP.get(field)?.label || field);
  return `请先补全这些必填项：${labels.join("、")}`;
}

function fillSelfCardFields(fields = {}) {
  SELF_CARD_FIELD_BINDINGS.forEach(([field, id]) => {
    setValue(id, fields?.[field] || "");
  });
}

function buildSelfCardEditorState() {
  return {
    cardId: trimmedValue("self-card-id", ""),
    status: String(el("self-card-status")?.textContent || "").trim(),
    deleteVisible: !el("delete-self-card-button")?.classList.contains("hidden"),
    modalOpen: !el("self-card-modal")?.classList.contains("hidden"),
    fields: collectSelfCardPayload(),
  };
}

window.__ZAOMENG_BUILD_SELF_CARD_EDITOR_STATE__ = buildSelfCardEditorState;

function publishSelfCardEditorState(source = "self-card-editor") {
  currentSelfCardEditor = buildSelfCardEditorState();
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState(source, { currentSelfCardEditor });
  } else if (typeof UI_BRIDGE_TOOLS.publishLegacyStateSlice === "function") {
    UI_BRIDGE_TOOLS.publishLegacyStateSlice(source, "currentSelfCardEditor", currentSelfCardEditor);
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState(source, { currentSelfCardEditor });
  }
}

function updateSelfCardDeleteButton(shouldPublish = true) {
  const hasCard = Boolean(trimmedValue("self-card-id", ""));
  toggle("delete-self-card-button", hasCard);
  if (shouldPublish) {
    publishSelfCardEditorState("self-card-delete-visibility-updated");
  }
}

function startSelfCardDraft(fields = {}) {
  currentSelfCard = { card_id: "", fields: { ...fields } };
  setValue("self-card-id", "");
  fillSelfCardFields(fields);
  updateSelfCardDeleteButton();
}

function openNewSelfCard() {
  startSelfCardDraft({
    display_name: trimmedValue("dialogue-self-name", "") || "你",
    scene_identity: trimmedValue("dialogue-self-identity", ""),
    interaction_style: trimmedValue("dialogue-self-style", ""),
  });
  setStatus("self-card-status", "你可以手写，也可以让 AI 先随机捏一张。");
  openSelfCardModal();
  publishSelfCardEditorState("self-card-new-opened");
}

async function openExistingSelfCard(cardId) {
  if (!cardId) {
    openNewSelfCard();
    return;
  }
  setStatus("self-card-status", "正在载入角色卡...");
  publishSelfCardEditorState("self-card-loading");
  try {
    const payload = await apiJson(`/api/web/self-cards/${encodeURIComponent(cardId)}`, {}, "角色卡载入失败。");
    currentSelfCard = payload;
    setValue("self-card-id", payload.card_id || "");
    fillSelfCardFields(payload.fields || {});
    updateSelfCardDeleteButton();
    setStatus("self-card-status", "");
    openSelfCardModal();
    publishSelfCardEditorState("self-card-loaded");
  } catch (error) {
    setStatus("dialogue-session-status", error.message || "角色卡载入失败。");
    publishSelfCardEditorState("self-card-load-failed");
  }
}

function renderSelfCardOptions(items = selfCards) {
  const select = el("dialogue-self-card");
  if (!(select instanceof HTMLSelectElement)) return;
  const trigger = el("dialogue-self-card-trigger");
  const hint = el("dialogue-self-card-hint");
  const previous = select.value || selectedSelfCardId || "";
  select.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = items.length ? "先挑一张角色卡" : "还没有角色卡，先新建一张";
  select.appendChild(blank);
  (items || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.card_id || "";
    const displayName = item?.preview?.display_name || item?.fields?.display_name || item.card_id || "未命名角色卡";
    const sceneIdentity = item?.preview?.scene_identity || item?.fields?.scene_identity || "";
    option.textContent = sceneIdentity ? `${displayName} · ${sceneIdentity}` : displayName;
    select.appendChild(option);
  });
  if ((items || []).some((item) => item.card_id === previous)) {
    select.value = previous;
  } else {
    select.value = "";
  }
  if (trigger instanceof HTMLButtonElement) {
    trigger.disabled = items.length === 0;
  }
  if (hint) {
    hint.textContent = items.length
      ? "不选也能手动写，但选卡后会把完整人设一起带进场景。"
      : "你还没有角色卡。先新建一张，后面就能直接选卡入场。";
  }
  selectedSelfCardId = select.value;
  syncCustomSelect("dialogue-self-card");
  syncSelectedSelfCardFromSelect();
}

async function loadSelfCards() {
  const payload = await apiJson("/api/web/self-cards", {}, "角色卡列表载入失败。");
  selfCards = Array.isArray(payload?.items) ? payload.items : [];
  renderSelfCardOptions(selfCards);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("self-cards-loaded", { selfCards });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("self-cards-loaded");
  }
  return selfCards;
}

function syncSelectedSelfCardFromSelect() {
  const select = el("dialogue-self-card");
  const nextId = select?.value || "";
  selectedSelfCardId = nextId;
  currentSelfCard = selfCards.find((item) => item.card_id === nextId) || null;
  if (currentSelfCard?.fields) {
    if (el("dialogue-self-name")) setValue("dialogue-self-name", currentSelfCard.fields.display_name || "");
    if (el("dialogue-self-identity")) {
      setValue("dialogue-self-identity", currentSelfCard.fields.scene_identity || currentSelfCard.fields.core_identity || "");
    }
    if (el("dialogue-self-style")) setValue("dialogue-self-style", currentSelfCard.fields.interaction_style || "");
  }
  renderSelectedSelfCardPreview(false);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("self-card-selection-changed", {
      selectedSelfCardId,
      currentSelfCard,
    });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("self-card-selection-changed");
  }
  publishChatSetupState("chat-setup-self-card-selection-changed");
}

function renderSelectedSelfCardPreview(shouldPublish = true) {
  const card = currentSelfCard;
  const hasCards = selfCards.length > 0;
  const title = card?.preview?.display_name || card?.fields?.display_name || "";
  const copy =
    card?.preview?.scene_identity || card?.fields?.scene_identity || card?.fields?.core_identity || "";
  setText("self-card-preview-title", title || (hasCards ? "还没有选中角色卡" : "你还没有角色卡"), "");
  setText(
    "self-card-preview-copy",
    card
      ? copy || "这张卡已经接上，会把完整人设带进这场聊天。"
      : hasCards
        ? "选一张卡后，你的身份、气质和说话方式都会一起带进这场聊天。"
        : "先新建一张角色卡，后面就可以直接把完整人设带进场景。",
    ""
  );
  const root = el("self-card-preview-pills");
  if (!root) return;
  root.innerHTML = "";
  const preview = card?.preview || {};
  [preview.core_identity, preview.story_role, preview.temperament_type, preview.speech_style, preview.soul_goal]
    .filter(Boolean)
    .slice(0, 5)
    .forEach((value) => {
      const chip = document.createElement("span");
      chip.textContent = value;
      root.appendChild(chip);
    });
  const editButton = el("edit-self-card-button");
  if (editButton) {
    editButton.disabled = !card;
    editButton.classList.toggle("hidden", !card);
  }
  if (shouldPublish) {
    publishChatSetupState("chat-setup-self-card-preview-rendered");
  }
}

async function handleSelfCardSelectionChange() {
  syncSelectedSelfCardFromSelect();
}

async function handleOpenNewSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  openNewSelfCard();
}

async function handleEditCurrentSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!selectedSelfCardId) {
    openNewSelfCard();
    return;
  }
  await openExistingSelfCard(selectedSelfCardId);
}

async function handleGenerateSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const button = el("generate-self-card-button");
  if (button) button.disabled = true;
  setStatus("self-card-status", "正在随机生成一张角色卡...");
  publishSelfCardEditorState("self-card-generating");
  try {
    const payload = await apiJson(
      "/api/web/self-cards/generate",
      { method: "POST" },
      "角色卡生成失败。"
    );
    fillSelfCardFields(payload.fields || {});
    setStatus("self-card-status", "AI 已经把整张卡先填好了，你可以直接保存，也可以再手修。");
    publishSelfCardEditorState("self-card-generated");
  } catch (error) {
    setStatus("self-card-status", error.message || "角色卡生成失败。");
    publishSelfCardEditorState("self-card-generate-failed");
  } finally {
    if (button) button.disabled = false;
  }
}

async function handleSelfCardSubmit(event) {
  event.preventDefault();
  const cardId = trimmedValue("self-card-id", "");
  const fields = collectSelfCardPayload();
  const validationMessage = validateSelfCardPayload(fields);
  if (validationMessage) {
    setStatus("self-card-status", validationMessage);
    publishSelfCardEditorState("self-card-validation-failed");
    return;
  }
  setStatus("self-card-status", "正在保存角色卡...");
  publishSelfCardEditorState("self-card-saving");
  try {
    const payload = await apiJson(
      cardId ? `/api/web/self-cards/${encodeURIComponent(cardId)}` : "/api/web/self-cards",
      {
        method: cardId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      },
      "角色卡保存失败。"
    );
    await loadSelfCards();
    selectedSelfCardId = payload.card_id || "";
    const select = el("dialogue-self-card");
    if (select) {
      select.value = selectedSelfCardId;
      syncCustomSelect("dialogue-self-card");
    }
    syncSelectedSelfCardFromSelect();
    setStatus("dialogue-session-status", "角色卡已经接好，现在可以直接带它入场。");
    setStatus("self-card-status", "角色卡已保存。");
    publishSelfCardEditorState("self-card-saved");
    closeSelfCardModal();
  } catch (error) {
    setStatus("self-card-status", error.message || "角色卡保存失败。");
    publishSelfCardEditorState("self-card-save-failed");
  }
}

async function handleDeleteSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const cardId = trimmedValue("self-card-id", "");
  if (!cardId) return;
  if (!window.confirm("确定删除这张角色卡吗？")) {
    return;
  }
  setStatus("self-card-status", "正在删除角色卡...");
  publishSelfCardEditorState("self-card-deleting");
  try {
    await apiJson(
      `/api/web/self-cards/${encodeURIComponent(cardId)}`,
      { method: "DELETE" },
      "角色卡删除失败。"
    );
    if (selectedSelfCardId === cardId) {
      selectedSelfCardId = "";
    }
    await loadSelfCards();
    currentSelfCard = null;
    renderSelectedSelfCardPreview();
    setStatus("dialogue-session-status", "角色卡已经删掉了。");
    publishSelfCardEditorState("self-card-deleted");
    closeSelfCardModal();
  } catch (error) {
    setStatus("self-card-status", error.message || "角色卡删除失败。");
    publishSelfCardEditorState("self-card-delete-failed");
  }
}

function fillOpeningPresetMetaForm(preset = null) {
  const cardId = preset?.card_id || "";
  setValue("opening-preset-id", cardId);
  setValue("opening-preset-title", preset?.preview?.title || preset?.fields?.title || "");
  setValue("opening-preset-note", preset?.preview?.note || preset?.fields?.note || "");
  const deleteButton = el("delete-opening-preset-button");
  if (deleteButton) {
    deleteButton.disabled = !cardId;
    deleteButton.classList.toggle("hidden", !cardId);
  }
}

function renderOpeningPresetOptions(items = openingPresets) {
  const select = el("dialogue-opening-preset");
  if (!(select instanceof HTMLSelectElement)) return;
  const previous = select.value || selectedOpeningPresetId || "";
  select.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = items.length ? "先挑一套开局模板" : "还没有开局模板，先存一套";
  select.appendChild(blank);
  (items || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.card_id || "";
    const preview = item.preview || {};
    const title = preview.title || item.fields?.title || item.card_id || "未命名模板";
    const modeLabel = humanizeChatMode(preview.mode || item.fields?.mode || "observe");
    option.textContent = `${title} · ${modeLabel}`;
    select.appendChild(option);
  });
  select.value = (items || []).some((item) => item.card_id === previous) ? previous : "";
  selectedOpeningPresetId = select.value;
  currentOpeningPreset = (items || []).find((item) => item.card_id === selectedOpeningPresetId) || null;
  renderOpeningPresetPreview(false);
}

function renderOpeningPresetPreview(shouldPublish = true) {
  const preset = currentOpeningPreset;
  const hasPresets = openingPresets.length > 0;
  const preview = preset?.preview || {};
  setText("opening-preset-preview-title", preview.title || preset?.fields?.title || (hasPresets ? "还没有选中开局模板" : "你还没有开局模板"), "");
  const summaryBits = [
    humanizeChatMode(preview.mode || preset?.fields?.mode || "observe"),
    Array.isArray(preview.participants) && preview.participants.length ? `同席：${preview.participants.join("、")}` : "",
    preview.scene_title ? `场景：${preview.scene_title}` : "",
    preview.self_name ? `入场：${preview.self_name}` : "",
  ].filter(Boolean);
  setText(
    "opening-preset-preview-copy",
    preset
      ? (preview.note || preset?.fields?.note || summaryBits.join(" · ") || "这套模板已经把入场方式、人物和场景打包好了。")
      : (hasPresets ? "选中一套模板后，就能把整套开局方式一键套进来。" : "先把你喜欢的角色卡、场景卡和入场方式搭好，再存成模板。"),
    ""
  );
  const root = el("opening-preset-preview-pills");
  if (root) {
    root.innerHTML = "";
    summaryBits.slice(0, 4).forEach((value) => {
      const chip = document.createElement("span");
      chip.textContent = value;
      root.appendChild(chip);
    });
  }
  const editButton = el("edit-opening-preset-button");
  const applyButton = el("apply-opening-preset-button");
  const startButton = el("start-opening-preset-button");
  if (editButton) {
    editButton.disabled = !preset;
    editButton.classList.toggle("hidden", !preset);
  }
  if (applyButton) {
    applyButton.disabled = !preset;
    applyButton.classList.toggle("hidden", !preset);
  }
  if (startButton) {
    startButton.disabled = !preset;
    startButton.classList.toggle("hidden", !preset);
  }
  if (shouldPublish) {
    publishChatSetupState("chat-setup-opening-preset-preview-rendered");
  }
}

function syncSelectedOpeningPresetFromSelect() {
  const select = el("dialogue-opening-preset");
  selectedOpeningPresetId = select?.value || "";
  currentOpeningPreset = openingPresets.find((item) => item.card_id === selectedOpeningPresetId) || null;
  renderOpeningPresetPreview(false);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("opening-preset-selection-changed", {
      openingPresets,
      selectedOpeningPresetId,
      currentOpeningPreset,
    });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("opening-preset-selection-changed");
  }
  publishChatSetupState("chat-setup-opening-preset-selection-changed");
}

async function loadOpeningPresets() {
  const payload = await window.__ZAOMENG_WEBUI_API__.listOpeningPresets();
  openingPresets = Array.isArray(payload?.items) ? payload.items : [];
  renderOpeningPresetOptions(openingPresets);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("opening-presets-loaded", { openingPresets, currentOpeningPreset, selectedOpeningPresetId });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("opening-presets-loaded");
  }
  return openingPresets;
}

function applyPresetSceneCard(presetFields = {}) {
  const sceneId = String(presetFields.scene_card_id || "").trim();
  const sceneSnapshot = buildCardSnapshot(presetFields.scene_card || {}, sceneId);
  const matched = sceneId ? sceneCards.find((item) => item.card_id === sceneId) || null : null;
  const select = el("dialogue-scene-card");
  if (matched) {
    selectedSceneCardId = matched.card_id || "";
    currentSceneCard = matched;
    if (select) select.value = selectedSceneCardId;
    syncCustomSelect("dialogue-scene-card");
    syncSelectedSceneCardFromSelect();
    return;
  }
  selectedSceneCardId = "";
  currentSceneCard = sceneSnapshot.fields && Object.keys(sceneSnapshot.fields).length ? sceneSnapshot : null;
  if (select) {
    select.value = "";
    syncCustomSelect("dialogue-scene-card");
  }
  renderSelectedSceneCardPreview(false);
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("scene-card-selection-changed", {
      selectedSceneCardId,
      currentSceneCard,
      currentSceneCardRecommendation,
    });
  }
}

function applyPresetSelfCard(mode, presetFields = {}) {
  const selfId = mode === "insert" ? String(presetFields.self_card_id || "").trim() : "";
  const selfSnapshot = buildCardSnapshot(presetFields.self_card || {}, selfId);
  const matched = selfId ? selfCards.find((item) => item.card_id === selfId) || null : null;
  const select = el("dialogue-self-card");
  if (matched) {
    selectedSelfCardId = matched.card_id || "";
    currentSelfCard = matched;
    if (select) select.value = selectedSelfCardId;
    syncCustomSelect("dialogue-self-card");
    syncSelectedSelfCardFromSelect();
  } else {
    selectedSelfCardId = "";
    currentSelfCard = mode === "insert" && selfSnapshot.fields && Object.keys(selfSnapshot.fields).length ? selfSnapshot : null;
    if (select) {
      select.value = "";
      syncCustomSelect("dialogue-self-card");
    }
    renderSelectedSelfCardPreview(false);
    if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
      UI_BRIDGE_TOOLS.syncLegacyUiState("self-card-selection-changed", {
        selectedSelfCardId,
        currentSelfCard,
      });
    }
  }
  if (mode === "insert") {
    setValue("dialogue-self-name", presetFields.self_name || currentSelfCard?.fields?.display_name || "");
    setValue("dialogue-self-identity", presetFields.self_identity || currentSelfCard?.fields?.scene_identity || currentSelfCard?.fields?.core_identity || "");
    setValue("dialogue-self-style", presetFields.self_style || currentSelfCard?.fields?.interaction_style || "");
  } else {
    setValue("dialogue-self-name", "");
    setValue("dialogue-self-identity", "");
    setValue("dialogue-self-style", "");
  }
}

function applyOpeningPresetToChatSetup(preset) {
  const fields = preset?.fields || {};
  const mode = String(fields.mode || "observe").trim() || "observe";
  setValue("dialogue-mode", mode);
  setValue("dialogue-participants", Array.isArray(fields.participants) ? fields.participants.join("、") : "");
  setValue("dialogue-controlled", fields.controlled_character || "");
  syncModeFields();
  updateCharacterPillState();
  applyPresetSceneCard(fields);
  applyPresetSelfCard(mode, fields);
  setStatus("dialogue-session-status", `已套用开局模板「${preset?.preview?.title || fields.title || "未命名模板"}」。`);
  publishChatSetupState("chat-setup-opening-preset-applied");
}

async function handleOpeningPresetSelectionChange() {
  syncSelectedOpeningPresetFromSelect();
}

function openNewOpeningPreset() {
  fillOpeningPresetMetaForm({
    preview: {
      title: "",
      note: "",
    },
  });
  setStatus("opening-preset-status", "会把你当前这套模式、人物、角色卡和场景卡一起收成模板。");
  openOpeningPresetModal();
}

function openExistingOpeningPreset() {
  if (!currentOpeningPreset) {
    openNewOpeningPreset();
    return;
  }
  fillOpeningPresetMetaForm(currentOpeningPreset);
  setStatus("opening-preset-status", "保存时会用你当前这套搭配覆盖模板内容。");
  openOpeningPresetModal();
}

async function handleOpeningPresetSubmit(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const title = trimmedValue("opening-preset-title", "");
  const note = trimmedValue("opening-preset-note", "");
  const cardId = trimmedValue("opening-preset-id", "");
  setStatus("opening-preset-status", "正在保存开局模板...");
  try {
    const payload = await window.__ZAOMENG_WEBUI_API__.saveOpeningPreset(cardId, collectOpeningPresetPayload({ title, note }));
    await loadOpeningPresets();
    const select = el("dialogue-opening-preset");
    if (select) {
      select.value = payload.card_id || "";
    }
    syncSelectedOpeningPresetFromSelect();
    setStatus("dialogue-session-status", "这套开局已经收成模板，下次可以一键套用。");
    setStatus("opening-preset-status", "开局模板已保存。");
    closeOpeningPresetModal();
  } catch (error) {
    setStatus("opening-preset-status", error.message || "开局模板保存失败。");
  }
}

async function handleDeleteOpeningPreset(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const cardId = trimmedValue("opening-preset-id", "");
  if (!cardId) return;
  if (!window.confirm("确定删除这套开局模板吗？")) return;
  setStatus("opening-preset-status", "正在删除开局模板...");
  try {
    await window.__ZAOMENG_WEBUI_API__.deleteOpeningPreset(cardId);
    if (selectedOpeningPresetId === cardId) {
      selectedOpeningPresetId = "";
      currentOpeningPreset = null;
    }
    await loadOpeningPresets();
    renderOpeningPresetPreview();
    setStatus("dialogue-session-status", "这套开局模板已经删掉了。");
    setStatus("opening-preset-status", "开局模板已删除。");
    closeOpeningPresetModal();
  } catch (error) {
    setStatus("opening-preset-status", error.message || "开局模板删除失败。");
  }
}

async function handleApplyOpeningPreset(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!currentOpeningPreset) {
    setStatus("dialogue-session-status", "先挑一套开局模板。");
    return;
  }
  applyOpeningPresetToChatSetup(currentOpeningPreset);
}

async function handleStartOpeningPreset(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!currentOpeningPreset) {
    setStatus("dialogue-session-status", "先挑一套开局模板。");
    return;
  }
  applyOpeningPresetToChatSetup(currentOpeningPreset);
  await handleDialogueSessionSubmit({ preventDefault() {} });
}

async function openPersonaReviewForCharacter(characterName = "") {
  if (!currentRunId || !currentRun) return;
  fillPersonaReviewCharacterOptions(currentRun);
  const fallbackCharacter = getRunCharacterNames(currentRun)[0] || "";
  const character = String(characterName || "").trim() || valueOf("persona-review-character", fallbackCharacter) || fallbackCharacter;
  if (character && el("persona-review-character")) {
    setValue("persona-review-character", character);
  }
  if (!character) {
    setStatus("persona-review-status", "这一卷里还没有可校对的人物。");
    return;
  }
  openPersonaReviewModal();
  const reviewActions = readNamedActionBridge("__ZAOMENG_PERSONA_REVIEW_ACTIONS__");
  if (typeof reviewActions.openForCharacter === "function") {
    reviewActions.openForCharacter(character);
    return;
  }
  setStatus("persona-review-status", "正在载入人物档案...");
  try {
    renderPersonaReview(await apiJson(`/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`));
    renderPersonaAutofillReferences(null);
    setStatus("persona-review-status", ""); 
  } catch (error) {
    setStatus("persona-review-status", error.message || "人物档案暂时没有载入。");
  }
}

async function openPersonaReview() {
  await openPersonaReviewForCharacter("");
}

async function openWorkCharacterReview() {
  if (!currentRunId || !currentRun) return;
  const names = getRunCharacterNames(currentRun);
  if (!names.length) {
    setStatus("bookshelf-status", "这一卷里还没有可校对的人物。");
    return;
  }

  let targetCharacter = "";
  if (typeof buildWorkPriorityReviewItems === "function") {
    const priority = buildWorkPriorityReviewItems(currentRun);
    targetCharacter = String(priority?.[0]?.name || "").trim();
  }
  if (!targetCharacter) {
    targetCharacter = names[0] || "";
  }
  if (!targetCharacter) {
    setStatus("bookshelf-status", "这一卷里还没有可校对的人物。");
    return;
  }

  try {
    await openCharacterOverviewViaBridge(targetCharacter);
  } catch (_error) {
    await openPersonaReviewForCharacter(targetCharacter);
  }
}

async function openQuickDialogueMode(mode) {
  await openNewDialogueSession();
  if (!currentRun || !el("dialogue-mode")) return;
  setValue("dialogue-mode", mode);
  syncModeFields();
  updateCharacterPillState();
}

async function handlePersonaCharacterChange() {
  const reviewActions = readNamedActionBridge("__ZAOMENG_PERSONA_REVIEW_ACTIONS__");
  if (typeof reviewActions.handleCharacterChange === "function") {
    reviewActions.handleCharacterChange(valueOf("persona-review-character", ""));
    return;
  }
  if (!currentRunId) return;
  const character = valueOf("persona-review-character", "");
  if (!character) return;
  setStatus("persona-review-status", "正在切换人物...");
  try {
    renderPersonaReview(await apiJson(`/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`));
    renderPersonaAutofillReferences(null);
    setStatus("persona-review-status", "");
  } catch (error) {
    setStatus("persona-review-status", error.message || "人物档案暂时没有载入。");
  }
}

function collectPersonaReviewPayload() {
  return Object.fromEntries(
    (PERSONA_REVIEW_FIELD_BINDINGS || []).map(([field, id]) => [field, trimmedValue(id, "")])
  );
}

async function handlePersonaFieldAutofill(event) {
  const reviewActions = readNamedActionBridge("__ZAOMENG_PERSONA_REVIEW_ACTIONS__");
  if (typeof reviewActions.handleLegacyAutofillEvent === "function") {
    const consumed = reviewActions.handleLegacyAutofillEvent(event);
    if (consumed) return;
  }
  const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-persona-autofill-field]") : null;
  if (!(trigger instanceof HTMLButtonElement) || !currentRunId) return;
  const character = valueOf("persona-review-character", "");
  const field = trigger.getAttribute("data-persona-autofill-field") || "";
  if (!character || !field) {
    setStatus("persona-review-status", "先选一个人物。");
    return;
  }
  const labelText = trigger.closest(".field-card")?.querySelector(".field-card-head span, span")?.textContent || field;
  trigger.dataset.loading = "true";
  trigger.disabled = true;
  const originalText = trigger.textContent || "AI补全";
  trigger.textContent = "生成中...";
  setPersonaReviewFieldFeedback(field, "loading", "正在生成补全...");
  setStatus("persona-review-status", `正在生成「${labelText}」的补全内容...`);
  try {
    const payload = await apiJson(
      `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}/suggest-field`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field }),
      },
      "人物信息补全失败。"
    );
    if (payload?.status === "filled" && payload?.value) {
      const targetId = personaReviewFieldId(field);
      if (targetId) {
        setValue(targetId, payload.value);
      }
      markPersonaReviewFieldAutofilled(field);
      renderPersonaAutofillReferences(payload);
      setPersonaReviewFieldFeedback(field, "success", "已生成补全内容，记得保存。");
      setStatus("persona-review-status", payload.message || "已生成补全内容，请记得保存人物校对。");
    } else {
      renderPersonaAutofillReferences(payload);
      setPersonaReviewFieldFeedback(field, "error", payload?.message || payload?.reason || "人物信息补全无法生成。");
      setStatus("persona-review-status", payload?.message || payload?.reason || "人物信息补全无法生成。");
    }
  } catch (error) {
    renderPersonaAutofillReferences(null);
    setPersonaReviewFieldFeedback(field, "error", error.message || "人物信息补全无法生成。");
    setStatus("persona-review-status", error.message || "人物信息补全无法生成。");
  } finally {
    delete trigger.dataset.loading;
    trigger.disabled = false;
    trigger.textContent = originalText;
    syncPersonaReviewAutofillButtons();
  }
}

async function handlePersonaReviewSubmit(event) {
  event.preventDefault();
  const reviewActions = readNamedActionBridge("__ZAOMENG_PERSONA_REVIEW_ACTIONS__");
  if (typeof reviewActions.submit === "function") {
    reviewActions.submit();
    return;
  }
  if (!currentRunId) return;
  const character = valueOf("persona-review-character", "");
  if (!character) {
    setStatus("persona-review-status", "先选一个人物。");
    return;
  }
  setStatus("persona-review-status", "正在写回人物校对...");
  try {
    renderPersonaReview(
      await apiJson(
        `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectPersonaReviewPayload()),
        },
        "保存人物校对失败。"
      )
    );
    clearAllPersonaReviewAutofilledFields();
    clearAllPersonaReviewFieldFeedback();
    renderPersonaAutofillReferences(null);
    applyRunViewSafely(await apiJson(`/api/web/runs/${currentRunId}`));
    setStatus("persona-review-status", "人物校对已经写回这一卷。");
  } catch (error) {
    setStatus("persona-review-status", error.message || "这次校对没有保存成功。");
  }
}

async function openRelationDetails() {
  if (!currentRunId) return;
  openRelationDetailsModal();
  currentRelationDetails = null;
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("relation-details-loading", { currentRelationDetails: null });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("relation-details-loading", { currentRelationDetails: null });
  }
  setStatus("relation-details-status", "正在整理关系明细...");
  try {
    renderRelationDetails(await apiJson(`/api/web/runs/${currentRunId}/relations`));
  } catch (error) {
    setStatus("relation-details-status", error.message || "关系明细暂时没有载入。");
  }
}

function renderBuiltinNovelList(items) {
  const root = el("builtin-novel-list");
  if (!root) return;
  root.innerHTML = "";
  const entries = Array.isArray(items) ? items : [];
  entries.forEach((item) => {
    const card = document.createElement("article");
    card.className = "builtin-novel-card";

    const head = document.createElement("div");
    head.className = "builtin-novel-card-head";
    head.innerHTML = `
      <div>
        <strong>${escapeHtml(item.title || item.novel_id || item.package_id || "未命名书卷")}</strong>
        <p>${escapeHtml(item.novel_id || "")}</p>
      </div>
      <span class="builtin-novel-badge">${escapeHtml(item.status || "ready")}</span>
    `;

    const meta = document.createElement("p");
    meta.className = "builtin-novel-card-meta";
    const metaParts = [];
    if (Number(item.character_count || 0) > 0) {
      metaParts.push(`${Number(item.character_count || 0)} 位角色`);
    }
    if (item.has_relation_graph) {
      metaParts.push("含关系图谱");
    }
    if (item.updated_at) {
      metaParts.push(`更新于 ${escapeHtml(formatWeakTime(item.updated_at) || item.updated_at)}`);
    }
    meta.textContent = metaParts.join(" · ");

    const actions = document.createElement("div");
    actions.className = "card-actions";
    const startButton = document.createElement("button");
    startButton.type = "button";
    startButton.className = "primary-button";
    startButton.textContent = "复制到我的书架";
    startButton.addEventListener("click", () => {
      handleCloneBuiltinNovel(item.package_id, item.title || item.novel_id || "");
    });
    actions.appendChild(startButton);

    card.appendChild(head);
    if (meta.textContent) {
      card.appendChild(meta);
    }
    card.appendChild(actions);
    root.appendChild(card);
  });
}

async function loadBuiltinNovels() {
  setStatus("builtin-novel-status", "正在翻出内置书卷...");
  try {
    const payload = await apiJson("/api/web/builtin-novels", {}, "内置小说列表载入失败。");
    const items = Array.isArray(payload.items) ? payload.items : [];
    renderBuiltinNovelList(items);
    setStatus(
      "builtin-novel-status",
      items.length
        ? `当前有 ${items.length} 卷可直接试玩的内置小说。`
        : "内置目录里暂时还没有小说包，你可以先导出一卷再放进去。"
    );
    return items;
  } catch (error) {
    renderBuiltinNovelList([]);
    setStatus("builtin-novel-status", error.message || "内置小说列表暂时没有载入。");
    throw error;
  }
}

async function handleOpenBuiltinNovelModal() {
  if (!modelSettings.configured) {
    openSettingsModal();
    setStatus("builtin-novel-status", "先把故事声源接进来，再直接试玩内置小说。");
    return;
  }
  openBuiltinNovelModal();
  await loadBuiltinNovels().catch(() => {});
}

async function handleCloneBuiltinNovel(packageId, title = "") {
  const safeTitle = String(title || "").trim();
  setStatus("builtin-novel-status", safeTitle ? `正在把《${safeTitle}》复制到你的书架...` : "正在复制这卷书...");
  try {
    const run = await apiJson(
      `/api/web/builtin-novels/${encodeURIComponent(packageId)}/clone`,
      {
        method: "POST",
      },
      "复制内置小说失败。"
    );
    closeBuiltinNovelModal();
    applyRunViewSafely(run);
    await loadRunsOverview();
    setStatus("bookshelf-status", safeTitle ? `《${safeTitle}》已经落到你的书架里，可以直接开聊。` : "内置小说已经复制到你的书架里。");
  } catch (error) {
    setStatus("builtin-novel-status", error.message || "这卷内置小说暂时没有复制成功。");
  }
}

function triggerImportRunPackage() {
  el("import-run-package-input")?.click();
}

async function handleImportRunPackage(event) {
  const input = event?.target;
  if (!(input instanceof HTMLInputElement)) return;
  const file = input.files?.[0];
  if (!file) return;
  setStatus("bookshelf-status", `正在导入 ${file.name}...`);
  try {
    const run = await apiJson(
      "/api/web/runs/import",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          content_base64: await fileToBase64(file),
        }),
      },
      "导入小说包失败。"
    );
    input.value = "";
    applyRunViewSafely(run);
    await loadRunsOverview();
    setStatus("bookshelf-status", `《${runNovelTitle(run)}》已经导入到你的书架。`);
  } catch (error) {
    input.value = "";
    setStatus("bookshelf-status", error.message || "这次导入没有接上。");
  }
}

async function handleExportRunPackage() {
  if (!currentRunId) {
    setStatus("bookshelf-status", "先选中一卷书，再导出小说包。");
    return;
  }
  const run = currentRun || findRunById(currentRunId);
  if (String(run?.status || "").trim() === "running") {
    setStatus("bookshelf-status", "这本书还在整理中，等这一轮结束后再导出。");
    return;
  }
  const runId = String(currentRunId || "").trim();
  if (isRunPackageExportPending(runId)) {
    return;
  }
  const title = runNovelTitle(run);
  setRunPackageExportPending(runId, true);
  setStatus("bookshelf-status", `正在打包《${title}》的小说包...`);
  try {
    const response = await fetch(`/api/web/runs/${encodeURIComponent(runId)}/export`);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "导出小说包失败。");
    }
    const blob = await response.blob();
    const fallbackName = `${String(run?.novel_id || title || "zaomeng-run").trim() || "zaomeng-run"}.zaomeng-run.zip`;
    downloadBlobFile(blob, resolveDownloadFilename(response, fallbackName));
    setStatus("bookshelf-status", `《${title}》的小说包已经准备好，正在开始下载。`);
  } catch (error) {
    setStatus("bookshelf-status", error.message || "这次导出没有接上。");
  } finally {
    setRunPackageExportPending(runId, false);
  }
}

function openAppUpdateModal() {
  toggle("app-update-modal", true);
  if (typeof syncModalScrollLock === "function") syncModalScrollLock();
}

function closeAppUpdateModal() {
  toggle("app-update-modal", false);
  if (typeof syncModalScrollLock === "function") syncModalScrollLock();
}

function appUpdateDismissKey(currentVersion, remoteVersion) {
  return `${APP_UPDATE_DISMISS_PREFIX}${String(currentVersion || "").trim()}->${String(remoteVersion || "").trim()}`;
}

function rememberDismissedAppUpdate(status = appUpdateStatus) {
  const currentVersion = String(status?.current_version || "").trim();
  const remoteVersion = String(status?.remote_version || "").trim();
  if (!currentVersion || !remoteVersion || !window.localStorage) return;
  window.localStorage.setItem(appUpdateDismissKey(currentVersion, remoteVersion), "1");
}

function wasAppUpdateDismissed(status = appUpdateStatus) {
  const currentVersion = String(status?.current_version || "").trim();
  const remoteVersion = String(status?.remote_version || "").trim();
  if (!currentVersion || !remoteVersion || !window.localStorage) return false;
  return window.localStorage.getItem(appUpdateDismissKey(currentVersion, remoteVersion)) === "1";
}

function clearAppUpdatePolling() {
  if (!appUpdatePollTimer) return;
  window.clearTimeout(appUpdatePollTimer);
  appUpdatePollTimer = 0;
}

function renderAppUpdateStatus(status) {
  appUpdateStatus = status || null;
  setText("app-update-current-version", status?.current_version || "-", "");
  setText("app-update-remote-version", status?.remote_version || "-", "");
  setStatus("app-update-status", status?.message || "");
  const confirmButton = el("confirm-app-update-button");
  const closeButton = el("close-app-update-button");
  const dismissButton = el("dismiss-app-update-button");
  const updating = String(status?.status || "") === "updating";
  if (confirmButton) {
    confirmButton.disabled = updating || !status?.update_available;
    confirmButton.textContent = updating ? "更新中..." : "现在更新";
  }
  if (closeButton) closeButton.disabled = updating;
  if (dismissButton) dismissButton.disabled = updating;
}

async function fetchAppUpdateStatus(force = false) {
  const suffix = force ? "?force=true" : "";
  const status = await apiJson(`/api/web/settings/update${suffix}`, {}, "检查更新失败。");
  renderAppUpdateStatus(status);
  return status;
}

function scheduleAppUpdatePolling() {
  clearAppUpdatePolling();
  appUpdatePollTimer = window.setTimeout(async () => {
    try {
      const status = await fetchAppUpdateStatus(false);
      if (status?.status === "updating") {
        scheduleAppUpdatePolling();
        return;
      }
      if (status?.status === "completed" && status?.reload_required) {
        window.setTimeout(() => window.location.reload(), 900);
      }
    } catch (error) {
      setStatus("app-update-status", error.message || "刚才那次更新状态暂时没取到。");
    }
  }, 1200);
}

async function checkAppUpdateOnBoot() {
  try {
    const status = await fetchAppUpdateStatus(true);
    if (!status?.supported || !status?.update_available || wasAppUpdateDismissed(status)) {
      return;
    }
    openAppUpdateModal();
  } catch (error) {
    console.warn("checkAppUpdateOnBoot failed", error);
  }
}

function dismissAppUpdateModal() {
  rememberDismissedAppUpdate(appUpdateStatus);
  closeAppUpdateModal();
}

async function handleConfirmAppUpdate() {
  const confirmButton = el("confirm-app-update-button");
  if (confirmButton) confirmButton.disabled = true;
  setStatus("app-update-status", "正在替你接上更新...");
  try {
    const status = await apiJson(
      "/api/web/settings/update",
      {
        method: "POST",
      },
      "开始更新失败。"
    );
    renderAppUpdateStatus(status);
    openAppUpdateModal();
    scheduleAppUpdatePolling();
  } catch (error) {
    if (confirmButton) confirmButton.disabled = false;
    setStatus("app-update-status", error.message || "这次更新没有接上。");
  }
}

const DIALOGUE_PLACEHOLDER_DEFAULT = "写一句你想让他们听见的话";
const DIALOGUE_PLACEHOLDER_NARRATION = "写一句推进剧情的场景提示";
const DIALOGUE_PLACEHOLDER_WAITING = "他们正在接住你的话。";
const DIALOGUE_SUGGESTION_WAITING = "正在生成中...";
const DIALOGUE_SUGGESTION_BUSY_LABEL = "…";
const DIALOGUE_RETRY_FEEDBACK_DELAY_MS = 2200;
const DIALOGUE_SEND_RETRY_MESSAGE = "这次声源有点慢，正在自动重试...";
const DIALOGUE_SUGGEST_RETRY_MESSAGE = "这次生成有点慢，正在自动重试...";
const OBSERVE_QUICK_REPLIES = [
  { label: "……", value: "……" },
  { label: "继续聊", value: "继续聊。" },
  { label: "别停", value: "别停，继续往下说。" },
  { label: "有人打断", value: "门外忽然传来一点动静，屋里的人都顿了一下。" },
  { label: "再逼近点", value: "这句话落下去以后，气氛反而更近了一步。" },
];
let currentDialogueMessageKind = "dialogue";

function buildObserveQuickReplies(session = currentDialogueSession) {
  const overview = session?.runtime_state_overview || {};
  const present = Array.isArray(overview?.present) ? overview.present.filter(Boolean) : [];
  const offstage = Array.isArray(overview?.offstage) ? overview.offstage.filter(Boolean) : [];
  const shouldShift = Boolean(overview?.should_offer_scene_shift);
  const nextHint = String(overview?.next_hint || "").trim();
  const tension = String(overview?.tension || "").trim();
  const eventRows = Array.isArray(overview?.event_rows) ? overview.event_rows : [];
  const dynamic = [];

  if (shouldShift) {
    dynamic.push({
      label: "转下一幕",
      value: nextHint || "这一拍差不多收住了，场面顺势往下一幕转过去。",
    });
  }
  if (offstage.length) {
    dynamic.push({
      label: `切回${String(offstage[0]).slice(0, 4)}`,
      value: `${offstage[0]}那边也有了新的动静，镜头顺势切过去。`,
    });
  }
  if (present.length >= 2) {
    dynamic.push({
      label: "只留他们",
      value: `旁的人都暂时退开，只剩${present.slice(0, 2).join("和")}把这句话接下去。`,
    });
  }
  if (tension) {
    dynamic.push({
      label: "顺着张力",
      value: "这股气氛没有散，反而又往前逼近了一步。",
    });
  }
  const lastEvent = eventRows.length ? eventRows[eventRows.length - 1] : null;
  if (lastEvent?.copy) {
    dynamic.push({
      label: "顺着波动",
      value: String(lastEvent.copy || "").trim(),
    });
  }

  const merged = [];
  const seen = new Set();
  [...dynamic, ...OBSERVE_QUICK_REPLIES].forEach((item) => {
    const label = String(item?.label || "").trim();
    const value = String(item?.value || "").trim();
    if (!label || !value) return;
    const key = `${label}::${value}`;
    if (seen.has(key)) return;
    seen.add(key);
    merged.push({ label, value });
  });
  return merged.slice(0, 6);
}

function buildComposerUiState() {
  const area = el("dialogue-message");
  const sendButton = el("prepare-turn-button");
  const suggestButton = el("suggest-turn-button");
  const mode = currentDialogueSession?.mode || currentDialogueSession?.session_card?.mode || "";
  const nextHint = mode === "observe" ? String(currentDialogueSession?.runtime_state_overview?.next_hint || "").trim() : "";
  return {
    mode,
    kind: normalizeDialogueMessageKind(currentDialogueMessageKind),
    message: String(area?.value || ""),
    placeholder: String(area?.placeholder || ""),
    disabled: Boolean(area?.disabled),
    suggestHidden: Boolean(suggestButton?.classList.contains("hidden")),
    suggestDisabled: Boolean(suggestButton?.disabled),
    sendDisabled: Boolean(sendButton?.disabled),
    quickReplies: mode === "observe" ? buildObserveQuickReplies(currentDialogueSession) : [],
    quickHint: nextHint,
  };
}

window.__ZAOMENG_BUILD_COMPOSER_STATE__ = buildComposerUiState;

function publishComposerUiState(source = "composer") {
  if (typeof UI_BRIDGE_TOOLS.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState(source, { composer: buildComposerUiState() });
  } else if (typeof UI_BRIDGE_TOOLS.publishLegacyStateSlice === "function") {
    UI_BRIDGE_TOOLS.publishLegacyStateSlice(source, "composer", buildComposerUiState());
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState(source, { composer: buildComposerUiState() });
  }
}

function normalizeDialogueMessageKind(kind) {
  const value = String(kind || "").trim().toLowerCase();
  return value === "narration" ? "narration" : "dialogue";
}

function readDialogueMessageKind() {
  const active = document.querySelector("#dialogue-message-kind .kind-chip.active");
  if (active instanceof HTMLElement) {
    return normalizeDialogueMessageKind(active.dataset.kind);
  }
  return normalizeDialogueMessageKind(currentDialogueMessageKind);
}

function updateDialogueMessagePlaceholder() {
  const area = el("dialogue-message");
  if (!area) return;
  const kind = readDialogueMessageKind();
  area.placeholder = kind === "narration" ? DIALOGUE_PLACEHOLDER_NARRATION : DIALOGUE_PLACEHOLDER_DEFAULT;
}

function setDialogueMessageKind(kind) {
  currentDialogueMessageKind = normalizeDialogueMessageKind(kind);
  document.querySelectorAll("#dialogue-message-kind .kind-chip").forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    node.classList.toggle("active", normalizeDialogueMessageKind(node.dataset.kind) === currentDialogueMessageKind);
  });
  updateDialogueMessagePlaceholder();
  publishComposerUiState("composer-kind-updated");
}

function setQuickRepliesEnabled(enabled) {
  document.querySelectorAll("#observe-quick-replies .quick-reply-chip").forEach((node) => {
    node.disabled = !enabled;
  });
}

function syncSuggestButtonVisibility(session = currentDialogueSession) {
  const suggestButton = el("suggest-turn-button");
  if (!suggestButton) return;
  const mode = session?.mode || session?.session_card?.mode || "";
  const hidden = mode === "observe";
  suggestButton.classList.toggle("hidden", hidden);
  if (hidden) {
    suggestButton.disabled = true;
  }
  publishComposerUiState("composer-suggest-visibility-updated");
}

function setComposerWaiting(waiting, message = "") {
  const area = el("dialogue-message");
  const sendButton = el("prepare-turn-button");
  const suggestButton = el("suggest-turn-button");
  if (!area) return;
  if (waiting) {
    area.value = message || DIALOGUE_PLACEHOLDER_WAITING;
    area.disabled = true;
    if (sendButton) sendButton.disabled = true;
    if (suggestButton) suggestButton.disabled = true;
  } else {
    area.disabled = false;
    if (sendButton) sendButton.disabled = false;
    if (suggestButton) suggestButton.disabled = false;
    area.value = message || "";
    updateDialogueMessagePlaceholder();
  }
  setQuickRepliesEnabled(!waiting);
  resizeComposer();
  publishComposerUiState("composer-waiting-updated");
}

function setSuggestingState(waiting) {
  const area = el("dialogue-message");
  const sendButton = el("prepare-turn-button");
  const suggestButton = el("suggest-turn-button");
  if (area) area.disabled = waiting;
  if (sendButton) sendButton.disabled = waiting;
  if (suggestButton) {
    suggestButton.disabled = waiting;
    suggestButton.textContent = waiting ? DIALOGUE_SUGGESTION_BUSY_LABEL : "✨";
    suggestButton.setAttribute("aria-busy", waiting ? "true" : "false");
  }
  setQuickRepliesEnabled(!waiting);
  publishComposerUiState("composer-suggesting-updated");
}

function renderObserveQuickReplies(session = currentDialogueSession) {
  const root = el("observe-quick-replies");
  const hint = el("observe-quick-hint");
  const hintRow = el("observe-quick-hint-row");
  const hintSend = el("observe-quick-hint-send");
  if (!root) return;
  const mode = session?.mode || session?.session_card?.mode || "";
  if (mode !== "observe") {
    root.innerHTML = "";
    root.classList.add("hidden");
    if (hintRow) hintRow.classList.add("hidden");
    if (hint) {
      hint.textContent = "";
      hint.classList.add("hidden");
    }
    if (hintSend) {
      hintSend.classList.add("hidden");
      hintSend.removeAttribute("data-value");
    }
    publishComposerUiState("composer-quick-replies-hidden");
    return;
  }

  root.innerHTML = "";
  buildObserveQuickReplies(session).forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-reply-chip";
    button.textContent = item.label;
    button.setAttribute("data-value", item.value);
    button.addEventListener("click", () => {
      applyQuickReply(item.value);
    });
    root.appendChild(button);
  });
  root.classList.remove("hidden");
  const nextHint = String(session?.runtime_state_overview?.next_hint || "").trim();
  if (hint) {
    hint.textContent = nextHint ? `顺手往下推：${nextHint}` : "";
    hint.classList.toggle("hidden", !nextHint);
  }
  if (hintSend) {
    hintSend.classList.toggle("hidden", !nextHint);
    if (nextHint) {
      hintSend.setAttribute("data-value", nextHint);
    } else {
      hintSend.removeAttribute("data-value");
    }
  }
  if (hintRow) {
    hintRow.classList.toggle("hidden", !nextHint);
  }
  publishComposerUiState("composer-quick-replies-rendered");
}

async function applyQuickHint() {
  const button = el("observe-quick-hint-send");
  const value = String(button?.getAttribute("data-value") || "").trim();
  if (!value) return;
  await applyQuickReply(value);
}

async function applyQuickReply(value) {
  const message = String(value || "").trim();
  const area = el("dialogue-message");
  if (!message || !area || area.disabled) return;
  publishComposerUiState("composer-quick-reply-picked");
  await handleSendTurn(message, "narration");
}

function setComposerDraft(value = "", options = {}) {
  const area = el("dialogue-message");
  if (!area) return;
  area.value = String(value || "");
  resizeComposer();
  if (options.focus) {
    area.focus();
    area.setSelectionRange(area.value.length, area.value.length);
  }
  if (options.publish !== false) {
    publishComposerUiState("composer-draft-updated");
  }
}

function coerceMessageOverride(value) {
  if (value && typeof value === "object") {
    if (typeof value.preventDefault === "function") value.preventDefault();
    if (typeof value.stopPropagation === "function") value.stopPropagation();
    return "";
  }
  return String(value || "");
}

async function handleSendTurn(messageOverride = "", messageKindOverride = "") {
  if (!currentRunId || !currentDialogueSessionId) {
    setComposerWaiting(false, "先进入这一幕，再把话递出去。");
    return;
  }
  const message = coerceMessageOverride(messageOverride).trim() || trimmedValue("dialogue-message", "");
  const messageKind = normalizeDialogueMessageKind(messageKindOverride || readDialogueMessageKind());
  if (!message) {
    setComposerWaiting(false, messageKind === "narration" ? "先写一句剧情推动提示。" : "先写一句你想让他们听见的话。");
    return;
  }

  const sessionSnapshot = currentDialogueSession ? JSON.parse(JSON.stringify(currentDialogueSession)) : null;
  const retryFeedbackTimer = window.setTimeout(() => {
    setComposerWaiting(true, DIALOGUE_SEND_RETRY_MESSAGE);
  }, DIALOGUE_RETRY_FEEDBACK_DELAY_MS);
  setComposerWaiting(true, DIALOGUE_PLACEHOLDER_WAITING);

  if (currentDialogueSession) {
    currentDialogueSession = {
      ...currentDialogueSession,
      transcript: buildOptimisticTranscript(currentDialogueSession, message, messageKind),
    };
    renderDialogueTranscript(currentDialogueSession);
    if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
      UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-optimistic", {
        currentDialogueSessionId,
        currentDialogueSession,
      });
    } else if (typeof publishLegacyUiState === "function") {
      publishLegacyUiState("dialogue-session-optimistic", {
        currentDialogueSessionId,
        currentDialogueSession,
      });
    }
  }

  try {
    await renderDialogueSession(
      await apiJson(
        `/api/web/runs/${currentRunId}/dialogue/sessions/${currentDialogueSessionId}/reply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, message_kind: messageKind }),
        },
        "发送失败。"
      )
    );
    window.clearTimeout(retryFeedbackTimer);
    setComposerWaiting(false, "");
  } catch (error) {
    window.clearTimeout(retryFeedbackTimer);
    if (sessionSnapshot) {
      if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
        UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-restore-local", {
          currentDialogueSessionId,
          currentDialogueSession: sessionSnapshot,
        });
      } else {
        currentDialogueSession = sessionSnapshot;
      }
      renderDialogueTranscript(sessionSnapshot);
      if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
        UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-restore", {
          currentDialogueSessionId,
          currentDialogueSession: sessionSnapshot,
        });
      } else if (typeof publishLegacyUiState === "function") {
        publishLegacyUiState("dialogue-session-restore", {
          currentDialogueSessionId,
          currentDialogueSession: sessionSnapshot,
        });
      }
    }
    setComposerWaiting(false, error.message || "这句话暂时没有送达。");
  }
}

async function handleSuggestTurn(event) {
  if (event && typeof event.preventDefault === "function") {
    event.preventDefault();
  }
  console.log("[dialogue suggest] click", {
    runId: currentRunId,
    sessionId: currentDialogueSessionId,
  });
  if (!currentRunId || !currentDialogueSessionId) {
    return;
  }

  const area = el("dialogue-message");
  if (!area) return;

  const draftText = String(area.value || "");
  const seedText = draftText.trim();
  area.value = DIALOGUE_SUGGESTION_WAITING;
  resizeComposer();
  setSuggestingState(true);
  const retryFeedbackTimer = window.setTimeout(() => {
    area.value = DIALOGUE_SUGGEST_RETRY_MESSAGE;
    resizeComposer();
    publishComposerUiState("composer-suggest-retrying");
  }, DIALOGUE_RETRY_FEEDBACK_DELAY_MS);

  try {
    console.log("[dialogue suggest] request", { seedText });
    const payload = await apiJson(
      `/api/web/runs/${currentRunId}/dialogue/sessions/${currentDialogueSessionId}/suggest`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed_text: seedText }),
      },
      "续写建议生成失败。"
    );
    console.log("[dialogue suggest] success", payload);
    window.clearTimeout(retryFeedbackTimer);
    area.value = payload.suggestion || "";
    area.focus();
    area.setSelectionRange(area.value.length, area.value.length);
    resizeComposer();
  } catch (error) {
    console.log("[dialogue suggest] error", error);
    window.clearTimeout(retryFeedbackTimer);
    area.value = draftText;
    resizeComposer();
  } finally {
    setSuggestingState(false);
  }
}

function bindEvents() {
  bind("open-bookshelf-button", "click", showBookshelfHome);
  bind("open-settings-button", "click", openSettingsModal);
  bind("open-settings-primary", "click", openSettingsModal);
  bind("close-settings-button", "click", closeSettingsModal);
  bind("close-persona-review-button", "click", closePersonaReviewModal);
  bind("close-relation-details-button", "click", closeRelationDetailsModal);
  bind("close-scene-card-button", "click", closeSceneCardModal);
  bind("close-self-card-button", "click", closeSelfCardModal);
  bind("close-opening-preset-button", "click", closeOpeningPresetModal);
  bind("close-builtin-novel-button", "click", closeBuiltinNovelModal);
  bind("close-app-update-button", "click", dismissAppUpdateModal);
  bind("dismiss-app-update-button", "click", dismissAppUpdateModal);
  bind("confirm-app-update-button", "click", handleConfirmAppUpdate);
  bind("toggle-sidebar-button", "click", () => {
    sidebarCollapsed = !sidebarCollapsed;
    applySidebarState();
  });
  bind("new-dialogue-session-button", "click", openNewDialogueSession);
  bind("bookshelf-open-builtin-button", "click", () => {
    handleOpenBuiltinNovelModal().catch((error) => setStatus("builtin-novel-status", error.message || "内置小说列表暂时没有载入。"));
  });
  bind("bookshelf-import-run-button", "click", triggerImportRunPackage);
  bind("refresh-builtin-novels-button", "click", () => {
    loadBuiltinNovels().catch(() => {});
  });
  bind("bookshelf-new-run-button", "click", startNewRunFlow);
  bind("back-from-distill-button", "click", showBookshelfHome);
  bind("import-run-package-input", "change", handleImportRunPackage);
  bind("detail-start-chat-button", "click", openNewDialogueSession);
  bind("quick-open-observe-button", "click", () => {
    openQuickDialogueMode("observe").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
  });
  bind("quick-open-act-button", "click", () => {
    openQuickDialogueMode("act").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
  });
  bind("quick-open-insert-button", "click", () => {
    openQuickDialogueMode("insert").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
  });
  bind("detail-stop-run-button", "click", handleStopRun);
  bind("open-persona-review-button", "click", () => {
    openWorkCharacterReview().catch((error) => {
      setStatus("bookshelf-status", error.message || "人物档案暂时没有载入。");
    });
  });
  bind("open-relation-details-button", "click", openRelationDetails);
  bind("detail-export-summary-button", "click", () => {
    if (typeof openWorkSummaryExport === "function") {
      openWorkSummaryExport();
      return;
    }
    openWorkSummaryExportFallback();
  });
  bind("detail-export-package-button", "click", handleExportRunPackage);
  bind("detail-view-timeline-button", "click", () => {
    if (typeof openWorkTimeline === "function") {
      openWorkTimeline();
      return;
    }
    openWorkTimelineFallback();
  });
  bind("back-to-work-overview-button", "click", () => {
    characterOverviewOpen = false;
    updateWorkflowState();
  });
  bind("character-overview-review-button", "click", () => {
    if (!currentCharacterOverview?.character) return;
    openPersonaReviewForCharacter(currentCharacterOverview.character).catch((error) =>
      setStatus("persona-review-status", error.message || "人物档案暂时没有载入。")
    );
  });
  bind("character-overview-redistill-button", "click", () => {
    if (typeof openCharacterOverviewIncrementalDistill === "function") {
      openCharacterOverviewIncrementalDistill();
      return;
    }
    if (!openCharacterOverviewIncrementalDistillViaBridge()) {
      setStatus("redistill-status", "角色增量能力暂时没有载入。");
    }
  });
  bind("character-overview-act-button", "click", () => {
    if (typeof openCharacterOverviewSessionMode === "function") {
      openCharacterOverviewSessionMode("act").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
      return;
    }
    openCharacterOverviewSessionModeViaBridge("act").catch((error) =>
      setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。")
    );
  });
  bind("character-overview-insert-button", "click", () => {
    if (typeof openCharacterOverviewSessionMode === "function") {
      openCharacterOverviewSessionMode("insert").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
      return;
    }
    openCharacterOverviewSessionModeViaBridge("insert").catch((error) =>
      setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。")
    );
  });
  bind("character-overview-export-button", "click", () => {
    if (typeof openCurrentCharacterProfileFile === "function") {
      openCurrentCharacterProfileFile();
      return;
    }
    if (!openCurrentCharacterProfileFileViaBridge()) {
      setStatus("character-overview-status", "当前人物原档暂时不可用。");
    }
  });
  el("character-overview-key-fields")?.addEventListener("click", (event) => {
    if (typeof handleCharacterOverviewFieldAutofill === "function") {
      handleCharacterOverviewFieldAutofill(event);
    }
    if (typeof handleCharacterOverviewFieldSave === "function") {
      handleCharacterOverviewFieldSave(event);
    }
  });
  el("character-overview-key-fields")?.addEventListener("input", (event) => {
    if (typeof handleCharacterOverviewFieldInput === "function") {
      handleCharacterOverviewFieldInput(event);
    }
  });
  el("character-overview-advanced-groups")?.addEventListener("click", (event) => {
    if (typeof handleCharacterOverviewAdvancedGroupToggle === "function") {
      handleCharacterOverviewAdvancedGroupToggle(event);
    }
  });
  window.addEventListener("resize", () => {
    if (typeof syncViewportHeightVar === "function") {
      syncViewportHeightVar();
    }
    if (typeof applySessionListViewportLock === "function") {
      applySessionListViewportLock();
    }
  });
  bind("detail-redistill-button", "click", () => {
    if (!currentRunId) return;
    redistillPanelOpen = !redistillPanelOpen;
    renderBookshelfDetail(currentRun);
    updateWorkflowState();
    if (redistillPanelOpen) {
      el("redistill-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      el("redistill-characters")?.focus();
    }
  });
  bind("source-history-toggle", "click", () => {
    sourceHistoryExpanded = !sourceHistoryExpanded;
    if (currentRun) {
      renderSourceHistory(currentRun);
    }
  });
  bind("run-character-readiness-toggle", "click", () => {
    characterReadinessExpanded = !characterReadinessExpanded;
    if (currentRun) {
      renderCharacterReadiness(currentRun);
    }
  });
  bind("work-session-preview-toggle", "click", () => {
    workSessionPreviewExpanded = !workSessionPreviewExpanded;
    if (currentRun) {
      renderWorkSessionPreview(currentRun);
    }
  });
  bind("back-to-bookshelf-button", "click", showBookshelfHome);
  bind("back-to-detail-button", "click", () => {
    chatModePickerOpen = false;
    updateWorkflowState();
  });

  bind("model-settings-form", "submit", handleModelSettingsSubmit);
  bind("persona-review-form", "submit", handlePersonaReviewSubmit);
  bind("scene-card-form", "submit", handleSceneCardSubmit);
  bind("self-card-form", "submit", handleSelfCardSubmit);
  bind("opening-preset-form", "submit", handleOpeningPresetSubmit);
  bind("create-run-form", "submit", handleCreateRunSubmit);
  bind("redistill-button", "click", handleRedistill);
  bind("redistill-add-button", "click", handleRedistillAdd);
  bind("redistill-refresh-button", "click", handleRedistillRefresh);
  bind("redistill-recommend-button", "click", handleRedistillRecommend);
  bind("dialogue-session-form", "submit", handleDialogueSessionSubmit);
  bind("create-opening-preset-button", "click", () => openNewOpeningPreset());
  bind("edit-opening-preset-button", "click", () => openExistingOpeningPreset());
  bind("apply-opening-preset-button", "click", handleApplyOpeningPreset);
  bind("start-opening-preset-button", "click", handleStartOpeningPreset);
  bind("delete-opening-preset-button", "click", handleDeleteOpeningPreset);
  bind("recommend-scene-card-button", "click", handleRecommendSceneCard);
  bind("dialogue-live-scene-recommend", "click", handleRecommendDialogueSceneCard);
  bind("dialogue-live-scene-shift-recommend", "click", handleRecommendDialogueSceneCard);
  bind("dialogue-live-scene-apply", "click", handleApplyDialogueSceneCard);
  bind("create-scene-card-button", "click", handleOpenNewSceneCard);
  bind("edit-scene-card-button", "click", handleEditCurrentSceneCard);
  bind("generate-scene-card-button", "click", handleGenerateSceneCard);
  bind("duplicate-scene-card-button", "click", handleDuplicateSceneCard);
  bind("delete-scene-card-button", "click", handleDeleteSceneCard);
  bind("create-self-card-button", "click", handleOpenNewSelfCard);
  bind("edit-self-card-button", "click", handleEditCurrentSelfCard);
  bind("generate-self-card-button", "click", handleGenerateSelfCard);
  bind("delete-self-card-button", "click", handleDeleteSelfCard);
  bind("suggest-turn-button", "click", handleSuggestTurn);
  bind("prepare-turn-button", "click", handleSendTurn);
  el("dialogue-message-kind")?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.classList.contains("kind-chip")) return;
    setDialogueMessageKind(target.dataset.kind || "dialogue");
  });
  bind("dialogue-memory-copy-button", "click", () => {
    if (typeof window.copyDialogueMemorySummary === "function") {
      window.copyDialogueMemorySummary();
    }
  });
  bind("dialogue-memory-toggle-button", "click", () => {
    if (typeof window.toggleDialogueMemory === "function") {
      window.toggleDialogueMemory();
    }
  });
  bind("observe-quick-hint-send", "click", () => {
    applyQuickHint().catch((error) => {
      setStatus("dialogue-session-status", error.message || "这句推进提示暂时没有送出去。");
    });
  });
  bind("close-dialogue-memory-modal-button", "click", () => {
    if (typeof window.closeDialogueMemoryModal === "function") {
      window.closeDialogueMemoryModal();
    }
  });
  bind("dialogue-memory-modal-backdrop", "click", () => {
    if (typeof window.closeDialogueMemoryModal === "function") {
      window.closeDialogueMemoryModal();
    }
  });

  bind("dialogue-mode", "change", syncModeFields);
  bind("dialogue-opening-preset", "change", handleOpeningPresetSelectionChange);
  bind("dialogue-scene-card", "change", handleSceneCardSelectionChange);
  bind("dialogue-self-card", "change", handleSelfCardSelectionChange);
  el("scene-card-form")?.addEventListener("input", () => {
    publishSceneCardEditorState("scene-card-input");
  });
  el("self-card-form")?.addEventListener("input", () => {
    publishSelfCardEditorState("self-card-input");
  });
  bind("persona-review-character", "change", handlePersonaCharacterChange);
  el("persona-review-form")?.addEventListener("input", (event) => {
    const target = event.target;
    if (target instanceof HTMLElement) {
      const field = PERSONA_REVIEW_FIELD_BINDINGS.find(([, id]) => id === target.id)?.[0];
      if (field) {
        clearPersonaReviewFieldAutofilled(field);
        setPersonaReviewFieldFeedback(field, "", "");
      }
    }
    syncPersonaReviewAutofillButtons();
  });
  el("persona-review-form")?.addEventListener("click", handlePersonaFieldAutofill);
  bind("dialogue-mode", "change", updateCharacterPillState);
  bind("dialogue-participants", "input", updateCharacterPillState);
  bind("dialogue-participants", "input", () => publishChatSetupState("chat-setup-participants-input"));
  bind("dialogue-controlled", "input", () => publishChatSetupState("chat-setup-controlled-input"));
  bind("dialogue-self-name", "input", () => publishChatSetupState("chat-setup-self-name-input"));
  bind("dialogue-self-identity", "input", () => publishChatSetupState("chat-setup-self-identity-input"));
  bind("dialogue-self-style", "input", () => publishChatSetupState("chat-setup-self-style-input"));
  bind("redistill-characters", "input", updateRedistillPillState);
  bind("dialogue-message", "input", () => {
    resizeComposer();
    publishComposerUiState("composer-input");
  });
  bind("novel-file", "change", updateNovelFileView);
  bind("characters", "input", refreshSamplingHintEstimate);
  bind("max-sentences", "input", refreshSamplingHintEstimate);
  bind("max-chars", "input", refreshSamplingHintEstimate);
  bind("redistill-novel-file", "change", updateRedistillFileView);
  bind("dialogue-message", "keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      el("prepare-turn-button")?.click();
    }
  });

  bindChoiceGroup("dialogue-mode-options", "dialogue-mode", syncModeFields);
  bindChoiceGroup("dialogue-mode-options", "dialogue-mode", updateCharacterPillState);
  bindChoiceGroup("model-provider-options", "model-provider");

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.closeModal === "true") {
      const modalId = target.dataset.modalId || "settings-modal";
      if (modalId === "persona-review-modal") {
        closePersonaReviewModal();
      } else if (modalId === "scene-card-modal") {
        closeSceneCardModal();
      } else if (modalId === "self-card-modal") {
        closeSelfCardModal();
      } else if (modalId === "dialogue-memory-modal") {
        if (typeof window.closeDialogueMemoryModal === "function") {
          window.closeDialogueMemoryModal();
        }
      } else if (modalId === "relation-details-modal") {
        closeRelationDetailsModal();
      } else if (modalId === "builtin-novel-modal") {
        closeBuiltinNovelModal();
      } else if (modalId === "app-update-modal") {
        dismissAppUpdateModal();
      } else {
        closeSettingsModal();
      }
    }
  });
}

async function boot() {
  if (typeof syncViewportHeightVar === "function") {
    syncViewportHeightVar();
  }
  ensureConnectionDetailsVisible();
  syncModeFields();
  syncChoiceGroup("dialogue-mode-options", "dialogue-mode");
  syncChoiceGroup("model-provider-options", "model-provider");
  updateNovelFileView();
  updateRedistillFileView();
  resizeComposer();
  setDialogueMessageKind(currentDialogueMessageKind);
  applySidebarState();
  initCustomSelect("dialogue-scene-card");
  initCustomSelect("dialogue-self-card");
  try {
    await Promise.all([
      loadModelSettings().catch((error) => console.warn("loadModelSettings failed", error)),
      loadOpeningPresets().catch((error) => console.warn("loadOpeningPresets failed", error)),
      loadSceneCards().catch((error) => console.warn("loadSceneCards failed", error)),
      loadSelfCards().catch((error) => console.warn("loadSelfCards failed", error)),
      loadRecentSessions().catch((error) => console.warn("loadRecentSessions failed", error)),
      loadRunsOverview().catch((error) => console.warn("loadRunsOverview failed", error)),
    ]);
    await checkAppUpdateOnBoot();
  } finally {
    workflowBootPending = false;
    updateWorkflowState();
  }
}

bindEvents();
const chatSetupActions = {
  setMode(mode) {
    setValue("dialogue-mode", mode);
    syncModeFields();
    updateCharacterPillState();
  },
  setParticipants(value) {
    setValue("dialogue-participants", value);
    updateCharacterPillState();
    publishChatSetupState("chat-setup-participants-updated");
  },
  toggleParticipant(name) {
    toggleNameInInput("dialogue-participants", name);
    if (valueOf("dialogue-mode", "observe") === "act" && el("dialogue-controlled")) {
      setValue("dialogue-controlled", name);
    }
    updateCharacterPillState();
    publishChatSetupState("chat-setup-participant-toggled");
  },
  setControlledCharacter(value) {
    setValue("dialogue-controlled", value);
    publishChatSetupState("chat-setup-controlled-updated");
  },
  setOpeningPresetId(cardId) {
    const select = el("dialogue-opening-preset");
    if (select) {
      select.value = cardId;
    }
    syncSelectedOpeningPresetFromSelect();
  },
  applyOpeningPreset() {
    return handleApplyOpeningPreset({ preventDefault() {} });
  },
  applyOpeningPresetAndSubmit() {
    return handleStartOpeningPreset({ preventDefault() {} });
  },
  setSceneCardId(cardId) {
    const select = el("dialogue-scene-card");
    if (select) {
      select.value = cardId;
      syncCustomSelect("dialogue-scene-card");
    }
    syncSelectedSceneCardFromSelect();
  },
  setSelfCardId(cardId) {
    const select = el("dialogue-self-card");
    if (select) {
      select.value = cardId;
      syncCustomSelect("dialogue-self-card");
    }
    syncSelectedSelfCardFromSelect();
  },
  setSelfProfileField(field, value) {
    const idMap = {
      display_name: "dialogue-self-name",
      scene_identity: "dialogue-self-identity",
      interaction_style: "dialogue-self-style",
    };
    const id = idMap[field] || "";
    if (id) setValue(id, value);
    publishChatSetupState("chat-setup-self-profile-updated");
  },
  submit() {
    return handleDialogueSessionSubmit({ preventDefault() {} });
  },
  openNewOpeningPreset() {
    return openNewOpeningPreset();
  },
  editCurrentOpeningPreset() {
    return openExistingOpeningPreset();
  },
  openNewSceneCard() {
    return openNewSceneCard();
  },
  editCurrentSceneCard() {
    return selectedSceneCardId ? openExistingSceneCard(selectedSceneCardId) : openNewSceneCard();
  },
  recommendSceneCard() {
    return handleRecommendSceneCard({ preventDefault() {} });
  },
  openNewSelfCard() {
    return openNewSelfCard();
  },
  editCurrentSelfCard() {
    return selectedSelfCardId ? openExistingSelfCard(selectedSelfCardId) : openNewSelfCard();
  },
};

const composerActions = {
  send(message = "", kind = "") {
    return handleSendTurn(message, kind);
  },
  suggest() {
    return handleSuggestTurn();
  },
  setKind(kind) {
    setDialogueMessageKind(kind);
  },
  setDraft(value, options = {}) {
    setComposerDraft(value, options);
  },
  quickReply(value) {
    return applyQuickReply(value);
  },
};

if (typeof UI_BRIDGE_TOOLS.mergeLegacyActionBridge === "function") {
  UI_BRIDGE_TOOLS.mergeLegacyActionBridge("__ZAOMENG_CHAT_SETUP_ACTIONS__", chatSetupActions);
  UI_BRIDGE_TOOLS.mergeLegacyActionBridge("__ZAOMENG_COMPOSER_ACTIONS__", composerActions);
} else {
  window.__ZAOMENG_CHAT_SETUP_ACTIONS__ = chatSetupActions;
  window.__ZAOMENG_COMPOSER_ACTIONS__ = composerActions;
}
window.handleSuggestTurn = handleSuggestTurn;
window.applyQuickReply = applyQuickReply;
window.syncSuggestButtonVisibility = syncSuggestButtonVisibility;
syncSuggestButtonVisibility(null);
console.log("[zaomeng web] main.js loaded", window.__ZAOMENG_WEB_UI_VERSION__ || "unknown");
boot();
window.applyRunViewSafely = applyRunViewSafely;
window.readNamedActionBridge = readNamedActionBridge;
window.characterOverviewActions = characterOverviewActions;
window.openCharacterOverviewViaBridge = openCharacterOverviewViaBridge;
window.openCharacterOverviewIncrementalDistillViaBridge = openCharacterOverviewIncrementalDistillViaBridge;
window.openCharacterOverviewSessionModeViaBridge = openCharacterOverviewSessionModeViaBridge;
window.openCurrentCharacterProfileFileViaBridge = openCurrentCharacterProfileFileViaBridge;
window.openWorkSummaryExportFallback = openWorkSummaryExportFallback;
window.openWorkTimelineFallback = openWorkTimelineFallback;
window.buildChatSetupState = buildChatSetupState;
window.publishChatSetupState = publishChatSetupState;
window.syncModeFields = syncModeFields;
window.handleModelSettingsSubmit = handleModelSettingsSubmit;
window.handleCreateRunSubmit = handleCreateRunSubmit;
window.handleRedistill = handleRedistill;
window.handleRedistillRecommend = handleRedistillRecommend;
window.handleStopRun = handleStopRun;
window.handleRedistillAdd = handleRedistillAdd;
window.handleRedistillRefresh = handleRedistillRefresh;
window.handleDialogueSessionSubmit = handleDialogueSessionSubmit;
window.sceneCardFieldId = sceneCardFieldId;
window.collectSceneCardPayload = collectSceneCardPayload;
window.validateSceneCardPayload = validateSceneCardPayload;
window.fillSceneCardFields = fillSceneCardFields;
window.buildSceneCardEditorState = buildSceneCardEditorState;
window.publishSceneCardEditorState = publishSceneCardEditorState;
window.updateSceneCardDeleteButton = updateSceneCardDeleteButton;
window.startSceneCardDraft = startSceneCardDraft;
window.openNewSceneCard = openNewSceneCard;
window.openExistingSceneCard = openExistingSceneCard;
window.renderSceneCardOptions = renderSceneCardOptions;
window.loadSceneCards = loadSceneCards;
window.syncSelectedSceneCardFromSelect = syncSelectedSceneCardFromSelect;
window.renderSelectedSceneCardPreview = renderSelectedSceneCardPreview;
window.handleSceneCardSelectionChange = handleSceneCardSelectionChange;
window.handleOpenNewSceneCard = handleOpenNewSceneCard;
window.handleEditCurrentSceneCard = handleEditCurrentSceneCard;
window.handleGenerateSceneCard = handleGenerateSceneCard;
window.handleDuplicateSceneCard = handleDuplicateSceneCard;
window.handleSceneCardSubmit = handleSceneCardSubmit;
window.handleDeleteSceneCard = handleDeleteSceneCard;
window.renderDialogueSceneSwitcher = renderDialogueSceneSwitcher;
window.handleApplyDialogueSceneCard = handleApplyDialogueSceneCard;
window.handleRecommendDialogueSceneCard = handleRecommendDialogueSceneCard;
window.applyDialogueSceneTimelineEntry = applyDialogueSceneTimelineEntry;
window.branchDialogueSessionFromScene = branchDialogueSessionFromScene;
window.handleRecommendSceneCard = handleRecommendSceneCard;
window.selfCardFieldId = selfCardFieldId;
window.collectSelfCardPayload = collectSelfCardPayload;
window.validateSelfCardPayload = validateSelfCardPayload;
window.fillSelfCardFields = fillSelfCardFields;
window.buildSelfCardEditorState = buildSelfCardEditorState;
window.publishSelfCardEditorState = publishSelfCardEditorState;
window.updateSelfCardDeleteButton = updateSelfCardDeleteButton;
window.startSelfCardDraft = startSelfCardDraft;
window.openNewSelfCard = openNewSelfCard;
window.openExistingSelfCard = openExistingSelfCard;
window.renderSelfCardOptions = renderSelfCardOptions;
window.loadSelfCards = loadSelfCards;
window.syncSelectedSelfCardFromSelect = syncSelectedSelfCardFromSelect;
window.renderSelectedSelfCardPreview = renderSelectedSelfCardPreview;
window.handleSelfCardSelectionChange = handleSelfCardSelectionChange;
window.handleOpenNewSelfCard = handleOpenNewSelfCard;
window.handleEditCurrentSelfCard = handleEditCurrentSelfCard;
window.handleGenerateSelfCard = handleGenerateSelfCard;
window.handleSelfCardSubmit = handleSelfCardSubmit;
window.handleDeleteSelfCard = handleDeleteSelfCard;
window.openPersonaReviewForCharacter = openPersonaReviewForCharacter;
window.openPersonaReview = openPersonaReview;
window.openWorkCharacterReview = openWorkCharacterReview;
window.openQuickDialogueMode = openQuickDialogueMode;
window.handlePersonaCharacterChange = handlePersonaCharacterChange;
window.collectPersonaReviewPayload = collectPersonaReviewPayload;
window.handlePersonaFieldAutofill = handlePersonaFieldAutofill;
window.handlePersonaReviewSubmit = handlePersonaReviewSubmit;
window.openRelationDetails = openRelationDetails;
window.renderBuiltinNovelList = renderBuiltinNovelList;
window.loadBuiltinNovels = loadBuiltinNovels;
window.handleOpenBuiltinNovelModal = handleOpenBuiltinNovelModal;
window.handleCloneBuiltinNovel = handleCloneBuiltinNovel;
window.triggerImportRunPackage = triggerImportRunPackage;
window.handleImportRunPackage = handleImportRunPackage;
window.isRunPackageExportPending = isRunPackageExportPending;
window.handleExportRunPackage = handleExportRunPackage;
window.openAppUpdateModal = openAppUpdateModal;
window.closeAppUpdateModal = closeAppUpdateModal;
window.appUpdateDismissKey = appUpdateDismissKey;
window.rememberDismissedAppUpdate = rememberDismissedAppUpdate;
window.wasAppUpdateDismissed = wasAppUpdateDismissed;
window.clearAppUpdatePolling = clearAppUpdatePolling;
window.renderAppUpdateStatus = renderAppUpdateStatus;
window.fetchAppUpdateStatus = fetchAppUpdateStatus;
window.scheduleAppUpdatePolling = scheduleAppUpdatePolling;
window.checkAppUpdateOnBoot = checkAppUpdateOnBoot;
window.dismissAppUpdateModal = dismissAppUpdateModal;
window.handleConfirmAppUpdate = handleConfirmAppUpdate;
window.buildComposerUiState = buildComposerUiState;
window.publishComposerUiState = publishComposerUiState;
window.normalizeDialogueMessageKind = normalizeDialogueMessageKind;
window.readDialogueMessageKind = readDialogueMessageKind;
window.updateDialogueMessagePlaceholder = updateDialogueMessagePlaceholder;
window.setDialogueMessageKind = setDialogueMessageKind;
window.setQuickRepliesEnabled = setQuickRepliesEnabled;
window.syncSuggestButtonVisibility = syncSuggestButtonVisibility;
window.setComposerWaiting = setComposerWaiting;
window.setSuggestingState = setSuggestingState;
window.renderObserveQuickReplies = renderObserveQuickReplies;
window.applyQuickReply = applyQuickReply;
window.setComposerDraft = setComposerDraft;
window.coerceMessageOverride = coerceMessageOverride;
window.handleSendTurn = handleSendTurn;
window.handleSuggestTurn = handleSuggestTurn;
window.bindEvents = bindEvents;
window.boot = boot;
window.__ZAOMENG_MAIN_MODULE__ = {
  initialized: true,
  version: String(window.__ZAOMENG_WEB_UI_VERSION__ || ""),
};
})();

