async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function textToBase64(text) {
  const bytes = new TextEncoder().encode(String(text || ""));
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

var currentRunId = "";
var currentRun = null;
var currentDialogueSessionId = "";
var currentDialogueSession = null;
var modelSettings = { configured: false, provider: "", model: "", base_url: "", max_tokens: 0, api_key_configured: false };
var runCreationPending = false;
var runPollTimer = null;
var chatSetupPrefilledForRunId = "";
var sidebarCollapsed = false;
var sessionBooting = false;
var workflowBootPending = true;
var recentSessionsRequestId = 0;
var recentSessionsCache = [];
var recentSessionSnippets = new Map();
var allRuns = [];
var chatModePickerOpen = false;
var newRunFlowOpen = false;
var redistillPanelOpen = false;
var sourceHistoryExpanded = false;
var characterReadinessExpanded = false;
var workSessionPreviewExpanded = false;
var characterOverviewOpen = false;
var currentCharacterOverview = null;
var currentPersonaReview = null;
var currentPersonaAutofill = null;
var currentRelationDetails = null;
var currentSelfCardEditor = null;
var selfCards = [];
var currentSelfCard = null;
var selectedSelfCardId = "";
var samplingSuggestion = null;
var redistillSuggestionState = {
  runId: "",
  character: "",
  sourceName: "",
  weakFieldLabels: [],
  items: [],
  selectedSegmentId: "",
  loading: false,
};
const DISTILL_CHUNK_MAX_CHARS = 9000;
const DISTILL_CHUNK_MAX_SENTENCES = 70;
const RELATION_CHUNK_MAX_CHARS = 4800;
const RELATION_CHUNK_MAX_SENTENCES = 36;

function getLegacyBridge() {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  if (!bridge || typeof bridge.publish !== "function") {
    return null;
  }
  return bridge;
}

function readLegacyActionBridge(name) {
  const key = String(name || "").trim();
  if (!key) return {};
  const value = window[key];
  return value && typeof value === "object" ? value : {};
}

function mergeLegacyActionBridge(name, actions = {}) {
  const key = String(name || "").trim();
  if (!key) return {};
  const nextValue = {
    ...readLegacyActionBridge(key),
    ...(actions && typeof actions === "object" ? actions : {}),
  };
  window[key] = nextValue;
  return nextValue;
}

function buildLegacyUiStateSnapshot(overrides = {}) {
  return {
    currentRunId,
    currentRun,
    allRuns,
    currentDialogueSessionId,
    currentDialogueSession,
    modelSettings,
    currentCharacterOverview,
    currentPersonaReview,
    currentPersonaAutofill,
    currentRelationDetails,
    currentSelfCardEditor,
    selfCards,
    currentSelfCard,
    selectedSelfCardId,
    redistillSuggestionState,
    redistillDraft: buildRedistillDraftState(),
    chatSetup: typeof window.__ZAOMENG_BUILD_CHAT_SETUP_STATE__ === "function" ? window.__ZAOMENG_BUILD_CHAT_SETUP_STATE__() : {},
    composer: typeof window.__ZAOMENG_BUILD_COMPOSER_STATE__ === "function" ? window.__ZAOMENG_BUILD_COMPOSER_STATE__() : {},
    workflow: window.__ZAOMENG_WORKFLOW_STATE__ || {},
    ...overrides,
  };
}

function publishLegacyUiState(source = "legacy", overrides = {}) {
  const bridge = getLegacyBridge();
  if (!bridge) {
    return;
  }
  bridge.publish(buildLegacyUiStateSnapshot(overrides), source);
}

function publishLegacyStateSlice(source, key, value) {
  const name = String(key || "").trim();
  if (!name) return;
  publishLegacyUiState(source, { [name]: value });
}

window.__ZAOMENG_UI_BRIDGE_TOOLS__ = {
  readLegacyActionBridge,
  mergeLegacyActionBridge,
  publishLegacyStateSlice,
};

function el(id) {
  return document.getElementById(id);
}

function bind(id, eventName, handler) {
  const node = el(id);
  if (node) {
    node.addEventListener(eventName, handler);
  }
}

function setText(id, value, fallback = "-") {
  const node = el(id);
  if (!node) return;
  node.textContent = value || fallback;
}

function setStatus(id, value = "") {
  const node = el(id);
  if (!node) return;
  node.textContent = value;
}

function setValue(id, value = "") {
  const node = el(id);
  if (!node) return null;
  node.value = value;
  return node;
}

function valueOf(id, fallback = "") {
  return el(id)?.value ?? fallback;
}

function trimmedValue(id, fallback = "") {
  return String(valueOf(id, fallback)).trim();
}

function numberValue(id, fallback) {
  return Number(valueOf(id, fallback));
}

function charactersOf(id) {
  return parseCharacters(valueOf(id, ""));
}

function setSessionBadge(text) {
  setText("dialogue-session-id", text, "");
}

function toggle(id, visible) {
  const node = el(id);
  if (!node) return;
  node.classList.toggle("hidden", !visible);
}

function uniq(values) {
  return [...new Set((values || []).map((item) => String(item || "").trim()).filter(Boolean))];
}

function joinCharacters(values) {
  return uniq(values).join("、");
}

function parseCharacters(value) {
  return uniq(String(value || "").split(/[\n,，、]+/));
}

function sessionSnippetKey(runId, sessionId) {
  return `${String(runId || "").trim()}::${String(sessionId || "").trim()}`;
}

function rememberRecentSessionSnippet(runId, sessionId, message) {
  const key = sessionSnippetKey(runId, sessionId);
  const text = String(message || "").trim();
  if (!key || !text) return;
  recentSessionSnippets.set(key, text);
}

function readRecentSessionSnippet(runId, sessionId) {
  const key = sessionSnippetKey(runId, sessionId);
  if (!key) return "";
  return String(recentSessionSnippets.get(key) || "").trim();
}

function applySidebarState() {
  const shell = el("app-shell");
  if (shell) {
    shell.classList.toggle("sidebar-collapsed", sidebarCollapsed);
  }
  const experienceShell = el("experience-shell");
  if (experienceShell) {
    experienceShell.classList.toggle("sidebar-collapsed", sidebarCollapsed);
  }
  const button = el("toggle-sidebar-button");
  if (button) {
    const label = sidebarCollapsed ? "展开侧栏" : "收起侧栏";
    button.textContent = label;
    button.setAttribute("aria-label", label);
    button.title = label;
  }
}

function normalizeNovelTitle(value) {
  return String(value || "")
    .trim()
    .replace(/\.(txt|md|text|epub)$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function runNovelTitle(run) {
  return normalizeNovelTitle(run?.novel_id || run?.novel_name || "") || "未命名书卷";
}

function stopRunPolling() {
  if (runPollTimer) {
    clearTimeout(runPollTimer);
    runPollTimer = null;
  }
}

function syncViewportHeightVar() {
  document.documentElement.style.setProperty("--viewport-height", `${window.innerHeight}px`);
}

function resizeComposer() {
  const area = el("dialogue-message");
  if (!area) return;
  area.style.height = "auto";
  area.style.height = `${Math.min(area.scrollHeight, 160)}px`;
}

function setComposerEnabled(enabled) {
  const area = el("dialogue-message");
  const sendButton = el("prepare-turn-button");
  const suggestButton = el("suggest-turn-button");
  if (area) area.disabled = !enabled;
  if (sendButton) sendButton.disabled = !enabled;
  if (suggestButton) suggestButton.disabled = !enabled;
}

function updatePillState(rootSelector, values) {
  const selected = new Set(values);
  document.querySelectorAll(`${rootSelector} .pill`).forEach((node) => {
    node.classList.toggle("active", selected.has(node.textContent || ""));
  });
}

function syncChoiceGroup(rootId, inputId) {
  const root = el(rootId);
  if (!root) return;
  const value = valueOf(inputId, "");
  root.querySelectorAll("[data-value]").forEach((node) => {
    node.classList.toggle("active", node.getAttribute("data-value") === value);
  });
}

function bindChoiceGroup(rootId, inputId, onChange) {
  const root = el(rootId);
  if (!root) return;
  root.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const button = target.closest("[data-value]");
    if (!(button instanceof HTMLElement)) return;
    event.preventDefault();
    setValue(inputId, button.getAttribute("data-value") || "");
    syncChoiceGroup(rootId, inputId);
    if (typeof onChange === "function") onChange();
  });
}

function updateNovelFileView() {
  const file = el("novel-file")?.files?.[0];
  setText("novel-file-name", file?.name || "还没有放入书页", "");
  setText("novel-file-hint", file ? "书页已经放好，可以继续点亮人物。" : "支持 txt / md / text / epub", "");
  applySamplingHint(file).catch((error) => {
    console.warn("sampling suggestion failed", error);
    samplingSuggestion = null;
    setText("sampling-hint", file ? "这份书页暂时无法估算体量，先沿用默认取样。" : "选好正文后，这里会按体量自动给出建议。", "");
    setText("sampling-estimate", file ? "预计轮次、调用次数和耗时粗估暂时不可用。" : "长篇会自动分批蒸馏，这里会显示预计轮次、调用次数和粗估耗时。", "");
  });
}

function closeCustomSelect(selectId) {
  const root = el(`${selectId}-select`);
  const trigger = el(`${selectId}-trigger`);
  const menu = el(`${selectId}-menu`);
  if (!root || !trigger || !menu) return;
  root.classList.remove("open");
  menu.classList.add("hidden");
  trigger.setAttribute("aria-expanded", "false");
}

function syncCustomSelect(selectId) {
  const select = el(selectId);
  const root = el(`${selectId}-select`);
  const trigger = el(`${selectId}-trigger`);
  const menu = el(`${selectId}-menu`);
  if (!(select instanceof HTMLSelectElement) || !root || !trigger || !menu) return;
  const label = trigger.querySelector(".custom-select-label");

  const options = Array.from(select.options);
  const current = options.find((option) => option.value === select.value) || options[0] || null;
  if (label) {
    label.textContent = current?.textContent?.trim() || "请选择";
  }
  menu.innerHTML = "";

  options.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "custom-select-option";
    if (option.value === select.value) {
      button.classList.add("active");
    }
    button.textContent = option.textContent || option.value;
    button.setAttribute("data-value", option.value);
    button.addEventListener("click", () => {
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      syncCustomSelect(selectId);
      closeCustomSelect(selectId);
    });
    menu.appendChild(button);
  });
}

