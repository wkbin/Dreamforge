(() => {
  function cloneValue(value) {
    if (value == null) return value ?? null;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return value;
    }
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (error) {
      console.warn("legacy bridge clone failed", error);
      return null;
    }
  }

  const subscribers = new Set();
  const hosts = new Map();
  let snapshot = {
    updatedAt: "",
    source: "boot",
    uiVersion: String(window.__ZAOMENG_WEB_UI_VERSION__ || "").trim(),
    currentRunId: "",
    currentRun: null,
    currentDialogueSessionId: "",
    currentDialogueSession: null,
    modelSettings: null,
    sceneCards: [],
    currentSceneCard: null,
    selectedSceneCardId: "",
    selfCards: [],
    currentSelfCard: null,
    selectedSelfCardId: "",
    redistillSuggestionState: null,
    workflow: {},
    hosts: [],
  };

  function emit(detail) {
    window.dispatchEvent(
      new CustomEvent("zaomeng:legacy-state-change", {
        detail,
      })
    );
    subscribers.forEach((listener) => {
      try {
        listener(detail);
      } catch (error) {
        console.error("legacy bridge subscriber failed", error);
      }
    });
  }

  function getSnapshot() {
    return cloneValue(snapshot) || {};
  }

  function syncHosts() {
    snapshot.hosts = [...hosts.values()].map((item) => cloneValue(item));
  }

  function publish(partial = {}, source = "legacy") {
    snapshot = {
      ...snapshot,
      ...cloneValue(partial),
      source: String(source || "legacy"),
      updatedAt: new Date().toISOString(),
      uiVersion: String(window.__ZAOMENG_WEB_UI_VERSION__ || snapshot.uiVersion || "").trim(),
    };
    syncHosts();
    emit(getSnapshot());
  }

  function subscribe(listener) {
    if (typeof listener !== "function") {
      return () => {};
    }
    subscribers.add(listener);
    return () => subscribers.delete(listener);
  }

  function registerHost(name, elementId, meta = {}) {
    const key = String(name || elementId || "").trim();
    if (!key) return;
    hosts.set(key, {
      name: key,
      elementId: String(elementId || "").trim(),
      meta: cloneValue(meta) || {},
    });
    publish({}, "register-host");
  }

  window.__ZAOMENG_LEGACY_BRIDGE__ = {
    getSnapshot,
    publish,
    subscribe,
    registerHost,
  };
})();
