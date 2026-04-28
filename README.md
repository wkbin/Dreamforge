# 造梦.skill

[中文](README.md) | [English](README.en.md)

`zaomeng` 是一个本地小说角色工具。

它做三件事：

- 从小说里蒸馏人物
- 从小说里抽取人物关系
- 让这些角色按设定进入群聊或和你对话

它不是普通陪聊机器人。  
它更像一个“小说角色引擎”。

许可证：主项目为 `AGPL-3.0-only`；`clawhub-zaomeng-skill` 子目录继续使用 `MIT-0`

当前推荐版本思路是：

- Markdown-first：人物与关系主存储已经不再以旧版 JSON 为准
- 自然语言优先：先蒸馏，再通过自然语言进入 `act` / `observe`
- skill 内嵌最小运行子集：`clawhub-zaomeng-skill` 已内置可运行的最小运行时
- 约束分层：`output_schema.md` 管格式，`style_differ.md` 管去同质化，`logic_constraint.md` 管防 OOC
- 聊天分层：`zaomeng` 继续负责人物约束、关系约束、记忆约束；若配置真实 LLM，则由 LLM 负责把回复说得更自然

## 对话生成

当前聊天支持两种生成路径：

- `local-rule-engine`
  不调用外部模型，直接按人物档案与规则生成，优点是稳定、离线；缺点是自然度有限。
- 真实 LLM 聊天生成
  `zaomeng` 先整理人物/关系/记忆约束，再把这些约束喂给 LLM 生成最终台词，群聊时后发言角色还会看到本轮前面已经说过的话。

常见配置示例：

```yaml
llm:
  provider: "openai"               # 也可用 openai-compatible / anthropic / ollama
  model: "gpt-4.1-mini"
  api_key: ""
  api_key_env: "OPENAI_API_KEY"
  base_url: ""
  temperature: 0.7
  max_tokens: 300

chat_engine:
  generation_mode: "auto"          # auto / rule-only / llm-only
  enable_turn_interactions: true   # 群聊里后发言角色可接前一句
  allow_character_silence: true    # 低相关角色可以不强行插话
  min_reply_relevance: 4
```

## 安装方式

你可以按自己的使用场景选择安装方式。

请注意：

- 现在的 `clawhub-zaomeng-skill` 已经内嵌最小可运行子集，不再把“运行时自动克隆外部仓库”作为主路径
- `openclaw skills install ...`、`clawhub ... install ...` 安装的是 skill 包；其中 `clawhub-zaomeng-skill` 已包含打包后的运行时与说明文件
- 如果当前宿主不允许执行本地 Python 命令，或缺少必要依赖，那么仍然无法运行真实工作流
- 如果你要直接改源码、跑测试、或使用仓库主 CLI，仍然推荐直接克隆本仓库

### 1. 直接克隆仓库

如果你想本地运行完整项目、直接执行 CLI，或者自己改代码，推荐直接克隆仓库：

```bash
git clone https://github.com/wkbin/zaomeng.git
cd zaomeng
```

### 2. 安装到 OpenClaw

如果你主要是在 OpenClaw 里把它当作 skill 使用，可以直接安装：

```bash
openclaw skills install wkbin/zaomeng-skill
```

这一步安装的是 skill 包，不等于完整的 `zaomeng` 仓库源码。  
当前 `clawhub-zaomeng-skill` 已内嵌最小运行时；在支持本地命令执行的宿主中，可直接走打包运行时。

### 3. 用 ClawHub 安装

如果你使用 ClawHub，可以选你习惯的命令：

```bash
npx clawhub@latest install zaomeng-skill
```

```bash
pnpm dlx clawhub@latest install zaomeng-skill
```

```bash
bunx clawhub@latest install zaomeng-skill
```

同样，这一步安装的是 skill 包，不等于你本地已经有完整的 `zaomeng` 开发仓库。
当前 `clawhub-zaomeng-skill` 已内嵌最小运行时；在支持本地命令执行的宿主中，可直接走打包运行时。

### 4. 已有本地 skill 目录时安装

如果你自己的项目里已经有 `skills/` 目录，也可以把仓库里的 skill 安装进去：

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

## 运行前提

要运行真实工作流，宿主环境至少要允许其中一种能力：

- 直接运行本仓库主 CLI
- 或运行 `clawhub-zaomeng-skill` 包内的最小运行时

如果当前宿主环境不允许执行本地命令，或缺少必要的 Python 依赖，那么就不能运行真实的 `zaomeng` CLI 工作流。

## 效果示例一：行动模式

