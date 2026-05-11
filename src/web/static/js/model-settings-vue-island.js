(() => {
  const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
  const webuiApi = window.__ZAOMENG_WEBUI_API__;
  const vue = window.Vue;
  const host = document.getElementById("model-settings-vue-root");
  const modal = document.getElementById("settings-modal");
  const legacy = document.getElementById("model-settings-legacy");
  if (!bridge || !webuiApi || !vue || !host || !modal || !legacy) {
    return;
  }

  const { computed, createApp, onBeforeUnmount, onMounted, reactive, ref, watch } = vue;
  const PROVIDERS = [
    { value: "openai-compatible", title: "通用接口", copy: "适合大多数兼容 OpenAI 的声源" },
    { value: "openai", title: "OpenAI", copy: "直接连到 OpenAI 官方接口" },
    { value: "anthropic", title: "Anthropic", copy: "用 Claude 系列声源继续故事" },
    { value: "ollama", title: "Ollama", copy: "连接本地已运行的模型服务" },
  ];

  function emptyDraft() {
    return {
      provider: "openai-compatible",
      model: "",
      base_url: "",
      api_key: "",
      max_tokens: "",
    };
  }

  function modelSettingsSnapshot(settings) {
    return JSON.stringify({
      provider: settings?.provider || "",
      model: settings?.model || "",
      base_url: settings?.base_url || "",
      max_tokens: settings?.max_tokens || 0,
      api_key_configured: Boolean(settings?.api_key_configured),
      configured: Boolean(settings?.configured),
    });
  }

  createApp({
    setup() {
      const snapshot = ref(bridge.getSnapshot ? bridge.getSnapshot() : {});
      const state = reactive({
        saving: false,
        status: "",
        draft: emptyDraft(),
      });

      const unsubscribe = typeof bridge.subscribe === "function"
        ? bridge.subscribe((nextSnapshot) => {
          snapshot.value = nextSnapshot || {};
        })
        : () => {};

      const modelSettingsState = computed(() => snapshot.value.modelSettings || { configured: false, provider: "openai-compatible" });
      const settingsKey = computed(() => modelSettingsSnapshot(modelSettingsState.value));
      const apiKeyHint = computed(() => modelSettingsState.value.api_key_configured ? "当前密钥已经保存，留空提交时会继续沿用。" : "留空时会沿用已经保存的密钥。");
      const apiKeyPlaceholder = computed(() => modelSettingsState.value.api_key_configured ? "当前密钥已保存，如需更换再填写" : "把密钥放在这里，故事才会真正开口");
      const maxTokensHint = computed(() => {
        const maxTokens = Number(modelSettingsState.value.max_tokens || 0);
        return maxTokens > 0
          ? `当前单次输出上限为 ${maxTokens}，留空或填 0 会改回默认值。`
          : "当前未另设单次输出上限，会沿用默认值。";
      });
      const maxTokensPlaceholder = computed(() => {
        const maxTokens = Number(modelSettingsState.value.max_tokens || 0);
        return maxTokens > 0 ? String(maxTokens) : "留空或填 0，则沿用推荐值";
      });

      function applySettingsToDraft(settings) {
        state.draft = {
          provider: settings?.provider || "openai-compatible",
          model: settings?.model || "",
          base_url: settings?.base_url || "",
          api_key: "",
          max_tokens: Number(settings?.max_tokens || 0) > 0 ? String(settings.max_tokens) : "",
        };
      }

      watch(settingsKey, () => {
        applySettingsToDraft(modelSettingsState.value);
      }, { immediate: true });

      onMounted(() => {
        modal.classList.add("has-vue-island");
        host.classList.remove("hidden");
        legacy.classList.add("hidden");
      });

      onBeforeUnmount(() => {
        unsubscribe();
      });

      function close() {
        if (typeof closeSettingsModal === "function") {
          closeSettingsModal();
        }
      }

      async function submit() {
        state.saving = true;
        state.status = "正在把故事声源接进来...";
        try {
          modelSettings = await webuiApi.saveModelSettings({
            provider: String(state.draft.provider || "openai-compatible").trim(),
            model: String(state.draft.model || "").trim(),
            base_url: String(state.draft.base_url || "").trim(),
            api_key: String(state.draft.api_key || "").trim(),
            max_tokens: Math.max(0, Number(state.draft.max_tokens || 0) || 0),
          });
          applyModelSettingsView();
          state.status = "故事声源已经接通。";
          close();
          updateWorkflowState();
        } catch (error) {
          state.status = error.message || "这次连接没有成功。";
        } finally {
          state.saving = false;
        }
      }

      return {
        apiKeyHint,
        apiKeyPlaceholder,
        close,
        maxTokensHint,
        maxTokensPlaceholder,
        providers: PROVIDERS,
        state,
        submit,
      };
    },
    template: `
      <form class="stack-form model-settings-vue-form" @submit.prevent="submit">
        <section class="connection-details">
          <label class="field-card">
            <span>故事声源</span>
            <div class="choice-deck provider-deck modal-choice-deck">
              <button
                v-for="item in providers"
                :key="item.value"
                type="button"
                class="choice-card compact-choice-card"
                :class="{ active: state.draft.provider === item.value }"
                @click="state.draft.provider = item.value"
              >
                <strong>{{ item.title }}</strong>
                <span>{{ item.copy }}</span>
              </button>
            </div>
          </label>

          <div class="mini-grid">
            <label class="field-card">
              <span>声源名</span>
              <input v-model="state.draft.model" type="text" placeholder="例如：deepseek-chat / gpt-4.1 / qwen2.5:14b" />
            </label>
            <label class="field-card">
              <span>入口地址</span>
              <input v-model="state.draft.base_url" type="text" placeholder="例如：https://api.openai.com/v1" />
            </label>
          </div>

          <div class="mini-grid">
            <label class="field-card">
              <span>通信密钥</span>
              <input v-model="state.draft.api_key" type="password" :placeholder="apiKeyPlaceholder" />
              <small>{{ apiKeyHint }}</small>
            </label>
            <label class="field-card">
              <span>单次输出上限</span>
              <input v-model="state.draft.max_tokens" type="number" min="0" max="16000" step="100" :placeholder="maxTokensPlaceholder" />
              <small>{{ maxTokensHint }}</small>
            </label>
          </div>
        </section>

        <div class="card-actions">
          <button type="button" class="soft-button" :disabled="state.saving" @click="close">稍后再说</button>
          <button type="submit" class="primary-button" :disabled="state.saving">{{ state.saving ? '保存中...' : '保存' }}</button>
        </div>
        <p class="card-note">{{ state.status }}</p>
      </form>
    `,
  }).mount(host);
})();