function initCustomSelect(selectId) {
  const select = el(selectId);
  const root = el(`${selectId}-select`);
  const trigger = el(`${selectId}-trigger`);
  const menu = el(`${selectId}-menu`);
  if (!(select instanceof HTMLSelectElement) || !root || !trigger || !menu) return;
  if (root.dataset.bound === "true") {
    syncCustomSelect(selectId);
    return;
  }
  root.dataset.bound = "true";
  syncCustomSelect(selectId);
  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    const opening = menu.classList.contains("hidden");
    document.querySelectorAll(".custom-select.open").forEach((node) => {
      const currentId = node.id.replace(/-select$/, "");
      closeCustomSelect(currentId);
    });
    if (!opening) {
      return;
    }
    root.classList.add("open");
    menu.classList.remove("hidden");
    trigger.setAttribute("aria-expanded", "true");
  });
  select.addEventListener("change", () => syncCustomSelect(selectId));
}

function updateRedistillFileView() {
  const file = el("redistill-novel-file")?.files?.[0];
  const selected = getSelectedRedistillSegment();
  const activeName = file?.name || (selected ? `${selected.character || redistillSuggestionState.character}-推荐片段.txt` : "沿用当前书段");
  setText("redistill-file-name", activeName, "");
  setText(
    "redistill-file-hint",
    file
      ? "新的书段已经放好，这一轮会基于它继续整理人物。"
      : selected
        ? "当前会直接使用所选推荐片段继续增量蒸馏。"
        : "如果这是连载的新章节，就在这里换入新的正文片段",
    ""
  );
  if (file) {
    redistillSuggestionState.selectedSegmentId = "";
    renderRedistillRecommendationState();
    setText("redistill-plan-title", "这轮会换入新的书段继续整理", "");
    setText("redistill-source-note", `当前准备换入新的正文片段：${file.name}`, "");
  } else if (selected) {
    setText("redistill-plan-title", "这轮会使用推荐片段继续整理", "");
    setText(
      "redistill-source-note",
      `当前准备切到推荐片段：${selected.reason || "更适合补稳目标字段"}${redistillSuggestionState.sourceName ? ` · 来源 ${redistillSuggestionState.sourceName}` : ""}`,
      ""
    );
  } else if (currentRun) {
    renderRedistillPlan(currentRun);
    syncRedistillPreview();
  }
  syncRedistillRecommendationState();
  publishLegacyUiState("redistill-file-view-updated");
}