```
用户      ❯  让我扮演贾宝玉和林黛玉聊天。
            场景定在：大观园沁芳亭畔，春日午后，黛玉正在桥上看鱼。

zaomeng   ❯ （春日午后，阳光透过柳丝洒在沁芳溪上，水光粼粼。
            黛玉独自立在沁芳桥畔，一手扶着桥栏，俯身看着溪中锦鲤游弋。
            风吹起她的裙角和鬓边几缕碎发，她似看得入神，
            手中捏着一朵不知何时摘的落花，指节微微发白。）

用户      ❯  林妹妹，这般暖的日头，怎一个人躲在这里发呆？   
            风吹得人倦，仔细站久了头晕。     

zaomeng   ❯ （闻声未回头，目光仍凝在粼粼溪水与游鱼之上，半晌才轻声道——）
             你倒管得宽。我在这里看鱼，鱼又不嫌我碍眼——哪像你们那些热闹去处，
             处处都是人，倒嫌我一个多余。
             （手指无意识地捻着那朵落花，花瓣碎了几片落在水面上，被鱼啄了去。
             这才微微侧过脸，眼尾扫了宝玉一眼，声音仍淡淡的。）
             仔细头晕的是你自己。这般好日头，不去陪宝姐姐下棋品茶，
             倒来这冷清地方找我——也不怕别人说你没正形。   

用户      ❯  好好的，怎又说出这般醋意十足的话来。
            世上热闹去处再多，于我而言，都不及沁芳桥边，有你在的半分意趣。        

zaomeng   ❯ （手中的落花一颤，指尖微微收紧。耳根慢慢泛起薄红，却将脸别向另一边，不肯让他瞧见。）
            ……哼。
            （沉默了一瞬，声音比方才软了几分，像是被春风化了一角棱角。）
            这样的话，你说过几遍了。再好听的话，说多了也就不稀奇了。
            （溪中锦鲤甩尾溅起一小朵水花，正落在她手背上。她低头看了看，忽然轻声念了一句——）
            "桃花帘外东风软，桃花帘内晨妆懒。帘外桃花帘内人，人与桃花隔不远。"
            （念完才意识到自己失言，耳根更红了，连忙用手中残花遮了遮嘴角，眼神飘忽地看向远处。）
            ……看鱼便是看鱼，谁与你念什么诗。你若嫌无聊，自去别处逛，不必杵在这里碍我的眼。
```

## 效果示例二：群里模式（观察）
```
用户      ❯  让贾宝玉，林黛玉，薛宝钗进入群聊模式（未指定场景）
            
zaomeng   ❯  好，角色档案和关系图谱已全部加载。设定场景——
             🎭 群聊模式启动
             📍 场景：蘅芜苑，秋日午后。宝钗正在房中理线。
              宝玉来找宝钗借书，撞见黛玉也在。三人聚于蘅芜苑中。
              ⏰ 时间线：第四十二回之后
              （金兰契已过，黛玉宝钗表面和解，但三角关系的暗流仍在）

宝玉（踏进蘅芜苑，见黛玉也在，喜上眉梢）：

好妹妹们都在这里！我原是来寻宝姐姐借书的，不想林妹妹也来了，倒省了我一趟腿。今日天好，不如咱们一处坐坐，说说话儿。

宝钗（放下手中针线，微微笑道）：

你倒来得巧。我这里正有一部新得的《广韵》，你若要借，拿去便是。只是别再像上回那般，借去了搁在怡红院积灰，没的糟蹋了书。——颦儿是来看我的，你坐下罢，我叫莺儿沏茶来。

黛玉（斜倚在榻上，目光扫过宝玉，淡淡道）：

倒是我来得不巧了。早知你在，我便不来了——免得有人说我又来搅扰你们说悄悄话。

(此处省略过多对话......)

zaomeng > 🌸 群聊暂停

          以上是第一轮群聊，基于三人蒸馏档案中的性格特征、语言风格和关系动态。你可以：
          
          继续聊 — 指定话题或让剧情自然发展
          切入某个角色 — 如"让黛玉说……"
          切换场景 — 比如搬到大观园诗社、宝玉挨打后、或者更紧张的对手戏
          结束群聊 — 回到正常对话
          怎么说？
```            



## 先看怎么用

正确顺序不是上来就群聊。  
**第一步永远是先给小说，再蒸馏人物。蒸馏完成后，才能进入群聊或扮演模式。**

用户最常见的使用路径是：

1. 把小说文件附上，或者指定小说文件路径
2. 用自然语言说你要蒸馏谁
3. 蒸馏完成后，再进入群聊或扮演

## 一个完整例子

### 第一步：先附上小说，再说要蒸馏谁

比如你先提供《红楼梦》的小说文本，然后说：

```text
帮我蒸馏林黛玉和贾宝玉
```

