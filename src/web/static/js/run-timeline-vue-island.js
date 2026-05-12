(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const stateApi = window.__ZAOMENG_RUN_DETAIL_SUPPORT_STATE__ || {};
  const vue = window.Vue;
  const host = document.getElementById("run-timeline-vue-root");
  const panel = document.getElementById("step-progress");
  const legacy = document.getElementById("run-timeline-legacy");
  if (!bridge || !stateApi || !vue || !host || !panel || !legacy) {
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
      const items = computed(() => {
        if (!run.value || typeof stateApi.buildRunEventsViewState !== "function") {
          return [];
        }
        return stateApi.buildRunEventsViewState(run.value, formatWeakTime, humanizeRunEventStage);
      });

      return {
        items,
        visible,
      };
    },
    template: `
      <div v-if="visible" class="run-timeline-vue-shell">
        <ol v-if="items.length" class="timeline timeline-dense">
          <li v-for="item in items" :key="item.stageLabel + item.message + item.updated">
            <strong>{{ item.stageLabel }}</strong>
            <p>{{ item.message }}</p>
            <small>{{ item.updated }}</small>
          </li>
        </ol>
        <p v-else class="card-note">这轮还没有新的时间线事件。</p>
      </div>
    `,
  }).mount(host);
})();