async function applySamplingHint(file) {
  if (!file) {
    samplingSuggestion = null;
    setText("sampling-hint", "选好正文后，这里会按体量自动给出建议。", "");
    setText("sampling-estimate", "长篇会自动分批蒸馏，这里会显示预计轮次、调用次数和粗估耗时。", "");
    return;
  }
  if (!/\.(txt|md|text)$/i.test(file.name)) {
    samplingSuggestion = null;
    setText("sampling-hint", "这份书页会先沿用当前默认取样；txt / md 可以自动估算更合适的范围。", "");
    setText("sampling-estimate", "如需看到预计轮次、调用次数和耗时粗估，建议优先上传 txt / md。", "");
    return;
  }
  const text = await readTextFileBestEffort(file);
  const suggestion = suggestSamplingFromText(text);
  samplingSuggestion = suggestion;
  setValue("max-sentences", String(suggestion.maxSentences));
  setValue("max-chars", String(suggestion.maxChars));
  setText(
    "sampling-hint",
    `已按这份正文体量建议：约 ${suggestion.maxSentences} 句 / ${suggestion.maxChars} 字。${suggestion.note}`,
    ""
  );
  refreshSamplingHintEstimate();
}

async function readTextFileBestEffort(file) {
  const buffer = await file.arrayBuffer();
  const encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk"];
  for (const encoding of encodings) {
    try {
      return new TextDecoder(encoding, { fatal: true }).decode(buffer);
    } catch (_error) {
      continue;
    }
  }
  return new TextDecoder("utf-8").decode(buffer);
}

function suggestSamplingFromText(text) {
  const plain = String(text || "").replace(/\r\n/g, "\n").trim();
  const charCount = plain.length;
  const sentenceCount = plain ? plain.split(/[。！？!?；;\n]+/).map((item) => item.trim()).filter(Boolean).length : 0;

  let maxChars = 50000;
  if (charCount > 0 && charCount <= 50000) {
    maxChars = Math.max(2000, roundToStep(charCount, 1000));
  } else if (charCount > 50000) {
    maxChars = Math.min(120000, roundToStep(Math.max(50000, Math.round(charCount * 0.38)), 5000));
  }

  let maxSentences = 120;
  if (sentenceCount > 0 && sentenceCount <= 120) {
    maxSentences = Math.max(20, sentenceCount);
  } else if (sentenceCount > 120) {
    maxSentences = Math.min(300, roundToStep(Math.max(120, Math.round(sentenceCount * 0.32)), 10));
  }

  const note =
    charCount <= 50000
      ? "这份正文不算太长，会尽量吃全。"
      : "这份正文较长，会自动留出跨章节取样空间。";

  return { charCount, sentenceCount, maxChars, maxSentences, note };
}

