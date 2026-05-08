function syncBookshelfSelection() {
  document.querySelectorAll("#bookshelf-list .bookshelf-item").forEach((node) => {
    const runId = node.getAttribute("data-run-id") || "";
    const nodeRun = findRunById(runId);
    const sameNovel = nodeRun && currentRun && runNovelTitle(nodeRun) === runNovelTitle(currentRun);
    node.classList.toggle("active", runId === currentRunId || Boolean(sameNovel));
  });
}

function renderBookshelfDetail(run) {
  setText("run-stage-title", run ? `《${runNovelTitle(run)}》` : "人物与关系正在慢慢浮现", "");
  setText("run-novel", run ? runNovelTitle(run) : "", "");
  setText("run-characters", run ? joinCharacters(getRunCharacterNames(run)) : "", "");
  setText("run-summary", run ? humanizeSummary(run.summary?.status_text) : "", "");
  setText("progress-copy", run?.progress?.message || "人物会依次显形，关系也会慢慢织起来。", "");
  const isRunning = Boolean(run) && run.status === "running";
  const isStopped = Boolean(run) && run.status === "stopped";
  const stopRequested = isRunning && Boolean(run?.control?.stop_requested);
  const canEnterChat = Boolean(run) && run.status === "ready" && getRunCharacterNames(run).length > 0;
  const canRedistill = Boolean(run) && run.status !== "running";
  const canStop = isRunning && !stopRequested;
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
    chatButton.disabled = !canEnterChat;
    chatButton.classList.toggle("hidden", !canEnterChat);
  }
  const redistillButton = el("detail-redistill-button");
  if (redistillButton) {
    redistillButton.disabled = !canRedistill;
    redistillButton.classList.toggle("hidden", !canRedistill);
    redistillButton.textContent = redistillPanelOpen ? "收起继续蒸馏" : "继续蒸馏";
  }
  const stopButton = el("detail-stop-run-button");
  if (stopButton) {
    stopButton.disabled = !canStop;
    stopButton.classList.toggle("hidden", !isRunning);
    stopButton.textContent = stopRequested ? "正在停止..." : "停止蒸馏";
  }
  const detailActions = el("detail-primary-actions");
  if (detailActions) {
    detailActions.classList.toggle("hidden", !canEnterChat && !canRedistill && !canStop);
  }
  toggle("detail-action-note", Boolean(run) && (isRunning || isStopped));
  if (stopRequested) {
    setText("detail-action-note", "已收到停止请求，正在把当前这一步收住。", "");
  } else if (isRunning) {
    setText("detail-action-note", "这一卷还在整理中，先盯住进度，人物落定后再继续别的动作。", "");
  } else if (isStopped) {
    setText("detail-action-note", "这一轮已经停在这里，可以继续蒸馏把它接上。", "");
  } else if (run?.status === "failed") {
    setText("detail-action-note", "这一轮停在了半途，可以继续蒸馏把它接上。", "");
    toggle("detail-action-note", true);
  }
}

function renderRunStatusBanner(run) {
  const visible = Boolean(run) && (run.status === "running" || run.status === "failed" || run.status === "ready" || run.status === "stopped");
  toggle("run-status-banner", visible);
  if (!visible) return;

  const progressMessage = run?.progress?.message || "这一卷还在慢慢成形。";
  const stage = String(run?.progress?.stage || "").trim();
  const summary = humanizeSummary(run?.summary?.status_text);
  const stopRequested = Boolean(run?.control?.stop_requested) && run?.status === "running";

  if (run?.status === "running") {
    setText("run-status-kicker", stopRequested ? "正在停下" : "正在整理", "");
    setText("run-status-stage", summary || "人物依次显形中", "");
    setText(
      "run-status-description",
      progressMessage || (stopRequested ? "已经收到停止请求，正在收束当前步骤。" : "这一卷还在慢慢成形，先看它往哪里走。"),
      ""
    );
    return;
  }
  if (run?.status === "failed") {
    setText("run-status-kicker", "这卷停住了", "");
    setText("run-status-stage", "可以从这里重新接上", "");
    setText("run-status-description", progressMessage || "这一次停在半途，继续蒸馏就能把它接回去。", "");
    return;
  }
  if (run?.status === "stopped") {
    setText("run-status-kicker", "这卷先停下了", "");
    setText("run-status-stage", "已经按你的意思收住", "");
    setText("run-status-description", progressMessage || "这一轮已经停止，可以稍后继续蒸馏，或直接把它移出书架。", "");
    return;
  }

  const stageText =
    stage === "graph_done" || run?.summary?.status_text === "workflow_complete"
      ? "人物与关系已经落稳"
      : summary || "这一卷已经可以继续";
  setText("run-status-kicker", "已经可入场", "");
  setText("run-status-stage", stageText, "");
  setText("run-status-description", "可以开始聊天，也可以继续补入新书段与新人物。", "");
}

