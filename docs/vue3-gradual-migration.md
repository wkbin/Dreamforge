# Web UI Vue 3 渐进迁移方案

## 目标

在不打断当前功能迭代的前提下，把现有 Web UI 从传统 `HTML + CSS + JavaScript` 逐步迁到 `Vue 3`，优先解决以下问题：

- 全局状态分散，依赖 `currentRun` / `currentDialogueSession` / `selectedSelfCardId` 等变量手动同步
- 复杂界面依赖大量 `renderXxx()`、`toggle()`、`setText()`，新增功能时容易出现状态漏刷
- 模块边界偏弱，`run-detail.js`、`main.js`、`core.js` 都在同时读写同一批状态
- 后续还会继续新增“增量蒸馏工作台、人物校对、聊天增强、角色卡”等高交互能力，原生 DOM 维护成本会持续走高

## 现状判断

当前 Web UI 已经属于“中等复杂度的单页交互应用”，但还没有正式的组件系统或状态层：

- 入口为 [index.html](/d:/work2/Dreamforge/src/web/static/index.html) + [bootstrap.js](/d:/work2/Dreamforge/src/web/static/js/bootstrap.js)
- 页面通过 fragments 组装：`header`、`workspace-shell`、`workflow-strip`、`main-shell`、`settings-modal`
- 核心运行态由全局变量维护，定义在 [core.js](/d:/work2/Dreamforge/src/web/static/js/core.js)
- 主要交互逻辑分散在：
  - [workflow.js](/d:/work2/Dreamforge/src/web/static/js/workflow.js)
  - [run-detail.js](/d:/work2/Dreamforge/src/web/static/js/run-detail.js)
  - [dialogue.js](/d:/work2/Dreamforge/src/web/static/js/dialogue.js)
  - [main.js](/d:/work2/Dreamforge/src/web/static/js/main.js)

这说明它已经具备改用 Vue 的价值，但**不适合一次性整体重写**。

## 迁移原则

### 1. 后端接口保持不动

本轮只动前端渲染与状态组织，不改 FastAPI 路由设计，不改现有 Web API 数据结构。

### 2. 先岛式迁移，再看是否整体 SPA 化

先让 Vue 以“局部挂载”的方式接管某些高复杂度区域，而不是整页重写：

- Vue 组件只接管自己的 mount 点
- 旧页面继续存在
- 旧逻辑与新逻辑通过桥接层共存

### 3. 先建稳定边界，再迁复杂模块

优先建立两层边界：

- `Legacy UI State Bridge`
- `API Access Layer`

这样后续 Vue 岛组件可以只依赖桥接状态和 API 封装，而不直接读写旧时代 DOM 工具函数。

## 推荐迁移顺序

### Phase 0：铺路

目标：不改视觉与主流程，只补“可迁移基础设施”。

本轮应完成：

- 建立前端状态桥接层
- 对外暴露当前运行态快照和订阅机制
- 在 bootstrap 中登记可挂载的前端 host
- 约定 Vue 岛组件未来只通过桥接层取状态

### Phase 1：试点 Vue 岛

目标：选一个状态复杂但边界清晰的模块，先做 Vue 局部接管。

当前分支已启动第一块试点：

- `增量蒸馏工作台（上半区）`
- 接管内容：
  - 本轮计划摘要
  - 最近变化摘要
  - 推荐片段区
- 保留旧逻辑：
  - 文件上传
  - 角色输入
  - 继续整理按钮

当前分支也已启动第二块试点：

- `人物校对 modal`
- 接管内容：
  - 人物切换
  - 关键字段编辑
  - 二级字段细调
  - AI 补全
  - 保存写回
- 保留旧逻辑：
  - modal 外壳
  - 关闭与滚动锁

当前分支现已完成第三块试点：

- `聊天输入区 / 快捷回复区`
- 接管内容：
  - 输入类型切换
  - 输入框草稿
  - 自动续写按钮
  - 观察模式快捷回复
  - 发送按钮与 loading 态展示
- 保留旧逻辑：
  - 实际发送/续写请求
  - optimistic transcript 更新
  - 会话切换后的底层状态同步

当前分支也已完成第四块试点：

- `关系明细 modal`
- 接管内容：
  - 关系条目列表展示
  - 分值与关系摘要编辑
  - 保存态反馈
  - 证据句回看
