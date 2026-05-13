(() => {
const existingRunDetailModule = window.__ZAOMENG_RUN_DETAIL_MODULE__;
if (existingRunDetailModule?.initialized) {
  return;
}

const WORK_OVERVIEW_STATE = window.__ZAOMENG_WORK_OVERVIEW_STATE__ || {};
const CHARACTER_OVERVIEW_STATE = window.__ZAOMENG_CHARACTER_OVERVIEW_STATE__ || {};
const RUN_DETAIL_SUPPORT_STATE = window.__ZAOMENG_RUN_DETAIL_SUPPORT_STATE__ || {};
const CHARACTER_OVERVIEW_KEY_FIELDS = Array.isArray(CHARACTER_OVERVIEW_STATE.KEY_FIELDS) ? CHARACTER_OVERVIEW_STATE.KEY_FIELDS : [];
const CHARACTER_OVERVIEW_ADVANCED_GROUPS = Array.isArray(CHARACTER_OVERVIEW_STATE.ADVANCED_GROUPS) ? CHARACTER_OVERVIEW_STATE.ADVANCED_GROUPS : [];
const CHARACTER_OVERVIEW_FIELD_LABELS = CHARACTER_OVERVIEW_STATE.FIELD_LABELS || {};

const characterOverviewExpandedGroups = new Set();
const characterOverviewAutofillHistory = new Map();

function getCurrentRunEvents() {
  return Array.isArray(currentRun?.events) ? currentRun.events : [];
}

function setWorkOverviewLoading(loading, message = "") {
  const progressRoot = el("step-progress");
  if (progressRoot) {
    progressRoot.classList.toggle("is-loading-work", Boolean(loading));
  }
  const loadingRoot = el("work-overview-loading");
  if (loadingRoot) {
    loadingRoot.classList.toggle("hidden", !loading);
  }
  if (loading) {
    setText("detail-action-note", message || "正在载入这一卷...", "");
    toggle("detail-action-note", true);
  } else if (currentRun?.status !== "running" && currentRun?.status !== "stopped" && currentRun?.status !== "failed") {
    toggle("detail-action-note", false);
  }
}

function renderRunSummary(run) {
  setValue("redistill-characters", joinCharacters(getRunCharacterNames(run)));
  setText("redistill-status", run.redistill?.summary || "", "");
  setText("run-progress-import", buildWorkImportStatus(run), "");
  setText("run-progress-distill", buildWorkDistillStatus(run), "");
  setText("run-progress-latest", formatWeakTime(run.updated_at || "") || "刚刚", "");
  const elapsedText = String(run?.summary?.elapsed_text || run?.timing?.elapsed_text || "").trim();
  const progressCopy = String(run.progress?.message || "").trim() || "人物与关系会依次浮现。";
  const enrichedCopy =
    elapsedText && run.summary?.status_text === "workflow_complete" ? `${progressCopy} · 本次用时 ${elapsedText}` : progressCopy;
  setText("progress-copy", enrichedCopy, "");
  setText("work-overview-next-step", buildWorkOverviewNextStep(run), "");
  setText("run-progress-review", buildWorkReviewStatus(run), "");
  setText("run-progress-graph", buildWorkGraphStatus(run), "");
  renderWorkHeroMetrics(run);
  renderWorkSummaryNarrative(run);
  renderSourceHistory(run);
  renderRedistillPlan(run);
  renderQualitySnapshot(run);
  renderCharacterReadiness(run);
  renderWorkPriorityReview(run);
  renderWorkGraphSummary(run);
  renderWorkSessionPreview(run);
  syncRedistillPreview();
}

function buildWorkImportStatus(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkImportStatus === "function") {
    return WORK_OVERVIEW_STATE.buildWorkImportStatus(run);
  }
  return "未开始";
}

function buildWorkDistillStatus(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkDistillStatus === "function") {
    return WORK_OVERVIEW_STATE.buildWorkDistillStatus(run);
  }
  return "未开始";
}

function renderWorkHeroMetrics(run) {
  const sourceName = String(getCurrentNovelSource(run)?.source_name || "").trim() || "当前书页";
  const characterTotal = getRunCharacterNames(run).length;
  const statusText = humanizeSummary(run?.summary?.status_text);
  const elapsedText = String(run?.summary?.elapsed_text || run?.timing?.elapsed_text || "").trim() || "进行中";
  setText("run-hero-source", sourceName, "");
  setText("run-hero-character-total", characterTotal > 0 ? `${characterTotal} 位` : "0 位", "");
  setText("run-hero-status", statusText || "未开始", "");
  setText("run-hero-elapsed", elapsedText, "");
}

function renderWorkSummaryNarrative(run) {
  setText("work-summary-line", buildWorkSummaryLine(run), "");
  setText("work-summary-bottleneck", buildWorkSummaryBottleneck(run), "");
  renderWorkSummaryEvents(run);
  renderWorkRecommendedAction(run);
}

function buildWorkSummaryEvents(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkSummaryEvents === "function") {
    return WORK_OVERVIEW_STATE.buildWorkSummaryEvents(run);
  }
  return Array.isArray(run?.events)
    ? run.events.slice(-3).reverse().map((item) => ({
      stageLabel: humanizeRunEventStage(String(item?.stage || "").trim()),
      message: String(item?.message || "").trim() || "这一轮有新的变化落在这里。",
    }))
    : [];
}

function buildWorkSummaryLine(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkSummaryLine === "function") {
    return WORK_OVERVIEW_STATE.buildWorkSummaryLine(run);
  }
  if (!run) {
    return "先放入一本书，这里会开始归纳整卷状态。";
  }
  const title = runNovelTitle(run);
  const characterCount = getRunCharacterNames(run).length;
  const weakCount = countWeakCharacters(run);
  if (run.status === "running") {
    return `《${title}》还在整理中，目前已经请出了 ${characterCount || 0} 位角色。`;
  }
  if (run.status === "failed") {
    return `《${title}》这一轮停在半途，但已落下的角色和资料仍然能继续接着用。`;
  }
  if (run.status === "stopped") {
    return `《${title}》这轮已经收住，现在适合决定是继续蒸馏还是先校对人物。`;
  }
  if (!characterCount) {
    return `《${title}》还没有稳定的人物包，先把角色请出来。`;
  }
  if (weakCount > 0) {
    return `《${title}》的人物骨架已经立住一部分，但还有 ${weakCount} 位角色值得优先补稳。`;
  }
  if (!run?.artifact_index?.relation_graph?.relations_file) {
    return `《${title}》的人物已基本站稳，关系图谱还没落下，但不影响先开聊。`;
  }
    return `《${title}》这卷已形成完整工作面，可以校对、看关系，也能直接入场。`;
}

function buildWorkSummaryBottleneck(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkSummaryBottleneck === "function") {
    return WORK_OVERVIEW_STATE.buildWorkSummaryBottleneck(run);
  }
  if (!run) {
    return "当前还没有工作对象。";
  }
  if (run.status === "running") {
    return String(run.progress?.message || "").trim() || "当前瓶颈是流程仍在进行，先盯住这一轮进度。";
  }
  if (run.status === "failed") {
    return "这一轮已中断；最稳的接法是继续蒸馏，而不是从零重来。";
  }
  const priority = buildWorkPriorityReviewItems(run)[0];
  if (priority?.hasEvidenceGap) {
    return `当前最卡的是「${priority.name}」证据偏薄，建议换入更贴近他的正文片段做增量蒸馏。`;
  }
  if (priority?.weakCount > 0) {
    return `当前最卡的是「${priority.name}」还有 ${priority.weakCount} 处关键字段偏薄，先补这个角色最划算。`;
  }
  if (!run?.artifact_index?.relation_graph?.relations_file) {
    return "当前主要瓶颈是关系图谱尚未落成；不过这不阻塞聊天与校对。";
  }
  return "当前没有明显卡点，这卷可以把重点从整理切到体验。";
}

