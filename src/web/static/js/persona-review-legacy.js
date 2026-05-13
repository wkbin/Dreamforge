function fillPersonaReviewCharacterOptions(run) {
  const select = el("persona-review-character");
  if (!select) return;
  const names = getRunCharacterNames(run);
  const currentValue = select.value;
  select.innerHTML = "";
  names.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
  if (names.includes(currentValue)) {
    select.value = currentValue;
  } else if (names.length) {
    select.value = names[0];
  }
  renderPersonaReviewCharacterOptions(names, select.value);
}

function renderPersonaReview(payload) {
  currentPersonaReview = payload;
  fillPersonaReviewFields(payload?.fields || {});
  if (payload?.character && el("persona-review-character")) {
    el("persona-review-character").value = payload.character;
  }
  renderPersonaReviewCharacterOptions(getRunCharacterNames(currentRun), valueOf("persona-review-character", ""));
  if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("persona-review-rendered");
  }
}

function renderPersonaReviewCharacterOptions(names, currentValue) {
  const root = el("persona-review-character-options");
  const select = el("persona-review-character");
  if (!root || !select) return;
  root.innerHTML = "";
  if (!(names || []).length) {
    const hint = document.createElement("span");
    hint.className = "pill hint-pill";
    hint.textContent = "请先选择一卷已完成的人物";
    root.appendChild(hint);
    return;
  }

  names.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pill persona-pill";
    button.textContent = name;
    if (name === currentValue) {
      button.classList.add("active");
    }
    button.addEventListener("click", () => {
      if (select.value === name) {
        return;
      }
      select.value = name;
      renderPersonaReviewCharacterOptions(names, name);
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    root.appendChild(button);
  });
}

const PERSONA_REVIEW_FIELD_BINDINGS = [
  ["core_identity", "persona-core-identity"],
  ["story_role", "persona-story-role"],
  ["identity_anchor", "persona-identity-anchor"],
  ["temperament_type", "persona-temperament-type"],
  ["gender", "persona-gender"],
  ["age_stage", "persona-age-stage"],
  ["appearance_feature", "persona-appearance-feature"],
  ["habit_action", "persona-habit-action"],
  ["soul_goal", "persona-soul-goal"],
  ["hidden_desire", "persona-hidden-desire"],
  ["inner_conflict", "persona-inner-conflict"],
  ["self_cognition", "persona-self-cognition"],
  ["private_self", "persona-private-self"],
  ["core_traits", "persona-core-traits"],
  ["speech_style", "persona-speech-style"],
  ["cadence", "persona-cadence"],
  ["typical_lines", "persona-typical-lines"],
  ["signature_phrases", "persona-signature-phrases"],
  ["sentence_openers", "persona-sentence-openers"],
  ["sentence_endings", "persona-sentence-endings"],
  ["social_mode", "persona-social-mode"],
  ["thinking_style", "persona-thinking-style"],
  ["decision_rules", "persona-decision-rules"],
  ["reward_logic", "persona-reward-logic"],
  ["worldview", "persona-worldview"],
  ["belief_anchor", "persona-belief-anchor"],
  ["moral_bottom_line", "persona-moral-bottom-line"],
  ["restraint_threshold", "persona-restraint-threshold"],
  ["key_bonds", "persona-key-bonds"],
  ["preference_like", "persona-preference-like"],
  ["dislike_hate", "persona-dislike-hate"],
  ["forbidden_behaviors", "persona-forbidden-behaviors"],
  ["stress_response", "persona-stress-response"],
  ["emotion_model", "persona-emotion-model"],
  ["anger_style", "persona-anger-style"],
  ["joy_style", "persona-joy-style"],
  ["grievance_style", "persona-grievance-style"],
  ["others_impression", "persona-others-impression"],
];

const PERSONA_AUTOFILLABLE_FIELDS = new Set([
  "core_identity",
  "story_role",
  "identity_anchor",
  "temperament_type",
  "gender",
  "age_stage",
  "appearance_feature",
  "habit_action",
  "soul_goal",
  "hidden_desire",
  "inner_conflict",
  "self_cognition",
  "private_self",
  "core_traits",
  "speech_style",
  "social_mode",
  "thinking_style",
  "worldview",
  "belief_anchor",
  "moral_bottom_line",
  "key_bonds",
  "preference_like",
  "dislike_hate",
  "others_impression",
]);

const personaReviewAutofilledFields = new Set();

function fillPersonaReviewFields(fields) {
  personaReviewAutofilledFields.clear();
  clearAllPersonaReviewFieldFeedback();
  PERSONA_REVIEW_FIELD_BINDINGS.forEach(([field, id]) => {
    setValue(id, fields?.[field] || "");
  });
  syncPersonaReviewFieldHighlights();
  syncPersonaReviewAutofillButtons();
}

