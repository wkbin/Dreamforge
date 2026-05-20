# 内部数据字典

更新时间：2026-05-20

这份文档只描述当前主线里最值得稳定下来的几类核心结构：

1. `run manifest`
2. `package manifest`
3. `dialogue session`
4. `session state`
5. `character snapshot`
6. `relation delta`
7. `runtime_state_overview`

目标不是列出每一个零碎字段，而是说明：

- 哪些字段是 source of truth
- 哪些字段是 derived view
- 这些结构分别服务于哪条主流程

## 1. Run Manifest

主文件来源：

- [creation.py](d:/work2/Dreamforge/src/web/run_ops/creation.py)
- [store.py](d:/work2/Dreamforge/src/web/manifest/store.py)
- [views.py](d:/work2/Dreamforge/src/web/manifest/views.py)

磁盘位置：

- `<runs>/<run_id>/run_manifest.json`

身份字段：

- `kind`: 当前固定为 `zaomeng_web_run`
- `schema_version`: 当前版本号
- `run_id`: 本地运行实例 id
- `novel_id`: 小说 id / 标题归一标识

主状态字段：

- `status`
  - 运行态真相之一
  - 常见值：`running` / `ready` / `failed` / `stopped`
- `success`
  - 整轮是否成功结束
- `entrypoint`
  - 当前 run 的来源，如 `webui` / `import` / `builtin`

时间字段：

- `created_at`
- `updated_at`
- `timing.started_at`
- `timing.completed_at`
- `timing.failed_at`
- `timing.stopped_at`
- `timing.elapsed_seconds`
- `timing.elapsed_text`

工作流字段：

- `locked_characters`
  - 本轮锁定待蒸馏的人物名单
- `progress`
  - 当前流程运行态真相之一
  - 记录当前阶段、当前人物、已完成数量、图谱状态、chunking 进度
- `capabilities`
  - 各能力位的状态，例如 `distill` / `export_graph` / `verify_workflow`
- `artifacts`
  - 运行产物索引
  - 包括 payload 路径、status 文件、角色目录、关系图、chunking 元信息
- `summary`
  - 更偏 UI / 列表展示的短摘要，不适合作为唯一真相来源
- `quality`
  - 质量与证据层视图
  - 用于提示哪些角色证据偏薄、是否触发 repair、是否发生 chunking
- `events`
  - 线性时间线记录
- `control`
  - 停止请求等控制态
- `webui`
  - 当前运行目录、输入目录、payload 目录、artifact 目录、workspace 根

source of truth（已落地）：

- 真正驱动业务判断时，优先依赖：
  - `status`
  - `progress`
  - `control`
  - `artifacts`
- `summary` 已收口为 derived projection（展示层）：
  - `summary.status_text` 由 `status/progress/control` 投影得到
  - `summary.graph_status` 由 `progress.graph_status`（必要时回退旧字段）投影得到
  - `summary.characters_total` / `summary.characters_completed` 由 `progress` 与 `locked_characters` 投影得到
  - `summary.elapsed_text` 由 `timing.elapsed_text` 投影得到

实现入口：

- `src/web/run_ops/state.py`
  - `derive_summary_status_text`
  - `derive_summary_graph_status`
  - `project_manifest_summary`

约束：

- 不允许再以 `summary.*` 字段作为核心流程分支判定条件
- 新增业务判定时，优先读取 `status/progress/control/artifacts`

## 2. Package Manifest

主文件来源：

- [packages.py](d:/work2/Dreamforge/src/web/run_ops/packages.py)

压缩包内路径：

- `package_manifest.json`

字段：

- `kind`
  - 当前固定为 `zaomeng_web_run_package`
- `schema_version`
  - 小说包 schema 版本
- `package_id`
  - 包 id
- `title`
  - 展示标题
- `novel_id`
  - 小说 id
- `original_run_id`
  - 导出时来源的 run id