function renderWorkSummaryEvents(run) {
  const root = el("work-summary-events");
  if (!root) return;
  root.innerHTML = "";
  buildWorkSummaryEvents(run).forEach((item) => {
    const row = document.createElement("div");
    row.className = "work-summary-event";
    row.innerHTML = `
      <strong>${escapeHtml(item.stageLabel)}</strong>
      <p>${escapeHtml(item.message)}</p>
    `;
    root.appendChild(row);
  });
  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle("work-summary-events-empty", root.childElementCount === 0);
}

function buildWorkRecommendedAction(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkRecommendedAction === "function") {
    return WORK_OVERVIEW_STATE.buildWorkRecommendedAction(run);
  }
  const priority = buildWorkPriorityReviewItems(run)[0];
  if (!run) {
    return {
      buttonLabel: "开始蒸馏",
      title: "先放入一本书",
      copy: "先新建一卷，把故事请上书架。",
      action: "new_run",
      payload: "",
    };
  }
  if (run.status === "running") {
    return {
      buttonLabel: "查看进度",
      title: "先盯住当前整理进度",
      copy: "这一轮还在跑，先不用切太多动作，等角色再落下几位再判断。",
      action: "focus_timeline",
      payload: "",
    };
  }
  if (run.status === "failed" || run.status === "stopped") {
    return {
      buttonLabel: "继续蒸馏",
      title: "把这一轮先接上",
      copy: "沿着这卷继续往下走，比把已落成的人物重做一遍更划算。",
      action: "open_redistill",
      payload: "",
    };
  }
  if (priority?.hasEvidenceGap) {
    return {
      buttonLabel: "补这位角色",
      title: `先给「${priority.name}」补正文证据`,
      copy: "这个角色不只是字段缺字，而是素材偏薄；优先增量蒸馏更有效。",
      action: "redistill_character",
      payload: priority.name,
    };
  }
  if (priority?.weakCount > 0) {
    return {
      buttonLabel: "打开角色页",
      title: `先补稳「${priority.name}」`,
      copy: "先把最薄的角色补稳，这样整卷对话信任感提升最快。",
      action: "open_character",
      payload: priority.name,
    };
  }
  if (!run?.artifact_index?.relation_graph?.relations_file) {
    return {
      buttonLabel: "开始聊天",
      title: "人物已经够用，可以先入场",
      copy: "关系图还没落下，但不影响体验；可以先开一局，回头再补图谱。",
      action: "start_chat",
      payload: "",
    };
  }
  return {
      buttonLabel: "查看关系",
      title: "先看整卷关系",
      copy: "人物和图谱都已稳定，先看全局关系，再决定从谁入场。",
      action: "open_relations",
      payload: "",
    };
}

function renderWorkRecommendedAction(run) {
  const recommendation = buildWorkRecommendedAction(run);
  setText("work-summary-recommend-title", recommendation.title, "");
  setText("work-summary-recommend-copy", recommendation.copy, "");
  const button = el("work-summary-recommend-button");
  if (!button) return;
  button.textContent = recommendation.buttonLabel;
  button.dataset.workRecommendedAction = recommendation.action || "";
  button.dataset.workRecommendedPayload = recommendation.payload || "";
  button.onclick = () => {
    if (typeof window.__ZAOMENG_HANDLE_WORK_RECOMMENDED_ACTION__ === "function") {
      window.__ZAOMENG_HANDLE_WORK_RECOMMENDED_ACTION__(button.dataset.workRecommendedAction || "", button.dataset.workRecommendedPayload || "");
    }
  };
}

function buildQualitySnapshotState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildQualitySnapshotState === "function") {
    return WORK_OVERVIEW_STATE.buildQualitySnapshotState(run);
  }
  const quality = run?.quality || {};
  const summaryChunking = run?.summary?.chunking || {};
  const progressChunking = run?.progress?.chunking || {};
  const focus = quality.excerpt_focus || {};
  const matched = Array.isArray(focus.matched_characters) ? focus.matched_characters : [];
  const missing = Array.isArray(focus.missing_characters) ? focus.missing_characters : [];
  const stages = Array.isArray(quality.stage_presence) ? quality.stage_presence : [];

  const profileRepairs = quality.profile_repairs || {};
  const relationRepairs = quality.relation_repairs || {};
  const profileCount = Number(profileRepairs.count || 0);
  const relationCount = Number(relationRepairs.count || 0);
  const profileNames = joinCharacters(profileRepairs.characters || []);
  const relationPairs = Array.isArray(relationRepairs.pairs) ? relationRepairs.pairs : [];
  const characterFocus = quality.character_focus || {};
  const chunkedCharacters = Object.entries(characterFocus).filter(([, item]) => Number(item?.chunk_count || 1) > 1);
  const relationChunked = Boolean(relationRepairs.chunked) || Number(relationRepairs.chunk_count || 1) > 1;
  const relationChunkCount = Number(relationRepairs.chunk_count || 1);
  const distillChunkSummary = summaryChunking?.distill || {};
  const relationChunkSummary = summaryChunking?.relation || {};
  const distillChunkProgress = progressChunking?.distill || {};
  const relationChunkProgress = progressChunking?.relation || {};

  const repairSegments = [];
  if (profileCount > 0) {
    repairSegments.push(`人物字段收束 ${profileCount} 次${profileNames ? `：${profileNames}` : ""}`);
  }
  if (relationCount > 0) {
    repairSegments.push(`关系字段收束 ${relationCount} 次${relationPairs.length ? `：${relationPairs.slice(0, 3).join("、")}` : ""}`);
  }

  const chunkSegments = [];
  if (distillChunkSummary.mode === "chunked" || Number(distillChunkSummary.chunk_count || 0) > 1) {
    const currentChunk = Number(distillChunkProgress.current_chunk || 0);
    const totalChunks = Number(distillChunkSummary.chunk_count || distillChunkProgress.chunk_count || 0);
    const mergeStatus = String(distillChunkSummary.merge_status || distillChunkProgress.merge_status || "").trim();
    const currentLabel = String(distillChunkProgress.current_label || "").trim();
    let line = `人物实际分为 ${totalChunks} 块`;
    if (currentChunk > 0 && totalChunks > 0) {
      line += `，当前进行到 ${currentChunk}/${totalChunks}`;
    }
    if (currentLabel) {
      line += `（${currentLabel}）`;
    }
    if (mergeStatus && mergeStatus !== "pending") {
      line += `，汇总状态：${mergeStatus === "running" ? "正在汇总" : "已汇总"}`;
    }
    chunkSegments.push(line);
  } else if (chunkedCharacters.length) {
    chunkSegments.push(
      `人物实际分为 ${chunkedCharacters.reduce((total, [, item]) => total + Number(item?.chunk_count || 0), 0)} 块：${chunkedCharacters
        .map(([name, item]) => `${name}${Number(item?.chunk_count || 1)}块`)
        .join("、")}`
    );
  } else {
    chunkSegments.push("人物蒸馏这轮没有触发分批。");
  }
  if (relationChunkSummary.mode === "chunked" || Number(relationChunkSummary.chunk_count || 0) > 1) {
    const currentChunk = Number(relationChunkProgress.current_chunk || 0);
    const totalChunks = Number(relationChunkSummary.chunk_count || relationChunkProgress.chunk_count || 0);
    const mergeStatus = String(relationChunkSummary.merge_status || relationChunkProgress.merge_status || "").trim();
    const currentLabel = String(relationChunkProgress.current_label || "").trim();
    let line = `关系抽取实际分为 ${totalChunks} 块`;
    if (currentChunk > 0 && totalChunks > 0) {
      line += `，当前进行到 ${currentChunk}/${totalChunks}`;
    }
    if (currentLabel) {
      line += `（${currentLabel}）`;
    }
    if (mergeStatus && mergeStatus !== "pending") {
      line += `，汇总状态：${mergeStatus === "running" ? "正在汇总" : "已汇总"}`;
    }
    chunkSegments.push(line);
  } else if (relationChunked) {
    chunkSegments.push(`关系抽取实际分为 ${relationChunkCount} 块，并做了最终汇总。`);
  } else {
    chunkSegments.push("关系抽取这轮没有触发分批。");
  }

  const standardChunkingVisible =
    Number(distillChunkSummary.chunk_count || 0) > 0 ||
    Number(relationChunkSummary.chunk_count || 0) > 0 ||
    String(distillChunkSummary.mode || "").trim() === "chunked" ||
    String(relationChunkSummary.mode || "").trim() === "chunked";
  const visible =
    Boolean(matched.length) ||
    Boolean(missing.length) ||
    Boolean(stages.length) ||
    profileCount > 0 ||
    relationCount > 0 ||
    Boolean(chunkedCharacters.length) ||
    relationChunked ||
    standardChunkingVisible;

  return {
    visible,
    open: Boolean(run?.status === "running"),
    emptyCopyVisible: !visible,
    matched,
    missing,
    stages,
    repairsText: repairSegments.join("；") || "暂时没有发生自动收束。",
    chunksText: chunkSegments.join("；"),
  };
}

