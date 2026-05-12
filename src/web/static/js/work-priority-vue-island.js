(() => {
  const shared = window.__ZAOMENG_WORK_OVERVIEW_VUE__;
  const vue = window.Vue;
  const host = document.getElementById("work-priority-vue-root");
  if (!shared || typeof shared.useRunOverviewIsland !== "function" || typeof shared.getRunOverviewActions !== "function" || !vue || !host) {
    console.warn("[zaomeng] work-priority vue island skipped: shared overview helpers are not ready.");
    return;
  }

  const builder = window.__ZAOMENG_BUILD_WORK_PRIORITY_STATE__;
  if (typeof builder !== "function") {
    console.warn("[zaomeng] work-priority vue island skipped: state builder is not ready.");
    return;
  }

  const { createApp, computed } = vue;

  createApp({
    setup() {
      const { run } = shared.useRunOverviewIsland("work-priority-panel", "work-priority-legacy");
      host.classList.remove("hidden");
      const viewState = computed(() => builder(run.value || null));

      function openCharacter(name) {
        const api = shared.getRunOverviewActions();
        if (typeof api.openPriorityCharacter === "function") {
          api.openPriorityCharacter(name);
        }
      }

      function redistillCharacter(name) {
        const api = shared.getRunOverviewActions();
        if (typeof api.redistillPriorityCharacter === "function") {
          api.redistillPriorityCharacter(name);
        }
      }

      return {
        openCharacter,
        redistillCharacter,
        run,
        viewState,
      };
    },
    template: `
      <div v-if="run" class="work-priority-vue-shell">
        <div v-if="viewState.items.length" class="work-priority-review-list">
          <article v-for="item in viewState.items" :key="item.name" class="work-priority-card">
            <div class="work-priority-card-head">
              <span class="work-priority-rank">优先 {{ item.order }}</span>
              <span class="work-character-status" :class="'is-' + item.statusTone">{{ item.statusText }}</span>
            </div>
            <div class="work-priority-title">
              <strong>{{ item.name }}</strong>
              <small>{{ item.preview.core_identity || item.preview.story_role || '人物轮廓还在慢慢站稳' }}</small>
            </div>
            <p class="work-priority-headline">{{ item.headline }}</p>
            <p class="work-priority-copy">{{ item.reason }}</p>
            <div class="work-priority-meta">
              <span>{{ item.weakCount > 0 ? ('待补关键字段 ' + item.weakCount) : '关键字段已齐' }}</span>
              <span>{{ item.updatedText ? ('最近更新 ' + item.updatedText) : '刚刚落成' }}</span>
            </div>
            <p class="work-priority-hint">{{ item.actionHint }}</p>
            <div class="work-priority-actions">
              <button type="button" class="soft-button" @click="openCharacter(item.name)">打开角色页</button>
              <button type="button" class="soft-button" @click="redistillCharacter(item.name)">增量蒸馏</button>
            </div>
          </article>
        </div>
        <p v-else class="card-note">{{ viewState.emptyCopy }}</p>
      </div>
    `,
  }).mount(host);
})();
