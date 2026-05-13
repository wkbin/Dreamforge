# 输出规范

## 人物档案

```md
# PROFILE
<!-- Canonical markdown profile storage. -->

## Meta
- name: 角色名
- novel_id: sample_novel
- source_path: data/sample_novel.txt
- timeline_stage: 前期 / 中期 / 后期 / 结局 / 未判定
- role_tags: 核心主角；悲剧型；群像核心

## Basic Positioning
- core_identity: 核心身份与社会定位
- gender: 性别或性别呈现；证据不足时写证据不足
- age_stage: 年龄阶段或年龄感；优先写少年 / 青年 / 中年 / 长者等稳定阶段
- faction_position: 阵营、派系、立场位置
- world_belong: 所属势力 / 地域 / 种族 / 阶层标签
- story_role: 剧情职能定位
- stance_stability: 立场稳定度或摇摆特性
- identity_anchor: 角色如何定义“我是谁、我站在哪边、我凭什么行动”
- world_rule_fit: 人物理念与世界规则的契合度
- rule_view: 对世界核心规则的接受 / 反抗 / 利用态度
- plot_restriction: 原作设定枷锁，如血脉、身份、宿命、制度、种族限制

## Root Layer
- background_imprint: 出身背景与成长烙印
- life_experience: 关键经历、转折与长期处境
- trauma_scar: 至今仍在起作用的旧伤与精神擦痕
- taboo_topics: 不能触碰的话题
- forbidden_behaviors: 明确不会做或极度排斥的行为

## Inner Core
- soul_goal: 长期驱动目标
- hidden_desire: 深层执念或隐秘欲望
- core_traits: 性格1；性格2
- temperament_type: 整体气质底色
- values: 勇气=0；智慧=0；善良=0；忠诚=0；野心=0；正义=0；自由=0；责任=0
- worldview: 对世界、秩序、善恶、因果的基本看法
- belief_anchor: 高压时仍会抓住的信念、规矩或精神支柱
- moral_bottom_line: 道德底线与不能跨过的红线
- restraint_threshold: 欲望、情绪、嫉妒、愤怒平时如何克制，何时会失控

## External Persona
- appearance_feature: 标志性长相、穿着、体态、器物或可识别外观
- habit_action: 无意识小动作、口癖外的小习惯、微行为
- preference_like: 偏好的人、物、食物、作息、环境或氛围
- dislike_hate: 生理性厌恶、本能排斥、长期反感的对象或状态

## Interest And Resources
- interest_claim: 核心利益诉求，如权、财、地位、自由、传承、安全感
- resource_dependence: 依赖的资源、软肋筹码、容易被拿捏的关键点
- trade_principle: 利益交换底线，以及合作 / 背叛的触发条件

## Value And Conflict
- inner_conflict: 理念、责任、欲望之间的内在冲突
- self_cognition: 角色如何看待自己，如清醒、自卑、高估、偏执
- private_self: 不轻易示人的柔软面、阴暗面或真实隐藏面
- disguise_switch: 是否存在假面人格、演戏状态，以及何时切换

## Thinking And Decision
- thinking_style: 理性 / 感性、短视 / 长远、经验驱动 / 直觉驱动等思维偏好
- cognitive_limits: 认知盲区、思维短板、反复犯错的局限
- decision_rules: 条件 -> 反应；固定决策准则
- action_style: 执行方式、推进节奏、惯用手段
- reward_logic: 角色如何判断谁值得回报、谁该惩罚、何时翻脸、何时让步

## Emotion And Stress
- emotion_model: 日常情绪基调与主要调节方式
- fear_triggers: 恐惧点、雷点、避讳触发项
- stress_response: 高压、绝境、崩溃边缘时的应激人格
- anger_style: 生气时的表达方式
- joy_style: 开心时的表达方式
- grievance_style: 委屈、受压时的表达方式

## Social Pattern
- social_mode: 社交距离与相处模式
- carry_style: 对陌生人 / 亲友 / 上级 / 下属 / 敌人的分层态度
- others_impression: 他人观感、外界标签、第一印象
- key_bonds: 关键羁绊、宿命联系、关系落点

## Voice
- speech_style: 说话风格总述
- cadence: 语气节奏
- signature_phrases: 标志性句式、口头禅
- typical_lines: 代表性台词或高辨识表达
- sentence_openers: 常见起句（可选）
- connective_tokens: 常用连接词（可选）
- sentence_endings: 常见收尾方式（可选）
- forbidden_fillers: 禁用口水词、禁用通用助词（可选）

## Capability
- strengths: 专属优势、能力强项
- weaknesses: 性格短板、能力缺陷、致命弱点

## Arc
- arc_type: 成长类型，如觉醒、救赎、黑化、麻木、堕落、和解
- arc_blocker: 阻碍人物变化的核心心结
- arc_start: 前段稳定状态
- arc_mid: 中段变化与触发事件
- arc_end: 当前可见终点或结局状态

## Performance Boundary
- ooc_redline: 绝对不能捏造给该角色的 OOC 行为清单

## Evidence
- description_count: 1
- dialogue_count: 2
- thought_count: 0
- chunk_count: 1
- evidence_source: 第03回-段落12；第05回-段落03
- contradiction_note: 前期偏克制，后期在特定关系中明显失控，需按时间线区分
```

