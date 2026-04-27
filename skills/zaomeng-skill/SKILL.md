---
name: zaomeng-skill
description: zaomeng 本地规则型中文小说人物工作流技能。
---

# Zaomeng 技能

## 先看这个

- `zaomeng` 是本地规则驱动的人物引擎。
- 它不是通用大模型聊天机器人。
- 它做的是基于人物档案、关系数据、记忆文件的受约束角色互动。
- Agent 必须直接调用 CLI，不要自己重建聊天流程，也不要手动模拟角色回复。

## Chat 调用规则

- 默认规则：任何 agent 或工具调用 `chat` 时，都应该带 `--message`。
- 首选用法：
  - `python -m src.core.main chat --novel <路径或名称> --mode auto --message "<用户原话>"`
  - `python -m src.core.main chat --novel <路径或名称> --mode observe --message "<提示语>"`
  - `python -m src.core.main chat --novel <路径或名称> --mode act --character <角色名> --message "<用户台词>"`
- 多轮继续时，持续使用 `--session <id> --message "<提示语或台词>"`。
- 只有当用户明确想要交互式终端会话时，才允许使用不带 `--message` 的 `chat`。

## 自然语言意图映射

- 用户说 `让我扮演X和Y聊天`、`我来扮演X，你让Y回我`、`我说一句，Y回一句`、`进入 act 模式` 时，要把它当成 `act` 的启动意图。
- 这类启动语不能直接当成角色台词喂给引擎；应先让 CLI 建立或恢复 `act` 会话。
- 启动完成后，等用户下一句真正开口，再继续用 `--session <id> --message "<用户台词>"`。
- `act` 启动完成后，CLI 会把受控角色写进 session；后续同一会话里，除非要换角色，否则不需要重复传 `--character`。
- 用户说 `进入刘备、张飞、关羽群聊模式` 这类话时，是进入 `observe` 的启动意图。
- 用户说 `请让大家围绕这件事各说一句` 时，则是立刻执行一轮 `observe`，不是仅仅切模式。

## 禁止行为

- 不要在尝试 `--message` 之前就认定“环境不支持交互，所以 chat 不能用”。
- 不要模拟 stdin，也不要自动播放整段对话，除非用户明确要求脚本化交互。
- 不要读取 `chat_engine.py`、直接调用 `speaker.generate()`、或手动加载旧版 JSON 档案来替代 CLI。
- 不要把“模式切换请求”改写成你自己的自由发挥剧情演示。

## 其他命令

- 蒸馏：`python -m src.core.main distill --novel <路径> [--characters A,B] [--force]`
- 关系抽取：`python -m src.core.main extract --novel <路径> [--output <路径>] [--force]`
- 查看角色：`python -m src.core.main view --character <角色名> [--novel <路径或名称>]`
- 保存纠错：`python -m src.core.main correct --session <id> --message <原句> --corrected <修正句> [--character <角色名>]`

## 人格文件与记忆说明

- `distill` 现在会为每个角色生成 Markdown 人格包，位于 `data/characters/<novel_id>/<角色名>/`
- 核心文件包括：
  - `PROFILE.md`
  - `NAVIGATION.md`
  - `SOUL.md`
  - `IDENTITY.md`
  - `AGENTS.md`
  - `MEMORY.md`
  - `RELATIONS.md`
- 运行时会先读 `NAVIGATION.generated.md`，再叠加 `NAVIGATION.md`，按 `load_order` 加载人格层。
- `GOALS.md`、`STYLE.md`、`TRAUMA.md`、`RELATIONS.md` 是可选层，只在蒸馏或后续编辑确实需要时创建。
- 用户在群聊中的长期修正提示，以及 `/correct` 产生的纠错，会写入对应角色的 `MEMORY.md`。
- 不要假设角色设定只存在于 JSON；Markdown 人格文件才是当前主存储。