function buildWorkPriorityReviewViewState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkPriorityReviewViewState === "function") {
    return WORK_OVERVIEW_STATE.buildWorkPriorityReviewViewState(run);
  }
  return {
    items: buildWorkPriorityReviewItems(run),
    emptyCopy: "目前没有明显掉队角色，可以直接开聊或查看关系图。",
  };
}

function buildWorkGraphSummaryState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkGraphSummaryState === "function") {
    return WORK_OVERVIEW_STATE.buildWorkGraphSummaryState(run);
  }
  const hasGraph = Boolean(run?.artifact_index?.relation_graph?.relations_file);
  const graphFailed = String(run?.summary?.graph_status || "").trim() === "failed" || String(run?.progress?.graph_status || "").trim() === "failed";
  const hasCharacters = getRunCharacterNames(run).length > 0;
  if (hasGraph) {
    return { badgeText: "已完成", badgeTone: "stable", copy: "关系线已经能看，先看牵系和张力，再决定从哪种方式入场。" };
  }
  if (graphFailed) {
    return { badgeText: "失败可跳过", badgeTone: "weak", copy: "这轮关系图谱生成失败，但不会阻塞聊天；可以先入场，稍后再补图谱。" };
  }
  if (run?.status === "running") {
    return { badgeText: "进行中", badgeTone: "warning", copy: "关系网还在织，但不妨先盯住人物进度；图谱落下后会自动接到这里。" };
  }
  if (hasCharacters) {
    return { badgeText: "待补图谱", badgeTone: "warning", copy: "关系图暂时还没落成，但人物已经可以继续校对，也不影响你先进入聊天。" };
  }
  return { badgeText: "未开始", badgeTone: "warning", copy: "先把人物请出来，关系网才会在这里慢慢织成。" };
}

function buildWorkGraphLinks(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkGraphLinks === "function") {
    return WORK_OVERVIEW_STATE.buildWorkGraphLinks(run);
  }
  return [
    run?.file_urls?.graph_html ? { url: run.file_urls.graph_html, label: "查看关系图谱" } : null,
    run?.file_urls?.graph_svg ? { url: run.file_urls.graph_svg, label: "查看 SVG" } : null,
  ].filter(Boolean);
}

function buildWorkSessionPreviewState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkSessionPreviewState === "function") {
    return WORK_OVERVIEW_STATE.buildWorkSessionPreviewState(run);
  }
  const novelTitle = runNovelTitle(run);
  const characterNames = getRunCharacterNames(run);
  const allSessions = (recentSessionsCache || [])
    .filter((item) => normalizeNovelTitle(item?.novel_id || "") === novelTitle)
    .sort((left, right) => String(right?.updated_at || "").localeCompare(String(left?.updated_at || "")));
  const rankedSessions = [...allSessions].sort((left, right) => {
    const rightMatch = Boolean(findMatchedSessionCharacter(getSessionPreviewSnippet(right), characterNames).character);
    const leftMatch = Boolean(findMatchedSessionCharacter(getSessionPreviewSnippet(left), characterNames).character);
    if (rightMatch !== leftMatch) {
      return Number(rightMatch) - Number(leftMatch);
    }
    return String(right?.updated_at || "").localeCompare(String(left?.updated_at || ""));
  });
  return {
    canExpand: rankedSessions.length > 3,
    expanded: Boolean(workSessionPreviewExpanded),
    toggleLabel: workSessionPreviewExpanded ? "收起部分" : "展开全部",
    latest: allSessions[0]
      ? {
        label: `继续：${joinCharacters(allSessions[0].participants || []) || "最近会话"}`,
        raw: allSessions[0],
      }
      : null,
    items: (workSessionPreviewExpanded ? rankedSessions : rankedSessions.slice(0, 3)).map((item) => {
      const snippet = getSessionPreviewSnippet(item);
      const matchInfo = findMatchedSessionCharacter(snippet, characterNames);
      return {
        label: joinCharacters(item?.participants || []) || "未命名会话",
        modeLabel: item?.mode_display || humanizeMode(item?.mode) || "这一幕",
        participantCount: Array.isArray(item?.participants) ? item.participants.length : 0,
        hasMatch: Boolean(matchInfo.character),
        matchText: matchInfo.character ? `命中 ${matchInfo.character} · ${matchInfo.reason}` : "",
        snippet,
        updatedText: formatWeakTime(item?.updated_at) || "刚刚",
        statusText: humanizeSessionStatus(item?.status),
        raw: item,
      };
    }),
    emptyCopy: "还没有会话，随时可以从下方三种方式开局。",
  };
}


function buildWorkOverviewNextStep(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkOverviewNextStep === "function") {
    return WORK_OVERVIEW_STATE.buildWorkOverviewNextStep(run);
  }
  return "这一卷的下一步会在这里告诉你。";
}

function buildWorkReviewStatus(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkReviewStatus === "function") {
    return WORK_OVERVIEW_STATE.buildWorkReviewStatus(run);
  }
  return "未开始";
}

function buildWorkGraphStatus(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkGraphStatus === "function") {
    return WORK_OVERVIEW_STATE.buildWorkGraphStatus(run);
  }
  return "未开始";
}

function countWeakCharacters(run) {
  if (typeof WORK_OVERVIEW_STATE.countWeakCharacters === "function") {
    return WORK_OVERVIEW_STATE.countWeakCharacters(run);
  }
  return 0;
}

function buildCharacterReadinessItems(run) {
  if (typeof WORK_OVERVIEW_STATE.buildCharacterReadinessItems === "function") {
    return WORK_OVERVIEW_STATE.buildCharacterReadinessItems(run);
  }
  return [];
}

function buildCharacterReadinessViewState(run) {
  if (typeof WORK_OVERVIEW_STATE.buildCharacterReadinessViewState === "function") {
    return WORK_OVERVIEW_STATE.buildCharacterReadinessViewState(run);
  }
  return {
    items: [],
    canExpand: false,
    expanded: false,
    toggleLabel: "展开全部",
    emptyCopy: "还没有角色卡，先继续蒸馏把人物请出来。",
  };
}

function renderCharacterReadiness(run) {
  window.__ZAOMENG_WORK_OVERVIEW_LEGACY_RENDER__?.renderCharacterReadiness?.(run);
}

function buildWorkPriorityReviewItems(run) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkPriorityReviewItems === "function") {
    return WORK_OVERVIEW_STATE.buildWorkPriorityReviewItems(run);
  }
  return [];
}

function buildWorkPriorityHeadline(item) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkPriorityHeadline === "function") {
    return WORK_OVERVIEW_STATE.buildWorkPriorityHeadline(item);
  }
  return "";
}

function buildWorkPriorityReason(item) {
  if (typeof WORK_OVERVIEW_STATE.buildWorkPriorityReason === "function") {
    return WORK_OVERVIEW_STATE.buildWorkPriorityReason(item);
  }
  return "";
}