系统会先处理小说，生成这两个人物的档案和关系信息。

### 第二步：蒸馏完成后，再进入聊天

这时你再说：

```text
让我扮演贾宝玉和林黛玉聊天
```

系统才会进入“你扮演贾宝玉，林黛玉回应你”的玩法。

接着你可以继续说：

```text
妹妹今日可大安了？
```

系统会把这句当成贾宝玉真正说出口的话，再让林黛玉回话。

### 第三步：如果你想看多人互动，也要在蒸馏之后

比如你先提供《三国演义》，蒸馏刘备、张飞、关羽之后，再说：

```text
进入刘备、张飞、关羽群聊模式
```

然后你再说：

```text
刘备：二位贤弟，近日战事稍歇，倒是难得清闲。
```

系统才会让张飞、关羽接话。

## 你可以直接这样说

### 蒸馏人物

```text
帮我蒸馏林黛玉和贾宝玉
```

```text
请从这本小说里提取刘备、张飞、关羽的人设
```

### 蒸馏完成后进入扮演

```text
让我扮演贾宝玉和林黛玉聊天
```

### 蒸馏完成后进入群聊

```text
进入刘备、张飞、关羽群聊模式
```

### 直接让大家开口

```text
请让大家围绕联合孙权这件事各说一句
```

## 它能做什么

### 1. 人物蒸馏

从 `.txt` 或 `.epub` 小说中提取主要角色，输出 Markdown 人物档案。

当前档案会尽量覆盖更完整的人物维度，包括：

- 核心身份
- 核心动机
- 性格基底
- 行为逻辑
- 人物弧光
- 关键羁绊
- 符号化特征
- 世界观适配性
- 价值取舍体系
- 情绪反应模式
- 思维认知偏好
- 语言表达特质
- 专属能力与致命短板
- 出身背景与生存处境
- 深层执念与隐秘欲望
- 行事风格倾向
- 过往创伤与人生烙印
- 社交相处模式
- 内在自我矛盾
- 剧情职能定位
- 恐惧与避讳事物
- 信仰与精神支柱
- 认知局限与成长短板
- 立场摇摆特性
- 恩怨奖惩逻辑
- 私下真实面貌

核心字段示例包括：

- `core_traits`
- `values`
- `speech_style`
- `typical_lines`
- `decision_rules`
- `identity_anchor`
- `soul_goal`
- `core_identity`
- `faction_position`
- `background_imprint`
- `world_rule_fit`
- `social_mode`
- `hidden_desire`
- `inner_conflict`
- `story_role`
- `belief_anchor`
- `private_self`
- `stance_stability`
- `reward_logic`
- `strengths`
- `weaknesses`
- `cognitive_limits`
- `fear_triggers`
- `key_bonds`
- `action_style`
- `life_experience`
- `taboo_topics`
- `forbidden_behaviors`

### 2. 关系抽取

从小说中生成关系图谱，当前核心字段包括：

- `trust`
- `affection`
- `power_gap`
- `conflict_point`
- `typical_interaction`

### 3. 角色群聊

支持两种聊天方式：

- `observe`
  你给出一个场景、话题或开场白，让角色自然互动
- `act`
  你控制一个角色发言，其余角色按设定回话

### 4. 纠错记忆

如果某句明显不符合人物设定，可以把修正写入记忆。  
后续对话会尽量避开同类偏差。

### 5. Markdown 人格包

当前人物主存储已经是 Markdown，不再以旧版 JSON 为准。

每个角色目录现在以导航 + 生成层 + 可覆写层为主，常见文件包括：

- `data/characters/<novel_id>/<角色名>/NAVIGATION.generated.md`
- `data/characters/<novel_id>/<角色名>/NAVIGATION.md`
- `data/characters/<novel_id>/<角色名>/PROFILE.generated.md`
- `data/characters/<novel_id>/<角色名>/PROFILE.md`
- `data/characters/<novel_id>/<角色名>/RELATIONS.generated.md`
- `data/characters/<novel_id>/<角色名>/RELATIONS.md`
- `data/characters/<novel_id>/<角色名>/MEMORY.md`

按人物证据情况，还可能生成可选的人格拆分文件：

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

运行时会优先读取：

- `NAVIGATION.generated.md`
- `NAVIGATION.md`

并按 `load_order` 决定后续人格文件的加载顺序。

### 6. 约束参考文档

当前 skill 和运行时会把约束拆成三层：

- `references/output_schema.md`
  负责输出格式与字段规范
- `references/style_differ.md`
  负责防同质化与风格差异化
- `references/logic_constraint.md`
  负责全局人设底线、防 OOC 与模式边界

