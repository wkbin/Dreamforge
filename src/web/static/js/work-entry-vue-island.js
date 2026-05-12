(() => {
  const shared = window.__ZAOMENG_WORK_OVERVIEW_VUE__;
  const vue = window.Vue;
  const host = document.getElementById("work-entry-vue-root");
  if (!shared || typeof shared.useRunOverviewIsland !== "function" || typeof shared.getRunOverviewActions !== "function" || !vue || !host) {
    console.warn("[zaomeng] work-entry vue island skipped: shared overview helpers are not ready.");
    return;
  }

  const builder = window.__ZAOMENG_BUILD_WORK_ENTRY_STATE__;
  if (typeof builder !== "function") {
    console.warn("[zaomeng] work-entry vue island skipped: state builder is not ready.");
    return;
  }

  const { createApp, computed } = vue;

  createApp({
    setup() {
      const { run } = shared.useRunOverviewIsland("work-entry-panel", "work-entry-legacy");
      host.classList.remove("hidden");
      const viewState = computed(() => builder(run.value || null));

      function openSession(item) {
        const api = shared.getRunOverviewActions();
        if (typeof api.openEntrySession === "function") {
          api.openEntrySession(item);
        }
      }

      function toggleSessions() {
        const api = shared.getRunOverviewActions();
        if (typeof api.toggleEntrySessions === "function") {
          api.toggleEntrySessions();
        }
      }

      function openMode(mode) {
        const api = shared.getRunOverviewActions();
        if (typeof api.openEntryMode === "function") {
          api.openEntryMode(mode);
        }
      }

      return {
        openMode,
        openSession,
        run,
        toggleSessions,
        viewState,
      };
    },
    template: `
      <div v-if="run" class="work-entry-vue-shell">
        <article class="work-graph-card">
          <div class="work-graph-head">
            <strong>关系图谱</strong>
            <span class="work-character-status" :class="'is-' + viewState.graph.badgeTone">{{ viewState.graph.badgeText }}</span>
          </div>
          <p class="detail-section-copy">{{ viewState.graph.copy }}</p>
        </article>
        <div v-if="viewState.graph.links.length" class="link-row">
          <a
            v-for="item in viewState.graph.links"
            :key="item.url"
            :href="item.url"
            target="_blank"
            rel="noreferrer"
          >
            {{ item.label }}
          </a>
        </div>
        <p v-else class="card-note">{{ viewState.graph.emptyCopy }}</p>

        <div class="work-session-preview-head">
          <strong>最近会话</strong>
          <small>可以直接从这里接着说</small>
        </div>
        <div v-if="viewState.sessions.latest" class="card-actions">
          <button type="button" class="soft-button" @click="openSession(viewState.sessions.latest.raw)">
            {{ viewState.sessions.latest.label }}
          </button>
        </div>
        <div v-if="viewState.sessions.items.length" class="work-session-preview">
          <button
            v-for="item in viewState.sessions.items"
            :key="item.raw.session_id || item.raw.updated_at || item.label"
            type="button"
            class="work-session-card"
            :class="{ 'has-match': item.hasMatch }"
            @click="openSession(item.raw)"
          >
            <div class="work-session-head">
              <div class="work-session-title">
                <strong>{{ item.label }}</strong>
                <small>{{ item.modeLabel }} · {{ item.participantCount || 0 }} 人</small>
              </div>
            </div>
            <span v-if="item.matchText" class="work-session-match">{{ item.matchText }}</span>
            <p v-if="item.snippet" class="work-session-copy">{{ item.snippet }}</p>
            <div class="work-session-meta">
              <span>{{ item.updatedText }}</span>
              <span>{{ item.statusText }}</span>
            </div>
          </button>
        </div>
        <button
          v-if="viewState.sessions.canExpand"
          type="button"
          class="soft-button"
          @click="toggleSessions"
        >
          {{ viewState.sessions.toggleLabel }}
        </button>
        <p v-if="!viewState.sessions.items.length" class="card-note">{{ viewState.sessions.emptyCopy }}</p>

        <div class="work-mode-shortcuts">
          <button
            v-for="item in viewState.quickModes"
            :key="item.mode"
            type="button"
            class="soft-button"
            @click="openMode(item.mode)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
    `,
  }).mount(host);
})();
