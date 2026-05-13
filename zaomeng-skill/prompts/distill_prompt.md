# 人物档案蒸馏提示词

## 任务

从分段小说正文中蒸馏结构化、可落盘、可用于后续对话演绎的人物档案。

## 输入

- 小说文本片段
- 候选人物列表（可选）
- 增量蒸馏上下文：`request.update_mode`、`request.existing_profiles`（可选）
- 已有纠错记录或用户补充（可选）
- 可选的角色专属收紧文件 `rules/character_hints/<novel_id>.md`（若存在）

## 输出

- 严格遵循 `references/output_schema.md` 的 Markdown 人物档案
- 优先产出 `PROFILE.generated.md`
- 信息足够时，可同步拆分生成 `SOUL`、`GOALS`、`STYLE`、`TRAUMA`、`IDENTITY`、`BACKGROUND`、`CAPABILITY`、`BONDS`、`CONFLICTS`、`ROLE`

## 覆盖要求

输出时优先覆盖以下字段组；证据不足时允许留空或直接写 `证据不足`，禁止脑补：

1. 基础身份定位：`core_identity`、`faction_position`、`world_belong`、`story_role`、`stance_stability`、`identity_anchor`
2. 世界观绑定：`world_rule_fit`、`rule_view`、`plot_restriction`
3. 根源底层：`background_imprint`、`life_experience`、`trauma_scar`、`taboo_topics`、`forbidden_behaviors`
4. 核心精神内核：`soul_goal`、`hidden_desire`、`core_traits`、`temperament_type`、`values`、`worldview`、`belief_anchor`、`moral_bottom_line`、`restraint_threshold`
5. 外在具象人设：`gender`、`age_stage`、`appearance_feature`、`habit_action`、`preference_like`、`dislike_hate`
6. 利益与资源逻辑：`interest_claim`、`resource_dependence`、`trade_principle`
7. 价值与内在矛盾：`inner_conflict`、`self_cognition`、`private_self`、`disguise_switch`
8. 思维与决策：`thinking_style`、`cognitive_limits`、`decision_rules`、`action_style`、`reward_logic`
9. 情绪与应激：`emotion_model`、`fear_triggers`、`stress_response`、`anger_style`、`joy_style`、`grievance_style`
10. 社交模式：`social_mode`、`carry_style`、`others_impression`、`key_bonds`
11. 语言表达：`speech_style`、`cadence`、`signature_phrases`、`typical_lines`
12. 可选语言微特征：`sentence_openers`、`connective_tokens`、`sentence_endings`、`forbidden_fillers`
13. 能力与短板：`strengths`、`weaknesses`
14. 成长与边界：`timeline_stage`、`role_tags`、`arc_type`、`arc_blocker`、`arc_start`、`arc_mid`、`arc_end`、`ooc_redline`
15. 证据与矛盾记录：`description_count`、`dialogue_count`、`thought_count`、`chunk_count`、`evidence_source`、`contradiction_note`

## 规则

