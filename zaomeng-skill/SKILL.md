---
name: zaomeng-skill
description: 用于中文小说人物蒸馏、关系抽取、关系图谱导出与角色对话准备；当宿主需要基于小说内容生成结构化人物档案、关系结果或多角色对话上下文时使用。
license: MIT-0
compatibility: 需要宿主支持 Markdown skill 目录、YAML frontmatter，以及本 skill 内置 Python helper
  scripts 所需的本地 Python 运行环境。
metadata:
  version: 4.1.7
  hostMode: llm-first
  releaseTag: v2026.05.11
---

# zaomeng-skill

| 项目 | 内容 |
| --- | --- |
| 名称 | `zaomeng-skill` |
| 类型 | ClawHub / Host-managed skill |
| 核心模式 | LLM-first |
| 适用场景 | 人物蒸馏、人物包物化、关系图谱导出、角色 `act` / `insert` / `observe` |
| 宿主职责 | 调用宿主 LLM，负责最终生成与对话推进 |
| skill 职责 | 准备 prompt payload、物化人物包、导出图谱、校验产物、维护运行状态，并提供角色卡/人物补全/对话建议 helper |

## 1. 定位

- 这是一个宿主驱动的 prompt-first skill。
- 宿主负责实际调用 LLM；skill 负责把任务整理成标准输入、标准产物和标准状态。
- skill 的主路径是 `prompts + helper tools + run_manifest.json`，不是内嵌 chat CLI。
- 对话阶段除了宿主直读人物包，也可以调用 skill helper 来生成角色卡、人物字段补全 payload、以及 `act` / `insert` / `observe` 的自动回复建议 payload。

## 2. 宿主能力契约

宿主侧只需要理解四个标准能力，以及三组对话 helper：

| 能力 | 入口 | 作用 | 标准成功标记 |
| --- | --- | --- | --- |
| `distill` | `tools/build_prompt_payload.py --mode distill` | 生成蒸馏 payload，等待宿主 LLM 产出 `PROFILE.generated.md` | capability status `status=ready, success=true` |
| `materialize` | `tools/materialize_persona_bundle.py` | 把 `PROFILE.generated.md` 物化为完整人物包 | `ARTIFACT_STATUS.generated.json` + capability status |
| `export_graph` | `tools/export_relation_graph.py` | 导出人物关系图谱 HTML / Mermaid / SVG | `<relations>.status.json` + capability status |
| `verify_workflow` | `tools/verify_host_workflow.py` | 校验整条宿主工作流产物是否完整 | capability status `status=complete, success=true` |

对话 helper：

| helper | 入口 | 作用 |
| --- | --- | --- |
| `self_card` | `tools/manage_self_card.py` | 创建 / 保存 / 读取 / 删除 self-insert 角色卡，并生成随机角色卡 prompt payload |
| `persona_autofill` | `tools/build_persona_autofill_payload.py` | 为人物校对单字段生成宿主可调用的补全 payload，并解析模型返回 |
| `dialogue_suggestion` | `tools/build_dialogue_suggestion_payload.py` | 为 `act` / `insert` / `observe` 生成自动回复建议 payload，并提供压缩重试版本 |

所有能力都应该满足：

- 有明确输入
- 有 JSON 输出
- 有 sidecar status 文件
- 有 `success` 布尔值
- 可选更新 `run_manifest.json`

能力总览集中定义在：

- `references/capability_index.md`
- `examples/host_workflow_example.md`

`distill` 默认支持增量蒸馏：

- 如果 `data/characters/<novel_id>/<角色名>/` 已存在人物包，`tools/build_prompt_payload.py --mode distill` 会自动把已有档案并入 `request.existing_profiles`
- `request.update_mode` 会自动落成 `incremental`
- `run_manifest.json` 的 `artifacts.distill_context` 会记录本次是 `create` 还是 `incremental`，以及命中的已有角色数量

`distill` 与 `relation` 现在也默认支持长篇自动分批：

- 小文本保持单次 payload，不改变既有调用方式
- 当 excerpt 过长时，payload 会额外给出 `chunks[]`
- 宿主按 `chunks[]` 顺序调用 LLM，收集每块局部草稿
- 然后再按 `merge_payload` 做一次合并，得到最终 `PROFILE.generated.md` 或 `RELATION_GRAPH`
- `request.chunk_mode`、`meta.chunk_count`、`meta.merge_required` 会明确告诉宿主当前是否处于分批模式

## 3. 标准运行状态

宿主如果要跑完整蒸馏链路，先初始化一个 `run_manifest.json`：

```bash
python tools/init_host_run.py --novel <路径> --characters A,B,C --output <run_manifest.json>
```

`run_manifest.json` 是宿主侧的统一索引，记录：

- 当前阶段
- 已锁定角色
- 当前正在处理的角色
- 已完成数量
- 关系图导出状态
- 各能力 status 文件
- 人物目录
- 关系图 HTML / SVG / Mermaid 路径
- 最终 workflow 校验结果
- 增量蒸馏上下文（`update_mode`、已有档案数量、已有档案目录）
- 分批执行概览（`progress.chunking`、`summary.chunking`）

## 4. 标准进度阶段

宿主侧统一使用这些阶段名：

- `characters_locked`
- `distill_payload_ready`
- `relation_payload_ready`
- `chunk_started`
- `chunk_completed`
- `merge_started`
- `merge_completed`
- `character_started`
- `character_completed`
- `graph_export_started`
- `graph_export_completed`
- `workflow_verified`

