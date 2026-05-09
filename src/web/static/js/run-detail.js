const CHARACTER_OVERVIEW_KEY_FIELDS = [
  ["core_identity", "核心身份"],
  ["story_role", "故事位置"],
  ["identity_anchor", "身份锚点"],
  ["temperament_type", "气质底色"],
  ["soul_goal", "灵魂目标"],
  ["core_traits", "核心特质"],
  ["key_bonds", "重要牵系"],
  ["speech_style", "说话方式"],
  ["worldview", "世界观"],
  ["belief_anchor", "信念支点"],
  ["moral_bottom_line", "道德底线"],
  ["restraint_threshold", "失控阈值"],
  ["stress_response", "应激反应"],
];

const CHARACTER_OVERVIEW_ADVANCED_GROUPS = [
  ["内核细调", ["hidden_desire", "inner_conflict", "self_cognition", "private_self", "social_mode", "thinking_style", "decision_rules", "reward_logic", "others_impression"]],
  ["对白细调", ["cadence", "typical_lines", "signature_phrases", "sentence_openers", "sentence_endings"]],
  ["情绪细调", ["forbidden_behaviors", "emotion_model", "anger_style", "joy_style", "grievance_style"]],
];

const CHARACTER_OVERVIEW_FIELD_LABELS = {
  core_identity: "核心身份",
  story_role: "故事位置",
  identity_anchor: "身份锚点",
  temperament_type: "气质底色",
  soul_goal: "灵魂目标",
  hidden_desire: "隐秘渴望",
  inner_conflict: "内在冲突",
  self_cognition: "自我认知",
  private_self: "私下的一面",
  speech_style: "说话方式",
  cadence: "语句节奏",
  typical_lines: "代表句",
  signature_phrases: "口头禅",
  sentence_openers: "起句习惯",
  sentence_endings: "句尾习惯",
  social_mode: "社交模式",
  thinking_style: "思考方式",
  decision_rules: "决策规则",
  reward_logic: "回报逻辑",
  worldview: "世界观",
  belief_anchor: "信念支点",
  moral_bottom_line: "道德底线",
  restraint_threshold: "失控阈值",
  core_traits: "核心特质",
  key_bonds: "重要牵系",
  forbidden_behaviors: "不会做的事",
  stress_response: "应激反应",
  emotion_model: "情绪底模",
  anger_style: "发怒方式",
  joy_style: "开心方式",
  grievance_style: "委屈方式",
  others_impression: "他人观感",
};

const characterOverviewExpandedGroups = new Set();
const characterOverviewAutofillHistory = new Map();

function getCurrentRunEvents() {
  return Array.isArray(currentRun?.events) ? currentRun.events : [];
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
  const source = getCurrentNovelSource(run);
  const sourceName = String(source?.source_name || "").trim();
  if (!sourceName) {
    return "未开始";
  }
  return `已完成 · ${sourceName}`;
}

function buildWorkDistillStatus(run) {
  const total = Number(run?.progress?.total_characters || run?.locked_characters?.length || 0);
  const completed = Number(run?.progress?.completed_count || run?.artifact_index?.characters?.length || 0);
  if (total <= 0 && completed <= 0) {
    return "未开始";
  }
  if (run?.status === "failed" || run?.status === "stopped") {
    return `已中断 · ${completed}/${Math.max(total, completed)}`;
  }
  if (completed >= total && total > 0) {
    return `已完成 · ${completed}/${total}`;
  }
  if (run?.status === "running") {
    return `进行中 · ${completed}/${Math.max(total, completed)}`;
  }
  return `待校对 · ${completed}/${Math.max(total, completed)}`;
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

function buildWorkSummaryLine(run) {
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
  const events = Array.isArray(run?.events) ? run.events.slice(-3).reverse() : [];
  events.forEach((item) => {
    const stageLabel = humanizeRunEventStage(String(item?.stage || "").trim());
    const row = document.createElement("div");
    row.className = "work-summary-event";
    row.innerHTML = `
      <strong>${escapeHtml(stageLabel)}</strong>
      <p>${String(item.message || "").trim() || "这一轮有新的变化落在这里。"}</p>
    `;
    root.appendChild(row);
  });
  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle("work-summary-events-empty", root.childElementCount === 0);
}

function buildWorkRecommendedAction(run) {
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
    handleWorkRecommendedAction(button.dataset.workRecommendedAction || "", button.dataset.workRecommendedPayload || "");
  };
}

