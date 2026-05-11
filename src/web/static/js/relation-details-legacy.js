function renderRelationDetails(payload) {
  currentRelationDetails = payload;
  const root = el("relation-details-list");
  if (!root) return;
  root.innerHTML = "";
  const conflictMap = new Map(
    (payload?.conflicts || [])
      .filter((item) => item?.pair_key)
      .map((item) => [item.pair_key, item])
  );
  (payload?.items || []).forEach((item) => {
    const card = document.createElement("article");
    card.className = "relation-detail-card";
    const conflict = conflictMap.get(item.pair_key);
    const conflictLabel = conflict?.tags?.length ? ` · 冲突：${conflict.tags.join(", ")}` : "";
    card.innerHTML = `
      <div class="relation-detail-head">
        <strong>${joinCharacters(item.characters || []) || item.pair_key || "未命名关系"}</strong>
        <span class="relation-detail-type">${item.relationship_type || "牵连"}${conflictLabel}</span>
      </div>
      <div class="relation-detail-edit-grid">
        <label>信 <input type="number" data-field="trust" min="0" max="10" value="${Number(item.trust || 0)}" /></label>
        <label>情 <input type="number" data-field="affection" min="0" max="10" value="${Number(item.affection || 0)}" /></label>
        <label>冲 <input type="number" data-field="hostility" min="0" max="10" value="${Number(item.hostility || 0)}" /></label>
        <label>疑 <input type="number" data-field="ambiguity" min="0" max="10" value="${Number(item.ambiguity || 3)}" /></label>
      </div>
      <div class="relation-detail-copy relation-detail-edit-text">
        <label>关系类型<input type="text" data-field="relationship_type" value="${escapeHtml(item.relationship_type || "牵连")}" /></label>
        <label>互动摘要<textarea data-field="typical_interaction" rows="2">${escapeHtml(item.typical_interaction || "")}</textarea></label>
        <label>冲突点<textarea data-field="conflict_point" rows="2">${escapeHtml(item.conflict_point || "")}</textarea></label>
        <label>关系变化<textarea data-field="relation_change" rows="2">${escapeHtml(item.relation_change || "")}</textarea></label>
      </div>
      <div class="relation-detail-actions">
        <button type="button" class="soft-button" data-action="save-relation" data-pair-key="${escapeHtml(item.pair_key || "")}">保存</button>
      </div>
      <div class="relation-detail-evidence">
        <p>证据句</p>
        <ul>${(item.evidence_lines || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>
      </div>
    `;
    const saveButton = card.querySelector('[data-action="save-relation"]');
    if (saveButton instanceof HTMLButtonElement) {
      saveButton.addEventListener("click", async () => {
        if (!currentRunId) return;
        const pairKey = saveButton.dataset.pairKey || "";
        if (!pairKey) return;
        const body = {};
        card.querySelectorAll("[data-field]").forEach((node) => {
          if (!(node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement)) return;
          const field = node.dataset.field || "";
          if (!field) return;
          body[field] = node.value;
        });
        saveButton.disabled = true;
        setStatus("relation-details-status", "正在保存关系修改...");
        try {
          const refreshed = await apiJson(
            `/api/web/runs/${currentRunId}/relations/${encodeURIComponent(pairKey)}`,
            {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            },
            "关系保存失败。"
          );
          renderRelationDetails(refreshed);
          setStatus("relation-details-status", "关系已保存。");
        } catch (error) {
          saveButton.disabled = false;
          setStatus("relation-details-status", error.message || "关系保存失败。");
        }
      });
    }
    root.appendChild(card);
  });
  setStatus("relation-details-status", payload?.items?.length ? "" : "这张关系网暂时还没有明细。");
  if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("relation-details-rendered", { currentRelationDetails: payload });
  }
}