- `status`
  - 导出时 run 状态快照
- `character_count`
  - 导出时角色数
- `has_relation_graph`
  - 导出时是否带关系图谱
- `summary.status_text`
  - 导出时运行态投影（由 run 真相字段推导）
- `summary.graph_status`
  - 导出时图谱态投影（由 run 真相字段推导）
- `exported_at`
- `updated_at`
- `builtin`
  - 是否作为内置小说包发布

兼容冻结规则（2026-05-20）：

- 读取入口统一走 `src/web/run_ops/packages.py::_read_package_manifest` 与 `_normalize_package_manifest`
- 当前支持版本：`0`（legacy）与 `1`（current）
- 未知版本：直接拒绝（`schema_version` 不在支持集合时抛错）
- `schema_version=0` 迁移到 current 规则：
  - 缺失 `summary.status_text` 时回填为 `status`
  - 缺失 `summary.graph_status` 时按 `has_relation_graph` 回填：`complete` / `pending`
  - 缺失 `builtin` 回填 `false`
  - 缺失或非法 `character_count` 回填 `0`
- 归一化后对外统一输出 `schema_version=1`（逻辑视角为 current schema）
- 导入流程在解压前先读取并校验 `package_manifest.json`，确保未知版本不会进入后续导入逻辑

定位：

- 这是“包级元数据”，不是完整运行态
- 它应该只回答“这包是什么、够不够试玩、值不值得导入”

## 3. Dialogue Session

主文件来源：

- [service.py](d:/work2/Dreamforge/src/web/chat/service.py)

磁盘位置：

- `<runs>/<run_id>/dialogue/<session_id>/session.json`

身份字段：

- `kind`: 当前固定为 `zaomeng_dialogue_session`
- `session_id`
- `run_id`
- `novel_id`

会话配置字段：

- `mode`
  - `observe` / `act` / `insert`
- `participants`
  - 当前会话主参与角色
- `controlled_character`
  - 仅 `act` 模式使用
- `scene_card`
- `scene_card_id`
- `scene_history`
- `self_insert`
- `self_card_id`
- `carried_memory_summary`
- `branch_origin`

运行字段：

- `history`
  - 原始对话历史
- `pending_turn`
  - 当前尚未收口的一拍
- `state`
  - 会话运行态真相
- `created_at`
- `updated_at`
- `status`

derived 输出字段：

- `transcript`
- `scene_progress`
- `relation_delta`
- `character_snapshots`
- `event_signals`
- `relation_matrix`
- `last_entry_preview`
- `session_card`
- `pending_turn_summary`
- `session_memory_summary`
- `runtime_state_overview`
- `file_urls`

source of truth 建议：

- 真相字段：
  - `history`
  - `pending_turn`
  - `state`
  - `scene_card`
  - `participants`
- 投影视图：
  - `scene_progress`
  - `relation_delta`
  - `character_snapshots`
  - `runtime_state_overview`
  - `session_memory_summary`

## 4. Session State

主文件来源：

- [session-state-v1.md](d:/work2/Dreamforge/docs/session-state-v1.md)
- [service.py](d:/work2/Dreamforge/src/web/chat/service.py)

`state` 是会话运行态唯一真相。

当前 canonical shape：

```json
{
  "version": 1,
  "scene": {},
  "presence": {},
  "progression": {},
  "relations": {},
  "characters": {},
  "signals": {},
  "memory": {}
}
```

各子块含义：

- `scene`
  - 当前地点、时间提示、氛围摘要、当前推进说明
- `presence`
  - 谁在场、谁离场
- `progression`
  - 当前一拍是否成熟、是否该转场、世界张力如何
- `relations`
  - 基线关系矩阵 + 本局增量变化
- `characters`
  - 会话级角色快照
- `signals`
  - 最近事件信号
- `memory`
  - 当前会话摘要与压缩态

稳定性分级（2026-05-20）：

