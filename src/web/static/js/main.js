let appUpdateStatus = null;
let appUpdatePollTimer = 0;

const APP_UPDATE_DISMISS_PREFIX = "zaomeng:update-dismissed:";

function syncModeFields() {
  const mode = valueOf("dialogue-mode", "observe");
  syncChoiceGroup("dialogue-mode-options", "dialogue-mode");
  if (el("dialogue-controlled")) el("dialogue-controlled").disabled = mode !== "act";
  if (el("dialogue-self-card")) el("dialogue-self-card").disabled = mode !== "insert";
  if (el("dialogue-self-name")) el("dialogue-self-name").disabled = mode !== "insert";
  if (el("dialogue-self-identity")) el("dialogue-self-identity").disabled = mode !== "insert";
  if (el("dialogue-self-style")) el("dialogue-self-style").disabled = mode !== "insert";
  toggle("controlled-field", mode === "act");
  toggle("self-card-field", mode === "insert");
  toggle("insert-self-fields", mode === "insert");
  toggle("self-card-preview-shell", mode === "insert");
  syncCustomSelect("dialogue-self-card");
  renderSelectedSelfCardPreview();
}

async function handleModelSettingsSubmit(event) {
  event.preventDefault();
  setStatus("model-settings-status", "正在把故事声源接进来...");
  try {
    modelSettings = await apiJson(
      "/api/web/settings/model",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: valueOf("model-provider", ""),
          model: trimmedValue("model-name", ""),
          base_url: trimmedValue("model-base-url", ""),
          api_key: trimmedValue("model-api-key", ""),
          max_tokens: Math.max(0, numberValue("model-max-tokens", 0) || 0),
        }),
      },
      "保存失败。"
    );
    applyModelSettingsView();
    setStatus("model-settings-status", "故事声源已经接通。");
    closeSettingsModal();
    updateWorkflowState();
  } catch (error) {
    setStatus("model-settings-status", error.message || "这次连接没有成功。");
  }
}

async function handleCreateRunSubmit(event) {
  event.preventDefault();
  if (!modelSettings.configured) {
    openSettingsModal();
    setStatus("form-status", "先把故事声源接进来，再开始这一卷。");
    return;
  }
  const file = el("novel-file")?.files?.[0];
  if (!file) {
    setStatus("form-status", "先放入一本书，故事才会往下走。");
    return;
  }
  const characters = charactersOf("characters");
  if (!characters.length) {
    setStatus("form-status", "至少写下一个你想遇见的人。");
    return;
  }
  runCreationPending = true;
  updateWorkflowState();
  setStatus("form-status", "正在翻检正文，替你把人物请出来...");
  try {
    renderRun(
      await apiJson(
        "/api/web/runs",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            novel_name: file.name,
            novel_content_base64: await fileToBase64(file),
            characters,
            max_sentences: numberValue("max-sentences", 120),
            max_chars: numberValue("max-chars", 50000),
            auto_run: true,
          }),
        },
        "蒸馏失败。"
      )
    );
    await loadRunsOverview();
    setStatus("form-status", "人物整理已经开始，进度会在这里慢慢往前走。");
  } catch (error) {
    runCreationPending = false;
    stopRunPolling();
    updateWorkflowState();
    setStatus("form-status", error.message || "这一轮人物整理没有成功。");
  }
}

async function handleRedistill() {
  if (!currentRunId) {
    setStatus("redistill-status", "先让这一卷成形，再继续补入人物。");
    return;
  }
  const characters = charactersOf("redistill-characters");
  const file = el("redistill-novel-file")?.files?.[0];
  if (!characters.length) {
    setStatus("redistill-status", "写下想继续补入的人物名字。");
    return;
  }
  runCreationPending = true;
  updateWorkflowState();
  setStatus("redistill-status", file ? "正在换入新的书段，并继续整理人物..." : "正在沿着这卷书继续往下整理...");
  try {
    renderRun(
      await apiJson(
        `/api/web/runs/${currentRunId}/redistill`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            characters,
            novel_name: file?.name || "",
            novel_content_base64: file ? await fileToBase64(file) : "",
            max_sentences: numberValue("max-sentences", 120),
            max_chars: numberValue("max-chars", 50000),
          }),
        },
        "继续蒸馏失败。"
      )
    );
    await loadRunsOverview();
    if (el("redistill-novel-file")) {
      el("redistill-novel-file").value = "";
      updateRedistillFileView();
    }
    setStatus("redistill-status", file ? "新的书段已经接入，这一轮增量整理开始了。" : "新的整理已经开始，人物会陆续补进来。");
  } catch (error) {
    runCreationPending = false;
    stopRunPolling();
    updateWorkflowState();
    setStatus("redistill-status", error.message || "这次继续整理没有接上。");
  }
}

async function handleStopRun() {
  if (!currentRunId || !currentRun || currentRun.status !== "running") {
    return;
  }
  if (!window.confirm(`确定先停下《${runNovelTitle(currentRun)}》这一轮蒸馏吗？`)) {
    return;
  }
  const stopButton = el("detail-stop-run-button");
  if (stopButton) {
    stopButton.disabled = true;
  }
  setText("detail-action-note", "正在收束当前步骤，很快就会停下来。", "");
  toggle("detail-action-note", true);
  try {
    renderRun(
      await apiJson(
        `/api/web/runs/${currentRunId}/stop`,
        {
          method: "POST",
        },
        "停止蒸馏失败。"
      ),
      { preserveDialogue: true }
    );
  } catch (error) {
    if (stopButton) {
      stopButton.disabled = false;
    }
    setText("detail-action-note", error.message || "这次停止没有成功。", "");
    toggle("detail-action-note", true);
  }
}

function handleRedistillAdd() {
  setValue("redistill-characters", "");
  setStatus("redistill-status", "写下新人物后，就可以继续整理。");
  updateRedistillPillState();
}