function renderWorkPriorityReview(run) {
  window.__ZAOMENG_WORK_OVERVIEW_LEGACY_RENDER__?.renderWorkPriorityReview?.(run);
}

function renderWorkGraphSummary(run) {
  window.__ZAOMENG_WORK_OVERVIEW_LEGACY_RENDER__?.renderWorkGraphSummary?.(run);
}

function renderWorkSessionPreview(run) {
  window.__ZAOMENG_WORK_OVERVIEW_LEGACY_RENDER__?.renderWorkSessionPreview?.(run);
}

function getSessionPreviewSnippet(item) {
  const serverSnippet = String(item?.last_entry_preview || "").trim();
  return serverSnippet || readRecentSessionSnippet(item?.run_id, item?.session_id);
}

function findMatchedSessionCharacter(snippet, characterNames) {
  const text = String(snippet || "").trim();
  if (!text) return { character: "", reason: "" };
  const matched = (Array.isArray(characterNames) ? characterNames : []).find((name) => {
    const candidate = String(name || "").trim();
    return candidate && text.includes(candidate);
  }) || "";
  return matched ? { character: matched, reason: "摘要提到" } : { character: "", reason: "" };
}

async function openWorkSessionFromPreviewItem(item) {
  if (!item?.run_id || !item?.session_id) return;
  const previousRunId = currentRunId;
  const previousRun = currentRun;
  const previousSessionId = currentDialogueSessionId;
  const previousSession = currentDialogueSession;
  currentRunId = item.run_id || currentRunId;
  currentDialogueSessionId = item.session_id || "";
  currentDialogueSession = null;
  sessionBooting = true;
  setComposerEnabled(false);
  setSessionBadge("入场中");
  renderSessionBooting(item.mode, item.participants || []);
  updateWorkflowState();
  try {
    const [freshRun, session] = await Promise.all([
      apiJson(`/api/web/runs/${item.run_id}`),
      apiJson(`/api/web/runs/${item.run_id}/dialogue/sessions/${item.session_id}`),
    ]);
    if (typeof window.renderRun === "function") {
      window.renderRun(freshRun, { preserveDialogue: true, suppressWorkflowUpdate: true });
    } else {
      currentRun = freshRun;
      currentRunId = String(freshRun?.run_id || item.run_id || "").trim();
      updateWorkflowState();
    }
    await renderDialogueSession(session);
  } catch (error) {
    currentRunId = previousRunId;
    currentRun = previousRun;
    currentDialogueSessionId = previousSessionId;
    currentDialogueSession = previousSession;
    sessionBooting = false;
    if (previousSession) {
      renderDialogueMemory(previousSession);
      renderDialogueTranscript(previousSession);
      setComposerEnabled(true);
      setSessionBadge("对话中");
    } else {
      resetDialogueView();
    }
    updateWorkflowState();
    setStatus("dialogue-session-status", error.message || "这段会话暂时没有载入成功。");
  }
}

function openWorkSummaryExport() {
  const target =
    currentRun?.file_urls?.manifest ||
    currentRun?.file_urls?.graph_relations_file ||
    currentRun?.file_urls?.graph_html ||
    currentRun?.file_urls?.graph_svg ||
    "";
  if (!target) {
    setStatus("bookshelf-status", "当前没有可导出的摘要文件。");
    return;
  }
  window.open(target, "_blank", "noopener,noreferrer");
}

async function openCharacterOverview(characterName) {
  return window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.openCharacterOverview?.(characterName);
}

function renderCharacterOverview(payload) {
  const fields = payload?.fields || {};
  const character = String(payload?.character || "").trim() || "人物";
  const workTitle = runNovelTitle(currentRun);
  const role = String(fields.story_role || fields.core_identity || "这一页会慢慢把他的轮廓立起来").trim();
  const snapshot = buildCharacterOverviewHealthSnapshot(fields);
  const evidenceSnapshot = buildCharacterOverviewEvidenceSnapshot(character);

  setText("character-overview-title", `${character} · 人物档案`, "");
  setText("character-overview-work", `出自《${workTitle}》`, "");
  setText("character-overview-name", character, "");
  setText("character-overview-role", role, "");
  setText("character-overview-health-badge", snapshot.healthText, "");
  const badge = el("character-overview-health-badge");
  if (badge) {
    badge.className = `work-character-status is-${snapshot.healthTone}`;
  }
  setText("character-overview-health-copy", snapshot.summaryCopy, "");
  setStatus("character-overview-status", "");

  renderCharacterOverviewHealthMetrics(snapshot);
  renderCharacterOverviewEvidenceMetrics(evidenceSnapshot);
  renderCharacterOverviewTrustSignals(payload, snapshot, evidenceSnapshot);
  renderCharacterOverviewChangeTimeline(payload);
  renderCharacterOverviewKeyFields(fields);
  renderCharacterOverviewVoiceSummary(fields);
  renderCharacterOverviewRelationSummary(fields);
  renderCharacterOverviewAdvancedGroups(fields);
}

function buildCharacterOverviewChangeTimelineItems(character) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildChangeTimelineItems === "function") {
    return CHARACTER_OVERVIEW_STATE.buildChangeTimelineItems(getCurrentRunEvents(), character, formatWeakTime);
  }
  const name = String(character || "").trim();
  if (!name) return [];
  const events = getCurrentRunEvents()
    .filter((item) => String(item?.character || "").trim() === name && String(item?.stage || "").trim() === "persona_review_saved")
    .slice()
    .reverse();
  return events.slice(0, 8).map((item) => {
    const reviewSource = String(item?.review_source || "").trim();
    const reviewNote = String(item?.review_note || "").trim();
    const changedFields = Array.isArray(item?.changed_fields) ? item.changed_fields.filter(Boolean) : [];
    const changedLabels = changedFields.map((field) => CHARACTER_OVERVIEW_FIELD_LABELS[field] || field).slice(0, 3);
    let title = "字段已写回";
    let badge = "手动校对";
    let copy = String(item?.message || "").trim() || "这次改动已经写回这一卷。";
    if (reviewSource === "character_overview_autofill") {
      title = "AI补全已写回";
      badge = formatCharacterOverviewAutofillSource(reviewNote);
      copy = changedLabels.length ? `已补：${changedLabels.join("、")}。` : "AI 补全结果已写回。";
    } else if (reviewSource === "character_overview_inline_edit") {
      title = "手动改动已写回";
      badge = "字段直改";
      copy = changedLabels.length ? `你改了：${changedLabels.join("、")}。` : "手动改动已写回。";
    }
    return {
      title,
      badge,
      copy,
      updated: formatWeakTime(item?.timestamp || "") || "刚刚",
    };
  });
}

function renderCharacterOverviewChangeTimeline(payload) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderChangeTimeline?.(payload);
}

function buildCharacterOverviewHealthSnapshot(fields) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildHealthSnapshot === "function") {
    return CHARACTER_OVERVIEW_STATE.buildHealthSnapshot(fields, currentRun?.updated_at || "", formatWeakTime);
  }
  let filledKeyCount = 0;
  let weakKeyCount = 0;
  CHARACTER_OVERVIEW_KEY_FIELDS.forEach(([field]) => {
    const value = String(fields[field] || "").trim();
    if (value) {
      filledKeyCount += 1;
    }
    if (isCharacterOverviewFieldWeak(field, value)) {
      weakKeyCount += 1;
    }
  });
  const advancedFieldNames = CHARACTER_OVERVIEW_ADVANCED_GROUPS.flatMap(([, fieldNames]) => fieldNames);
  const advancedFilledCount = advancedFieldNames.filter((field) => String(fields[field] || "").trim()).length;
  const totalFieldCount = CHARACTER_OVERVIEW_KEY_FIELDS.length + advancedFieldNames.length;
  const filledFieldCount = filledKeyCount + advancedFilledCount;
  const completeness = totalFieldCount > 0 ? Math.round((filledFieldCount / totalFieldCount) * 100) : 0;
  const stableKeyCount = Math.max(0, CHARACTER_OVERVIEW_KEY_FIELDS.length - weakKeyCount);
  const healthTone = weakKeyCount <= 0 ? "stable" : weakKeyCount >= 4 ? "weak" : "warning";
  const healthText = weakKeyCount <= 0 ? "关键字段已齐" : weakKeyCount >= 4 ? "待校对" : "待补全";
  const updatedText = formatWeakTime(currentRun?.updated_at || "") || "刚刚";
  const summaryCopy =
    weakKeyCount <= 0
      ? "这个角色的关键骨架已经比较完整，可以直接带进对话；如果还想更像本人，再慢慢抠细调字段。"
      : `当前还有 ${weakKeyCount} 处关键字段偏薄，建议先补稳骨架，再决定是否继续增量蒸馏。`;
  return {
    completeness,
    stableKeyCount,
    weakKeyCount,
    advancedFilledCount,
    advancedTotalCount: advancedFieldNames.length,
    updatedText,
    healthTone,
    healthText,
    summaryCopy,
  };
}