function handleWorkRecommendedAction(action, payload = "") {
  if (action === "new_run") {
    startNewRunFlow();
    return;
  }
  if (action === "focus_timeline") {
    el("events")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }
  if (action === "open_redistill") {
    redistillPanelOpen = true;
    renderBookshelfDetail(currentRun);
    updateWorkflowState();
    el("redistill-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    el("redistill-characters")?.focus();
    return;
  }
  if (action === "redistill_character") {
    openIncrementalDistillForCharacter(payload);
    return;
  }
  if (action === "open_character") {
    openCharacterOverview(payload).catch((error) => {
      setStatus("bookshelf-status", error.message || "人物档案暂时没有载入。");
    });
    return;
  }
  if (action === "start_chat") {
    openNewDialogueSession().catch((error) => {
      setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。");
    });
    return;
  }
  if (action === "open_relations") {
    openRelationDetails().catch((error) => {
      setStatus("bookshelf-status", error.message || "关系明细暂时没有载入。");
    });
  }
}

function buildWorkOverviewNextStep(run) {
  if (!run) {
    return "先放入一本书，人物和关系才会在这里出现。";
  }
  if (run.status === "running") {
    return "先盯住这轮进度，等人物落定后再决定是否补人或开聊。";
  }
  if (run.status === "failed") {
    return "这一轮停在半途，先继续蒸馏把人物和关系接上。";
  }
  if (run.status === "stopped") {
    return "这卷已经收住，下一步可继续蒸馏，或先校对已落成人物。";
  }
  if (!getRunCharacterNames(run).length) {
    return "这一卷还没有稳定人物包，先继续蒸馏把角色请出来。";
  }
  if (!run?.artifact_index?.relation_graph?.relations_file) {
    return "人物已开始成形，可先校对角色，关系图谱补出后再看全局。";
  }
  return "这卷可以继续校对人物、查看关系，或直接进入其中一幕。";
}

function buildWorkReviewStatus(run) {
  const weakCount = countWeakCharacters(run);
  if (!getRunCharacterNames(run).length) {
    return "未开始";
  }
  if (weakCount <= 0) {
    return "已完成";
  }
  return `待校对 · ${weakCount} 位`;
}

function buildWorkGraphStatus(run) {
  const hasGraph = Boolean(run?.artifact_index?.relation_graph?.relations_file);
  const graphFailed = String(run?.summary?.graph_status || "").trim() === "failed" || String(run?.progress?.graph_status || "").trim() === "failed";
  if (hasGraph) {
    return "已完成";
  }
  if (graphFailed) {
    return "图谱失败但不影响聊天";
  }
  if (run?.status === "failed" || run?.status === "stopped") {
    return "已中断";
  }
  if (run?.status === "running") {
    return "进行中";
  }
  return "未开始";
}

function countWeakCharacters(run) {
  return buildCharacterReadinessItems(run).filter((item) => item.weakCount > 0 || item.statusTone !== "stable").length;
}

function buildCharacterReadinessItems(run) {
  const qualityMissing = new Set(Array.isArray(run?.quality?.excerpt_focus?.missing_characters) ? run.quality.excerpt_focus.missing_characters : []);
  const cards = Array.isArray(run?.artifact_index?.characters) ? run.artifact_index.characters : [];
  return cards.map((item) => {
    const preview = item?.preview || {};
    const missingFields = [
      !String(preview.core_identity || "").trim() ? "核心身份" : "",
      !String(preview.story_role || "").trim() ? "故事位置" : "",
      !String(preview.soul_goal || "").trim() ? "灵魂目标" : "",
      !String(preview.speech_style || "").trim() ? "说话方式" : "",
      !String(preview.temperament_type || "").trim() ? "气质底色" : "",
    ].filter(Boolean);
    const weakCount = missingFields.length;
    let statusText = "稳定";
    let statusTone = "stable";
    if (qualityMissing.has(item.name)) {
      statusText = "证据偏薄";
      statusTone = "weak";
    } else if (weakCount >= 3) {
      statusText = "待校对";
      statusTone = "weak";
    } else if (weakCount > 0) {
      statusText = "待补全";
      statusTone = "warning";
    }
    return {
      name: item.name,
      preview,
      weakCount,
      missingFields,
      statusText,
      statusTone,
      hasEvidenceGap: qualityMissing.has(item.name),
      priorityScore: qualityMissing.has(item.name) ? 100 + weakCount : weakCount,
      updatedText: formatWeakTime(run.updated_at || ""),
    };
  });
}

function renderCharacterReadiness(run) {
  const root = el("run-character-readiness");
  if (!root) return;
  root.innerHTML = "";
  const items = buildCharacterReadinessItems(run);
  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "work-character-card";
    button.innerHTML = `
      <div class="work-character-head">
        <div class="work-character-title">
          <strong>${item.name}</strong>
          <small>${item.preview.core_identity || item.preview.story_role || "人物包已经落地，可继续补细节"}</small>
        </div>
        <span class="work-character-status is-${item.statusTone}">${item.statusText}</span>
      </div>
      <p class="work-character-copy">${item.preview.speech_style || item.preview.soul_goal || "说话方式或灵魂目标还可以继续补得更稳。"}</p>
      <div class="work-character-meta">
        <span>${item.weakCount > 0 ? `待补关键字段 ${item.weakCount}` : "关键字段已齐"}</span>
        <span>${item.updatedText ? `最近更新 ${item.updatedText}` : "刚刚落成"}</span>
      </div>
    `;
    button.addEventListener("click", () => {
      openCharacterOverview(item.name).catch((error) => {
        setStatus("bookshelf-status", error.message || "人物档案暂时没有载入。");
      });
    });
    root.appendChild(button);
  });
  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle("run-character-readiness-empty", root.childElementCount === 0);
}

function buildWorkPriorityReviewItems(run) {
  return buildCharacterReadinessItems(run)
    .filter((item) => item.hasEvidenceGap || item.weakCount > 0 || item.statusTone !== "stable")
    .sort((left, right) => {
      if (right.priorityScore !== left.priorityScore) {
        return right.priorityScore - left.priorityScore;
      }
      if (right.weakCount !== left.weakCount) {
        return right.weakCount - left.weakCount;
      }
      return String(left.name).localeCompare(String(right.name), "zh-Hans-CN");
    })
    .slice(0, 3)
    .map((item, index) => ({
      ...item,
      order: index + 1,
      headline: buildWorkPriorityHeadline(item),
      reason: buildWorkPriorityReason(item),
      actionHint: item.hasEvidenceGap ? "建议换入新书段做增量蒸馏，别只靠字段补全硬补。" : "可以先打开角色页，把关键字段补稳后再决定要不要继续增量蒸馏。",
    }));
}

function buildWorkPriorityHeadline(item) {
  if (item.hasEvidenceGap) {
    return "正文证据偏薄，优先补素材";
  }
  if (item.weakCount >= 3) {
    return "关键骨架还没站稳，优先校对";
  }
  return "还差最后几笔，适合快速补齐";
}

function buildWorkPriorityReason(item) {
  if (item.hasEvidenceGap) {
    return "当前正文里对这个角色的有效片段还偏少，容易出现信息薄、口气虚或关系不稳。";
  }
  if (item.missingFields.length) {
    return `当前最薄的地方是：${item.missingFields.slice(0, 3).join("、")}。`;
  }
  return "这个角色已经有轮廓，但还有几处字段偏薄，适合顺手补稳。";
}

function renderWorkPriorityReview(run) {
  const root = el("work-priority-review-list");
  if (!root) return;
  root.innerHTML = "";
  const items = buildWorkPriorityReviewItems(run);
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "work-priority-card";
    card.innerHTML = `
      <div class="work-priority-card-head">
        <span class="work-priority-rank">优先 ${item.order}</span>
        <span class="work-character-status is-${item.statusTone}">${item.statusText}</span>
      </div>
      <div class="work-priority-title">
        <strong>${item.name}</strong>
        <small>${item.preview.core_identity || item.preview.story_role || "人物轮廓还在慢慢站稳"}</small>
      </div>
      <p class="work-priority-headline">${item.headline}</p>
      <p class="work-priority-copy">${item.reason}</p>
      <div class="work-priority-meta">
        <span>${item.weakCount > 0 ? `待补关键字段 ${item.weakCount}` : "关键字段已齐"}</span>
        <span>${item.updatedText ? `最近更新 ${item.updatedText}` : "刚刚落成"}</span>
      </div>
      <p class="work-priority-hint">${item.actionHint}</p>
      <div class="work-priority-actions">
        <button type="button" class="soft-button" data-work-priority-open="${item.name}">打开角色页</button>
        <button type="button" class="soft-button" data-work-priority-redistill="${item.name}">增量蒸馏</button>
      </div>
    `;
    root.appendChild(card);
  });
  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle("work-priority-review-empty", root.childElementCount === 0);
  root.querySelectorAll("[data-work-priority-open]").forEach((button) => {
    button.addEventListener("click", () => {
      openCharacterOverview(button.getAttribute("data-work-priority-open") || "").catch((error) => {
        setStatus("bookshelf-status", error.message || "人物档案暂时没有载入。");
      });
    });
  });
  root.querySelectorAll("[data-work-priority-redistill]").forEach((button) => {
    button.addEventListener("click", () => {
      openIncrementalDistillForCharacter(button.getAttribute("data-work-priority-redistill") || "");
    });
  });
}