function handleRedistillRefresh() {
  setValue("redistill-characters", joinCharacters(getRunCharacterNames(currentRun)));
  setStatus("redistill-status", "当前人物已经带回来了，可以直接重新整理。");
  updateRedistillPillState();
}

async function handleDialogueSessionSubmit(event) {
  event.preventDefault();
  if (!currentRunId) {
    setStatus("dialogue-session-status", "先让人物从书页里走出来，再进入这一幕。");
    return;
  }
  try {
    const mode = valueOf("dialogue-mode", "observe");
    const controlledCharacter = trimmedValue("dialogue-controlled", "");
    let participants = charactersOf("dialogue-participants");
    if (mode === "act") {
      if (!controlledCharacter) {
        setStatus("dialogue-session-status", "先写下此刻由你扮演谁。");
        return;
      }
      participants = uniq([controlledCharacter, ...participants]);
      setValue("dialogue-participants", joinCharacters(participants));
      updateCharacterPillState();
    }
    sessionBooting = true;
    setComposerEnabled(false);
    renderSessionBooting(mode, participants);
    updateWorkflowState();
    setStatus("dialogue-session-status", "正在替你铺开这一幕...");
    await renderDialogueSession(
      await apiJson(
        `/api/web/runs/${currentRunId}/dialogue/sessions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode,
            participants,
            controlled_character: controlledCharacter,
            self_card_id: mode === "insert" ? selectedSelfCardId : "",
            self_profile:
              mode === "insert"
                ? {
                    ...(currentSelfCard?.fields || {}),
                    display_name: trimmedValue("dialogue-self-name", ""),
                    scene_identity: trimmedValue("dialogue-self-identity", ""),
                    interaction_style: trimmedValue("dialogue-self-style", ""),
                  }
                : {},
          }),
        },
        "进入聊天失败。"
      )
    );
    setStatus("dialogue-session-status", "这一幕已经铺好，你可以继续说下去。");
  } catch (error) {
    sessionBooting = false;
    setComposerEnabled(Boolean(currentDialogueSessionId));
    updateWorkflowState();
    setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。");
  }
}

const SELF_CARD_FIELD_BINDINGS = [
  ["display_name", "self-card-display-name"],
  ["scene_identity", "self-card-scene-identity"],
  ["interaction_style", "self-card-interaction-style"],
  ["core_identity", "self-card-core-identity"],
  ["story_role", "self-card-story-role"],
  ["identity_anchor", "self-card-identity-anchor"],
  ["temperament_type", "self-card-temperament-type"],
  ["soul_goal", "self-card-soul-goal"],
  ["hidden_desire", "self-card-hidden-desire"],
  ["inner_conflict", "self-card-inner-conflict"],
  ["self_cognition", "self-card-self-cognition"],
  ["private_self", "self-card-private-self"],
  ["speech_style", "self-card-speech-style"],
  ["cadence", "self-card-cadence"],
  ["typical_lines", "self-card-typical-lines"],
  ["signature_phrases", "self-card-signature-phrases"],
  ["sentence_openers", "self-card-sentence-openers"],
  ["sentence_endings", "self-card-sentence-endings"],
  ["social_mode", "self-card-social-mode"],
  ["thinking_style", "self-card-thinking-style"],
  ["decision_rules", "self-card-decision-rules"],
  ["reward_logic", "self-card-reward-logic"],
  ["worldview", "self-card-worldview"],
  ["belief_anchor", "self-card-belief-anchor"],
  ["moral_bottom_line", "self-card-moral-bottom-line"],
  ["restraint_threshold", "self-card-restraint-threshold"],
  ["core_traits", "self-card-core-traits"],
  ["key_bonds", "self-card-key-bonds"],
  ["forbidden_behaviors", "self-card-forbidden-behaviors"],
  ["stress_response", "self-card-stress-response"],
  ["emotion_model", "self-card-emotion-model"],
  ["anger_style", "self-card-anger-style"],
  ["joy_style", "self-card-joy-style"],
  ["grievance_style", "self-card-grievance-style"],
  ["others_impression", "self-card-others-impression"],
];

const SELF_CARD_REQUIRED_FIELDS = [
  "display_name",
  "core_identity",
  "story_role",
  "identity_anchor",
  "temperament_type",
  "soul_goal",
  "core_traits",
  "key_bonds",
  "speech_style",
  "worldview",
  "belief_anchor",
  "moral_bottom_line",
  "restraint_threshold",
  "stress_response",
];

function selfCardFieldId(field) {
  const item = SELF_CARD_FIELD_BINDINGS.find(([key]) => key === field);
  return item ? item[1] : "";
}

function collectSelfCardPayload() {
  return Object.fromEntries(SELF_CARD_FIELD_BINDINGS.map(([field, id]) => [field, trimmedValue(id, "")]));
}

function validateSelfCardPayload(fields) {
  const missing = SELF_CARD_REQUIRED_FIELDS.filter((field) => !String(fields?.[field] || "").trim());
  if (!missing.length) return "";
  const labels = missing.map((field) => {
    const span = el(selfCardFieldId(field))?.closest(".field-card")?.querySelector("span");
    return span?.textContent?.trim() || field;
  });
  return `请先补全这些必填项：${labels.join("、")}`;
}

function fillSelfCardFields(fields = {}) {
  SELF_CARD_FIELD_BINDINGS.forEach(([field, id]) => {
    setValue(id, fields?.[field] || "");
  });
}

function updateSelfCardDeleteButton() {
  const hasCard = Boolean(trimmedValue("self-card-id", ""));
  toggle("delete-self-card-button", hasCard);
}

function startSelfCardDraft(fields = {}) {
  currentSelfCard = { card_id: "", fields: { ...fields } };
  setValue("self-card-id", "");
  fillSelfCardFields(fields);
  updateSelfCardDeleteButton();
}

function openNewSelfCard() {
  startSelfCardDraft({
    display_name: trimmedValue("dialogue-self-name", "") || "你",
    scene_identity: trimmedValue("dialogue-self-identity", ""),
    interaction_style: trimmedValue("dialogue-self-style", ""),
  });
  setStatus("self-card-status", "你可以手写，也可以让 AI 先随机捏一张。");
  openSelfCardModal();
}

async function openExistingSelfCard(cardId) {
  if (!cardId) {
    openNewSelfCard();
    return;
  }
  setStatus("self-card-status", "正在载入角色卡...");
  try {
    const payload = await apiJson(`/api/web/self-cards/${encodeURIComponent(cardId)}`, {}, "角色卡载入失败。");
    currentSelfCard = payload;
    setValue("self-card-id", payload.card_id || "");
    fillSelfCardFields(payload.fields || {});
    updateSelfCardDeleteButton();
    setStatus("self-card-status", "");
    openSelfCardModal();
  } catch (error) {
    setStatus("dialogue-session-status", error.message || "角色卡载入失败。");
  }
}

function renderSelfCardOptions(items = selfCards) {
  const select = el("dialogue-self-card");
  if (!(select instanceof HTMLSelectElement)) return;
  const trigger = el("dialogue-self-card-trigger");
  const hint = el("dialogue-self-card-hint");
  const previous = select.value || selectedSelfCardId || "";
  select.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = items.length ? "先挑一张角色卡" : "还没有角色卡，先新建一张";
  select.appendChild(blank);
  (items || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.card_id || "";
    const displayName = item?.preview?.display_name || item?.fields?.display_name || item.card_id || "未命名角色卡";
    const sceneIdentity = item?.preview?.scene_identity || item?.fields?.scene_identity || "";
    option.textContent = sceneIdentity ? `${displayName} · ${sceneIdentity}` : displayName;
    select.appendChild(option);
  });
  if ((items || []).some((item) => item.card_id === previous)) {
    select.value = previous;
  } else {
    select.value = "";
  }
  if (trigger instanceof HTMLButtonElement) {
    trigger.disabled = items.length === 0;
  }
  if (hint) {
    hint.textContent = items.length
      ? "不选也能手动写，但选卡后会把完整人设一起带进场景。"
      : "你还没有角色卡。先新建一张，后面就能直接选卡入场。";
  }
  selectedSelfCardId = select.value;
  syncCustomSelect("dialogue-self-card");
  syncSelectedSelfCardFromSelect();
}

async function loadSelfCards() {
  const payload = await apiJson("/api/web/self-cards", {}, "角色卡列表载入失败。");
  selfCards = Array.isArray(payload?.items) ? payload.items : [];
  renderSelfCardOptions(selfCards);
  return selfCards;
}

function syncSelectedSelfCardFromSelect() {
  const select = el("dialogue-self-card");
  const nextId = select?.value || "";
  selectedSelfCardId = nextId;
  currentSelfCard = selfCards.find((item) => item.card_id === nextId) || null;
  if (currentSelfCard?.fields) {
    if (el("dialogue-self-name")) setValue("dialogue-self-name", currentSelfCard.fields.display_name || "");
    if (el("dialogue-self-identity")) {
      setValue("dialogue-self-identity", currentSelfCard.fields.scene_identity || currentSelfCard.fields.core_identity || "");
    }
    if (el("dialogue-self-style")) setValue("dialogue-self-style", currentSelfCard.fields.interaction_style || "");
  }
  renderSelectedSelfCardPreview();
}

function renderSelectedSelfCardPreview() {
  const card = currentSelfCard;
  const hasCards = selfCards.length > 0;
  const title = card?.preview?.display_name || card?.fields?.display_name || "";
  const copy =
    card?.preview?.scene_identity || card?.fields?.scene_identity || card?.fields?.core_identity || "";
  setText("self-card-preview-title", title || (hasCards ? "还没有选中角色卡" : "你还没有角色卡"), "");
  setText(
    "self-card-preview-copy",
    card
      ? copy || "这张卡已经接上，会把完整人设带进这场聊天。"
      : hasCards
        ? "选一张卡后，你的身份、气质和说话方式都会一起带进这场聊天。"
        : "先新建一张角色卡，后面就可以直接把完整人设带进场景。",
    ""
  );
  const root = el("self-card-preview-pills");
  if (!root) return;
  root.innerHTML = "";
  const preview = card?.preview || {};
  [preview.core_identity, preview.story_role, preview.temperament_type, preview.speech_style, preview.soul_goal]
    .filter(Boolean)
    .slice(0, 5)
    .forEach((value) => {
      const chip = document.createElement("span");
      chip.textContent = value;
      root.appendChild(chip);
    });
  const editButton = el("edit-self-card-button");
  if (editButton) {
    editButton.disabled = !card;
    editButton.classList.toggle("hidden", !card);
  }
}

async function handleSelfCardSelectionChange() {
  syncSelectedSelfCardFromSelect();
}

async function handleOpenNewSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  openNewSelfCard();
}

async function handleEditCurrentSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  if (!selectedSelfCardId) {
    openNewSelfCard();
    return;
  }
  await openExistingSelfCard(selectedSelfCardId);
}

async function handleGenerateSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const button = el("generate-self-card-button");
  if (button) button.disabled = true;
  setStatus("self-card-status", "正在随机生成一张角色卡...");
  try {
    const payload = await apiJson(
      "/api/web/self-cards/generate",
      { method: "POST" },
      "角色卡生成失败。"
    );
    fillSelfCardFields(payload.fields || {});
    setStatus("self-card-status", "AI 已经把整张卡先填好了，你可以直接保存，也可以再手修。");
  } catch (error) {
    setStatus("self-card-status", error.message || "角色卡生成失败。");
  } finally {
    if (button) button.disabled = false;
  }
}

async function handleSelfCardSubmit(event) {
  event.preventDefault();
  const cardId = trimmedValue("self-card-id", "");
  const fields = collectSelfCardPayload();
  const validationMessage = validateSelfCardPayload(fields);
  if (validationMessage) {
    setStatus("self-card-status", validationMessage);
    return;
  }
  setStatus("self-card-status", "正在保存角色卡...");
  try {
    const payload = await apiJson(
      cardId ? `/api/web/self-cards/${encodeURIComponent(cardId)}` : "/api/web/self-cards",
      {
        method: cardId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      },
      "角色卡保存失败。"
    );
    await loadSelfCards();
    selectedSelfCardId = payload.card_id || "";
    const select = el("dialogue-self-card");
    if (select) {
      select.value = selectedSelfCardId;
      syncCustomSelect("dialogue-self-card");
    }
    syncSelectedSelfCardFromSelect();
    setStatus("dialogue-session-status", "角色卡已经接好，现在可以直接带它入场。");
    setStatus("self-card-status", "角色卡已保存。");
    closeSelfCardModal();
  } catch (error) {
    setStatus("self-card-status", error.message || "角色卡保存失败。");
  }
}

async function handleDeleteSelfCard(event) {
  if (event && typeof event.preventDefault === "function") event.preventDefault();
  const cardId = trimmedValue("self-card-id", "");
  if (!cardId) return;
  if (!window.confirm("确定删除这张角色卡吗？")) {
    return;
  }
  setStatus("self-card-status", "正在删除角色卡...");
  try {
    await apiJson(
      `/api/web/self-cards/${encodeURIComponent(cardId)}`,
      { method: "DELETE" },
      "角色卡删除失败。"
    );
    if (selectedSelfCardId === cardId) {
      selectedSelfCardId = "";
    }
    await loadSelfCards();
    currentSelfCard = null;
    renderSelectedSelfCardPreview();
    setStatus("dialogue-session-status", "角色卡已经删掉了。");
    closeSelfCardModal();
  } catch (error) {
    setStatus("self-card-status", error.message || "角色卡删除失败。");
  }
}

async function openPersonaReviewForCharacter(characterName = "") {
  if (!currentRunId || !currentRun) return;
  fillPersonaReviewCharacterOptions(currentRun);
  const fallbackCharacter = getRunCharacterNames(currentRun)[0] || "";
  const character = String(characterName || "").trim() || valueOf("persona-review-character", fallbackCharacter) || fallbackCharacter;
  if (character && el("persona-review-character")) {
    setValue("persona-review-character", character);
  }
  if (!character) {
    setStatus("persona-review-status", "这一卷里还没有可校对的人物。");
    return;
  }
  openPersonaReviewModal();
  setStatus("persona-review-status", "正在载入人物档案...");
  try {
    renderPersonaReview(await apiJson(`/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`));
    renderPersonaAutofillReferences(null);
    setStatus("persona-review-status", ""); 
  } catch (error) {
    setStatus("persona-review-status", error.message || "人物档案暂时没有载入。");
  }
}

async function openPersonaReview() {
  await openPersonaReviewForCharacter("");
}

async function openWorkCharacterReview() {
  if (!currentRunId || !currentRun) return;
  const names = getRunCharacterNames(currentRun);
  if (!names.length) {
    setStatus("bookshelf-status", "这一卷里还没有可校对的人物。");
    return;
  }

  let targetCharacter = "";
  if (typeof buildWorkPriorityReviewItems === "function") {
    const priority = buildWorkPriorityReviewItems(currentRun);
    targetCharacter = String(priority?.[0]?.name || "").trim();
  }
  if (!targetCharacter) {
    targetCharacter = names[0] || "";
  }
  if (!targetCharacter) {
    setStatus("bookshelf-status", "这一卷里还没有可校对的人物。");
    return;
  }

  if (typeof openCharacterOverview === "function") {
    await openCharacterOverview(targetCharacter);
    return;
  }
  await openPersonaReviewForCharacter(targetCharacter);
}

async function openQuickDialogueMode(mode) {
  await openNewDialogueSession();
  if (!currentRun || !el("dialogue-mode")) return;
  setValue("dialogue-mode", mode);
  syncModeFields();
  updateCharacterPillState();
}

async function handlePersonaCharacterChange() {
  if (!currentRunId) return;
  const character = valueOf("persona-review-character", "");
  if (!character) return;
  setStatus("persona-review-status", "正在切换人物...");
  try {
    renderPersonaReview(await apiJson(`/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`));
    renderPersonaAutofillReferences(null);
    setStatus("persona-review-status", "");
  } catch (error) {
    setStatus("persona-review-status", error.message || "人物档案暂时没有载入。");
  }
}

function collectPersonaReviewPayload() {
  return Object.fromEntries(
    (PERSONA_REVIEW_FIELD_BINDINGS || []).map(([field, id]) => [field, trimmedValue(id, "")])
  );
}

async function handlePersonaFieldAutofill(event) {
  const trigger = event.target instanceof HTMLElement ? event.target.closest("[data-persona-autofill-field]") : null;
  if (!(trigger instanceof HTMLButtonElement) || !currentRunId) return;
  const character = valueOf("persona-review-character", "");
  const field = trigger.getAttribute("data-persona-autofill-field") || "";
  if (!character || !field) {
    setStatus("persona-review-status", "先选一个人物。");
    return;
  }
  const labelText = trigger.closest(".field-card")?.querySelector(".field-card-head span, span")?.textContent || field;
  trigger.dataset.loading = "true";
  trigger.disabled = true;
  const originalText = trigger.textContent || "AI补全";
  trigger.textContent = "生成中...";
  setPersonaReviewFieldFeedback(field, "loading", "正在生成补全...");
  setStatus("persona-review-status", `正在生成「${labelText}」的补全内容...`);
  try {
    const payload = await apiJson(
      `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}/suggest-field`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field }),
      },
      "人物信息补全失败。"
    );
    if (payload?.status === "filled" && payload?.value) {
      const targetId = personaReviewFieldId(field);
      if (targetId) {
        setValue(targetId, payload.value);
      }
      markPersonaReviewFieldAutofilled(field);
      renderPersonaAutofillReferences(payload);
      setPersonaReviewFieldFeedback(field, "success", "已生成补全内容，记得保存。");
      setStatus("persona-review-status", payload.message || "已生成补全内容，请记得保存人物校对。");
    } else {
      renderPersonaAutofillReferences(payload);
      setPersonaReviewFieldFeedback(field, "error", payload?.message || payload?.reason || "人物信息补全无法生成。");
      setStatus("persona-review-status", payload?.message || payload?.reason || "人物信息补全无法生成。");
    }
  } catch (error) {
    renderPersonaAutofillReferences(null);
    setPersonaReviewFieldFeedback(field, "error", error.message || "人物信息补全无法生成。");
    setStatus("persona-review-status", error.message || "人物信息补全无法生成。");
  } finally {
    delete trigger.dataset.loading;
    trigger.disabled = false;
    trigger.textContent = originalText;
    syncPersonaReviewAutofillButtons();
  }
}

async function handlePersonaReviewSubmit(event) {
  event.preventDefault();
  if (!currentRunId) return;
  const character = valueOf("persona-review-character", "");
  if (!character) {
    setStatus("persona-review-status", "先选一个人物。");
    return;
  }
  setStatus("persona-review-status", "正在写回人物校对...");
  try {
    renderPersonaReview(
      await apiJson(
        `/api/web/runs/${currentRunId}/personas/${encodeURIComponent(character)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectPersonaReviewPayload()),
        },
        "保存人物校对失败。"
      )
    );
    clearAllPersonaReviewAutofilledFields();
    clearAllPersonaReviewFieldFeedback();
    renderPersonaAutofillReferences(null);
    renderRun(await apiJson(`/api/web/runs/${currentRunId}`));
    setStatus("persona-review-status", "人物校对已经写回这一卷。");
  } catch (error) {
    setStatus("persona-review-status", error.message || "这次校对没有保存成功。");
  }
}

