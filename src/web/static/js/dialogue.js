(() => {
const existingDialogueModule = window.__ZAOMENG_DIALOGUE_MODULE__;
if (existingDialogueModule?.initialized) {
  return;
}
const UI_BRIDGE_TOOLS = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};

function scrollTranscriptToBottom() {
  const root = el("dialogue-transcript");
  if (!root) return;
  const apply = () => {
    root.scrollTop = root.scrollHeight;
    const last = root.lastElementChild;
    if (last instanceof HTMLElement) {
      last.scrollIntoView({ block: "end" });
    }
  };
  requestAnimationFrame(() => {
    apply();
    requestAnimationFrame(apply);
  });
  window.setTimeout(apply, 0);
  window.setTimeout(apply, 60);
  window.setTimeout(apply, 180);
}

function applySessionListViewportLock() {
  const root = el("sidebar-session-list");
  if (!root) return;
  const rect = root.getBoundingClientRect();
  const bottomGap = 28;
  const available = Math.max(180, Math.floor(window.innerHeight - rect.top - bottomGap));
  root.style.overflowY = "auto";
  root.style.overflowX = "hidden";
  root.style.maxHeight = `${available}px`;
  root.style.height = "auto";
}

function appendStyledMessageContent(target, message) {
  const text = String(message || "");
  const pattern = /([（(][^（）()\n]*[）)])/g;
  let lastIndex = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      target.appendChild(document.createTextNode(text.slice(lastIndex, start)));
    }
    const aside = document.createElement("span");
    aside.className = "message-aside";
    aside.textContent = match[0] || "";
    target.appendChild(aside);
    lastIndex = start + String(match[0] || "").length;
  }
  if (lastIndex < text.length) {
    target.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
}

function createMessageBubble(role, message) {
  const bubble = document.createElement("div");
  bubble.className = `message-bubble ${role}`;
  const body = document.createElement("p");
  appendStyledMessageContent(body, message);
  bubble.appendChild(body);
  return bubble;
}

function buildSessionMetaMessage({ mode = "", participants = [], controlledCharacter = "", selfInsert = {}, sceneCard = {} }) {
  const lines = [];
  if (mode) lines.push(`今夜入场：${humanizeMode(mode)}`);
  if ((participants || []).length) lines.push(`与你同席：${joinCharacters(participants)}`);
  if (controlledCharacter) lines.push(`此刻你是：${controlledCharacter}`);
  if (selfInsert?.display_name) lines.push(`他们会称呼你：${selfInsert.display_name}`);
  if (selfInsert?.scene_identity) lines.push(`旁人眼中的你：${selfInsert.scene_identity}`);
  if (sceneCard?.title || sceneCard?.location || sceneCard?.atmosphere) {
    const sceneBits = [sceneCard?.title, sceneCard?.location, sceneCard?.atmosphere].filter(Boolean);
    lines.push(`当前挂载场景：${sceneBits.join(" / ")}`);
  }
  if (!lines.length) return null;
  return { role: "scene", message: lines.join("\n\n") };
}

function renderDialogueTranscript(session) {
  const card = session?.session_card || {};
  const metaMessage = buildSessionMetaMessage({
    mode: card.mode_display || session?.mode || "",
    participants: card.participants || [],
    controlledCharacter: card.controlled_character || "",
    sceneCard: card.scene_card || {},
    selfInsert: card.self_insert || {},
  });
  const items = metaMessage ? [metaMessage, ...(session?.transcript || [])] : session?.transcript || [];
  renderTranscript(items);
}

function trimInlineMessage(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > 88 ? `${text.slice(0, 88)}...` : text;
}