function renderCharacterOverviewHealthMetrics(snapshot) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderHealthMetrics?.(snapshot);
}

function buildCharacterOverviewEvidenceSnapshot(character) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildEvidenceSnapshot === "function") {
    return CHARACTER_OVERVIEW_STATE.buildEvidenceSnapshot(currentRun, character, formatWeakTime, formatSourceStats, getCurrentNovelSource);
  }
  const name = String(character || "").trim();
  const focus = currentRun?.quality?.excerpt_focus || {};
  const missing = new Set(Array.isArray(focus.missing_characters) ? focus.missing_characters : []);
  const matched = new Set(Array.isArray(focus.matched_characters) ? focus.matched_characters : []);
  const currentSource = getCurrentNovelSource(currentRun);
  const allSources = Array.isArray(currentRun?.novel_sources) ? currentRun.novel_sources : [];
  const currentSourceName = String(currentSource?.source_name || "").trim() || "当前书页";
  const currentSourceKind = currentSource?.kind === "incremental_update" ? "增量书段" : "初始正文";
  const currentSourceStats = formatSourceStats(currentSource);
  const updatedText = formatWeakTime(currentRun?.updated_at || "") || "刚刚";
  if (missing.has(name)) {
    return {
      evidenceLabel: "证据偏薄",
      evidenceCopy: "这位角色在当前正文里的有效命中还偏少，字段补全可以救急，但更稳的办法仍然是补更贴近他的书段。",
      sourceLabel: currentSourceName,
      sourceCopy: [currentSourceKind, currentSourceStats].filter(Boolean).join(" · ") || "当前整理基于这份书段继续往下走。",
      traceLabel: `${allSources.length || 1} 段来源`,
      traceCopy: `最近更新 ${updatedText}。这轮更适合做增量蒸馏，而不是只补字段。`,
      recommendationLabel: "建议动作",
      recommendationCopy: "优先换入更贴近这个角色的正文片段，然后继续增量蒸馏。",
    };
  }
  if (matched.has(name)) {
    return {
      evidenceLabel: "命中稳定",
      evidenceCopy: "这位角色在当前正文中已经被稳定命中，当前更适合继续补关键字段或做细修。",
      sourceLabel: currentSourceName,
      sourceCopy: [currentSourceKind, currentSourceStats].filter(Boolean).join(" · ") || "当前整理基于这份书段继续往下走。",
      traceLabel: `${allSources.length || 1} 段来源`,
      traceCopy: `最近更新 ${updatedText}。如果字段已经够用，可以直接带进对话测试。`,
      recommendationLabel: "建议动作",
      recommendationCopy: "先补最薄的关键字段；若骨架已稳，就直接带进聊天里验证说话是否像本人。",
    };
  }
  return {
    evidenceLabel: currentRun?.status === "running" ? "仍在整理" : "等待更多证据",
    evidenceCopy: currentRun?.status === "running" ? "这一轮还在继续，人物证据可能还会再长出来。" : "这位角色暂时没有明确命中或缺证据标记，先结合字段薄弱程度判断是否要继续补。",
    sourceLabel: currentSourceName,
    sourceCopy: [currentSourceKind, currentSourceStats].filter(Boolean).join(" · ") || "当前整理基于这份书段继续往下走。",
    traceLabel: `${allSources.length || 1} 段来源`,
    traceCopy: `最近更新 ${updatedText}。你可以先在角色页补字段，再决定要不要换入新书段。`,
    recommendationLabel: "建议动作",
    recommendationCopy: "如果说话方式和灵魂目标还薄，先补字段；如果整个人都虚，再考虑增量蒸馏。",
  };
}

function renderCharacterOverviewEvidenceMetrics(snapshot) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderEvidenceMetrics?.(snapshot);
}

function characterOverviewHistoryKey(character) {
  return window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.historyKey?.(character) || `${currentRunId || ""}::${String(character || "").trim()}`;
}

function getCharacterOverviewAutofillItems(character) {
  return window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.getAutofillItems?.(character) || [];
}

function rememberCharacterOverviewAutofill(character, payload) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.rememberAutofill?.(character, payload);
}

function buildCharacterOverviewTrustSignals(payload, healthSnapshot, evidenceSnapshot) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildTrustSignals === "function") {
    return CHARACTER_OVERVIEW_STATE.buildTrustSignals({
      payload,
      healthSnapshot,
      evidenceSnapshot,
      autofillItems: getCharacterOverviewAutofillItems(String(payload?.character || "").trim()),
      reviewEvent: findLatestRunEventForCharacter(String(payload?.character || "").trim(), "persona_review_saved"),
      redistillSignal: buildCharacterOverviewRedistillSignal(String(payload?.character || "").trim()),
      formatWeakTime,
    });
  }
  const character = String(payload?.character || "").trim();
  const autofillItems = getCharacterOverviewAutofillItems(character);
  const lastAutofill = autofillItems[0] || null;
  const reviewEvent = findLatestRunEventForCharacter(character, "persona_review_saved");
  const redistillSignal = buildCharacterOverviewRedistillSignal(character);
  const editableProfilePath = String(payload?.editable_profile_path || "").trim();
  const generatedProfilePath = String(payload?.generated_profile_path || "").trim();
  const sourceLabel = editableProfilePath ? "校对稿" : generatedProfilePath ? "蒸馏稿" : "来源待确认";
  const sourceCopy = editableProfilePath
    ? "已经存在可编辑人物稿，说明这份档案至少被写回过一次；字段仍可继续逐项复核。"
    : generatedProfilePath
      ? "当前主要来自自动蒸馏生成稿；关键字段稳了再进入对话会更可靠。"
      : "暂时没有拿到明确的人物稿路径，建议先打开原档或重新载入角色页。";
  return [
    {
      label: "字段来源",
      value: sourceLabel,
      copy: sourceCopy,
      tone: editableProfilePath ? "stable" : "neutral",
    },
    {
      label: "最近 AI 补全",
      value: lastAutofill ? lastAutofill.label : "暂无本次补全",
      copy: lastAutofill
        ? `${lastAutofill.label} 刚由 ${formatCharacterOverviewAutofillSource(lastAutofill.sourceMode)}写回，建议再用对话测试口气。`
        : healthSnapshot.weakKeyCount > 0
          ? "关键字段里还有薄处，可以点字段旁的 AI补全 先补一版。"
          : "本次打开角色页后还没有使用 AI补全。",
      tone: lastAutofill ? "stable" : healthSnapshot.weakKeyCount > 0 ? "warning" : "neutral",
    },
    {
      label: "最近增量蒸馏",
      value: redistillSignal.value,
      copy: redistillSignal.copy,
      tone: redistillSignal.tone,
    },
    {
      label: "手动校对",
      value: reviewEvent && String(reviewEvent.review_source || "").trim() !== "character_overview_autofill" ? "已有保存痕迹" : editableProfilePath ? "有可编辑稿" : "未见保存",
      copy: reviewEvent
        ? buildCharacterOverviewReviewCopy(reviewEvent)
        : editableProfilePath
          ? "这份角色已经有可编辑稿，但当前运行记录里没有找到最近保存事件。"
          : "还没有看到人工校对痕迹，适合先从薄字段开始检查。",
      tone: reviewEvent || editableProfilePath ? "stable" : "warning",
    },
    {
      label: "证据提醒",
      value: evidenceSnapshot.evidenceLabel,
      copy: evidenceSnapshot.evidenceCopy,
      tone: evidenceSnapshot.evidenceLabel === "证据偏薄" ? "weak" : "neutral",
    },
  ];
}

