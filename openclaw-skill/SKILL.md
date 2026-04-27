---
name: openclaw-zaomeng
description: OpenClaw 适配器，用于 zaomeng 的本地规则型中文小说人物工作流。
---

# OpenClaw 适配器

## 先看这个

- `zaomeng` 是本地规则驱动的人物引擎，不是开放式自由聊天模型。
- OpenClaw 必须直接走项目公开的 CLI 入口，不要自己拼装内部流程。

## 引擎准备

- 这个 skill 适配层本身不包含 `zaomeng` 引擎源码，但允许自动准备本地仓库。
- 正常顺序：
  - 先检查当前工作区是否已经有 `zaomeng` 仓库
  - 如果没有，就克隆 `https://github.com/wkbin/zaomeng.git`
  - 进入仓库目录后，再执行真实 CLI
- 默认仓库目录名可用 `zaomeng`。如果当前工作区已经是该仓库，就直接复用。
- 推荐准备命令：
  - `git clone https://github.com/wkbin/zaomeng.git`
  - `cd zaomeng`
- 只有在无法访问网络、无法克隆、或本地环境禁止执行时，才向用户简短说明阻塞原因。

## Chat 调用规则

- 前提：先确认本地已有仓库，或先自动克隆仓库，再执行以下命令。
- 默认规则：OpenClaw 调用 `chat` 时，必须带 `--message`。
- 首选用法：
  - `python -m src.core.main chat --novel <路径或名称> --mode auto --message "<用户原话>"`
  - `python -m src.core.main chat --novel <路径或名称> --mode observe --message "<提示语>"`
  - `python -m src.core.main chat --novel <路径或名称> --mode act --character <角色名> --message "<用户台词>"`
- 多轮继续时，复用 `--session <id> --message "<提示语或台词>"`。

## 自然语言意图映射

- `让我扮演X和Y聊天`、`我来扮演X，你让Y回我`、`我说一句，Y回一句`、`进入 act 模式`：按 `act` 启动意图处理。
- 启动意图不能直接当成角色台词；要先让 CLI 建立或恢复 `act` 会话。
- 后续用户真正进入对白时，再继续用 `--session <id> --message "<用户台词>"`。
- `act` 启动后，CLI 会把受控角色写进 session；同一会话续聊时，通常不必重复传 `--character`。
- `进入刘备、张飞、关羽群聊模式`：按 `observe` 启动意图处理。
- `请让大家围绕这件事各说一句`：按真实 `observe` 单轮执行。

## 禁止行为

- 不要在尝试 `--message` 前就说 PTY 失败、stdin 失败或环境不支持交互。
- 不要在 `--message` 可以表达请求时模拟 stdin 或脚本化聊天。
- 不要手动读取内部模块来绕开 CLI。
- 不要在尚未检查本地仓库、也没有尝试自动克隆时，就直接说“引擎不存在”。
- 不要把模式切换请求改写成自由发挥的剧情演示。

## 其他命令

- 蒸馏：`python -m src.core.main distill --novel <路径> [--characters A,B] [--force]`
- 关系抽取：`python -m src.core.main extract --novel <路径> [--output <路径>] [--force]`
- 查看角色：`python -m src.core.main view --character <角色名> [--novel <路径或名称>]`
- 保存纠错：`python -m src.core.main correct --session <id> --message <原句> --corrected <修正句> [--character <角色名>]`

## 人格文件与记忆说明

- 角色设定主存储为 Markdown，不再以 JSON 为准。
- 运行时会按 `NAVIGATION` 的 `load_order` 读取人格文件层。
- 用户长期修正和 `/correct` 的结果会写入对应角色的 `MEMORY.md`。