function buildDialogueMemorySnapshot(session) {
  const summary = session?.session_memory_summary || {};
  const summaryMode = String(summary.mode || "").trim();
  const summaryModeLabel = String(summary.mode_display || "").trim();
  const summaryRecap = String(summary.recap || "").trim();
  const summaryCast = String(summary.cast || "").trim();
  const summaryRelation = String(summary.relation_drift || "").trim();
  const summaryPerspective = String(summary.perspective || "").trim();
  const summaryScene = String(summary.scene_frame || "").trim();
  const summaryWorld = String(summary.world || "").trim();
  const summaryUpdated = String(summary.updated_at || "").trim();

  if (summaryRecap || summaryCast || summaryRelation || summaryPerspective || summaryScene || summaryWorld) {
    return {
      modeLabel: summaryModeLabel || humanizeMode(summaryMode || session?.mode || session?.session_card?.mode || "observe"),
      recap: summaryRecap || "这局刚开场，回顾会在这里滚动更新。",
      cast: summaryCast || "人物发言次序会在这里收住。",
      relation: summaryRelation || "关系线会在这里滚动提示。",
      perspective: summaryPerspective || "你当前的入场方式会在这里提示。",
      scene: summaryScene || "当前这幕的地点、气氛与推进方向会在这里提醒你。",
      world: summaryWorld || "当前局势里的动作与情绪线会在这里提醒你。",
      updated: formatWeakTime(summaryUpdated) || formatWeakTime(session?.updated_at) || "刚刚更新",
    };
  }

  const mode = String(session?.mode || session?.session_card?.mode || "observe").trim() || "observe";
  const modeLabel = humanizeMode(mode) || mode;
  const transcript = Array.isArray(session?.transcript) ? session.transcript : [];
  const castRows = transcript.filter((item) => item?.role === "character");
  const worldRows = transcript.filter((item) => item?.role === "scene" || item?.role === "director");
  const lastRows = transcript.slice(-6);
  const lastCharacter = castRows.length ? castRows[castRows.length - 1] : null;
  const lastWorld = worldRows.length ? worldRows[worldRows.length - 1] : null;
  const speakerOrder = [];
  const seen = new Set();
  castRows.forEach((item) => {
    const speaker = String(item?.speaker || "").trim();
    if (!speaker || seen.has(speaker)) return;
    seen.add(speaker);
    speakerOrder.push(speaker);
  });
  const lastBeatMessages = lastRows
    .filter((item) => String(item?.message || "").trim())
    .map((item) => trimInlineMessage(item.message))
    .slice(-3);

  let recap = "这局刚开场，回顾会在这里滚动更新。";
  if (lastBeatMessages.length) {
    recap = `最近一拍：${lastBeatMessages.join(" / ")}`;
  }

  let cast = "人物发言次序会在这里收住。";
  if (speakerOrder.length) {
    cast = `当前主要在场：${speakerOrder.slice(0, 5).join("、")}${speakerOrder.length > 5 ? "..." : ""}`;
  } else if (lastCharacter?.speaker) {
    cast = `${lastCharacter.speaker} 刚刚接话：${trimInlineMessage(lastCharacter.message)}`;
  }

  let relation = "关系线会在这里滚动提示。";
  if (castRows.length >= 2) {
    const recent = castRows
      .slice(-4)
      .map((item) => String(item?.speaker || "").trim())
      .filter(Boolean);
    if (recent.length >= 2) {
      relation = `最近接话链：${recent.join(" → ")}`;
    }
  } else if (speakerOrder.length) {
    relation = `本局关键人物：${speakerOrder.slice(0, 4).join("、")}`;
  }

  let perspective = "你当前的入场方式会在这里提示。";
  if (mode === "act") {
    const controlled = String(session?.session_card?.controlled_character || "").trim() || "该角色";
    perspective = `你正以「${controlled}」发言，其他人会按角色关系回应。`;
  } else if (mode === "insert") {
    const selfName = String(session?.session_card?.self_insert?.display_name || "").trim() || "你";
    const identity = String(session?.session_card?.self_insert?.scene_identity || "").trim();
    perspective = identity ? `你以「${selfName}」入场（${identity}）。` : `你以「${selfName}」入场，直接参与这幕。`;
  } else {
    perspective = "你在旁观推进模式里，主要作用是推动局势进入下一拍。";
  }

  let world = "当前局势里的动作与情绪线会在这里提醒你。";
  let scene = "当前这幕的地点、气氛与推进方向会在这里提醒你。";
  const sceneCard = session?.session_card?.scene_card || {};
  if (sceneCard && (sceneCard.title || sceneCard.location || sceneCard.atmosphere || sceneCard.scene_drive)) {
    const sceneBits = [sceneCard.title, sceneCard.location, sceneCard.atmosphere].filter(Boolean);
    const drive = trimInlineMessage(sceneCard.scene_drive || sceneCard.opening_situation || "");
    scene = sceneBits.length ? `挂载场景：${sceneBits.join(" / ")}${drive ? ` · ${drive}` : ""}` : drive || scene;
  }
  if (lastWorld?.message) {
    world = trimInlineMessage(lastWorld.message);
  } else if (lastCharacter?.message) {
    world = `人物最新情绪线：${trimInlineMessage(lastCharacter.message)}`;
  }

  return {
    modeLabel,
    recap,
    cast,
    relation,
    perspective,
    scene,
    world,
    updated: formatWeakTime(session?.updated_at) || "刚刚更新",
  };
}

