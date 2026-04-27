# 人物档案蒸馏提示词

## 任务

从分段小说原文中，蒸馏结构化、通用化、可落盘的人物心智档案。

## 输入

- 小说文本片段
- 候选人物列表（可选）
- 已有修正记录或用户补充（可选）

## 输出

- 严格遵循 `references/output_schema.md` 的 Markdown 人物档案
- 优先产出 `PROFILE.generated.md`
- 如信息足够，可同步支持导航内的可选人格文件拆分：`SOUL`、`GOALS`、`STYLE`、`TRAUMA`、`IDENTITY`、`BACKGROUND`、`CAPABILITY`、`BONDS`、`CONFLICTS`、`ROLE`

## 26 维度覆盖要求

输出时必须尽量覆盖以下 26 个蒸馏维度；若原文证据不足，可留空、降置信度或明确写成“证据不足”，但禁止脑补：

1. 核心身份
2. 核心动机
3. 性格基底
4. 行为逻辑
5. 人物弧光
6. 关键羁绊
7. 符号化特征
8. 世界观适配性
9. 价值取舍体系
10. 情绪反应模式
11. 思维认知偏好
12. 语言表达特质
13. 专属能力与致命短板
14. 出身背景与生存处境
15. 深层执念与隐秘欲望
16. 行事风格倾向
17. 过往创伤与人生烙印
18. 社交相处模式
19. 内在自我矛盾
20. 剧情职能定位
21. 恐惧与避讳事物
22. 信仰与精神支柱
23. 认知局限与成长短板
24. 立场摇摆特性
25. 恩怨奖惩逻辑
26. 私下真实面貌

## 字段映射约束

将上面的 26 维度尽量映射到当前 Markdown 档案字段中：

- 核心身份 -> `core_identity`、`faction_position`、`story_role`
- 核心动机 -> `soul_goal`、`hidden_desire`
- 性格基底 -> `core_traits`、`values`
- 行为逻辑 -> `decision_rules`、`action_style`、`reward_logic`
- 人物弧光 -> `arc_start`、`arc_mid`、`arc_end`
- 关键羁绊 -> `key_bonds`
- 符号化特征 -> `typical_lines`、`signature_phrases`、`sentence_openers`、`sentence_endings`
- 世界观适配性 -> `world_rule_fit`
- 价值取舍体系 -> `values`、`belief_anchor`、`worldview`
- 情绪反应模式 -> `anger_style`、`joy_style`、`grievance_style`、`fear_triggers`
- 思维认知偏好 -> `thinking_style`、`cognitive_limits`
- 语言表达特质 -> `speech_style`、`cadence`、`connective_tokens`、`forbidden_fillers`
- 专属能力与致命短板 -> `strengths`、`weaknesses`
- 出身背景与生存处境 -> `background_imprint`、`life_experience`
- 深层执念与隐秘欲望 -> `hidden_desire`
- 行事风格倾向 -> `action_style`
- 过往创伤与人生烙印 -> `background_imprint`、`taboo_topics`
- 社交相处模式 -> `social_mode`
- 内在自我矛盾 -> `inner_conflict`
- 剧情职能定位 -> `story_role`
- 恐惧与避讳事物 -> `fear_triggers`、`taboo_topics`、`forbidden_behaviors`
- 信仰与精神支柱 -> `belief_anchor`
- 认知局限与成长短板 -> `cognitive_limits`、`weaknesses`
- 立场摇摆特性 -> `stance_stability`
- 恩怨奖惩逻辑 -> `reward_logic`
- 私下真实面貌 -> `private_self`

## 规则

1. 只提取原文有直接依据的内容，禁止编造、脑补、过度解读。
2. 所有量化分值必须使用整数；`values` 维持 `0–10` 区间。
3. 若文本内人物线索稀少、证据薄弱，降低整体置信度，并在相关字段保持克制。
4. `core_traits`、`typical_lines`、`decision_rules`、`strengths`、`weaknesses`、`fear_triggers` 等列表必须自动去重，避免同义重复。
5. 全程使用通用描述逻辑，不绑定单本小说专属黑话、专属 archetype 标签或作品内私有名词模板。
6. 若某维度无法被当前片段支持，不要用“常识”补全；保持空值或保守概括即可。
7. 人物弧光必须基于当前可见片段；若不足以判断成长变化，明确按“静态人物 / 当前片段不足以判断弧光”处理。
8. 语言表达特质必须来自说话内容、叙述描写或稳定互动习惯，不能套用万能“冷静、理智、温和”模板。
9. 对深层执念、私下真实面貌、内在冲突等高风险维度，宁缺毋滥，优先短句事实总结。
10. 如果输入中包含用户纠正或长期修正记录，应把它们视为高优先级约束，但不得覆盖原文中明确相反的硬证据。
