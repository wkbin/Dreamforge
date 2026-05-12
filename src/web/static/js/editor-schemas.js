(() => {
  const PERSONA_KEY_FIELDS = [
    { field: "core_identity", label: "核心身份", control: "input", autofill: true, required: true },
    { field: "story_role", label: "故事位置", control: "input", autofill: true, required: true },
    { field: "identity_anchor", label: "身份锚点", control: "input", autofill: true, required: true },
    { field: "temperament_type", label: "气质底色", control: "input", autofill: true, required: true },
    { field: "soul_goal", label: "灵魂目标", control: "textarea", autofill: true, required: true },
    { field: "core_traits", label: "核心特质", control: "textarea", autofill: true, required: true, placeholder: "用；分开" },
    { field: "key_bonds", label: "重要牵系", control: "textarea", autofill: true, required: true, placeholder: "用；分开" },
    { field: "speech_style", label: "说话方式", control: "textarea", autofill: true, required: true },
    { field: "worldview", label: "世界观", control: "textarea", autofill: true, required: true },
    { field: "belief_anchor", label: "信念支点", control: "textarea", autofill: true, required: true },
    { field: "moral_bottom_line", label: "道德底线", control: "textarea", autofill: true, required: true },
    { field: "restraint_threshold", label: "失控阈值", control: "textarea", autofill: false, required: false },
    { field: "stress_response", label: "应激反应", control: "textarea", autofill: false, required: false },
  ];

  const PERSONA_ADVANCED_GROUPS = [
    {
      title: "内核细调",
      copy: "这里放更细的心理、判断和外界观感，适合补齐人物的细腻层次。",
      selfCardCopy: "补齐更细的欲望、矛盾、判断方式和他人观感。",
      fields: [
        { field: "hidden_desire", label: "隐秘渴望", control: "textarea", autofill: true },
        { field: "inner_conflict", label: "内在冲突", control: "textarea", autofill: true },
        { field: "self_cognition", label: "自我认知", control: "textarea", autofill: true },
        { field: "private_self", label: "私下的一面", control: "textarea", autofill: true },
        { field: "thinking_style", label: "思考方式", control: "textarea", autofill: true },
        { field: "social_mode", label: "社交模式", control: "textarea", autofill: true },
        { field: "decision_rules", label: "决策规则", control: "textarea", autofill: false, placeholder: "用；分开" },
        { field: "reward_logic", label: "回报逻辑", control: "textarea", autofill: false },
        { field: "others_impression", label: "他人观感", control: "textarea", autofill: true },
      ],
    },
    {
      title: "对白细调",
      copy: "这些字段不一定适合联网补全，但很适合你直接手修出人物口气。",
      selfCardCopy: "这一层更适合手修，也能让“以自己入场”更像真的有声音。",
      fields: [
        { field: "cadence", label: "语句节奏", control: "input", autofill: false },
        { field: "sentence_endings", label: "句尾习惯", control: "input", autofill: false, placeholder: "用；分开" },
        { field: "sentence_openers", label: "起句习惯", control: "input", autofill: false, placeholder: "用；分开" },
        { field: "signature_phrases", label: "口头禅", control: "input", autofill: false, placeholder: "用；分开" },
        { field: "typical_lines", label: "代表句", control: "textarea", autofill: false, placeholder: "用；分开" },
      ],
    },
    {
      title: "情绪细调",
      copy: "这一层更偏细节表现。没有把握时宁可留空，也别强凹一套设定。",
      selfCardCopy: "这部分决定你在故事里的情绪展开方式。",
      fields: [
        { field: "forbidden_behaviors", label: "不会做的事", control: "textarea", autofill: false, placeholder: "用；分开" },
        { field: "emotion_model", label: "情绪底模", control: "textarea", autofill: false },
        { field: "anger_style", label: "发怒方式", control: "textarea", autofill: false },
        { field: "joy_style", label: "开心方式", control: "textarea", autofill: false },
        { field: "grievance_style", label: "委屈方式", control: "textarea", autofill: false },
      ],
    },
  ];

  const SELF_CARD_ENTRY_FIELDS = [
    { field: "display_name", label: "角色名", control: "input", required: true },
    { field: "scene_identity", label: "入场身份", control: "input", required: false, placeholder: "例如：借住府中的远亲；误入夜宴的来客" },
    { field: "interaction_style", label: "互动气氛", control: "input", required: false, placeholder: "例如：初见试探；夜谈；久别重逢；局中搅局" },
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

  function flattenFieldGroups(groups = []) {
    return groups.flatMap((group) => Array.isArray(group.fields) ? group.fields : []);
  }

  function fieldMapFrom(definitions = []) {
    return new Map(definitions.map((item) => [item.field, item]));
  }

  const PERSONA_ALL_FIELDS = [...PERSONA_KEY_FIELDS, ...flattenFieldGroups(PERSONA_ADVANCED_GROUPS)];
  const SELF_CARD_ALL_FIELDS = [...SELF_CARD_ENTRY_FIELDS, ...PERSONA_ALL_FIELDS];

  window.__ZAOMENG_EDITOR_SCHEMAS__ = {
    PERSONA_KEY_FIELDS,
    PERSONA_ADVANCED_GROUPS,
    PERSONA_ALL_FIELDS,
    PERSONA_FIELD_MAP: fieldMapFrom(PERSONA_ALL_FIELDS),
    SELF_CARD_ENTRY_FIELDS,
    SELF_CARD_REQUIRED_FIELDS,
    SELF_CARD_ALL_FIELDS,
    SELF_CARD_FIELD_MAP: fieldMapFrom(SELF_CARD_ALL_FIELDS),
  };
})();
