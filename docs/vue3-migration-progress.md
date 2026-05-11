# Vue 3 渐进迁移进度

## 当前分支

- `feat/vue3-gradual-migration`

## 已完成

### 基础设施

- 本地引入 Vue 3 vendor 文件
- 新增 `legacy-bridge.js`
- 新增 `webui-api.js`
- bootstrap 已支持按顺序加载 Vue island 脚本
- bridge snapshot 已覆盖：
  - run / session
  - workflow
  - character overview
  - redistill draft / recommendation
  - composer
  - persona review
  - relation details
  - self card editor

### 已落地的 Vue islands

1. 增量蒸馏工作台
2. 人物校对 modal
3. 聊天输入区 / 快捷回复区
4. 关系明细 modal
5. 角色卡编辑器 modal
6. 新建会话 / 入场设置区
7. 工作流概览面板
8. 工作流优先补稳面板
9. 工作流入口面板
10. 工作流顶部进度与动作条
11. 工作流角色就绪列表
12. 人物档案页主体
13. 书页来源区
14. 运行时间线区
15. 书架列表区
16. 模型设置弹窗主体

## 本轮额外收口

- 新增 `editor-schemas.js`
- 新增 `editor-vue-components.js`
- `legacy action bridge` 读写已统一到共享 helper
- 人物校对与角色卡编辑器的字段 schema 已统一
- 人物校对与角色卡编辑器的字段卡片模板已统一到共享 Vue 组件
- 关键字段、扩展字段、字段标签、占位文案、必填项不再散落多处
- 聊天输入区补上“本地乐观草稿 + bridge 回刷校准”，减少输入后立刻发送时的草稿滞后风险
- 工作流“概览”区已用共享派生状态切成独立 Vue island，开始从核心交互区向外围摘要区扩张
- 工作流“下一刀”区已切成独立 Vue island，优先级排序与动作按钮开始复用统一派生状态和 action bridge
- 工作流“入口”区已切成独立 Vue island，关系图谱、最近会话与快速开局开始复用统一 view state 和入口动作桥
- 新增 `work-overview-vue-shared.js`，把 workflow 三块 island 的 bridge 订阅、legacy 隐藏与 action bridge 读取收进共享 helper
- 工作流顶部 `hero / metrics / progress / actions` 已切成独立 Vue island，并开始复用 `bookshelf.js` 抽出的顶部状态 builder
- 工作流“角色就绪”区已切成独立 Vue island，角色列表开始复用统一就绪度 view state 与入口动作桥
- 新增 `work-overview-state.js`，把顶部条、角色就绪与优先补稳等高复用 builder 从 `bookshelf.js / run-detail.js` 抽到独立状态模块
- `work-overview-state.js` 已继续收口第二批 workflow 派生逻辑，`summary / quality / recommendation / graph / session preview / entry` 也开始由共享状态模块统一产出
- `run-detail.js` 现已把上述第二批 builder 改成薄包装，Vue island 与旧 DOM 渲染正式共用同一份 workflow 派生状态
- 新增 `work-overview-actions.js`，把 run overview 的推荐动作、顶部动作、角色列表动作、会话预览动作从 `run-detail.js` 中独立出来
- workflow 相关的全局 builder 导出已回收到 `work-overview-state.js`，`run-detail.js` 进一步退回为 legacy 渲染宿主而不是状态/动作出口中心
- 新增 `work-overview-legacy-render.js`，把 workflow 的 legacy 卡片 DOM 渲染从 `run-detail.js` 再拆出一层
- `run-detail.js` 里的角色就绪、优先补稳、关系图摘要、最近会话预览等 workflow 渲染函数已收成真正的薄壳转发
- 新增 `character-overview-state.js`，把人物档案页的字段常量、健康度/证据/信号等纯派生逻辑从 `run-detail.js` 中抽离
- `run-detail.js` 里的 character overview 已开始改用共享 state builder，后续可以继续把渲染层和动作层拆分
- 新增 `character-overview-legacy-render.js`，把人物档案页的大部分 legacy DOM 渲染从 `run-detail.js` 中独立出来
- `run-detail.js` 里的人物档案展示函数已大多收成薄壳，当前剩余重心开始转向保存、补全、增量蒸馏与入场动作
- 新增 `character-overview-actions.js`，把人物档案页的保存、补全、增量蒸馏、入场、原档打开等动作从 `run-detail.js` 中独立出来
- `run-detail.js` 现在更多只保留人物档案的编排入口和兼容壳，人物档案线已经具备 `state + legacy-render + actions` 三层结构
- 新增 `character-overview-vue-island.js`，人物档案页主体已经正式切成 Vue island，关键字段编辑、AI 补全、信号卡片、时间线与细调折叠不再依赖 legacy DOM 直接拼装
- `character-overview-actions.js` 已补齐 direct method 形态，现可同时服务旧事件代理和 Vue 直接调用，避免新旧两套业务逻辑分叉
- bridge snapshot 已补入 `currentCharacterOverview`，人物档案 Vue island 不再依赖旧脚本私有作用域读状态
- 新增 `run-detail-support-state.js`，把 source history / redistill plan / timeline 等书卷支撑视图的派生状态与格式化 helper 从 `run-detail.js` 中抽离
- 新增 `run-detail-support-legacy-render.js`，把上述支撑视图的 legacy DOM 渲染再拆出一层，`run-detail.js` 继续向 orchestration 收口
- 新增 `source-history-vue-island.js`，书页来源区已切成独立 Vue island，展开/收起动作开始通过 action bridge 驱动
- 新增 `run-timeline-vue-island.js`，运行时间线区已切成独立 Vue island，不再依赖 legacy DOM 直接拼接事件列表
- 新增 `persona-review-legacy.js`，人物校对 legacy 兼容层已从 `run-detail.js` 中独立出去，继续压缩主编排文件
- 新增 `relation-details-legacy.js`，关系明细 legacy 兼容层也已从 `run-detail.js` 中独立出去
- 质量快照 legacy fallback 已继续收口到 `work-overview-legacy-render.js`，`run-detail.js` 不再亲自维护这段摘要 DOM
- 新增 `bookshelf-vue-island.js`，书架列表与空状态已经正式切成 Vue island，打开书卷与删除书卷开始由 Vue 宿主管理
- 新增 `bookshelf-state.js` 与 `bookshelf-legacy-render.js`，书架也已形成 `state + legacy-render + vue-island` 三层结构
- bridge snapshot 已补入 `allRuns`，书架 Vue island 不需要再从旧 DOM 反推列表态
- `webui-api.js` 已补充删除书卷能力，书架 Vue island 不必直接拼装原始请求
- 新增 `model-settings-vue-island.js`，模型设置弹窗主体已切成 Vue island，保存动作改走 API 层，旧表单退成 fallback
- `run-detail.js` 本轮已继续收缩到约 `1228` 行，剩余内容更集中在总线编排、少量共享 helper 与兼容入口

