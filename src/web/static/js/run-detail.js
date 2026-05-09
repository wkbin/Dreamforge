function renderRunSummary(run) {
  setValue("redistill-characters", joinCharacters(getRunCharacterNames(run)));
  setText("redistill-status", run.redistill?.summary || "", "");
  setText("run-novel", runNovelTitle(run));
  setText("run-characters", joinCharacters(getRunCharacterNames(run) || run.locked_characters || []));
  setText("run-summary", humanizeSummary(run.summary?.status_text));
  const elapsedText = String(run?.summary?.elapsed_text || run?.timing?.elapsed_text || "").trim();
  const progressCopy = String(run.progress?.message || "").trim() || "人物与关系会依次浮现。";
  const enrichedCopy =
    elapsedText && run.summary?.status_text === "workflow_complete" ? `${progressCopy} · 本次用时 ${elapsedText}` : progressCopy;
  setText("progress-copy", enrichedCopy, "");
  renderSourceHistory(run);
  renderRedistillPlan(run);
  renderQualitySnapshot(run);
  syncRedistillPreview();
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
    const item = document.createElement("li");
    item.textContent = event.message || event.stage || "";
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
