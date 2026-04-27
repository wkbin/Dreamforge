---
name: zaomeng-skill
description: ClawHub 技能包，用于 zaomeng 的本地规则型中文小说人物工作流。
---

# zaomeng 技能（ClawHub）

## 先看这个

- `zaomeng` 是本地规则驱动的人物引擎，不是自由生成式陪聊。
- 使用这个技能的 agent 必须直接调用 CLI 入口，不要手动模拟角色链路。
- 正常用户任务不要先读 `INSTALL.md` 或 `MANIFEST.md`；那是打包说明，不是运行说明。
- 正常用户任务不要把环境排查过程逐条说给用户听。

## 引擎准备

- 这个 skill 包已经内嵌最小可运行子集，优先直接使用 skill 包内运行时，不要再自动克隆外部仓库。
- 运行时入口：
  - `runtime/zaomeng_cli.py`
  - 核心源码位于 `runtime/src/...`
  - 默认数据目录位于 `runtime/data/...`
- 依赖要求：
  - 必需：`PyYAML`
  - 可选：`tiktoken`，仅用于更准确的 token 估算
  - 可选：`ebooklib`，仅在读取 `.epub` 小说时需要
- 命令建议：
  - Windows / PowerShell 优先使用 `py -3 runtime/zaomeng_cli.py ...`
  - 其他环境可使用 `python runtime/zaomeng_cli.py ...`
- 如果只是普通 `.txt` 小说蒸馏/群聊，缺少 `tiktoken` 不会阻塞执行。
- 只有在 Python 本身不可用、`PyYAML` 缺失、或当前宿主禁止执行本地命令时，才向用户简短说明阻塞原因。

## 正常执行顺序

- 开始执行前，先确认可调用 skill 包内运行时。
- 用户给了小说文件并要求蒸馏时，先按真实工作流处理：`distill`，必要时再 `extract`。
- 当运行时或辅助 agent 需要参考 skill 内的 Markdown 约束时，除 `references/output_schema.md` 外，还应同时参考 `references/style_differ.md` 与 `references/logic_constraint.md`。
- 蒸馏完成后，才进入 `chat` / `observe` / `act`。
- 只有在内嵌运行时不可执行时，才简短说明“当前环境无法启动可运行的 zaomeng 引擎，无法执行真实工作流”。
- 除非用户明确要求“按 skill 模板手动生成一版”，否则不要退化成读取 prompt/schema 后手工模拟引擎输出。
- 不要向用户输出类似 `src.core.main 不存在`、`先读取安装说明`、`我来检查依赖情况` 这种调试式提示。

## Chat 调用规则

- 前提：优先直接调用 `runtime/zaomeng_cli.py`，不要绕过它去手动拼装内部模块。
- 默认规则：任何 agent 使用这个技能调用 `chat` 时，必须带 `--message`。
- Windows / PowerShell 首选用法：
  - `py -3 runtime/zaomeng_cli.py chat --novel <路径或名称> --mode auto --message "<用户原话>"`
  - `py -3 runtime/zaomeng_cli.py chat --novel <路径或名称> --mode observe --message "<提示语>"`
  - `py -3 runtime/zaomeng_cli.py chat --novel <路径或名称> --mode act --character <角色名> --message "<用户台词>"`
  - `py -3 runtime/zaomeng_cli.py chat --novel <路径或名称> --mode auto|observe|act [--character <角色名>] --session <id> --message "<提示语或台词>"`

## 自然语言意图映射

- `让我扮演X和Y聊天`、`我来扮演X，你让Y回我`、`我说一句，Y回一句`、`进入 act 模式`：按 `act` 启动意图处理。
- 这类启动语不能直接当成角色台词喂给引擎；先让 CLI 建立或恢复 `act` 会话。
- 后续用户真正进入对白时，再继续用 `--session <id> --message "<用户台词>"`。
- `act` 启动后，CLI 会把受控角色写进 session；同一会话续聊时，通常不必重复传 `--character`。
- `进入刘备、张飞、关羽群聊模式`：按 `observe` 启动意图处理。
- `请让大家围绕这件事各说一句`：按真实 `observe` 单轮执行。

