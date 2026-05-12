(() => {
  const bridgeTools = window.__ZAOMENG_UI_BRIDGE_TOOLS__ || {};

  function runDetailActions() {
    if (typeof bridgeTools.readLegacyActionBridge === "function") {
      return bridgeTools.readLegacyActionBridge("__ZAOMENG_RUN_DETAIL_ACTIONS__");
    }
    return window.__ZAOMENG_RUN_DETAIL_ACTIONS__ || {};
  }

  function historyKey(character) {
    return `${currentRunId || ""}::${String(character || "").trim()}`;
  }

  function getAutofillItems(character) {
    const items = characterOverviewAutofillHistory.get(historyKey(character)) || [];
    const eventItems = getCurrentRunEvents()
      .filter((item) => {
        const eventCharacter = String(item?.character || "").trim();
        const eventStage = String(item?.stage || "").trim();
        const reviewSource = String(item?.review_source || "").trim();
        return eventCharacter === String(character || "").trim() && eventStage === "persona_review_saved" && reviewSource === "character_overview_autofill";
      })
      .slice()
      .reverse()
      .map((item) => {
        const changedFields = Array.isArray(item?.changed_fields) ? item.changed_fields : [];
        const firstField = String(changedFields[0] || "").trim();
        const reviewNote = String(item?.review_note || "").trim();
        return {
          field: firstField,
          label: CHARACTER_OVERVIEW_FIELD_LABELS[firstField] || reviewNote || firstField || "最近补全",
          value: "",
          message: String(item?.message || "").trim(),
          sourceMode: reviewNote,
          timestamp: String(item?.timestamp || "").trim(),
        };
      });
    const merged = [];
    const seen = new Set();
    [...items, ...eventItems].forEach((item) => {
      const key = `${String(item?.field || "").trim()}::${String(item?.timestamp || "").trim()}::${String(item?.sourceMode || "").trim()}`;
      if (seen.has(key)) return;
      seen.add(key);
      merged.push(item);
    });
    return merged
      .sort((left, right) => String(right?.timestamp || "").localeCompare(String(left?.timestamp || "")))
      .slice(0, 6);
  }

  function rememberAutofill(character, payload) {
    const field = String(payload?.field || "").trim();
    if (!character || !field) return;
    const key = historyKey(character);
    const items = getAutofillItems(character).filter((item) => item.field !== field);
    items.unshift({
      field,
      label: CHARACTER_OVERVIEW_FIELD_LABELS[field] || String(payload?.label || field).trim() || field,
      value: String(payload?.value || "").trim(),
      message: String(payload?.message || "").trim(),
      sourceMode: String(payload?.source_mode || "").trim(),
      timestamp: new Date().toISOString(),
    });
    characterOverviewAutofillHistory.set(key, items.slice(0, 6));
  }

  function getExpandedGroups() {
    return [...characterOverviewExpandedGroups];
  }

  function buildSavePayload(nextFields, reviewSource = "", reviewNote = "") {
    const payload = {};
    (PERSONA_REVIEW_FIELD_BINDINGS || []).forEach(([field]) => {
      payload[field] = String(nextFields?.[field] || "").trim();
    });
    payload.review_source = reviewSource;
    payload.review_note = reviewNote;
    return payload;
  }

  function publishCharacterOverviewState(source = "character-overview") {
    if (typeof publishLegacyUiState === "function") {
      publishLegacyUiState(source, { currentCharacterOverview });
    }
  }

  async function refreshRunAfterCharacterOverviewUpdate() {
    if (!currentRunId) return currentRun;
    const actions = runDetailActions();
    if (typeof actions.refreshRunView === "function") {
      return actions.refreshRunView(currentRunId);
    }
    const run = await apiJson(`/api/web/runs/${currentRunId}`);
    if (typeof window.__ZAOMENG_APPLY_RUN_VIEW__ === "function") {
      window.__ZAOMENG_APPLY_RUN_VIEW__(run);
      return run;
    }
    if (typeof actions.renderRunView === "function") {
      actions.renderRunView(run);
    } else if (typeof window.renderRun === "function") {
      window.renderRun(run);
    }
    return run;
  }

  async function applyCharacterOverviewPayload(payload, source = "character-overview-updated", options = {}) {
    currentCharacterOverview = payload;
    characterOverviewOpen = true;
    renderCharacterOverview(payload);
    if (!options.skipRunRefresh) {
      await refreshRunAfterCharacterOverviewUpdate();
    }
    updateWorkflowState();
    publishCharacterOverviewState(source);
    return payload;
  }

  function setButtonPendingState(button, pendingText) {
    if (!(button instanceof HTMLButtonElement)) {
      return () => {};
    }
    const previousText = button.textContent || "";
    const previousDisabled = button.disabled;
    button.disabled = true;
    button.textContent = pendingText;
    return () => {
      button.disabled = previousDisabled;
      button.textContent = previousText;
    };
  }

  async function openCharacterOverview(characterName) {
    if (!currentRunId || !currentRun || !characterName) return null;
    const payload = await apiJson(`/api/web/runs/${currentRunId}/personas/${encodeURIComponent(characterName)}`);
    characterOverviewExpandedGroups.clear();
    return applyCharacterOverviewPayload(payload, "character-overview-opened", { skipRunRefresh: true });
  }

  function closeOverview() {
    characterOverviewOpen = false;
    updateWorkflowState();
    publishCharacterOverviewState("character-overview-closed");
  }

  async function openReview() {
    const character = String(currentCharacterOverview?.character || "").trim();
    if (!character || typeof openPersonaReviewForCharacter !== "function") {
      return false;
    }
    await openPersonaReviewForCharacter(character);
    return true;
  }

  function handleFieldInput(event) {
    const target = event.target;
    if (!(target instanceof HTMLTextAreaElement)) return;
    if (!target.hasAttribute("data-character-overview-input")) return;
    syncCharacterOverviewFieldSaveButton(target);
  }

  function toggleAdvancedGroup(groupName) {
    const name = String(groupName || "").trim();
    if (!name || !currentCharacterOverview?.fields) return false;
    if (characterOverviewExpandedGroups.has(name)) {
      characterOverviewExpandedGroups.delete(name);
    } else {
      characterOverviewExpandedGroups.add(name);
    }
    renderCharacterOverviewAdvancedGroups(currentCharacterOverview.fields || {});
    publishCharacterOverviewState("character-overview-advanced-toggle");
    return true;
  }

  function handleAdvancedGroupToggle(event) {
    const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-character-overview-group]") : null;
    if (!(trigger instanceof HTMLButtonElement)) return;
    const groupName = String(trigger.getAttribute("data-character-overview-group") || "").trim();
    toggleAdvancedGroup(groupName);
  }

  async function autofillField(field, controls = {}) {
    if (!currentRunId || !currentCharacterOverview) return { ok: false, filled: false, message: "" };
    const character = String(currentCharacterOverview.character || "").trim();
    const fieldName = String(field || "").trim();
    if (!character || !fieldName) return { ok: false, filled: false, message: "" };
    const labelText = CHARACTER_OVERVIEW_FIELD_LABELS[fieldName] || fieldName;
    if (typeof controls.onPending === "function") {
      controls.onPending(labelText, fieldName);
    }
    const restoreButton = setButtonPendingState(controls.button, "生成中...");
    try {
      const payload = await apiJson(
        `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}/suggest-field`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ field: fieldName }),
        },
        "人物信息补全失败。"
      );
      if (payload?.status !== "filled" || !payload?.value) {
        return {
          ok: true,
          filled: false,
          payload,
          field: fieldName,
          message: payload?.message || payload?.reason || "人物信息补全无法生成。",
        };
      }
      const nextFields = {
        ...(currentCharacterOverview.fields || {}),
        [fieldName]: payload.value,
      };
      const saved = await apiJson(
        `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...nextFields,
            review_source: "character_overview_autofill",
            review_note: String(payload?.source_mode || "").trim(),
          }),
        },
        "保存人物校对失败。"
      );
      rememberAutofill(character, payload);
      await applyCharacterOverviewPayload(saved, "character-overview-autofilled");
      return {
        ok: true,
        filled: true,
        payload,
        saved,
        field: fieldName,
        message: payload.message || `「${labelText}」已经补上，并写回这一卷。`,
      };
    } finally {
      restoreButton();
      if (typeof controls.onSettled === "function") {
        controls.onSettled(fieldName);
      }
    }
  }

  async function handleFieldAutofill(event) {
    const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-character-overview-field]") : null;
    if (!(trigger instanceof HTMLButtonElement)) return;
    const field = String(trigger.getAttribute("data-character-overview-field") || "").trim();
    const labelText = CHARACTER_OVERVIEW_FIELD_LABELS[field] || field;
    setStatus("character-overview-status", `正在补全「${labelText}」...`);
    try {
      const result = await autofillField(field, { button: trigger });
      if (result?.message) {
        setStatus("character-overview-status", result.message);
      }
    } catch (error) {
      setStatus("character-overview-status", error.message || "人物信息补全无法生成。");
    }
  }

  function resolveFieldInput(field, controls = {}) {
    if (controls.input instanceof HTMLTextAreaElement) {
      return controls.input;
    }
    const root = controls.root instanceof HTMLElement ? controls.root : el("character-overview-key-fields");
    const selector = `[data-character-overview-input="${field}"]`;
    const input = root?.querySelector(selector);
    return input instanceof HTMLTextAreaElement ? input : null;
  }

  async function saveField(field, value, controls = {}) {
    if (!currentRunId || !currentCharacterOverview) return { ok: false, changed: false, message: "" };
    const character = String(currentCharacterOverview.character || "").trim();
    const fieldName = String(field || "").trim();
    if (!character || !fieldName) return { ok: false, changed: false, message: "" };
    const labelText = CHARACTER_OVERVIEW_FIELD_LABELS[fieldName] || fieldName;
    const nextValue = String(value || "").trim();
    const currentValue = String(currentCharacterOverview?.fields?.[fieldName] || "").trim();
    if (nextValue === currentValue) {
      return {
        ok: true,
        changed: false,
        field: fieldName,
        saved: currentCharacterOverview,
        message: `「${labelText}」没有变化。`,
      };
    }
    if (typeof controls.onPending === "function") {
      controls.onPending(labelText, fieldName);
    }
    const button = controls.button instanceof HTMLButtonElement ? controls.button : null;
    const restoreButton = (() => {
      if (!button) return () => {};
      button.dataset.saving = "true";
      return setButtonPendingState(button, "保存中...");
    })();
    try {
      const nextFields = {
        ...(currentCharacterOverview.fields || {}),
        [fieldName]: nextValue,
      };
      const saved = await apiJson(
        `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildSavePayload(nextFields, "character_overview_inline_edit", "field_direct_save")),
        },
        "保存人物校对失败。"
      );
      await applyCharacterOverviewPayload(saved, "character-overview-field-saved");
      return {
        ok: true,
        changed: true,
        field: fieldName,
        saved,
        message: `「${labelText}」已经写回这一卷。`,
      };
    } finally {
      if (button) {
        delete button.dataset.saving;
      }
      restoreButton();
      if (typeof controls.onSettled === "function") {
        controls.onSettled(fieldName);
      }
    }
  }

  async function handleFieldSave(event) {
    const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-character-overview-save]") : null;
    if (!(trigger instanceof HTMLButtonElement) || !currentRunId || !currentCharacterOverview) return;
    const field = String(trigger.getAttribute("data-character-overview-save") || "").trim();
    if (!field) return;
    const input = resolveFieldInput(field);
    if (!(input instanceof HTMLTextAreaElement)) return;
    const labelText = CHARACTER_OVERVIEW_FIELD_LABELS[field] || field;
    setStatus("character-overview-status", `正在保存「${labelText}」...`);
    try {
      const result = await saveField(field, input.value, { button: trigger, input });
      if (!result.changed) {
        syncCharacterOverviewFieldSaveButton(input);
      }
      if (result?.message) {
        setStatus("character-overview-status", result.message);
      }
    } catch (error) {
      syncCharacterOverviewFieldSaveButton(input);
      setStatus("character-overview-status", error.message || "这次保存没有成功。");
    }
  }

  function openIncrementalDistillForCharacter(characterName) {
    const character = String(characterName || "").trim();
    if (!character || !currentRun) return;
    characterOverviewOpen = false;
    redistillPanelOpen = true;
    renderBookshelfDetail(currentRun);
    updateWorkflowState();
    publishCharacterOverviewState("character-overview-redistill-opened");
    const mergedCharacters = joinCharacters([character, ...parseCharacters(valueOf("redistill-characters", ""))]);
    setValue("redistill-characters", mergedCharacters);
    syncRedistillPreview();
    setStatus("redistill-status", `这轮会把「${character}」按增量方式继续补稳。`);
    el("redistill-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    el("redistill-characters")?.focus();
  }

  function openCharacterOverviewIncrementalDistill() {
    const character = String(currentCharacterOverview?.character || "").trim();
    openIncrementalDistillForCharacter(character);
  }

  async function openCharacterOverviewSessionMode(mode) {
    const character = String(currentCharacterOverview?.character || "").trim();
    if (!character || !currentRun) return false;
    await openNewDialogueSession();
    const characters = getRunCharacterNames(currentRun);
    setValue("dialogue-participants", joinCharacters(characters));
    setValue("dialogue-mode", mode);
    if (mode === "act") {
      setValue("dialogue-controlled", character);
    }
    syncModeFields();
    updateCharacterPillState();
    return true;
  }

  function openCurrentCharacterProfileFile() {
    const character = String(currentCharacterOverview?.character || "").trim();
    if (!character || !currentRun?.file_urls) return false;
    const url = currentRun.file_urls[`character_${character}`];
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
      return true;
    }
    return false;
  }

  window.__ZAOMENG_CHARACTER_OVERVIEW_ACTIONS__ = {
    autofillField,
    buildSavePayload,
    closeOverview,
    getExpandedGroups,
    getAutofillItems,
    handleAdvancedGroupToggle,
    handleFieldAutofill,
    handleFieldInput,
    handleFieldSave,
    historyKey,
    openCharacterOverview,
    openCharacterOverviewIncrementalDistill,
    openCharacterOverviewSessionMode,
    openCurrentCharacterProfileFile,
    openIncrementalDistillForCharacter,
    openReview,
    rememberAutofill,
    saveField,
    toggleAdvancedGroup,
  };
})();