function renderCharacterOverviewTrustSignals(payload, healthSnapshot, evidenceSnapshot) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderTrustSignals?.(payload, healthSnapshot, evidenceSnapshot);
}

function findLatestRunEventForCharacter(character, stage = "") {
  if (typeof CHARACTER_OVERVIEW_STATE.findLatestRunEvent === "function") {
    return CHARACTER_OVERVIEW_STATE.findLatestRunEvent(getCurrentRunEvents(), character, stage);
  }
  const name = String(character || "").trim();
  const expectedStage = String(stage || "").trim();
  const events = getCurrentRunEvents();
  return events
    .slice()
    .reverse()
    .find((item) => {
      const eventCharacter = String(item?.character || "").trim();
      const eventStage = String(item?.stage || "").trim();
      return (!name || eventCharacter === name) && (!expectedStage || eventStage === expectedStage);
    });
}

function buildCharacterOverviewReviewCopy(reviewEvent) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildReviewCopy === "function") {
    return CHARACTER_OVERVIEW_STATE.buildReviewCopy(reviewEvent, formatWeakTime);
  }
  const timestampText = formatWeakTime(reviewEvent?.timestamp || "") || "最近";
  const reviewSource = String(reviewEvent?.review_source || "").trim();
  const reviewNote = String(reviewEvent?.review_note || "").trim();
  const changedFields = Array.isArray(reviewEvent?.changed_fields) ? reviewEvent.changed_fields.filter(Boolean) : [];
  const changedLabels = changedFields.map((field) => CHARACTER_OVERVIEW_FIELD_LABELS[field] || field).slice(0, 3);
  const changedCopy = changedLabels.length ? `涉及 ${changedLabels.join("、")}。` : "";
  if (reviewSource === "character_overview_autofill") {
    const sourceLabel = formatCharacterOverviewAutofillSource(reviewNote);
    return `${timestampText}通过 ${sourceLabel} 自动写回过补全；${changedCopy || "仍建议人工扫一眼关键字段。"}`
      .replace("；", "，")
      .trim();
  }
  if (reviewSource === "character_overview_inline_edit") {
    return `${timestampText}在角色页直接保存过字段。${changedCopy}`.trim();
  }
  return `${timestampText}保存过人物校对。${changedCopy}`.trim();
}

function openWorkTimeline() {
  const vueTimelineRoot = el("run-timeline-vue-root");
  const legacyEvents = el("events");
  const timelineSection = document.querySelector(".detail-section-timeline");
  const target =
    (vueTimelineRoot && !vueTimelineRoot.classList.contains("hidden") && vueTimelineRoot) ||
    (legacyEvents && !legacyEvents.classList.contains("hidden") && legacyEvents) ||
    timelineSection ||
    legacyEvents;
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildCharacterOverviewRedistillSignal(character) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildRedistillSignal === "function") {
    return CHARACTER_OVERVIEW_STATE.buildRedistillSignal(currentRun, character, getCurrentNovelSource);
  }
  const name = String(character || "").trim();
  const redistill = currentRun?.redistill || {};
  const existing = new Set(Array.isArray(redistill.existing_characters) ? redistill.existing_characters : []);
  const newcomers = new Set(Array.isArray(redistill.new_characters) ? redistill.new_characters : []);
  const currentSource = getCurrentNovelSource(currentRun);
  const sourceName = String(redistill.source_name || currentSource?.source_name || "").trim();
  if (existing.has(name)) {
    return {
      value: "本轮做过增量",
      copy: `${sourceName ? `最近沿着「${sourceName}」` : "最近"}继续更新过这个角色，适合检查新片段有没有进入关键字段。`,
      tone: "stable",
    };
  }
  if (newcomers.has(name)) {
    return {
      value: "本轮首次蒸馏",
      copy: `${sourceName ? `来自「${sourceName}」` : "来自本轮正文"}的新角色，建议先校对核心身份、目标和说话方式。`,
      tone: "warning",
    };
  }
  if (currentRun?.status === "running") {
    return {
      value: "仍在整理",
      copy: "这一轮还没结束，增量痕迹可能稍后才会落到角色页。",
      tone: "neutral",
    };
  }
  return {
    value: "暂无近期增量",
    copy: "当前没有看到这位角色在最近一轮增量名单里；如果证据偏薄，可以换入更贴近他的书段继续蒸馏。",
    tone: "neutral",
  };
}

function formatCharacterOverviewAutofillSource(sourceMode) {
  if (typeof CHARACTER_OVERVIEW_STATE.formatAutofillSource === "function") {
    return CHARACTER_OVERVIEW_STATE.formatAutofillSource(sourceMode);
  }
  if (sourceMode === "web_fallback") {
    return "联网参考";
  }
  if (sourceMode === "model_knowledge") {
    return "模型知识";
  }
  return "AI";
}

function buildCharacterOverviewFieldTags(field, value, evidenceSnapshot) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildFieldTags === "function") {
    const recentAutofill = getCharacterOverviewAutofillItems(currentCharacterOverview?.character).find((item) => item.field === field);
    return CHARACTER_OVERVIEW_STATE.buildFieldTags(field, value, evidenceSnapshot, {
      recentAutofill,
      editableProfilePath: String(currentCharacterOverview?.editable_profile_path || "").trim(),
    });
  }
  const text = String(value || "").trim();
  const tags = [];
  const recentAutofill = getCharacterOverviewAutofillItems(currentCharacterOverview?.character).find((item) => item.field === field);
  if (recentAutofill) {
    tags.push({ label: "AI补全", tone: "stable" });
  }
  if (!text) {
    tags.push({ label: "待补", tone: "weak" });
  } else if (!recentAutofill) {
    tags.push({ label: currentCharacterOverview?.editable_profile_path ? "校对稿" : "蒸馏稿", tone: "neutral" });
  }
  if (evidenceSnapshot?.evidenceLabel === "证据偏薄" && ["core_identity", "story_role", "soul_goal", "key_bonds"].includes(field)) {
    tags.push({ label: "证据薄", tone: "weak" });
  }
  return tags.slice(0, 3);
}

function renderCharacterOverviewKeyFields(fields) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderKeyFields?.(fields);
}

function syncCharacterOverviewFieldSaveButton(inputNode) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.syncFieldSaveButton?.(inputNode);
}

function handleCharacterOverviewFieldInput(event) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.handleFieldInput?.(event);
}

function buildCharacterOverviewSavePayload(nextFields, reviewSource = "", reviewNote = "") {
  return window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.buildSavePayload?.(nextFields, reviewSource, reviewNote) || {};
}

function isCharacterOverviewFieldWeak(field, value) {
  if (typeof CHARACTER_OVERVIEW_STATE.isFieldWeak === "function") {
    return CHARACTER_OVERVIEW_STATE.isFieldWeak(field, value);
  }
  const text = String(value || "").trim();
  if (!text) return true;
  if (["worldview", "belief_anchor", "moral_bottom_line", "restraint_threshold", "stress_response", "speech_style", "identity_anchor", "soul_goal"].includes(field)) {
    return text.length < 10;
  }
  if (["core_traits", "key_bonds"].includes(field)) {
    return text.length < 6;
  }
  return text.length < 4;
}

