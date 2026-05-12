(() => {
  const shared = window.__ZAOMENG_WORK_OVERVIEW_VUE__;
  const vue = window.Vue;
  const host = document.getElementById("work-summary-vue-root");
  if (!shared || typeof shared.useRunOverviewIsland !== "function" || typeof shared.getRunOverviewActions !== "function" || !vue || !host) {
    console.warn("[zaomeng] work-summary vue island skipped: shared overview helpers are not ready.");
    return;
  }

  const builder = window.__ZAOMENG_BUILD_WORK_SUMMARY_STATE__;
  if (typeof builder !== "function") {
    console.warn("[zaomeng] work-summary vue island skipped: state builder is not ready.");
    return;
  }

  const { createApp, computed } = vue;

  createApp({
    setup() {
      const { run } = shared.useRunOverviewIsland("work-summary-panel", "work-summary-legacy");
      host.classList.remove("hidden");
      const viewState = computed(() => builder(run.value || null));

      function runRecommended(action, payload) {
        const api = shared.getRunOverviewActions();
        if (typeof api.handleRecommended === "function") {
          api.handleRecommended(action, payload);
        }
      }

      return {
        run,
        runRecommended,
        viewState,
      };
    },
    template: `
      <div v-if="run" class="work-summary-vue-shell">
        <section class="work-summary-shell">
          <article class="work-summary-card is-hero">
            <span class="work-summary-label">一句话概览</span>
            <strong>{{ viewState.summaryLine }}</strong>
            <p class="work-summary-copy">{{ viewState.bottleneck }}</p>
          </article>
          <div class="work-summary-grid">
            <article class="work-summary-card">
              <span class="work-summary-label">最近进展</span>
              <div v-if="viewState.events.length" class="work-summary-events">
                <div v-for="item in viewState.events" :key="item.stageLabel + ':' + item.message" class="work-summary-event">
                  <strong>{{ item.stageLabel }}</strong>
                  <p>{{ item.message }}</p>
                </div>
              </div>
              <p v-else class="card-note">这一轮暂时还没有新的进展记录。</p>
            </article>
            <article class="work-summary-card">
              <span class="work-summary-label">推荐动作</span>
              <strong>{{ viewState.recommendation.title }}</strong>
              <p class="work-summary-copy">{{ viewState.recommendation.copy }}</p>
              <div class="work-summary-actions">
                <button
                  type="button"
                  class="soft-button"
                  @click="runRecommended(viewState.recommendation.action, viewState.recommendation.payload)"
                >
                  {{ viewState.recommendation.buttonLabel || '去执行' }}
                </button>
              </div>
            </article>
          </div>
        </section>

        <details v-if="viewState.quality.visible" class="quality-section-shell" :open="viewState.quality.open">
          <summary class="quality-summary">
            <span>蒸馏质量快照</span>
            <small>展开看命中、缺证据与分批信息</small>
          </summary>
          <div class="quality-grid">
            <article class="quality-card">
              <span class="quality-label">已命中人物</span>
              <div v-if="viewState.quality.matched.length" class="bookshelf-links">
                <span v-for="item in viewState.quality.matched" :key="'matched-' + item">{{ item }}</span>
              </div>
              <p v-else class="card-note">这一轮还没从正文里稳定捞到目标人物。</p>
            </article>
            <article class="quality-card">
              <span class="quality-label">暂时缺证据</span>
              <div v-if="viewState.quality.missing.length" class="bookshelf-links">
                <span v-for="item in viewState.quality.missing" :key="'missing-' + item">{{ item }}</span>
              </div>
              <p v-else class="card-note">目前没有缺席的人物。</p>
            </article>
            <article class="quality-card">
              <span class="quality-label">用到的阶段</span>
              <div v-if="viewState.quality.stages.length" class="bookshelf-links">
                <span v-for="item in viewState.quality.stages" :key="'stage-' + item">{{ item }}</span>
              </div>
              <p v-else class="card-note">这一轮暂时还没拆出明确阶段。</p>
            </article>
            <article class="quality-card">
              <span class="quality-label">自动收束</span>
              <p class="quality-copy">{{ viewState.quality.repairsText }}</p>
            </article>
            <article class="quality-card">
              <span class="quality-label">实际分批</span>
              <p class="quality-copy">{{ viewState.quality.chunksText }}</p>
            </article>
          </div>
        </details>
        <p v-else class="card-note">这卷暂时还没有足够多的蒸馏线索，但人物和进度会继续在这里显出来。</p>
      </div>
    `,
  }).mount(host);
})();