## 禁止行为

- 不要在尝试单轮 `--message` 前就说环境没有 PTY、没有 stdin、或者不支持交互。
- 不要在 `--message` 能表达请求时改成自动脚本化 stdin。
- 不要读取 `chat_engine.py`、直接调用 `speaker.generate()`、或手动适配旧版 JSON 档案来替代 CLI。
- 不要因为看到 `prompts/*.md`、`references/output_schema.md`、`INSTALL.md`、`MANIFEST.md`，就把它们当成“可直接替代本地引擎”的执行方案。
- 不要只读取 `references/output_schema.md` 就直接生成结果；如果需要参考 skill 内的 Markdown 约束，必须同时纳入 `references/style_differ.md` 与 `references/logic_constraint.md`。
- 不要自动克隆外部 Git 仓库，也不要把运行时退回到“先去 GitHub 拿源码再执行”。
- 不要在尚未检查 skill 包内运行时、也没有尝试直接执行时，就直接说“引擎不存在”。
- 不要把模式切换请求改写成自由发挥的剧情演示。

## 面对用户的标准回复模板

- 总原则：面对用户时，只说“现在要做什么”和“接下来发生什么”，不要输出调试日志、依赖排查过程、源码路径判断过程。

### 1. 用户要求蒸馏人物

推荐说法：

```text
我先按 zaomeng 的流程处理这本小说，蒸馏出你指定的人物档案。蒸馏完成后，如果你要，我再继续进入群聊或扮演模式。
```

不要说：

```text
先读取安装说明。
src.core.main 不存在。
我来检查依赖。
```

### 2. 蒸馏完成后，用户要求进入 act / observe

推荐说法：

```text
人物档案已经可用，我现在按 zaomeng 的聊天流程进入对应模式。
```

如果是 act 启动语：

```text
我先为你建立 act 会话。接下来你说一句角色台词，我再让对方角色按设定回应。
```

如果是 observe 启动语：

```text
我先为你建立群聊会话。接下来你可以给场景、话题，或者让某个角色先开口。
```

### 3. 本机没有真实 zaomeng 引擎时

只允许简短说明：

```text
我先尝试启动 skill 内嵌的 zaomeng 运行时；如果当前环境不允许执行，或缺少必要依赖，我再告诉你这一点。
当前环境暂时无法启动可运行的 zaomeng 引擎，所以我现在不能执行真实的 zaomeng 工作流。
如果你愿意，我可以按 skill 的格式要求手动整理一版兼容结果，但这不等同于真实引擎输出。
```

不要说：

```text
src.core.main 模块不存在
让我检查依赖情况
先看一下安装说明
先读取 output_schema 和 distill_prompt
```

### 4. 用户已经给了自然语言意图

- 如果用户在描述玩法，就直接进入对应流程，不要把这句改写成剧情演示。
- 如果用户已经在以角色身份说话，就直接把它当成该角色台词处理。

推荐说法：

```text
我先按你的要求进入这个模式。
```

或：

```text
这句我会直接当成该角色的发言来处理。
```

## 其他命令

- 蒸馏：`py -3 runtime/zaomeng_cli.py distill --novel <路径> [--characters A,B] [--force]`
- 关系抽取：`py -3 runtime/zaomeng_cli.py extract --novel <路径> [--output <路径>] [--force]`
- 查看角色：`py -3 runtime/zaomeng_cli.py view --character <角色名> [--novel <路径或名称>]`
- 保存纠错：`py -3 runtime/zaomeng_cli.py correct --session <id> --message <原句> --corrected <修正句> [--character <角色名>]`

## 人格文件与记忆说明

- 当前主存储为 Markdown 人格包，不再以 JSON 为准。
- 人格文件默认位于 `runtime/data/characters/<novel_id>/<角色名>/`。
- 运行时会先读 `NAVIGATION.generated.md`，再叠加 `NAVIGATION.md`，然后按 `load_order` 加载人格文件。
- 用户长期修正和 `/correct` 的结果会写入对应角色的 `MEMORY.md`。