async function openRelationDetails() {
  if (!currentRunId) return;
  openRelationDetailsModal();
  setStatus("relation-details-status", "正在整理关系明细...");
  try {
    renderRelationDetails(await apiJson(`/api/web/runs/${currentRunId}/relations`));
  } catch (error) {
    setStatus("relation-details-status", error.message || "关系明细暂时没有载入。");
  }
}

function openAppUpdateModal() {
  toggle("app-update-modal", true);
  if (typeof syncModalScrollLock === "function") syncModalScrollLock();
}

function closeAppUpdateModal() {
  toggle("app-update-modal", false);
  if (typeof syncModalScrollLock === "function") syncModalScrollLock();
}

function appUpdateDismissKey(currentVersion, remoteVersion) {
  return `${APP_UPDATE_DISMISS_PREFIX}${String(currentVersion || "").trim()}->${String(remoteVersion || "").trim()}`;
}

function rememberDismissedAppUpdate(status = appUpdateStatus) {
  const currentVersion = String(status?.current_version || "").trim();
  const remoteVersion = String(status?.remote_version || "").trim();
  if (!currentVersion || !remoteVersion || !window.localStorage) return;
  window.localStorage.setItem(appUpdateDismissKey(currentVersion, remoteVersion), "1");
}

function wasAppUpdateDismissed(status = appUpdateStatus) {
  const currentVersion = String(status?.current_version || "").trim();
  const remoteVersion = String(status?.remote_version || "").trim();
  if (!currentVersion || !remoteVersion || !window.localStorage) return false;
  return window.localStorage.getItem(appUpdateDismissKey(currentVersion, remoteVersion)) === "1";
}

