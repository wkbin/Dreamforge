from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
JS_ROOT = REPO_ROOT / "src" / "web" / "static" / "js"


def read_js(name: str) -> str:
    return (JS_ROOT / name).read_text(encoding="utf-8")


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

    def test_main_publishes_optimistic_dialogue_and_suggest_retry_state(self):
        content = read_js("main.js")
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-optimistic", {', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("dialogue-session-restore", {', content)
        self.assertIn('publishComposerUiState("composer-suggest-retrying");', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("relation-details-loading", { currentRelationDetails: null });', content)

    def test_main_uses_shared_bridge_sync_for_self_card_state(self):
        content = read_js("main.js")
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState(source, { currentSelfCardEditor });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("self-cards-loaded", { selfCards });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState("self-card-selection-changed", {', content)
        self.assertIn("selectedSelfCardId,", content)
        self.assertIn("currentSelfCard,", content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState(source, { chatSetup: buildChatSetupState() });', content)
        self.assertIn('UI_BRIDGE_TOOLS.syncLegacyUiState(source, { composer: buildComposerUiState() });', content)

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
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("self-card-modal-opened", { currentSelfCardEditor });', content)
        self.assertIn('window.__ZAOMENG_UI_BRIDGE_TOOLS__.syncLegacyUiState("self-card-modal-closed", { currentSelfCardEditor });', content)

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