- 保留旧逻辑：
  - 关系明细数据拉取入口
  - 旧版 `renderRelationDetails()` 作为回刷兼容层

当前分支也已完成第五块试点：

- `角色卡编辑器 modal`
- 接管内容：
  - 新建 / 编辑角色卡草稿
  - AI 随机生成
  - 必填校验
  - 保存 / 删除
- 保留旧逻辑：
  - 外部“新建角色卡 / 编辑当前卡”入口
  - 角色卡列表与选卡预览刷新

当前分支也已完成第六块试点：

- `新建会话 / 入场设置区`
- 接管内容：
  - 入场模式切换
  - 参与人物选择
  - 扮演角色输入
  - 以自己入场时的角色卡选择与预览
  - 进入会话提交
- 保留旧逻辑：
  - 会话创建请求
  - 预填逻辑
  - 既有角色卡打开/编辑入口

当前分支现已完成第七块试点：

- `工作流概览面板`
- 接管内容：
  - 一句话概览
  - 最近进展
  - 推荐动作
  - 蒸馏质量快照
- 保留旧逻辑：
  - 推荐动作实际执行
  - run 详情轮询与回刷
  - 其他工作流面板的既有 DOM 渲染

当前分支现已完成第八块试点：

- `工作流优先补稳面板`
- 接管内容：
  - 角色优先级排序
  - 优先原因与行动建议
  - 打开角色页 / 增量蒸馏动作
- 保留旧逻辑：
  - 角色详情加载
  - 增量蒸馏打开与表单预填
  - 其他工作流卡片的既有 DOM 渲染

当前分支现已完成第九块试点：

- `工作流入口面板`
- 接管内容：
  - 关系图谱状态与链接
  - 最近会话预览与恢复
  - 三种快速开局入口
- 保留旧逻辑：
  - 最近会话真正恢复
  - 快速开局流程
  - 图谱文件与关系详情的底层打开逻辑

当前分支现已完成第十块试点：

- `工作流顶部进度与动作条`
- 接管内容：
  - 顶部进度摘要
  - 状态横幅
  - 指标卡片与进度卡片
  - 主次动作按钮
- 保留旧逻辑：
  - 继续蒸馏 / 校对 / 开聊 / 停止等实际动作
  - 书架返回与加载占位
  - 运行态轮询与底层 DOM 回刷兼容

当前分支现已完成第十一块试点：

- `工作流角色就绪列表`
- 接管内容：
  - 角色就绪卡片
  - 展开 / 收起
  - 打开角色页
- 保留旧逻辑：
  - 角色详情真实加载
  - 人物校对 / 角色页里的后续动作
  - 运行态轮询与底层 DOM 回刷兼容

当前分支同时已进入下一轮“共享状态抽取”收口：

- `work-overview-state.js`
- 已统一承接内容：
  - 顶部概览 / 动作条派生状态
  - 角色就绪与优先补稳派生状态
  - 工作流概览区 `summary / quality / recommendation`
  - 工作流入口区 `graph / session preview / quick modes`
- 当前收益：
  - `bookshelf.js` 与 `run-detail.js` 不再各自维护同一套 workflow 派生逻辑
  - Vue islands 与 legacy DOM 渲染开始真正共享一份 builder，而不是“看起来复用、实际双写”

当前分支也已开始把 workflow 动作层独立出去：

- `work-overview-actions.js`
- 已统一承接内容：
  - 推荐动作分发
  - 顶部动作条点击行为
  - 角色就绪 / 优先补稳 / 最近会话 / 快速开局的 action bridge
- 当前收益：
  - `run-detail.js` 不再同时承担“视图渲染 + 状态 builder + 动作注册”三重职责
  - 后续继续把 workflow 片区迁成 Vue island 时，优先复用动作桥，而不是在各文件重复写点击处理

当前分支也已把 workflow 的 legacy 渲染层开始独立出去：

- `work-overview-legacy-render.js`
- 已统一承接内容：
  - 角色就绪列表
  - 优先补稳卡片
  - 关系图摘要
  - 最近会话预览
- 当前收益：
  - `run-detail.js` 进一步退回为“什么时候刷新”的编排文件，而不是亲自拼每一块 workflow 卡片 DOM
  - 旧 DOM 区和 Vue island 现在都开始围绕“共享 state + 共享 action + 独立 renderer”组织

当前分支也已开始处理人物档案页的状态层：