- `state.version`: `stable`
  - 仅在发生明确破坏性迁移时升级版本号
- `state.scene`: `stable`
  - 允许在保持语义不变前提下增补可选字段
- `state.presence`: `stable`
  - 参与者在场/离场语义保持稳定
- `state.progression`: `evolving`
  - 节奏与转场策略仍在持续打磨，字段可能继续细化
- `state.relations.matrix`: `stable`
  - 作为基线关系视图，优先保持向后兼容
- `state.relations.delta`: `evolving`
  - 会话增量表达仍会按对话质量优化而迭代
- `state.characters.snapshots`: `evolving`
  - 快照字段会随演出连贯性需求扩展
- `state.signals`: `experimental`
  - 事件信号仍处于探索期，不保证字段长期稳定
- `state.memory.summary`: `evolving`
  - 压缩摘要结构将继续围绕长会话质量调整

升级影响约定：

- `stable`：新增可选字段可接受；删除/重命名需显式迁移说明
- `evolving`：允许增补或收敛字段，但需保持旧字段至少一版兼容期
- `experimental`：可能快速调整；调用方应做缺省容错与非阻塞降级

规则：

- 新逻辑优先写入 `state`
- 顶层 `scene_progress` / `relation_delta` / `character_snapshots` 是兼容投影

## 5. Character Snapshot

来源：

- `state.characters.snapshots.<character_name>`

定位：

- 描述“这个角色在当前会话这一阶段是什么状态”
- 不是角色永久档案，不是 persona card 的替代品

当前常见字段：

- `present_state`
  - `onstage` / `offstage`
- `scene_location`
- `time_hint`
- `mood`
- `interaction_state`
- `focus`
- `last_target`
- `last_event`
- `updated_at`

使用边界：

- 适合驱动当前一幕的演出连贯性
- 不适合回写到人物档案本体

## 6. Relation Delta

来源：

- `state.relations.delta`

定位：

- 只记录“本会话里”的关系变化
- 不是角色一生的最终关系裁决

当前常见字段：

- `trust`
- `affection`
- `hostility`
- `ambiguity`
- `momentum`
- `last_event`
- `last_actor`
- `last_target`
- `evidence_lines`

键形态：

- 常见为人物对组合键，例如 `甲::乙`

规则：

- 它是会话增量，不是全局关系库
- 真正展示时可以和 `relation_matrix` 合并，但不要丢掉“这是 session delta”这个语义

## 7. Runtime State Overview

来源：

- [service.py](d:/work2/Dreamforge/src/web/chat/service.py)

定位：

- 专门给前端展示的轻量视图
- 它不是新真相层，而是 `state` 的 presentation projection

典型内容：

- pills
  - 地点、时间、氛围、推进度、是否可转场
- character_rows
  - 每位角色当前是否在场、当前情绪 / 互动状态 / 关注对象
- relation_rows
  - 本局里最值得看的关系变化
- signals
  - 最近事件信号的短列表

规则：

- 保持短、稳、可排序
- 不承担写回职责

## 8. 哪些字段最容易混

最容易混淆的几组概念：

1. `summary` vs `progress`
   - `progress` 更像运行态真相
   - `summary` 更像 UI 摘要
2. `state` vs 顶层 session 派生字段
   - `state` 才是 canonical runtime state
   - 顶层 `scene_progress` / `relation_delta` / `character_snapshots` 是兼容投影
3. `character snapshot` vs 人物档案
   - snapshot 是会话态
   - 人物档案是长期资产
4. `relation delta` vs relation graph
   - delta 是本局变化
   - graph / relation_matrix 更接近基线结构

## 9. 后续建议

下一轮如果继续收口，最值得继续补的是：

1. 给 `run manifest` 明确标注 source-of-truth 字段和 derived 字段
2. 给 `package manifest` 写正式兼容策略
3. 给 `session state` 补一版字段稳定性分级
4. 给 skill 同步一份精简版数据契约
