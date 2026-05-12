(() => {
  const vue = window.Vue;
  if (!vue) {
    return;
  }

  const SchemaFieldCard = {
    props: {
      item: { type: Object, required: true },
      modelValue: { type: String, default: "" },
      feedback: { type: Object, default: null },
      autofillEnabled: { type: Boolean, default: false },
      autofillField: { type: String, default: "" },
      needsAutofill: { type: Function, default: null },
    },
    emits: ["update:modelValue", "autofill"],
    computed: {
      showAutofill() {
        if (!this.autofillEnabled || !this.item?.autofill) return false;
        if (typeof this.needsAutofill !== "function") return true;
        return Boolean(this.needsAutofill(this.item.field));
      },
      isAutofilling() {
        return this.autofillField === this.item?.field;
      },
    },
    template: `
      <label class="field-card">
        <div class="field-card-head">
          <span>{{ item.label }}</span>
          <button
            v-if="item.autofill"
            type="button"
            class="inline-assist-button"
            :class="{ hidden: !showAutofill }"
            :disabled="isAutofilling"
            @click="$emit('autofill', item.field)"
          >
            {{ isAutofilling ? '生成中...' : 'AI补全' }}
          </button>
        </div>
        <input
          v-if="item.control === 'input'"
          :value="modelValue || ''"
          type="text"
          :placeholder="item.placeholder || ''"
          @input="$emit('update:modelValue', $event.target.value)"
        />
        <textarea
          v-else
          :value="modelValue || ''"
          rows="2"
          :placeholder="item.placeholder || ''"
          @input="$emit('update:modelValue', $event.target.value)"
        ></textarea>
        <small v-if="feedback" class="persona-field-feedback" :data-kind="feedback.kind">
          {{ feedback.message }}
        </small>
      </label>
    `,
  };

  window.__ZAOMENG_EDITOR_VUE_COMPONENTS__ = {
    SchemaFieldCard,
  };
})();