function refreshSamplingHintEstimate() {
  if (!samplingSuggestion) {
    setText("sampling-estimate", "长篇会自动分批蒸馏，这里会显示预计轮次、调用次数和粗估耗时。", "");
    return;
  }
  const characterCount = Math.max(1, charactersOf("characters").length || 1);
  const maxSentences = Math.max(20, numberValue("max-sentences", samplingSuggestion.maxSentences || 120));
  const maxChars = Math.max(2000, numberValue("max-chars", samplingSuggestion.maxChars || 50000));
  const estimate = estimateSamplingPlan(samplingSuggestion, {
    characterCount,
    maxSentences,
    maxChars,
  });
  const distillCopy =
    estimate.distillChunkCount > 1
      ? `预计每个角色 ${estimate.distillChunkCount} 块，含汇总约 ${estimate.distillCallsPerCharacter} 轮`
      : "预计每个角色 1 轮";
  const relationCopy =
    estimate.relationChunkCount > 1
      ? `关系约 ${estimate.relationChunkCount} 块，含汇总约 ${estimate.relationCalls} 轮`
      : "关系约 1 轮";
  setText(
    "sampling-estimate",
    `按当前体量与人数粗估：人物 ${distillCopy}，约 ${formatDurationRange(
      estimate.distillTimeLowSeconds,
      estimate.distillTimeHighSeconds
    )}；${relationCopy}，约 ${formatDurationRange(
      estimate.relationTimeLowSeconds,
      estimate.relationTimeHighSeconds
    )}；总计约 ${estimate.totalCalls} 次模型调用，约 ${formatCompactTokenRange(
      estimate.tokenLow,
      estimate.tokenHigh
    )} tokens，整体约 ${formatDurationRange(estimate.timeLowSeconds, estimate.timeHighSeconds)}。`,
    ""
  );
}

function estimateSamplingPlan(suggestion, { characterCount, maxSentences, maxChars }) {
  const effectiveChars = Math.max(1, Math.min(Number(suggestion?.charCount || maxChars || 0), Number(maxChars || 0) || 0) || Number(maxChars || 0));
  const effectiveSentences =
    Math.max(1, Math.min(Number(suggestion?.sentenceCount || maxSentences || 0), Number(maxSentences || 0) || 0) || Number(maxSentences || 0));
  const distillChunkCount = estimateChunkCount(effectiveChars, effectiveSentences, DISTILL_CHUNK_MAX_CHARS, DISTILL_CHUNK_MAX_SENTENCES);
  const relationChars = Math.min(effectiveChars, 12000);
  const relationSentences = Math.min(effectiveSentences, 80);
  const relationChunkCount = estimateChunkCount(relationChars, relationSentences, RELATION_CHUNK_MAX_CHARS, RELATION_CHUNK_MAX_SENTENCES);
  const distillCallsPerCharacter = distillChunkCount > 1 ? distillChunkCount + 1 : 1;
  const relationCalls = relationChunkCount > 1 ? relationChunkCount + 1 : 1;
  const totalCalls = characterCount * distillCallsPerCharacter + relationCalls;
  const distillTokensPerCharacter = estimateTokenBudget(effectiveChars, distillChunkCount, "distill");
  const relationTokens = estimateTokenBudget(relationChars, relationChunkCount, "relation");
  const totalTokens = characterCount * distillTokensPerCharacter + relationTokens;
  const timeEstimate = estimateSamplingTime({
    characterCount,
    distillChunkCount,
    relationChunkCount,
  });
  return {
    effectiveChars,
    effectiveSentences,
    distillChunkCount,
    relationChunkCount,
    distillCallsPerCharacter,
    relationCalls,
    totalCalls,
    tokenLow: roundToStep(totalTokens * 0.82, 500),
    tokenHigh: roundToStep(totalTokens * 1.18, 500),
    distillTimeLowSeconds: timeEstimate.distillLowSeconds,
    distillTimeHighSeconds: timeEstimate.distillHighSeconds,
    relationTimeLowSeconds: timeEstimate.relationLowSeconds,
    relationTimeHighSeconds: timeEstimate.relationHighSeconds,
    timeLowSeconds: timeEstimate.lowSeconds,
    timeHighSeconds: timeEstimate.highSeconds,
  };
}

function estimateChunkCount(chars, sentences, chunkChars, chunkSentences) {
  const byChars = Math.max(1, Math.ceil(Number(chars || 0) / chunkChars));
  const bySentences = Math.max(1, Math.ceil(Number(sentences || 0) / chunkSentences));
  return Math.max(1, byChars, bySentences);
}