- `character-overview-state.js`
- 已统一承接内容：
  - 关键字段/细调字段常量
  - 健康度、证据、信号、时间线等纯派生状态
  - 字段标签、弱字段判断、摘要卡片数据
- 当前收益：
  - `run-detail.js` 不再独占人物档案页的大量“知识性逻辑”
  - 后续若继续把人物档案页拆成 Vue island 或独立 renderer，会有稳定的状态出口可复用

当前分支也已把人物档案页的 legacy 渲染层开始独立出去：

- `character-overview-legacy-render.js`
- 已统一承接内容：
  - 健康度指标卡
  - 证据指标卡
  - 信号卡片
  - 改动时间线
  - 关键字段卡片
  - 语音/关系摘要
  - 高级分组折叠区
- 当前收益：
  - `run-detail.js` 在人物档案页这条线上，也开始向“状态 + 渲染 + 动作”三层分化
  - 下一步若继续处理人物档案 actions，就不必再和大段 DOM 模板混在一起改

当前分支也已把人物档案页的动作层独立出去：

- `character-overview-actions.js`
- 已统一承接内容：
  - 打开人物档案
  - 字段 AI 补全
  - 字段保存
  - 高级分组展开/收起
  - 继续增量蒸馏
  - 以人物身份 / 以自己入场
  - 查看原档
- 当前收益：
  - 人物档案这条线已经形成和 workflow 类似的 `state + renderer + actions` 结构
  - `run-detail.js` 进一步逼近真正的 orchestrator，而不是继续承载大段人物档案业务实现

当前分支现已完成第十二块试点：

- `人物档案页主体`
- 接管内容：
  - 人物健康度 / 证据 / 可信痕迹 / 改动时间线
  - 关键字段编辑与 AI 补全
  - 细调字段折叠展开
  - 继续增量蒸馏 / 角色入场 / 查看原档动作入口
- 保留旧逻辑：
  - 人物档案数据拉取
  - workflow 显隐编排
  - 旧 DOM 区作为 fallback 与兼容层

当前分支这一步也顺手补齐了人物档案桥接快照：

- `currentCharacterOverview`
- 当前收益：
  - 人物档案 Vue island 不再需要偷读旧作用域
  - 桥接层已经能覆盖 run / session / workflow / character overview / modal editor 几条主线

当前分支也已开始把书卷支撑视图独立出去：

- `run-detail-support-state.js`
- `run-detail-support-legacy-render.js`
- 已统一承接内容：
  - 时间线事件列表
  - 关系图文件链接区
  - 增量蒸馏计划摘要
  - 最近书页来源列表
  - 相关格式化 helper（字数、文件体量、当前书段判定）
- 当前收益：
  - `run-detail.js` 不再亲自拼这些“支撑结构但不属于主流程”的视图
  - 剩余内容更聚焦在页面编排和少量流程动作，离真正的 orchestrator 更近

当前分支现已完成第十三块与第十四块试点：

- `书页来源区`
- `运行时间线区`
- 接管内容：
  - 来源片段列表
  - 当前书段标记
  - 展开 / 收起
  - 最近事件列表
- 保留旧逻辑：
  - workflow 显隐编排
  - legacy DOM 作为 fallback

当前分支这一步也继续处理 legacy 收口：

- `persona-review-legacy.js`
- `relation-details-legacy.js`
- 当前收益：
  - 即使某些 modal 仍保留 fallback，`run-detail.js` 也不需要再长期背着整段 legacy 兼容实现
  - 主文件开始更明显地退回到“编排入口 + 跨区 helper + 少量兼容出口”

当前分支现已完成第十五块试点：

- `书架列表区`
- 接管内容：
  - 书卷列表
  - 空状态
  - 打开书卷
  - 删除书卷
- 保留旧逻辑：
  - 书架头部按钮
  - 进入新建蒸馏流程
  - 既有 fallback DOM

当前分支这一步也继续补齐桥接态：

- `allRuns`
- 当前收益：
  - 书架 Vue island 能直接基于快照渲染，不需要再依赖 legacy DOM 回推列表
  - 书架开始从“纯旧时代入口”变成“真正纳入渐进迁移主线”的第一层页面

当前分支现已完成第十六块试点：

- `模型设置弹窗主体`
- 接管内容：
  - 声源类型切换
  - 模型名称 / 地址 / 密钥 / token 上限编辑
  - 保存与关闭