## 快速开始

### 1. 先准备小说文件

支持：

- `.txt`
- `.epub`

### 2. 先蒸馏，再聊天

以《红楼梦》为例：

```bash
python -m src.core.main distill --novel data/hongloumeng.txt --characters 林黛玉,贾宝玉 --force
python -m src.core.main extract --novel data/hongloumeng.txt --force
```

这一步会生成：

- `data/characters/hongloumeng/<角色名>/`
- `data/relations/hongloumeng/hongloumeng_relations.md`

### 3. 蒸馏完成后，开始聊天

推荐直接用自然语言：

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode auto --message "让我扮演贾宝玉和林黛玉聊天"
```

然后继续：

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --session <session_id> --message "妹妹今日可大安了？"
```

如果你想进入多人群聊：

```bash
python -m src.core.main chat --novel data/sanguo.txt --mode auto --message "进入刘备、张飞、关羽群聊模式"
python -m src.core.main chat --novel data/sanguo.txt --session <session_id> --message "刘备：二位贤弟，近日战事稍歇。"
```

如果你使用的是 `clawhub-zaomeng-skill` 打包运行时，对应入口是：

```bash
py -3 runtime/zaomeng_cli.py distill --novel <路径> --characters A,B
py -3 runtime/zaomeng_cli.py extract --novel <路径>
py -3 runtime/zaomeng_cli.py chat --novel <路径或名称> --mode auto --message "让我扮演A和B聊天"
```

## 其他命令

### 查看角色档案

```bash
python -m src.core.main view --character 林黛玉 --novel data/hongloumeng.txt
```

### 保存一次纠错

```bash
python -m src.core.main correct \
  --session <session_id> \
  --message "宝玉打算离家经商" \
  --corrected "宝玉一向厌弃仕途经济，更愿留在诗酒园林之间" \
  --character 贾宝玉
```

## 命令总览

```bash
python -m src.core.main distill --novel <path> [--characters A,B] [--output <dir>] [--force]
python -m src.core.main extract --novel <path> [--output <path>] [--force]
python -m src.core.main chat --novel <path-or-name> --mode auto|observe|act [--character <name>] [--session <id>] [--message <text>]
python -m src.core.main view --character <name> [--novel <path-or-name>]
python -m src.core.main correct --session <id> --message <raw> --corrected <fixed> [--character <name>] [--target <name>] [--reason <text>]
```

## 项目结构

```text
Dreamforge/
├─ src/                          # 主源码
│  ├─ core/                      # 入口、配置、依赖注入、规则加载
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ contracts.py
│  │  ├─ llm_client.py
│  │  ├─ path_provider.py
│  │  └─ rulebook.py
│  ├─ modules/                   # 核心业务模块：蒸馏、关系、聊天、纠错、发言
│  │  ├─ distillation.py
│  │  ├─ relationships.py
│  │  ├─ chat_engine.py
│  │  ├─ reflection.py
│  │  └─ speaker.py
│  └─ utils/                     # 文本解析、文件读写、token 统计等通用工具
│     ├─ file_utils.py
│     ├─ text_parser.py
│     └─ token_counter.py
├─ rules/                        # 仓库主规则文件
│  ├─ distillation_rules.md
│  └─ relationship_rules.md
├─ clawhub-zaomeng-skill/        # 可独立发布的 ClawHub/OpenClaw skill 包
│  ├─ README.md
│  ├─ README_EN.md
│  ├─ SKILL.md
│  ├─ INSTALL.md
│  ├─ MANIFEST.md
│  ├─ PUBLISH.md
│  ├─ prompts/                   # skill 内置 prompt 模板
│  ├─ references/                # schema、去同质化、逻辑约束等参考文档
│  ├─ examples/                  # 示例档案与关系图谱
│  └─ runtime/                   # skill 打包运行时（最小执行子集）
│     ├─ zaomeng_cli.py
│     ├─ requirements.txt
│     ├─ rules/
│     └─ src/
├─ skills/                       # 其它宿主技能目录
│  └─ zaomeng-skill/
├─ openclaw-skill/               # OpenClaw 侧集成物
├─ hermes-skill/                 # Hermes 侧集成物
├─ scripts/                      # 安装与辅助脚本
├─ tests/                        # 回归与行为测试
│  └─ test_relation_behavior.py
├─ data/                         # 本地运行数据（人物、关系、会话等）
├─ README.md                     # 中文说明
├─ README.en.md                  # 英文说明
├─ LICENSE                       # 仓库许可证
└─ requirements.txt              # 主项目依赖
```

## License

主项目：`AGPL-3.0-only`

`clawhub-zaomeng-skill`：`MIT-0`
