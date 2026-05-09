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

function renderRunSummary(run) {
  setValue("redistill-characters", joinCharacters(getRunCharacterNames(run)));
  setText("redistill-status", run.redistill?.summary || "", "");
  setText("run-novel", runNovelTitle(run));
  setText("run-characters", joinCharacters(getRunCharacterNames(run) || run.locked_characters || []));
  setText("run-summary", humanizeSummary(run.summary?.status_text));
  setText("run-progress-latest", formatWeakTime(run.updated_at || "") || "刚刚", "");
  const elapsedText = String(run?.summary?.elapsed_text || run?.timing?.elapsed_text || "").trim();
  const progressCopy = String(run.progress?.message || "").trim() || "人物与关系会依次浮现。";
  const enrichedCopy =
    elapsedText && run.summary?.status_text === "workflow_complete" ? `${progressCopy} · 本次用时 ${elapsedText}` : progressCopy;
  setText("progress-copy", enrichedCopy, "");
  setText("work-overview-next-step", buildWorkOverviewNextStep(run), "");
  setText("run-progress-review", buildWorkReviewStatus(run), "");
  setText("run-progress-graph", buildWorkGraphStatus(run), "");
  renderSourceHistory(run);
  renderRedistillPlan(run);
  renderQualitySnapshot(run);
  renderCharacterReadiness(run);
  renderWorkGraphSummary(run);
  renderWorkSessionPreview(run);
  syncRedistillPreview();
}

function buildWorkOverviewNextStep(run) {
  if (!run) {
    return "先放入一本书，人物和关系才会在这里长出来。";
  }
  if (run.status === "running") {
    return "先盯住这一轮的进度，等人物落定后再决定要不要继续补人或开聊。";
  }
  if (run.status === "failed") {
    return "这一轮停在半途，最值得做的是继续蒸馏，把人物和关系重新接上。";
  }
  if (run.status === "stopped") {
    return "这卷已经收住，下一步可以继续蒸馏，也可以先回头校对已落成的人物。";
  }
  if (!getRunCharacterNames(run).length) {
    return "这一卷还没有稳定的人物包，先继续蒸馏，把角色请出来。";
  }
  if (!run?.artifact_index?.relation_graph?.relations_file) {
    return "人物已经开始成形，接下来可以先校对角色，关系图谱补出来后再看全局。";
  }
  return "这卷已经可以继续校对人物、查看关系，或者直接进入其中一幕。";
}

function buildWorkReviewStatus(run) {
  const weakCount = countWeakCharacters(run);
  if (!getRunCharacterNames(run).length) {
    return "还没有人物";
  }
  if (weakCount <= 0) {
    return "关键字段已齐";
  }
  return `还有 ${weakCount} 位待补`;
}

function buildWorkGraphStatus(run) {
  if (run?.artifact_index?.relation_graph?.relations_file) {
    return "已可查看";
  }
  if (run?.status === "running") {
    return "正在织就";
  }
  return "暂未落成";
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

function renderWorkGraphSummary(run) {
  const hasGraph = Boolean(run?.artifact_index?.relation_graph?.relations_file);
  const hasCharacters = getRunCharacterNames(run).length > 0;
  if (hasGraph) {
    setText("run-graph-status-copy", "关系线已经能看，先看牵系和张力，再决定从哪种方式入场。", "");
    return;
  }
  if (run?.status === "running") {
    setText("run-graph-status-copy", "关系网还在织，但不妨先盯住人物进度；图谱落下后会自动接到这里。", "");
    return;
  }
  if (hasCharacters) {
    setText("run-graph-status-copy", "关系图暂时还没落成，但人物已经可以继续校对，也不影响你先进入聊天。", "");
    return;
  }
  setText("run-graph-status-copy", "先把人物请出来，关系网才会在这里慢慢织成。", "");
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
    button.innerHTML = `
      <div class="work-session-head">
        <div class="work-session-title">
          <strong>${joinCharacters(item.participants || []) || "未命名会话"}</strong>
          <small>${item.mode_display || humanizeMode(item.mode) || "这一幕"}</small>
        </div>
      </div>
      <div class="work-session-meta">
        <span>${humanizeSessionStatus(item.status)}</span>
        <span>${formatWeakTime(item.updated_at) || "刚刚"}</span>
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

function renderCharacterOverviewKeyFields(fields) {
  const root = el("character-overview-key-fields");
  if (!root) return;
  root.innerHTML = "";
  CHARACTER_OVERVIEW_KEY_FIELDS.forEach(([field, label]) => {
    const value = String(fields[field] || "").trim();
    const weak = isCharacterOverviewFieldWeak(field, value);
    const card = document.createElement("article");
    card.className = `character-overview-field-card${weak ? " is-missing" : ""}`;
    const canAutofill = weak;
    card.innerHTML = `
      <div class="character-overview-field-head">
        <span>${label}</span>
        <div class="character-overview-field-actions">
          ${canAutofill ? `<button type="button" class="character-overview-mini-button" data-character-overview-field="${field}">AI补全</button>` : ""}
        </div>
      </div>
      <strong>${value || "这部分还值得继续补稳"}</strong>
      <small class="character-overview-field-hint">${buildCharacterOverviewFieldHint(field, value)}</small>
    `;
    root.appendChild(card);
  });
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
        body: JSON.stringify(nextFields),
      },
      "保存人物校对失败。"
    );
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

function openCharacterOverviewIncrementalDistill() {
  const character = String(currentCharacterOverview?.character || "").trim();
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
