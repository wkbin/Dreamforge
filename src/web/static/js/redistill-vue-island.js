(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const webuiApi = window.__ZAOMENG_WEBUI_API__;
  const vue = window.Vue;
  const host = document.getElementById("redistill-vue-root");
  const panel = document.getElementById("redistill-panel");
  if (!bridge || !vue || !host || !panel || !webuiApi) {
    return;
  }

  const { createApp, computed, onBeforeUnmount, onMounted, ref } = vue;

  function redistillActions() {
    const tools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
    if (typeof tools.readLegacyActionBridge === "function") {
      return tools.readLegacyActionBridge("__ZAOMENG_REDISTILL_ACTIONS__");
    }
    return window.__ZAOMENG_REDISTILL_ACTIONS__ || {};
  }

  function deriveTitle(redistill, draft) {
    if (draft.fileAttached) return "这轮会换入新的书段继续整理";
    if (draft.usingSuggestedSegment) return "这轮会使用推荐片段继续整理";
    if (redistill.used_new_source) return "这轮会换入新的书段继续整理";
    return "这轮会沿用当前书段继续整理";
  }

  function deriveSourceNote(redistill, draft, run) {
    const latestSource = Array.isArray(run?.novel_sources) ? run.novel_sources[run.novel_sources.length - 1] : null;
    const sourceName = String(redistill.source_name || latestSource?.source_name || "").trim();
    if (draft.fileAttached) {
      return `当前准备换入新的正文片段：${draft.fileName || "新的书页"}`;
    }
    if (draft.usingSuggestedSegment) {
      const reason = String(draft.selectedSegment?.reason || "更适合补稳目标字段").trim();
      return `当前准备切到推荐片段：${reason}${sourceName ? ` · 来源 ${sourceName}` : ""}`;
    }
    if (redistill.used_new_source) {
      return `当前已换入新的正文片段：${sourceName || "新的书页"}`;
    }
    return `当前会沿用上一轮使用的正文片段${sourceName ? `：${sourceName}` : ""}。`;
  }

  createApp({
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const unsubscribe = bridge.subscribe((nextSnapshot) => {
        snapshot.value = nextSnapshot || {};
      });

      onMounted(() => {
        panel.classList.add("has-vue-island");
        host.classList.remove("hidden");
      });

      onBeforeUnmount(() => {
        unsubscribe();
      });

      const run = computed(() => snapshot.value.currentRun || {});
      const redistill = computed(() => run.value.redistill || {});
      const draft = computed(() => snapshot.value.redistillDraft || {});
      const suggestions = computed(() => snapshot.value.redistillSuggestionState || {});
      const existing = computed(() => {
        const preferred = Array.isArray(draft.value.existingSelectedCharacters) ? draft.value.existingSelectedCharacters : [];
        return preferred.length ? preferred : (Array.isArray(redistill.value.existing_characters) ? redistill.value.existing_characters : []);
      });
      const newcomers = computed(() => {
        const preferred = Array.isArray(draft.value.newSelectedCharacters) ? draft.value.newSelectedCharacters : [];
        return preferred.length ? preferred : (Array.isArray(redistill.value.new_characters) ? redistill.value.new_characters : []);
      });
      const recentChanges = computed(() => (Array.isArray(redistill.value.recent_changes) ? redistill.value.recent_changes : []));
      const recommendationItems = computed(() => (Array.isArray(suggestions.value.items) ? suggestions.value.items : []));
      const recommendationTarget = computed(() => String(draft.value.recommendationTarget || suggestions.value.character || "").trim());
      const recommendationVisible = computed(() => Boolean(recommendationTarget.value && !draft.value.fileAttached));
      const recommendationNote = computed(() => {
        if (!recommendationTarget.value) {
          return "只选中一位已有角色时，这里会给出适合补稳这位角色的正文窗口。";
        }
        if (suggestions.value.loading) {
          return `正在替「${recommendationTarget.value}」翻当前书段，找更适合补稳的正文片段...`;
        }
        if (!recommendationItems.value.length) {
          const weakLabels = Array.isArray(suggestions.value.weakFieldLabels) ? suggestions.value.weakFieldLabels.filter(Boolean) : [];
          return weakLabels.length
            ? `只选中「${recommendationTarget.value}」后，可一键从当前书段里挑推荐片段。优先盯：${weakLabels.join("、")}。`
            : `只选中「${recommendationTarget.value}」后，可一键从当前书段里挑推荐片段。`;
        }
        return `当前基于 ${String(suggestions.value.sourceName || "当前书段").trim()} 为「${recommendationTarget.value}」挑了 ${recommendationItems.value.length} 段候选正文。`;
      });

      function recommend() {
        const actions = redistillActions();
        if (typeof actions.recommend === "function") {
          actions.recommend();
        }
      }

      function selectSegment(segmentId) {
        const actions = redistillActions();
        if (typeof actions.selectSegment === "function") {
          actions.selectSegment(segmentId);
        }
      }

      return {
        run,
        redistill,
        draft,
        existing,
        newcomers,
        recentChanges,
        recommendationItems,
        recommendationTarget,
        recommendationVisible,
        recommendationNote,
        suggestions,
        deriveTitle,
        deriveSourceNote,
        recommend,
        selectSegment,
      };
    },
    template: `
      <div class="redistill-vue-stack">
        <section class="detail-section redistill-summary-card">
          <div class="detail-section-head">
            <div>
              <p class="eyebrow">这一轮会如何继续</p>
              <h4>{{ deriveTitle(redistill, draft) }}</h4>
            </div>
          </div>
          <p class="detail-section-copy">{{ deriveSourceNote(redistill, draft, run) }}</p>
          <div class="plan-split">
            <div class="plan-group">
              <span class="plan-label">会做增量更新</span>
              <div v-if="existing.length" class="bookshelf-links">
                <span v-for="name in existing" :key="'existing-' + name">{{ name }}</span>
              </div>
              <p v-else class="card-note">这一轮暂时没有需要增量更新的角色。</p>
            </div>
            <div class="plan-group">
              <span class="plan-label">会首次蒸馏</span>
              <div v-if="newcomers.length" class="bookshelf-links">
                <span v-for="name in newcomers" :key="'new-' + name">{{ name }}</span>
              </div>
              <p v-else class="card-note">这一轮暂时没有新角色。</p>
            </div>
          </div>
          <div class="plan-group">
            <span class="plan-label">这轮刚补稳了什么</span>
            <div v-if="recentChanges.length" class="redistill-change-list">
              <article v-for="item in recentChanges" :key="'change-' + item.character" class="redistill-change-card">
                <strong>{{ item.character || '角色' }}</strong>
                <p>{{ item.summary || '这一轮有新的字段变化落了下来。' }}</p>
                <small v-if="(item.highlight_field_labels || []).length || item.changed_count">
                  <template v-if="(item.highlight_field_labels || []).length">重点：{{ item.highlight_field_labels.join('、') }}</template>
                  <template v-if="item.changed_count">
                    <span v-if="(item.highlight_field_labels || []).length"> · </span>共 {{ item.changed_count }} 项
                  </template>
                </small>
              </article>
            </div>
            <p v-else class="card-note">增量蒸馏完成后，这里会总结本轮字段变化。</p>
          </div>
        </section>

        <section v-if="recommendationVisible" class="detail-section redistill-recommend-shell">
          <div class="detail-section-head">
            <div>
              <p class="eyebrow">推荐片段</p>
              <h4>替这一轮找更适合补料的正文窗口</h4>
            </div>
            <div class="card-actions">
              <button type="button" class="soft-button" :disabled="suggestions.loading || !recommendationTarget" @click="recommend">
                {{ suggestions.loading ? '正在挑片段...' : '推荐片段' }}
              </button>
            </div>
          </div>
          <p class="detail-section-copy">{{ recommendationNote }}</p>
          <div v-if="recommendationItems.length" class="redistill-recommend-list">
            <article
              v-for="item in recommendationItems"
              :key="item.segment_id"
              class="redistill-recommend-card"
              :class="{ 'is-selected': item.segment_id === suggestions.selectedSegmentId }"
            >
              <div class="redistill-recommend-card-head">
                <strong>{{ item.preview || '推荐片段' }}</strong>
                <small>句段 {{ item.start_sentence }}-{{ item.end_sentence }} · 分数 {{ item.score || 0 }}</small>
              </div>
              <p class="redistill-recommend-card-meta">
                {{ [item.reason, (item.estimated_field_labels || []).length ? '预计能补：' + item.estimated_field_labels.join('、') : ''].filter(Boolean).join(' · ') }}
              </p>
              <div class="card-actions">
                <button
                  type="button"
                  :class="item.segment_id === suggestions.selectedSegmentId ? 'primary-button' : 'soft-button'"
                  @click="selectSegment(item.segment_id)"
                >
                  {{ item.segment_id === suggestions.selectedSegmentId ? '已选这段' : '用这一段' }}
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>
    `,
  }).mount(host);
})();
