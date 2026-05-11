(() => {
  const stateApi = window.__ZAOMENG_BOOKSHELF_STATE__ || {};

  function bookshelfActions() {
    const tools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
    if (typeof tools.readLegacyActionBridge === "function") {
      return tools.readLegacyActionBridge("__ZAOMENG_BOOKSHELF_ACTIONS__");
    }
    return window.__ZAOMENG_BOOKSHELF_ACTIONS__ || {};
  }

  function syncBookshelfSelection() {
    document.querySelectorAll("#bookshelf-list .bookshelf-item").forEach((node) => {
      const runId = node.getAttribute("data-run-id") || "";
      const nodeRun = findRunById(runId);
      const sameNovel = nodeRun && currentRun && typeof runNovelTitle === "function" && runNovelTitle(nodeRun) === runNovelTitle(currentRun);
      node.classList.toggle("active", runId === currentRunId || Boolean(sameNovel));
    });
  }

  function renderBookshelf(runs) {
    const listRoot = el("bookshelf-list");
    const emptyRoot = el("bookshelf-empty");
    if (!listRoot || !emptyRoot) return;

    const items = typeof stateApi.buildBookshelfItems === "function"
      ? stateApi.buildBookshelfItems(runs || [], currentRunId, currentRun)
      : [];
    listRoot.innerHTML = "";
    emptyRoot.classList.toggle("hidden", items.length > 0);
    if (!items.length) {
      renderBookshelfDetail(null);
      return;
    }

    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const run = item.run;
      const row = document.createElement("div");
      row.className = "bookshelf-item-row";
      const button = document.createElement("button");
      button.type = "button";
      button.className = `bookshelf-item ${item.className}`.trim();
      button.setAttribute("data-run-id", item.runId || "");
      button.innerHTML = `
        <span class="bookshelf-item-top">
          <span class="bookshelf-item-status-row">
            <span class="bookshelf-item-dot" aria-hidden="true"></span>
            <span class="bookshelf-item-status">${item.status}</span>
          </span>
          <strong>${item.title}</strong>
        </span>
        <span class="bookshelf-item-meta">
          <span>${item.characterCopy}</span>
          <span>${item.updatedAt}</span>
        </span>
      `;
      button.title = `${item.title}${item.status ? ` · ${item.status}` : ""}`;
      button.addEventListener("click", async () => {
        try {
          const actions = bookshelfActions();
          if (typeof actions.openRun === "function") {
            await actions.openRun(run.run_id);
          } else {
            throw new Error("书架动作尚未就绪，请稍后再试。");
          }
        } catch (error) {
          setStatus("bookshelf-status", error.message || "这卷暂时没有载入。");
        }
      });

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "bookshelf-delete-button";
      removeButton.textContent = "×";
      removeButton.title = item.deleteTitle;
      removeButton.setAttribute("aria-label", `删除《${item.title}》`);
      removeButton.disabled = Boolean(item.deletingDisabled);
      removeButton.addEventListener("click", async (event) => {
        event.stopPropagation();
        if (run?.status === "running") {
          window.alert("这本书还在整理中，暂时不能删除。");
          return;
        }
        const title = item.title;
        if (!window.confirm(`确定把《${title}》从书架移走吗？`)) return;
        if (!window.confirm(`最后确认：删除《${title}》后，这本书的人物、关系图和会话记录都会一起删除，且无法恢复。`)) return;
        try {
          const actions = bookshelfActions();
          const deleted = typeof actions.deleteRun === "function"
            ? await actions.deleteRun(run.run_id, title)
            : await apiJson(`/api/web/runs/${run.run_id}`, { method: "DELETE" }, "删除失败。");
          const formatter = typeof stateApi.formatBookshelfDeleteStatus === "function"
            ? stateApi.formatBookshelfDeleteStatus
            : (nextTitle, payload) => `已移走《${nextTitle}》，同时删除 ${Number(payload?.deleted_run_count || 0)} 轮记录 / ${Number(payload?.deleted_session_count || 0)} 个会话。`;
          setStatus("bookshelf-status", formatter(title, deleted));
        } catch (error) {
          window.alert(error.message || "删除失败。");
        }
      });

      row.appendChild(button);
      row.appendChild(removeButton);
      fragment.appendChild(row);
    });
    listRoot.appendChild(fragment);
    syncBookshelfSelection();
    renderBookshelfDetail(currentRun || null);
  }

  window.__ZAOMENG_BOOKSHELF_LEGACY_RENDER__ = {
    renderBookshelf,
    syncBookshelfSelection,
  };
})();