function renderDialogueMemory(session) {
  const root = el("dialogue-memory");
  if (!root) return;
  if (!session) {
    root.classList.add("hidden");
    return;
  }
  const snapshot = buildDialogueMemorySnapshot(session);
  const collapsed = root.classList.contains("is-collapsed");
  root.classList.remove("hidden");
  setText("dialogue-memory-recap", snapshot.recap, "");
  setText("dialogue-memory-cast", snapshot.cast, "");
  setText("dialogue-memory-relation", snapshot.relation, "");
  setText("dialogue-memory-perspective", snapshot.perspective, "");
  setText("dialogue-memory-scene", snapshot.scene, "");
  setText("dialogue-memory-world", snapshot.world, "");
  setText("dialogue-memory-mode", `模式：${snapshot.modeLabel}`, "");
  const branchNote = el("dialogue-memory-branch");
  const branchOrigin = session?.branch_origin || {};
  const branchTitle = String(branchOrigin?.scene_title || "").trim();
  if (branchNote) {
    branchNote.textContent = branchTitle ? `分支自：${branchTitle}` : "";
    branchNote.classList.toggle("hidden", !branchTitle);
  }
  setText("dialogue-memory-updated", `更新于 ${snapshot.updated}`, "");
  const toggle = el("dialogue-memory-toggle-button");
  if (toggle) {
    toggle.textContent = collapsed ? "展开" : "收起";
  }
  const body = el("dialogue-memory-body");
  if (body) {
    body.classList.toggle("hidden", collapsed);
  }
  renderDialogueSceneTimeline(session);
  if (typeof window.renderDialogueSceneSwitcher === "function") {
    window.renderDialogueSceneSwitcher(session);
  }
}

