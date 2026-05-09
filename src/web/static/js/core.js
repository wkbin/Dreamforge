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
var recentSessionsRequestId = 0;
var allRuns = [];
var chatModePickerOpen = false;
var newRunFlowOpen = false;
var redistillPanelOpen = false;
var sourceHistoryExpanded = false;
var currentPersonaReview = null;
var currentPersonaAutofill = null;
var currentRelationDetails = null;
var selfCards = [];
var currentSelfCard = null;
var selectedSelfCardId = "";
var samplingSuggestion = null;
const DISTILL_CHUNK_MAX_CHARS = 9000;
const DISTILL_CHUNK_MAX_SENTENCES = 70;
const RELATION_CHUNK_MAX_CHARS = 4800;
const RELATION_CHUNK_MAX_SENTENCES = 36;

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
  setText("redistill-file-name", file?.name || "沿用当前书段", "");
  setText(
    "redistill-file-hint",
    file ? "新的书段已经放好，这一轮会基于它继续整理人物。" : "如果这是连载的新章节，就在这里换入新的正文片段",
    ""
  );
  if (file) {
    setText("redistill-plan-title", "这轮会换入新的书段继续整理", "");
    setText("redistill-source-note", `当前准备换入新的正文片段：${file.name}`, "");
  } else if (currentRun) {
    renderRedistillPlan(currentRun);
    syncRedistillPreview();
  }
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
    });
    root.appendChild(button);
  });
  updateCharacterPillState();
}

function updateCharacterPillState() {
  updatePillState("#dialogue-character-pills", charactersOf("dialogue-participants"));
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
}

function syncRedistillPreview() {
  const requested = charactersOf("redistill-characters");
  const existingNames = new Set(getRunCharacterNames(currentRun));
  const existing = requested.filter((name) => existingNames.has(name));
  const newcomers = requested.filter((name) => !existingNames.has(name));
  renderRedistillPlanGroup("redistill-existing-list", existing, "redistill-existing-empty");
  renderRedistillPlanGroup("redistill-new-list", newcomers, "redistill-new-empty");
}

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
}

function closeSelfCardModal() {
  toggle("self-card-modal", false);
  syncModalScrollLock();
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

