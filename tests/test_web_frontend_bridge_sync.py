from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
JS_ROOT = REPO_ROOT / "src" / "web" / "static" / "js"
FRAGMENT_ROOT = REPO_ROOT / "src" / "web" / "static" / "fragments"


def read_js(name: str) -> str:
    return (JS_ROOT / name).read_text(encoding="utf-8")


def read_fragment(name: str) -> str:
    return (FRAGMENT_ROOT / name).read_text(encoding="utf-8")


class WebFrontendBridgeSyncTests(unittest.TestCase):
    def test_bootstrap_loads_webui_api_before_bookshelf_island(self):
        content = read_js("bootstrap.js")
        api_index = content.index('/web/js/webui-api.js?v=${version}')
        island_index = content.index('/web/js/bookshelf-vue-island.js?v=${version}')
        self.assertLess(api_index, island_index)

    def test_bootstrap_keeps_optional_islands_non_fatal(self):
        content = read_js("bootstrap.js")
        self.assertIn("const coreScripts = [", content)
        self.assertIn("const optionalScripts = [", content)
        self.assertIn("await loadScriptBatch(coreScripts);", content)
        self.assertIn("await loadScriptBatch(optionalScripts, { continueOnError: true });", content)
        self.assertIn("renderBootFailure(error);", content)

    def test_dialogue_publish_includes_session_payloads_for_bridge_sync(self):
        content = read_js("dialogue.js")
        self.assertIn("const UI_BRIDGE_TOOLS = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};", content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-rendered", {', content)
        self.assertIn("currentDialogueSessionId,", content)
        self.assertIn("currentDialogueSession: session,", content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-booting", {', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-restore", {', content)
        self.assertIn('window.applyDialogueSceneTimelineEntry(item);', content)
        self.assertIn('window.branchDialogueSessionFromScene(index);', content)

    def test_main_publishes_optimistic_dialogue_and_suggest_retry_state(self):
        content = read_js("main.js")
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-optimistic", {', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-restore", {', content)
        self.assertIn('publishComposerUiState("composer-suggest-retrying");', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("relation-details-loading", { currentRelationDetails: null });', content)
        self.assertIn("window.applyDialogueSceneTimelineEntry = applyDialogueSceneTimelineEntry;", content)
        self.assertIn("window.branchDialogueSessionFromScene = branchDialogueSessionFromScene;", content)
        self.assertIn("function renderDialogueSceneChainSuggestions(chains = [], sessionId = \"\") {", content)
        self.assertIn("function applyDialogueSceneChain(chain = {}) {", content)

    def test_main_uses_shared_bridge_sync_for_self_card_state(self):
        content = read_js("main.js")
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("opening-presets-loaded", { openingPresets, currentOpeningPreset, selectedOpeningPresetId });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("opening-preset-selection-changed", {', content)
        self.assertIn("selectedOpeningPresetId,", content)
        self.assertIn("currentOpeningPreset,", content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState(source, { currentSceneCardEditor });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("scene-cards-loaded", { sceneCards });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("scene-card-selection-changed", {', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("scene-card-recommended", { currentSceneCardRecommendation });', content)
        self.assertIn("selectedSceneCardId,", content)
        self.assertIn("currentSceneCard,", content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState(source, { currentSelfCardEditor });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("self-cards-loaded", { selfCards });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("self-card-selection-changed", {', content)
        self.assertIn("selectedSelfCardId,", content)
        self.assertIn("currentSelfCard,", content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState(source, { chatSetup: buildChatSetupState() });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState(source, { composer: buildComposerUiState() });', content)
        self.assertIn('const isInsertMode = mode === "insert";', content)
        self.assertIn('selfCardId: isInsertMode ? selectedSelfCardId : "",', content)
        self.assertIn('currentSelfCard: isInsertMode ? currentSelfCard : null,', content)
        self.assertIn('if (mode !== "insert") {', content)
        self.assertIn("clearChatSetupSelfCardSelection();", content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("self-card-selection-cleared", {', content)

    def test_persona_review_vue_publishes_bridge_updates_after_load_save_and_autofill(self):
        content = read_js("persona-review-vue-island.js")
        self.assertIn("bridgeTools.syncLegacyUiState(source, overrides);", content)
        self.assertIn('syncPersonaBridgeState("persona-review-vue-loaded", {', content)
        self.assertIn('syncPersonaBridgeState("persona-review-vue-saved", {', content)
        self.assertIn('syncPersonaBridgeState("persona-review-vue-autofill", {', content)
        self.assertIn('syncPersonaBridgeState("persona-review-vue-autofill-cleared", {', content)

    def test_relation_details_vue_publishes_saved_payload_back_to_bridge(self):
        content = read_js("relation-details-vue-island.js")
        self.assertIn("bridgeTools.syncLegacyUiState(source, overrides);", content)
        self.assertIn('syncRelationBridgeState("relation-details-vue-saved", { currentRelationDetails: refreshed });', content)

    def test_character_overview_actions_use_shared_bridge_sync_helper(self):
        content = read_js("character-overview-actions.js")
        self.assertIn('bridgeTools.syncLegacyUiState(source, { currentCharacterOverview });', content)

    def test_workflow_and_model_settings_use_shared_bridge_sync_helper(self):
        content = read_js("workflow.js")
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("model-settings-view", { modelSettings });', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("workflow-update", { workflow: state });', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("model-settings-loaded", { modelSettings });', content)
        self.assertIn("const workflowState = typeof buildWorkflowVisibilityState === \"function\"", content)
        self.assertIn("window.__ZAOMENG_WORKFLOW_STATE__ = workflowState;", content)
        self.assertIn("workflow: workflowState,", content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("dialogue-reset", {', content)

    def test_core_uses_shared_bridge_sync_for_redistill_and_self_card_modal(self):
        content = read_js("core.js")
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("redistill-file-view-updated", {', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("redistill-pill-state-updated", {', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("redistill-segment-selected", {', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("redistill-recommendation-rendered", {', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("scene-card-modal-opened", { currentSceneCardEditor });', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("scene-card-modal-closed", { currentSceneCardEditor });', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("self-card-modal-opened", { currentSelfCardEditor });', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("self-card-modal-closed", { currentSelfCardEditor });', content)

    def test_chat_setup_vue_island_only_exposes_self_card_picker_in_insert_mode(self):
        content = read_js("chat-setup-vue-island.js")
        self.assertIn('const isInsertMode = computed(() => mode.value === "insert");', content)
        self.assertIn("if (!isInsertMode.value) return null;", content)
        self.assertIn('<template v-if=\"isInsertMode\">', content)
        self.assertIn("chat-setup-optional-section", content)
        self.assertIn("chat-setup-curation-stack", content)
        self.assertIn("openingPresetEntries", content)
        self.assertIn("sceneCardEntries", content)
        self.assertIn("selfCardEntries", content)

    def test_workflow_fragment_keeps_chat_setup_as_vue_surface_with_hidden_state_cache(self):
        content = read_fragment("workflow-strip.html")
        self.assertIn('<div id="chat-setup-vue-root" class="chat-setup-vue-root hidden" tabindex="-1"></div>', content)
        self.assertIn('<div id="chat-setup-state-cache" class="hidden" aria-hidden="true">', content)
        self.assertNotIn('<form id="dialogue-session-form" class="stack-form">', content)

    def test_workspace_styles_define_unified_chat_setup_curation_layout(self):
        content = (REPO_ROOT / "src" / "web" / "static" / "styles" / "workspace.css").read_text(encoding="utf-8")
        self.assertIn(".chat-setup-optional-section {", content)
        self.assertIn(".chat-setup-curation-stack {", content)
        self.assertIn(".chat-setup-curation-card {", content)
        self.assertIn(".chat-setup-option-card.active {", content)

    def test_editor_schema_exposes_embodiment_fields_in_persona_core(self):
        content = read_js("editor-schemas.js")
        self.assertIn('{ field: "gender", label: "性别"', content)
        self.assertIn('{ field: "age_stage", label: "年龄阶段"', content)
        self.assertIn('{ field: "appearance_feature", label: "外貌辨识"', content)
        self.assertIn('{ field: "habit_action", label: "习惯动作"', content)
        self.assertIn('{ field: "preference_like", label: "偏好喜好"', content)
        self.assertIn('{ field: "dislike_hate", label: "明显厌恶"', content)
        self.assertIn('hint: "只写正文能稳定判断的性别或呈现。"', content)
        self.assertIn('hint: "优先写年龄感和阶段，不强求具体岁数。"', content)
        self.assertIn('hint: "写客观身份和社会定位，不写剧情职能。"', content)
        self.assertIn('hint: "写他主观上怎么定义自己、怎么站位。"', content)

    def test_editor_schema_exposes_self_card_entry_hints(self):
        content = read_js("editor-schemas.js")
        self.assertIn('hint: "别人会怎么称呼你，尽量简短好叫。"', content)
        self.assertIn('hint: "写你在这场故事里以什么身份走进来。"', content)

    def test_editor_schema_exposes_overlap_hints_for_redundant_persona_fields(self):
        content = read_js("editor-schemas.js")
        self.assertIn('hint: "写他在剧情里承担什么职能，不是身份头衔。"', content)
        self.assertIn('hint: "只写拉扯和矛盾，不写自评和隐藏面。"', content)
        self.assertIn('hint: "只写他怎么看自己，可与他人观感形成反差。"', content)
        self.assertIn('hint: "写不对外展示的一面，不要重复内在冲突。"', content)

    def test_core_exposes_shared_bridge_sync_helper(self):
        content = read_js("core.js")
        self.assertIn("function syncLegacyUiState(source = \"legacy\", overrides = {}) {", content)
        self.assertIn("modelSettings = nextState.modelSettings || { configured: false, provider: \"\", model: \"\", base_url: \"\", max_tokens: 0, api_key_configured: false };", content)
        self.assertIn("currentPersonaReview = nextState.currentPersonaReview || null;", content)
        self.assertIn("currentRelationDetails = nextState.currentRelationDetails || null;", content)
        self.assertIn("currentDialogueSession = nextState.currentDialogueSession || null;", content)
        self.assertIn("window.__ZAOMENG_WORKFLOW_STATE__ = nextState.workflow || {};", content)
        self.assertIn("syncLegacyUiState,", content)


if __name__ == "__main__":
    unittest.main()