规则：
- `core_traits` max 10 unique items
- `typical_lines` max 8 unique items
- `decision_rules` max 8 unique items
- list-like fields use `；` as the separator in markdown scalar lines
- `values` all integers in `[0,10]`
- evidence fields优先存索引、章节、段落编号，不复制大段原文
- `sentence_openers` / `connective_tokens` / `sentence_endings` / `forbidden_fillers` 为可选字段，无稳定证据时留空
- 任意高风险深层字段若证据不足，允许直接写 `证据不足`
- `arc_start` / `arc_mid` / `arc_end` 只有在识别到稳定阶段变化时才量化；证据不足时可保留空值或只写 `trigger_event` / `final_state` 类说明

### 统一标尺

- 0 = 完全无 / 极致排斥
- 5 = 中立普通 / 无明显偏向
- 10 = 极致执念 / 完全忠诚 / 彻底坚守

### 易混字段收紧定义

- `core_identity`: 只写客观身份与社会定位，例如公子、管家者、宗门继承人；不要把剧情功能或主观宣言塞进来。
- `story_role`: 只写角色在剧情里承担的职能，例如事件推进者、局面维持者、矛盾引爆点；不要重复 `core_identity`。
- `identity_anchor`: 角色如何定义“我是谁、我站在哪边、我凭什么行动”。必须是该角色自己的自我定位，不是团队口号。
- `soul_goal`: 长期驱动力或执念，必须能解释关键选择中反复追求什么，禁止使用“活下去”“赢下来”“保护同伴”这类任何人都适用的空泛目标。
- `background_imprint`: 对当前人格与决策有持续影响的出身、成长、代价与烙印，不得把多人共场景的剧情摘要直接搬过来。
- `trauma_scar`: 不是“悲惨经历简介”，而是至今仍在影响其反应方式的旧伤。
- `temperament_type`: 强调整体气质底色，要能一眼区分人物，不是把 `core_traits` 换词重写。
- `rule_view`: 写人物面对世界规则时是顺从、利用、怀疑、反抗还是借势，而不是重复 `world_rule_fit`。
- `plot_restriction`: 写原作设定层面的束缚，例如身份、制度、血脉、宿命、誓约、种族限制。
- `gender`: 只能依据正文稳定称谓、亲属关系、辈分或明确描写判断；不能按名字印象、二创常识或影视印象脑补。
- `age_stage`: 优先写年龄阶段或年龄感，如少年、青年、中年、长者；除非原文明确，不要硬写具体年龄。
- `appearance_feature`: 只写原文稳定可见的外在标识，不凭空补完影视化细节。
- `habit_action`: 写能在多次互动中观察到的习惯动作，不写一次性动作描写。
- `interest_claim`: 写角色真正在争夺什么、守住什么，而不是泛泛而谈“想变强”。
- `resource_dependence`: 写其依赖、短缺、害怕失去或会被控制的关键资源与筹码。
- `trade_principle`: 写利益交换与合作背叛的底线条件，不与 `reward_logic` 混写。
- `inner_conflict`: 只写内在冲突，不承担自评或隐藏面职能。
- `self_cognition`: 只写角色如何看自己，可与 `others_impression` 形成反差，但两者都必须有证据。
- `private_self`: 保留原字段名用于兼容，语义按“hidden_side”理解，写不对外展示的真实面与隐蔽面。
- `action_style`: 只写怎么做；`decision_rules` 只写为什么选。
- `stress_response`: 必须描述高压、绝境、崩溃边缘时的异常面，而不是重复日常 `action_style`。
- `carry_style`: 写其对不同关系层级的差异化态度，不得用一个“对人冷淡”打包全部对象。
- `ooc_redline`: 只写绝对不能虚构给该角色的行为边界，优先写背叛、失格、自毁、违背设定底线的行为。

### 原作优先原则

- 只采信原作正文中的描写、行为、对话、心理活动与明确叙述。
- 拒绝二创、同人、读者脑补、影视改编附会与“合理推测式补全”。
- 无原文支撑时直接写 `证据不足`，不要用常识补完。

### 人设权重规则

- 长期稳定性格 > 一时情绪冲动行为
- 核心底色 > 阶段性反常行为
- 童年 / 成长烙印 > 临时环境刺激
- 结论若受时间线影响，必须配合 `timeline_stage` 或 `contradiction_note` 说明

