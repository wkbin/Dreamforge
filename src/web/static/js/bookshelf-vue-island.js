(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const stateApi = window.__ZAOMENG_BOOKSHELF_STATE__ || {};
  const webuiApi = window.__ZAOMENG_WEBUI_API__;
  const vue = window.Vue;
  const host = document.getElementById("bookshelf-vue-root");
  const section = document.getElementById("bookshelf-section");
  const legacy = document.getElementById("bookshelf-legacy");
  if (!bridge || !webuiApi || !vue || !host || !section || !legacy) {
    return;
  }

  const { computed, createApp, onBeforeUnmount, onMounted, ref } = vue;

  function bookshelfActions() {
    const tools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
    if (typeof tools.readLegacyActionBridge === "function") {
      return tools.readLegacyActionBridge("__ZAOMENG_BOOKSHELF_ACTIONS__");
    }
    return window.__ZAOMENG_BOOKSHELF_ACTIONS__ || {};
  }

  function formatDeleteStatus(title, payload) {
    if (typeof stateApi.formatBookshelfDeleteStatus === "function") {
      return stateApi.formatBookshelfDeleteStatus(title, payload);
    }
    const runCount = Number(payload?.deleted_run_count || 0);
    const sessionCount = Number(payload?.deleted_session_count || 0);
    return `已移走《${title}》，同时删除 ${runCount} 轮记录 / ${sessionCount} 个会话。`;
  }

  createApp({
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const loadingRunId = ref("");
      const deletingRunId = ref("");
      const unsubscribe = typeof bridge.subscribe === "function"
        ? bridge.subscribe((nextSnapshot) => {
          snapshot.value = nextSnapshot || {};
        })
        : () => {};

      onMounted(() => {
        section.classList.add("has-vue-island");
        host.classList.remove("hidden");
        legacy.classList.add("hidden");
      });

      onBeforeUnmount(() => {
        unsubscribe();
      });

      const workflow = computed(() => snapshot.value.workflow || {});
      const visible = computed(() => Boolean(workflow.value.showBookshelf));
      const items = computed(() => {
        if (typeof stateApi.buildBookshelfItems === "function") {
          return stateApi.buildBookshelfItems(snapshot.value?.allRuns || [], snapshot.value?.currentRunId || "", snapshot.value?.currentRun || null);
        }
        return [];
      });

      async function openRun(runId) {
        const target = String(runId || "").trim();
        if (!target || loadingRunId.value) return;
        loadingRunId.value = target;
        try {
          const actions = bookshelfActions();
          if (typeof actions.openRun === "function") {
            await actions.openRun(target);
          } else {
            throw new Error("书架动作尚未就绪，请稍后再试。");
          }
        } catch (error) {
          setStatus("bookshelf-status", error.message || "这卷暂时没有载入。");
        } finally {
          loadingRunId.value = "";
        }
      }

      async function deleteRun(item) {
        const run = item?.run;
        if (!run?.run_id || deletingRunId.value) return;
        if (run?.status === "running") {
          window.alert("这本书还在整理中，暂时不能删除。");
          return;
        }
        const title = item.title || (typeof runNovelTitle === "function" ? runNovelTitle(run) : "这本书");
        if (!window.confirm(`确定把《${title}》从书架移走吗？`)) return;
        if (!window.confirm(`最后确认：删除《${title}》后，这本书的人物、关系图和会话记录都会一起删除，且无法恢复。`)) return;
        deletingRunId.value = String(run.run_id || "");
        try {
          const actions = bookshelfActions();
          let deleted = null;
          if (typeof actions.deleteRun === "function") {
            deleted = await actions.deleteRun(run.run_id, title);
          } else {
            deleted = await webuiApi.deleteRun(run.run_id);
          }
          setStatus("bookshelf-status", formatDeleteStatus(title, deleted));
        } catch (error) {
          window.alert(error.message || "删除失败。");
        } finally {
          deletingRunId.value = "";
        }
      }

      return {
        deleteRun,
        deletingRunId,
        items,
        loadingRunId,
        openRun,
        visible,
      };
    },
    template: `
      <div v-if="visible" class="bookshelf-vue-shell">
        <div v-if="items.length" class="bookshelf-grid">
          <div v-for="item in items" :key="item.runId" class="bookshelf-item-row">
            <button
              type="button"
              class="bookshelf-item"
              :class="[item.className, { active: item.current }]"
              :data-run-id="item.runId"
              :title="item.title + (item.status ? ' · ' + item.status : '')"
              :disabled="loadingRunId === item.runId"
              @click="openRun(item.runId)"
            >
              <span class="bookshelf-item-top">
                <span class="bookshelf-item-status-row">
                  <span class="bookshelf-item-dot" aria-hidden="true"></span>
                  <span class="bookshelf-item-status">{{ loadingRunId === item.runId ? '载入中...' : item.status }}</span>
                </span>
                <strong>{{ item.title }}</strong>
              </span>
              <span class="bookshelf-item-meta">
                <span>{{ item.characterCopy }}</span>
                <span>{{ item.updatedAt }}</span>
              </span>
            </button>
            <button
              type="button"
              class="bookshelf-delete-button"
              :title="item.deleteTitle"
              :aria-label="'删除《' + item.title + '》'"
              :disabled="item.deletingDisabled || deletingRunId === item.runId"
              @click.stop="deleteRun(item)"
            >{{ deletingRunId === item.runId ? '…' : '×' }}</button>
          </div>
        </div>
        <div v-else class="bookshelf-empty">
          <p class="card-copy">还没有放入新的故事。先挑一本书，把想遇见的人请出来。</p>
        </div>
      </div>
    `,
  }).mount(host);
})();
