(() => {
  const PERSONA_KEY_FIELDS = [
    { field: "core_identity", label: "核心身份", control: "input", autofill: true, required: true, hint: "写客观身份和社会定位，不写剧情职能。" },
    { field: "identity_anchor", label: "身份锚点", control: "input", autofill: true, required: true, hint: "写他主观上怎么定义自己、怎么站位。" },
    { field: "temperament_type", label: "气质底色", control: "input", autofill: true, required: true, hint: "先写整体气口，不要堆很多形容词。" },
    { field: "gender", label: "性别", control: "input", autofill: true, required: true, placeholder: "例如：女性；男性；不明", hint: "只写正文能稳定判断的性别或呈现。" },
    { field: "age_stage", label: "年龄阶段", control: "input", autofill: true, required: true, placeholder: "例如：豆蔻少女；弱冠前后；青年", hint: "优先写年龄感和阶段，不强求具体岁数。" },
    { field: "appearance_feature", label: "外貌辨识", control: "textarea", autofill: true, required: true, hint: "写一眼能认出的外形、穿着、体态或器物。" },
    { field: "habit_action", label: "习惯动作", control: "textarea", autofill: true, required: true, hint: "写会反复出现的小动作，不写一次性剧情动作。" },
    { field: "soul_goal", label: "灵魂目标", control: "textarea", autofill: true, required: true, hint: "他长期真正想守住或得到什么。" },
    { field: "core_traits", label: "核心特质", control: "textarea", autofill: true, required: true, placeholder: "用；分开", hint: "挑 2-4 个最能区分他的性格词就够了。" },
    { field: "key_bonds", label: "重要牵系", control: "textarea", autofill: true, required: true, placeholder: "用；分开", hint: "写最牵动他的关系对象或关系落点。" },
    { field: "speech_style", label: "说话方式", control: "textarea", autofill: true, required: true, hint: "尽量写出句子手感，不只写抽象性格。" },
    { field: "worldview", label: "世界观", control: "textarea", autofill: true, required: true, hint: "他怎么看人情、秩序、得失和善恶。" },
  ];

  const PERSONA_ADVANCED_GROUPS = [
    {
      title: "定位与外显",
      copy: "把故事站位、社交外观和生活偏好收在这里，避免关键层一上来堆得太满。",
      selfCardCopy: "这里补的是角色在场时最容易被别人感受到的一层。",
      fields: [
        { field: "story_role", label: "故事位置", control: "input", autofill: true, hint: "写他在剧情里承担什么职能，不是身份头衔。" },
        { field: "social_mode", label: "社交模式", control: "textarea", autofill: true },
        { field: "others_impression", label: "他人观感", control: "textarea", autofill: true },
        { field: "preference_like", label: "偏好喜好", control: "textarea", autofill: true, placeholder: "用；分开" },
        { field: "dislike_hate", label: "明显厌恶", control: "textarea", autofill: true, placeholder: "用；分开" },
      ],
    },
    {
      title: "内核细调",
      copy: "这里放更细的心理、判断与底层驱动，适合补齐人物的内在逻辑。",
      selfCardCopy: "补齐更细的欲望、矛盾、判断方式和底线支点。",
      fields: [
        { field: "hidden_desire", label: "隐秘渴望", control: "textarea", autofill: true, hint: "写不轻易说出口、但一直在牵动他的欲望。" },
        { field: "inner_conflict", label: "内在冲突", control: "textarea", autofill: true, hint: "只写拉扯和矛盾，不写自评和隐藏面。" },
        { field: "self_cognition", label: "自我认知", control: "textarea", autofill: true, hint: "只写他怎么看自己，可与他人观感形成反差。" },
        { field: "private_self", label: "私下的一面", control: "textarea", autofill: true, hint: "写不对外展示的一面，不要重复内在冲突。" },
        { field: "thinking_style", label: "思考方式", control: "textarea", autofill: true },
        { field: "decision_rules", label: "决策规则", control: "textarea", autofill: false, placeholder: "用；分开" },
        { field: "reward_logic", label: "回报逻辑", control: "textarea", autofill: false },
        { field: "belief_anchor", label: "信念支点", control: "textarea", autofill: true },
        { field: "moral_bottom_line", label: "道德底线", control: "textarea", autofill: true },
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
      copy: "这一层更偏情绪展开与边界控制。没有把握时宁可留空，也别强凹一套设定。",
      selfCardCopy: "这部分决定你在故事里的情绪展开方式和失控边界。",
      fields: [
        { field: "forbidden_behaviors", label: "不会做的事", control: "textarea", autofill: false, placeholder: "用；分开" },
        { field: "restraint_threshold", label: "失控阈值", control: "textarea", autofill: false },
        { field: "stress_response", label: "应激反应", control: "textarea", autofill: false },
        { field: "emotion_model", label: "情绪底模", control: "textarea", autofill: false },
        { field: "anger_style", label: "发怒方式", control: "textarea", autofill: false },
        { field: "joy_style", label: "开心方式", control: "textarea", autofill: false },
        { field: "grievance_style", label: "委屈方式", control: "textarea", autofill: false },
      ],
    },
  ];

  const SELF_CARD_ENTRY_FIELDS = [
    { field: "display_name", label: "角色名", control: "input", required: true, hint: "别人会怎么称呼你，尽量简短好叫。" },
    { field: "scene_identity", label: "入场身份", control: "input", required: false, placeholder: "例如：借住府中的远亲；误入夜宴的来客", hint: "写你在这场故事里以什么身份走进来。" },
    { field: "interaction_style", label: "互动气氛", control: "input", required: false, placeholder: "例如：初见试探；夜谈；久别重逢；局中搅局", hint: "决定这张卡更适合什么样的相处手感。" },
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

  const SCENE_CARD_FIELDS = [
    { field: "title", label: "场景名", control: "input", required: true, placeholder: "例如：雨夜探院；花厅夜宴；船舫对坐" },
    { field: "time_hint", label: "时间提示", control: "input", required: false, placeholder: "例如：上元夜；雨后傍晚；三更将尽" },
    { field: "location", label: "地点", control: "input", required: true, placeholder: "例如：荣府偏厅；临河船舫；后园回廊" },
    { field: "atmosphere", label: "场面气氛", control: "input", required: true, placeholder: "例如：表面松弛，暗地试探" },
    { field: "opening_situation", label: "开场局面", control: "textarea", required: true },
    { field: "public_goal", label: "明面目标", control: "textarea", required: false },
    { field: "hidden_tension", label: "暗线张力", control: "textarea", required: false },
    { field: "scene_drive", label: "推进方向", control: "textarea", required: true },
    { field: "expected_rhythm", label: "节奏手感", control: "input", required: false, placeholder: "例如：慢热试探；三句一推进；越聊越绷紧" },
    { field: "forbidden_topics", label: "不想碰的话头", control: "textarea", required: false, placeholder: "用；分开" },
  ];

  const SCENE_CARD_REQUIRED_FIELDS = ["title", "location", "atmosphere", "opening_situation", "scene_drive"];

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
    SCENE_CARD_FIELDS,
    SCENE_CARD_REQUIRED_FIELDS,
    SCENE_CARD_FIELD_MAP: fieldMapFrom(SCENE_CARD_FIELDS),
    SELF_CARD_ENTRY_FIELDS,
    SELF_CARD_REQUIRED_FIELDS,
    SELF_CARD_ALL_FIELDS,
    SELF_CARD_FIELD_MAP: fieldMapFrom(SELF_CARD_ALL_FIELDS),
  };
})();
