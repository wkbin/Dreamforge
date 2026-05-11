(() => {
  function getCurrentNovelSource(run) {
    const sources = Array.isArray(run?.novel_sources) ? run.novel_sources : [];
    const currentPath = String(run?.novel_path || "").trim();
    return sources.find((item) => String(item?.source_path || "").trim() === currentPath) || sources[sources.length - 1] || null;
  }

  function pathNameFrom(pathText) {
    const parts = String(pathText || "").split(/[\\/]/);
    return parts[parts.length - 1] || "";
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

  function buildRunEventsViewState(run, formatWeakTimeFn, humanizeRunEventStageFn) {
    return (Array.isArray(run?.events) ? run.events : []).slice(-8).map((event) => ({
      stageLabel: typeof humanizeRunEventStageFn === "function" ? humanizeRunEventStageFn(String(event?.stage || "").trim()) : String(event?.stage || "").trim(),
      message: String(event?.message || "").trim() || "这一轮有新的变化落在这里。",
      updated: typeof formatWeakTimeFn === "function" ? formatWeakTimeFn(String(event?.timestamp || "").trim()) || "刚刚" : "刚刚",
    }));
  }

  function buildRedistillPlanState(run) {
    const redistill = run?.redistill || {};
    const currentSource = getCurrentNovelSource(run);
    const sourceName = String(redistill.source_name || currentSource?.source_name || "").trim();
    const usingNewSource = Boolean(redistill.used_new_source);
    const recentChanges = (Array.isArray(redistill.recent_changes) ? redistill.recent_changes : []).map((item) => {
      const labels = Array.isArray(item?.highlight_field_labels) ? item.highlight_field_labels.filter(Boolean) : [];
      const changedCount = Number(item?.changed_count || 0);
      const metaBits = [];
      if (labels.length) {
        metaBits.push(`重点：${labels.join("、")}`);
      }
      if (changedCount > 0) {
        metaBits.push(`共 ${changedCount} 项`);
      }
      return {
        title: String(item?.character || "角色").trim() || "角色",
        summary: String(item?.summary || "").trim() || "这一轮有新的字段变化落了下来。",
        meta: metaBits.join(" · "),
      };
    });
    return {
      title: usingNewSource ? "这轮会换入新的书段继续整理" : "这轮会沿用当前书段继续整理",
      sourceNote: usingNewSource
        ? `当前已换入新的正文片段：${sourceName || "新的书页"}`
        : `当前会沿用上一轮使用的正文片段${sourceName ? `：${sourceName}` : ""}。`,
      existing: Array.isArray(redistill.existing_characters) ? redistill.existing_characters : [],
      newcomers: Array.isArray(redistill.new_characters) ? redistill.new_characters : [],
      recentChanges,
      showChanges: recentChanges.length > 0,
    };
  }

  function buildSourceHistoryViewState(run, expanded, formatWeakTimeFn) {
    const sources = Array.isArray(run?.novel_sources) ? [...run.novel_sources] : [];
    const currentPath = String(run?.novel_path || "").trim();
    const sortedItems = sources
      .slice()
      .sort((a, b) => String(b?.timestamp || "").localeCompare(String(a?.timestamp || "")));
    const visibleItems = expanded ? sortedItems : sortedItems.slice(0, 3);
    return {
      items: visibleItems.map((source) => {
        const sourcePath = String(source?.source_path || "").trim();
        const current = Boolean(currentPath) && sourcePath === currentPath;
        return {
          current,
          title: String(source?.source_name || "未命名书页").trim() || "未命名书页",
          meta: [
            source?.kind === "incremental_update" ? "增量书段" : "初始正文",
            formatSourceStats(source),
            typeof formatWeakTimeFn === "function" ? formatWeakTimeFn(String(source?.timestamp || "").trim()) : "",
          ].filter(Boolean).join(" · "),
          detail: buildSourceDetailText(source, current),
        };
      }),
      emptyVisible: sortedItems.length <= 1,
      canExpand: sortedItems.length > 3,
      toggleLabel: expanded ? "收起部分" : "展开全部",
      note: currentPath
        ? `当前整理会基于最近一次换入的书页继续往下走。现在使用的是：${String(getCurrentNovelSource(run)?.source_name || pathNameFrom(currentPath) || "当前书页")}`
        : "当前整理会基于最近一次换入的书页继续往下走。",
    };
  }

  window.__ZAOMENG_RUN_DETAIL_SUPPORT_STATE__ = {
    buildRedistillPlanState,
    buildRunEventsViewState,
    buildSourceDetailText,
    buildSourceHistoryViewState,
    formatByteSize,
    formatCompactNumber,
    formatSourceStats,
    getCurrentNovelSource,
    pathNameFrom,
  };
})();
