(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const webuiApi = window.__ZAOMENG_WEBUI_API__;
  const vue = window.Vue;
  const host = document.getElementById("persona-review-vue-root");
  const modal = document.getElementById("persona-review-modal");
  if (!bridge || !vue || !host || !modal || !webuiApi) {
    return;
  }

  const { createApp, computed, onBeforeUnmount, onMounted, reactive, ref } = vue;
  const schemas = window.__ZAOMENG_EDITOR_SCHEMAS__ || {};
  const editorComponents = window.__ZAOMENG_EDITOR_VUE_COMPONENTS__ || {};
  const bridgeTools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
  const KEY_FIELDS = Array.isArray(schemas.PERSONA_KEY_FIELDS) ? schemas.PERSONA_KEY_FIELDS : [];
  const ADVANCED_GROUPS = Array.isArray(schemas.PERSONA_ADVANCED_GROUPS) ? schemas.PERSONA_ADVANCED_GROUPS : [];
  const ALL_FIELDS = Array.isArray(schemas.PERSONA_ALL_FIELDS) ? schemas.PERSONA_ALL_FIELDS : [];

  function emptyFieldMap() {
    const fields = {};
    ALL_FIELDS.forEach((item) => {
      fields[item.field] = "";
    });
    return fields;
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function runDetailActions() {
    if (typeof bridgeTools.readLegacyActionBridge === "function") {
      return bridgeTools.readLegacyActionBridge("__ZAOMENG_RUN_DETAIL_ACTIONS__");
    }
    return window.__ZAOMENG_RUN_DETAIL_ACTIONS__ || {};
  }

  function syncPersonaBridgeState(source, overrides) {
    if (typeof bridgeTools.syncLegacyUiState === "function") {
      bridgeTools.syncLegacyUiState(source, overrides);
    } else if (typeof publishLegacyUiState === "function") {
      publishLegacyUiState(source, overrides);
    }
  }

  createApp({
    components: {
      SchemaFieldCard: editorComponents.SchemaFieldCard,
    },
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const modalVisible = ref(!modal.classList.contains("hidden"));
      const state = reactive({
        loading: false,
        saving: false,
        autofillField: "",
        character: "",
        status: "",
        fields: emptyFieldMap(),
        references: [],
        referenceSummary: "网页摘要参考",
        advancedOpen: false,
        feedback: {},
      });

      const unsubscribe = bridge.subscribe((nextSnapshot) => {
        snapshot.value = nextSnapshot || {};
      });

      function setStatus(message = "") {
        state.status = String(message || "").trim();
      }

      function applyReviewPayload(payload) {
        state.character = String(payload?.character || "").trim();
        state.fields = {
          ...emptyFieldMap(),
          ...(payload?.fields || {}),
        };
        state.feedback = {};
        state.references = [];
        state.referenceSummary = "网页摘要参考";
      }

      function applyAutofillReferences(payload) {
        const refs = Array.isArray(payload?.references) ? payload.references : [];
        state.references = refs;
        state.referenceSummary = refs.length ? `${refs.length} 条网页摘要参考` : "网页摘要参考";
      }

      async function loadCharacter(characterName) {
        const runId = String(snapshot.value.currentRunId || "").trim();
        const character = String(characterName || "").trim();
        if (!runId || !character) return;
          state.loading = true;
          setStatus("正在载入人物档案...");
        try {
          const payload = await webuiApi.getPersonaReview(runId, character);
          applyReviewPayload(payload);
          setStatus("");
          syncPersonaBridgeState("persona-review-vue-loaded", {
            currentPersonaReview: payload,
            currentPersonaAutofill: null,
          });
        } catch (error) {
          setStatus(error.message || "人物档案暂时没有载入。");
        } finally {
          state.loading = false;
        }
      }

      async function saveReview() {
        const runId = String(snapshot.value.currentRunId || "").trim();
        const character = String(state.character || "").trim();
        if (!runId || !character || state.saving) return;
        state.saving = true;
        setStatus("正在写回人物校对...");
        try {
          const saved = await webuiApi.savePersonaReview(runId, character, clone(state.fields));
          applyReviewPayload(saved);
          applyAutofillReferences(null);
          syncPersonaBridgeState("persona-review-vue-saved", {
            currentPersonaReview: saved,
            currentPersonaAutofill: null,
          });
          setStatus("人物校对已经写回这一卷。");
          const actions = runDetailActions();
          if (typeof actions.refreshRunView === "function") {
            await actions.refreshRunView(runId);
          } else {
            const run = await webuiApi.getRun(runId);
            if (typeof window.__ZAOMENG_APPLY_RUN_VIEW__ === "function") {
              window.__ZAOMENG_APPLY_RUN_VIEW__(run);
            } else if (typeof actions.renderRunView === "function") {
              actions.renderRunView(run);
            } else if (typeof window.renderRun === "function") {
              window.renderRun(run);
            }
          }
        } catch (error) {
          setStatus(error.message || "这次校对没有保存成功。");
        } finally {
          state.saving = false;
        }
      }

      async function autofillField(field) {
        const runId = String(snapshot.value.currentRunId || "").trim();
        const character = String(state.character || "").trim();
        const fieldName = String(field || "").trim();
        if (!runId || !character || !fieldName || state.autofillField) return;
        state.autofillField = fieldName;
        state.feedback[fieldName] = { kind: "loading", message: "正在生成补全..." };
        setStatus(`正在生成「${fieldLabel(fieldName)}」的补全内容...`);
        try {
          const payload = await webuiApi.suggestPersonaField(runId, character, fieldName);
          applyAutofillReferences(payload);
          syncPersonaBridgeState("persona-review-vue-autofill", {
            currentPersonaReview,
            currentPersonaAutofill: payload || null,
          });
          if (payload?.status === "filled" && payload?.value) {
            state.fields[fieldName] = payload.value;
            state.feedback[fieldName] = { kind: "success", message: "已生成补全内容，记得保存。" };
            setStatus(payload.message || "已生成补全内容，请记得保存人物校对。");
          } else {
            state.feedback[fieldName] = { kind: "error", message: payload?.message || payload?.reason || "人物信息补全无法生成。" };
            setStatus(payload?.message || payload?.reason || "人物信息补全无法生成。");
          }
        } catch (error) {
          applyAutofillReferences(null);
          syncPersonaBridgeState("persona-review-vue-autofill-cleared", {
            currentPersonaReview,
            currentPersonaAutofill: null,
          });
          state.feedback[fieldName] = { kind: "error", message: error.message || "人物信息补全无法生成。" };
          setStatus(error.message || "人物信息补全无法生成。");
        } finally {
          state.autofillField = "";
        }
      }

      function fieldLabel(field) {
        const item = ALL_FIELDS.find((entry) => entry.field === field);
        return item ? item.label : field;
      }

      function needsAutofill(field) {
        const value = String(state.fields[field] || "").trim();
        if (!value) return true;
        const normalized = value.replace(/\s+/g, "");
        return ["证据不足", "资料不足", "信息不足", "暂无资料", "暂缺", "待补充"].includes(normalized);
      }

      const availableCharacters = computed(() => {
        const items = Array.isArray(snapshot.value.currentRun?.artifact_index?.characters) ? snapshot.value.currentRun.artifact_index.characters : [];
        return items.map((item) => String(item?.name || "").trim()).filter(Boolean);
      });

      const visible = computed(() => modalVisible.value);

      onMounted(() => {
        modal.classList.add("has-vue-island");
        host.classList.remove("hidden");
        const observer = new MutationObserver(() => {
          modalVisible.value = !modal.classList.contains("hidden");
        });
        observer.observe(modal, { attributes: true, attributeFilter: ["class"] });
        host.__zaomengModalObserver = observer;
      });

      onBeforeUnmount(() => {
        host.__zaomengModalObserver?.disconnect?.();
        delete host.__zaomengModalObserver;
        unsubscribe();
      });

      const personaReviewActions = {
        openForCharacter(character) {
          state.character = String(character || "").trim();
          if (state.character) {
            loadCharacter(state.character);
          }
        },
        handleCharacterChange(character) {
          const target = String(character || "").trim();
          if (!target || target === state.character) return true;
          state.character = target;
          loadCharacter(target);
          return true;
        },
        submit() {
          saveReview();
          return true;
        },
        handleLegacyAutofillEvent(event) {
          const trigger = event?.target instanceof HTMLElement ? event.target.closest("[data-persona-autofill-field]") : null;
          if (!(trigger instanceof HTMLButtonElement)) return false;
          const field = trigger.getAttribute("data-persona-autofill-field") || "";
          if (!field) return false;
          autofillField(field);
          return true;
        },
      };

      if (typeof bridgeTools.mergeLegacyActionBridge === "function") {
        bridgeTools.mergeLegacyActionBridge("__ZAOMENG_PERSONA_REVIEW_ACTIONS__", personaReviewActions);
      } else {
        window.__ZAOMENG_PERSONA_REVIEW_ACTIONS__ = personaReviewActions;
      }

      return {
        state,
        visible,
        availableCharacters,
        keyFields: KEY_FIELDS,
        advancedGroups: ADVANCED_GROUPS,
        needsAutofill,
        fieldLabel,
        loadCharacter,
        saveReview,
        autofillField,
      };
    },
    template: `
      <form v-if="visible" class="stack-form persona-review-vue-form" @submit.prevent="saveReview">
        <label class="field-card">
          <span>当前人物</span>
          <select v-model="state.character" class="native-hidden" @change="loadCharacter(state.character)">
            <option v-for="name in availableCharacters" :key="name" :value="name">{{ name }}</option>
          </select>
          <div class="pill-row persona-pill-row modal-pill-row">
            <button
              v-for="name in availableCharacters"
              :key="'pill-' + name"
              type="button"
              class="pill persona-pill"
              :class="{ active: name === state.character }"
              @click="state.character = name; loadCharacter(name)"
            >
              {{ name }}
            </button>
            <span v-if="!availableCharacters.length" class="pill hint-pill">请先选择一卷已完成的人物</span>
          </div>
        </label>

        <section class="review-group">
          <div class="review-group-head">
            <strong>关键字段</strong>
            <p>先收紧最影响聊天味道的人物骨架。剩下的细字段收进二级菜单里慢慢磨。</p>
          </div>
          <div class="mini-grid persona-vue-grid">
            <schema-field-card
              v-for="item in keyFields"
              :key="item.field"
              :item="item"
              :model-value="state.fields[item.field]"
              :feedback="state.feedback[item.field] || null"
              :autofill-enabled="true"
              :autofill-field="state.autofillField"
              :needs-autofill="needsAutofill"
              @update:model-value="state.fields[item.field] = $event"
              @autofill="autofillField"
            />
          </div>
        </section>

        <details class="review-advanced-shell" :open="state.advancedOpen" @toggle="state.advancedOpen = $event.target.open">
          <summary class="review-advanced-trigger">
            <span>继续细调更多字段</span>
            <small>打开二级菜单，补全和微调全部剩余字段</small>
          </summary>
          <section v-for="group in advancedGroups" :key="group.title" class="review-group review-advanced-panel">
            <div class="review-group-head">
              <strong>{{ group.title }}</strong>
              <p>{{ group.copy }}</p>
            </div>
            <div class="mini-grid persona-vue-grid">
              <schema-field-card
                v-for="item in group.fields"
                :key="item.field"
                :item="item"
                :model-value="state.fields[item.field]"
                :feedback="state.feedback[item.field] || null"
                :autofill-enabled="true"
                :autofill-field="state.autofillField"
                :needs-autofill="needsAutofill"
                @update:model-value="state.fields[item.field] = $event"
                @autofill="autofillField"
              />
            </div>
          </section>
        </details>

        <div class="card-actions">
          <button type="submit" class="primary-button" :disabled="state.saving || state.loading">
            {{ state.saving ? '正在保存...' : '保存校对' }}
          </button>
        </div>

        <p class="card-note">{{ state.status }}</p>

        <details v-if="state.references.length" class="persona-reference-panel">
          <summary class="persona-reference-trigger">
            <span>看看这次补全参考了什么</span>
            <small>{{ state.referenceSummary }}</small>
          </summary>
          <div class="persona-reference-list">
            <article v-for="(item, index) in state.references" :key="'ref-' + index" class="persona-reference-card">
              <div class="persona-reference-head">
                <strong>{{ item.title || ('参考 ' + (index + 1)) }}</strong>
                <span v-if="item.source">{{ item.source }}</span>
              </div>
              <p v-if="item.query" class="persona-reference-query">检索词：{{ item.query }}</p>
              <p v-if="item.snippet" class="persona-reference-snippet">{{ item.snippet }}</p>
            </article>
          </div>
        </details>
      </form>
    `,
  }).mount(host);
})();