function clearAppUpdatePolling() {
  if (!appUpdatePollTimer) return;
  window.clearTimeout(appUpdatePollTimer);
  appUpdatePollTimer = 0;
}

function renderAppUpdateStatus(status) {
  appUpdateStatus = status || null;
  setText("app-update-current-version", status?.current_version || "-", "");
  setText("app-update-remote-version", status?.remote_version || "-", "");
  setStatus("app-update-status", status?.message || "");
  const confirmButton = el("confirm-app-update-button");
  const closeButton = el("close-app-update-button");
  const dismissButton = el("dismiss-app-update-button");
  const updating = String(status?.status || "") === "updating";
  if (confirmButton) {
    confirmButton.disabled = updating || !status?.update_available;
    confirmButton.textContent = updating ? "更新中..." : "现在更新";
  }
  if (closeButton) closeButton.disabled = updating;
  if (dismissButton) dismissButton.disabled = updating;
}

async function fetchAppUpdateStatus(force = false) {
  const suffix = force ? "?force=true" : "";
  const status = await apiJson(`/api/web/settings/update${suffix}`, {}, "检查更新失败。");
  renderAppUpdateStatus(status);
  return status;
}

function scheduleAppUpdatePolling() {
  clearAppUpdatePolling();
  appUpdatePollTimer = window.setTimeout(async () => {
    try {
      const status = await fetchAppUpdateStatus(false);
      if (status?.status === "updating") {
        scheduleAppUpdatePolling();
        return;
      }
      if (status?.status === "completed" && status?.reload_required) {
        window.setTimeout(() => window.location.reload(), 900);
      }
    } catch (error) {
      setStatus("app-update-status", error.message || "刚才那次更新状态暂时没取到。");
    }
  }, 1200);
}

