(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const vue = window.Vue;
  const host = document.getElementById("character-overview-vue-root");
  const panel = document.getElementById("step-character-overview");
  const legacy = document.getElementById("character-overview-legacy");
  const stateApi = window.__ZAOMENG_CHARACTER_OVERVIEW_STATE__ || {};
  const actionApi = window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__ || {};
  if (!bridge || !vue || !host || !panel || !legacy || !stateApi || !actionApi) {
    return;
  }

  const {
    computed,
    createApp,
    onBeforeUnmount,
    onMounted,
    reactive,
    ref,
    watch,
  } = vue;

  const KEY_FIELDS = Array.isArray(stateApi.KEY_FIELDS) ? stateApi.KEY_FIELDS : [];

  function clone(value) {
    return JSON.parse(JSON.stringify(value ?? null));
  }

  function formatWeakTimeSafe(timestamp) {
    if (typeof formatWeakTime === "function") {
      return formatWeakTime(timestamp || "") || "刚刚";
    }
    return "刚刚";
  }

  createApp({
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const ui = reactive({
        status: "",
        savingField: "",
        autofillField: "",
        dirtyFields: {},
        localFields: {},
      });

      const unsubscribe = typeof bridge.subscribe === "function"
        ? bridge.subscribe((nextSnapshot) => {
          snapshot.value = nextSnapshot || {};
        })
        : () => {};

      const payload = computed(() => snapshot.value.currentCharacterOverview || null);
      const run = computed(() => snapshot.value.currentRun || null);
      const visible = computed(() => Boolean(snapshot.value.workflow?.showCharacterOverview));
      const character = computed(() => String(payload.value?.character || "").trim());
      const payloadKey = computed(() => JSON.stringify({
        character: payload.value?.character || "",
        fields: payload.value?.fields || {},
        editable: payload.value?.editable_profile_path || "",
        generated: payload.value?.generated_profile_path || "",
      }));

      function applyPayload(nextPayload) {
        const fields = nextPayload?.fields || {};
        const nextFields = {};
        KEY_FIELDS.forEach(([field]) => {
          nextFields[field] = String(fields[field] || "");
        });
        ui.localFields = nextFields;
        ui.dirtyFields = {};
      }

      watch(payloadKey, () => {
        applyPayload(payload.value);
      }, { immediate: true });

      watch(visible, (nextVisible) => {
        if (!nextVisible) {
          ui.status = "";
          ui.savingField = "";
          ui.autofillField = "";
        }
      });

      const healthSnapshot = computed(() => {
        if (typeof stateApi.buildHealthSnapshot !== "function") {
          return null;
        }
        return stateApi.buildHealthSnapshot(payload.value?.fields || {}, run.value?.updated_at || "", formatWeakTimeSafe);
      });

      const evidenceSnapshot = computed(() => {
        if (typeof stateApi.buildEvidenceSnapshot !== "function") {
          return null;
        }
        return stateApi.buildEvidenceSnapshot(run.value, character.value, formatWeakTimeSafe, formatSourceStats, getCurrentNovelSource);
      });

      const trustSignals = computed(() => {
        if (typeof stateApi.buildTrustSignals !== "function") {
          return [];
        }
        return stateApi.buildTrustSignals({
          payload: payload.value,
          healthSnapshot: healthSnapshot.value,
          evidenceSnapshot: evidenceSnapshot.value,
          autofillItems: typeof actionApi.getAutofillItems === "function" ? actionApi.getAutofillItems(character.value) : [],
          reviewEvent: typeof stateApi.findLatestRunEvent === "function"
            ? stateApi.findLatestRunEvent(Array.isArray(run.value?.events) ? run.value.events : [], character.value, "persona_review_saved")
            : null,
          redistillSignal: typeof stateApi.buildRedistillSignal === "function"
            ? stateApi.buildRedistillSignal(run.value, character.value, getCurrentNovelSource)
            : null,
          formatWeakTime: formatWeakTimeSafe,
        }) || [];
      });

      const timelineItems = computed(() => {
        if (typeof stateApi.buildChangeTimelineItems !== "function") {
          return [];
        }
        return stateApi.buildChangeTimelineItems(Array.isArray(run.value?.events) ? run.value.events : [], character.value, formatWeakTimeSafe) || [];
      });

      const voiceSummary = computed(() => {
        if (typeof stateApi.buildVoiceSummaryItems !== "function") {
          return [];
        }
        return stateApi.buildVoiceSummaryItems(payload.value?.fields || {}) || [];
      });

      const relationSummary = computed(() => {
        if (typeof stateApi.buildRelationSummaryItems !== "function") {
          return [];
        }
        return stateApi.buildRelationSummaryItems(payload.value?.fields || {}) || [];
      });

      const advancedGroups = computed(() => {
        if (typeof stateApi.buildAdvancedGroupsView !== "function") {
          return [];
        }
        const expandedGroups = new Set(
          typeof actionApi.getExpandedGroups === "function" ? actionApi.getExpandedGroups() : []
        );
        return stateApi.buildAdvancedGroupsView(payload.value?.fields || {}, expandedGroups) || [];
      });

      const keyFields = computed(() => {
        const fields = payload.value?.fields || {};
        return KEY_FIELDS.map(([field, label]) => {
          const value = String(fields[field] || "").trim();
          const draftValue = String(ui.localFields[field] ?? value).trim();
          const tags = typeof stateApi.buildFieldTags === "function"
            ? stateApi.buildFieldTags(field, value, evidenceSnapshot.value, {
              recentAutofill: typeof actionApi.getAutofillItems === "function"
                ? actionApi.getAutofillItems(character.value).find((item) => item.field === field) || null
                : null,
              editableProfilePath: String(payload.value?.editable_profile_path || "").trim(),
            })
            : [];
          return {
            field,
            label,
            value: ui.localFields[field] ?? value,
            initialValue: value,
            dirty: draftValue !== value,
            weak: typeof stateApi.isFieldWeak === "function" ? stateApi.isFieldWeak(field, draftValue) : !draftValue,
            hint: typeof stateApi.buildFieldHint === "function" ? stateApi.buildFieldHint(field, draftValue) : "",
            tags,
          };
        });
      });

      function setField(field, value) {
        ui.localFields[field] = value;
        const currentValue = String(payload.value?.fields?.[field] || "").trim();
        const nextValue = String(value || "").trim();
        ui.dirtyFields[field] = nextValue !== currentValue;
      }

      async function autofillField(field) {
        const label = typeof stateApi.fieldLabel === "function" ? stateApi.fieldLabel(field) : field;
        ui.autofillField = field;
        ui.status = `正在补全「${label}」...`;
        try {
          const result = await actionApi.autofillField(field);
          ui.status = result?.message || "人物信息补全无法生成。";
          if (result?.filled && result?.saved) {
            applyPayload(result.saved);
          }
        } catch (error) {
          ui.status = error.message || "人物信息补全无法生成。";
        } finally {
          ui.autofillField = "";
        }
      }

      async function saveField(field) {
        const label = typeof stateApi.fieldLabel === "function" ? stateApi.fieldLabel(field) : field;
        ui.savingField = field;
        ui.status = `正在保存「${label}」...`;
        try {
          const result = await actionApi.saveField(field, ui.localFields[field]);
          ui.status = result?.message || `「${label}」已经写回这一卷。`;
          if (result?.saved) {
            applyPayload(result.saved);
          }
        } catch (error) {
          ui.status = error.message || "这次保存没有成功。";
        } finally {
          ui.savingField = "";
        }
      }

      async function openReview() {
        try {
          await actionApi.openReview?.();
        } catch (error) {
          ui.status = error.message || "人物档案暂时没有载入。";
        }
      }

      async function openSession(mode) {
        try {
          await actionApi.openCharacterOverviewSessionMode?.(mode);
        } catch (error) {
          ui.status = error.message || "这一幕暂时没有铺开。";
        }
      }

      function openIncremental() {
        actionApi.openCharacterOverviewIncrementalDistill?.();
      }

      function openSourceFile() {
        const opened = actionApi.openCurrentCharacterProfileFile?.();
        if (!opened) {
          ui.status = "当前没有可打开的人物原档。";
        }
      }

      function closeOverview() {
        actionApi.closeOverview?.();
      }

      function toggleAdvancedGroup(groupName) {
        actionApi.toggleAdvancedGroup?.(groupName);
      }

      onMounted(() => {
        panel.classList.add("has-vue-island");
        host.classList.remove("hidden");
        if (visible.value) {
          legacy.classList.add("hidden");
        }
      });

      watch(visible, (nextVisible) => {
        legacy.classList.toggle("hidden", Boolean(nextVisible));
      }, { immediate: true });

      onBeforeUnmount(() => {
        unsubscribe();
      });

      return {
        advancedGroups,
        autofillField,
        character,
        closeOverview,
        evidenceSnapshot,
        healthSnapshot,
        keyFields,
        openIncremental,
        openReview,
        openSession,
        openSourceFile,
        payload,
        relationSummary,
        run,
        saveField,
        setField,
        timelineItems,
        toggleAdvancedGroup,
        trustSignals,
        ui,
        visible,
        voiceSummary,
      };
    },
    template: `
      <div v-if="visible && payload" class="character-overview-vue-shell">
        <section class="character-overview-hero">
          <div class="character-overview-hero-copy">
            <p class="character-overview-kicker">出自《{{ run ? runNovelTitle(run) : '当前书卷' }}》</p>
            <h4>{{ character || '人物' }}</h4>
            <p class="character-overview-role">{{ payload.fields?.story_role || payload.fields?.core_identity || '这一页会慢慢把他的轮廓立起来' }}</p>
          </div>
          <div class="character-overview-health">
            <span class="work-character-status" :class="healthSnapshot ? 'is-' + healthSnapshot.healthTone : ''">{{ healthSnapshot ? healthSnapshot.healthText : '待整理' }}</span>
            <p class="card-note">{{ healthSnapshot ? healthSnapshot.summaryCopy : '关键字段状态会在这里汇总。' }}</p>
          </div>
        </section>

        <div class="card-actions">
          <button type="button" class="primary-button" @click="openReview">校对字段</button>
          <button type="button" class="soft-button" @click="openIncremental">继续增量蒸馏</button>
          <button type="button" class="soft-button" @click="openSession('act')">化身此人</button>
          <button type="button" class="soft-button" @click="openSession('insert')">以自己入场</button>
          <button type="button" class="soft-button" @click="openSourceFile">查看原档</button>
          <button type="button" class="soft-button" @click="closeOverview">返回书卷</button>
        </div>
        <p class="card-note">{{ ui.status }}</p>

        <section class="detail-section">
          <div class="detail-section-head">
            <div>
              <p class="eyebrow">健康度</p>
              <h4>这一页当前能信到什么程度</h4>
            </div>
          </div>
          <div class="character-overview-health-metrics">
            <article class="character-overview-health-card">
              <span>完整度</span>
              <strong>{{ healthSnapshot ? healthSnapshot.completeness + '%' : '0%' }}</strong>
              <small>按关键字段与细调字段的当前覆盖度估算</small>
            </article>
            <article class="character-overview-health-card">
              <span>稳住的关键字段</span>
              <strong>{{ healthSnapshot ? healthSnapshot.stableKeyCount + ' / ' + keyFields.length : '0 / 0' }}</strong>
              <small>这些字段已经足够支撑角色概览与基础对话</small>
            </article>
            <article class="character-overview-health-card">
              <span>待补位置</span>
              <strong>{{ healthSnapshot ? healthSnapshot.weakKeyCount + ' 处' : '0 处' }}</strong>
              <small>{{ healthSnapshot && healthSnapshot.weakKeyCount > 0 ? '优先补这些地方，人物会更像自己' : '关键骨架已经收住，可以转去细修' }}</small>
            </article>
            <article class="character-overview-health-card">
              <span>细调覆盖</span>
              <strong>{{ healthSnapshot ? healthSnapshot.advancedFilledCount + ' / ' + healthSnapshot.advancedTotalCount : '0 / 0' }}</strong>
              <small>用于抠语气、情绪和更细的人设纹理</small>
            </article>
            <article class="character-overview-health-card">
              <span>最近更新</span>
              <strong>{{ healthSnapshot ? healthSnapshot.updatedText : '刚刚' }}</strong>
              <small>显示这一卷最近一次落盘或校对的大致时间</small>
            </article>
          </div>
        </section>

        <section class="detail-section" v-if="evidenceSnapshot">
          <div class="detail-section-head">
            <div>
              <p class="eyebrow">来源与证据</p>
              <h4>这个角色现在主要是靠什么站住的</h4>
            </div>
          </div>
          <div class="character-overview-evidence-metrics">
            <article class="character-overview-evidence-card">
              <span>证据判断</span>
              <strong>{{ evidenceSnapshot.evidenceLabel }}</strong>
              <small>{{ evidenceSnapshot.evidenceCopy }}</small>
            </article>
            <article class="character-overview-evidence-card">
              <span>当前依据书段</span>
              <strong>{{ evidenceSnapshot.sourceLabel }}</strong>
              <small>{{ evidenceSnapshot.sourceCopy }}</small>
            </article>
            <article class="character-overview-evidence-card">
              <span>来源足迹</span>
              <strong>{{ evidenceSnapshot.traceLabel }}</strong>
              <small>{{ evidenceSnapshot.traceCopy }}</small>
            </article>
            <article class="character-overview-evidence-card">
              <span>{{ evidenceSnapshot.recommendationLabel }}</span>
              <strong>下一步</strong>
              <small>{{ evidenceSnapshot.recommendationCopy }}</small>
            </article>
          </div>
        </section>

        <section class="detail-section">
          <div class="detail-section-head">
            <div>
              <p class="eyebrow">可信痕迹</p>
              <h4>这份人物资产最近被怎样改过</h4>
            </div>
          </div>
          <p class="detail-section-copy">这里先做轻量判断，帮你分清哪些字段来自蒸馏稿、哪些刚被补全或校对过。</p>
          <div class="character-overview-trust-signals">
            <article v-for="item in trustSignals" :key="item.label" class="character-overview-trust-card" :class="'is-' + (item.tone || 'neutral')">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.copy }}</small>
            </article>
          </div>
        </section>

        <section class="detail-section">
          <div class="detail-section-head">
            <div>
              <p class="eyebrow">改动时间线</p>
              <h4>这一页最近怎样被写回过</h4>
            </div>
          </div>
          <p class="detail-section-copy">这里按时间记录字段补全、手动保存和增量蒸馏写回，方便快速回看这份角色资产是怎么稳起来的。</p>
          <div v-if="timelineItems.length" class="character-overview-change-timeline">
            <article v-for="item in timelineItems" :key="item.title + item.updated + item.badge" class="character-overview-change-item">
              <div class="character-overview-change-item-head">
                <strong>{{ item.title }}</strong>
                <small>{{ item.updated }}</small>
              </div>
              <p>{{ item.copy }}</p>
              <span>{{ item.badge }}</span>
            </article>
          </div>
          <p v-else class="card-note">还没有这位角色的改动记录，先补一次字段或继续增量蒸馏就会出现。</p>
        </section>

        <div class="character-overview-grid">
          <section class="detail-section">
            <div class="detail-section-head">
              <div>
                <p class="eyebrow">关键字段</p>
                <h4>先看这个角色最稳的骨架</h4>
              </div>
            </div>
            <div class="character-overview-fields">
              <article v-for="item in keyFields" :key="item.field" class="character-overview-field-card" :class="{ 'is-missing': item.weak }">
                <div class="character-overview-field-head">
                  <span>{{ item.label }}</span>
                  <div class="character-overview-field-actions">
                    <span v-for="tag in item.tags" :key="tag.label + tag.tone" class="character-overview-field-tag" :class="'is-' + tag.tone">{{ tag.label }}</span>
                    <button
                      v-if="item.weak"
                      type="button"
                      class="character-overview-mini-button"
                      :disabled="ui.autofillField === item.field"
                      @click="autofillField(item.field)"
                    >{{ ui.autofillField === item.field ? '生成中...' : 'AI补全' }}</button>
                    <button
                      type="button"
                      class="character-overview-mini-button"
                      :disabled="!item.dirty || ui.savingField === item.field"
                      @click="saveField(item.field)"
                    >{{ ui.savingField === item.field ? '保存中...' : (item.dirty ? '保存改动' : '已保存') }}</button>
                  </div>
                </div>
                <textarea
                  class="character-overview-field-input"
                  rows="4"
                  :value="item.value"
                  placeholder="可以直接在这里修改，然后点保存改动。"
                  @input="setField(item.field, $event.target.value)"
                ></textarea>
                <small class="character-overview-field-hint">{{ item.hint }}</small>
              </article>
            </div>
          </section>

          <section class="detail-section">
            <div class="detail-section-head">
              <div>
                <p class="eyebrow">声音与牵系</p>
                <h4>这一页最值得带进对话的部分</h4>
              </div>
            </div>
            <div class="character-overview-summary">
              <article v-for="item in voiceSummary" :key="'voice-' + item[0]" class="character-overview-summary-card">
                <span>{{ item[0] }}</span>
                <p>{{ item[1] }}</p>
              </article>
            </div>
            <div class="character-overview-summary">
              <article v-for="item in relationSummary" :key="'relation-' + item[0]" class="character-overview-summary-card">
                <span>{{ item[0] }}</span>
                <p>{{ item[1] }}</p>
              </article>
            </div>
          </section>
        </div>

        <section class="detail-section">
          <div class="detail-section-head">
            <div>
              <p class="eyebrow">细调字段</p>
              <h4>这些部分可以再慢慢抠细节</h4>
            </div>
          </div>
          <p class="detail-section-copy">默认先收起，等关键骨架稳了，再逐组展开做细修。</p>
          <div class="character-overview-advanced-groups">
            <article v-for="group in advancedGroups" :key="group.title" class="character-overview-advanced-group">
              <button
                type="button"
                class="character-overview-advanced-toggle"
                :class="{ 'is-open': group.expanded }"
                :aria-expanded="group.expanded ? 'true' : 'false'"
                @click="toggleAdvancedGroup(group.title)"
              >
                <span class="character-overview-advanced-title">{{ group.title }}</span>
                <span class="character-overview-advanced-meta">{{ group.items.length > 0 ? ('已填 ' + group.items.length + ' / ' + group.fieldNames.length) : '这一组还没铺开' }}</span>
                <span class="character-overview-advanced-arrow">{{ group.expanded ? '收起' : '展开' }}</span>
              </button>
              <p v-if="!group.expanded" class="character-overview-advanced-preview">{{ group.previewText }}</p>
              <div v-else class="character-overview-advanced-body">
                <article v-for="item in group.items" :key="group.title + item.field" class="character-overview-advanced-field">
                  <span>{{ item.label }}</span>
                  <p>{{ item.value }}</p>
                </article>
                <p v-if="!group.items.length" class="character-overview-advanced-empty">这一组暂时还没写开，可以先稳住关键字段，再决定要不要继续细修。</p>
              </div>
            </article>
          </div>
        </section>
      </div>
    `,
  }).mount(host);
})();
