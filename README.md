# 造梦.skill

[中文](README.md) | [English](README.en.md)

本地小说人物蒸馏、关系抽取、角色群聊与记忆修正工具链。

它的目标不是做一个泛用聊天机器人，而是把小说文本转成可复用的角色资产：

- 人物档案
- 关系图谱
- 对话约束
- 纠错记忆
- 可直接接入 Agent 的 skill 包

当前版本基于本地规则引擎运行，不依赖云端模型或 API Key，适合离线分析、角色扮演、同人创作、文学研究和 Agent 编排。

## 这个项目能做什么

### 1. 人物蒸馏

从 `.txt` 或 `.epub` 小说中抽取主要角色，输出结构化人物画像，包括：

- 核心性格特征 `core_traits`
- 价值观维度 `values`
- 语言风格 `speech_style`
- 代表性台词 `typical_lines`
- 行为决策倾向 `decision_rules`
- 阶段性人物弧光 `arc`
- 证据计数 `evidence`

适合做：

- 角色档案整理
- 原著人物设定提炼
- 后续群聊和剧情实验的底层资产

### 2. 关系抽取

从小说中生成角色关系图谱，当前输出字段包括：

- `trust`
- `affection`
- `power_gap`
- `conflict_point`
- `typical_interaction`

当前关系建边策略已经收紧到“同句共现”，比粗糙的 chunk 共现更适合做后续群聊约束。

### 3. 角色群聊

基于蒸馏出的角色档案和关系图谱，启动本地多角色对话。

支持两种模式：

- `observe`
  你给出一个场景或一句引导语，系统让角色围绕它展开互动
- `act`
  你控制某个角色发言，其他角色按自身设定和关系状态回复

群聊过程中支持：

- `/save` 保存会话
- `/reflect` 检查最近发言是否偏离人设
- `/correct 角色|对象|原句|修正句|原因` 写入纠错记忆
- `/quit` 退出会话

### 4. 记忆修正

当角色说出明显不符合原著设定的话时，可以把修正写入本地记忆：

```bash
python -m src.core.main correct \
  --session <session_id> \
  --message "宝玉说要离开贾府经商" \
  --corrected "宝玉对仕途经济不感兴趣，只愿与姐妹们作诗赏花" \
  --character 贾宝玉
```

修正数据会落到 `data/corrections/`，后续聊天会尝试避免重复出现类似的 OOC 行为。

### 5. Agent 快速接入

当前仓库同时提供：

- `openclaw-skill/`
- `hermes-skill/`
- `skills/zaomeng-skill/`
- `clawhub-zaomeng-skill/`

可以直接接入 OpenClaw、Hermes Agent、ClawHub CLI 或你自己的本地项目。

## 核心玩法

### 玩法一：先蒸馏人物，再进入群聊

以《红楼梦》为例：

```bash
python -m src.core.main distill --novel data/hongloumeng.txt --characters 林黛玉,贾宝玉 --force
python -m src.core.main extract --novel data/hongloumeng.txt --force
```

这一步会在小说级目录下生成角色档案和关系文件：

- `data/characters/hongloumeng/*.json`
- `data/relations/hongloumeng/hongloumeng_relations.json`

现在系统已经支持指定角色时的两字别名匹配，例如：

- `林黛玉 -> 黛玉`
- `贾宝玉 -> 宝玉`

所以即使正文里常写“黛玉”“宝玉”，蒸馏和关系抽取也能更稳地命中证据。

### 玩法二：观察模式

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode observe --message "请让大家围绕黛玉初到贾府时的见面场景各说一句。"
```

这个模式不是“自动无输入跑完”，而是交互式会话。你应该先给系统一个起始场景或一句引导语，例如：

```text
请让大家围绕黛玉初到贾府时的见面场景各说一句。
```

适合做：

- 观察角色自然互动
- 看关系参数如何影响说话方式
- 验证人物蒸馏是否贴近原著

### 玩法三：行动模式

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode act --character 林黛玉 --message "宝玉，你今日为何这样看我？"
```

这个模式下你控制指定角色发言，其他角色回应。推荐直接输入一个具体意图，例如：

```text
我先表态，你们再接。
```

或者更像剧情推进的开场：

```text
宝玉，你今日怎么又来得这样晚？
```

适合做：

- 沉浸式角色扮演
- 测试某个角色在特定关系下的回应
- 做剧情分支实验

### 玩法四：查看角色档案

```bash
python -m src.core.main view --character 林黛玉 --novel data/hongloumeng.txt
python -m src.core.main view --character 贾宝玉 --novel data/hongloumeng.txt
```

当前 `view` 命令一次查看一个角色。如果你要批量看多个角色，最直接的方式是浏览：

- `data/characters/<novel_id>/`

适合做：

- 检查蒸馏结果
- 对比不同角色的语言风格和价值观
- 为后续手动调参提供依据

### 玩法五：手动调关系，再进群聊

