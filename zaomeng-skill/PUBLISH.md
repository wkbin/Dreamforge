# ClawHub 发布说明

## 建议元数据

- Type: OpenClaw Skill
- Name: zaomeng-skill
- Display Name: 造梦技能
- License: MIT-0
- Category: Writing / Roleplay / Character Simulation

## 风险说明

- 这是一个以 prompt-first 资产为主的 skill 包
- skill 包内已携带 `requirements.txt`，声明 Python 依赖版本边界
- 仍依赖本地 Python 执行，以及 Python 包信任链：`PyYAML`，可选 `tiktoken`，可选 `ebooklib`
- 已包含显式安全策略

## 发布前检查

1. `SKILL.md` frontmatter 合法。
2. prompt-first helper 入口可以执行。
3. 输出规范与安全相关文件齐全。
4. 示例文件与当前 schema 一致。
5. 包内不包含凭证、密钥或其他敏感信息。

## 版本说明

- `4.1.6`：升级 skill 包版本，补齐当前发布 tag 到 `v2026.05.09`，让 `SKILL.md`、`.metadata.json`、示例文件与发布元数据继续保持一致。
- `4.1.5`：同步当前 skill 包版本元数据与中英文文档，补齐发布说明，确保打包与示例版本号一致。
- `4.1.4`：整理 skill 打包产物，确保从 `zaomeng-skill/` 目录生成的 `zaomeng-<version>.skill.zip` 不混入 `__pycache__`、`.pytest_cache`、`.mypy_cache` 等缓存目录，同时收紧 stdout 输出格式，避免 JSON 以外内容干扰 Windows CI，并尽量保持 ASCII-safe，降低 GitHub Actions 在 `cp1252` 环境下的编码问题。
- `4.1.3`：增强关系图谱导出，优先生成静态 SVG 并在 HTML 中直接内嵌，降低本地 `file://` 打开时 Mermaid 脚本受限导致图谱空白的概率，同时修正明细表布局挤压问题。
- `4.1.2`：补入 persona bundle materializer，支持在宿主只落盘 `PROFILE.generated.md` 后继续生成拆分人格文件与 `NAVIGATION.generated.md`，并同步补齐 skill 文档与安装回归测试。
- `4.1.1`：让 skill 包内 helper 脚本摆脱对仓库级 `src` 模块的依赖，补入包内最小 support 层，并收紧进度播报规则，避免向用户暴露大段内部思考与排障过程。
- `4.1.0`：对齐 `references/output_schema.md` 的最新字段定义，补全人物档案与关系图谱示例，并同步收紧关系抽取与人设纠错提示词。
- `4.0.1`：补充 skill 包内 `requirements.txt`，明确 Python 依赖版本边界，并将安装、清单与发布文档同步到依赖文件。
- `4.0.0`：移除 skill 包内置 runtime 与 CLI 入口，skill 资产收敛为宿主驱动的 prompts、references、examples 和 helper scripts，并统一产物为人物档案、关系结果、人物关系图谱与角色对话。
- `3.3.0`：明确 skill 以宿主驱动的 prompt-first 资产为核心，新增 excerpt 与 prompt payload helper scripts，并统一文档口径到宿主 LLM 工作流。
- `3.1.0`：将 prompt 引用从纯文本切换为 Markdown，对齐 Markdown-first 人格工作流，在 `references/output_schema.md` 中补充 26 维度人格覆盖说明，并新增 `references/style_differ.md` 与 `references/logic_constraint.md`，用于去同质化和防止人设崩坏。
- `3.0.0`：完成 skill 包内资产收敛，强化人物蒸馏、关系抽取与角色对话的一体化组织方式。
- `2.1.1`：将自动引导流程固定到外部 zaomeng 仓库的特定 commit `649f7466738f99d60c454e167835462215cffc7d`，降低运行时供应链漂移风险。
- `2.1.0`：调整早期引导流，统一 skill 资产与本地工程之间的衔接方式。
- `2.0.0`：切换到 Markdown-first 人格存储，引入导航/人格包与运行时记忆写入，并加入自然语言聊天意图路由与 distill-before-chat、act/observe 会话建立逻辑。
- `1.0.9`：重写早期 skill 文档，并统一 agent 侧调用约束。
- `1.0.8`：强化 agent 聊天规则，要求在任何 PTY 或 stdin 回退前必须优先使用 `--message`。
- `1.0.7`：补充早期单轮交互说明，并对齐 ClawHub 聊天规则。
- `1.0.6`：补充交互式聊天与需要确认的执行约束说明。
- `1.0.5`：让 ClawHub 打包 schema 和示例与当前按小说分组的本地工作流保持一致。

## 发布范围

- 默认发布的 skill 以 prompts、references、examples 和 helper scripts 为主。
- 发布说明应围绕宿主调用、人物蒸馏、关系抽取、人物关系图谱和角色对话展开。