function estimateTokenBudget(chars, chunkCount, mode) {
  const charTokens = Math.round(Number(chars || 0) * 1.1);
  const base = mode === "distill" ? 1800 : 1200;
  if (chunkCount <= 1) {
    return charTokens + base;
  }
  const chunkOverhead = mode === "distill" ? chunkCount * 700 + 1100 : chunkCount * 500 + 900;
  return charTokens + base + chunkOverhead;
}

function estimateSamplingTime({ characterCount, distillChunkCount, relationChunkCount }) {
  const parallelWorkers = distillChunkCount >= 6 ? 6 : distillChunkCount >= 4 ? 4 : distillChunkCount >= 2 ? 2 : 1;
  const distillLowPerCharacter =
    distillChunkCount > 1
      ? Math.ceil(distillChunkCount / parallelWorkers) * 22 + 28
      : 35;
  const distillHighPerCharacter =
    distillChunkCount > 1
      ? Math.ceil(distillChunkCount / parallelWorkers) * 42 + 55
      : 70;
  const relationLow =
    relationChunkCount > 1
      ? Math.ceil(relationChunkCount / parallelWorkers) * 14 + 18
      : 24;
  const relationHigh =
    relationChunkCount > 1
      ? Math.ceil(relationChunkCount / parallelWorkers) * 28 + 38
      : 48;
  const materializeLow = Math.max(4, characterCount * 3);
  const materializeHigh = Math.max(8, characterCount * 7);
  const distillLowSeconds = characterCount * distillLowPerCharacter + materializeLow;
  const distillHighSeconds = characterCount * distillHighPerCharacter + materializeHigh;
  const relationLowSeconds = relationLow;
  const relationHighSeconds = relationHigh;
  const lowSeconds = distillLowSeconds + relationLowSeconds;
  const highSeconds = distillHighSeconds + relationHighSeconds;
  return {
    distillLowSeconds: roundToStep(distillLowSeconds, 5),
    distillHighSeconds: roundToStep(distillHighSeconds, 10),
    relationLowSeconds: roundToStep(relationLowSeconds, 5),
    relationHighSeconds: roundToStep(relationHighSeconds, 10),
    lowSeconds: roundToStep(lowSeconds, 5),
    highSeconds: roundToStep(highSeconds, 10),
  };
}

function formatDurationRange(lowSeconds, highSeconds) {
  return `${formatDurationCompact(lowSeconds)}-${formatDurationCompact(highSeconds)}`;
}

function formatDurationCompact(seconds) {
  const total = Math.max(0, Math.round(Number(seconds || 0)));
  const minutes = Math.floor(total / 60);
  const remain = total % 60;
  if (minutes <= 0) {
    return `${remain}秒`;
  }
  if (remain === 0) {
    return `${minutes}分钟`;
  }
  if (minutes >= 10) {
    return `${minutes}分钟`;
  }
  return `${minutes}分${remain}秒`;
}

function formatCompactTokenRange(low, high) {
  const minValue = Math.max(0, Math.round(Number(low || 0)));
  const maxValue = Math.max(minValue, Math.round(Number(high || 0)));
  return `${formatCompactNumber(minValue)}-${formatCompactNumber(maxValue)}`;
}

function roundToStep(value, step) {
  const amount = Number(value || 0);
  const unit = Number(step || 1);
  if (!Number.isFinite(amount) || !Number.isFinite(unit) || unit <= 0) return 0;
  return Math.max(unit, Math.round(amount / unit) * unit);
}

function ensureConnectionDetailsVisible() {
  const details = el("connection-details");
  if (details) {
    details.classList.remove("hidden");
  }
}

function toggleNameInInput(inputId, name) {
  const values = charactersOf(inputId);
  const nextValues = values.includes(name) ? values.filter((item) => item !== name) : [...values, name];
  setValue(inputId, joinCharacters(nextValues));
  return nextValues;
}

function maybePrefillChatSetup(run) {
  if (!run || !run.run_id) return;
  if (chatSetupPrefilledForRunId === run.run_id) return;
  const characters = run.artifact_index?.characters?.map((item) => item.name).filter(Boolean) || run.locked_characters || [];
  if (!characters.length) return;

  setValue("dialogue-participants", joinCharacters(characters));
  setValue("dialogue-mode", "insert");
  setValue("dialogue-controlled", characters[0] || "");
  if (el("dialogue-self-name") && !el("dialogue-self-name").value.trim()) setValue("dialogue-self-name", "你");
  if (el("dialogue-self-identity") && !el("dialogue-self-identity").value.trim()) {
    setValue("dialogue-self-identity", "误入此间的来客");
  }
  if (el("dialogue-self-style") && !el("dialogue-self-style").value.trim()) {
    setValue("dialogue-self-style", "自然进入场景");
  }

  chatSetupPrefilledForRunId = run.run_id;
  syncModeFields();
  updateCharacterPillState();
  if (typeof publishChatSetupState === "function") {
    publishChatSetupState("chat-setup-prefilled");
  }
}

