(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const vue = window.Vue;
  if (!bridge || !vue) {
    return;
  }

  const { computed, onBeforeUnmount, onMounted, ref } = vue;

  function getRunOverviewActions() {
    const tools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
    if (typeof tools.readLegacyActionBridge === "function") {
      return tools.readLegacyActionBridge("__ZAOMENG_RUN_OVERVIEW_ACTIONS__");
    }
    return window.__ZAOMENG_RUN_OVERVIEW_ACTIONS__ || {};
  }

  function useRunOverviewIsland(panelId, legacyId) {
    const panel = document.getElementById(panelId);
    const legacy = document.getElementById(legacyId);
    const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
    const unsubscribe = typeof bridge.subscribe === "function"
      ? bridge.subscribe((nextSnapshot) => {
        snapshot.value = nextSnapshot || {};
      })
      : () => {};

    onMounted(() => {
      if (panel) {
        panel.classList.add("has-vue-island");
      }
      if (legacy) {
        legacy.classList.add("hidden");
      }
    });

    onBeforeUnmount(() => {
      unsubscribe();
    });

    return {
      snapshot,
      run: computed(() => snapshot.value.currentRun || null),
    };
  }

  window.__ZAOMENG_WORK_OVERVIEW_VUE__ = {
    getRunOverviewActions,
    useRunOverviewIsland,
  };
})();