function renderPersonaAutofillReferences(payload) {
  currentPersonaAutofill = payload || null;
  const panel = el("persona-review-reference-panel");
  const summary = el("persona-review-reference-summary");
  const list = el("persona-review-reference-list");
  if (!panel || !summary || !list) return;
  const refs = Array.isArray(payload?.references) ? payload.references : [];
  panel.classList.toggle("hidden", refs.length === 0);
  panel.open = false;
  list.innerHTML = "";
  if (!refs.length) {
    summary.textContent = "网页摘要参考";
    return;
  }
  summary.textContent = `${refs.length} 条网页摘要参考`;
  refs.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "persona-reference-card";
    const title = escapeHtml(item?.title || `参考 ${index + 1}`);
    const snippet = escapeHtml(item?.snippet || "");
    const source = escapeHtml(item?.source || "");
    const query = escapeHtml(item?.query || "");
    card.innerHTML = `
      <div class="persona-reference-head">
        <strong>${title}</strong>
        ${source ? `<span>${source}</span>` : ""}
      </div>
      ${query ? `<p class="persona-reference-query">检索词：${query}</p>` : ""}
      ${snippet ? `<p class="persona-reference-snippet">${snippet}</p>` : ""}
    `;
    list.appendChild(card);
  });
  if (typeof publishLegacyUiState === "function") {
    publishLegacyUiState("persona-autofill-references-rendered");
  }
}

function personaReviewFieldId(field) {
  const item = PERSONA_REVIEW_FIELD_BINDINGS.find(([key]) => key === field);
  return item ? item[1] : "";
}

function personaReviewFieldValue(field) {
  const id = personaReviewFieldId(field);
  return id ? trimmedValue(id, "") : "";
}

function personaReviewFieldNeedsAutofill(field) {
  const value = personaReviewFieldValue(field);
  if (!value) return true;
  const normalized = value.replace(/\s+/g, "");
  return ["证据不足", "资料不足", "信息不足", "暂无资料", "暂缺", "待补充"].includes(normalized);
}

function setPersonaReviewFieldFeedback(field, kind = "", message = "") {
  const id = personaReviewFieldId(field);
  const input = id ? el(id) : null;
  const card = input?.closest(".field-card");
  if (!card) return;
  let note = card.querySelector(".persona-field-feedback");
  const text = String(message || "").trim();
  if (!text) {
    if (note) {
      note.remove();
    }
    card.classList.remove("field-card-feedback-loading", "field-card-feedback-success", "field-card-feedback-error");
    return;
  }
  if (!(note instanceof HTMLElement)) {
    note = document.createElement("p");
    note.className = "persona-field-feedback";
    card.appendChild(note);
  }
  note.textContent = text;
  card.classList.remove("field-card-feedback-loading", "field-card-feedback-success", "field-card-feedback-error");
  if (kind) {
    card.classList.add(`field-card-feedback-${kind}`);
  }
}

function clearAllPersonaReviewFieldFeedback() {
  PERSONA_REVIEW_FIELD_BINDINGS.forEach(([field]) => setPersonaReviewFieldFeedback(field, "", ""));
}

function markPersonaReviewFieldAutofilled(field) {
  if (!field) return;
  personaReviewAutofilledFields.add(field);
  syncPersonaReviewFieldHighlights();
}

function clearPersonaReviewFieldAutofilled(field) {
  if (!field) return;
  personaReviewAutofilledFields.delete(field);
  syncPersonaReviewFieldHighlights();
}

function clearAllPersonaReviewAutofilledFields() {
  personaReviewAutofilledFields.clear();
  syncPersonaReviewFieldHighlights();
}

function syncPersonaReviewFieldHighlights() {
  PERSONA_REVIEW_FIELD_BINDINGS.forEach(([field, id]) => {
    const input = el(id);
    const card = input?.closest(".field-card");
    if (!card) return;
    card.classList.toggle("field-card-autofilled", personaReviewAutofilledFields.has(field));
  });
}

function syncPersonaReviewAutofillButtons() {
  document.querySelectorAll("[data-persona-autofill-field]").forEach((node) => {
    const field = node.getAttribute("data-persona-autofill-field") || "";
    if (!(node instanceof HTMLButtonElement)) return;
    const shouldShow = PERSONA_AUTOFILLABLE_FIELDS.has(field) && personaReviewFieldNeedsAutofill(field);
    node.classList.toggle("hidden", !shouldShow);
    node.disabled = Boolean(node.dataset.loading === "true");
  });
}
