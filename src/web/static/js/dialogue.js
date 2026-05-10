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

function buildSessionMetaMessage({ mode = "", participants = [], controlledCharacter = "", selfInsert = {} }) {
  const lines = [];
  if (mode) lines.push(`今夜入场：${humanizeMode(mode)}`);
  if ((participants || []).length) lines.push(`与你同席：${joinCharacters(participants)}`);
  if (controlledCharacter) lines.push(`此刻你是：${controlledCharacter}`);
  if (selfInsert?.display_name) lines.push(`他们会称呼你：${selfInsert.display_name}`);
  if (selfInsert?.scene_identity) lines.push(`旁人眼中的你：${selfInsert.scene_identity}`);
  if (!lines.length) return null;
  return { role: "scene", message: lines.join("\n\n") };
}

function renderDialogueTranscript(session) {
  const card = session?.session_card || {};
  const metaMessage = buildSessionMetaMessage({
    mode: card.mode_display || session?.mode || "",
    participants: card.participants || [],
    controlledCharacter: card.controlled_character || "",
    selfInsert: card.self_insert || {},
  });
  const items = metaMessage ? [metaMessage, ...(session?.transcript || [])] : session?.transcript || [];
  renderTranscript(items);
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

function buildOptimisticTranscript(session, message) {
  const transcript = Array.isArray(session?.transcript) ? [...session.transcript] : [];
  const mode = session?.mode || session?.session_card?.mode || "observe";
  const selfInsert = session?.session_card?.self_insert || {};
  const speaker =
    mode === "act"
      ? session?.session_card?.controlled_character || "你"
      : mode === "insert"
        ? selfInsert.display_name || "你"
        : "你";
  const role = mode === "observe" ? "director" : "user";
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
  currentDialogueSessionId = session.session_id || "";
  currentDialogueSession = session;
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
  renderDialogueTranscript(session);
  await loadRecentSessions();
  updateWorkflowState();
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
        currentRunId = item.run_id || currentRunId;
        currentDialogueSessionId = item.session_id || "";
        currentDialogueSession = null;
        sessionBooting = true;
        setComposerEnabled(false);
        setSessionBadge("入场中");
        renderSessionBooting(item.mode, item.participants || []);
        updateWorkflowState();
        const [run, session] = await Promise.all([
          apiJson(`/api/web/runs/${item.run_id}`),
          apiJson(`/api/web/runs/${item.run_id}/dialogue/sessions/${item.session_id}`),
        ]);
        renderRun(run, { preserveDialogue: true, suppressWorkflowUpdate: true });
        await renderDialogueSession(session);
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

