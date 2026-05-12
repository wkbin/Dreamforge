(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const vue = window.Vue;
  const host = document.getElementById("chat-setup-vue-root");
  const shell = document.getElementById("step-chat-setup");
  if (!bridge || !vue || !host || !shell) {
    return;
  }

  const { createApp, computed, onBeforeUnmount, onMounted, ref } = vue;

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
      const unsubscribe = bridge.subscribe((nextSnapshot) => {
        snapshot.value = nextSnapshot || {};
      });

      onMounted(() => {
        shell.classList.add("has-vue-island");
        host.classList.remove("hidden");
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
      const participants = computed(() => Array.isArray(setup.value.participantList) ? setup.value.participantList : []);
      const availableCharacters = computed(() => Array.isArray(setup.value.availableCharacters) ? setup.value.availableCharacters : []);
      const selfCards = computed(() => Array.isArray(setup.value.selfCards) ? setup.value.selfCards : []);
      const currentSelfCard = computed(() => selfCards.value.find((item) => item.card_id === setup.value.selfCardId) || null);
      const selfPreviewPills = computed(() => {
        const preview = currentSelfCard.value?.preview || {};
        return [preview.core_identity, preview.story_role, preview.temperament_type, preview.speech_style, preview.soul_goal].filter(Boolean).slice(0, 5);
      });

      function isSelected(name) {
        return participants.value.includes(name);
      }

      function setMode(nextMode) {
        const api = actions();
        if (typeof api.setMode === "function") api.setMode(nextMode);
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

      function editCard() {
        const api = actions();
        if (typeof api.editCurrentSelfCard === "function") api.editCurrentSelfCard();
      }

      return {
        availableCharacters,
        createCard,
        currentSelfCard,
        editCard,
        isSelected,
        mode,
        participants,
        selfCards,
        selfPreviewPills,
        setControlled,
        setMode,
        setParticipantsFromInput,
        setSelfCard,
        setSelfField,
        setup,
        submit,
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

        <template v-if="mode === 'insert'">
          <label class="field-card">
            <span>直接带哪张角色卡入场</span>
            <select :value="setup.selfCardId || ''" @change="setSelfCard($event.target.value)">
              <option value="">{{ selfCards.length ? '先挑一张角色卡' : '还没有角色卡，先新建一张' }}</option>
              <option v-for="item in selfCards" :key="item.card_id" :value="item.card_id">
                {{ item.preview?.display_name || item.fields?.display_name || item.card_id || '未命名角色卡' }}
              </option>
            </select>
            <small id="dialogue-self-card-hint">{{ selfCards.length ? '不选也能手动写，但选卡后会把完整人设一起带进场景。' : '你还没有角色卡。先新建一张，后面就能直接选卡入场。' }}</small>
          </label>

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

          <section class="detail-section">
            <div class="detail-section-head">
              <div>
                <p class="eyebrow">角色卡预览</p>
                <h4>{{ currentSelfCard?.preview?.display_name || currentSelfCard?.fields?.display_name || (selfCards.length ? '还没有选中角色卡' : '你还没有角色卡') }}</h4>
              </div>
              <div class="card-actions">
                <button type="button" class="soft-button" @click="createCard">新建角色卡</button>
                <button v-if="setup.canEditCurrentCard" type="button" class="soft-button" @click="editCard">编辑当前卡</button>
              </div>
            </div>
            <p class="detail-section-copy">
              {{
                currentSelfCard
                  ? (currentSelfCard.preview?.scene_identity || currentSelfCard.fields?.scene_identity || currentSelfCard.fields?.core_identity || '这张卡已经接上，会把完整人设带进这场聊天。')
                  : (selfCards.length ? '选一张卡后，你的身份、气质和说话方式都会一起带进这场聊天。' : '先新建一张角色卡，后面就可以直接把完整人设带进场景。')
              }}
            </p>
            <div class="bookshelf-links">
              <span v-for="pill in selfPreviewPills" :key="pill">{{ pill }}</span>
            </div>
            <p v-if="!selfPreviewPills.length" class="chat-setup-inline-note">选中角色卡后，这里会显示最关键的几条入场标签。</p>
          </section>
        </template>

        <div class="card-actions">
          <button type="submit" class="primary-button">进入这一幕</button>
        </div>

        <p class="card-note">{{ setup.status }}</p>
      </form>
    `,
  }).mount(host);
})();
