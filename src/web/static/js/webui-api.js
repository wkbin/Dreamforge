(() => {
  function requireApiJson() {
    if (typeof apiJson !== "function") {
      throw new Error("apiJson is not ready.");
    }
    return apiJson;
  }

  async function getPersonaReview(runId, character) {
    return requireApiJson()(`/api/web/runs/${runId}/personas/${encodeURIComponent(character)}`);
  }

  async function saveModelSettings(payload) {
    return requireApiJson()(
      "/api/web/settings/model",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      },
      "保存失败。"
    );
  }

  async function savePersonaReview(runId, character, fields) {
    return requireApiJson()(
      `/api/web/runs/${runId}/personas/${encodeURIComponent(character)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields || {}),
      },
      "保存人物校对失败。"
    );
  }

  async function suggestPersonaField(runId, character, field) {
    return requireApiJson()(
      `/api/web/runs/${runId}/personas/${encodeURIComponent(character)}/suggest-field`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field }),
      },
      "人物信息补全失败。"
    );
  }

  async function restartRedistill(runId, payload) {
    return requireApiJson()(
      `/api/web/runs/${runId}/redistill`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      },
      "继续蒸馏失败。"
    );
  }

  async function recommendRedistillSegments(runId, character, maxSegments = 3) {
    return requireApiJson()(
      `/api/web/runs/${runId}/redistill/recommend`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character, max_segments: maxSegments }),
      },
      "推荐片段失败。"
    );
  }

  async function getRun(runId) {
    return requireApiJson()(`/api/web/runs/${runId}`);
  }

  async function deleteRun(runId) {
    return requireApiJson()(
      `/api/web/runs/${runId}`,
      { method: "DELETE" },
      "删除失败。"
    );
  }

  async function getRelationDetails(runId) {
    return requireApiJson()(`/api/web/runs/${runId}/relations`, {}, "关系明细暂时没有载入。");
  }

  async function saveRelationDetail(runId, pairKey, fields) {
    return requireApiJson()(
      `/api/web/runs/${runId}/relations/${encodeURIComponent(pairKey)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields || {}),
      },
      "关系保存失败。"
    );
  }

  async function listSelfCards() {
    return requireApiJson()("/api/web/self-cards", {}, "角色卡列表载入失败。");
  }

  async function getSelfCard(cardId) {
    return requireApiJson()(`/api/web/self-cards/${encodeURIComponent(cardId)}`, {}, "角色卡载入失败。");
  }

  async function generateSelfCard() {
    return requireApiJson()("/api/web/self-cards/generate", { method: "POST" }, "角色卡生成失败。");
  }

  async function saveSelfCard(cardId, fields) {
    return requireApiJson()(
      cardId ? `/api/web/self-cards/${encodeURIComponent(cardId)}` : "/api/web/self-cards",
      {
        method: cardId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields || {}),
      },
      "角色卡保存失败。"
    );
  }

  async function deleteSelfCard(cardId) {
    return requireApiJson()(
      `/api/web/self-cards/${encodeURIComponent(cardId)}`,
      { method: "DELETE" },
      "角色卡删除失败。"
    );
  }

  window.__ZAOMENG_WEBUI_API__ = {
    saveModelSettings,
    getPersonaReview,
    savePersonaReview,
    suggestPersonaField,
    restartRedistill,
    recommendRedistillSegments,
    getRun,
    deleteRun,
    getRelationDetails,
    saveRelationDetail,
    listSelfCards,
    getSelfCard,
    generateSelfCard,
    saveSelfCard,
    deleteSelfCard,
  };
})();