如果宿主要主动播报当前角色和进度，直接调用：

```bash
python tools/update_run_progress.py --run-manifest <run_manifest.json> --stage character_started --character 林黛玉 --message "正在蒸馏林黛玉"
```

如果是长篇自动分批流程，也可以写入当前块进度：

```bash
python tools/update_run_progress.py --run-manifest <run_manifest.json> --stage chunk_started --message "正在执行第 1 块" --chunk-capability distill --chunk-mode chunked --chunk-count 6 --current-chunk 1 --chunk-label 前段-1 --chunk-status running --merge-required --merge-status pending
```

写入后，宿主可直接从 `run_manifest.json` 读取：

- `progress.chunking.distill.current_chunk`
- `progress.chunking.distill.chunk_count`
- `progress.chunking.distill.current_label`
- `summary.chunking.distill`

## 5. 标准流程

1. 初始化 `run_manifest.json`
2. 运行 `distill` 能力，生成蒸馏 payload
3. 如果 payload 含 `chunks[]`，宿主先逐块生成局部草稿，再执行 `merge_payload`
4. 否则直接为每个角色生成 `PROFILE.generated.md`
5. 每个角色生成后立刻运行 `materialize`
6. 如果 relation payload 含 `chunks[]`，也先逐块抽取，再执行 `merge_payload`
7. 宿主 LLM 生成关系结果后运行 `export_graph`
8. 运行 `verify_workflow`
9. 宿主向用户展示：
   - 人物目录
   - 关系图 HTML / SVG
   - 状态摘要
   - 可进入 `act` / `insert` / `observe`

## 6. 推荐宿主串联方式

### A. 初始化运行

```bash
python tools/init_host_run.py --novel <路径> --characters A,B --output <run_manifest.json>
```

### B. 准备 distill payload

```bash
python tools/build_prompt_payload.py --mode distill --novel <路径> --characters A,B --output <distill_payload.json> --run-manifest <run_manifest.json>
```

如果小说较长，输出 JSON 会自动包含：

- `chunks[]`：每一块都已经是可直接交给宿主 LLM 的局部 payload
- `merge_payload`：宿主把所有 chunk 草稿结果塞回 `request.chunk_drafts` 后，再调用一次用于最终合并
- `host_plan`：宿主串联建议，包括 `single_pass` 或 `sequential_chunks_then_merge`

如果宿主要显式指定已有角色目录，或强制切换创建 / 增量模式，可加：

```bash
python tools/build_prompt_payload.py --mode distill --novel <路径> --characters A,B --characters-root <data/characters 或 data/characters/<novel_id>> --update-mode auto|create|incremental --output <distill_payload.json> --run-manifest <run_manifest.json>
```

### C. 角色开始 / 完成进度

```bash
python tools/update_run_progress.py --run-manifest <run_manifest.json> --stage character_started --character A
python tools/update_run_progress.py --run-manifest <run_manifest.json> --stage character_completed --character A
```

### D. 物化人物包

```bash
python tools/materialize_persona_bundle.py --profile-file <character-dir/PROFILE.generated.md> --run-manifest <run_manifest.json>
```

### E. 导出关系图谱

```bash
python tools/export_relation_graph.py --relations-file <relations.md> --run-manifest <run_manifest.json>
```

### F. 校验工作流

```bash
python tools/verify_host_workflow.py --characters-root <characters/<novel_id>> --relations-file <relations.md> --run-manifest <run_manifest.json>
```

## 7. 最终产物

完整 run 结束后，宿主应该直接拿到：

- `run_manifest.json`
- 每个角色的人物目录
- distill 增量上下文：
  - `artifacts.distill_context.update_mode`
  - `artifacts.distill_context.existing_character_count`
  - `artifacts.distill_context.existing_profile_paths`
- 每个角色的 `ARTIFACT_STATUS.generated.json`
- 关系图：
  - `*_relations.html`
  - `*_relations.svg`
  - `*_relations.mermaid.md`
  - `*.status.json`
- workflow 校验 JSON

## 8. 对话接管

当人物包和关系图准备完成后，宿主即可进入：

- `act`：指定角色代入发言，既可单聊，也可直接参与多人群聊
- `insert`：用户以“自己”的身份进入小说场景，角色按人设与场景身份回应用户；首次进入应建立轻量身份卡
- `observe`：进入群聊模式，但用户不代入具体角色，只观察多角色对话推进

这里的对话由宿主直接驱动，skill 不提供单独的 `chat` CLI 能力。宿主应直接使用：

- 人物包目录
- `PROFILE.md` / 拆分人格文件 / `MEMORY.md`
- 关系图谱及关系 markdown
- `run_manifest.json`
- `references/output_schema.md`、`references/style_differ.md`、`references/logic_constraint.md`

如果宿主需要角色卡、人物字段补全或对话建议 helper，可直接调用：

- `python tools/manage_self_card.py --mode blank|list|get|save|delete|build-random-payload|parse-random-response`
- `python tools/build_persona_autofill_payload.py --persona-dir <角色目录> --field <字段名> --strategy auto|model_knowledge|web_fallback [--collect-web]`
- `python tools/build_dialogue_suggestion_payload.py --context-file <context.json>`

宿主结束提示建议直接说清楚：

- 人物档案已完成
- 关系图谱已生成
- 可以查看图谱
- 可以进入 `act`
- 可以进入 `insert`
- 可以进入 `observe`