async function checkAppUpdateOnBoot() {
  try {
    const status = await fetchAppUpdateStatus(true);
    if (!status?.supported || !status?.update_available || wasAppUpdateDismissed(status)) {
      return;
    }
    openAppUpdateModal();
  } catch (error) {
    console.warn("checkAppUpdateOnBoot failed", error);
  }
}

function dismissAppUpdateModal() {
  rememberDismissedAppUpdate(appUpdateStatus);
  closeAppUpdateModal();
}

async function handleConfirmAppUpdate() {
  const confirmButton = el("confirm-app-update-button");
  if (confirmButton) confirmButton.disabled = true;
  setStatus("app-update-status", "正在替你接上更新...");
  try {
    const status = await apiJson(
      "/api/web/settings/update",
      {
        method: "POST",
      },
      "开始更新失败。"
    );
    renderAppUpdateStatus(status);
    openAppUpdateModal();
    scheduleAppUpdatePolling();
  } catch (error) {
    if (confirmButton) confirmButton.disabled = false;
    setStatus("app-update-status", error.message || "这次更新没有接上。");
  }
}

const DIALOGUE_PLACEHOLDER_DEFAULT = "写一句你想让他们听见的话";
const DIALOGUE_PLACEHOLDER_WAITING = "他们正在接住你的话。";
const DIALOGUE_SUGGESTION_WAITING = "正在生成中...";
const DIALOGUE_SUGGESTION_BUSY_LABEL = "…";
const DIALOGUE_RETRY_FEEDBACK_DELAY_MS = 2200;
const DIALOGUE_SEND_RETRY_MESSAGE = "这次声源有点慢，正在自动重试...";
const DIALOGUE_SUGGEST_RETRY_MESSAGE = "这次生成有点慢，正在自动重试...";
const OBSERVE_QUICK_REPLIES = [
  { label: "……", value: "……" },
  { label: "继续聊", value: "继续聊。" },
  { label: "别停", value: "别停，继续往下说。" },
  { label: "有人打断", value: "门外忽然传来一点动静，屋里的人都顿了一下。" },
  { label: "再逼近点", value: "这句话落下去以后，气氛反而更近了一步。" },
];