function renderWorkGraphSummary(run) {
  const hasGraph = Boolean(run?.artifact_index?.relation_graph?.relations_file);
  const graphFailed = String(run?.summary?.graph_status || "").trim() === "failed" || String(run?.progress?.graph_status || "").trim() === "failed";
  const hasCharacters = getRunCharacterNames(run).length > 0;
  if (hasGraph) {
    setWorkGraphStatusBadge("已完成", "stable");
    setText("run-graph-status-copy", "关系线已经能看，先看牵系和张力，再决定从哪种方式入场。", "");
    return;
  }
  if (graphFailed) {
    setWorkGraphStatusBadge("失败可跳过", "weak");
    setText("run-graph-status-copy", "这轮关系图谱生成失败，但不会阻塞聊天；可以先入场，稍后再补图谱。", "");
    return;
  }
  if (run?.status === "running") {
    setWorkGraphStatusBadge("进行中", "warning");
    setText("run-graph-status-copy", "关系网还在织，但不妨先盯住人物进度；图谱落下后会自动接到这里。", "");
    return;
  }
  if (hasCharacters) {
    setWorkGraphStatusBadge("待补图谱", "warning");
    setText("run-graph-status-copy", "关系图暂时还没落成，但人物已经可以继续校对，也不影响你先进入聊天。", "");
    return;
  }
  setWorkGraphStatusBadge("未开始", "warning");
  setText("run-graph-status-copy", "先把人物请出来，关系网才会在这里慢慢织成。", "");
}

function setWorkGraphStatusBadge(text, tone = "warning") {
  const badge = el("run-graph-status-badge");
  if (!badge) return;
  badge.textContent = text || "未开始";
  badge.className = `work-character-status is-${tone}`;
}

function renderWorkSessionPreview(run) {
  const root = el("work-session-preview");
  if (!root) return;
  root.innerHTML = "";
  const novelTitle = runNovelTitle(run);
  const sessions = (recentSessionsCache || [])
    .filter((item) => normalizeNovelTitle(item?.novel_id || "") === novelTitle)
    .slice(0, 3);
  sessions.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "work-session-card";
    const participantCount = Array.isArray(item.participants) ? item.participants.length : 0;
    button.innerHTML = `
      <div class="work-session-head">
        <div class="work-session-title">
          <strong>${joinCharacters(item.participants || []) || "未命名会话"}</strong>
          <small>${item.mode_display || humanizeMode(item.mode) || "这一幕"} · ${participantCount || 0} 人</small>
        </div>
      </div>
      <div class="work-session-meta">
        <span>${formatWeakTime(item.updated_at) || "刚刚"}</span>
        <span>${humanizeSessionStatus(item.status)}</span>
      </div>
    `;
    button.addEventListener("click", async () => {
      currentRunId = item.run_id || currentRunId;
      currentDialogueSessionId = item.session_id || "";
      currentDialogueSession = null;
      sessionBooting = true;
      setComposerEnabled(false);
      setSessionBadge("入场中");
      renderSessionBooting(item.mode, item.participants || []);
      updateWorkflowState();
      const [freshRun, session] = await Promise.all([
        apiJson(`/api/web/runs/${item.run_id}`),
        apiJson(`/api/web/runs/${item.run_id}/dialogue/sessions/${item.session_id}`),
      ]);
      renderRun(freshRun, { preserveDialogue: true, suppressWorkflowUpdate: true });
      await renderDialogueSession(session);
    });
    root.appendChild(button);
  });
  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle("work-session-preview-empty", root.childElementCount === 0);
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
  if (!currentRunId || !currentRun || !characterName) return;
  const payload = await apiJson(`/api/web/runs/${currentRunId}/personas/${encodeURIComponent(characterName)}`);
  characterOverviewExpandedGroups.clear();
  currentCharacterOverview = payload;
  characterOverviewOpen = true;
  renderCharacterOverview(payload);
  updateWorkflowState();
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
  renderCharacterOverviewKeyFields(fields);
  renderCharacterOverviewVoiceSummary(fields);
  renderCharacterOverviewRelationSummary(fields);
  renderCharacterOverviewAdvancedGroups(fields);
}

function buildCharacterOverviewHealthSnapshot(fields) {
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
  const root = el("character-overview-health-metrics");
  if (!root) return;
  root.innerHTML = "";
  const metrics = [
    ["完整度", `${snapshot.completeness}%`, "按关键字段与细调字段的当前覆盖度估算"],
    ["稳住的关键字段", `${snapshot.stableKeyCount} / ${CHARACTER_OVERVIEW_KEY_FIELDS.length}`, "这些字段已经足够支撑角色概览与基础对话"],
    ["待补位置", `${snapshot.weakKeyCount} 处`, snapshot.weakKeyCount > 0 ? "优先补这些地方，人物会更像自己" : "关键骨架已经收住，可以转去细修"],
    ["细调覆盖", `${snapshot.advancedFilledCount} / ${snapshot.advancedTotalCount}`, "用于抠语气、情绪和更细的人设纹理"],
    ["最近更新", snapshot.updatedText, "显示这一卷最近一次落盘或校对的大致时间"],
  ];
  metrics.forEach(([label, value, hint]) => {
    const card = document.createElement("article");
    card.className = "character-overview-health-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong><small>${hint}</small>`;
    root.appendChild(card);
  });
}

function buildCharacterOverviewEvidenceSnapshot(character) {
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
  const root = el("character-overview-evidence-metrics");
  if (!root) return;
  root.innerHTML = "";
  const items = [
    ["证据判断", snapshot.evidenceLabel, snapshot.evidenceCopy],
    ["当前依据书段", snapshot.sourceLabel, snapshot.sourceCopy],
    ["来源足迹", snapshot.traceLabel, snapshot.traceCopy],
    [snapshot.recommendationLabel, "下一步", snapshot.recommendationCopy],
  ];
  items.forEach(([label, value, hint]) => {
    const card = document.createElement("article");
    card.className = "character-overview-evidence-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong><small>${hint}</small>`;
    root.appendChild(card);
  });
}

function characterOverviewHistoryKey(character) {
  return `${currentRunId || ""}::${String(character || "").trim()}`;
}