### 公平蒸馏规则

- 对反派、灰色人物、失败者一律客观记录其逻辑、创伤、欲望、利益与边界
- 不洗白，不丑化，不做道德审判式总结

### 多角色蒸馏约束

- 一次同时蒸馏多名角色时，每个角色必须被当作独立任务处理。
- 必须明确回答“这个角色与同批其他角色最不同的地方是什么”。
- 共享场景优先用于提取 `key_bonds`、关系变化、冲突点与互动节奏，不得直接批量写入多人共同的背景与人格字段。
- 若某字段与其他角色高度雷同且缺少更强证据，应留空或写 `证据不足`，不要用模板话术填满。

### 推荐字段分组

为避免录入时重复堆叠同义字段，推荐按以下 14 组理解与填写：

1. 基础身份定位：`core_identity` / `faction_position` / `world_belong` / `story_role` / `stance_stability` / `identity_anchor`
2. 世界观绑定：`world_rule_fit` / `rule_view` / `plot_restriction`
3. 根源底层：`background_imprint` / `life_experience` / `trauma_scar` / `taboo_topics` / `forbidden_behaviors`
4. 核心精神内核：`soul_goal` / `hidden_desire` / `core_traits` / `temperament_type` / `values` / `worldview` / `belief_anchor` / `moral_bottom_line` / `restraint_threshold`
5. 外在具象人设：`appearance_feature` / `habit_action` / `preference_like` / `dislike_hate`
6. 利益与资源逻辑：`interest_claim` / `resource_dependence` / `trade_principle`
7. 价值与内在矛盾：`inner_conflict` / `self_cognition` / `private_self` / `disguise_switch`
8. 思维与决策：`thinking_style` / `cognitive_limits` / `decision_rules` / `action_style` / `reward_logic`
9. 情绪与应激：`emotion_model` / `fear_triggers` / `stress_response` / `anger_style` / `joy_style` / `grievance_style`
10. 社交模式：`social_mode` / `carry_style` / `others_impression` / `key_bonds`
11. 语言表达：`speech_style` / `cadence` / `signature_phrases` / `typical_lines`
12. 可选语言微特征：`sentence_openers` / `connective_tokens` / `sentence_endings` / `forbidden_fillers`
13. 能力与短板：`strengths` / `weaknesses`
14. 成长与边界：`timeline_stage` / `role_tags` / `arc_type` / `arc_blocker` / `arc_start` / `arc_mid` / `arc_end` / `ooc_redline` / `evidence_source` / `contradiction_note`

## 人格包文件

蒸馏过程还可以在以下目录下生成可选人格包：

```text
runtime/data/characters/<novel_id>/<角色名>/
```

常见文件：
- `NAVIGATION.generated.md`: generated load order and file intent
- `NAVIGATION.md`: manual override and navigation supplement
- `PROFILE.generated.md`: canonical generated profile
- `PROFILE.md`: manual override profile
- `RELATIONS.generated.md`: generated target-specific relations
- `RELATIONS.md`: manual relation overrides
- `MEMORY.md`: durable memory and user corrections

可选的聚焦人格文件：
- `SOUL.generated.md`
- `GOALS.generated.md`
- `STYLE.generated.md`
- `TRAUMA.generated.md`
- `IDENTITY.generated.md`
- `BACKGROUND.generated.md`
- `CAPABILITY.generated.md`
- `BONDS.generated.md`
- `CONFLICTS.generated.md`
- `ROLE.generated.md`

## 关系图谱

```md
# RELATION_GRAPH

## 林黛玉_贾宝玉
- trust: 8
- affection: 9
- power_gap: 1
- conflict_point: 表达方式差异
- typical_interaction: 黛玉试探 -> 宝玉安抚 -> 短暂缓和
- hidden_attitude: 表面克制，私下更在意对方是否偏心
- relation_change: 缓慢升温，但受误会反复波动
- appellation_to_target: 宝玉
- confidence: 8
```

规则：
- relation section title must use sorted key format `<A>_<B>`
- `trust` and `affection` in `[0,10]`
- `power_gap` in `[-5,5]`
- `confidence` in `[0,10]`
- `relation_change` 描述趋势，如升温、恶化、固化、反复波动
- `hidden_attitude` 用于记录表面态度与私下真实态度的落差；无证据时留空
- 关系条目必须基于同场景互动证据

## 聊天约束（可选）

```md
# CHAT_CONSTRAINTS

- character: 林黛玉
- must_follow: 语气克制但可反讽；冲突时先防御再观察
- must_avoid: 无证据的极端背叛表达；与高忠诚价值冲突的抛弃宣言
- fallback_action: rewrite_once_then_needs_revision
```

## 纠错输出

```md
# CORRECTION

- corrected_message: 修正后的台词
- correction_reason: 基于哪些人格字段收紧
- confidence: 7
```