## 当前架构判断

这条迁移路线已经验证成立：

- 不需要整站重写
- 不需要先上 Vite
- 不需要先改后端 API

当前最适合继续的方式仍然是：

- 保留 fragments 外壳
- 保留旧逻辑作为 action host / fallback
- Vue 只接管高交互区域

## 还值得继续优化的点

### 1. 抽共享的字段渲染 helper

目前 `persona-review-vue-island.js` 和 `self-card-vue-island.js` 已共享 schema，
但模板层仍有一部分重复。后续可以考虑继续抽：

- schema-driven field renderer
- schema-driven section renderer

这样后面新增字段会更轻。

### 2. 为 islands 增加更明确的加载/错误边界

当前多数 island 已有状态文案，但还可以进一步统一：

- loading skeleton
- empty state
- retry action

### 3. 继续迁移剩余外围区块

还可考虑继续 Vue 化：

- 角色卡预览区
- 工作流顶部条
- 书架详情中的部分摘要卡片
- 关系图 / 时间线等后续扩展面板

## 建议的下一步顺序

1. 继续处理 `run-detail.js` 里残留的少量共享 helper / wrapper，进一步逼近真正 orchestrator
2. 评估 `应用更新弹窗 / 头部栏 / 侧边辅助区` 哪块最适合作为下一层 Vue 化入口
3. 继续抽共享 renderer / bridge helper，优先降低重复模板和直连全局状态

## 回归状态

最近一次验证结果：

- `node --check` 通过
- `py -3 scripts/dev_checks.py` 通过
- 单测通过，保留既有 skipped 项
- 最近一次完整回归为 `156 passed / 18 skipped`
