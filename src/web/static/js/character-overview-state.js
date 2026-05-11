(() => {
  const KEY_FIELDS = [
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

  const ADVANCED_GROUPS = [
    ["内核细调", ["hidden_desire", "inner_conflict", "self_cognition", "private_self", "social_mode", "thinking_style", "decision_rules", "reward_logic", "others_impression"]],
    ["对白细调", ["cadence", "typical_lines", "signature_phrases", "sentence_openers", "sentence_endings"]],
    ["情绪细调", ["forbidden_behaviors", "emotion_model", "anger_style", "joy_style", "grievance_style"]],
  ];

  const FIELD_LABELS = {
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

  function fieldLabel(field) {
    return FIELD_LABELS[String(field || "").trim()] || String(field || "").trim();
  }

  function isFieldWeak(field, value) {
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

  function formatAutofillSource(sourceMode) {
    if (sourceMode === "web_fallback") {
      return "联网参考";
    }
    if (sourceMode === "model_knowledge") {
      return "模型知识";
    }
    return "AI";
  }

  function buildChangeTimelineItems(events, character, formatWeakTimeFn) {
    const name = String(character || "").trim();
    if (!name) return [];
    const safeEvents = Array.isArray(events) ? events : [];
    return safeEvents
      .filter((item) => String(item?.character || "").trim() === name && String(item?.stage || "").trim() === "persona_review_saved")
      .slice()
      .reverse()
      .slice(0, 8)
      .map((item) => {
        const reviewSource = String(item?.review_source || "").trim();
        const reviewNote = String(item?.review_note || "").trim();
        const changedFields = Array.isArray(item?.changed_fields) ? item.changed_fields.filter(Boolean) : [];
        const changedLabels = changedFields.map((field) => fieldLabel(field)).slice(0, 3);
        let title = "字段已写回";
        let badge = "手动校对";
        let copy = String(item?.message || "").trim() || "这次改动已经写回这一卷。";
        if (reviewSource === "character_overview_autofill") {
          title = "AI补全已写回";
          badge = formatAutofillSource(reviewNote);
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
          updated: typeof formatWeakTimeFn === "function" ? formatWeakTimeFn(item?.timestamp || "") || "刚刚" : "刚刚",
        };
      });
  }

  function buildHealthSnapshot(fields, updatedAt, formatWeakTimeFn) {
    const values = fields || {};
    let filledKeyCount = 0;
    let weakKeyCount = 0;
    KEY_FIELDS.forEach(([field]) => {
      const value = String(values[field] || "").trim();
      if (value) {
        filledKeyCount += 1;
      }
      if (isFieldWeak(field, value)) {
        weakKeyCount += 1;
      }
    });
    const advancedFieldNames = ADVANCED_GROUPS.flatMap(([, fieldNames]) => fieldNames);
    const advancedFilledCount = advancedFieldNames.filter((field) => String(values[field] || "").trim()).length;
    const totalFieldCount = KEY_FIELDS.length + advancedFieldNames.length;
    const filledFieldCount = filledKeyCount + advancedFilledCount;
    const completeness = totalFieldCount > 0 ? Math.round((filledFieldCount / totalFieldCount) * 100) : 0;
    const stableKeyCount = Math.max(0, KEY_FIELDS.length - weakKeyCount);
    const healthTone = weakKeyCount <= 0 ? "stable" : weakKeyCount >= 4 ? "weak" : "warning";
    const healthText = weakKeyCount <= 0 ? "关键字段已齐" : weakKeyCount >= 4 ? "待校对" : "待补全";
    const updatedText = typeof formatWeakTimeFn === "function" ? formatWeakTimeFn(updatedAt || "") || "刚刚" : "刚刚";
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

  function buildEvidenceSnapshot(run, character, formatWeakTimeFn, formatSourceStatsFn, getCurrentNovelSourceFn) {
    const name = String(character || "").trim();
    const focus = run?.quality?.excerpt_focus || {};
    const missing = new Set(Array.isArray(focus.missing_characters) ? focus.missing_characters : []);
    const matched = new Set(Array.isArray(focus.matched_characters) ? focus.matched_characters : []);
    const currentSource = typeof getCurrentNovelSourceFn === "function" ? getCurrentNovelSourceFn(run) : null;
    const allSources = Array.isArray(run?.novel_sources) ? run.novel_sources : [];
    const currentSourceName = String(currentSource?.source_name || "").trim() || "当前书页";
    const currentSourceKind = currentSource?.kind === "incremental_update" ? "增量书段" : "初始正文";
    const currentSourceStats = typeof formatSourceStatsFn === "function" ? formatSourceStatsFn(currentSource) : "";
    const updatedText = typeof formatWeakTimeFn === "function" ? formatWeakTimeFn(run?.updated_at || "") || "刚刚" : "刚刚";
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
      evidenceLabel: run?.status === "running" ? "仍在整理" : "等待更多证据",
      evidenceCopy: run?.status === "running" ? "这一轮还在继续，人物证据可能还会再长出来。" : "这位角色暂时没有明确命中或缺证据标记，先结合字段薄弱程度判断是否要继续补。",
      sourceLabel: currentSourceName,
      sourceCopy: [currentSourceKind, currentSourceStats].filter(Boolean).join(" · ") || "当前整理基于这份书段继续往下走。",
      traceLabel: `${allSources.length || 1} 段来源`,
      traceCopy: `最近更新 ${updatedText}。你可以先在角色页补字段，再决定要不要换入新书段。`,
      recommendationLabel: "建议动作",
      recommendationCopy: "如果说话方式和灵魂目标还薄，先补字段；如果整个人都虚，再考虑增量蒸馏。",
    };
  }

  function findLatestRunEvent(events, character, stage = "") {
    const name = String(character || "").trim();
    const expectedStage = String(stage || "").trim();
    const safeEvents = Array.isArray(events) ? events : [];
    return safeEvents
      .slice()
      .reverse()
      .find((item) => {
        const eventCharacter = String(item?.character || "").trim();
        const eventStage = String(item?.stage || "").trim();
        return (!name || eventCharacter === name) && (!expectedStage || eventStage === expectedStage);
      });
  }

  function buildReviewCopy(reviewEvent, formatWeakTimeFn) {
    const timestampText = typeof formatWeakTimeFn === "function" ? formatWeakTimeFn(reviewEvent?.timestamp || "") || "最近" : "最近";
    const reviewSource = String(reviewEvent?.review_source || "").trim();
    const reviewNote = String(reviewEvent?.review_note || "").trim();
    const changedFields = Array.isArray(reviewEvent?.changed_fields) ? reviewEvent.changed_fields.filter(Boolean) : [];
    const changedLabels = changedFields.map((field) => fieldLabel(field)).slice(0, 3);
    const changedCopy = changedLabels.length ? `涉及 ${changedLabels.join("、")}。` : "";
    if (reviewSource === "character_overview_autofill") {
      const sourceLabel = formatAutofillSource(reviewNote);
      return `${timestampText}通过 ${sourceLabel} 自动写回过补全；${changedCopy || "仍建议人工扫一眼关键字段。"}`.replace("；", "，").trim();
    }
    if (reviewSource === "character_overview_inline_edit") {
      return `${timestampText}在角色页直接保存过字段。${changedCopy}`.trim();
    }
    return `${timestampText}保存过人物校对。${changedCopy}`.trim();
  }

  function buildRedistillSignal(run, character, getCurrentNovelSourceFn) {
    const name = String(character || "").trim();
    const redistill = run?.redistill || {};
    const existing = new Set(Array.isArray(redistill.existing_characters) ? redistill.existing_characters : []);
    const newcomers = new Set(Array.isArray(redistill.new_characters) ? redistill.new_characters : []);
    const currentSource = typeof getCurrentNovelSourceFn === "function" ? getCurrentNovelSourceFn(run) : null;
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
    if (run?.status === "running") {
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

  function buildTrustSignals(options = {}) {
    const payload = options.payload || {};
    const healthSnapshot = options.healthSnapshot || {};
    const evidenceSnapshot = options.evidenceSnapshot || {};
    const autofillItems = Array.isArray(options.autofillItems) ? options.autofillItems : [];
    const reviewEvent = options.reviewEvent || null;
    const redistillSignal = options.redistillSignal || { value: "暂无近期增量", copy: "", tone: "neutral" };
    const formatWeakTimeFn = options.formatWeakTime;
    const character = String(payload?.character || "").trim();
    const lastAutofill = autofillItems[0] || null;
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
          ? `${lastAutofill.label} 刚由 ${formatAutofillSource(lastAutofill.sourceMode)}写回，建议再用对话测试口气。`
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
          ? buildReviewCopy(reviewEvent, formatWeakTimeFn)
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

  function buildFieldTags(field, value, evidenceSnapshot, options = {}) {
    const text = String(value || "").trim();
    const tags = [];
    const recentAutofill = options.recentAutofill || null;
    if (recentAutofill) {
      tags.push({ label: "AI补全", tone: "stable" });
    }
    if (!text) {
      tags.push({ label: "待补", tone: "weak" });
    } else if (!recentAutofill) {
      tags.push({ label: options.editableProfilePath ? "校对稿" : "蒸馏稿", tone: "neutral" });
    }
    if (evidenceSnapshot?.evidenceLabel === "证据偏薄" && ["core_identity", "story_role", "soul_goal", "key_bonds"].includes(field)) {
      tags.push({ label: "证据薄", tone: "weak" });
    }
    return tags.slice(0, 3);
  }

  function buildFieldHint(field, value) {
    const text = String(value || "").trim();
    if (!text) {
      return "这块还空着，可以先让 AI 补一版，再进人物校对里细修。";
    }
    if (isFieldWeak(field, text)) {
      return "这块已经有轮廓，但还偏薄，适合继续补稳。";
    }
    return "这块已经能支撑当前角色概览。";
  }

  function buildVoiceSummaryItems(fields) {
    const values = fields || {};
    return [
      ["说话方式", values.speech_style || "这部分还可以继续抠细。"],
      ["代表句", values.typical_lines || values.signature_phrases || "人物口气还没有完全落稳。"],
      ["句子习惯", [values.sentence_openers, values.sentence_endings].filter(Boolean).join(" / ") || "起句和句尾还可以继续补。"],
    ];
  }

  function buildRelationSummaryItems(fields) {
    const values = fields || {};
    return [
      ["重要牵系", values.key_bonds || "这部分还没有完全落下来。"],
      ["气质底色", values.temperament_type || "气质底色还可以继续补稳。"],
      ["世界观", values.worldview || "世界观还没有完全成形。"],
    ];
  }

  function buildAdvancedGroupsView(fields, expandedGroups) {
    const values = fields || {};
    const expandedSet = expandedGroups instanceof Set ? expandedGroups : new Set();
    return ADVANCED_GROUPS.map(([title, fieldNames]) => {
      const items = fieldNames
        .map((field) => {
          const value = String(values[field] || "").trim();
          return value ? { field, label: fieldLabel(field), value } : null;
        })
        .filter(Boolean);
      return {
        title,
        fieldNames,
        items,
        expanded: expandedSet.has(title),
        previewText: items.slice(0, 2).map((item) => `${item.label}：${item.value}`).join("；") || "这一组还可以继续补更多细节，不必一次写满。",
      };
    });
  }

  window.__ZAOMENG_CHARACTER_OVERVIEW_STATE__ = {
    ADVANCED_GROUPS,
    FIELD_LABELS,
    KEY_FIELDS,
    buildAdvancedGroupsView,
    buildChangeTimelineItems,
    buildEvidenceSnapshot,
    buildFieldHint,
    buildFieldTags,
    buildHealthSnapshot,
    buildRelationSummaryItems,
    buildRedistillSignal,
    buildReviewCopy,
    buildTrustSignals,
    buildVoiceSummaryItems,
    fieldLabel,
    findLatestRunEvent,
    formatAutofillSource,
    isFieldWeak,
  };
})();