- 保留旧逻辑：
  - modal 开关
  - 旧表单 fallback
  - 全局 `applyModelSettingsView()` 继续负责把模型配置同步回外层界面

当前分支这一步也把书架进一步补成统一结构：

- `bookshelf-state.js`
- `bookshelf-legacy-render.js`
- 当前收益：
  - 书架不再只是“先上了个 Vue 列表”，而是也具备和 workflow / character overview 一样的三层边界
  - 后续如果继续扩展书架筛选、搜索、批量操作，就不需要重新回到 `bookshelf.js` 里混写

推荐优先级：

1. `增量蒸馏工作台`
2. `人物校对 modal`
3. `聊天输入区 / 快捷回复区`

以上三块都已经足够说明当前“桥接层 + 局部 island”方案是成立的，后续可以按同样方式继续扩张，而不用回到一次性整站重写。

### Phase 2：抽 API 层与共享状态

目标：让 Vue 岛不再直接依赖 `apiJson` + 全局变量 + DOM helper 的混合调用方式。

建议新增：

- `webuiApi.ts` / `webuiApi.js`
- `legacyBridgeAdapter.ts`
- `useRunState()`
- `useDialogueState()`
- `useRedistillState()`

当前分支已先落一个最小 API 层：

- `src/web/static/js/webui-api.js`

当前已收口的能力：

- 人物校对读取
- 人物校对保存
- 人物字段 AI 补全
- 增量蒸馏推荐片段
- run 刷新读取

### Phase 3：扩大接管范围

这一阶段已经基本落地，当前已完成以下高交互区块的 Vue 接管：

- 人物校对 modal
- 聊天输入区
- 关系明细 modal
- 角色卡编辑器
- 新建会话 / 入场设置区

当前剩余更值得继续 Vue 化的部分，已经从“核心交互区”转成“外围摘要区 / 壳层区”：

- 角色卡预览区
- 工作流顶部条与右侧摘要卡片
- 设置弹窗里的局部交互区
- 后续新增的关系图 / 时间线 / 诊断面板

### Phase 4：再决定是否整页 SPA 化

当以下条件同时满足，再考虑整页 Vue：

- 主要交互区都已 Vue 化
- 旧 DOM 渲染函数明显只剩壳层
- 状态读写已经集中
- API 调用已收口

## 不建议现在做的事

以下动作现在都不划算：

- 直接整站改成 Vue Router SPA
- 同时重写样式体系
- 一边迁 Vue 一边大改接口协议
- 一次性替换所有 fragments

这些动作会显著拉高回归成本，也会拖慢产品迭代。

## 本轮落地的技术基础

本轮已经开始为渐进迁移做准备：

- 新增 `legacy-bridge.js`，统一对外发布当前 Web UI 的运行态
- 旧逻辑在关键状态变化后主动 publish 快照
- bootstrap 会登记可挂载的 fragment host

这意味着后续 Vue 岛组件可以直接：

1. 订阅桥接层状态
2. 读取当前 run / session / workflow snapshot
3. 局部挂载到指定 host
4. 不必先拆掉旧 UI

## 局部重构建议

下一步最推荐的不是继续盲目扩岛，而是先做两类“收口”工作：

### 方案 A：继续抽共享层

优先方向：

- 把更多字段编辑 UI 收到 schema-driven renderer
- 给 islands 统一 loading / empty / retry 边界
- 继续收拢 action bridge / state publish 的读写模式

收益：

- 能明显降低后续新增字段和新增 island 的重复代码
- 更容易避免“Vue 岛写了一套、旧 DOM 又写一套”的双份逻辑

### 方案 B：把外围摘要区逐步 Vue 化

优先范围：

- 工作流顶部条
- 书架详情摘要卡片
- 角色卡预览区

收益：

- 能继续减少 `renderXxx()` / `setText()` / `toggle()` 组合式更新
- 让当前已接管的核心区域和外围信息展示区风格更统一

## 验收标准

当一个 Vue 岛试点完成时，应满足：

- 对用户来说功能无回退
- 旧页面仍可继续工作
- Vue 组件只依赖桥接层和 API 层
- 不直接读写随机 DOM 节点
- 同一状态变化不再需要多处手动刷新

## 建议结论

结论很明确：

- **值得迁 Vue 3**
- **不值得整体重写**
- **最优路径是：先铺桥，再岛式迁移，再扩大接管范围**
