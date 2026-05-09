let appUpdateStatus = null;
let appUpdatePollTimer = 0;

const APP_UPDATE_DISMISS_PREFIX = "zaomeng:update-dismissed:";

function syncModeFields() {
  const mode = valueOf("dialogue-mode", "observe");
  syncChoiceGroup("dialogue-mode-options", "dialogue-mode");
  if (el("dialogue-controlled")) el("dialogue-controlled").disabled = mode !== "act";
  if (el("dialogue-self-name")) el("dialogue-self-name").disabled = mode !== "insert";
  if (el("dialogue-self-identity")) el("dialogue-self-identity").disabled = mode !== "insert";
  if (el("dialogue-self-style")) el("dialogue-self-style").disabled = mode !== "insert";
  toggle("controlled-field", mode === "act");
  toggle("self-name-field", mode === "insert");
  toggle("self-identity-field", mode === "insert");
  toggle("self-style-field", mode === "insert");
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
            self_profile: {
              display_name: trimmedValue("dialogue-self-name", ""),
              scene_identity: trimmedValue("dialogue-self-identity", ""),
              interaction_style: trimmedValue("dialogue-self-style", ""),
            },
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

async function openPersonaReview() {
  if (!currentRunId || !currentRun) return;
  fillPersonaReviewCharacterOptions(currentRun);
  const character = valueOf("persona-review-character", getRunCharacterNames(currentRun)[0] || "");
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
  bind("detail-stop-run-button", "click", handleStopRun);
  bind("open-persona-review-button", "click", openPersonaReview);
  bind("open-relation-details-button", "click", openRelationDetails);
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
  bind("back-to-bookshelf-button", "click", showBookshelfHome);
  bind("back-to-detail-button", "click", () => {
    chatModePickerOpen = false;
    updateWorkflowState();
  });

  bind("model-settings-form", "submit", handleModelSettingsSubmit);
  bind("persona-review-form", "submit", handlePersonaReviewSubmit);
  bind("create-run-form", "submit", handleCreateRunSubmit);
  bind("redistill-button", "click", handleRedistill);
  bind("redistill-add-button", "click", handleRedistillAdd);
  bind("redistill-refresh-button", "click", handleRedistillRefresh);
  bind("dialogue-session-form", "submit", handleDialogueSessionSubmit);
  bind("suggest-turn-button", "click", handleSuggestTurn);
  bind("prepare-turn-button", "click", handleSendTurn);

  bind("dialogue-mode", "change", syncModeFields);
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
  await Promise.all([
    loadModelSettings().catch((error) => console.warn("loadModelSettings failed", error)),
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