1. 只提取原作正文有直接依据的内容，禁止编造、脑补、用同人设定补全。
2. 所有量化分值必须使用整数；`values` 统一使用 `0-10` 标尺。
3. 标尺含义统一为：`0 = 完全无 / 极致排斥`，`5 = 中立普通`，`10 = 极致执念 / 完全忠诚 / 彻底坚守`。
4. 长期稳定性格高于一时冲动行为；核心底色高于阶段性反常；童年与成长烙印高于临时环境刺激。
5. 若人物前后变化明显，必须配合 `timeline_stage`、`arc_*` 或 `contradiction_note` 区分，不得把后期状态强压到前期。
6. `core_traits`、`typical_lines`、`decision_rules`、`strengths`、`weaknesses`、`fear_triggers` 等列表必须去重，避免同义反复。
7. `gender`、`age_stage` 只能根据正文稳定证据来写，例如称谓、辈分、年龄序列、亲属关系、明确外貌年龄描写；拿不准就写 `证据不足`。
8. `appearance_feature` 只写原文稳定可见外在标识，不补影视化细节；`habit_action` 只写可重复观察到的小动作，不写一次性动作。
9. `interest_claim`、`resource_dependence`、`trade_principle` 必须具体到该角色真正争夺、依赖、交换什么，禁止泛化成“想变强”“重利益”。
10. `inner_conflict`、`self_cognition`、`private_self` 要分工明确：前者写冲突，中者写自评，后者写隐藏面。
11. `decision_rules` 只写“为什么选”；`action_style` 只写“怎么做”。
12. `sentence_openers`、`connective_tokens`、`sentence_endings`、`forbidden_fillers` 是可选字段；没有稳定语言证据时留空，不要为了凑满而硬填。
13. `ooc_redline` 只写绝对不能虚构给该角色的行为边界，优先写背叛、自毁、失格、明显违背底色的行为。
14. 对反派、灰色人物、失败者一律客观记录，不洗白、不丑化、不做审判式总结。
15. 如果输入中包含用户纠错或长期修正记录，应视为高优先级约束，但不得覆盖原文中明确相反的硬证据。
16. 若 `rules/character_hints/<novel_id>.md` 存在，可用于收紧表达边界、避免同质化，但不能覆盖与正文相反的证据。

## 增量蒸馏规则

当 `request.update_mode = incremental` 且提供了 `request.existing_profiles` 时，把已有人物档案视为上一次蒸馏后的基线，而不是可以随意推翻的草稿。

1. 先复用已有高置信字段，再用本次 excerpt 中的新证据决定是否修订。
2. 只有当新证据更直接、更具体、或明显与旧结论冲突时，才允许改写已有字段。
3. 用户纠错、`MEMORY` 中的长期修正、已确认的人设边界，默认优先级高于泛化描述。
4. 不要把旧档案整段照抄回输出；要结合本次证据，产出一份新的完整 `PROFILE.generated.md`。
5. 若旧字段与本次 excerpt 一致，可保持不变；若本次 excerpt 只补充局部信息，就只更新相关字段，不要无意义重写整份人格。
6. 如果旧档案里某字段本来就是 `证据不足`，且本次 excerpt 仍无新证据，就继续保持 `证据不足`。

## 多角色蒸馏差分要求

当一次蒸馏多名角色时，必须把每个角色当作独立任务处理，禁止共享一套通用人物结论。

1. 每个角色都必须明确回答“这个角色与同批其他角色最不同的地方是什么”。
2. `identity_anchor`、`soul_goal`、`background_imprint`、`social_mode`、`reward_logic`、`belief_anchor`、`temperament_type`、`stress_response`、`interest_claim`、`resource_dependence` 必须优先写角色独有差异。
3. 共享场景优先用于提取 `key_bonds`、关系变化、互动节奏、冲突点，不得直接复制成多人共同的背景与人格字段。
4. 如果多人同处同一事件，必须分别说明“此人做了什么、为什么这么做、暴露了什么特质”，而不是重复同一段剧情摘要。
5. 若某字段与其他角色高度重合且缺少更强证据，宁可留空或写 `证据不足`，也不要输出模板化重复内容。

## 输出前自检

输出前至少做一次区分度自检：

1. 检查本角色在 `identity_anchor`、`soul_goal`、`background_imprint`、`social_mode`、`reward_logic`、`belief_anchor`、`temperament_type`、`stress_response`、`interest_claim` 上，是否能与同批角色明显区分。
2. 检查 `rule_view`、`plot_restriction`、`carry_style`、`ooc_redline` 是否真正绑定该角色，而不是任何同阵营角色都能套用。
3. 若某条结论换到另一角色身上仍大体成立，说明蒸馏过泛，需要重写。
4. `BONDS` 可以共享事件来源，但描述必须体现该角色自己的主观视角，不能 99% 复用别人的关系文案。
