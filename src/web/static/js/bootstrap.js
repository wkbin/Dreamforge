(() => {
  const version = "20260516154853";
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
    ["scene-card-vue-root", "scene-card-vue-root", { kind: "vue-island", trial: "scene-card" }],
    ["self-card-vue-root", "self-card-vue-root", { kind: "vue-island", trial: "self-card" }],
    ["model-settings-vue-root", "model-settings-vue-root", { kind: "vue-island", trial: "model-settings" }],
    ["modal-root", "modal-root", { kind: "root" }],
  ];
  const coreScripts = [
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
    `/web/js/workflow.js?v=${version}`,
    `/web/js/run-detail.js?v=${version}`,
    `/web/js/persona-review-legacy.js?v=${version}`,
    `/web/js/relation-details-legacy.js?v=${version}`,
    `/web/js/dialogue.js?v=${version}`,
    `/web/js/webui-api.js?v=${version}`,
    `/web/js/main.js?v=${version}`,
  ];
  const optionalScripts = [
    `/web/js/bookshelf-vue-island.js?v=${version}`,
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
    `/web/js/scene-card-vue-island.js?v=${version}`,
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

  function renderBootFailure(error) {
    const detail = error instanceof Error ? error.message : String(error || "未知错误");
    const host = document.getElementById("workspace-root") || document.body;
    if (!host) {
      return;
    }
    host.innerHTML = `
      <section class="app-shell">
        <div class="panel-card" style="max-width: 760px; margin: 48px auto; padding: 28px;">
          <p class="eyebrow">Web UI 初始化失败</p>
          <h2 style="margin-top: 0;">这一页暂时没有铺开</h2>
          <p class="card-copy">页面资源没有完整加载成功。你可以先刷新一次；如果问题仍然存在，再查看控制台里的报错详情。</p>
          <pre style="white-space: pre-wrap; word-break: break-word; margin: 16px 0 0; padding: 12px 14px; border-radius: 16px; background: rgba(15, 23, 42, 0.08); color: #334155;">${detail}</pre>
        </div>
      </section>
    `;
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

  async function loadScriptBatch(sources, { continueOnError = false } = {}) {
    for (const src of sources) {
      try {
        await loadScript(src);
        if (src.includes("/web/js/legacy-bridge.js")) {
          const bridge = window.__ZAOMENG_LEGACY_BRIDGE__;
          if (bridge && typeof bridge.registerHost === "function") {
            bridgeHosts.forEach(([name, elementId, meta]) => {
              bridge.registerHost(name, elementId, meta);
            });
          }
        }
      } catch (error) {
        if (!continueOnError) {
          throw error;
        }
        console.warn(error);
      }
    }
  }

  async function boot() {
    await loadFragmentBatch(rootFragments);
    await loadFragmentBatch(nestedFragments);
    await loadScriptBatch(coreScripts);
    await loadScriptBatch(optionalScripts, { continueOnError: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      boot().catch((error) => {
        console.error(error);
        renderBootFailure(error);
      });
    }, { once: true });
  } else {
    boot().catch((error) => {
      console.error(error);
      renderBootFailure(error);
    });
  }
})();