function buildCharacterOverviewFieldHint(field, value) {
  if (typeof CHARACTER_OVERVIEW_STATE.buildFieldHint === "function") {
    return CHARACTER_OVERVIEW_STATE.buildFieldHint(field, value);
  }
  const text = String(value || "").trim();
  if (!text) {
    return "这块还空着，可以先让 AI 补一版，再进人物校对里细修。";
  }
  if (isCharacterOverviewFieldWeak(field, text)) {
    return "这块已经有轮廓，但还偏薄，适合继续补稳。";
  }
  return "这块已经能支撑当前角色概览。";
}

function renderCharacterOverviewVoiceSummary(fields) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderVoiceSummary?.(fields);
}

function renderCharacterOverviewRelationSummary(fields) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderRelationSummary?.(fields);
}

function renderCharacterOverviewAdvancedGroups(fields) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__?.renderAdvancedGroups?.(fields);
}

function handleCharacterOverviewAdvancedGroupToggle(event) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.handleAdvancedGroupToggle?.(event);
}

async function handleCharacterOverviewFieldAutofill(event) {
  return window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.handleFieldAutofill?.(event);
}

async function handleCharacterOverviewFieldSave(event) {
  return window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.handleFieldSave?.(event);
}

function openCharacterOverviewIncrementalDistill() {
  window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.openCharacterOverviewIncrementalDistill?.();
}

function openIncrementalDistillForCharacter(characterName) {
  window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.openIncrementalDistillForCharacter?.(characterName);
}

async function openCharacterOverviewSessionMode(mode) {
  return window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.openCharacterOverviewSessionMode?.(mode);
}

function openCurrentCharacterProfileFile() {
  window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__?.openCurrentCharacterProfileFile?.();
}

function renderQualitySnapshot(run) {
  window.__ZAOMENG_WORK_OVERVIEW_LEGACY_RENDER__?.renderQualitySnapshot?.(run);
}

function renderRunEvents(run) {
  window.__ZAOMENG_RUN_DETAIL_SUPPORT_RENDER__?.renderRunEvents?.(run);
}

function renderRunGraphLinks(run) {
  window.__ZAOMENG_RUN_DETAIL_SUPPORT_RENDER__?.renderRunGraphLinks?.(run);
}

function syncRunArtifacts(run) {
  renderCharacterPills(run);
  renderRedistillPills(run);
  const reviewButton = el("open-persona-review-button");
  if (reviewButton) {
    reviewButton.classList.remove("hidden");
    reviewButton.disabled = !Boolean(run?.artifact_index?.characters?.length);
  }
  if (run.artifact_index?.characters?.length) {
    maybePrefillChatSetup(run);
  }
}

function renderRun(run, options = {}) {
  setWorkOverviewLoading(false);
  const preserveDialogue = Boolean(options.preserveDialogue);
  const suppressWorkflowUpdate = Boolean(options.suppressWorkflowUpdate);
  setStatus("bookshelf-status", "");
  currentRunId = run.run_id || "";
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
  renderRunSummary(run);
  renderRunEvents(run);
  renderRunGraphLinks(run);
  syncRunArtifacts(run);
  if (!preserveDialogue) {
    resetDialogueView();
  }
  renderBookshelfDetail(run);
  syncBookshelfSelection();
  loadRunsOverview().catch((error) => console.warn("loadRunsOverview failed", error));
  loadRecentSessions().catch((error) => console.warn("loadRecentSessions failed", error));
  if (!suppressWorkflowUpdate) {
    updateWorkflowState();
  }
  if (run.status === "running") {
    scheduleRunPolling();
  } else {
    stopRunPolling();
  }
  if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("run-rendered");
  }
}

const RUN_DETAIL_BRIDGE_TOOLS = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
window.renderRun = renderRun;

async function refreshCurrentRunView(runId = currentRunId, options = {}) {
  const target = String(runId || "").trim();
  if (!target) return null;
  const run = await apiJson(`/api/web/runs/${target}`);
  renderRun(run, options);
  return run;
}
window.refreshCurrentRunView = refreshCurrentRunView;

if (typeof RUN_DETAIL_BRIDGE_TOOLS.mergeLegacyActionBridge === "function") {
  RUN_DETAIL_BRIDGE_TOOLS.mergeLegacyActionBridge("__ZAOMENG_RUN_DETAIL_ACTIONS__", {
    refreshRunView: refreshCurrentRunView,
    renderRunView: renderRun,
  });
} else {
  window.__ZAOMENG_RUN_DETAIL_ACTIONS__ = {
    ...(window.__ZAOMENG_RUN_DETAIL_ACTIONS__ || {}),
    refreshRunView: refreshCurrentRunView,
    renderRunView: renderRun,
  };
}
window.__ZAOMENG_RUN_DETAIL_ACTIONS__ = {
  ...(window.__ZAOMENG_RUN_DETAIL_ACTIONS__ || {}),
  refreshRunView: refreshCurrentRunView,
  renderRunView: renderRun,
};

function scheduleRunPolling() {
  stopRunPolling();
  if (!currentRunId) return;
  runPollTimer = window.setTimeout(async () => {
    try {
      await refreshCurrentRunView(currentRunId);
    } catch (error) {
      console.warn("poll run failed", error);
    }
  }, 1800);
}

function renderRedistillPlan(run) {
  window.__ZAOMENG_RUN_DETAIL_SUPPORT_RENDER__?.renderRedistillPlan?.(run);
}

function renderRedistillPlanGroup(rootId, names, emptyId) {
  const root = el(rootId);
  if (!root) return;
  root.innerHTML = "";
  (names || []).forEach((name) => {
    const chip = document.createElement("span");
    chip.textContent = name;
    root.appendChild(chip);
  });
  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle(emptyId, root.childElementCount === 0);
}

function renderRedistillRecentChanges(items) {
  const root = el("redistill-change-list");
  if (!root) return;
  root.innerHTML = "";
  (items || []).forEach((item) => {
    const card = document.createElement("article");
    card.className = "redistill-change-card";

    const title = document.createElement("strong");
    title.textContent = String(item?.character || "角色").trim() || "角色";

    const summary = document.createElement("p");
    summary.textContent = String(item?.summary || "").trim() || "这一轮有新的字段变化落了下来。";

    const metaBits = [];
    const labels = Array.isArray(item?.highlight_field_labels) ? item.highlight_field_labels.filter(Boolean) : [];
    if (labels.length) {
      metaBits.push(`重点：${labels.join("、")}`);
    }
    const changedCount = Number(item?.changed_count || 0);
    if (changedCount > 0) {
      metaBits.push(`共 ${changedCount} 项`);
    }
    const meta = document.createElement("small");
    meta.textContent = metaBits.join(" · ");

    card.appendChild(title);
    card.appendChild(summary);
    if (meta.textContent) {
      card.appendChild(meta);
    }
    root.appendChild(card);
  });
  toggle("redistill-change-shell", root.childElementCount > 0);
  toggle("redistill-change-empty", root.childElementCount === 0);
}

function renderSourceHistory(run) {
  window.__ZAOMENG_RUN_DETAIL_SUPPORT_RENDER__?.renderSourceHistory?.(run);
}

function getCurrentNovelSource(run) {
  return typeof RUN_DETAIL_SUPPORT_STATE.getCurrentNovelSource === "function"
    ? RUN_DETAIL_SUPPORT_STATE.getCurrentNovelSource(run)
    : null;
}

function PathNameFrom(pathText) {
  return typeof RUN_DETAIL_SUPPORT_STATE.pathNameFrom === "function"
    ? RUN_DETAIL_SUPPORT_STATE.pathNameFrom(pathText)
    : "";
}

function formatSourceStats(source) {
  return typeof RUN_DETAIL_SUPPORT_STATE.formatSourceStats === "function"
    ? RUN_DETAIL_SUPPORT_STATE.formatSourceStats(source)
    : "";
}

function buildSourceDetailText(source, current) {
  return typeof RUN_DETAIL_SUPPORT_STATE.buildSourceDetailText === "function"
    ? RUN_DETAIL_SUPPORT_STATE.buildSourceDetailText(source, current)
    : "";
}

