(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const stateApi = window.__ZAOMENG_RUN_DETAIL_SUPPORT_STATE__ || {};
  const vue = window.Vue;
  const host = document.getElementById("source-history-vue-root");
  const panel = document.getElementById("step-progress");
  const legacy = document.getElementById("source-history-legacy");
  const toggleButton = document.getElementById("source-history-toggle");
  const shared = window.__ZAOMENG_WORK_OVERVIEW_VUE__;
  if (!bridge || !stateApi || !vue || !host || !panel || !legacy || !toggleButton || !shared) {
    return;
  }

  const { computed, createApp, onBeforeUnmount, onMounted, ref } = vue;

  createApp({
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const unsubscribe = typeof bridge.subscribe === "function"
        ? bridge.subscribe((nextSnapshot) => {
          snapshot.value = nextSnapshot || {};
        })
        : () => {};

      onMounted(() => {
        panel.classList.add("has-vue-island");
        host.classList.remove("hidden");
        legacy.classList.add("hidden");
      });

      onBeforeUnmount(() => {
        unsubscribe();
      });

      const run = computed(() => snapshot.value.currentRun || null);
      const workflow = computed(() => snapshot.value.workflow || {});
      const visible = computed(() => Boolean(workflow.value.showProgress));
      const viewState = computed(() => {
        if (!run.value || typeof stateApi.buildSourceHistoryViewState !== "function") {
          return null;
        }
        return stateApi.buildSourceHistoryViewState(run.value, Boolean(window.sourceHistoryExpanded), formatWeakTime);
      });

      function toggleExpanded() {
        const actions = shared.getRunOverviewActions();
        if (typeof actions.toggleSourceHistory === "function") {
          actions.toggleSourceHistory();
        }
      }

      return {
        toggleExpanded,
        viewState,
        visible,
      };
    },
    template: `
      <div v-if="visible && viewState" class="source-history-vue-shell">
        <p class="detail-section-copy">{{ viewState.note }}</p>
        <div v-if="viewState.items.length" class="source-history-list">
          <article v-for="item in viewState.items" :key="item.title + item.meta + item.detail" class="source-history-item" :class="{ current: item.current }">
            <div class="source-history-title">
              {{ item.title }}
              <span v-if="item.current" class="source-history-badge">当前使用中</span>
            </div>
            <div class="source-history-meta">{{ item.meta }}</div>
            <div v-if="item.detail" class="source-history-detail">{{ item.detail }}</div>
          </article>
        </div>
        <p v-else class="card-note">目前只有最初那一份正文。</p>
        <div v-if="viewState.canExpand" class="card-actions">
          <button type="button" class="soft-button" @click="toggleExpanded">{{ viewState.toggleLabel }}</button>
        </div>
      </div>
    `,
  }).mount(host);
})();