function renderDialogueSceneTimeline(session) {
  const root = el("dialogue-scene-timeline");
  if (!root) return;
  const items = Array.isArray(session?.scene_history) ? session.scene_history : [];
  if (!items.length) {
    root.innerHTML = "";
    root.classList.add("hidden");
    return;
  }
  root.classList.remove("hidden");
  root.innerHTML = "";

  const head = document.createElement("div");
  head.className = "dialogue-scene-timeline-head";
  const title = document.createElement("strong");
  title.textContent = "场景时间线";
  const note = document.createElement("small");
  note.textContent = "这一局从哪一幕走到哪一幕，会在这里顺着记下来。";
  head.appendChild(title);
  head.appendChild(note);
  root.appendChild(head);

  const list = document.createElement("div");
  list.className = "dialogue-scene-timeline-list";
  items.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "dialogue-scene-timeline-item";
    card.tabIndex = 0;
    if (String(item?.is_current || "").trim()) {
      card.classList.add("is-current");
    }
    const strong = document.createElement("strong");
    const titleText = String(item?.title || "").trim() || `第 ${index + 1} 幕`;
    const location = String(item?.location || "").trim();
    strong.textContent = location ? `${titleText} · ${location}` : titleText;
    card.appendChild(strong);
    const atmosphere = String(item?.atmosphere || "").trim();
    if (atmosphere) {
      const copy = document.createElement("p");
      copy.textContent = atmosphere;
      card.appendChild(copy);
    }
    const transition = String(item?.transition_message || "").trim();
    if (transition) {
      const transitionNode = document.createElement("small");
      transitionNode.textContent = `转场提示：${transition}`;
      card.appendChild(transitionNode);
    }
    const actions = document.createElement("div");
    actions.className = "dialogue-scene-timeline-actions";
    const branchButton = document.createElement("button");
    branchButton.type = "button";
    branchButton.className = "soft-button";
    branchButton.textContent = "从这里重开";
    branchButton.addEventListener("click", (event) => {
      event.stopPropagation();
      if (typeof window.branchDialogueSessionFromScene === "function") {
        window.branchDialogueSessionFromScene(index);
      }
    });
    actions.appendChild(branchButton);
    card.appendChild(actions);
    card.addEventListener("click", () => {
      if (typeof window.applyDialogueSceneTimelineEntry === "function") {
        window.applyDialogueSceneTimelineEntry(item);
      }
    });
    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      if (typeof window.applyDialogueSceneTimelineEntry === "function") {
        window.applyDialogueSceneTimelineEntry(item);
      }
    });
    list.appendChild(card);
  });
  root.appendChild(list);
}

function buildDialogueMemoryClipboardText(session) {
  if (!session) return "";
  const snapshot = buildDialogueMemorySnapshot(session);
  const participants = Array.isArray(session?.session_card?.participants) ? session.session_card.participants : [];
  const participantText = participants.length ? joinCharacters(participants) : "未记录";
  return [
    `【本局记忆】`,
    `模式：${snapshot.modeLabel}`,
    `同席：${participantText}`,
    `场景回顾：${snapshot.recap}`,
    `人物动向：${snapshot.cast}`,
    `关系变化：${snapshot.relation}`,
    `你的位置：${snapshot.perspective}`,
    `场景框架：${snapshot.scene}`,
    `世界状态：${snapshot.world}`,
    `更新时间：${snapshot.updated}`,
  ].join("\n");
}

async function copyDialogueMemorySummary() {
  if (!currentDialogueSession) return;
  const button = el("dialogue-memory-copy-button");
  const status = el("dialogue-memory-copy-status");
  const original = button?.textContent || "复制摘要";
  const text = buildDialogueMemoryClipboardText(currentDialogueSession);
  if (!text) return;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "readonly");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      const ok = document.execCommand("copy");
      textarea.remove();
      if (!ok) {
        throw new Error("copy_failed");
      }
    }
    if (button) {
      button.textContent = "已复制";
      window.setTimeout(() => {
        if (button) button.textContent = original;
      }, 1200);
    }
    if (status) status.textContent = "已复制";
    window.setTimeout(() => {
      if (status) status.textContent = "";
    }, 1600);
  } catch (_error) {
    if (button) {
      button.textContent = "复制失败";
      window.setTimeout(() => {
        if (button) button.textContent = original;
      }, 1400);
    }
    if (status) status.textContent = "复制失败";
    window.setTimeout(() => {
      if (status) status.textContent = "";
    }, 1600);
  }
}

function toggleDialogueMemory() {
  const root = el("dialogue-memory");
  if (!root) return;
  root.classList.toggle("is-collapsed");
  renderDialogueMemory(currentDialogueSession);
}

