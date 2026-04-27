# 输出规范

## 人物档案

```md
# PROFILE
<!-- Canonical markdown profile storage. -->

## Meta
- name: 角色名
- novel_id: sample_novel
- source_path: data/sample_novel.txt

## Core
- core_traits: 性格1；性格2
- values: 勇气=0；智慧=0；善良=0；忠诚=0；野心=0；正义=0；自由=0；责任=0
- speech_style: 语言风格描述
- identity_anchor: 角色在世界中的自我定位
- soul_goal: 长期驱动目标
- worldview: 对世界、规则、善恶、秩序的基本看法
- thinking_style: 理性/感性/短视/长远等思考偏好

## Deep Persona
- core_identity: 核心身份与定位
- faction_position: 阵营、派系、立场位置
- background_imprint: 出身背景与成长烙印
- world_rule_fit: 人物理念与世界观规则的契合度描述
- social_mode: 社交距离与相处模式
- hidden_desire: 深层执念或隐秘欲望
- inner_conflict: 内在矛盾
- story_role: 剧情职能定位
- belief_anchor: 信仰与精神支柱
- private_self: 私下真实面貌
- stance_stability: 立场稳定度或摇摆特性
- reward_logic: 恩怨奖惩逻辑
- strengths: 专属能力；擅长项
- weaknesses: 性格缺陷；明显短板
- cognitive_limits: 认知盲区；成长短板
- fear_triggers: 恐惧点；雷点；避讳触发项
- key_bonds: 关键羁绊；宿命联结
- action_style: 行事风格倾向

## Voice
- typical_lines: 代表性台词；高辨识表达
- decision_rules: 条件->反应；固定决策准则
- life_experience: 关键经历；过往创伤；人生烙印
- taboo_topics: 不能触碰的话题
- forbidden_behaviors: 绝不会做的行为
- cadence: 说话节奏
- signature_phrases: 专属口头禅；标志句式
- sentence_openers: 常见起句
- connective_tokens: 常用连接词
- sentence_endings: 常见收尾方式
- forbidden_fillers: 禁用口水词；禁用通用助词
- anger_style: 生气时的表达方式
- joy_style: 开心时的表达方式
- grievance_style: 委屈/受压时的表达方式

## Arc
- arc_start: 勇气=5；立场=6
- arc_mid: 勇气=6；trigger_event=事件
- arc_end: 勇气=7；final_state=状态

## Evidence
- description_count: 1
- dialogue_count: 2
- thought_count: 0
- chunk_count: 1
```

规则：

- `core_traits` max 10 unique items
- `typical_lines` max 8 unique items
- `decision_rules` max 8 unique items
- list-like fields use `；` as the separator in markdown scalar lines
- `values` all integers in `[0,10]`
- evidence fields store counts, not raw text arrays
- any deep persona field without solid evidence may stay empty
- `arc_start` / `arc_mid` / `arc_end` 只有在识别到稳定阶段变化时才应量化；若证据不足，应留空或仅保留 `trigger_event` / `final_state` 的未判定说明

### 26 维度覆盖映射

当前这套 Markdown 结构应尽量覆盖以下 26 个人格维度：

1. 核心身份 -> `core_identity` / `faction_position` / `story_role`
2. 核心动机 -> `soul_goal` / `hidden_desire`
3. 性格基底 -> `core_traits` / `values`
4. 行为逻辑 -> `decision_rules` / `action_style` / `reward_logic`
5. 人物弧光 -> `arc_start` / `arc_mid` / `arc_end`
6. 关键羁绊 -> `key_bonds`
7. 符号化特征 -> `typical_lines` / `signature_phrases` / `sentence_openers` / `sentence_endings`
8. 世界观适配性 -> `world_rule_fit`
9. 价值取舍体系 -> `values` / `belief_anchor` / `worldview`
10. 情绪反应模式 -> `anger_style` / `joy_style` / `grievance_style` / `fear_triggers`
11. 思维认知偏好 -> `thinking_style` / `cognitive_limits`
12. 语言表达特质 -> `speech_style` / `cadence` / `connective_tokens`
13. 专属能力与致命短板 -> `strengths` / `weaknesses`
14. 出身背景与生存处境 -> `background_imprint` / `life_experience`
15. 深层执念与隐秘欲望 -> `hidden_desire`
16. 行事风格倾向 -> `action_style`
17. 过往创伤与人生烙印 -> `background_imprint` / `life_experience` / `taboo_topics`
18. 社交相处模式 -> `social_mode`
19. 内在自我矛盾 -> `inner_conflict`
20. 剧情职能定位 -> `story_role`
21. 恐惧与避讳事物 -> `fear_triggers` / `taboo_topics` / `forbidden_behaviors`
22. 信仰与精神支柱 -> `belief_anchor`
23. 认知局限与成长短板 -> `cognitive_limits` / `weaknesses`
24. 立场摇摆特性 -> `stance_stability`
25. 恩怨奖惩逻辑 -> `reward_logic`
26. 私下真实面貌 -> `private_self`

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
- typical_interaction: 黛玉质问->宝玉安抚->短暂缓和
- appellation_to_target: 宝玉
- confidence: 8
```

规则：

- relation section title must use sorted key format `<A>_<B>`
- `trust` and `affection` in `[0,10]`
- `power_gap` in `[-5,5]`
- `confidence` in `[0,10]`
- 关系条目必须基于同场景互动证据

## 聊天约束（可选）

```md
# CHAT_CONSTRAINTS

- character: 林黛玉
- must_follow: 语气克制但可反讽；冲突时先防御再观察
- must_avoid: 无证据的极端背叛表述；与高忠诚值冲突的抛弃宣言
- fallback_action: rewrite_once_then_needs_revision
```

## 纠错输出

```md
# CORRECTION

- corrected_message: 修正后的台词
- correction_reason: 基于哪些人格字段收紧
- confidence: 7
```