function getRunCharacterNames(run) {
  return run?.artifact_index?.characters?.map((item) => item.name).filter(Boolean) || run?.locked_characters || [];
}

function renderCharacterPills(run) {
  const root = el("dialogue-character-pills");
  if (!root) return;
  const characters = getRunCharacterNames(run);
  root.innerHTML = "";
  characters.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pill";
    button.textContent = name;
    button.addEventListener("click", () => {
      toggleNameInInput("dialogue-participants", name);
      if (valueOf("dialogue-mode", "observe") === "act" && el("dialogue-controlled")) {
        setValue("dialogue-controlled", name);
      }
      updateCharacterPillState();
      if (typeof publishChatSetupState === "function") {
        publishChatSetupState("chat-setup-pill-clicked");
      }
    });
    root.appendChild(button);
  });
  updateCharacterPillState();
}

function updateCharacterPillState() {
  updatePillState("#dialogue-character-pills", charactersOf("dialogue-participants"));
  if (typeof publishChatSetupState === "function") {
    publishChatSetupState("chat-setup-pill-state-updated");
  }
}

function renderRedistillPills(run) {
  const root = el("redistill-character-pills");
  if (!root) return;
  const characters = getRunCharacterNames(run);
  root.innerHTML = "";
  characters.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pill";
    button.textContent = name;
    button.addEventListener("click", () => {
      toggleNameInInput("redistill-characters", name);
      updateRedistillPillState();
    });
    root.appendChild(button);
  });
  root.classList.toggle("hidden", characters.length === 0);
  updateRedistillPillState();
}

function updateRedistillPillState() {
  updatePillState("#redistill-character-pills", charactersOf("redistill-characters"));
  syncRedistillPreview();
  syncRedistillRecommendationState();
  publishLegacyUiState("redistill-pill-state-updated");
}

function syncRedistillPreview() {
  const requested = charactersOf("redistill-characters");
  const existingNames = new Set(getRunCharacterNames(currentRun));
  const existing = requested.filter((name) => existingNames.has(name));
  const newcomers = requested.filter((name) => !existingNames.has(name));
  renderRedistillPlanGroup("redistill-existing-list", existing, "redistill-existing-empty");
  renderRedistillPlanGroup("redistill-new-list", newcomers, "redistill-new-empty");
}

function buildRedistillDraftState() {
  const requestedCharacters = charactersOf("redistill-characters");
  const existingNames = new Set(getRunCharacterNames(currentRun));
  const existingSelectedCharacters = requestedCharacters.filter((name) => existingNames.has(name));
  const newSelectedCharacters = requestedCharacters.filter((name) => !existingNames.has(name));
  const file = el("redistill-novel-file")?.files?.[0] || null;
  const selectedSegment = !file ? getSelectedRedistillSegment() : null;
  return {
    requestedCharacters,
    existingSelectedCharacters,
    newSelectedCharacters,
    fileAttached: Boolean(file),
    fileName: file?.name || "",
    recommendationTarget: !file && requestedCharacters.length === 1 && existingSelectedCharacters.length === 1 ? existingSelectedCharacters[0] : "",
    selectedSegmentId: selectedSegment?.segment_id || "",
    selectedSegment,
    usingSuggestedSegment: Boolean(selectedSegment && !file),
    panelOpen: Boolean(redistillPanelOpen),
  };
}

function getSelectedRedistillSegment() {
  return redistillSuggestionState.items.find((item) => item.segment_id === redistillSuggestionState.selectedSegmentId) || null;
}

function selectRedistillSuggestedSegment(segmentId) {
  const nextId = String(segmentId || "").trim();
  redistillSuggestionState.selectedSegmentId = nextId;
  const target = String(redistillSuggestionState.character || "").trim();
  if (nextId && target) {
    setStatus("redistill-status", `这轮会直接用推荐片段为「${target}」继续增量蒸馏。`);
  }
  updateRedistillFileView();
  renderRedistillRecommendationState(target);
  publishLegacyUiState("redistill-segment-selected");
}

function getRedistillRecommendationTarget() {
  const file = el("redistill-novel-file")?.files?.[0];
  if (file || !currentRunId || !currentRun) {
    return "";
  }
  const requested = charactersOf("redistill-characters");
  const existingNames = new Set(getRunCharacterNames(currentRun));
  const existing = requested.filter((name) => existingNames.has(name));
  return existing.length === 1 && requested.length === 1 ? existing[0] : "";
}

function resetRedistillRecommendationState() {
  redistillSuggestionState = {
    runId: currentRunId || "",
    character: "",
    sourceName: "",
    weakFieldLabels: [],
    items: [],
    selectedSegmentId: "",
    loading: false,
  };
}