function renderTranscript(items) {
  const root = el("dialogue-transcript");
  if (!root) return;
  root.innerHTML = "";

  (items || []).forEach((item) => {
    const role = item.role || "character";
    const row = document.createElement("article");
    row.className = `transcript-item ${role}`;

    if (role === "scene" || role === "director" || role === "loading") {
      row.appendChild(createMessageBubble(role, item.message || ""));
      root.appendChild(row);
      return;
    }

    const inline = document.createElement("div");
    inline.className = `message-inline ${role}`;

    const name = document.createElement("span");
    name.className = "speaker-name";
    name.textContent = item.speaker || (role === "user" ? "你" : "角色");

    const bubble = createMessageBubble(role, item.message || "");
    if (role === "user") {
      inline.appendChild(bubble);
      inline.appendChild(name);
    } else {
      inline.appendChild(name);
      inline.appendChild(bubble);
    }

    row.appendChild(inline);
    root.appendChild(row);
  });

  scrollTranscriptToBottom();
}

function renderSessionBooting(mode, participants) {
  const items = [];
  const meta = buildSessionMetaMessage({ mode, participants });
  if (meta) items.push(meta);
  items.push({ role: "loading", message: "正在替你铺开场景与第一轮对白..." });
  setSessionBadge("入场中");
  renderTranscript(items);
}

function runDetailActionsForDialogue() {
  const tools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
  if (typeof tools.readLegacyActionBridge === "function") {
    return tools.readLegacyActionBridge("__ZAOMENG_RUN_DETAIL_ACTIONS__");
  }
  return window.__ZAOMENG_RUN_DETAIL_ACTIONS__ || {};
}

function renderRunFallbackForDialogue(run) {
  if (!run || typeof run !== "object") {
    return null;
  }
  currentRunId = String(run.run_id || currentRunId || "").trim();
  currentRun = run;
  newRunFlowOpen = false;
  characterOverviewOpen = false;
  currentCharacterOverview = null;
  redistillPanelOpen = false;
  sourceHistoryExpanded = false;
  characterReadinessExpanded = false;
  workSessionPreviewExpanded = false;
  runCreationPending = run.status === "running" && run.summary?.status_text !== "workflow_complete";
  if (typeof renderBookshelfDetail === "function") {
    renderBookshelfDetail(run);
  }
  if (typeof syncBookshelfSelection === "function") {
    syncBookshelfSelection();
  }
  if (typeof updateWorkflowState === "function") {
    updateWorkflowState();
  }
  if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("dialogue-run-rendered-fallback");
  }
  return run;
}

function ensureRunReadyForDialogue(run, options = {}) {
  if (typeof window.__ZAOMENG_APPLY_RUN_VIEW__ === "function") {
    window.__ZAOMENG_APPLY_RUN_VIEW__(run, options);
    return true;
  }
  const actions = runDetailActionsForDialogue();
  if (typeof actions.renderRunView === "function") {
    actions.renderRunView(run, options);
    return true;
  }
  if (typeof window.renderRun === "function") {
    window.renderRun(run, options);
    return true;
  }
  renderRunFallbackForDialogue(run);
  return false;
}

function buildOptimisticTranscript(session, message, messageKind = "dialogue") {
  const transcript = Array.isArray(session?.transcript) ? [...session.transcript] : [];
  const mode = session?.mode || session?.session_card?.mode || "observe";
  const selfInsert = session?.session_card?.self_insert || {};
  const isNarration = String(messageKind || "").trim() === "narration";
  const speaker = isNarration
    ? "场景提示"
    : mode === "act"
      ? session?.session_card?.controlled_character || "你"
      : mode === "insert"
        ? selfInsert.display_name || "你"
        : "你";
  const role = isNarration ? "scene" : mode === "observe" ? "director" : "user";
  transcript.push({ speaker, message, role });
  transcript.push({ speaker: "", message: "正在生成回复...", role: "loading" });
  return transcript;
}

function latestSessionSnippetFromTranscript(items) {
  const rows = Array.isArray(items) ? items : [];
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    const entry = rows[index] || {};
    const role = String(entry.role || "").trim();
    const message = String(entry.message || "").trim();
    if (!message) continue;
    if (role === "loading") continue;
    return message;
  }
  return "";
}

