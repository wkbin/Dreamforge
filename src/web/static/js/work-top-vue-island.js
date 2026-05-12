(() => {
  const shared = window.__ZAOMENG_WORK_OVERVIEW_VUE__;
  const vue = window.Vue;
  const host = document.getElementById("work-top-vue-root");
  if (!shared || typeof shared.useRunOverviewIsland !== "function" || typeof shared.getRunOverviewActions !== "function" || !vue || !host) {
    console.warn("[zaomeng] work-top vue island skipped: shared overview helpers are not ready.");
    return;
  }

  const builder = window.__ZAOMENG_BUILD_WORK_TOP_OVERVIEW_STATE__;
  if (typeof builder !== "function") {
    console.warn("[zaomeng] work-top vue island skipped: state builder is not ready.");
    return;
  }

  const { createApp, computed } = vue;

  function invokeAction(key) {
    const api = shared.getRunOverviewActions();
    const handlers = {
      redistill: "toggleTopRedistill",
      review: "openTopReview",
      chat: "openTopChat",
      stop: "stopTopRun",
      relations: "openTopRelations",
      export: "exportTopSummary",
      graph: "openTopGraph",
      timeline: "openTopTimeline",
    };
    const handlerName = handlers[String(key || "").trim()] || "";
    if (handlerName && typeof api[handlerName] === "function") {
      api[handlerName]();
    }
  }

  createApp({
    setup() {
      const { run } = shared.useRunOverviewIsland("step-progress", "work-top-legacy");
      host.classList.remove("hidden");
      const viewState = computed(() => builder(run.value || null));

      return {
        invokeAction,
        run,
        viewState,
      };
    },
    template: `
      <div v-if="run" class="work-top-vue-shell">
        <section class="work-overview-hero">
          <div class="work-overview-hero-copy">
            <p class="card-copy">{{ viewState.progressCopy }}</p>
            <p class="work-overview-next-step">{{ viewState.nextStep }}</p>
          </div>
          <section v-if="viewState.banner.visible" class="run-status-banner">
            <div class="run-status-banner-head">
              <span class="run-status-kicker">{{ viewState.banner.kicker }}</span>
              <span class="run-status-stage">{{ viewState.banner.stage }}</span>
            </div>
            <p class="run-status-description">{{ viewState.banner.description }}</p>
          </section>
        </section>

        <div class="work-hero-metrics">
          <article v-for="item in viewState.heroMetrics" :key="'hero-' + item.label" class="work-hero-metric">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>

        <div class="work-progress-strip">
          <article v-for="item in viewState.progressMetrics" :key="'progress-' + item.label" class="work-progress-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>

        <section class="work-action-groups">
          <div v-if="viewState.actions.primaryVisible" class="work-action-group">
            <span class="work-action-label">主动作</span>
            <div class="card-actions">
              <button
                v-for="item in viewState.actions.primaryButtons.filter((entry) => !entry.hidden)"
                :key="'primary-' + item.key"
                type="button"
                :class="item.tone === 'primary' ? 'primary-button' : 'soft-button'"
                :disabled="item.disabled"
                @click="invokeAction(item.key)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <div v-if="viewState.actions.secondaryVisible" class="work-action-group">
            <span class="work-action-label">次动作</span>
            <div class="card-actions" :class="{ 'is-softened': viewState.actions.softenSecondary }">
              <button
                v-for="item in viewState.actions.secondaryButtons"
                :key="'secondary-' + item.key"
                type="button"
                class="soft-button"
                :disabled="item.disabled"
                @click="invokeAction(item.key)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
        </section>

        <p v-if="viewState.actions.actionNoteVisible" class="card-note">{{ viewState.actions.actionNote }}</p>
      </div>
    `,
  }).mount(host);
})();
