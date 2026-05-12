(() => {
  const version = "20260512093001";
  window.__ZAOMENG_WEB_UI_VERSION__ = version;
  const rootFragments = [
    { id: "header-root", url: `/web/fragments/header.html?v=${version}` },
    { id: "workspace-root", url: `/web/fragments/workspace-shell.html?v=${version}` },
    { id: "modal-root", url: `/web/fragments/settings-modal.html?v=${version}` },
  ];
  const nestedFragments = [
    { id: "library-rail-root", url: `/web/fragments/library-rail.html?v=${version}` },
    { id: "workflow-strip-root", url: `/web/fragments/workflow-strip.html?v=${version}` },
    { id: "main-shell-root", url: `/web/fragments/main-shell.html?v=${version}` },
  ];
  const bridgeHosts = [
    ["workspace", "workspace-root", { kind: "root" }],
    ["workflow-strip", "workflow-strip-root", { kind: "fragment" }],
    ["bookshelf-vue-root", "bookshelf-vue-root", { kind: "vue-island", trial: "bookshelf" }],
    ["work-top-vue-root", "work-top-vue-root", { kind: "vue-island", trial: "work-top" }],
    ["work-character-vue-root", "work-character-vue-root", { kind: "vue-island", trial: "work-character" }],
    ["work-summary-vue-root", "work-summary-vue-root", { kind: "vue-island", trial: "work-summary" }],
    ["work-priority-vue-root", "work-priority-vue-root", { kind: "vue-island", trial: "work-priority" }],
    ["work-entry-vue-root", "work-entry-vue-root", { kind: "vue-island", trial: "work-entry" }],
    ["source-history-vue-root", "source-history-vue-root", { kind: "vue-island", trial: "source-history" }],
    ["redistill-vue-root", "redistill-vue-root", { kind: "vue-island", trial: "redistill" }],
    ["run-timeline-vue-root", "run-timeline-vue-root", { kind: "vue-island", trial: "run-timeline" }],
    ["main-shell", "main-shell-root", { kind: "fragment" }],
    ["character-overview-vue-root", "character-overview-vue-root", { kind: "vue-island", trial: "character-overview" }],
    ["chat-setup-vue-root", "chat-setup-vue-root", { kind: "vue-island", trial: "chat-setup" }],
    ["composer-vue-root", "composer-vue-root", { kind: "vue-island", trial: "composer" }],
    ["persona-review-vue-root", "persona-review-vue-root", { kind: "vue-island", trial: "persona-review" }],
    ["relation-details-vue-root", "relation-details-vue-root", { kind: "vue-island", trial: "relation-details" }],
    ["self-card-vue-root", "self-card-vue-root", { kind: "vue-island", trial: "self-card" }],
    ["model-settings-vue-root", "model-settings-vue-root", { kind: "vue-island", trial: "model-settings" }],
    ["modal-root", "modal-root", { kind: "root" }],
  ];
  const scripts = [
    `/web/vendor/vue.global.prod.js?v=${version}`,
    `/web/js/legacy-bridge.js?v=${version}`,
    `/web/js/core.js?v=${version}`,
    `/web/js/bookshelf-state.js?v=${version}`,
    `/web/js/work-overview-state.js?v=${version}`,
    `/web/js/character-overview-state.js?v=${version}`,
    `/web/js/run-detail-support-state.js?v=${version}`,
    `/web/js/editor-schemas.js?v=${version}`,
    `/web/js/editor-vue-components.js?v=${version}`,
    `/web/js/bookshelf.js?v=${version}`,
    `/web/js/bookshelf-legacy-render.js?v=${version}`,
    `/web/js/bookshelf-vue-island.js?v=${version}`,
    `/web/js/workflow.js?v=${version}`,
    `/web/js/run-detail.js?v=${version}`,
    `/web/js/persona-review-legacy.js?v=${version}`,
    `/web/js/relation-details-legacy.js?v=${version}`,
    `/web/js/dialogue.js?v=${version}`,
    `/web/js/main.js?v=${version}`,
    `/web/js/webui-api.js?v=${version}`,
    `/web/js/work-overview-vue-shared.js?v=${version}`,
    `/web/js/work-overview-actions.js?v=${version}`,
    `/web/js/work-overview-legacy-render.js?v=${version}`,
    `/web/js/character-overview-legacy-render.js?v=${version}`,
    `/web/js/run-detail-support-legacy-render.js?v=${version}`,
    `/web/js/character-overview-actions.js?v=${version}`,
    `/web/js/character-overview-vue-island.js?v=${version}`,
    `/web/js/work-top-vue-island.js?v=${version}`,
    `/web/js/work-character-vue-island.js?v=${version}`,
    `/web/js/redistill-vue-island.js?v=${version}`,
    `/web/js/persona-review-vue-island.js?v=${version}`,
    `/web/js/composer-vue-island.js?v=${version}`,
    `/web/js/relation-details-vue-island.js?v=${version}`,
    `/web/js/self-card-vue-island.js?v=${version}`,
    `/web/js/model-settings-vue-island.js?v=${version}`,
    `/web/js/chat-setup-vue-island.js?v=${version}`,
    `/web/js/work-summary-vue-island.js?v=${version}`,
    `/web/js/work-priority-vue-island.js?v=${version}`,
    `/web/js/work-entry-vue-island.js?v=${version}`,
    `/web/js/source-history-vue-island.js?v=${version}`,
    `/web/js/run-timeline-vue-island.js?v=${version}`,
  ];

  async function loadFragmentBatch(fragments) {
    await Promise.all(
      fragments.map(async ({ id, url }) => {
        const host = document.getElementById(id);
        if (!host) return;
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Failed to load fragment: ${url}`);
        }
        host.innerHTML = await response.text();
      })
    );
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
      document.body.appendChild(script);
    });
  }

  async function boot() {
    await loadFragmentBatch(rootFragments);
    await loadFragmentBatch(nestedFragments);
    for (const src of scripts) {
      await loadScript(src);
      if (src.includes("/web/js/legacy-bridge.js")) {
        const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
        if (bridge && typeof bridge.registerHost === "function") {
          bridgeHosts.forEach(([name, elementId, meta]) => {
            bridge.registerHost(name, elementId, meta);
          });
        }
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      boot().catch((error) => console.error(error));
    }, { once: true });
  } else {
    boot().catch((error) => console.error(error));
  }
})();
