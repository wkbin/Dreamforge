(() => {
  const supportState = window.__ZAOMENG_RUN_DETAIL_SUPPORT_STATE__ || {};

  function renderRunEvents(run) {
    const eventsRoot = el("events");
    if (!eventsRoot) return;
    eventsRoot.innerHTML = "";
    const items = typeof supportState.buildRunEventsViewState === "function"
      ? supportState.buildRunEventsViewState(run, formatWeakTime, humanizeRunEventStage)
      : [];
    items.forEach((item) => {
      const node = document.createElement("li");
      node.innerHTML = `
        <strong>${escapeHtml(item.stageLabel)}</strong>
        <p>${escapeHtml(item.message)}</p>
        <small>${escapeHtml(item.updated)}</small>
      `;
      eventsRoot.appendChild(node);
    });
    toggle("timeline-empty-note", eventsRoot.childElementCount === 0);
  }

  function renderRunGraphLinks(run) {
    const graphLinksRoot = el("graph-links");
    if (!graphLinksRoot) return;
    graphLinksRoot.innerHTML = "";
    buildWorkGraphLinks(run).forEach((entry) => {
      const link = document.createElement("a");
      link.href = entry.url;
      link.textContent = entry.label;
      link.target = "_blank";
      link.rel = "noreferrer";
      graphLinksRoot.appendChild(link);
    });
    graphLinksRoot.classList.toggle("hidden", graphLinksRoot.childElementCount === 0);
    toggle("graph-empty-note", graphLinksRoot.childElementCount === 0);
    const relationButton = el("open-relation-details-button");
    if (relationButton) {
      relationButton.classList.remove("hidden");
      relationButton.disabled = !Boolean(run?.artifact_index?.relation_graph?.relations_file);
    }
  }

  function renderNameGroup(rootId, names, emptyId) {
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
      title.textContent = item.title;
      const summary = document.createElement("p");
      summary.textContent = item.summary;
      const meta = document.createElement("small");
      meta.textContent = String(item.meta || "").trim();
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

  function renderRedistillPlan(run) {
    const state = typeof supportState.buildRedistillPlanState === "function"
      ? supportState.buildRedistillPlanState(run)
      : null;
    if (!state) return;
    setText("redistill-plan-title", state.title, "");
    setText("redistill-source-note", state.sourceNote, "");
    renderNameGroup("redistill-existing-list", state.existing, "redistill-existing-empty");
    renderNameGroup("redistill-new-list", state.newcomers, "redistill-new-empty");
    renderRedistillRecentChanges(state.recentChanges);
  }

  function renderSourceHistory(run) {
    const root = el("source-history-list");
    const toggleButton = el("source-history-toggle");
    if (!root) return;
    root.innerHTML = "";
    const state = typeof supportState.buildSourceHistoryViewState === "function"
      ? supportState.buildSourceHistoryViewState(run, Boolean(window.sourceHistoryExpanded), formatWeakTime)
      : null;
    if (!state) return;
    state.items.forEach((item) => {
      const card = document.createElement("article");
      card.className = `source-history-item${item.current ? " current" : ""}`;
      const title = document.createElement("div");
      title.className = "source-history-title";
      title.textContent = item.title;
      if (item.current) {
        const badge = document.createElement("span");
        badge.className = "source-history-badge";
        badge.textContent = "当前使用中";
        title.appendChild(badge);
      }
      const meta = document.createElement("div");
      meta.className = "source-history-meta";
      meta.textContent = item.meta;
      const detail = document.createElement("div");
      detail.className = "source-history-detail";
      detail.textContent = item.detail;
      card.appendChild(title);
      card.appendChild(meta);
      if (detail.textContent) {
        card.appendChild(detail);
      }
      root.appendChild(card);
    });
    root.classList.toggle("hidden", root.childElementCount === 0);
    toggle("source-history-empty", state.emptyVisible);
    if (toggleButton) {
      toggleButton.classList.toggle("hidden", !state.canExpand);
      toggleButton.textContent = state.toggleLabel;
    }
    setText("source-history-note", state.note, "");
  }

  window.__ZAOMENG_RUN_DETAIL_SUPPORT_RENDER__ = {
    renderRedistillPlan,
    renderRunEvents,
    renderRunGraphLinks,
    renderSourceHistory,
  };
})();
