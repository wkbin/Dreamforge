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
    setStatus("persona-review-status", "");
  } catch (error) {
    setStatus("persona-review-status", error.message || "人物档案暂时没有载入。");
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
          body: JSON.stringify({
            core_identity: trimmedValue("persona-core-identity", ""),
            story_role: trimmedValue("persona-story-role", ""),
            soul_goal: trimmedValue("persona-soul-goal", ""),
            speech_style: trimmedValue("persona-speech-style", ""),
            social_mode: trimmedValue("persona-social-mode", ""),
            worldview: trimmedValue("persona-worldview", ""),
            belief_anchor: trimmedValue("persona-belief-anchor", ""),
            moral_bottom_line: trimmedValue("persona-moral-bottom-line", ""),
            restraint_threshold: trimmedValue("persona-restraint-threshold", ""),
            stress_response: trimmedValue("persona-stress-response", ""),
            others_impression: trimmedValue("persona-others-impression", ""),
          }),
        },
        "保存人物校对失败。"
      )
    );
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

const DIALOGUE_PLACEHOLDER_DEFAULT = "写一句你想让他们听见的话";
const DIALOGUE_PLACEHOLDER_WAITING = "他们正在接住你的话。";

function setComposerWaiting(waiting, message = "") {
  const area = el("dialogue-message");
  const sendButton = el("prepare-turn-button");
  if (!area) return;
  if (waiting) {
    area.value = message || DIALOGUE_PLACEHOLDER_WAITING;
    area.disabled = true;
    if (sendButton) sendButton.disabled = true;
  } else {
    area.disabled = false;
    if (sendButton) sendButton.disabled = false;
    area.value = message || "";
    area.placeholder = DIALOGUE_PLACEHOLDER_DEFAULT;
  }
  resizeComposer();
}

async function handleSendTurn() {
  if (!currentRunId || !currentDialogueSessionId) {
    setComposerWaiting(false, "先进入这一幕，再把话递出去。");
    return;
  }
  const message = trimmedValue("dialogue-message", "");
  if (!message) {
    setComposerWaiting(false, "先写一句你想让他们听见的话。");
    return;
  }

  const sessionSnapshot = currentDialogueSession ? JSON.parse(JSON.stringify(currentDialogueSession)) : null;
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
    setComposerWaiting(false, "");
  } catch (error) {
    if (sessionSnapshot) {
      currentDialogueSession = sessionSnapshot;
      renderDialogueTranscript(sessionSnapshot);
    }
    setComposerWaiting(false, error.message || "这句话暂时没有送达。");
  }
}

function bindEvents() {
  bind("open-bookshelf-button", "click", showBookshelfHome);
  bind("open-settings-button", "click", openSettingsModal);
  bind("open-settings-primary", "click", openSettingsModal);
  bind("close-settings-button", "click", closeSettingsModal);
  bind("close-persona-review-button", "click", closePersonaReviewModal);
  bind("close-relation-details-button", "click", closeRelationDetailsModal);
  bind("toggle-connection-details-button", "click", () => {
    const details = el("connection-details");
    setConnectionDetailsVisible(details?.classList.contains("hidden"));
  });
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
  bind("prepare-turn-button", "click", handleSendTurn);

  bind("dialogue-mode", "change", syncModeFields);
  bind("persona-review-character", "change", handlePersonaCharacterChange);
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

  bindChoiceGroup("model-provider-options", "model-provider");
  bindChoiceGroup("dialogue-mode-options", "dialogue-mode", syncModeFields);
  bindChoiceGroup("dialogue-mode-options", "dialogue-mode", updateCharacterPillState);

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.closeModal === "true") {
      const modalId = target.dataset.modalId || "settings-modal";
      if (modalId === "persona-review-modal") {
        closePersonaReviewModal();
      } else if (modalId === "relation-details-modal") {
        closeRelationDetailsModal();
      } else {
        closeSettingsModal();
      }
    }
  });
}

async function boot() {
  syncModeFields();
  syncChoiceGroup("model-provider-options", "model-provider");
  syncChoiceGroup("dialogue-mode-options", "dialogue-mode");
  updateNovelFileView();
  updateRedistillFileView();
  resizeComposer();
  applySidebarState();
  await Promise.all([
    loadModelSettings().catch((error) => console.warn("loadModelSettings failed", error)),
    loadRecentSessions().catch((error) => console.warn("loadRecentSessions failed", error)),
    loadRunsOverview().catch((error) => console.warn("loadRunsOverview failed", error)),
  ]);
}

bindEvents();
boot();
