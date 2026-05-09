(() => {
  const version = "20260509183613";
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
  const scripts = [
    `/web/js/core.js?v=${version}`,
    `/web/js/bookshelf.js?v=${version}`,
    `/web/js/workflow.js?v=${version}`,
    `/web/js/run-detail.js?v=${version}`,
    `/web/js/dialogue.js?v=${version}`,
    `/web/js/main.js?v=${version}`,
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