function renderBookshelf(runs) {
  const listRoot = el("bookshelf-list");
  const emptyRoot = el("bookshelf-empty");
  if (!listRoot || !emptyRoot) return;

  const groupedRuns = aggregateRunsByNovel(runs);
  listRoot.innerHTML = "";
  emptyRoot.classList.toggle("hidden", groupedRuns.length > 0);
  if (!groupedRuns.length) {
    renderBookshelfDetail(null);
    return;
  }

  const fragment = document.createDocumentFragment();
  groupedRuns.forEach((run) => {
    const row = document.createElement("div");
    row.className = "bookshelf-item-row";
    const button = document.createElement("button");
    button.type = "button";
    const cardState = getBookshelfCardState(run);
    button.className = `bookshelf-item ${cardState.className}`.trim();
    button.setAttribute("data-run-id", run.run_id || "");
    const characterCount = getRunCharacterNames(run).length;
    const summary = humanizeSummary(run.summary?.status_text);
    const updatedAt = formatWeakTime(run.updated_at || "");
    button.innerHTML = `
      <span class="bookshelf-item-top">
        <span class="bookshelf-item-status-row">
          <span class="bookshelf-item-dot" aria-hidden="true"></span>
          <span class="bookshelf-item-status">${summary}</span>
        </span>
        <strong>${runNovelTitle(run)}</strong>
      </span>
      <span class="bookshelf-item-meta">
        <span>${characterCount ? `已落成人物 ${characterCount}` : "人物仍在整理"}</span>
        <span>${updatedAt || "刚刚放上书架"}</span>
      </span>
    `;
    button.title = `${runNovelTitle(run)}${humanizeSummary(run.summary?.status_text) ? ` · ${humanizeSummary(run.summary?.status_text)}` : ""}`;
    button.addEventListener("click", async () => {
      const freshRun = await apiJson(`/api/web/runs/${run.run_id}`);
      renderRun(freshRun);
    });

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "bookshelf-delete-button";
    removeButton.textContent = "×";
    removeButton.title = "删除这本书卷";
    removeButton.setAttribute("aria-label", `删除《${runNovelTitle(run)}》`);
    removeButton.disabled = run?.status === "running";
    if (removeButton.disabled) {
      removeButton.title = "这本书还在整理中，暂时不能删除";
    }
    removeButton.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (run?.status === "running") {
        window.alert("这本书还在整理中，暂时不能删除。");
        return;
      }
      const title = runNovelTitle(run);
      if (!window.confirm(`确定把《${title}》从书架移走吗？`)) return;
      if (!window.confirm(`最后确认：删除《${title}》后，这本书的人物、关系图和会话记录都会一起删除，且无法恢复。`)) return;
      try {
        const deleted = await apiJson(`/api/web/runs/${run.run_id}`, { method: "DELETE" }, "删除失败。");
        if (currentRun && runNovelTitle(currentRun) === title) {
          showBookshelfHome();
        }
        await loadRecentSessions();
        await loadRunsOverview();
        setStatus("bookshelf-status", formatBookshelfDeleteStatus(title, deleted));
      } catch (error) {
        window.alert(error.message || "删除失败。");
      }
    });

    row.appendChild(button);
    row.appendChild(removeButton);
    fragment.appendChild(row);
  });
  listRoot.appendChild(fragment);
  syncBookshelfSelection();
  renderBookshelfDetail(currentRun || null);
}

function formatBookshelfDeleteStatus(title, payload) {
  const runCount = Number(payload?.deleted_run_count || 0);
  const sessionCount = Number(payload?.deleted_session_count || 0);
  return `已移走《${title}》，同时删除 ${runCount} 轮记录 / ${sessionCount} 个会话。`;
}

function getBookshelfCardState(run) {
  if (run?.status === "failed") {
    return { className: "is-failed" };
  }
  if (run?.status === "stopped") {
    return { className: "is-stopped" };
  }
  if (run?.status === "running") {
    return { className: "is-running" };
  }
  if (run?.status === "ready") {
    return { className: "is-ready" };
  }
  return { className: "" };
}

async function loadRunsOverview() {
  const data = await apiJson("/api/web/runs");
  allRuns = Array.isArray(data.items) ? data.items : [];
  renderBookshelf(allRuns);
  return allRuns;
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
  resetDialogueView();
  renderBookshelfDetail(null);
  applySidebarState();
  updateWorkflowState();
  syncBookshelfSelection();
  el("characters")?.focus();
}