function setQuickRepliesEnabled(enabled) {
  document.querySelectorAll("#observe-quick-replies .quick-reply-chip").forEach((node) => {
    node.disabled = !enabled;
  });
}

function syncSuggestButtonVisibility(session = currentDialogueSession) {
  const suggestButton = el("suggest-turn-button");
  if (!suggestButton) return;
  const mode = session?.mode || session?.session_card?.mode || "";
  const hidden = mode === "observe";
  suggestButton.classList.toggle("hidden", hidden);
  if (hidden) {
    suggestButton.disabled = true;
  }
}

function setComposerWaiting(waiting, message = "") {
  const area = el("dialogue-message");
  const sendButton = el("prepare-turn-button");
  const suggestButton = el("suggest-turn-button");
  if (!area) return;
  if (waiting) {
    area.value = message || DIALOGUE_PLACEHOLDER_WAITING;
    area.disabled = true;
    if (sendButton) sendButton.disabled = true;
    if (suggestButton) suggestButton.disabled = true;
  } else {
    area.disabled = false;
    if (sendButton) sendButton.disabled = false;
    if (suggestButton) suggestButton.disabled = false;
    area.value = message || "";
    area.placeholder = DIALOGUE_PLACEHOLDER_DEFAULT;
  }
  setQuickRepliesEnabled(!waiting);
  resizeComposer();
}

function setSuggestingState(waiting) {
  const area = el("dialogue-message");
  const sendButton = el("prepare-turn-button");
  const suggestButton = el("suggest-turn-button");
  if (area) area.disabled = waiting;
  if (sendButton) sendButton.disabled = waiting;
  if (suggestButton) {
    suggestButton.disabled = waiting;
    suggestButton.textContent = waiting ? DIALOGUE_SUGGESTION_BUSY_LABEL : "✨";
    suggestButton.setAttribute("aria-busy", waiting ? "true" : "false");
  }
  setQuickRepliesEnabled(!waiting);
}

function renderObserveQuickReplies(session = currentDialogueSession) {
  const root = el("observe-quick-replies");
  if (!root) return;
  const mode = session?.mode || session?.session_card?.mode || "";
  if (mode !== "observe") {
    root.innerHTML = "";
    root.classList.add("hidden");
    return;
  }

  root.innerHTML = "";
  OBSERVE_QUICK_REPLIES.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-reply-chip";
    button.textContent = item.label;
    button.setAttribute("data-value", item.value);
    button.addEventListener("click", () => {
      applyQuickReply(item.value);
    });
    root.appendChild(button);
  });
  root.classList.remove("hidden");
}

async function applyQuickReply(value) {
  const message = String(value || "").trim();
  const area = el("dialogue-message");
  if (!message || !area || area.disabled) return;
  await handleSendTurn(message);
}

function coerceMessageOverride(value) {
  if (value && typeof value === "object") {
    if (typeof value.preventDefault === "function") value.preventDefault();
    if (typeof value.stopPropagation === "function") value.stopPropagation();
    return "";
  }
  return String(value || "");
}