如果你觉得自动抽取的关系不够细，完全可以手动编辑关系文件，再重新进入群聊：

- 查看现有关系：`data/relations/hongloumeng/hongloumeng_relations.json`
- 手动补充或调整某组角色关系
- 再运行 `chat`

例如你可以手动写入：

```json
{
  "林黛玉_贾宝玉": {
    "trust": 8,
    "affection": 9,
    "power_gap": 2,
    "conflict_point": "金玉良缘 vs 木石前盟",
    "typical_interaction": "黛玉质问，宝玉安抚，情绪短暂缓和"
  }
}
```

这类手动调校特别适合原著里关系复杂、情感层次多、但自动规则还难以完全覆盖的角色对。

## 红楼梦示例

### 示例 1：观察黛玉与宝玉的互动

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode observe --message "场景：荣国府内，黛玉初到贾府，宝玉第一次见到她。请让相关角色自然开口。"
```

首轮输入可以这样写：

```text
场景：荣国府内，黛玉初到贾府，宝玉第一次见到她。请让相关角色自然开口。
```

### 示例 2：你来扮演黛玉

```bash
python -m src.core.main chat --novel data/hongloumeng.txt --mode act --character 林黛玉 --message "宝玉，你今日为何这样看我？"
```

你可以输入：

```text
宝玉，你今日为何这样看我？
```

### 示例 3：修正一次出戏发言

```bash
python -m src.core.main correct \
  --session <session_id> \
  --message "宝玉打算离家创业" \
  --corrected "宝玉对仕途经济一向厌弃，更愿沉在闺阁诗酒之中" \
  --character 贾宝玉
```

## 适合怎么玩

### 1. 同人创作

- 让原著角色进入平行剧情
- 测试“如果当时说了另一句话”会怎样
- 写角色之间的补完对话

### 2. 文学研究

- 量化对比角色性格特征
- 从关系图角度看人物网络
- 分析不同角色的语言风格和互动模式

### 3. 剧情实验

- 给一个关键情节作为起始 prompt
- 改写某个冲突点
- 观察不同关系参数下角色行为如何变化

### 4. Agent 场景

- 把小说角色当作可复用人格资产
- 接入 OpenClaw / Hermes / ClawHub
- 用在多角色模拟、剧情树实验、角色约束测试里

## 可调配置

### 1. 价值观维度

你可以在 `config.yaml` 里调整人物价值观维度，让它更适配具体作品：

```yaml
distillation:
  values_dimensions:
    - "情缘"
    - "才情"
    - "命运"
    - "家族责任"
    - "个人追求"
    - "礼教束缚"
```

### 2. 群聊参数

```yaml
chat_engine:
  max_history_turns: 20
  max_speakers_per_turn: 6
  token_limit_per_turn: 800
```

适合做：

- 增加对话上下文长度
- 提高同场角色数量
- 放大复杂场景下的对话容量

## 命令总览

```bash
python -m src.core.main distill --novel <path> [--characters A,B] [--output <dir>] [--force]
python -m src.core.main extract --novel <path> [--output <path>] [--force]
python -m src.core.main chat --novel <path-or-name> --mode observe|act [--character <name>] [--session <id>] [--message <text>]
python -m src.core.main view --character <name> [--novel <path-or-name>]
python -m src.core.main correct --session <id> --message <raw> --corrected <fixed> [--character <name>] [--target <name>] [--reason <text>]
```

交互说明：

- `chat` 是交互式命令，进入前应先准备首轮输入
- `distill` / `extract` 默认会要求费用确认
- 在 Agent 或工具驱动场景中，应先征得用户同意，再使用 `--force`

## 快速接入

仓库地址：

```text
https://github.com/wkbin/zaomeng.git
```

### OpenClaw

推荐安装：

```bash
openclaw skills install wkbin/zaomeng-skill
```

### 你自己的项目

推荐使用 ClawHub CLI：

```bash
npx clawhub@latest install zaomeng-skill
```

如果你的项目已经有 `skills/` 目录，也可以直接安装：

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

## 当前实现说明

- 输入格式支持 `.txt` 和 `.epub`
- 角色档案默认按小说隔离输出到 `data/characters/<novel_id>/`
- 关系结果默认输出到 `data/relations/<novel_id>/`
- 群聊会优先读取对应小说范围内的人物与关系数据
- 关系抽取当前使用同句共现和规则打分，稳定但仍有上限
- `view` 当前一次只查看一个角色
- 项目当前以本地规则引擎为主，不依赖外部云端模型

## 项目结构

```text
src/core/main.py
src/modules/distillation.py
src/modules/relationships.py
src/modules/chat_engine.py
src/modules/reflection.py
src/modules/speaker.py
src/utils/
openclaw-skill/
hermes-skill/
skills/zaomeng-skill/
clawhub-zaomeng-skill/
tests/test_relation_behavior.py
```

## License

[MIT](LICENSE)
