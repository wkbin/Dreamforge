(() => {
  function buildWorkImportStatus(run) {
    const source = typeof getCurrentNovelSource === "function" ? getCurrentNovelSource(run) : null;
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
    if (!(typeof getRunCharacterNames === "function" ? getRunCharacterNames(run).length : 0)) {
      return "这一卷还没有稳定人物包，先继续蒸馏把角色请出来。";
    }
    if (!run?.artifact_index?.relation_graph?.relations_file) {
      return "人物已开始成形，可先校对角色，关系图谱补出后再看全局。";
    }
    return "这卷可以继续校对人物、查看关系，或直接进入其中一幕。";
  }

  function buildWorkReviewStatus(run) {
    const weakCount = countWeakCharacters(run);
    if (!(typeof getRunCharacterNames === "function" ? getRunCharacterNames(run).length : 0)) {
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
        updatedText: typeof formatWeakTime === "function" ? formatWeakTime(run.updated_at || "") : "",
      };
    });
  }

  function buildCharacterReadinessViewState(run) {
    const items = buildCharacterReadinessItems(run);
    const expanded = Boolean(window.characterReadinessExpanded);
    const canExpand = items.length > 3;
    return {
      items: expanded ? items : items.slice(0, 3),
      canExpand,
      expanded,
      toggleLabel: expanded ? "收起部分" : "展开全部",
      emptyCopy: "还没有角色卡，先继续蒸馏把人物请出来。",
    };
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

  function buildRunStatusBannerState(run) {
    const visible = Boolean(run) && (run.status === "running" || run.status === "failed" || run.status === "ready" || run.status === "stopped");
    if (!visible) {
      return { visible: false, kicker: "", stage: "", description: "" };
    }

    const progressMessage = run?.progress?.message || "这一卷还在慢慢成形。";
    const stage = String(run?.progress?.stage || "").trim();
    const summary = typeof humanizeSummary === "function" ? humanizeSummary(run?.summary?.status_text) : "";
    const stopRequested = Boolean(run?.control?.stop_requested) && run?.status === "running";

    if (run?.status === "running") {
      return {
        visible: true,
        kicker: stopRequested ? "正在停下" : "正在整理",
        stage: summary || "人物依次显形中",
        description: progressMessage || (stopRequested ? "已经收到停止请求，正在收束当前步骤。" : "这一卷还在慢慢成形，先看它往哪里走。"),
      };
    }
    if (run?.status === "failed") {
      return {
        visible: true,
        kicker: "这卷停住了",
        stage: "可以从这里重新接上",
        description: progressMessage || "这一次停在半途，继续蒸馏就能把它接回去。",
      };
    }
    if (run?.status === "stopped") {
      return {
        visible: true,
        kicker: "这卷先停下了",
        stage: "已经按你的意思收住",
        description: progressMessage || "这一轮已经停止，可以稍后继续蒸馏，或直接把它移出书架。",
      };
    }

    const stageText =
      stage === "graph_done" || run?.summary?.status_text === "workflow_complete"
        ? "人物与关系已经落稳"
        : summary || "这一卷已经可以继续";
    return {
      visible: true,
      kicker: "已经可入场",
      stage: stageText,
      description: "可以开始聊天，也可以继续补入新书段与新人物。",
    };
  }

  function buildWorkActionState(run) {
    const isRunning = Boolean(run) && run.status === "running";
    const isStopped = Boolean(run) && run.status === "stopped";
    const stopRequested = isRunning && Boolean(run?.control?.stop_requested);
    const canEnterChat = Boolean(run) && run.status === "ready" && (typeof getRunCharacterNames === "function" ? getRunCharacterNames(run).length > 0 : false);
    const canRedistill = Boolean(run) && run.status !== "running";
    const canStop = isRunning && !stopRequested;
    const hasReviewAction = Boolean(run?.artifact_index?.characters?.length);
    const hasRelation = Boolean(run?.artifact_index?.relation_graph?.relations_file);
    const hasExport =
      Boolean(run?.file_urls?.manifest) ||
      Boolean(run?.file_urls?.graph_relations_file) ||
      Boolean(run?.file_urls?.graph_html) ||
      Boolean(run?.file_urls?.graph_svg);
    const hasGraphLink = Boolean(run?.file_urls?.graph_html || run?.file_urls?.graph_svg);
    const exportPackagePending =
      Boolean(run) &&
      typeof isRunPackageExportPending === "function" &&
      isRunPackageExportPending(run?.run_id || run?.runId || "");
    const canExportPackage = Boolean(run) && run.status !== "running" && !exportPackagePending;
    const showActionNote = Boolean(run) && (isRunning || isStopped || run?.status === "failed");
    let actionNote = "";
    if (stopRequested) {
      actionNote = "已收到停止请求，正在把当前这一步收住。";
    } else if (isRunning) {
      actionNote = "这一卷还在整理中，先盯住进度，人物落定后再继续别的动作。";
    } else if (isStopped) {
      actionNote = "这一轮已经停在这里，可以继续蒸馏把它接上。";
    } else if (run?.status === "failed") {
      actionNote = "这一轮停在了半途，可以继续蒸馏把它接上。";
    }
    return {
      primaryVisible: canEnterChat || canRedistill || canStop || hasReviewAction,
      secondaryVisible: Boolean(run),
      softenSecondary: isRunning && (!hasRelation || !hasGraphLink || !hasExport),
      actionNoteVisible: showActionNote,
      actionNote,
      primaryButtons: [
        { key: "redistill", label: window.redistillPanelOpen ? "收起继续蒸馏" : "继续蒸馏", hidden: !canRedistill, disabled: !canRedistill, tone: "soft" },
        { key: "review", label: "校对人物", hidden: false, disabled: !hasReviewAction, tone: "soft" },
        { key: "chat", label: "开始聊天", hidden: !canEnterChat, disabled: !canEnterChat, tone: "primary" },
        { key: "stop", label: stopRequested ? "正在停止..." : "停止蒸馏", hidden: !isRunning, disabled: !canStop, tone: "soft" },
      ],
      secondaryButtons: [
        { key: "relations", label: "关系明细", disabled: !hasRelation },
        { key: "export_package", label: exportPackagePending ? "正在打包..." : "导出小说包", disabled: !canExportPackage, busy: exportPackagePending },
        { key: "export", label: "导出摘要", disabled: !hasExport },
        { key: "graph", label: "查看关系图", disabled: !hasGraphLink },
        { key: "timeline", label: "查看时间线", disabled: false },
      ],
    };
  }

  function buildWorkTopOverviewState(run) {
    const elapsedText = String(run?.summary?.elapsed_text || run?.timing?.elapsed_text || "").trim();
    const progressCopy = String(run?.progress?.message || "").trim() || "人物与关系会依次浮现。";
    const enrichedCopy =
      elapsedText && run?.summary?.status_text === "workflow_complete" ? `${progressCopy} · 本次用时 ${elapsedText}` : progressCopy;
    const currentSource = typeof getCurrentNovelSource === "function" ? getCurrentNovelSource(run) : null;
    return {
      title: run ? `《${runNovelTitle(run)}》` : "人物与关系正在慢慢浮现",
      progressCopy: enrichedCopy,
      nextStep: buildWorkOverviewNextStep(run),
      banner: buildRunStatusBannerState(run),
      heroMetrics: [
        { label: "当前书段", value: run ? (String(currentSource?.source_name || "").trim() || "当前书页") : "-" },
        { label: "角色总数", value: run ? `${(typeof getRunCharacterNames === "function" ? getRunCharacterNames(run).length : 0) || 0} 位` : "-" },
        { label: "总状态", value: run ? ((typeof humanizeSummary === "function" ? humanizeSummary(run?.summary?.status_text) : "") || "未开始") : "-" },
        { label: "累计耗时", value: run ? (String(run?.summary?.elapsed_text || run?.timing?.elapsed_text || "").trim() || "进行中") : "-" },
      ],
      progressMetrics: [
        { label: "正文导入", value: run ? buildWorkImportStatus(run) : "-" },
        { label: "人物蒸馏", value: run ? buildWorkDistillStatus(run) : "-" },
        { label: "关键字段校对", value: run ? buildWorkReviewStatus(run) : "-" },
        { label: "关系图谱", value: run ? buildWorkGraphStatus(run) : "-" },
        { label: "最近更新", value: run ? ((typeof formatWeakTime === "function" ? formatWeakTime(run.updated_at || "") : "") || "刚刚") : "-" },
      ],
      actions: buildWorkActionState(run),
    };
  }

  function buildWorkSummaryEvents(run) {
    return Array.isArray(run?.events)
      ? run.events.slice(-3).reverse().map((item) => ({
        stageLabel: typeof humanizeRunEventStage === "function" ? humanizeRunEventStage(String(item?.stage || "").trim()) : String(item?.stage || "").trim(),
        message: String(item?.message || "").trim() || "这一轮有新的变化落在这里。",
      }))
      : [];
  }

  function buildWorkSummaryLine(run) {
    if (!run) {
      return "先放入一本书，这里会开始归纳整卷状态。";
    }
    const title = runNovelTitle(run);
    const characterCount = typeof getRunCharacterNames === "function" ? getRunCharacterNames(run).length : 0;
    const weakCount = countWeakCharacters(run);
    if (run.status === "running") return `《${title}》还在整理中，目前已经请出了 ${characterCount || 0} 位角色。`;
    if (run.status === "failed") return `《${title}》这一轮停在半途，但已落下的角色和资料仍然能继续接着用。`;
    if (run.status === "stopped") return `《${title}》这轮已经收住，现在适合决定是继续蒸馏还是先校对人物。`;
    if (!characterCount) return `《${title}》还没有稳定的人物包，先把角色请出来。`;
    if (weakCount > 0) return `《${title}》的人物骨架已经立住一部分，但还有 ${weakCount} 位角色值得优先补稳。`;
    if (!run?.artifact_index?.relation_graph?.relations_file) return `《${title}》的人物已基本站稳，关系图谱还没落下，但不影响先开聊。`;
    return `《${title}》这卷已形成完整工作面，可以校对、看关系，也能直接入场。`;
  }

  function buildWorkSummaryBottleneck(run) {
    if (!run) return "当前还没有工作对象。";
    if (run.status === "running") return String(run.progress?.message || "").trim() || "当前瓶颈是流程仍在进行，先盯住这一轮进度。";
    if (run.status === "failed") return "这一轮已中断；最稳的接法是继续蒸馏，而不是从零重来。";
    const priority = buildWorkPriorityReviewItems(run)[0];
    if (priority?.hasEvidenceGap) return `当前最卡的是「${priority.name}」证据偏薄，建议换入更贴近他的正文片段做增量蒸馏。`;
    if (priority?.weakCount > 0) return `当前最卡的是「${priority.name}」还有 ${priority.weakCount} 处关键字段偏薄，先补这个角色最划算。`;
    if (!run?.artifact_index?.relation_graph?.relations_file) return "当前主要瓶颈是关系图谱尚未落成；不过这不阻塞聊天与校对。";
    return "当前没有明显卡点，这卷可以把重点从整理切到体验。";
  }

  function buildWorkRecommendedAction(run) {
    const priority = buildWorkPriorityReviewItems(run)[0];
    if (!run) return { buttonLabel: "开始蒸馏", title: "先放入一本书", copy: "先新建一卷，把故事请上书架。", action: "new_run", payload: "" };
    if (run.status === "running") return { buttonLabel: "查看进度", title: "先盯住当前整理进度", copy: "这一轮还在跑，先不用切太多动作，等角色再落下几位再判断。", action: "focus_timeline", payload: "" };
    if (run.status === "failed" || run.status === "stopped") return { buttonLabel: "继续蒸馏", title: "把这一轮先接上", copy: "沿着这卷继续往下走，比把已落成的人物重做一遍更划算。", action: "open_redistill", payload: "" };
    if (priority?.hasEvidenceGap) return { buttonLabel: "补这位角色", title: `先给「${priority.name}」补正文证据`, copy: "这个角色不只是字段缺字，而是素材偏薄；优先增量蒸馏更有效。", action: "redistill_character", payload: priority.name };
    if (priority?.weakCount > 0) return { buttonLabel: "打开角色页", title: `先补稳「${priority.name}」`, copy: "先把最薄的角色补稳，这样整卷对话信任感提升最快。", action: "open_character", payload: priority.name };
    if (!run?.artifact_index?.relation_graph?.relations_file) return { buttonLabel: "开始聊天", title: "人物已经够用，可以先入场", copy: "关系图还没落下，但不影响体验；可以先开一局，回头再补图谱。", action: "start_chat", payload: "" };
    return { buttonLabel: "查看关系", title: "先看整卷关系", copy: "人物和图谱都已稳定，先看全局关系，再决定从谁入场。", action: "open_relations", payload: "" };
  }

  function buildQualitySnapshotState(run) {
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
    const profileNames = typeof joinCharacters === "function" ? joinCharacters(profileRepairs.characters || []) : "";
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
    if (profileCount > 0) repairSegments.push(`人物字段收束 ${profileCount} 次${profileNames ? `：${profileNames}` : ""}`);
    if (relationCount > 0) repairSegments.push(`关系字段收束 ${relationCount} 次${relationPairs.length ? `：${relationPairs.slice(0, 3).join("、")}` : ""}`);
    const chunkSegments = [];
    if (distillChunkSummary.mode === "chunked" || Number(distillChunkSummary.chunk_count || 0) > 1) {
      const currentChunk = Number(distillChunkProgress.current_chunk || 0);
      const totalChunks = Number(distillChunkSummary.chunk_count || distillChunkProgress.chunk_count || 0);
      const mergeStatus = String(distillChunkSummary.merge_status || distillChunkProgress.merge_status || "").trim();
      const currentLabel = String(distillChunkProgress.current_label || "").trim();
      let line = `人物实际分为 ${totalChunks} 块`;
      if (currentChunk > 0 && totalChunks > 0) line += `，当前进行到 ${currentChunk}/${totalChunks}`;
      if (currentLabel) line += `（${currentLabel}）`;
      if (mergeStatus && mergeStatus !== "pending") line += `，汇总状态：${mergeStatus === "running" ? "正在汇总" : "已汇总"}`;
      chunkSegments.push(line);
    } else if (chunkedCharacters.length) {
      chunkSegments.push(`人物实际分为 ${chunkedCharacters.reduce((total, [, item]) => total + Number(item?.chunk_count || 0), 0)} 块：${chunkedCharacters.map(([name, item]) => `${name}${Number(item?.chunk_count || 1)}块`).join("、")}`);
    } else {
      chunkSegments.push("人物蒸馏这轮没有触发分批。");
    }
    if (relationChunkSummary.mode === "chunked" || Number(relationChunkSummary.chunk_count || 0) > 1) {
      const currentChunk = Number(relationChunkProgress.current_chunk || 0);
      const totalChunks = Number(relationChunkSummary.chunk_count || relationChunkProgress.chunk_count || 0);
      const mergeStatus = String(relationChunkSummary.merge_status || relationChunkProgress.merge_status || "").trim();
      const currentLabel = String(relationChunkProgress.current_label || "").trim();
      let line = `关系抽取实际分为 ${totalChunks} 块`;
      if (currentChunk > 0 && totalChunks > 0) line += `，当前进行到 ${currentChunk}/${totalChunks}`;
      if (currentLabel) line += `（${currentLabel}）`;
      if (mergeStatus && mergeStatus !== "pending") line += `，汇总状态：${mergeStatus === "running" ? "正在汇总" : "已汇总"}`;
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
    const visible = Boolean(matched.length) || Boolean(missing.length) || Boolean(stages.length) || profileCount > 0 || relationCount > 0 || Boolean(chunkedCharacters.length) || relationChunked || standardChunkingVisible;
    return { visible, open: Boolean(run?.status === "running"), emptyCopyVisible: !visible, matched, missing, stages, repairsText: repairSegments.join("；") || "暂时没有发生自动收束。", chunksText: chunkSegments.join("；") };
  }

  function buildWorkSummaryViewState(run) {
    const recommendation = buildWorkRecommendedAction(run);
    return { summaryLine: buildWorkSummaryLine(run), bottleneck: buildWorkSummaryBottleneck(run), events: buildWorkSummaryEvents(run), recommendation, quality: buildQualitySnapshotState(run) };
  }

  function buildWorkPriorityReviewViewState(run) {
    return {
      items: buildWorkPriorityReviewItems(run),
      emptyCopy: "目前没有明显掉队角色，可以直接开聊或查看关系图。",
    };
  }

  function buildWorkGraphSummaryState(run) {
    const hasGraph = Boolean(run?.artifact_index?.relation_graph?.relations_file);
    const graphFailed = String(run?.summary?.graph_status || "").trim() === "failed" || String(run?.progress?.graph_status || "").trim() === "failed";
    const hasCharacters = typeof getRunCharacterNames === "function" ? getRunCharacterNames(run).length > 0 : false;
    if (hasGraph) return { badgeText: "已完成", badgeTone: "stable", copy: "关系线已经能看，先看牵系和张力，再决定从哪种方式入场。" };
    if (graphFailed) return { badgeText: "失败可跳过", badgeTone: "weak", copy: "这轮关系图谱生成失败，但不会阻塞聊天；可以先入场，稍后再补图谱。" };
    if (run?.status === "running") return { badgeText: "进行中", badgeTone: "warning", copy: "关系网还在织，但不妨先盯住人物进度；图谱落下后会自动接到这里。" };
    if (hasCharacters) return { badgeText: "待补图谱", badgeTone: "warning", copy: "关系图暂时还没落成，但人物已经可以继续校对，也不影响你先进入聊天。" };
    return { badgeText: "未开始", badgeTone: "warning", copy: "先把人物请出来，关系网才会在这里慢慢织成。" };
  }

  function buildWorkGraphLinks(run) {
    return [
      run?.file_urls?.graph_html ? { url: run.file_urls.graph_html, label: "查看关系图谱" } : null,
      run?.file_urls?.graph_svg ? { url: run.file_urls.graph_svg, label: "查看 SVG" } : null,
    ].filter(Boolean);
  }

  function buildWorkSessionPreviewState(run) {
    const novelTitle = runNovelTitle(run);
    const characterNames = typeof getRunCharacterNames === "function" ? getRunCharacterNames(run) : [];
    const allSessions = (window.recentSessionsCache || [])
      .filter((item) => normalizeNovelTitle(item?.novel_id || "") === novelTitle)
      .sort((left, right) => String(right?.updated_at || "").localeCompare(String(left?.updated_at || "")));
    const rankedSessions = [...allSessions].sort((left, right) => {
      const rightMatch = Boolean(findMatchedSessionCharacter(getSessionPreviewSnippet(right), characterNames).character);
      const leftMatch = Boolean(findMatchedSessionCharacter(getSessionPreviewSnippet(left), characterNames).character);
      if (rightMatch !== leftMatch) return Number(rightMatch) - Number(leftMatch);
      return String(right?.updated_at || "").localeCompare(String(left?.updated_at || ""));
    });
    const expanded = Boolean(window.workSessionPreviewExpanded);
    return {
      canExpand: rankedSessions.length > 3,
      expanded,
      toggleLabel: expanded ? "收起部分" : "展开全部",
      latest: allSessions[0] ? { label: `继续：${(typeof joinCharacters === "function" ? joinCharacters(allSessions[0].participants || []) : "") || "最近会话"}`, raw: allSessions[0] } : null,
      items: (expanded ? rankedSessions : rankedSessions.slice(0, 3)).map((item) => {
        const snippet = getSessionPreviewSnippet(item);
        const matchInfo = findMatchedSessionCharacter(snippet, characterNames);
        return {
          label: (typeof joinCharacters === "function" ? joinCharacters(item?.participants || []) : "") || "未命名会话",
          modeLabel: item?.mode_display || (typeof humanizeMode === "function" ? humanizeMode(item?.mode) : item?.mode) || "这一幕",
          participantCount: Array.isArray(item?.participants) ? item.participants.length : 0,
          hasMatch: Boolean(matchInfo.character),
          matchText: matchInfo.character ? `命中 ${matchInfo.character} · ${matchInfo.reason}` : "",
          snippet,
          updatedText: (typeof formatWeakTime === "function" ? formatWeakTime(item?.updated_at) : "") || "刚刚",
          statusText: typeof humanizeSessionStatus === "function" ? humanizeSessionStatus(item?.status) : (item?.status || "未知"),
          raw: item,
        };
      }),
      emptyCopy: "还没有会话，随时可以从下方三种方式开局。",
    };
  }

  function buildWorkEntryViewState(run) {
    return {
      graph: { ...buildWorkGraphSummaryState(run), links: buildWorkGraphLinks(run), emptyCopy: "关系图暂未生成，稍后会自动补到这里。" },
      sessions: buildWorkSessionPreviewState(run),
      quickModes: [
        { mode: "observe", label: "旁观此局" },
        { mode: "act", label: "化身书中人" },
        { mode: "insert", label: "以自己入场" },
      ],
    };
  }

  window.__ZAOMENG_BUILD_WORK_SUMMARY_STATE__ = buildWorkSummaryViewState;
  window.__ZAOMENG_BUILD_WORK_PRIORITY_STATE__ = buildWorkPriorityReviewViewState;
  window.__ZAOMENG_BUILD_WORK_ENTRY_STATE__ = buildWorkEntryViewState;
  window.__ZAOMENG_BUILD_WORK_CHARACTER_STATE__ = buildCharacterReadinessViewState;
  window.__ZAOMENG_BUILD_WORK_TOP_OVERVIEW_STATE__ = buildWorkTopOverviewState;

  window.__ZAOMENG_WORK_OVERVIEW_STATE__ = {
    buildCharacterReadinessItems,
    buildCharacterReadinessViewState,
    buildQualitySnapshotState,
    buildRunStatusBannerState,
    buildWorkActionState,
    buildWorkDistillStatus,
    buildWorkEntryViewState,
    buildWorkGraphLinks,
    buildWorkGraphStatus,
    buildWorkGraphSummaryState,
    buildWorkImportStatus,
    buildWorkOverviewNextStep,
    buildWorkPriorityReviewViewState,
    buildWorkPriorityHeadline,
    buildWorkPriorityReason,
    buildWorkPriorityReviewItems,
    buildWorkRecommendedAction,
    buildWorkReviewStatus,
    buildWorkSessionPreviewState,
    buildWorkSummaryBottleneck,
    buildWorkSummaryEvents,
    buildWorkSummaryLine,
    buildWorkSummaryViewState,
    buildWorkTopOverviewState,
    countWeakCharacters,
  };
})();