function formatCompactNumber(value) {
  return typeof RUN_DETAIL_SUPPORT_STATE.formatCompactNumber === "function"
    ? RUN_DETAIL_SUPPORT_STATE.formatCompactNumber(value)
    : "";
}

function formatByteSize(value) {
  return typeof RUN_DETAIL_SUPPORT_STATE.formatByteSize === "function"
    ? RUN_DETAIL_SUPPORT_STATE.formatByteSize(value)
    : "";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

window.WORK_OVERVIEW_STATE = WORK_OVERVIEW_STATE;
window.CHARACTER_OVERVIEW_STATE = CHARACTER_OVERVIEW_STATE;
window.RUN_DETAIL_SUPPORT_STATE = RUN_DETAIL_SUPPORT_STATE;
window.CHARACTER_OVERVIEW_KEY_FIELDS = CHARACTER_OVERVIEW_KEY_FIELDS;
window.CHARACTER_OVERVIEW_ADVANCED_GROUPS = CHARACTER_OVERVIEW_ADVANCED_GROUPS;
window.CHARACTER_OVERVIEW_FIELD_LABELS = CHARACTER_OVERVIEW_FIELD_LABELS;
window.characterOverviewExpandedGroups = characterOverviewExpandedGroups;
window.characterOverviewAutofillHistory = characterOverviewAutofillHistory;

window.getCurrentRunEvents = getCurrentRunEvents;
window.setWorkOverviewLoading = setWorkOverviewLoading;
window.renderRunSummary = renderRunSummary;
window.buildWorkImportStatus = buildWorkImportStatus;
window.buildWorkDistillStatus = buildWorkDistillStatus;
window.renderWorkHeroMetrics = renderWorkHeroMetrics;
window.renderWorkSummaryNarrative = renderWorkSummaryNarrative;
window.buildWorkSummaryEvents = buildWorkSummaryEvents;
window.buildWorkSummaryLine = buildWorkSummaryLine;
window.buildWorkSummaryBottleneck = buildWorkSummaryBottleneck;
window.renderWorkSummaryEvents = renderWorkSummaryEvents;
window.buildWorkRecommendedAction = buildWorkRecommendedAction;
window.renderWorkRecommendedAction = renderWorkRecommendedAction;
window.buildQualitySnapshotState = buildQualitySnapshotState;
window.buildWorkPriorityReviewViewState = buildWorkPriorityReviewViewState;
window.buildWorkGraphSummaryState = buildWorkGraphSummaryState;
window.buildWorkGraphLinks = buildWorkGraphLinks;
window.buildWorkSessionPreviewState = buildWorkSessionPreviewState;
window.buildWorkOverviewNextStep = buildWorkOverviewNextStep;
window.buildWorkReviewStatus = buildWorkReviewStatus;
window.buildWorkGraphStatus = buildWorkGraphStatus;
window.countWeakCharacters = countWeakCharacters;
window.buildCharacterReadinessItems = buildCharacterReadinessItems;
window.buildCharacterReadinessViewState = buildCharacterReadinessViewState;
window.renderCharacterReadiness = renderCharacterReadiness;
window.buildWorkPriorityReviewItems = buildWorkPriorityReviewItems;
window.buildWorkPriorityHeadline = buildWorkPriorityHeadline;
window.buildWorkPriorityReason = buildWorkPriorityReason;
window.renderWorkPriorityReview = renderWorkPriorityReview;
window.renderWorkGraphSummary = renderWorkGraphSummary;
window.renderWorkSessionPreview = renderWorkSessionPreview;
window.getSessionPreviewSnippet = getSessionPreviewSnippet;
window.findMatchedSessionCharacter = findMatchedSessionCharacter;
window.openWorkSummaryExport = openWorkSummaryExport;
window.openCharacterOverview = openCharacterOverview;
window.renderCharacterOverview = renderCharacterOverview;
window.buildCharacterOverviewChangeTimelineItems = buildCharacterOverviewChangeTimelineItems;
window.renderCharacterOverviewChangeTimeline = renderCharacterOverviewChangeTimeline;
window.buildCharacterOverviewHealthSnapshot = buildCharacterOverviewHealthSnapshot;
window.renderCharacterOverviewHealthMetrics = renderCharacterOverviewHealthMetrics;
window.buildCharacterOverviewEvidenceSnapshot = buildCharacterOverviewEvidenceSnapshot;
window.renderCharacterOverviewEvidenceMetrics = renderCharacterOverviewEvidenceMetrics;
window.characterOverviewHistoryKey = characterOverviewHistoryKey;
window.getCharacterOverviewAutofillItems = getCharacterOverviewAutofillItems;
window.rememberCharacterOverviewAutofill = rememberCharacterOverviewAutofill;
window.buildCharacterOverviewTrustSignals = buildCharacterOverviewTrustSignals;
window.renderCharacterOverviewTrustSignals = renderCharacterOverviewTrustSignals;
window.findLatestRunEventForCharacter = findLatestRunEventForCharacter;
window.buildCharacterOverviewReviewCopy = buildCharacterOverviewReviewCopy;
window.openWorkTimeline = openWorkTimeline;
window.buildCharacterOverviewRedistillSignal = buildCharacterOverviewRedistillSignal;
window.formatCharacterOverviewAutofillSource = formatCharacterOverviewAutofillSource;
window.buildCharacterOverviewFieldTags = buildCharacterOverviewFieldTags;
window.renderCharacterOverviewKeyFields = renderCharacterOverviewKeyFields;
window.syncCharacterOverviewFieldSaveButton = syncCharacterOverviewFieldSaveButton;
window.handleCharacterOverviewFieldInput = handleCharacterOverviewFieldInput;
window.buildCharacterOverviewSavePayload = buildCharacterOverviewSavePayload;
window.isCharacterOverviewFieldWeak = isCharacterOverviewFieldWeak;
window.buildCharacterOverviewFieldHint = buildCharacterOverviewFieldHint;
window.renderCharacterOverviewVoiceSummary = renderCharacterOverviewVoiceSummary;
window.renderCharacterOverviewRelationSummary = renderCharacterOverviewRelationSummary;
window.renderCharacterOverviewAdvancedGroups = renderCharacterOverviewAdvancedGroups;
window.handleCharacterOverviewAdvancedGroupToggle = handleCharacterOverviewAdvancedGroupToggle;
window.handleCharacterOverviewFieldAutofill = handleCharacterOverviewFieldAutofill;
window.handleCharacterOverviewFieldSave = handleCharacterOverviewFieldSave;
window.openCharacterOverviewIncrementalDistill = openCharacterOverviewIncrementalDistill;
window.openIncrementalDistillForCharacter = openIncrementalDistillForCharacter;
window.openCharacterOverviewSessionMode = openCharacterOverviewSessionMode;
window.openCurrentCharacterProfileFile = openCurrentCharacterProfileFile;
window.renderQualitySnapshot = renderQualitySnapshot;
window.renderRunEvents = renderRunEvents;
window.renderRunGraphLinks = renderRunGraphLinks;
window.syncRunArtifacts = syncRunArtifacts;
window.renderRun = renderRun;
window.refreshCurrentRunView = refreshCurrentRunView;
window.scheduleRunPolling = scheduleRunPolling;
window.renderRedistillPlan = renderRedistillPlan;
window.renderRedistillPlanGroup = renderRedistillPlanGroup;
window.renderRedistillRecentChanges = renderRedistillRecentChanges;
window.renderSourceHistory = renderSourceHistory;
window.getCurrentNovelSource = getCurrentNovelSource;
window.PathNameFrom = PathNameFrom;
window.formatSourceStats = formatSourceStats;
window.buildSourceDetailText = buildSourceDetailText;
window.formatCompactNumber = formatCompactNumber;
window.formatByteSize = formatByteSize;
window.escapeHtml = escapeHtml;

window.__ZAOMENG_RUN_DETAIL_MODULE__ = {
  initialized: true,
  version: String(window.__ZAOMENG_WEB_UI_VERSION__ || ""),
};
})();
