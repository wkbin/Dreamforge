(() => {
  const shared = window.__ZAOMENG_WORK_OVERVIEW_VUE__;
  const vue = window.Vue;
  const host = document.getElementById("work-character-vue-root");
  if (!shared || typeof shared.useRunOverviewIsland !== "function" || typeof shared.getRunOverviewActions !== "function" || !vue || !host) {
    console.warn("[zaomeng] work-character vue island skipped: shared overview helpers are not ready.");
    return;
  }

  const builder = window.__ZAOMENG_BUILD_WORK_CHARACTER_STATE__;
  if (typeof builder !== "function") {
    console.warn("[zaomeng] work-character vue island skipped: state builder is not ready.");
    return;
  }

  const { createApp, computed } = vue;

  createApp({
    setup() {
      const { run } = shared.useRunOverviewIsland("work-character-panel", "work-character-legacy");
      host.classList.remove("hidden");
      const viewState = computed(() => builder(run.value || null));

      function openCharacter(name) {
        const api = shared.getRunOverviewActions();
        if (typeof api.openCharacterReadiness === "function") {
          api.openCharacterReadiness(name);
        }
      }

      function toggleExpanded() {
        const api = shared.getRunOverviewActions();
        if (typeof api.toggleCharacterReadiness === "function") {
          api.toggleCharacterReadiness();
        }
      }

      return {
        openCharacter,
        run,
        toggleExpanded,
        viewState,
      };
    },
    template: `
      <div v-if="run" class="work-character-vue-shell">
        <div v-if="viewState.items.length" class="work-character-list">
          <button
            v-for="item in viewState.items"
            :key="item.name"
            type="button"
            class="work-character-card"
            @click="openCharacter(item.name)"
          >
            <div class="work-character-head">
              <div class="work-character-title">
                <strong>{{ item.name }}</strong>
              </div>
              <span class="work-character-status" :class="'is-' + item.statusTone">{{ item.statusText }}</span>
            </div>
            <div class="work-character-meta">
              <span>{{ item.preview.core_identity || item.preview.story_role || '已落成人物包' }}</span>
              <span>{{ item.weakCount > 0 ? ('待补 ' + item.weakCount) : '已齐' }}</span>
            </div>
          </button>
        </div>
        <button
          v-if="viewState.canExpand"
          type="button"
          class="soft-button"
          @click="toggleExpanded"
        >
          {{ viewState.toggleLabel }}
        </button>
        <p v-if="!viewState.items.length" class="card-note">{{ viewState.emptyCopy }}</p>
      </div>
    `,
  }).mount(host);
})();
