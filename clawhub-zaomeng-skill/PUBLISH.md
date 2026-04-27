# ClawHub 发布说明

## 建议元数据

- Type: OpenClaw Skill
- Name: zaomeng-skill
- Display Name: 造梦技能
- Version: 3.1.0
- Category: Writing / Roleplay / Character Simulation

## 风险说明

- 这是一个内嵌最小运行时的自包含 skill 包
- 不再把运行时克隆或外部 Git 引导作为主执行路径
- 仍依赖本地 Python 执行，以及 Python 包信任链：`PyYAML`，可选 `tiktoken`，可选 `ebooklib`
- 已包含显式安全策略

## 发布前检查

1. `SKILL.md` frontmatter 合法。
2. 内嵌运行时入口可以启动。
3. 输出规范与安全相关文件齐全。
4. 示例文件与当前 schema 一致。
5. 包内不包含凭证、密钥或其他敏感信息。

## 版本说明

- `3.1.0`：将 prompt 引用从纯文本切换为 Markdown，对齐 Markdown-first 人格工作流，在 `references/output_schema.md` 中补充 26 维度人格覆盖说明，并新增 `references/style_differ.md` 与 `references/logic_constraint.md`，用于去同质化和防止人设崩坏。
- `3.0.0`：将最小本地 zaomeng 运行时直接内嵌进 skill 包，去除主执行路径上的运行时 Git 引导，并将 skill 的执行入口切换到打包内的 `runtime/zaomeng_cli.py`。
- `2.1.1`：将自动引导流程固定到外部 zaomeng 仓库的特定 commit `649f7466738f99d60c454e167835462215cffc7d`，降低运行时供应链漂移风险。
- `2.1.0`：切换到 A+ 引导流，优先复用本地 zaomeng 仓库，否则再克隆仓库并执行真实 CLI 工作流。
- `2.0.0`：切换到 Markdown-first 人格存储，引入导航/人格包与运行时记忆写入，并加入自然语言聊天意图路由与 distill-before-chat、act/observe 会话建立逻辑。
- `1.0.9`：重写 skill 文档，明确 zaomeng 是本地规则引擎，并要求 agent 使用 `chat --message`。
- `1.0.8`：强化 agent 聊天规则，要求在任何 PTY 或 stdin 回退前必须优先使用 `--message`。
- `1.0.7`：加入单轮 `chat --message` 直接执行说明，并对齐 ClawHub 聊天规则。
- `1.0.6`：补充交互式聊天与需要确认的执行约束说明。
- `1.0.5`：让 ClawHub 打包 schema 和示例与当前按小说分组的本地工作流保持一致。
