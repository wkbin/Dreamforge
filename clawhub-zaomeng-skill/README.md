# zaomeng-skill

`zaomeng-skill` 是一个面向中文小说人物蒸馏、关系抽取、角色单聊与群聊的技能包。

它不是普通陪聊模板，而是一套“先蒸馏，再按人物档案说话”的本地规则型工作流。

更准确地说：

- `zaomeng` 负责人物蒸馏、关系抽取、人格导航、持久记忆与 OOC 约束
- 默认情况下，`zaomeng` 仍可作为“人格与约束层”使用
- 如果配置了真实 LLM，`zaomeng chat` 现在也可以在人物/关系/记忆约束下直接生成更自然的最终台词

许可证：`MIT-0`（MIT No Attribution）

## 这版有什么变化

当前发布线已经切到 `3.2.0`，重点变化是：

- 继续保留 Markdown-first 的人物与关系工作流
- `RuntimeParts` 统一 skill 内嵌 runtime 的装配路径，补充懒加载、依赖复用与增量 overrides
- runtime 薄 wrapper 与共享实现镜像现在纳入同一套 mirror / wrapper / packaging guardrails
- 修复 Windows CI 下的路径解析与控制台编码问题
- 继续支持真实 LLM 聊天生成、群聊顺序互动、以及低相关角色按需沉默

## 对话生成模式

你现在可以按两种方式使用聊天：

- `local-rule-engine`
  完全本地规则生成，不调用外部模型。
- 真实 LLM
  由 `zaomeng` 先整理人物约束、关系约束、记忆约束，再调用外部模型生成最终回复。

配置示例：

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
  enable_turn_interactions: true
  allow_character_silence: true
  min_reply_relevance: 4
```

## 它能做什么

### 1. 蒸馏人物

从小说原文中提取人物档案，尽量覆盖更完整的人物维度，例如：

- 核心身份
- 核心动机
- 性格基底
- 行为逻辑
- 人物弧光
- 关键羁绊
- 语言表达特质
- 价值取舍体系
- 深层执念与隐秘欲望
- 私下真实面貌

### 2. 抽取关系

从同框互动中提取两两关系，输出关系图谱和角色侧关系层。

### 3. 进入角色聊天

支持两种主要玩法：

- `act`
  你扮演一个角色说话，其他角色按设定回应
- `observe`
  让多个角色围绕一个场景、话题或开场白进行互动

### 4. 保存纠错

如果某句明显 OOC，可以把纠错写回记忆，后续对话继续沿用。

## 安装方式

### OpenClaw

```bash
openclaw skills install wkbin/zaomeng-skill
```

### ClawHub

```bash
npx clawhub@latest install zaomeng-skill
```

```bash
pnpm dlx clawhub@latest install zaomeng-skill
```

```bash
bunx clawhub@latest install zaomeng-skill
```

### 本地 skill 目录安装

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

## 运行前提

要跑真实工作流，宿主环境至少需要满足这些条件：

- 能执行本地 Python 命令
- 已安装 `PyYAML`
- 如果读取 `.epub`，还需要 `ebooklib`
- 如果需要更准确的 token 估算，可选装 `tiktoken`

skill 包当前使用的打包运行时入口是：

```text
runtime/zaomeng_cli.py
```

当前 runtime 源码按两层组织：

- runtime 自持薄 wrapper：`runtime/src/core/main.py`、`runtime/src/core/runtime_factory.py`、`runtime/src/core/logging_utils.py`
- 共享实现镜像：`runtime/src/core/cli_app.py`、`runtime/src/core/runtime_parts.py`、`runtime/src/core/logging_setup.py`，以及 `modules/`、`utils/` 下的共享业务模块

## 推荐用法

正确顺序不是一上来就群聊。  
**先给小说，再蒸馏人物，蒸馏完成后再进入聊天。**

最常见的使用路径是：

1. 提供小说文件，或指定小说路径
2. 用自然语言说要蒸馏谁
3. 蒸馏完成后，再进入 `act` 或 `observe`

## 自然语言示例

### 蒸馏

```text
帮我蒸馏林黛玉和贾宝玉
```

```text
请从这本小说里提取刘备、张飞、关羽的人设
```

### 进入 act

```text
让我扮演贾宝玉和林黛玉聊天
```

```text
我来扮演宝玉，你让黛玉回我
```

### 进入 observe

```text
进入刘备、张飞、关羽群聊模式
```

```text
请让大家围绕联合孙权这件事各说一句
```

## CLI 示例

如果你直接运行打包运行时，可用这些命令：

```bash
py -3 runtime/zaomeng_cli.py distill --novel <路径> --characters A,B
py -3 runtime/zaomeng_cli.py extract --novel <路径>
py -3 runtime/zaomeng_cli.py chat --novel <路径或名称> --mode auto --message "让我扮演A和B聊天"
py -3 runtime/zaomeng_cli.py view --character <角色名> --novel <路径或名称>
py -3 runtime/zaomeng_cli.py correct --session <id> --message <原句> --corrected <修正句> --character <角色名>
```

## 人格包结构

当前人物主存储为 Markdown 人格包，常见目录结构如下：

```text
runtime/data/characters/<novel_id>/<角色名>/
```

常见文件：

- `NAVIGATION.generated.md`
- `NAVIGATION.md`
- `PROFILE.generated.md`
- `PROFILE.md`
- `RELATIONS.generated.md`
- `RELATIONS.md`
- `MEMORY.md`

按人物证据情况，还可能生成可选拆分文件：

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

## 约束文件

这版 skill 把约束拆成三层：

- `references/output_schema.md`
  负责输出格式与字段规范
- `references/style_differ.md`
  负责防同质化与风格差异化
- `references/logic_constraint.md`
  负责全局人设底线、防 OOC 与模式边界

如果你在检查输出质量，这三份文件应该一起看，而不是只看 schema。

## 和 SKILL.md 的区别

- `README.md` 是给用户看的，重点是安装、使用方式和产物说明
- `SKILL.md` 是给宿主和 agent 读的，重点是执行规则、调用约束和禁止行为

## 发布提示

如果你要把这个 skill 单独发布，建议至少一起带上这些文件：

- `README.md`
- `SKILL.md`
- `INSTALL.md`
- `MANIFEST.md`
- `PUBLISH.md`
- `prompts/`
- `references/`
- `runtime/`

## License

`MIT-0`
