---
name: hermes-zaomeng
description: Hermes 适配器，用于 zaomeng 的本地规则型中文小说人物工作流。
---

# Hermes 适配器

## 先看这个

- `zaomeng` 是本地规则驱动的人物引擎。
- 它不是通用大模型聊天机器人。
- 它做的是基于人物档案和关系数据的受约束角色互动。
- 不要把它描述成自由聊天、开放式生成、创意型模型对话。
- Hermes 必须直接调用 CLI，不要去读源码后自己重建流程。

## Chat 调用规则

- 默认规则：Hermes 调用 `chat` 时，必须带 `--message`。
- 首选用法：
  - `python -m src.core.main chat --novel <路径> --mode observe --message "<提示语>"`
  - `python -m src.core.main chat --novel <路径> --mode act --character <角色名> --message "<提示语>"`
- 多轮继续时，持续使用 `--session <id> --message "<提示语>"`。
- 只有当用户明确要求“实时终端交互”时，才允许使用不带 `--message` 的 `chat`。

## 禁止行为

- 不要在尝试 `--message` 之前先说环境不支持 PTY 或交互输入。
- 不要在 `--message` 能表达请求时改用 stdin 脚本。
- 不要读取 `chat_engine.py`、直接调用 `speaker.generate()`、或手动加载角色 JSON，除非用户明确要求你检查代码。

## 其他命令

- 蒸馏：`python -m src.core.main distill --novel <路径> [--characters A,B] [--force]`
- 关系抽取：`python -m src.core.main extract --novel <路径> [--force]`
- 查看角色：`python -m src.core.main view --character <角色名> [--novel <路径>]`
- 保存纠错：`python -m src.core.main correct --session <id> --message <原句> --corrected <修正句>`

## 人格文件与记忆说明

- `distill` 现在除了角色 JSON，还会为每个角色生成可编辑人格文件：
  - `NAVIGATION.md`
  - `SOUL.md`
  - `IDENTITY.md`
  - `AGENTS.md`
  - `MEMORY.md`
  - `RELATIONS.md`
- 这些文件位于 `data/characters/<novel_id>/<角色名>/`
- 运行时会先读取 `NAVIGATION.generated.md`，再应用 `NAVIGATION.md` 覆写，并按 `load_order` 加载人格文件
- `GOALS.md` / `STYLE.md` / `TRAUMA.md` / `RELATIONS.md` 属于可选层，蒸馏或后续编辑确实需要时才会创建
- 用户在群聊里给出的长期约束提示，以及 `/correct` 产生的纠正，也会写入对应角色的 `MEMORY.md`
- 所以 Hermes 不要假设角色设定只存在于 JSON；如果需要解释行为，请把这些人格文件也视作有效设定来源
