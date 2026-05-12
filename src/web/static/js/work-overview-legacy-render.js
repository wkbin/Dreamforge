(() => {
  const bridgeTools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};

  function readActions() {
    if (typeof bridgeTools.readLegacyActionBridge === "function") {
      return bridgeTools.readLegacyActionBridge("__ZAOMENG_RUN_OVERVIEW_ACTIONS__");
    }
    return window.__ZAOMENG_RUN_OVERVIEW_ACTIONS__ || {};
  }

  function buildCharacterState(run) {
    if (typeof window.__ZAOMENG_BUILD_WORK_CHARACTER_STATE__ === "function") {
      return window.__ZAOMENG_BUILD_WORK_CHARACTER_STATE__(run);
    }
    return { items: [], canExpand: false, toggleLabel: "展开全部" };
  }

  function buildPriorityState(run) {
    if (typeof window.__ZAOMENG_BUILD_WORK_PRIORITY_STATE__ === "function") {
      return window.__ZAOMENG_BUILD_WORK_PRIORITY_STATE__(run);
    }
    return { items: [] };
  }

  function buildGraphState(run) {
    const builder = window.__ZAOMENG_WORK_OVERVIEW_STATE__?.buildWorkGraphSummaryState;
    return typeof builder === "function"
      ? builder(run)
      : { badgeText: "未开始", badgeTone: "warning", copy: "先看关系与会话，再决定如何走进这一幕。" };
  }

  function buildSessionState(run) {
    const builder = window.__ZAOMENG_WORK_OVERVIEW_STATE__?.buildWorkSessionPreviewState;
    return typeof builder === "function"
      ? builder(run)
      : { latest: null, items: [], canExpand: false, toggleLabel: "展开全部" };
  }

  function setGraphStatusBadge(text, tone = "warning") {
    const badge = el("run-graph-status-badge");
    if (!badge) return;
    badge.textContent = text || "未开始";
    badge.className = `work-character-status is-${tone}`;
  }

  function renderCharacterReadiness(run) {
    const root = el("run-character-readiness");
    const toggleButton = el("run-character-readiness-toggle");
    if (!root) return;
    root.innerHTML = "";
    const state = buildCharacterState(run);
    const actions = readActions();
    state.items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "work-character-card";
      button.innerHTML = `
        <div class="work-character-head">
          <div class="work-character-title">
            <strong>${item.name}</strong>
            <small>${item.preview.core_identity || item.preview.story_role || "人物包已经落地，可继续补细节"}</small>
          </div>
          <span class="work-character-status is-${item.statusTone}">${item.statusText}</span>
        </div>
        <p class="work-character-copy">${item.preview.speech_style || item.preview.soul_goal || "说话方式或灵魂目标还可以继续补得更稳。"}</p>
        <div class="work-character-meta">
          <span>${item.weakCount > 0 ? `待补关键字段 ${item.weakCount}` : "关键字段已齐"}</span>
          <span>${item.updatedText ? `最近更新 ${item.updatedText}` : "刚刚落成"}</span>
        </div>
      `;
      button.addEventListener("click", () => {
        if (typeof actions.openCharacterReadiness === "function") {
          actions.openCharacterReadiness(item.name);
        }
      });
      root.appendChild(button);
    });
    if (toggleButton) {
      toggleButton.classList.toggle("hidden", !state.canExpand);
      toggleButton.textContent = state.toggleLabel;
    }
    root.classList.toggle("hidden", root.childElementCount === 0);
    toggle("run-character-readiness-empty", root.childElementCount === 0);
  }

  function renderWorkPriorityReview(run) {
    const root = el("work-priority-review-list");
    if (!root) return;
    root.innerHTML = "";
    const state = buildPriorityState(run);
    const actions = readActions();
    state.items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "work-priority-card";
      card.innerHTML = `
        <div class="work-priority-card-head">
          <span class="work-priority-rank">优先 ${item.order}</span>
          <span class="work-character-status is-${item.statusTone}">${item.statusText}</span>
        </div>
        <div class="work-priority-title">
          <strong>${item.name}</strong>
          <small>${item.preview.core_identity || item.preview.story_role || "人物轮廓还在慢慢站稳"}</small>
        </div>
        <p class="work-priority-headline">${item.headline}</p>
        <p class="work-priority-copy">${item.reason}</p>
        <div class="work-priority-meta">
          <span>${item.weakCount > 0 ? `待补关键字段 ${item.weakCount}` : "关键字段已齐"}</span>
          <span>${item.updatedText ? `最近更新 ${item.updatedText}` : "刚刚落成"}</span>
        </div>
        <p class="work-priority-hint">${item.actionHint}</p>
        <div class="work-priority-actions">
          <button type="button" class="soft-button" data-work-priority-open="${item.name}">打开角色页</button>
          <button type="button" class="soft-button" data-work-priority-redistill="${item.name}">增量蒸馏</button>
        </div>
      `;
      root.appendChild(card);
    });
    root.classList.toggle("hidden", root.childElementCount === 0);
    toggle("work-priority-review-empty", root.childElementCount === 0);
    root.querySelectorAll("[data-work-priority-open]").forEach((button) => {
      button.addEventListener("click", () => {
        if (typeof actions.openPriorityCharacter === "function") {
          actions.openPriorityCharacter(button.getAttribute("data-work-priority-open") || "");
        }
      });
    });
    root.querySelectorAll("[data-work-priority-redistill]").forEach((button) => {
      button.addEventListener("click", () => {
        if (typeof actions.redistillPriorityCharacter === "function") {
          actions.redistillPriorityCharacter(button.getAttribute("data-work-priority-redistill") || "");
        }
      });
    });
  }

  function renderWorkGraphSummary(run) {
    const state = buildGraphState(run);
    setGraphStatusBadge(state.badgeText, state.badgeTone);
    setText("run-graph-status-copy", state.copy, "");
  }

  function renderQualityPills(rootId, values, emptyId) {
    const root = el(rootId);
    if (!root) return;
    root.innerHTML = "";
    (values || []).forEach((value) => {
      const pill = document.createElement("span");
      pill.textContent = value;
      root.appendChild(pill);
    });
    root.classList.toggle("hidden", root.childElementCount === 0);
    toggle(emptyId, root.childElementCount === 0);
  }

  function renderQualitySnapshot(run) {
    const builder = window.__ZAOMENG_WORK_OVERVIEW_STATE__?.buildQualitySnapshotState;
    const snapshot = typeof builder === "function"
      ? builder(run)
      : { matched: [], missing: [], stages: [], repairsText: "", chunksText: "", visible: false, emptyCopyVisible: true, open: false };
    renderQualityPills("quality-matched", snapshot.matched, "quality-matched-empty");
    renderQualityPills("quality-missing", snapshot.missing, "quality-missing-empty");
    renderQualityPills("quality-stages", snapshot.stages, "quality-stages-empty");
    setText("quality-repairs", snapshot.repairsText, "");
    setText("quality-chunks", snapshot.chunksText, "");
    toggle("quality-section", snapshot.visible);
    toggle("quality-empty-copy", snapshot.emptyCopyVisible);
    const qualitySection = el("quality-section");
    if (qualitySection instanceof HTMLDetailsElement) {
      qualitySection.open = Boolean(snapshot.open);
    }
  }

  function renderWorkSessionPreview(run) {
    const root = el("work-session-preview");
    const toggleButton = el("work-session-preview-toggle");
    const resumeShell = el("work-session-resume-shell");
    const resumeButton = el("work-session-resume-latest-button");
    if (!root) return;
    root.innerHTML = "";
    const state = buildSessionState(run);
    const actions = readActions();
    if (resumeShell && resumeButton) {
      const latest = state.latest;
      resumeShell.classList.toggle("hidden", !latest);
      if (latest) {
        resumeButton.textContent = latest.label;
        resumeButton.onclick = () => {
          if (typeof actions.openEntrySession === "function") {
            actions.openEntrySession(latest.raw);
          }
        };
      } else {
        resumeButton.onclick = null;
        resumeButton.textContent = "继续最近一局";
      }
    }
    state.items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `work-session-card${item.hasMatch ? " has-match" : ""}`;
      button.innerHTML = `
        <div class="work-session-head">
          <div class="work-session-title">
            <strong>${escapeHtml(item.label)}</strong>
            <small>${escapeHtml(item.modeLabel)} · ${item.participantCount || 0} 人</small>
          </div>
        </div>
        ${item.matchText ? `<span class="work-session-match">${escapeHtml(item.matchText)}</span>` : ""}
        ${item.snippet ? `<p class="work-session-copy">${escapeHtml(item.snippet)}</p>` : ""}
        <div class="work-session-meta">
          <span>${escapeHtml(item.updatedText)}</span>
          <span>${escapeHtml(item.statusText)}</span>
        </div>
      `;
      button.addEventListener("click", () => {
        if (typeof actions.openEntrySession === "function") {
          actions.openEntrySession(item.raw);
        }
      });
      root.appendChild(button);
    });
    if (toggleButton) {
      toggleButton.classList.toggle("hidden", !state.canExpand);
      toggleButton.textContent = state.toggleLabel;
    }
    root.classList.toggle("hidden", root.childElementCount === 0);
    toggle("work-session-preview-empty", root.childElementCount === 0);
  }

  window.__ZAOMENG_WORK_OVERVIEW_LEGACY_RENDER__ = {
    renderCharacterReadiness,
    renderQualitySnapshot,
    renderWorkGraphSummary,
    renderWorkPriorityReview,
    renderWorkSessionPreview,
  };
})();