function getCharacterOverviewAutofillItems(character) {
  const historyItems = characterOverviewAutofillHistory.get(characterOverviewHistoryKey(character)) || [];
  const eventItems = getCurrentRunEvents()
    .filter((item) => {
      const eventCharacter = String(item?.character || "").trim();
      const eventStage = String(item?.stage || "").trim();
      const reviewSource = String(item?.review_source || "").trim();
      return eventCharacter === String(character || "").trim() && eventStage === "persona_review_saved" && reviewSource === "character_overview_autofill";
    })
    .slice()
    .reverse()
    .map((item) => {
      const changedFields = Array.isArray(item?.changed_fields) ? item.changed_fields : [];
      const firstField = String(changedFields[0] || "").trim();
      const reviewNote = String(item?.review_note || "").trim();
      return {
        field: firstField,
        label: CHARACTER_OVERVIEW_FIELD_LABELS[firstField] || reviewNote || firstField || "最近补全",
        value: "",
        message: String(item?.message || "").trim(),
        sourceMode: reviewNote,
        timestamp: String(item?.timestamp || "").trim(),
      };
    });
  const merged = [];
  const seen = new Set();
  [...historyItems, ...eventItems].forEach((item) => {
    const key = `${String(item?.field || "").trim()}::${String(item?.timestamp || "").trim()}::${String(item?.sourceMode || "").trim()}`;
    if (seen.has(key)) return;
    seen.add(key);
    merged.push(item);
  });
  return merged
    .sort((left, right) => String(right?.timestamp || "").localeCompare(String(left?.timestamp || "")))
    .slice(0, 6);
}

function rememberCharacterOverviewAutofill(character, payload) {
  const field = String(payload?.field || "").trim();
  if (!character || !field) return;
  const key = characterOverviewHistoryKey(character);
  const items = getCharacterOverviewAutofillItems(character).filter((item) => item.field !== field);
  items.unshift({
    field,
    label: CHARACTER_OVERVIEW_FIELD_LABELS[field] || String(payload?.label || field).trim() || field,
    value: String(payload?.value || "").trim(),
    message: String(payload?.message || "").trim(),
    sourceMode: String(payload?.source_mode || "").trim(),
    timestamp: new Date().toISOString(),
  });
  characterOverviewAutofillHistory.set(key, items.slice(0, 6));
}

function buildCharacterOverviewTrustSignals(payload, healthSnapshot, evidenceSnapshot) {
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
  const root = el("character-overview-trust-signals");
  if (!root) return;
  root.innerHTML = "";
  buildCharacterOverviewTrustSignals(payload, healthSnapshot, evidenceSnapshot).forEach((item) => {
    const card = document.createElement("article");
    card.className = `character-overview-trust-card is-${item.tone || "neutral"}`;
    card.innerHTML = `
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(item.value)}</strong>
      <small>${escapeHtml(item.copy)}</small>
    `;
    root.appendChild(card);
  });
}

function findLatestRunEventForCharacter(character, stage = "") {
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
  el("events")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function buildCharacterOverviewRedistillSignal(character) {
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
  if (sourceMode === "web_fallback") {
    return "联网参考";
  }
  if (sourceMode === "model_knowledge") {
    return "模型知识";
  }
  return "AI";
}

function buildCharacterOverviewFieldTags(field, value, evidenceSnapshot) {
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
  const root = el("character-overview-key-fields");
  if (!root) return;
  root.innerHTML = "";
  const evidenceSnapshot = buildCharacterOverviewEvidenceSnapshot(currentCharacterOverview?.character || "");
  CHARACTER_OVERVIEW_KEY_FIELDS.forEach(([field, label]) => {
    const value = String(fields[field] || "").trim();
    const weak = isCharacterOverviewFieldWeak(field, value);
    const tags = buildCharacterOverviewFieldTags(field, value, evidenceSnapshot);
    const card = document.createElement("article");
    card.className = `character-overview-field-card${weak ? " is-missing" : ""}`;
    const canAutofill = weak;
    card.innerHTML = `
      <div class="character-overview-field-head">
        <span>${label}</span>
        <div class="character-overview-field-actions">
          ${tags.map((tag) => `<span class="character-overview-field-tag is-${tag.tone}">${tag.label}</span>`).join("")}
          ${canAutofill ? `<button type="button" class="character-overview-mini-button" data-character-overview-field="${field}">AI补全</button>` : ""}
          <button type="button" class="character-overview-mini-button" data-character-overview-save="${field}" disabled>已保存</button>
        </div>
      </div>
      <textarea class="character-overview-field-input" data-character-overview-input="${field}" rows="4" placeholder="可以直接在这里修改，然后点保存改动。"></textarea>
      <small class="character-overview-field-hint">${buildCharacterOverviewFieldHint(field, value)}</small>
    `;
    const input = card.querySelector(`[data-character-overview-input="${field}"]`);
    if (input instanceof HTMLTextAreaElement) {
      input.value = value;
      input.dataset.initialValue = value;
      syncCharacterOverviewFieldSaveButton(input);
    }
    root.appendChild(card);
  });
}

function syncCharacterOverviewFieldSaveButton(inputNode) {
  if (!(inputNode instanceof HTMLTextAreaElement)) return;
  const field = String(inputNode.getAttribute("data-character-overview-input") || "").trim();
  if (!field) return;
  const card = inputNode.closest(".character-overview-field-card");
  if (!(card instanceof HTMLElement)) return;
  const button = card.querySelector(`[data-character-overview-save="${field}"]`);
  if (!(button instanceof HTMLButtonElement)) return;
  const initialValue = String(inputNode.dataset.initialValue || "").trim();
  const currentValue = String(inputNode.value || "").trim();
  const dirty = currentValue !== initialValue;
  card.classList.toggle("is-dirty", dirty);
  if (button.dataset.saving !== "true") {
    button.disabled = !dirty;
    button.textContent = dirty ? "保存改动" : "已保存";
  }
}

function handleCharacterOverviewFieldInput(event) {
  const target = event.target;
  if (!(target instanceof HTMLTextAreaElement)) return;
  if (!target.hasAttribute("data-character-overview-input")) return;
  syncCharacterOverviewFieldSaveButton(target);
}

function buildCharacterOverviewSavePayload(nextFields, reviewSource = "", reviewNote = "") {
  const payload = {};
  (PERSONA_REVIEW_FIELD_BINDINGS || []).forEach(([field]) => {
    payload[field] = String(nextFields?.[field] || "").trim();
  });
  payload.review_source = reviewSource;
  payload.review_note = reviewNote;
  return payload;
}

function isCharacterOverviewFieldWeak(field, value) {
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
  const root = el("character-overview-voice-summary");
  if (!root) return;
  root.innerHTML = "";
  const items = [
    ["说话方式", fields.speech_style || "这部分还可以继续抠细。"],
    ["代表句", fields.typical_lines || fields.signature_phrases || "人物口气还没有完全落稳。"],
    ["句子习惯", [fields.sentence_openers, fields.sentence_endings].filter(Boolean).join(" / ") || "起句和句尾还可以继续补。"],
  ];
  items.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "character-overview-summary-card";
    card.innerHTML = `<span>${label}</span><p>${value}</p>`;
    root.appendChild(card);
  });
}

function renderCharacterOverviewRelationSummary(fields) {
  const root = el("character-overview-relation-summary");
  if (!root) return;
  root.innerHTML = "";
  const items = [
    ["重要牵系", fields.key_bonds || "这部分还没有完全落下来。"],
    ["气质底色", fields.temperament_type || "气质底色还可以继续补稳。"],
    ["世界观", fields.worldview || "世界观还没有完全成形。"],
  ];
  items.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "character-overview-summary-card";
    card.innerHTML = `<span>${label}</span><p>${value}</p>`;
    root.appendChild(card);
  });
}

