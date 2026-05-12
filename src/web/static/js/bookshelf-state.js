(() => {
  function formatBookshelfDeleteStatus(title, payload) {
    const runCount = Number(payload?.deleted_run_count || 0);
    const sessionCount = Number(payload?.deleted_session_count || 0);
    return `已移走《${title}》，同时删除 ${runCount} 轮记录 / ${sessionCount} 个会话。`;
  }

  function getBookshelfCardState(run) {
    if (run?.status === "failed") return { className: "is-failed" };
    if (run?.status === "stopped") return { className: "is-stopped" };
    if (run?.status === "running") return { className: "is-running" };
    if (run?.status === "ready") return { className: "is-ready" };
    return { className: "" };
  }

  function buildBookshelfItems(runs, currentRunIdValue = "", currentRunValue = null) {
    const groupedRuns = typeof aggregateRunsByNovel === "function" ? aggregateRunsByNovel(runs || []) : (runs || []);
    return groupedRuns.map((run) => {
      const status = typeof humanizeSummary === "function" ? humanizeSummary(run?.summary?.status_text) : String(run?.summary?.status_text || "未开始");
      const updatedAt = typeof formatWeakTime === "function" ? formatWeakTime(run?.updated_at || "") : "";
      const characterCount = typeof getRunCharacterNames === "function" ? getRunCharacterNames(run).length : 0;
      const cardState = getBookshelfCardState(run);
      const sameNovel = currentRunValue && typeof runNovelTitle === "function" && runNovelTitle(run) === runNovelTitle(currentRunValue);
      return {
        run,
        runId: String(run?.run_id || ""),
        title: typeof runNovelTitle === "function" ? runNovelTitle(run) : String(run?.novel_name || "未命名书卷"),
        status,
        updatedAt: updatedAt || "刚刚放上书架",
        characterCopy: characterCount ? `已落成人物 ${characterCount}` : "人物仍在整理",
        className: cardState.className,
        current: String(run?.run_id || "") === String(currentRunIdValue || "") || Boolean(sameNovel),
        deletingDisabled: run?.status === "running",
        deleteTitle: run?.status === "running" ? "这本书还在整理中，暂时不能删除" : `删除《${typeof runNovelTitle === "function" ? runNovelTitle(run) : "这本书"}》`,
      };
    });
  }

  window.__ZAOMENG_BOOKSHELF_STATE__ = {
    buildBookshelfItems,
    formatBookshelfDeleteStatus,
    getBookshelfCardState,
  };
})();
