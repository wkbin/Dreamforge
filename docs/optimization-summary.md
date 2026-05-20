# 优化项汇总（来自 docs）

更新时间：2026-05-20

本清单汇总自以下文档中的“后续建议 / 后续收口方向 / 未完成项”：

- `docs/stage-closure-checklist.md`
- `docs/manifest-compatibility.md`
- `docs/data-dictionary.md`

## P0（优先执行）

1. 主流程状态反馈统一  
   - 统一 loading / 成功 / 失败 / 下一步建议文案规范。  
   - 失败文案必须说明“是否影响聊天主流程”。  
   - 成功文案统一给出下一步动作建议。

2. 跨平台主流程实机回归清单  
   - 覆盖 Windows / WSL / Linux / Termux 的安装、更新、运行、导入导出链路。  
   - 将回归项与发布流程绑定，作为发版前 gate。

3. manifest source-of-truth 与 derived 字段彻底拆分  
   - [x] `run_manifest.json` 明确真相字段与投影视图字段边界。  
   - [x] 避免使用 `summary` 决策核心流程（后端核心流程 + 前端关键判定已切到 `status/progress/control`）。

## P1（主流程稳定性）

1. 对话自然度继续打磨  
   - 时间推进、离场/回场、场景推进从“可用”提升到“自然”。  
   - 继续减少 observe 模式“推得生硬”的情况。

2. 对话压缩质量提升  
   - 重点验证长会话稳定性。  
   - 对近期承诺、冲突、动作、重大事件、当前目标、未收线摘要继续优化。

3. 前端 dual-path 收口  
   - 持续减少 legacy / Vue 双轨残留，降低维护复杂度与状态漂移风险。

## P1（资产与兼容）

1. package manifest 正式兼容策略冻结  
   - [x] 定义 schema version 迁移规范与版本演进规则。  
   - [x] 明确旧字段迁移与默认值策略。

2. 缺失 artifact 降级策略统一入兼容层  
   - [x] graph / payload / 可选产物缺失时统一降级说明与行为。  
   - [x] 兼容逻辑集中到 manifest compatibility layer，避免业务模块散落兜底。

3. 字段语义迁移统一治理  
   - [x] 路径问题、相对路径换算、导入后重写继续走兼容层。  
   - [x] 字段语义迁移已形成固定入口与规范（`apply_imported_run_semantics`）。

## P2（契约与文档）

1. session state 字段稳定性分级  
   - [x] 为 `state` 各子块标注稳定级别（stable / evolving / experimental）。  
   - [x] 给调用方明确升级影响面。

2. skill 侧精简数据契约  
   - [x] 与 Web UI 对齐 canonical 字段，不重复兼容补丁。  
   - [x] 明确哪些字段是必需、哪些字段是可选降级。

3. 运行期边界继续收口  
   - [x] 安装/运行/更新/导入导出职责边界从文档落到代码目录与模块职责。  
   - [x] 降低后续“边界继续散开”风险。

## 建议执行顺序（两周滚动）

1. 主流程状态反馈统一 + 发布回归 gate（P0）
2. manifest 真相/投影拆分 + 兼容层补全（P0/P1）
3. 对话自然度与压缩质量提升（P1）
4. 前端 dual-path 收口（P1）
5. 契约稳定性分级与文档固化（P2）