async function handleSendTurn(messageOverride = "") {
  if (!currentRunId || !currentDialogueSessionId) {
    setComposerWaiting(false, "先进入这一幕，再把话递出去。");
    return;
  }
  const message = coerceMessageOverride(messageOverride).trim() || trimmedValue("dialogue-message", "");
  if (!message) {
    setComposerWaiting(false, "先写一句你想让他们听见的话。");
    return;
  }

  const sessionSnapshot = currentDialogueSession ? JSON.parse(JSON.stringify(currentDialogueSession)) : null;
  const retryFeedbackTimer = window.setTimeout(() => {
    setComposerWaiting(true, DIALOGUE_SEND_RETRY_MESSAGE);
  }, DIALOGUE_RETRY_FEEDBACK_DELAY_MS);
  setComposerWaiting(true, DIALOGUE_PLACEHOLDER_WAITING);

  if (currentDialogueSession) {
    currentDialogueSession = {
      ...currentDialogueSession,
      transcript: buildOptimisticTranscript(currentDialogueSession, message),
    };
    renderDialogueTranscript(currentDialogueSession);
  }

  try {
    await renderDialogueSession(
      await apiJson(
        `/api/web/runs/${currentRunId}/dialogue/sessions/${currentDialogueSessionId}/reply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        },
        "发送失败。"
      )
    );
    window.clearTimeout(retryFeedbackTimer);
    setComposerWaiting(false, "");
  } catch (error) {
    window.clearTimeout(retryFeedbackTimer);
    if (sessionSnapshot) {
      currentDialogueSession = sessionSnapshot;
      renderDialogueTranscript(sessionSnapshot);
    }
    setComposerWaiting(false, error.message || "这句话暂时没有送达。");
  }
}

async function handleSuggestTurn(event) {
  if (event && typeof event.preventDefault === "function") {
    event.preventDefault();
  }
  console.log("[dialogue suggest] click", {
    runId: currentRunId,
    sessionId: currentDialogueSessionId,
  });
  if (!currentRunId || !currentDialogueSessionId) {
    return;
  }

  const area = el("dialogue-message");
  if (!area) return;

  const draftText = String(area.value || "");
  const seedText = draftText.trim();
  area.value = DIALOGUE_SUGGESTION_WAITING;
  resizeComposer();
  setSuggestingState(true);
  const retryFeedbackTimer = window.setTimeout(() => {
    area.value = DIALOGUE_SUGGEST_RETRY_MESSAGE;
    resizeComposer();
  }, DIALOGUE_RETRY_FEEDBACK_DELAY_MS);

  try {
    console.log("[dialogue suggest] request", { seedText });
    const payload = await apiJson(
      `/api/web/runs/${currentRunId}/dialogue/sessions/${currentDialogueSessionId}/suggest`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed_text: seedText }),
      },
      "续写建议生成失败。"
    );
    console.log("[dialogue suggest] success", payload);
    window.clearTimeout(retryFeedbackTimer);
    area.value = payload.suggestion || "";
    area.focus();
    area.setSelectionRange(area.value.length, area.value.length);
    resizeComposer();
  } catch (error) {
    console.log("[dialogue suggest] error", error);
    window.clearTimeout(retryFeedbackTimer);
    area.value = draftText;
    resizeComposer();
  } finally {
    setSuggestingState(false);
  }
}

function bindEvents() {
  bind("open-bookshelf-button", "click", showBookshelfHome);
  bind("open-settings-button", "click", openSettingsModal);
  bind("open-settings-primary", "click", openSettingsModal);
  bind("close-settings-button", "click", closeSettingsModal);
  bind("close-persona-review-button", "click", closePersonaReviewModal);
  bind("close-relation-details-button", "click", closeRelationDetailsModal);
  bind("close-self-card-button", "click", closeSelfCardModal);
  bind("close-app-update-button", "click", dismissAppUpdateModal);
  bind("dismiss-app-update-button", "click", dismissAppUpdateModal);
  bind("confirm-app-update-button", "click", handleConfirmAppUpdate);
  bind("toggle-sidebar-button", "click", () => {
    sidebarCollapsed = !sidebarCollapsed;
    applySidebarState();
  });
  bind("new-dialogue-session-button", "click", openNewDialogueSession);
  bind("bookshelf-new-run-button", "click", startNewRunFlow);
  bind("back-from-distill-button", "click", showBookshelfHome);
  bind("detail-start-chat-button", "click", openNewDialogueSession);
  bind("quick-open-observe-button", "click", () => {
    openQuickDialogueMode("observe").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
  });
  bind("quick-open-act-button", "click", () => {
    openQuickDialogueMode("act").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
  });
  bind("quick-open-insert-button", "click", () => {
    openQuickDialogueMode("insert").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
  });
  bind("detail-stop-run-button", "click", handleStopRun);
  bind("open-persona-review-button", "click", () => {
    openWorkCharacterReview().catch((error) => {
      setStatus("bookshelf-status", error.message || "人物档案暂时没有载入。");
    });
  });
  bind("open-relation-details-button", "click", openRelationDetails);
  bind("detail-export-summary-button", "click", () => {
    if (typeof openWorkSummaryExport === "function") {
      openWorkSummaryExport();
    }
  });
  bind("detail-view-timeline-button", "click", () => {
    if (typeof openWorkTimeline === "function") {
      openWorkTimeline();
    }
  });
  bind("back-to-work-overview-button", "click", () => {
    characterOverviewOpen = false;
    updateWorkflowState();
  });
  bind("character-overview-review-button", "click", () => {
    if (!currentCharacterOverview?.character) return;
    openPersonaReviewForCharacter(currentCharacterOverview.character).catch((error) =>
      setStatus("persona-review-status", error.message || "人物档案暂时没有载入。")
    );
  });
  bind("character-overview-redistill-button", "click", () => {
    if (typeof openCharacterOverviewIncrementalDistill === "function") {
      openCharacterOverviewIncrementalDistill();
    }
  });
  bind("character-overview-act-button", "click", () => {
    if (typeof openCharacterOverviewSessionMode === "function") {
      openCharacterOverviewSessionMode("act").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
    }
  });
  bind("character-overview-insert-button", "click", () => {
    if (typeof openCharacterOverviewSessionMode === "function") {
      openCharacterOverviewSessionMode("insert").catch((error) => setStatus("dialogue-session-status", error.message || "这一幕暂时没有铺开。"));
    }
  });
  bind("character-overview-export-button", "click", () => {
    if (typeof openCurrentCharacterProfileFile === "function") {
      openCurrentCharacterProfileFile();
    }
  });
  el("character-overview-key-fields")?.addEventListener("click", (event) => {
    if (typeof handleCharacterOverviewFieldAutofill === "function") {
      handleCharacterOverviewFieldAutofill(event);
    }
    if (typeof handleCharacterOverviewFieldSave === "function") {
      handleCharacterOverviewFieldSave(event);
    }
  });
  el("character-overview-key-fields")?.addEventListener("input", (event) => {
    if (typeof handleCharacterOverviewFieldInput === "function") {
      handleCharacterOverviewFieldInput(event);
    }
  });
  el("character-overview-advanced-groups")?.addEventListener("click", (event) => {
    if (typeof handleCharacterOverviewAdvancedGroupToggle === "function") {
      handleCharacterOverviewAdvancedGroupToggle(event);
    }
  });
  window.addEventListener("resize", () => {
    if (typeof syncViewportHeightVar === "function") {
      syncViewportHeightVar();
    }
    if (typeof applySessionListViewportLock === "function") {
      applySessionListViewportLock();
    }
  });
  bind("detail-redistill-button", "click", () => {
    if (!currentRunId) return;
    redistillPanelOpen = !redistillPanelOpen;
    renderBookshelfDetail(currentRun);
    updateWorkflowState();
    if (redistillPanelOpen) {
      el("redistill-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      el("redistill-characters")?.focus();
    }
  });
  bind("source-history-toggle", "click", () => {
    sourceHistoryExpanded = !sourceHistoryExpanded;
    if (currentRun) {
      renderSourceHistory(currentRun);
    }
  });
  bind("run-character-readiness-toggle", "click", () => {
    characterReadinessExpanded = !characterReadinessExpanded;
    if (currentRun) {
      renderCharacterReadiness(currentRun);
    }
  });
  bind("back-to-bookshelf-button", "click", showBookshelfHome);
  bind("back-to-detail-button", "click", () => {
    chatModePickerOpen = false;
    updateWorkflowState();
  });

  bind("model-settings-form", "submit", handleModelSettingsSubmit);
  bind("persona-review-form", "submit", handlePersonaReviewSubmit);
  bind("self-card-form", "submit", handleSelfCardSubmit);
  bind("create-run-form", "submit", handleCreateRunSubmit);
  bind("redistill-button", "click", handleRedistill);
  bind("redistill-add-button", "click", handleRedistillAdd);
  bind("redistill-refresh-button", "click", handleRedistillRefresh);
  bind("dialogue-session-form", "submit", handleDialogueSessionSubmit);
  bind("create-self-card-button", "click", handleOpenNewSelfCard);
  bind("edit-self-card-button", "click", handleEditCurrentSelfCard);
  bind("generate-self-card-button", "click", handleGenerateSelfCard);
  bind("delete-self-card-button", "click", handleDeleteSelfCard);
  bind("suggest-turn-button", "click", handleSuggestTurn);
  bind("prepare-turn-button", "click", handleSendTurn);

  bind("dialogue-mode", "change", syncModeFields);
  bind("dialogue-self-card", "change", handleSelfCardSelectionChange);
  bind("persona-review-character", "change", handlePersonaCharacterChange);
  el("persona-review-form")?.addEventListener("input", (event) => {
    const target = event.target;
    if (target instanceof HTMLElement) {
      const field = PERSONA_REVIEW_FIELD_BINDINGS.find(([, id]) => id === target.id)?.[0];
      if (field) {
        clearPersonaReviewFieldAutofilled(field);
        setPersonaReviewFieldFeedback(field, "", "");
      }
    }
    syncPersonaReviewAutofillButtons();
  });
  el("persona-review-form")?.addEventListener("click", handlePersonaFieldAutofill);
  bind("dialogue-mode", "change", updateCharacterPillState);
  bind("dialogue-participants", "input", updateCharacterPillState);
  bind("redistill-characters", "input", updateRedistillPillState);
  bind("dialogue-message", "input", resizeComposer);
  bind("novel-file", "change", updateNovelFileView);
  bind("characters", "input", refreshSamplingHintEstimate);
  bind("max-sentences", "input", refreshSamplingHintEstimate);
  bind("max-chars", "input", refreshSamplingHintEstimate);
  bind("redistill-novel-file", "change", updateRedistillFileView);
  bind("dialogue-message", "keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      el("prepare-turn-button")?.click();
    }
  });

  bindChoiceGroup("dialogue-mode-options", "dialogue-mode", syncModeFields);
  bindChoiceGroup("dialogue-mode-options", "dialogue-mode", updateCharacterPillState);
  bindChoiceGroup("model-provider-options", "model-provider");

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.closeModal === "true") {
      const modalId = target.dataset.modalId || "settings-modal";
      if (modalId === "persona-review-modal") {
        closePersonaReviewModal();
      } else if (modalId === "self-card-modal") {
        closeSelfCardModal();
      } else if (modalId === "relation-details-modal") {
        closeRelationDetailsModal();
      } else if (modalId === "app-update-modal") {
        dismissAppUpdateModal();
      } else {
        closeSettingsModal();
      }
    }
  });
}

async function boot() {
  if (typeof syncViewportHeightVar === "function") {
    syncViewportHeightVar();
  }
  ensureConnectionDetailsVisible();
  syncModeFields();
  syncChoiceGroup("dialogue-mode-options", "dialogue-mode");
  syncChoiceGroup("model-provider-options", "model-provider");
  updateNovelFileView();
  updateRedistillFileView();
  resizeComposer();
  applySidebarState();
  initCustomSelect("dialogue-self-card");
  await Promise.all([
    loadModelSettings().catch((error) => console.warn("loadModelSettings failed", error)),
    loadSelfCards().catch((error) => console.warn("loadSelfCards failed", error)),
    loadRecentSessions().catch((error) => console.warn("loadRecentSessions failed", error)),
    loadRunsOverview().catch((error) => console.warn("loadRunsOverview failed", error)),
  ]);
  await checkAppUpdateOnBoot();
}

bindEvents();
window.handleSuggestTurn = handleSuggestTurn;
window.applyQuickReply = applyQuickReply;
window.syncSuggestButtonVisibility = syncSuggestButtonVisibility;
syncSuggestButtonVisibility(null);
console.log("[zaomeng web] main.js loaded", window.__ZAOMENG_WEB_UI_VERSION__ || "unknown");
boot();