function syncRedistillRecommendationState() {
  if (redistillSuggestionState.runId && redistillSuggestionState.runId !== currentRunId) {
    resetRedistillRecommendationState();
  }
  const target = getRedistillRecommendationTarget();
  const file = el("redistill-novel-file")?.files?.[0];
  const shouldShow = Boolean(currentRunId && target && !file);
  toggle("redistill-recommend-shell", shouldShow);
  if (!shouldShow) {
    if (!file) {
      const hadSelectedSegment = Boolean(redistillSuggestionState.selectedSegmentId);
      resetRedistillRecommendationState();
      renderRedistillRecommendationState();
      if (hadSelectedSegment) {
        setText("redistill-file-name", "沿用当前书段", "");
        setText("redistill-file-hint", "如果这是连载的新章节，就在这里换入新的正文片段", "");
        if (currentRun) {
          renderRedistillPlan(currentRun);
          syncRedistillPreview();
        }
      }
    }
    return;
  }
  if (redistillSuggestionState.character && redistillSuggestionState.character !== target) {
    resetRedistillRecommendationState();
  }
  if (!redistillSuggestionState.runId) {
    redistillSuggestionState.runId = currentRunId || "";
  }
  renderRedistillRecommendationState(target);
}

function renderRedistillRecommendationState(targetCharacter = "") {
  const target = String(targetCharacter || redistillSuggestionState.character || getRedistillRecommendationTarget() || "").trim();
  const button = el("redistill-recommend-button");
  const root = el("redistill-recommend-list");
  if (button) {
    button.disabled = redistillSuggestionState.loading || !target;
    button.textContent = redistillSuggestionState.loading ? "正在挑片段..." : "推荐片段";
  }
  if (!root) return;
  root.innerHTML = "";
  if (!target) {
    setText("redistill-recommend-note", "只选中一位已有角色时，这里会给出适合补稳这位角色的正文窗口。", "");
    return;
  }
  if (!redistillSuggestionState.items.length) {
    const weakLabelText =
      Array.isArray(redistillSuggestionState.weakFieldLabels) && redistillSuggestionState.weakFieldLabels.length
        ? `优先盯：${redistillSuggestionState.weakFieldLabels.join("、")}。`
        : "";
    setText(
      "redistill-recommend-note",
      redistillSuggestionState.loading
        ? `正在替「${target}」翻当前书段，找更适合补稳的正文片段...`
        : `只选中「${target}」后，可一键从当前书段里挑推荐片段。${weakLabelText}`,
      ""
    );
    return;
  }
  setText(
    "redistill-recommend-note",
    `当前基于 ${redistillSuggestionState.sourceName || "当前书段"} 为「${target}」挑了 ${redistillSuggestionState.items.length} 段候选正文。`,
    ""
  );
  redistillSuggestionState.items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `redistill-recommend-card${item.segment_id === redistillSuggestionState.selectedSegmentId ? " is-selected" : ""}`;

    const head = document.createElement("div");
    head.className = "redistill-recommend-card-head";
    head.innerHTML = `
      <strong>${escapeHtml(item.preview || "推荐片段")}</strong>
      <small>句段 ${escapeHtml(`${item.start_sentence}-${item.end_sentence}`)} · 分数 ${escapeHtml(String(item.score || 0))}</small>
    `;

    const meta = document.createElement("p");
    meta.className = "redistill-recommend-card-meta";
    meta.textContent = [item.reason, Array.isArray(item.estimated_field_labels) ? `预计能补：${item.estimated_field_labels.join("、")}` : ""]
      .filter(Boolean)
      .join(" · ");

    const actions = document.createElement("div");
    actions.className = "card-actions";
    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = item.segment_id === redistillSuggestionState.selectedSegmentId ? "primary-button" : "soft-button";
    useButton.textContent = item.segment_id === redistillSuggestionState.selectedSegmentId ? "已选这段" : "用这一段";
    useButton.addEventListener("click", () => selectRedistillSuggestedSegment(item.segment_id));
    actions.appendChild(useButton);

    card.appendChild(head);
    if (meta.textContent) {
      card.appendChild(meta);
    }
    card.appendChild(actions);
    root.appendChild(card);
  });
  publishLegacyUiState("redistill-recommendation-rendered");
}

mergeLegacyActionBridge("__ZAOMENG_REDISTILL_ACTIONS__", {
  selectSegment: selectRedistillSuggestedSegment,
});

function humanizeSummary(summary) {
  const mapping = {
    waiting_for_payloads: "书页已备好",
    waiting_for_host_generation: "人物正在显形",
    graph_pending: "关系正在织就",
    graph_ready: "关系图已成",
    waiting_for_verification: "细节正在收束",
    workflow_complete: "已可入场",
    stop_requested: "正在收束当前步骤",
    stopped: "已停止蒸馏",
    failed: "这一轮中断了",
  };
  return mapping[summary] || summary || "未开始";
}

