(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const webuiApi = window.__ZAOMENG_WEBUI_API__;
  const vue = window.Vue;
  const host = document.getElementById("self-card-vue-root");
  const modal = document.getElementById("self-card-modal");
  if (!bridge || !webuiApi || !vue || !host || !modal) {
    return;
  }

  const { createApp, computed, onBeforeUnmount, onMounted, reactive, ref, watch } = vue;
  const schemas = window.__ZAOMENG_EDITOR_SCHEMAS__ || {};
  const editorComponents = window.__ZAOMENG_EDITOR_VUE_COMPONENTS__ || {};
  const ENTRY_FIELDS = Array.isArray(schemas.SELF_CARD_ENTRY_FIELDS) ? schemas.SELF_CARD_ENTRY_FIELDS : [];
  const KEY_FIELDS = Array.isArray(schemas.PERSONA_KEY_FIELDS) ? schemas.PERSONA_KEY_FIELDS : [];
  const ADVANCED_GROUPS = Array.isArray(schemas.PERSONA_ADVANCED_GROUPS)
    ? schemas.PERSONA_ADVANCED_GROUPS.map((group) => ({
      title: group.title,
      copy: group.selfCardCopy || group.copy,
      fields: group.fields,
    }))
    : [];
  const ALL_FIELDS = Array.isArray(schemas.SELF_CARD_ALL_FIELDS) ? schemas.SELF_CARD_ALL_FIELDS : [];

  function emptyFields() {
    return Object.fromEntries(ALL_FIELDS.map((item) => [item.field, ""]));
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  createApp({
    components: {
      SchemaFieldCard: editorComponents.SchemaFieldCard,
    },
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const modalVisible = ref(!modal.classList.contains("hidden"));
      const state = reactive({
        fields: emptyFields(),
        cardId: "",
        status: "",
        saving: false,
        generating: false,
        deleting: false,
        signature: "",
      });

      function syncFromEditor(editor) {
        const nextSignature = JSON.stringify(editor || null);
        if (state.signature === nextSignature) return;
        state.signature = nextSignature;
        state.cardId = String(editor?.cardId || "").trim();
        state.status = String(editor?.status || "").trim();
        state.fields = {
          ...emptyFields(),
          ...(editor?.fields || {}),
        };
      }

      const unsubscribe = bridge.subscribe((nextSnapshot) => {
        snapshot.value = nextSnapshot || {};
        syncFromEditor(snapshot.value.currentSelfCardEditor || null);
      });

      watch(
        () => snapshot.value.currentSelfCardEditor,
        (value) => {
          syncFromEditor(value || null);
        },
        { deep: true, immediate: true }
      );

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

      const visible = computed(() => modalVisible.value);
      const deleteVisible = computed(() => Boolean(state.cardId));
      const primaryEntryFields = computed(() => ENTRY_FIELDS.slice(0, 2));
      const secondaryEntryFields = computed(() => ENTRY_FIELDS.slice(2));

      function syncLegacyFields() {
        if (typeof setValue === "function") {
          setValue("self-card-id", state.cardId);
        }
        Object.entries(state.fields).forEach(([field, value]) => {
          if (typeof selfCardFieldId !== "function" || typeof setValue !== "function") return;
          const id = selfCardFieldId(field);
          if (id) setValue(id, value);
        });
        if (typeof updateSelfCardDeleteButton === "function") {
          updateSelfCardDeleteButton(false);
        }
      }

      function publish(source = "self-card-vue") {
        syncLegacyFields();
        if (typeof setStatus === "function") {
          setStatus("self-card-status", state.status);
        }
        if (typeof publishSelfCardEditorState === "function") {
          publishSelfCardEditorState(source);
        }
      }

      function updateField(field, value) {
        state.fields[field] = value;
        publish("self-card-vue-input");
      }

      async function generate() {
        if (state.generating || state.saving || state.deleting) return;
        state.generating = true;
        state.status = "正在随机生成一张角色卡...";
        publish("self-card-vue-generating");
        try {
          const payload = await webuiApi.generateSelfCard();
          state.fields = {
            ...state.fields,
            ...(payload?.fields || {}),
          };
          state.status = "AI 已经把整张卡先填好了，你可以直接保存，也可以再手修。";
          publish("self-card-vue-generated");
        } catch (error) {
          state.status = error.message || "角色卡生成失败。";
          publish("self-card-vue-generate-failed");
        } finally {
          state.generating = false;
        }
      }

      async function save() {
        if (state.generating || state.saving || state.deleting) return;
        const fields = clone(state.fields);
        const validationMessage = typeof validateSelfCardPayload === "function" ? validateSelfCardPayload(fields) : "";
        if (validationMessage) {
          state.status = validationMessage;
          publish("self-card-vue-validation-failed");
          return;
        }
        state.saving = true;
        state.status = "正在保存角色卡...";
        publish("self-card-vue-saving");
        try {
          const payload = await webuiApi.saveSelfCard(state.cardId, fields);
          state.cardId = String(payload?.card_id || "").trim();
          await loadSelfCards();
          const select = el("dialogue-self-card");
          if (select) {
            select.value = state.cardId;
            syncCustomSelect("dialogue-self-card");
          }
          syncSelectedSelfCardFromSelect();
          state.status = "角色卡已保存。";
          publish("self-card-vue-saved");
          if (typeof setStatus === "function") {
            setStatus("dialogue-session-status", "角色卡已经接好，现在可以直接带它入场。");
          }
          closeSelfCardModal();
        } catch (error) {
          state.status = error.message || "角色卡保存失败。";
          publish("self-card-vue-save-failed");
        } finally {
          state.saving = false;
        }
      }

      async function removeCard() {
        if (!state.cardId || state.generating || state.saving || state.deleting) return;
        if (!window.confirm("确定删除这张角色卡吗？")) return;
        state.deleting = true;
        state.status = "正在删除角色卡...";
        publish("self-card-vue-deleting");
        try {
          await webuiApi.deleteSelfCard(state.cardId);
          if (selectedSelfCardId === state.cardId) {
            selectedSelfCardId = "";
          }
          state.cardId = "";
          state.fields = emptyFields();
          await loadSelfCards();
          currentSelfCard = null;
          renderSelectedSelfCardPreview();
          state.status = "角色卡已经删掉了。";
          publish("self-card-vue-deleted");
          if (typeof setStatus === "function") {
            setStatus("dialogue-session-status", "角色卡已经删掉了。");
          }
          closeSelfCardModal();
        } catch (error) {
          state.status = error.message || "角色卡删除失败。";
          publish("self-card-vue-delete-failed");
        } finally {
          state.deleting = false;
        }
      }

      return {
        advancedGroups: ADVANCED_GROUPS,
        deleteVisible,
        entryFields: ENTRY_FIELDS,
        keyFields: KEY_FIELDS,
        primaryEntryFields,
        removeCard,
        save,
        secondaryEntryFields,
        state,
        updateField,
        visible,
        generate,
      };
    },
    template: `
      <form v-if="visible" class="stack-form self-card-vue-form" @submit.prevent="save">
        <div class="card-actions">
          <button type="button" class="soft-button" :disabled="state.generating || state.saving || state.deleting" @click="generate">
            {{ state.generating ? '生成中...' : 'AI随机生成' }}
          </button>
        </div>

        <section class="review-group">
          <div class="review-group-head">
            <strong>入场信息</strong>
            <p>先决定他们如何称呼你、你以什么身份走进场景，以及你想要的互动气氛。</p>
          </div>
          <div class="mini-grid">
            <schema-field-card
              v-for="item in primaryEntryFields"
              :key="item.field"
              :item="item"
              :model-value="state.fields[item.field]"
              @update:model-value="updateField(item.field, $event)"
            />
          </div>
          <schema-field-card
            v-for="item in secondaryEntryFields"
            :key="item.field"
            :item="item"
            :model-value="state.fields[item.field]"
            @update:model-value="updateField(item.field, $event)"
          />
        </section>

        <section class="review-group">
          <div class="review-group-head">
            <strong>关键字段</strong>
            <p>先把你这个人立住：别人眼里你是谁，你怎么说话，你看起来像什么样，会被什么关系牵动。</p>
          </div>
          <schema-field-card
            v-for="item in keyFields"
            :key="item.field"
            :item="item"
            :model-value="state.fields[item.field]"
            @update:model-value="updateField(item.field, $event)"
          />
        </section>

        <details class="review-advanced-shell">
          <summary class="review-advanced-trigger">
            <span>继续细调完整角色卡</span>
            <small>打开后可把更多心理、对白和情绪细节一起写满</small>
          </summary>

          <section v-for="group in advancedGroups" :key="group.title" class="review-group review-advanced-panel">
            <div class="review-group-head">
              <strong>{{ group.title }}</strong>
              <p>{{ group.copy }}</p>
            </div>
            <schema-field-card
              v-for="field in group.fields"
              :key="field.field"
              :item="field"
              :model-value="state.fields[field.field]"
              @update:model-value="updateField(field.field, $event)"
            />
          </section>
        </details>

        <div class="card-actions">
          <button v-if="deleteVisible" type="button" class="soft-button" :disabled="state.generating || state.saving || state.deleting" @click="removeCard">
            {{ state.deleting ? '删除中...' : '删除这张卡' }}
          </button>
          <button type="submit" class="primary-button" :disabled="state.generating || state.saving || state.deleting">
            {{ state.saving ? '保存中...' : '保存角色卡' }}
          </button>
        </div>

        <p class="card-note">{{ state.status }}</p>
      </form>
    `,
  }).mount(host);
})();
