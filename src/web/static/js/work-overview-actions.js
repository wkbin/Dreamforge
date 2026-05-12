(() => {
  const bridgeTools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
  const characterOverviewActions = () => window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__ || {};

  function openCharacterOverviewBridge(name = "") {
    const target = String(name || "").trim();
    if (!target) {
      return Promise.resolve(null);
    }
    const actions = characterOverviewActions();
    if (typeof actions.openCharacterOverview === "function") {
      return Promise.resolve(actions.openCharacterOverview(target));
    }
    return Promise.reject(new Error("人物档案暂时没有载入。"));
  }

  function openIncrementalDistillBridge(name = "") {
    const target = String(name || "").trim();
    if (!target) {
      return false;
    }
    const actions = characterOverviewActions();
    if (typeof actions.openIncrementalDistillForCharacter === "function") {
      actions.openIncrementalDistillForCharacter(target);
      return true;
    }
    return false;
  }

  function openSummaryExportBridge() {
    const target =
      currentRun?.file_urls?.manifest ||
      currentRun?.file_urls?.graph_relations_file ||
      currentRun?.file_urls?.graph_html ||
      currentRun?.file_urls?.graph_svg ||
      "";
    if (!target) {
      setStatus("bookshelf-status", "当前没有可导出的摘要文件。");
      return false;
    }
    window.open(target, "_blank", "noopener,noreferrer");
    return true;
  }

  function openTimelineBridge() {
    el("events")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function publishRunOverviewUi(source, overrides = {}) {
    if (typeof publishLegacyUiState === "function") {
      publishLegacyUiState(source, overrides);
    }
  }

  function openCharacterWithStatus(name = "") {
    openCharacterOverviewBridge(name).catch((error) => {
      setStatus("bookshelf-status", error.message || "人物档案暂时没有载入。");
    });
  }

  function openDialogueWithStatus() {
    openNewDialogueSession().catch((error) => {
      setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。");
    });
  }

  function openRelationsWithStatus() {
    openRelationDetails().catch((error) => {
      setStatus("bookshelf-status", error.message || "关系明细暂时没有载入。");
    });
  }

  function openPreviewSessionWithStatus(item) {
    openWorkSessionFromPreviewItem(item).catch((error) => {
      setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。");
    });
  }

  function toggleRedistillPanel() {
    if (!currentRunId) return;
    redistillPanelOpen = !redistillPanelOpen;
    renderBookshelfDetail(currentRun);
    updateWorkflowState();
    if (redistillPanelOpen) {
      el("redistill-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      el("redistill-characters")?.focus();
    }
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
      if (!openIncrementalDistillBridge(payload)) {
        setStatus("redistill-status", "角色增量能力暂时没有载入。");
      }
      return;
    }
    if (action === "open_character") {
      openCharacterWithStatus(payload);
      return;
    }
    if (action === "start_chat") {
      openDialogueWithStatus();
      return;
    }
    if (action === "open_relations") {
      openRelationsWithStatus();
    }
  }

  const actions = {
    handleRecommended(action = "", payload = "") {
      handleWorkRecommendedAction(action, payload);
    },
    openPriorityCharacter(name = "") {
      openCharacterWithStatus(name);
    },
    openCharacterReadiness(name = "") {
      openCharacterWithStatus(name);
    },
    toggleCharacterReadiness() {
      characterReadinessExpanded = !characterReadinessExpanded;
      publishRunOverviewUi("work-character-toggled");
    },
    redistillPriorityCharacter(name = "") {
      if (!openIncrementalDistillBridge(name)) {
        setStatus("redistill-status", "角色增量能力暂时没有载入。");
      }
    },
    openEntrySession(item) {
      openPreviewSessionWithStatus(item);
    },
    toggleEntrySessions() {
      workSessionPreviewExpanded = !workSessionPreviewExpanded;
      publishRunOverviewUi("work-entry-sessions-toggled");
    },
    toggleSourceHistory() {
      sourceHistoryExpanded = !sourceHistoryExpanded;
      publishRunOverviewUi("source-history-toggled");
    },
    openEntryMode(mode = "observe") {
      openQuickDialogueMode(String(mode || "observe").trim()).catch((error) => {
        setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。");
      });
    },
    toggleTopRedistill() {
      toggleRedistillPanel();
    },
    openTopReview() {
      openWorkCharacterReview().catch((error) => {
        setStatus("bookshelf-status", error.message || "人物档案暂时没有载入。");
      });
    },
    openTopChat() {
      openDialogueWithStatus();
    },
    stopTopRun() {
      handleStopRun().catch((error) => {
        setStatus("bookshelf-status", error.message || "这次停止没有成功。");
      });
    },
    openTopRelations() {
      openRelationsWithStatus();
    },
    exportTopSummary() {
      openSummaryExportBridge();
    },
    openTopGraph() {
      const target = currentRun?.file_urls?.graph_html || currentRun?.file_urls?.graph_svg || "";
      if (!target) return;
      window.open(target, "_blank", "noopener,noreferrer");
    },
    openTopTimeline() {
      openTimelineBridge();
    },
  };

  window.__ZAOMENG_HANDLE_WORK_RECOMMENDED_ACTION__ = handleWorkRecommendedAction;
  if (typeof bridgeTools.mergeLegacyActionBridge === "function") {
    bridgeTools.mergeLegacyActionBridge("__ZAOMENG_RUN_OVERVIEW_ACTIONS__", actions);
  } else {
    window.__ZAOMENG_RUN_OVERVIEW_ACTIONS__ = {
      ...(window.__ZAOMENG_RUN_OVERVIEW_ACTIONS__ || {}),
      ...actions,
    };
  }
})();
