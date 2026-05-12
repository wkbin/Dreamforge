(() => {
  function renderChangeTimeline(payload) {
    const root = el("character-overview-change-timeline");
    if (!root) return;
    root.innerHTML = "";
    const items = buildCharacterOverviewChangeTimelineItems(payload?.character || "");
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "character-overview-change-item";
      card.innerHTML = `
        <div class="character-overview-change-item-head">
          <strong>${item.title}</strong>
          <small>${item.updated}</small>
        </div>
        <p>${item.copy}</p>
        <span>${item.badge}</span>
      `;
      root.appendChild(card);
    });
    root.classList.toggle("hidden", root.childElementCount === 0);
    toggle("character-overview-change-timeline-empty", root.childElementCount === 0);
  }

  function renderHealthMetrics(snapshot) {
    const root = el("character-overview-health-metrics");
    if (!root) return;
    root.innerHTML = "";
    const metrics = [
      ["完整度", `${snapshot.completeness}%`, "按关键字段与细调字段的当前覆盖度估算"],
      ["稳住的关键字段", `${snapshot.stableKeyCount} / ${CHARACTER_OVERVIEW_KEY_FIELDS.length}`, "这些字段已经足够支撑角色概览与基础对话"],
      ["待补位置", `${snapshot.weakKeyCount} 处`, snapshot.weakKeyCount > 0 ? "优先补这些地方，人物会更像自己" : "关键骨架已经收住，可以转去细修"],
      ["细调覆盖", `${snapshot.advancedFilledCount} / ${snapshot.advancedTotalCount}`, "用于抠语气、情绪和更细的人设纹理"],
      ["最近更新", snapshot.updatedText, "显示这一卷最近一次落盘或校对的大致时间"],
    ];
    metrics.forEach(([label, value, hint]) => {
      const card = document.createElement("article");
      card.className = "character-overview-health-card";
      card.innerHTML = `<span>${label}</span><strong>${value}</strong><small>${hint}</small>`;
      root.appendChild(card);
    });
  }

  function renderEvidenceMetrics(snapshot) {
    const root = el("character-overview-evidence-metrics");
    if (!root) return;
    root.innerHTML = "";
    const items = [
      ["证据判断", snapshot.evidenceLabel, snapshot.evidenceCopy],
      ["当前依据书段", snapshot.sourceLabel, snapshot.sourceCopy],
      ["来源足迹", snapshot.traceLabel, snapshot.traceCopy],
      [snapshot.recommendationLabel, "下一步", snapshot.recommendationCopy],
    ];
    items.forEach(([label, value, hint]) => {
      const card = document.createElement("article");
      card.className = "character-overview-evidence-card";
      card.innerHTML = `<span>${label}</span><strong>${value}</strong><small>${hint}</small>`;
      root.appendChild(card);
    });
  }

  function renderTrustSignals(payload, healthSnapshot, evidenceSnapshot) {
    const root = el("character-overview-trust-signals");
    if (!root) return;
    root.innerHTML = "";
    buildCharacterOverviewTrustSignals(payload, healthSnapshot, evidenceSnapshot).forEach((item) => {
      const card = document.createElement("article");
      card.className = `character-overview-trust-card is-${item.tone || "neutral"}`;
      card.innerHTML = `
        <span>${escapeHtml(item.label)}</span>
        <strong>${escapeHtml(item.value)}</strong>
        <small>${escapeHtml(item.copy)}</small>
      `;
      root.appendChild(card);
    });
  }

  function syncFieldSaveButton(inputNode) {
    if (!(inputNode instanceof HTMLTextAreaElement)) return;
    const field = String(inputNode.getAttribute("data-character-overview-input") || "").trim();
    if (!field) return;
    const card = inputNode.closest(".character-overview-field-card");
    if (!(card instanceof HTMLElement)) return;
    const button = card.querySelector(`[data-character-overview-save="${field}"]`);
    if (!(button instanceof HTMLButtonElement)) return;
    const initialValue = String(inputNode.dataset.initialValue || "").trim();
    const currentValue = String(inputNode.value || "").trim();
    const dirty = currentValue !== initialValue;
    card.classList.toggle("is-dirty", dirty);
    if (button.dataset.saving !== "true") {
      button.disabled = !dirty;
      button.textContent = dirty ? "保存改动" : "已保存";
    }
  }

  function renderKeyFields(fields) {
    const root = el("character-overview-key-fields");
    if (!root) return;
    root.innerHTML = "";
    const evidenceSnapshot = buildCharacterOverviewEvidenceSnapshot(currentCharacterOverview?.character || "");
    CHARACTER_OVERVIEW_KEY_FIELDS.forEach(([field, label]) => {
      const value = String(fields[field] || "").trim();
      const weak = isCharacterOverviewFieldWeak(field, value);
      const tags = buildCharacterOverviewFieldTags(field, value, evidenceSnapshot);
      const card = document.createElement("article");
      card.className = `character-overview-field-card${weak ? " is-missing" : ""}`;
      const canAutofill = weak;
      card.innerHTML = `
        <div class="character-overview-field-head">
          <span>${label}</span>
          <div class="character-overview-field-actions">
            ${tags.map((tag) => `<span class="character-overview-field-tag is-${tag.tone}">${tag.label}</span>`).join("")}
            ${canAutofill ? `<button type="button" class="character-overview-mini-button" data-character-overview-field="${field}">AI补全</button>` : ""}
            <button type="button" class="character-overview-mini-button" data-character-overview-save="${field}" disabled>已保存</button>
          </div>
        </div>
        <textarea class="character-overview-field-input" data-character-overview-input="${field}" rows="4" placeholder="可以直接在这里修改，然后点保存改动。"></textarea>
        <small class="character-overview-field-hint">${buildCharacterOverviewFieldHint(field, value)}</small>
      `;
      const input = card.querySelector(`[data-character-overview-input="${field}"]`);
      if (input instanceof HTMLTextAreaElement) {
        input.value = value;
        input.dataset.initialValue = value;
        syncFieldSaveButton(input);
      }
      root.appendChild(card);
    });
  }

  function renderVoiceSummary(fields) {
    const root = el("character-overview-voice-summary");
    if (!root) return;
    root.innerHTML = "";
    const items = typeof CHARACTER_OVERVIEW_STATE.buildVoiceSummaryItems === "function"
      ? CHARACTER_OVERVIEW_STATE.buildVoiceSummaryItems(fields)
      : [];
    items.forEach(([label, value]) => {
      const card = document.createElement("article");
      card.className = "character-overview-summary-card";
      card.innerHTML = `<span>${label}</span><p>${value}</p>`;
      root.appendChild(card);
    });
  }

  function renderRelationSummary(fields) {
    const root = el("character-overview-relation-summary");
    if (!root) return;
    root.innerHTML = "";
    const items = typeof CHARACTER_OVERVIEW_STATE.buildRelationSummaryItems === "function"
      ? CHARACTER_OVERVIEW_STATE.buildRelationSummaryItems(fields)
      : [];
    items.forEach(([label, value]) => {
      const card = document.createElement("article");
      card.className = "character-overview-summary-card";
      card.innerHTML = `<span>${label}</span><p>${value}</p>`;
      root.appendChild(card);
    });
  }

  function renderAdvancedGroups(fields) {
    const root = el("character-overview-advanced-groups");
    if (!root) return;
    root.innerHTML = "";
    const groups = typeof CHARACTER_OVERVIEW_STATE.buildAdvancedGroupsView === "function"
      ? CHARACTER_OVERVIEW_STATE.buildAdvancedGroupsView(fields, characterOverviewExpandedGroups)
      : [];
    groups.forEach((group) => {
      const title = group.title;
      const fieldNames = Array.isArray(group.fieldNames) ? group.fieldNames : [];
      const values = Array.isArray(group.items) ? group.items : [];
      const expanded = Boolean(group.expanded);
      const previewText = String(group.previewText || "").trim();
      const card = document.createElement("article");
      card.className = "character-overview-advanced-group";
      card.innerHTML = `
        <button type="button" class="character-overview-advanced-toggle${expanded ? " is-open" : ""}" data-character-overview-group="${title}" aria-expanded="${expanded ? "true" : "false"}">
          <span class="character-overview-advanced-title">${title}</span>
          <span class="character-overview-advanced-meta">${values.length > 0 ? `已填 ${values.length} / ${fieldNames.length}` : "这一组还没铺开"}</span>
          <span class="character-overview-advanced-arrow">${expanded ? "收起" : "展开"}</span>
        </button>
        <p class="character-overview-advanced-preview${expanded ? " hidden" : ""}">${previewText || "这一组还可以继续补更多细节，不必一次写满。"}</p>
        <div class="character-overview-advanced-body${expanded ? "" : " hidden"}">
          ${
            values.length
              ? values.map((item) => `<article class="character-overview-advanced-field"><span>${item.label}</span><p>${item.value}</p></article>`).join("")
              : `<p class="character-overview-advanced-empty">这一组暂时还没写开，可以先稳住关键字段，再决定要不要继续细修。</p>`
          }
        </div>
      `;
      root.appendChild(card);
    });
  }

  window.__ZAOMENG_CHARACTER_OVERVIEW_LEGACY_RENDER__ = {
    renderAdvancedGroups,
    renderChangeTimeline,
    renderEvidenceMetrics,
    renderHealthMetrics,
    renderKeyFields,
    renderRelationSummary,
    renderTrustSignals,
    renderVoiceSummary,
    syncFieldSaveButton,
  };
})();