function renderCharacterOverviewAdvancedGroups(fields) {
  const root = el("character-overview-advanced-groups");
  if (!root) return;
  root.innerHTML = "";
  CHARACTER_OVERVIEW_ADVANCED_GROUPS.forEach(([title, fieldNames]) => {
    const values = fieldNames
      .map((field) => {
        const value = String(fields[field] || "").trim();
        return value ? { field, label: CHARACTER_OVERVIEW_FIELD_LABELS[field] || field, value } : null;
      })
      .filter(Boolean);
    const expanded = characterOverviewExpandedGroups.has(title);
    const previewText = values
      .slice(0, 2)
      .map((item) => `${item.label}：${item.value}`)
      .join("；");
    const card = document.createElement("article");
    card.className = "character-overview-advanced-group";
    card.innerHTML = `
      <button type="button" class="character-overview-advanced-toggle${expanded ? " is-open" : ""}" data-character-overview-group="${title}" aria-expanded="${expanded ? "true" : "false"}">
        <span class="character-overview-advanced-title">${title}</span>
        <span class="character-overview-advanced-meta">${values.length > 0 ? `已填 ${values.length} / ${fieldNames.length}` : "这一组还没铺开"}</span>
        <span class="character-overview-advanced-arrow">${expanded ? "收起" : "展开"}</span>
      </button>
      <p class="character-overview-advanced-preview${expanded ? " hidden" : ""}">${previewText || "这一组还可以继续补更多细节，不必一次写满。"}</p>
      <div class="character-overview-advanced-body${expanded ? "" : " hidden"}">
        ${
          values.length
            ? values.map((item) => `<article class="character-overview-advanced-field"><span>${item.label}</span><p>${item.value}</p></article>`).join("")
            : `<p class="character-overview-advanced-empty">这一组暂时还没写开，可以先稳住关键字段，再决定要不要继续细修。</p>`
        }
      </div>
    `;
    root.appendChild(card);
  });
}

function handleCharacterOverviewAdvancedGroupToggle(event) {
  const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-character-overview-group]") : null;
  if (!(trigger instanceof HTMLButtonElement) || !currentCharacterOverview?.fields) return;
  const groupName = String(trigger.getAttribute("data-character-overview-group") || "").trim();
  if (!groupName) return;
  if (characterOverviewExpandedGroups.has(groupName)) {
    characterOverviewExpandedGroups.delete(groupName);
  } else {
    characterOverviewExpandedGroups.add(groupName);
  }
  renderCharacterOverviewAdvancedGroups(currentCharacterOverview.fields || {});
}

async function handleCharacterOverviewFieldAutofill(event) {
  const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-character-overview-field]") : null;
  if (!(trigger instanceof HTMLButtonElement) || !currentRunId || !currentCharacterOverview) return;
  const character = String(currentCharacterOverview.character || "").trim();
  const field = String(trigger.getAttribute("data-character-overview-field") || "").trim();
  if (!character || !field) return;
  const labelText = CHARACTER_OVERVIEW_FIELD_LABELS[field] || field;
  const originalText = trigger.textContent || "AI补全";
  trigger.disabled = true;
  trigger.textContent = "生成中...";
  setStatus("character-overview-status", `正在补全「${labelText}」...`);
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
    if (payload?.status !== "filled" || !payload?.value) {
      setStatus("character-overview-status", payload?.message || payload?.reason || "人物信息补全无法生成。");
      return;
    }
    const nextFields = {
      ...(currentCharacterOverview.fields || {}),
      [field]: payload.value,
    };
    const saved = await apiJson(
      `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...nextFields,
          review_source: "character_overview_autofill",
          review_note: String(payload?.source_mode || "").trim(),
        }),
      },
      "保存人物校对失败。"
    );
    rememberCharacterOverviewAutofill(character, payload);
    currentCharacterOverview = saved;
    renderCharacterOverview(saved);
    renderRun(await apiJson(`/api/web/runs/${currentRunId}`));
    characterOverviewOpen = true;
    currentCharacterOverview = saved;
    updateWorkflowState();
    setStatus("character-overview-status", payload.message || `「${labelText}」已经补上，并写回这一卷。`);
  } catch (error) {
    setStatus("character-overview-status", error.message || "人物信息补全无法生成。");
  } finally {
    trigger.disabled = false;
    trigger.textContent = originalText;
  }
}

async function handleCharacterOverviewFieldSave(event) {
  const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-character-overview-save]") : null;
  if (!(trigger instanceof HTMLButtonElement) || !currentRunId || !currentCharacterOverview) return;
  const character = String(currentCharacterOverview.character || "").trim();
  const field = String(trigger.getAttribute("data-character-overview-save") || "").trim();
  if (!character || !field) return;
  const input = el("character-overview-key-fields")?.querySelector(`[data-character-overview-input="${field}"]`);
  if (!(input instanceof HTMLTextAreaElement)) return;
  const labelText = CHARACTER_OVERVIEW_FIELD_LABELS[field] || field;
  const nextValue = String(input.value || "").trim();
  const currentValue = String(currentCharacterOverview?.fields?.[field] || "").trim();
  if (nextValue === currentValue) {
    syncCharacterOverviewFieldSaveButton(input);
    return;
  }
  const previousText = trigger.textContent || "保存改动";
  trigger.dataset.saving = "true";
  trigger.disabled = true;
  trigger.textContent = "保存中...";
  setStatus("character-overview-status", `正在保存「${labelText}」...`);
  try {
    const nextFields = {
      ...(currentCharacterOverview.fields || {}),
      [field]: nextValue,
    };
    const saved = await apiJson(
      `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildCharacterOverviewSavePayload(nextFields, "character_overview_inline_edit", "field_direct_save")),
      },
      "保存人物校对失败。"
    );
    currentCharacterOverview = saved;
    renderCharacterOverview(saved);
    renderRun(await apiJson(`/api/web/runs/${currentRunId}`));
    characterOverviewOpen = true;
    currentCharacterOverview = saved;
    updateWorkflowState();
    setStatus("character-overview-status", `「${labelText}」已经写回这一卷。`);
  } catch (error) {
    trigger.textContent = previousText;
    setStatus("character-overview-status", error.message || "这次保存没有成功。");
  } finally {
    delete trigger.dataset.saving;
  }
}

function openCharacterOverviewIncrementalDistill() {
  const character = String(currentCharacterOverview?.character || "").trim();
  openIncrementalDistillForCharacter(character);
}