function humanizeRunEventStage(stage) {
  const mapping = {
    characters_locked: "角色已锁定",
    text_loaded: "正文已载入",
    characters_ready: "角色名单就绪",
    distill_payload_ready: "蒸馏任务已就绪",
    relation_payload_ready: "关系任务已就绪",
    drafting_character: "正在蒸馏角色",
    materializing_character: "正在落盘角色",
    chunking_character: "正在分批蒸馏",
    merging_character: "正在汇总角色",
    character_done: "角色蒸馏完成",
    rendering_graph: "正在生成关系图",
    chunking_graph: "正在分批抽取关系",
    merging_graph: "正在汇总关系",
    graph_done: "关系图已生成",
    graph_failed: "关系图生成失败",
    redistill_character_updated: "增量补稳完成",
    persona_review_saved: "人物稿已写回",
    workflow_complete: "这一卷已完成",
    stopped: "已停止",
    stopped_timing: "已停止（含耗时）",
    failed: "已中断",
    failed_timing: "已中断（含耗时）",
  };
  return mapping[stage] || stage || "进展";
}

function humanizeSessionStatus(status) {
  const mapping = {
    ready: "仍可续写",
    waiting_for_host_reply: "正在回望",
  };
  return mapping[status] || status || "未知";
}

function humanizeMode(mode) {
  const mapping = {
    observe: "旁观此局",
    act: "化身书中人",
    insert: "以自己入场",
  };
  return mapping[mode] || mode || "这一幕";
}

function humanizeProvider(provider) {
  const mapping = {
    "openai-compatible": "通用接口",
    openai: "OpenAI",
    anthropic: "Anthropic",
    ollama: "Ollama",
  };
  return mapping[provider] || provider || "未接入";
}

function syncModalScrollLock() {
  const hasVisibleModal = Boolean(document.querySelector(".modal:not(.hidden)"));
  document.documentElement.classList.toggle("modal-open", hasVisibleModal);
  document.body.classList.toggle("modal-open", hasVisibleModal);
}

function findRunById(runId) {
  return allRuns.find((item) => item.run_id === runId) || null;
}

function runSortScore(run) {
  const characterCount = (run?.artifact_index?.characters || []).length;
  const status = String(run?.summary?.status_text || "");
  const statusScore =
    status === "workflow_complete" ? 5 :
    status === "graph_ready" ? 4 :
    status === "waiting_for_verification" ? 3 :
    status === "graph_pending" ? 2 :
    status === "waiting_for_host_generation" ? 1 : 0;
  return statusScore * 100 + characterCount;
}

function aggregateRunsByNovel(runs) {
  const grouped = new Map();
  (runs || []).forEach((run) => {
    const novelId = runNovelTitle(run);
    const current = grouped.get(novelId);
    if (!current) {
      grouped.set(novelId, run);
      return;
    }
    const currentScore = runSortScore(current);
    const nextScore = runSortScore(run);
    if (nextScore > currentScore) {
      grouped.set(novelId, run);
      return;
    }
    if (nextScore === currentScore) {
      const currentUpdated = String(current?.updated_at || "");
      const nextUpdated = String(run?.updated_at || "");
      if (nextUpdated > currentUpdated) {
        grouped.set(novelId, run);
      }
    }
  });
  return [...grouped.values()].sort((a, b) => String(b?.updated_at || "").localeCompare(String(a?.updated_at || "")));
}

function formatWeakTime(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  if (now.toDateString() === date.toDateString()) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function openSettingsModal() {
  ensureConnectionDetailsVisible();
  toggle("settings-modal", true);
  syncModalScrollLock();
}

function closeSettingsModal() {
  toggle("settings-modal", false);
  syncModalScrollLock();
}

function openPersonaReviewModal() {
  toggle("persona-review-modal", true);
  syncModalScrollLock();
}

function closePersonaReviewModal() {
  toggle("persona-review-modal", false);
  syncModalScrollLock();
}

function openRelationDetailsModal() {
  toggle("relation-details-modal", true);
  syncModalScrollLock();
}

function closeRelationDetailsModal() {
  toggle("relation-details-modal", false);
  syncModalScrollLock();
}

function openSelfCardModal() {
  toggle("self-card-modal", true);
  syncModalScrollLock();
  currentSelfCardEditor = typeof window.__ZAOMENG_BUILD_SELF_CARD_EDITOR_STATE__ === "function"
    ? window.__ZAOMENG_BUILD_SELF_CARD_EDITOR_STATE__()
    : currentSelfCardEditor;
  publishLegacyUiState("self-card-modal-opened", { currentSelfCardEditor });
}

function closeSelfCardModal() {
  toggle("self-card-modal", false);
  syncModalScrollLock();
  currentSelfCardEditor = typeof window.__ZAOMENG_BUILD_SELF_CARD_EDITOR_STATE__ === "function"
    ? window.__ZAOMENG_BUILD_SELF_CARD_EDITOR_STATE__()
    : currentSelfCardEditor;
  publishLegacyUiState("self-card-modal-closed", { currentSelfCardEditor });
}

async function apiJson(url, options = {}, fallbackMessage = "请求失败。") {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || fallbackMessage);
  }
  return payload;
}

function syncSidebarSelection() {
  document.querySelectorAll("#sidebar-session-list .session-item").forEach((node) => {
    const runId = node.getAttribute("data-run-id") || "";
    const sessionId = node.getAttribute("data-session-id") || "";
    node.classList.toggle("active", runId === currentRunId && sessionId === currentDialogueSessionId);
  });
}

