(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const webuiApi = window.__ZAOMENG_WEBUI_API__;
  const vue = window.Vue;
  const bridgeTools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
  const host = document.getElementById("relation-details-vue-root");
  const modal = document.getElementById("relation-details-modal");
  if (!bridge || !webuiApi || !vue || !host || !modal) {
    return;
  }

  const { createApp, computed, onBeforeUnmount, onMounted, reactive, ref, watch } = vue;

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function syncRelationBridgeState(source, overrides) {
    if (typeof bridgeTools.syncLegacyUiState === "function") {
      bridgeTools.syncLegacyUiState(source, overrides);
    } else if (typeof publishLegacyUiState === "function") {
      publishLegacyUiState(source, overrides);
    }
  }

  createApp({
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const modalVisible = ref(!modal.classList.contains("hidden"));
      const state = reactive({
        status: "",
        savingPairKey: "",
        items: [],
        conflicts: [],
        signature: "",
      });

      function syncFromPayload(payload) {
        const nextSignature = JSON.stringify(payload || null);
        if (state.signature === nextSignature) return;
        state.signature = nextSignature;
        state.items = Array.isArray(payload?.items) ? clone(payload.items) : [];
        state.conflicts = Array.isArray(payload?.conflicts) ? clone(payload.conflicts) : [];
        if (!payload) {
          state.status = "正在整理关系明细...";
          return;
        }
        if (!state.savingPairKey) {
          state.status = state.items.length ? "" : "这张关系网暂时还没有明细。";
        }
      }

      const unsubscribe = bridge.subscribe((nextSnapshot) => {
        snapshot.value = nextSnapshot || {};
        syncFromPayload(snapshot.value.currentRelationDetails || null);
      });

      watch(
        () => snapshot.value.currentRelationDetails,
        (value) => {
          syncFromPayload(value || null);
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
      const conflictMap = computed(() => {
        return new Map(
          state.conflicts
            .filter((item) => item?.pair_key)
            .map((item) => [item.pair_key, item])
        );
      });

      async function saveItem(item) {
        const runId = String(snapshot.value.currentRunId || "").trim();
        const pairKey = String(item?.pair_key || "").trim();
        if (!runId || !pairKey || state.savingPairKey) return;
        state.savingPairKey = pairKey;
        state.status = "正在保存关系修改...";
        try {
          const body = {
            trust: item.trust,
            affection: item.affection,
            hostility: item.hostility,
            ambiguity: item.ambiguity,
            relationship_type: item.relationship_type,
            typical_interaction: item.typical_interaction,
            conflict_point: item.conflict_point,
            relation_change: item.relation_change,
          };
          const refreshed = await webuiApi.saveRelationDetail(runId, pairKey, body);
          syncFromPayload(refreshed);
          syncRelationBridgeState("relation-details-vue-saved", { currentRelationDetails: refreshed });
          state.status = "关系已保存。";
        } catch (error) {
          state.status = error.message || "关系保存失败。";
        } finally {
          state.savingPairKey = "";
        }
      }

      function clampMetric(item, field) {
        const numeric = Number(item[field]);
        if (Number.isNaN(numeric)) {
          item[field] = 0;
          return;
        }
        item[field] = Math.max(0, Math.min(10, numeric));
      }

      function pairTitle(item) {
        const names = Array.isArray(item?.characters) ? item.characters.filter(Boolean) : [];
        return names.length ? names.join("、") : (item?.pair_key || "未命名关系");
      }

      function conflictLabel(item) {
        const conflict = conflictMap.value.get(item?.pair_key || "");
        return Array.isArray(conflict?.tags) && conflict.tags.length ? `冲突：${conflict.tags.join("，")}` : "";
      }

      return {
        clampMetric,
        conflictLabel,
        pairTitle,
        saveItem,
        state,
        visible,
      };
    },
    template: `
      <div v-if="visible" class="relation-details-vue-shell">
        <article v-for="item in state.items" :key="item.pair_key" class="relation-detail-card">
          <div class="relation-detail-head">
            <strong>{{ pairTitle(item) }}</strong>
            <span class="relation-detail-type">
              {{ item.relationship_type || '牵连' }}
              <template v-if="conflictLabel(item)"> · {{ conflictLabel(item) }}</template>
            </span>
          </div>

          <div class="relation-detail-edit-grid">
            <label>信 <input v-model.number="item.trust" type="number" min="0" max="10" @change="clampMetric(item, 'trust')" /></label>
            <label>情 <input v-model.number="item.affection" type="number" min="0" max="10" @change="clampMetric(item, 'affection')" /></label>
            <label>冲 <input v-model.number="item.hostility" type="number" min="0" max="10" @change="clampMetric(item, 'hostility')" /></label>
            <label>疑 <input v-model.number="item.ambiguity" type="number" min="0" max="10" @change="clampMetric(item, 'ambiguity')" /></label>
          </div>

          <div class="relation-detail-copy relation-detail-edit-text">
            <label>关系类型<input v-model="item.relationship_type" type="text" /></label>
            <label>互动摘要<textarea v-model="item.typical_interaction" rows="2"></textarea></label>
            <label>冲突点<textarea v-model="item.conflict_point" rows="2"></textarea></label>
            <label>关系变化<textarea v-model="item.relation_change" rows="2"></textarea></label>
          </div>

          <div class="relation-detail-save-row">
            <button
              type="button"
              class="soft-button"
              :disabled="state.savingPairKey === item.pair_key"
              @click="saveItem(item)"
            >
              {{ state.savingPairKey === item.pair_key ? '保存中...' : '保存' }}
            </button>
          </div>

          <div class="relation-detail-evidence">
            <p>证据句</p>
            <ul>
              <li v-for="line in (item.evidence_lines || [])" :key="line">{{ line }}</li>
            </ul>
          </div>
        </article>

        <p v-if="!state.items.length" class="card-note">{{ state.status || '这张关系网暂时还没有明细。' }}</p>
        <p v-else class="card-note">{{ state.status }}</p>
      </div>
    `,
  }).mount(host);
})();