async function renderDialogueSession(session) {
  if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-local", {
      currentDialogueSessionId: session.session_id || "",
      currentDialogueSession: session,
    });
  } else {
    currentDialogueSessionId = session.session_id || "";
    currentDialogueSession = session;
  }
  const latestSnippet = latestSessionSnippetFromTranscript(session?.transcript);
  if (latestSnippet) {
    rememberRecentSessionSnippet(currentRunId, currentDialogueSessionId, latestSnippet);
  }
  sessionBooting = false;
  setComposerEnabled(true);
  if (typeof syncSuggestButtonVisibility === "function") {
    syncSuggestButtonVisibility(session);
  }
  if (typeof renderObserveQuickReplies === "function") {
    renderObserveQuickReplies(session);
  }
  setSessionBadge("对话中");
  renderDialogueMemory(session);
  renderDialogueTranscript(session);
  await loadRecentSessions();
  updateWorkflowState();
  if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
    UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-rendered", {
      currentDialogueSessionId,
      currentDialogueSession: session,
    });
  } else if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("dialogue-session-rendered", {
      currentDialogueSessionId,
      currentDialogueSession: session,
    });
  }
  scrollTranscriptToBottom();
  el("dialogue-message")?.focus();
}

async function loadRecentSessions() {
  const root = el("sidebar-session-list");
  if (!root) return;
  const requestId = ++recentSessionsRequestId;
  const data = await apiJson("/api/web/sessions");
  if (requestId !== recentSessionsRequestId) return;

  const deduped = [];
  const seen = new Set();
  for (const item of data.items || []) {
    const key = `${item.run_id || ""}::${item.session_id || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }
  recentSessionsCache = deduped;
  if (currentRun && typeof renderWorkSessionPreview === "function") {
    renderWorkSessionPreview(currentRun);
  }

  root.innerHTML = "";
  if (!deduped.length) {
    root.innerHTML = '<p class="sidebar-text">还没有停留下来的篇章。</p>';
    return;
  }

  const grouped = new Map();
  deduped.slice(0, 24).forEach((item) => {
    const novelId = normalizeNovelTitle(item.novel_id) || "未命名小说";
    if (!grouped.has(novelId)) grouped.set(novelId, []);
    grouped.get(novelId).push(item);
  });

  const fragment = document.createDocumentFragment();
  grouped.forEach((sessions, novelId) => {
    const section = document.createElement("section");
    section.className = "session-group";

    const title = document.createElement("div");
    title.className = "session-group-title";
    title.textContent = novelId;
    section.appendChild(title);

    sessions.forEach((item) => {
      const row = document.createElement("div");
      row.className = "session-row";
      row.style.position = "relative";
      row.style.display = "block";
      row.style.minWidth = "0";

      const button = document.createElement("button");
      button.className = "session-item";
      button.type = "button";
      button.setAttribute("data-run-id", item.run_id || "");
      button.setAttribute("data-session-id", item.session_id || "");
      button.style.display = "grid";
      button.style.gap = "0.25rem";
      button.style.width = "100%";
      button.style.minWidth = "0";
      button.style.padding = "0.8rem 0.9rem";
      button.style.paddingRight = "2.8rem";
      button.style.textAlign = "left";
      button.style.overflow = "hidden";
      const title = document.createElement("span");
      title.className = "session-title";
      title.textContent = joinCharacters(item.participants || []) || "未命名会话";
      title.style.display = "block";
      title.style.width = "100%";
      title.style.maxWidth = "100%";
      title.style.whiteSpace = "nowrap";
      title.style.overflow = "hidden";
      title.style.textOverflow = "ellipsis";
      title.style.color = "var(--ink)";
      title.style.fontSize = "0.84rem";
      title.style.fontWeight = "700";
      title.style.lineHeight = "1.42";

      const mode = document.createElement("span");
      mode.className = "session-mode";
      mode.textContent = item.mode_display || humanizeMode(item.mode) || "-";
      mode.style.display = "block";
      mode.style.maxWidth = "100%";
      mode.style.whiteSpace = "nowrap";
      mode.style.overflow = "hidden";
      mode.style.textOverflow = "ellipsis";
      mode.style.color = "var(--accent-strong)";
      mode.style.fontSize = "0.7rem";
      mode.style.fontWeight = "500";
      mode.style.lineHeight = "1.35";

      const meta = document.createElement("span");
      meta.className = "session-meta";
      meta.textContent = `${humanizeSessionStatus(item.status)}${formatWeakTime(item.updated_at) ? ` · ${formatWeakTime(item.updated_at)}` : ""}`;
      meta.style.display = "block";
      meta.style.maxWidth = "100%";
      meta.style.whiteSpace = "nowrap";
      meta.style.overflow = "hidden";
      meta.style.textOverflow = "ellipsis";
      meta.style.color = "var(--ink-faint)";
      meta.style.fontSize = "0.7rem";
      meta.style.fontWeight = "400";
      meta.style.lineHeight = "1.35";
      meta.style.opacity = "0.92";

      button.appendChild(title);
      button.appendChild(mode);
      button.appendChild(meta);
      button.addEventListener("click", async () => {
        const previousRunId = currentRunId;
        const previousRun = currentRun;
        const previousSessionId = currentDialogueSessionId;
        const previousSession = currentDialogueSession;
        currentRunId = item.run_id || currentRunId;
        if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
          UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-selecting", {
            currentRunId,
            currentDialogueSessionId: item.session_id || "",
            currentDialogueSession: null,
          });
        } else {
          currentDialogueSessionId = item.session_id || "";
          currentDialogueSession = null;
        }
        sessionBooting = true;
        setComposerEnabled(false);
        setSessionBadge("入场中");
        renderSessionBooting(item.mode, item.participants || []);
        updateWorkflowState();
        if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
          UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-booting", {
            currentRunId,
            currentDialogueSessionId,
            currentDialogueSession: null,
          });
        } else if (typeof publishLegacyUiState === "function") {
          publishLegacyUiState("dialogue-session-booting", {
            currentRunId,
            currentDialogueSessionId,
            currentDialogueSession: null,
          });
        }
        try {
          const [run, session] = await Promise.all([
            apiJson(`/api/web/runs/${item.run_id}`),
            apiJson(`/api/web/runs/${item.run_id}/dialogue/sessions/${item.session_id}`),
          ]);
          ensureRunReadyForDialogue(run, { preserveDialogue: true, suppressWorkflowUpdate: true });
          await renderDialogueSession(session);
        } catch (error) {
          currentRunId = previousRunId;
          currentRun = previousRun;
          if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
            UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-restore-local", {
              currentRunId,
              currentDialogueSessionId: previousSessionId,
              currentDialogueSession: previousSession,
            });
          } else {
            currentDialogueSessionId = previousSessionId;
            currentDialogueSession = previousSession;
          }
          sessionBooting = false;
          if (previousSession) {
            renderDialogueMemory(previousSession);
            renderDialogueTranscript(previousSession);
            setComposerEnabled(true);
            setSessionBadge("对话中");
          } else if (typeof resetDialogueView === "function") {
            resetDialogueView();
          }
          if (typeof updateWorkflowState === "function") {
            updateWorkflowState();
          }
          if (typeof UI_BRIDGE_TOOLS?.syncLegacyUiState === "function") {
            UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-restore", {
              currentRunId,
              currentDialogueSessionId,
              currentDialogueSession: previousSession,
            });
          } else if (typeof publishLegacyUiState === "function") {
            publishLegacyUiState("dialogue-session-restore", {
              currentRunId,
              currentDialogueSessionId,
              currentDialogueSession: previousSession,
            });
          }
          setStatus("dialogue-session-status", error.message || "这段会话暂时没有载入成功。");
        }
      });

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "session-delete-button";
      removeButton.textContent = "×";
      removeButton.title = "删除会话";
      removeButton.setAttribute("aria-label", "删除会话");
      removeButton.style.position = "absolute";
      removeButton.style.top = "0.55rem";
      removeButton.style.right = "0.55rem";
      removeButton.style.minHeight = "28px";
      removeButton.style.width = "28px";
      removeButton.style.padding = "0";
      removeButton.style.opacity = "0";
      removeButton.style.pointerEvents = "none";
      removeButton.style.transform = "translateY(-2px)";
      removeButton.style.transition = "opacity 160ms ease, transform 160ms ease";
      removeButton.addEventListener("click", async (event) => {
        event.stopPropagation();
        if (!window.confirm("确定删除这个会话吗？")) return;
        try {
          await apiJson(
            `/api/web/runs/${item.run_id}/dialogue/sessions/${item.session_id}`,
            { method: "DELETE" },
            "删除失败。"
          );
          if (currentRunId === item.run_id && currentDialogueSessionId === item.session_id) {
            resetDialogueView();
            updateWorkflowState();
          }
          await loadRecentSessions();
        } catch (error) {
          window.alert(error.message || "删除失败。");
        }
      });

      const revealDelete = () => {
        removeButton.style.opacity = "1";
        removeButton.style.pointerEvents = "auto";
        removeButton.style.transform = "translateY(0)";
      };
      const hideDelete = () => {
        removeButton.style.opacity = "0";
        removeButton.style.pointerEvents = "none";
        removeButton.style.transform = "translateY(-2px)";
      };
      row.addEventListener("mouseenter", revealDelete);
      row.addEventListener("mouseleave", hideDelete);
      row.addEventListener("focusin", revealDelete);
      row.addEventListener("focusout", hideDelete);

      row.appendChild(button);
      row.appendChild(removeButton);
      section.appendChild(row);
    });

    fragment.appendChild(section);
  });

  if (requestId !== recentSessionsRequestId) return;
  root.replaceChildren(fragment);
  applySessionListViewportLock();
  syncSidebarSelection();
}

async function loadLatestRun() {
  const items = allRuns.length ? allRuns : await loadRunsOverview();
  if (!items.length) return null;
  const preferred =
    items.find((item) => (item.artifact_index?.characters || []).length) ||
    items.find((item) => item.run_id) ||
    null;
  if (!preferred?.run_id) return null;
  return apiJson(`/api/web/runs/${preferred.run_id}`);
}
window.scrollTranscriptToBottom = scrollTranscriptToBottom;
window.applySessionListViewportLock = applySessionListViewportLock;
window.appendStyledMessageContent = appendStyledMessageContent;
window.createMessageBubble = createMessageBubble;
window.buildSessionMetaMessage = buildSessionMetaMessage;
window.renderDialogueTranscript = renderDialogueTranscript;
window.trimInlineMessage = trimInlineMessage;
window.buildDialogueMemorySnapshot = buildDialogueMemorySnapshot;
window.renderDialogueMemory = renderDialogueMemory;
window.buildDialogueMemoryClipboardText = buildDialogueMemoryClipboardText;
window.copyDialogueMemorySummary = copyDialogueMemorySummary;
window.toggleDialogueMemory = toggleDialogueMemory;
window.renderTranscript = renderTranscript;
window.renderSessionBooting = renderSessionBooting;
window.runDetailActionsForDialogue = runDetailActionsForDialogue;
window.renderRunFallbackForDialogue = renderRunFallbackForDialogue;
window.ensureRunReadyForDialogue = ensureRunReadyForDialogue;
window.buildOptimisticTranscript = buildOptimisticTranscript;
window.latestSessionSnippetFromTranscript = latestSessionSnippetFromTranscript;
window.renderDialogueSession = renderDialogueSession;
window.loadRecentSessions = loadRecentSessions;
window.loadLatestRun = loadLatestRun;
window.__ZAOMENG_DIALOGUE_MODULE__ = {
  initialized: true,
  version: String(window.__ZAOMENG_WEB_UI_VERSION__ || ""),
};
})();