function openIncrementalDistillForCharacter(characterName) {
  const character = String(characterName || "").trim();
  if (!character || !currentRun) return;
  characterOverviewOpen = false;
  redistillPanelOpen = true;
  renderBookshelfDetail(currentRun);
  updateWorkflowState();
  const mergedCharacters = joinCharacters([character, ...parseCharacters(valueOf("redistill-characters", ""))]);
  setValue("redistill-characters", mergedCharacters);
  syncRedistillPreview();
  setStatus("redistill-status", `这轮会把「${character}」按增量方式继续补稳。`);
  el("redistill-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  el("redistill-characters")?.focus();
}

async function openCharacterOverviewSessionMode(mode) {
  const character = String(currentCharacterOverview?.character || "").trim();
  if (!character || !currentRun) return;
  await openNewDialogueSession();
  const characters = getRunCharacterNames(currentRun);
  setValue("dialogue-participants", joinCharacters(characters));
  setValue("dialogue-mode", mode);
  if (mode === "act") {
    setValue("dialogue-controlled", character);
  }
  syncModeFields();
  updateCharacterPillState();
}

function openCurrentCharacterProfileFile() {
  const character = String(currentCharacterOverview?.character || "").trim();
  if (!character || !currentRun?.file_urls) return;
  const url = currentRun.file_urls[`character_${character}`];
  if (url) {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

function renderQualitySnapshot(run) {
  const quality = run?.quality || {};
  const summaryChunking = run?.summary?.chunking || {};
  const progressChunking = run?.progress?.chunking || {};
  const focus = quality.excerpt_focus || {};
  const matched = Array.isArray(focus.matched_characters) ? focus.matched_characters : [];
  const missing = Array.isArray(focus.missing_characters) ? focus.missing_characters : [];
  const stages = Array.isArray(quality.stage_presence) ? quality.stage_presence : [];
  renderQualityPills("quality-matched", matched, "quality-matched-empty");
  renderQualityPills("quality-missing", missing, "quality-missing-empty");
  renderQualityPills("quality-stages", stages, "quality-stages-empty");

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

  const segments = [];
  if (profileCount > 0) {
    segments.push(`人物字段收束 ${profileCount} 次${profileNames ? `：${profileNames}` : ""}`);
  }
  if (relationCount > 0) {
    segments.push(`关系字段收束 ${relationCount} 次${relationPairs.length ? `：${relationPairs.slice(0, 3).join("、")}` : ""}`);
  }
  setText("quality-repairs", segments.join("；") || "暂时没有发生自动收束。", "");

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
  setText("quality-chunks", chunkSegments.join("；"), "");

  const standardChunkingVisible =
    Number(distillChunkSummary.chunk_count || 0) > 0 ||
    Number(relationChunkSummary.chunk_count || 0) > 0 ||
    String(distillChunkSummary.mode || "").trim() === "chunked" ||
    String(relationChunkSummary.mode || "").trim() === "chunked";
  const shouldShow =
    matched.length ||
    missing.length ||
    stages.length ||
    profileCount > 0 ||
    relationCount > 0 ||
    chunkedCharacters.length ||
    relationChunked ||
    standardChunkingVisible;
  toggle("quality-section", shouldShow);
  toggle("quality-empty-copy", !shouldShow);
}

function renderQualityPills(rootId, values, emptyId) {
  const root = el(rootId);
  if (!root) return;
  root.innerHTML = "";
  (values || []).forEach((value) => {
    const chip = document.createElement("span");
    chip.textContent = value;
    root.appendChild(chip);
  });
  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle(emptyId, root.childElementCount === 0);
}

function renderRunEvents(run) {
  const eventsRoot = el("events");
  if (!eventsRoot) return;
  eventsRoot.innerHTML = "";
  (run.events || []).slice(-8).forEach((event) => {
    const stageLabel = humanizeRunEventStage(String(event?.stage || "").trim());
    const message = String(event?.message || "").trim();
    const updated = formatWeakTime(String(event?.timestamp || "").trim()) || "刚刚";
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${escapeHtml(stageLabel)}</strong>
      <p>${escapeHtml(message || "这一轮有新的变化落在这里。")}</p>
      <small>${escapeHtml(updated)}</small>
    `;
    eventsRoot.appendChild(item);
  });
  toggle("timeline-empty-note", eventsRoot.childElementCount === 0);
}

function renderRunGraphLinks(run) {
  const graphLinksRoot = el("graph-links");
  if (!graphLinksRoot) return;
  graphLinksRoot.innerHTML = "";
  [
    run.file_urls?.graph_html ? { url: run.file_urls.graph_html, label: "查看关系图谱" } : null,
    run.file_urls?.graph_svg ? { url: run.file_urls.graph_svg, label: "查看 SVG" } : null,
  ]
    .filter(Boolean)
    .forEach((entry) => {
      const link = document.createElement("a");
      link.href = entry.url;
      link.textContent = entry.label;
      link.target = "_blank";
      link.rel = "noreferrer";
      graphLinksRoot.appendChild(link);
    });
  graphLinksRoot.classList.toggle("hidden", graphLinksRoot.childElementCount === 0);
  toggle("graph-empty-note", graphLinksRoot.childElementCount === 0);
  toggle("open-relation-details-button", Boolean(run?.artifact_index?.relation_graph?.relations_file));
}

function syncRunArtifacts(run) {
  renderCharacterPills(run);
  renderRedistillPills(run);
  toggle("open-persona-review-button", Boolean(run?.artifact_index?.characters?.length));
  if (run.artifact_index?.characters?.length) {
    maybePrefillChatSetup(run);
  }
}

function renderRun(run, options = {}) {
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
}

function scheduleRunPolling() {
  stopRunPolling();
  if (!currentRunId) return;
  runPollTimer = window.setTimeout(async () => {
    try {
      renderRun(await apiJson(`/api/web/runs/${currentRunId}`));
    } catch (error) {
      console.warn("poll run failed", error);
    }
  }, 1800);
}

function renderRedistillPlan(run) {
  const redistill = run?.redistill || {};
  const currentSource = getCurrentNovelSource(run);
  const sourceName = String(redistill.source_name || currentSource?.source_name || "").trim();
  const usingNewSource = Boolean(redistill.used_new_source);
  const existing = Array.isArray(redistill.existing_characters) ? redistill.existing_characters : [];
  const newcomers = Array.isArray(redistill.new_characters) ? redistill.new_characters : [];

  setText(
    "redistill-plan-title",
    usingNewSource ? "这轮会换入新的书段继续整理" : "这轮会沿用当前书段继续整理",
    ""
  );
  setText(
    "redistill-source-note",
    usingNewSource
      ? `当前已换入新的正文片段：${sourceName || "新的书页"}`
      : `当前会沿用上一轮使用的正文片段${sourceName ? `：${sourceName}` : ""}。`,
    ""
  );

  renderRedistillPlanGroup("redistill-existing-list", existing, "redistill-existing-empty");
  renderRedistillPlanGroup("redistill-new-list", newcomers, "redistill-new-empty");
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

function renderSourceHistory(run) {
  const root = el("source-history-list");
  const toggleButton = el("source-history-toggle");
  if (!root) return;
  const sources = Array.isArray(run?.novel_sources) ? [...run.novel_sources] : [];
  const currentPath = String(run?.novel_path || "").trim();
  root.innerHTML = "";

  const sortedItems = sources
    .slice()
    .sort((a, b) => String(b?.timestamp || "").localeCompare(String(a?.timestamp || "")));
  const visibleItems = sourceHistoryExpanded ? sortedItems : sortedItems.slice(0, 3);

  visibleItems.forEach((source) => {
    const card = document.createElement("article");
    const sourcePath = String(source?.source_path || "").trim();
    const current = Boolean(currentPath) && sourcePath === currentPath;
    card.className = `source-history-item${current ? " current" : ""}`;

    const title = document.createElement("div");
    title.className = "source-history-title";
    title.textContent = String(source?.source_name || "未命名书页").trim() || "未命名书页";
    if (current) {
      const badge = document.createElement("span");
      badge.className = "source-history-badge";
      badge.textContent = "当前使用中";
      title.appendChild(badge);
    }

    const meta = document.createElement("div");
    meta.className = "source-history-meta";
    const kind = source?.kind === "incremental_update" ? "增量书段" : "初始正文";
    const time = formatWeakTime(String(source?.timestamp || "").trim());
    meta.textContent = [kind, formatSourceStats(source), time].filter(Boolean).join(" · ");

    const detail = document.createElement("div");
    detail.className = "source-history-detail";
    detail.textContent = buildSourceDetailText(source, current);

    card.appendChild(title);
    card.appendChild(meta);
    if (detail.textContent) {
      card.appendChild(detail);
    }
    root.appendChild(card);
  });

  root.classList.toggle("hidden", root.childElementCount === 0);
  toggle("source-history-empty", sortedItems.length <= 1);
  if (toggleButton) {
    const canExpand = sortedItems.length > 3;
    toggleButton.classList.toggle("hidden", !canExpand);
    toggleButton.textContent = sourceHistoryExpanded ? "收起部分" : "展开全部";
  }
  setText(
    "source-history-note",
    currentPath
      ? `当前整理会基于最近一次换入的书页继续往下走。现在使用的是：${String(getCurrentNovelSource(run)?.source_name || PathNameFrom(currentPath) || "当前书页")}`
      : "当前整理会基于最近一次换入的书页继续往下走。",
    ""
  );
}

function getCurrentNovelSource(run) {
  const sources = Array.isArray(run?.novel_sources) ? run.novel_sources : [];
  const currentPath = String(run?.novel_path || "").trim();
  return sources.find((item) => String(item?.source_path || "").trim() === currentPath) || sources[sources.length - 1] || null;
}

function PathNameFrom(pathText) {
  const parts = String(pathText || "").split(/[\\/]/);
  return parts[parts.length - 1] || "";
}

function formatSourceStats(source) {
  const charCount = Number(source?.char_count || 0);
  const byteSize = Number(source?.byte_size || 0);
  if (charCount > 0) {
    return `约 ${formatCompactNumber(charCount)} 字`;
  }
  if (byteSize > 0) {
    return formatByteSize(byteSize);
  }
  return "";
}

function buildSourceDetailText(source, current) {
  const segments = [];
  if (current) {
    segments.push("本轮整理正在使用这份正文");
  }
  const byteSize = Number(source?.byte_size || 0);
  if (byteSize > 0) {
    segments.push(`文件体量 ${formatByteSize(byteSize)}`);
  }
  return segments.join("，");
}

function formatCompactNumber(value) {
  const amount = Number(value || 0);
  if (!Number.isFinite(amount) || amount <= 0) {
    return "";
  }
  if (amount >= 10000) {
    return `${(amount / 10000).toFixed(amount >= 100000 ? 0 : 1).replace(/\.0$/, "")}万`;
  }
  return String(amount);
}

function formatByteSize(value) {
  const amount = Number(value || 0);
  if (!Number.isFinite(amount) || amount <= 0) {
    return "";
  }
  if (amount >= 1024 * 1024) {
    return `${(amount / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
  }
  if (amount >= 1024) {
    return `${(amount / 1024).toFixed(1).replace(/\.0$/, "")} KB`;
  }
  return `${amount} B`;
}

function fillPersonaReviewCharacterOptions(run) {
  const select = el("persona-review-character");
  if (!select) return;
  const names = getRunCharacterNames(run);
  const currentValue = select.value;
  select.innerHTML = "";
  names.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
  if (names.includes(currentValue)) {
    select.value = currentValue;
  } else if (names.length) {
    select.value = names[0];
  }
  renderPersonaReviewCharacterOptions(names, select.value);
}

function renderPersonaReview(payload) {
  currentPersonaReview = payload;
  fillPersonaReviewFields(payload?.fields || {});
  if (payload?.character && el("persona-review-character")) {
    el("persona-review-character").value = payload.character;
  }
  renderPersonaReviewCharacterOptions(getRunCharacterNames(currentRun), valueOf("persona-review-character", ""));
}

function renderPersonaReviewCharacterOptions(names, currentValue) {
  const root = el("persona-review-character-options");
  const select = el("persona-review-character");
  if (!root || !select) return;
  root.innerHTML = "";
  if (!(names || []).length) {
    const hint = document.createElement("span");
    hint.className = "pill hint-pill";
    hint.textContent = "请先选择一卷已完成的人物";
    root.appendChild(hint);
    return;
  }

  names.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pill persona-pill";
    button.textContent = name;
    if (name === currentValue) {
      button.classList.add("active");
    }
    button.addEventListener("click", () => {
      if (select.value === name) {
        return;
      }
      select.value = name;
      renderPersonaReviewCharacterOptions(names, name);
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    root.appendChild(button);
  });
}

const PERSONA_REVIEW_FIELD_BINDINGS = [
  ["core_identity", "persona-core-identity"],
  ["story_role", "persona-story-role"],
  ["identity_anchor", "persona-identity-anchor"],
  ["temperament_type", "persona-temperament-type"],
  ["soul_goal", "persona-soul-goal"],
  ["hidden_desire", "persona-hidden-desire"],
  ["inner_conflict", "persona-inner-conflict"],
  ["self_cognition", "persona-self-cognition"],
  ["private_self", "persona-private-self"],
  ["core_traits", "persona-core-traits"],
  ["speech_style", "persona-speech-style"],
  ["cadence", "persona-cadence"],
  ["typical_lines", "persona-typical-lines"],
  ["signature_phrases", "persona-signature-phrases"],
  ["sentence_openers", "persona-sentence-openers"],
  ["sentence_endings", "persona-sentence-endings"],
  ["social_mode", "persona-social-mode"],
  ["thinking_style", "persona-thinking-style"],
  ["decision_rules", "persona-decision-rules"],
  ["reward_logic", "persona-reward-logic"],
  ["worldview", "persona-worldview"],
  ["belief_anchor", "persona-belief-anchor"],
  ["moral_bottom_line", "persona-moral-bottom-line"],
  ["restraint_threshold", "persona-restraint-threshold"],
  ["key_bonds", "persona-key-bonds"],
  ["forbidden_behaviors", "persona-forbidden-behaviors"],
  ["stress_response", "persona-stress-response"],
  ["emotion_model", "persona-emotion-model"],
  ["anger_style", "persona-anger-style"],
  ["joy_style", "persona-joy-style"],
  ["grievance_style", "persona-grievance-style"],
  ["others_impression", "persona-others-impression"],
];

const PERSONA_AUTOFILLABLE_FIELDS = new Set([
  "core_identity",
  "story_role",
  "identity_anchor",
  "temperament_type",
  "soul_goal",
  "hidden_desire",
  "inner_conflict",
  "self_cognition",
  "private_self",
  "core_traits",
  "speech_style",
  "social_mode",
  "thinking_style",
  "worldview",
  "belief_anchor",
  "moral_bottom_line",
  "key_bonds",
  "others_impression",
]);

const personaReviewAutofilledFields = new Set();

function fillPersonaReviewFields(fields) {
  personaReviewAutofilledFields.clear();
  clearAllPersonaReviewFieldFeedback();
  PERSONA_REVIEW_FIELD_BINDINGS.forEach(([field, id]) => {
    setValue(id, fields?.[field] || "");
  });
  syncPersonaReviewFieldHighlights();
  syncPersonaReviewAutofillButtons();
}

function renderPersonaAutofillReferences(payload) {
  currentPersonaAutofill = payload || null;
  const panel = el("persona-review-reference-panel");
  const summary = el("persona-review-reference-summary");
  const list = el("persona-review-reference-list");
  if (!panel || !summary || !list) return;
  const refs = Array.isArray(payload?.references) ? payload.references : [];
  panel.classList.toggle("hidden", refs.length === 0);
  panel.open = false;
  list.innerHTML = "";
  if (!refs.length) {
    summary.textContent = "网页摘要参考";
    return;
  }
  summary.textContent = `${refs.length} 条网页摘要参考`;
  refs.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "persona-reference-card";
    const title = escapeHtml(item?.title || `参考 ${index + 1}`);
    const snippet = escapeHtml(item?.snippet || "");
    const source = escapeHtml(item?.source || "");
    const query = escapeHtml(item?.query || "");
    card.innerHTML = `
      <div class="persona-reference-head">
        <strong>${title}</strong>
        ${source ? `<span>${source}</span>` : ""}
      </div>
      ${query ? `<p class="persona-reference-query">检索词：${query}</p>` : ""}
      ${snippet ? `<p class="persona-reference-snippet">${snippet}</p>` : ""}
    `;
    list.appendChild(card);
  });
}

function personaReviewFieldId(field) {
  const item = PERSONA_REVIEW_FIELD_BINDINGS.find(([key]) => key === field);
  return item ? item[1] : "";
}

function personaReviewFieldValue(field) {
  const id = personaReviewFieldId(field);
  return id ? trimmedValue(id, "") : "";
}

function personaReviewFieldNeedsAutofill(field) {
  const value = personaReviewFieldValue(field);
  if (!value) return true;
  const normalized = value.replace(/\s+/g, "");
  return ["证据不足", "资料不足", "信息不足", "暂无资料", "暂缺", "待补充"].includes(normalized);
}

function setPersonaReviewFieldFeedback(field, kind = "", message = "") {
  const id = personaReviewFieldId(field);
  const input = id ? el(id) : null;
  const card = input?.closest(".field-card");
  if (!card) return;
  let note = card.querySelector(".persona-field-feedback");
  const text = String(message || "").trim();
  if (!text) {
    if (note) {
      note.remove();
    }
    card.classList.remove("field-card-feedback-loading", "field-card-feedback-success", "field-card-feedback-error");
    return;
  }
  if (!(note instanceof HTMLElement)) {
    note = document.createElement("p");
    note.className = "persona-field-feedback";
    card.appendChild(note);
  }
  note.textContent = text;
  card.classList.remove("field-card-feedback-loading", "field-card-feedback-success", "field-card-feedback-error");
  if (kind) {
    card.classList.add(`field-card-feedback-${kind}`);
  }
}

function clearAllPersonaReviewFieldFeedback() {
  PERSONA_REVIEW_FIELD_BINDINGS.forEach(([field]) => setPersonaReviewFieldFeedback(field, "", ""));
}

function markPersonaReviewFieldAutofilled(field) {
  if (!field) return;
  personaReviewAutofilledFields.add(field);
  syncPersonaReviewFieldHighlights();
}

function clearPersonaReviewFieldAutofilled(field) {
  if (!field) return;
  personaReviewAutofilledFields.delete(field);
  syncPersonaReviewFieldHighlights();
}

function clearAllPersonaReviewAutofilledFields() {
  personaReviewAutofilledFields.clear();
  syncPersonaReviewFieldHighlights();
}

function syncPersonaReviewFieldHighlights() {
  PERSONA_REVIEW_FIELD_BINDINGS.forEach(([field, id]) => {
    const input = el(id);
    const card = input?.closest(".field-card");
    if (!card) return;
    card.classList.toggle("field-card-autofilled", personaReviewAutofilledFields.has(field));
  });
}

function syncPersonaReviewAutofillButtons() {
  document.querySelectorAll("[data-persona-autofill-field]").forEach((node) => {
    const field = node.getAttribute("data-persona-autofill-field") || "";
    if (!(node instanceof HTMLButtonElement)) return;
    const shouldShow = PERSONA_AUTOFILLABLE_FIELDS.has(field) && personaReviewFieldNeedsAutofill(field);
    node.classList.toggle("hidden", !shouldShow);
    node.disabled = Boolean(node.dataset.loading === "true");
  });
}

function renderRelationDetails(payload) {
  currentRelationDetails = payload;
  const root = el("relation-details-list");
  if (!root) return;
  root.innerHTML = "";
  (payload?.items || []).forEach((item) => {
    const card = document.createElement("article");
    card.className = "relation-detail-card";
    card.innerHTML = `
      <div class="relation-detail-head">
        <strong>${joinCharacters(item.characters || []) || item.pair_key || "未命名关系"}</strong>
        <span class="relation-detail-type">${item.relationship_type || "牵连"}</span>
      </div>
      <div class="relation-detail-metrics">信 ${item.trust} · 情 ${item.affection} · 冲 ${item.hostility}</div>
      <div class="relation-detail-copy">
        <p>${item.typical_interaction || "关系摘要暂未生成。"}</p>
        ${item.conflict_point ? `<p>冲突点：${item.conflict_point}</p>` : ""}
        ${item.relation_change ? `<p>变化：${item.relation_change}</p>` : ""}
      </div>
      <div class="relation-detail-evidence">
        <p>证据句</p>
        <ul>${(item.evidence_lines || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>
      </div>
    `;
    root.appendChild(card);
  });
  setStatus("relation-details-status", payload?.items?.length ? "" : "这张关系网暂时还没有明细。");
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
