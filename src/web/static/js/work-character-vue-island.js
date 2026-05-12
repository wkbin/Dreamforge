(() => {
  const shared = window.__ZAOMENG_WORK_OVERVIEW_VUE__;
  const vue = window.Vue;
  const host = document.getElementById("work-character-vue-root");
  if (!shared || !vue || !host) {
    return;
  }

  const builder = window.__ZAOMENG_BUILD_WORK_CHARACTER_STATE__;
  if (typeof builder !== "function") {
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
                <small>{{ item.preview.core_identity || item.preview.story_role || '人物包已经落地，可继续补细节' }}</small>
              </div>
              <span class="work-character-status" :class="'is-' + item.statusTone">{{ item.statusText }}</span>
            </div>
            <p class="work-character-copy">{{ item.preview.speech_style || item.preview.soul_goal || '说话方式或灵魂目标还可以继续补得更稳。' }}</p>
            <div class="work-character-meta">
              <span>{{ item.weakCount > 0 ? ('待补关键字段 ' + item.weakCount) : '关键字段已齐' }}</span>
              <span>{{ item.updatedText ? ('最近更新 ' + item.updatedText) : '刚刚落成' }}</span>
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
