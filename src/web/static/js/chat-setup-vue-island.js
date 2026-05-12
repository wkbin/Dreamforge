(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const vue = window.Vue;
  const host = document.getElementById("chat-setup-vue-root");
  const shell = document.getElementById("step-chat-setup");
  if (!bridge || !vue || !host || !shell) {
    return;
  }

  const { createApp, computed, nextTick, onBeforeUnmount, onMounted, ref } = vue;

  function actions() {
    const tools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};
    if (typeof tools.readLegacyActionBridge === "function") {
      return tools.readLegacyActionBridge("__ZAOMENG_CHAT_SETUP_ACTIONS__");
    }
    return window.__ZAOMENG_CHAT_SETUP_ACTIONS__ || {};
  }

  createApp({
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const expandedPanel = ref("");
      const unsubscribe = bridge.subscribe((nextSnapshot) => {
        snapshot.value = nextSnapshot || {};
      });

      onMounted(() => {
        shell.classList.add("has-vue-island");
        host.classList.remove("hidden");
        nextTick(() => {
          host.querySelector(".choice-card")?.focus();
        });
      });

      onBeforeUnmount(() => {
        unsubscribe();
      });

      const workflow = computed(() => snapshot.value.workflow || {});
      const setup = computed(() => snapshot.value.chatSetup || {});
      const visible = computed(() => {
        if (Boolean(workflow.value.showChatSetup || workflow.value.chatModePickerOpen)) {
          return true;
        }
        return !shell.classList.contains("hidden");
      });
      const mode = computed(() => String(setup.value.mode || "observe").trim());
      const isInsertMode = computed(() => mode.value === "insert");
      const participants = computed(() => Array.isArray(setup.value.participantList) ? setup.value.participantList : []);
      const availableCharacters = computed(() => Array.isArray(setup.value.availableCharacters) ? setup.value.availableCharacters : []);
      const openingPresets = computed(() => Array.isArray(setup.value.openingPresets) ? setup.value.openingPresets : []);
      const currentOpeningPreset = computed(() => openingPresets.value.find((item) => item.card_id === setup.value.openingPresetId) || setup.value.currentOpeningPreset || null);
      const sceneCards = computed(() => Array.isArray(setup.value.sceneCards) ? setup.value.sceneCards : []);
      const sceneRecommendation = computed(() => setup.value.sceneCardRecommendation || null);
      const currentSceneCard = computed(() => sceneCards.value.find((item) => item.card_id === setup.value.sceneCardId) || setup.value.currentSceneCard || null);
      const selfCards = computed(() => isInsertMode.value && Array.isArray(setup.value.selfCards) ? setup.value.selfCards : []);
      const currentSelfCard = computed(() => {
        if (!isInsertMode.value) return null;
        return selfCards.value.find((item) => item.card_id === setup.value.selfCardId) || setup.value.currentSelfCard || null;
      });
      const openingPresetEntries = computed(() =>
        openingPresets.value.map((item) => {
          return {
            id: item.card_id || "",
            title: item.preview?.title || item.fields?.title || item.card_id || "未命名模板",
            selected: (item.card_id || "") === String(setup.value.openingPresetId || "").trim(),
          };
        })
      );
      const sceneCardEntries = computed(() =>
        sceneCards.value.map((item) => {
          return {
            id: item.card_id || "",
            title: item.preview?.title || item.fields?.title || item.card_id || "未命名场景卡",
            selected: (item.card_id || "") === String(setup.value.sceneCardId || "").trim(),
          };
        })
      );
      const selfCardEntries = computed(() =>
        selfCards.value.map((item) => {
          return {
            id: item.card_id || "",
            title: item.preview?.display_name || item.fields?.display_name || item.card_id || "未命名角色卡",
            selected: (item.card_id || "") === String(setup.value.selfCardId || "").trim(),
          };
        })
      );

      function isSelected(name) {
        return participants.value.includes(name);
      }

      function setMode(nextMode) {
        const api = actions();
        if (typeof api.setMode === "function") api.setMode(nextMode);
        if (nextMode !== "insert" && expandedPanel.value === "self") {
          expandedPanel.value = "";
        }
      }

      function toggleParticipant(name) {
        const api = actions();
        if (typeof api.toggleParticipant === "function") api.toggleParticipant(name);
      }

      function setParticipantsFromInput(value) {
        const api = actions();
        if (typeof api.setParticipants === "function") api.setParticipants(value);
      }

      function setControlled(value) {
        const api = actions();
        if (typeof api.setControlledCharacter === "function") api.setControlledCharacter(value);
      }

      function setOpeningPreset(value) {
        const api = actions();
        if (typeof api.setOpeningPresetId === "function") api.setOpeningPresetId(value);
      }

      function applyOpeningPreset() {
        const api = actions();
        if (typeof api.applyOpeningPreset === "function") api.applyOpeningPreset();
      }

      function startOpeningPreset() {
        const api = actions();
        if (typeof api.applyOpeningPresetAndSubmit === "function") api.applyOpeningPresetAndSubmit();
      }

      function setSceneCard(value) {
        const api = actions();
        if (typeof api.setSceneCardId === "function") api.setSceneCardId(value);
      }

      function recommendSceneCard() {
        const api = actions();
        if (typeof api.recommendSceneCard === "function") api.recommendSceneCard();
      }

      function setSelfCard(value) {
        const api = actions();
        if (typeof api.setSelfCardId === "function") api.setSelfCardId(value);
      }

      function setSelfField(field, value) {
        const api = actions();
        if (typeof api.setSelfProfileField === "function") api.setSelfProfileField(field, value);
      }

      function submit() {
        const api = actions();
        if (typeof api.submit === "function") api.submit();
      }

      function createCard() {
        const api = actions();
        if (typeof api.openNewSelfCard === "function") api.openNewSelfCard();
      }

      function createSceneCard() {
        const api = actions();
        if (typeof api.openNewSceneCard === "function") api.openNewSceneCard();
      }

      function editCard() {
        const api = actions();
        if (typeof api.editCurrentSelfCard === "function") api.editCurrentSelfCard();
      }

      function editSceneCard() {
        const api = actions();
        if (typeof api.editCurrentSceneCard === "function") api.editCurrentSceneCard();
      }

      function createOpeningPreset() {
        const api = actions();
        if (typeof api.openNewOpeningPreset === "function") api.openNewOpeningPreset();
      }

      function editOpeningPreset() {
        const api = actions();
        if (typeof api.editCurrentOpeningPreset === "function") api.editCurrentOpeningPreset();
      }

      function togglePanel(panel) {
        expandedPanel.value = expandedPanel.value === panel ? "" : panel;
      }

      function sceneCardSummary(card) {
        if (!card) {
          return sceneCards.value.length ? "未选场景" : "无场景卡";
        }
        return card.preview?.title || card.fields?.title || card.card_id || "已选场景";
      }

      function selfCardSummary(card) {
        if (!card) {
          return selfCards.value.length ? "未选角色卡" : "无角色卡";
        }
        return card.preview?.display_name || card.fields?.display_name || card.card_id || "已选角色卡";
      }

      return {
        availableCharacters,
        applyOpeningPreset,
        createCard,
        createOpeningPreset,
        createSceneCard,
        currentOpeningPreset,
        currentSceneCard,
        currentSelfCard,
        editOpeningPreset,
        editCard,
        editSceneCard,
        expandedPanel,
        isInsertMode,
        isSelected,
        mode,
        openingPresets,
        openingPresetEntries,
        participants,
        recommendSceneCard,
        sceneCardEntries,
        sceneCardSummary,
        sceneCards,
        sceneRecommendation,
        setOpeningPreset,
        setSceneCard,
        selfCardEntries,
        selfCardSummary,
        selfCards,
        startOpeningPreset,
        setControlled,
        setMode,
        setParticipantsFromInput,
        setSelfCard,
        setSelfField,
        setup,
        submit,
        togglePanel,
        toggleParticipant,
        visible,
      };
    },
    template: `
      <form v-if="visible" class="stack-form chat-setup-vue-form" @submit.prevent="submit">
        <div class="choice-deck">
          <button type="button" class="choice-card" :class="{ active: mode === 'observe' }" @click="setMode('observe')">
            <strong>旁观此局</strong>
            <span>只看人物自然开口。</span>
          </button>
          <button type="button" class="choice-card" :class="{ active: mode === 'act' }" @click="setMode('act')">
            <strong>化身书中人</strong>
            <span>代入角色，亲自接话。</span>
          </button>
          <button type="button" class="choice-card" :class="{ active: mode === 'insert' }" @click="setMode('insert')">
            <strong>以自己入场</strong>
            <span>保留自己，走进故事。</span>
          </button>
        </div>

        <section class="detail-section chat-setup-optional-section">
          <div class="detail-section-head compact">
            <h4>可选设置</h4>
          </div>

          <div class="chat-setup-curation-stack">
            <article class="chat-setup-curation-card compact">
              <div class="chat-setup-curation-head">
                <div>
                  <span class="eyebrow">开局模板</span>
                  <strong class="chat-setup-summary-line">{{ currentOpeningPreset?.preview?.title || currentOpeningPreset?.fields?.title || (openingPresets.length ? '未选择' : '暂无模板') }}</strong>
                </div>
                <div class="card-actions">
                  <button type="button" class="soft-button" @click="togglePanel('opening')">{{ expandedPanel === 'opening' ? '收起' : '选择' }}</button>
                  <button v-if="setup.canEditCurrentOpeningPreset" type="button" class="soft-button" @click="editOpeningPreset">编辑当前模板</button>
                  <button type="button" class="soft-button" @click="createOpeningPreset">新建模板</button>
                </div>
              </div>
              <div v-if="expandedPanel === 'opening' && openingPresetEntries.length" class="chat-setup-option-list compact">
                <button
                  v-for="item in openingPresetEntries"
                  :key="item.id"
                  type="button"
                  class="chat-setup-option-card"
                  :class="{ active: item.selected }"
                  @click="setOpeningPreset(item.id)"
                >
                  <strong>{{ item.title }}</strong>
                </button>
              </div>
              <div v-else-if="expandedPanel === 'opening'" class="chat-setup-option-empty">
                <strong>还没有开局模板</strong>
              </div>
            </article>

            <article class="chat-setup-curation-card compact">
              <div class="chat-setup-curation-head">
                <div>
                  <span class="eyebrow">场景卡</span>
                  <strong class="chat-setup-summary-line">{{ sceneCardSummary(currentSceneCard) }}</strong>
                </div>
                <div class="card-actions">
                  <button type="button" class="soft-button" @click="togglePanel('scene')">{{ expandedPanel === 'scene' ? '收起' : '选择' }}</button>
                  <button type="button" class="soft-button" @click="recommendSceneCard">替我挑一张</button>
                  <button type="button" class="soft-button" @click="createSceneCard">新建场景卡</button>
                  <button v-if="setup.canEditCurrentSceneCard" type="button" class="soft-button" @click="editSceneCard">编辑当前卡</button>
                </div>
              </div>
              <div v-if="expandedPanel === 'scene' && sceneCardEntries.length" class="chat-setup-option-list compact">
                <button
                  v-for="item in sceneCardEntries"
                  :key="item.id"
                  type="button"
                  class="chat-setup-option-card"
                  :class="{ active: item.selected }"
                  @click="setSceneCard(item.id)"
                >
                  <strong>{{ item.title }}</strong>
                </button>
              </div>
              <div v-else-if="expandedPanel === 'scene'" class="chat-setup-option-empty">
                <strong>还没有场景卡</strong>
              </div>
            </article>

            <article v-if="isInsertMode" class="chat-setup-curation-card compact">
              <div class="chat-setup-curation-head">
                <div>
                  <span class="eyebrow">角色卡</span>
                  <strong class="chat-setup-summary-line">{{ selfCardSummary(currentSelfCard) }}</strong>
                </div>
                <div class="card-actions">
                  <button type="button" class="soft-button" @click="togglePanel('self')">{{ expandedPanel === 'self' ? '收起' : '选择' }}</button>
                  <button type="button" class="soft-button" @click="createCard">新建角色卡</button>
                  <button v-if="setup.canEditCurrentCard" type="button" class="soft-button" @click="editCard">编辑当前卡</button>
                </div>
              </div>
              <div v-if="expandedPanel === 'self' && selfCardEntries.length" class="chat-setup-option-list compact">
                <button
                  v-for="item in selfCardEntries"
                  :key="item.id"
                  type="button"
                  class="chat-setup-option-card"
                  :class="{ active: item.selected }"
                  @click="setSelfCard(item.id)"
                >
                  <strong>{{ item.title }}</strong>
                </button>
              </div>
              <div v-else-if="expandedPanel === 'self'" class="chat-setup-option-empty">
                <strong>还没有角色卡</strong>
              </div>
            </article>
          </div>
        </section>

        <label class="field-card">
          <span>这一场里，你想和谁同席</span>
          <div class="pill-row">
            <button
              v-for="name in availableCharacters"
              :key="name"
              type="button"
              class="pill"
              :class="{ active: isSelected(name) }"
              @click="toggleParticipant(name)"
            >
              {{ name }}
            </button>
            <span v-if="!availableCharacters.length" class="pill hint-pill">这卷暂时还没有可选角色</span>
          </div>
          <input :value="setup.participants || ''" type="text" placeholder="点选上方人物，或自行补充名字" @input="setParticipantsFromInput($event.target.value)" />
        </label>

        <label v-if="mode === 'act'" class="field-card">
          <span>此刻你是谁</span>
          <input :value="setup.controlledCharacter || ''" type="text" placeholder="例如：贾宝玉" @input="setControlled($event.target.value)" />
        </label>

        <template v-if="isInsertMode">
          <div class="mini-grid insert-self-grid">
            <label class="field-card">
              <span>他们会怎样称呼你</span>
              <input :value="setup.selfName || ''" type="text" placeholder="例如：阿眠" @input="setSelfField('display_name', $event.target.value)" />
            </label>
            <label class="field-card">
              <span>你在故事中的身份</span>
              <input :value="setup.selfIdentity || ''" type="text" placeholder="例如：误入园中的来客" @input="setSelfField('scene_identity', $event.target.value)" />
            </label>
            <label class="field-card">
              <span>今夜的氛围</span>
              <input :value="setup.selfStyle || ''" type="text" placeholder="例如：初见、夜谈、试探、久别重逢" @input="setSelfField('interaction_style', $event.target.value)" />
            </label>
          </div>
        </template>

        <div class="card-actions">
          <button type="submit" class="primary-button">进入这一幕</button>
        </div>

        <p class="card-note">{{ setup.status }}</p>
      </form>
    `,
  }).mount(host);
})();
