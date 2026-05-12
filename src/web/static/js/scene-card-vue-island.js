(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const webuiApi = window.__ZAOMENG_WEBUI_API__;
  const vue = window.Vue;
  const host = document.getElementById("scene-card-vue-root");
  const modal = document.getElementById("scene-card-modal");
  if (!bridge || !webuiApi || !vue || !host || !modal) {
    return;
  }

  const { createApp, computed, onBeforeUnmount, onMounted, reactive, ref, watch } = vue;
  const schemas = window.__ZAOMENG_EDITOR_SCHEMAS__ || {};
  const editorComponents = window.__ZAOMENG_EDITOR_VUE_COMPONENTS__ || {};
  const FIELDS = Array.isArray(schemas.SCENE_CARD_FIELDS) ? schemas.SCENE_CARD_FIELDS : [];

  function emptyFields() {
    return Object.fromEntries(FIELDS.map((item) => [item.field, ""]));
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
        syncFromEditor(snapshot.value.currentSceneCardEditor || null);
      });

      watch(
        () => snapshot.value.currentSceneCardEditor,
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
      const duplicateVisible = computed(() => Boolean(state.cardId));

      function syncLegacyFields() {
        if (typeof setValue === "function") {
          setValue("scene-card-id", state.cardId);
        }
        Object.entries(state.fields).forEach(([field, value]) => {
          if (typeof sceneCardFieldId !== "function" || typeof setValue !== "function") return;
          const id = sceneCardFieldId(field);
          if (id) setValue(id, value);
        });
        if (typeof updateSceneCardDeleteButton === "function") {
          updateSceneCardDeleteButton(false);
        }
      }

      function publish(source = "scene-card-vue") {
        syncLegacyFields();
        if (typeof setStatus === "function") {
          setStatus("scene-card-status", state.status);
        }
        if (typeof publishSceneCardEditorState === "function") {
          publishSceneCardEditorState(source);
        }
      }

      function updateField(field, value) {
        state.fields[field] = value;
        publish("scene-card-vue-input");
      }

      async function generate() {
        if (state.generating || state.saving || state.deleting) return;
        state.generating = true;
        state.status = "正在随机生成一张场景卡...";
        publish("scene-card-vue-generating");
        try {
          const payload = await webuiApi.generateSceneCard();
          state.fields = {
            ...state.fields,
            ...(payload?.fields || {}),
          };
          state.status = "AI 已经把场景先搭好了，你可以直接保存，也可以再细调。";
          publish("scene-card-vue-generated");
        } catch (error) {
          state.status = error.message || "场景卡生成失败。";
          publish("scene-card-vue-generate-failed");
        } finally {
          state.generating = false;
        }
      }

      async function save() {
        if (state.generating || state.saving || state.deleting) return;
        const fields = clone(state.fields);
        const validationMessage = typeof validateSceneCardPayload === "function" ? validateSceneCardPayload(fields) : "";
        if (validationMessage) {
          state.status = validationMessage;
          publish("scene-card-vue-validation-failed");
          return;
        }
        state.saving = true;
        state.status = "正在保存场景卡...";
        publish("scene-card-vue-saving");
        try {
          const payload = await webuiApi.saveSceneCard(state.cardId, fields);
          state.cardId = String(payload?.card_id || "").trim();
          await loadSceneCards();
          const select = el("dialogue-scene-card");
          if (select) {
            select.value = state.cardId;
            syncCustomSelect("dialogue-scene-card");
          }
          syncSelectedSceneCardFromSelect();
          state.status = "场景卡已保存。";
          publish("scene-card-vue-saved");
          if (typeof setStatus === "function") {
            setStatus("dialogue-session-status", "场景卡已经接好，这一幕会按它的氛围和推进方向展开。");
          }
          closeSceneCardModal();
        } catch (error) {
          state.status = error.message || "场景卡保存失败。";
          publish("scene-card-vue-save-failed");
        } finally {
          state.saving = false;
        }
      }

      async function removeCard() {
        if (!state.cardId || state.generating || state.saving || state.deleting) return;
        if (!window.confirm("确定删除这张场景卡吗？")) return;
        state.deleting = true;
        state.status = "正在删除场景卡...";
        publish("scene-card-vue-deleting");
        try {
          await webuiApi.deleteSceneCard(state.cardId);
          if (selectedSceneCardId === state.cardId) {
            selectedSceneCardId = "";
          }
          state.cardId = "";
          state.fields = emptyFields();
          await loadSceneCards();
          currentSceneCard = null;
          renderSelectedSceneCardPreview();
          state.status = "场景卡已经删掉了。";
          publish("scene-card-vue-deleted");
          if (typeof setStatus === "function") {
            setStatus("dialogue-session-status", "场景卡已经删掉了。");
          }
          closeSceneCardModal();
        } catch (error) {
          state.status = error.message || "场景卡删除失败。";
          publish("scene-card-vue-delete-failed");
        } finally {
          state.deleting = false;
        }
      }

      function duplicateCard() {
        state.cardId = "";
        state.status = "已经按当前内容另起一张新卡。保存后会成为独立场景卡。";
        publish("scene-card-vue-duplicated");
      }

      return {
        deleteVisible,
        duplicateCard,
        duplicateVisible,
        fields: FIELDS,
        generate,
        removeCard,
        save,
        state,
        updateField,
        visible,
      };
    },
    template: `
      <form v-if="visible" class="stack-form scene-card-vue-form" @submit.prevent="save">
        <div class="card-actions">
          <button type="button" class="soft-button" :disabled="state.generating || state.saving || state.deleting" @click="generate">
            {{ state.generating ? '生成中...' : 'AI随机生成' }}
          </button>
        </div>

        <section class="review-group">
          <div class="review-group-head">
            <strong>场景骨架</strong>
            <p>先定下这一幕发生在哪、是什么气氛、从什么局面起势，再决定它往哪一拍推。</p>
          </div>
          <schema-field-card
            v-for="item in fields"
            :key="item.field"
            :item="item"
            :model-value="state.fields[item.field]"
            @update:model-value="updateField(item.field, $event)"
          />
        </section>

        <div class="card-actions">
          <button v-if="duplicateVisible" type="button" class="soft-button" :disabled="state.generating || state.saving || state.deleting" @click="duplicateCard">
            另存为新卡
          </button>
          <button v-if="deleteVisible" type="button" class="soft-button" :disabled="state.generating || state.saving || state.deleting" @click="removeCard">
            {{ state.deleting ? '删除中...' : '删除这张卡' }}
          </button>
          <button type="submit" class="primary-button" :disabled="state.generating || state.saving || state.deleting">
            {{ state.saving ? '保存中...' : '保存场景卡' }}
          </button>
        </div>

        <p class="card-note">{{ state.status }}</p>
      </form>
    `,
  }).mount(host);
})();
