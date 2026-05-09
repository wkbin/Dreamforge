# 产品分支进度交接

更新时间：2026-05-09

当前分支：`docs/product-roadmap-v1`

远端状态：已推送到 `origin/docs/product-roadmap-v1`

## 1. 这条分支现在已经做完什么

这条分支目前已经把「作品页」和「角色页」从原来的流程面板，推进到了更像产品页面的第一阶段。

### 已完成的产品文档

- `PRODUCT_ROADMAP.md`
- `PRODUCT_INFORMATION_ARCHITECTURE.md`
- `PRODUCT_PAGE_SKETCHES.md`
- `PRODUCT_EXECUTION_PLAN.md`
- `WORK_OVERVIEW_FRONTEND_PRD.md`
- `CHARACTER_OVERVIEW_FRONTEND_PRD.md`

### 已完成的前端能力

#### 作品页

- 第一版作品总览页已经落地
- 有 work hero、progress strip、角色 readiness、关系/会话入口
- 新增了“优先校对队列”
- 新增了中间“判断区 / 推荐动作区”
- 推荐动作已经能真正触发已有流程，不是静态展示

#### 角色页

- 第一版角色总览页已经落地
- 关键字段卡片已经成形
- 弱字段支持字段级 `AI补全`
- 新增“健康度”区块
- 新增“来源与证据”区块
- 细调字段已改成折叠式 drilldown
- 角色页可以直接发起“继续增量蒸馏”

## 2. 这条分支最近的关键提交

按时间从旧到新：

- `d276ee8` `Build first work and character overview pages`
- `30b551b` `Add character overview autofill actions`
- `2f53c04` `Refine character overview health and drilldowns`
- `ec1a145` `Add work overview priority review queue`
- `e3fda71` `Add work overview narrative decision panel`
- `4334001` `Add character overview evidence snapshot`

## 3. 主要改动集中在哪些文件

### 页面结构

- `src/web/static/fragments/workflow-strip.html`

### 核心页面逻辑

- `src/web/static/js/run-detail.js`
- `src/web/static/js/main.js`
- `src/web/static/js/workflow.js`

### 样式

- `src/web/static/styles/workspace.css`
- `src/web/static/styles/app.css`

### 静态资源版本

- `src/web/static/js/bootstrap.js`
- `src/web/static/index.html`
- `src/web/static/version.txt`

## 4. 当前页面已经是什么状态

### 作品页现在能回答的问题

- 这卷是否已经可入场
- 哪些角色已经稳了，哪些还薄
- 现在最值得先补谁
- 这卷目前卡在哪
- 推荐你下一步点哪个动作

### 角色页现在能回答的问题

- 这个角色是谁
- 哪些关键字段还薄
- 能不能直接 AI 补
- 这份人物当前靠什么书段站住
- 证据是偏薄还是命中稳定
- 现在更适合补字段还是继续增量蒸馏

## 5. 我建议你回家后最顺手继续做的方向

优先建议做下面这个方向，因为它和当前已完成页面最连续：

### 方向 A：补“角色资产可信度”的第二层

也就是把 `PRODUCT_EXECUTION_PLAN.md` 里 Week 2 的一部分往前做一点，但先做轻量版，不要一次上重系统。

推荐先做：

1. 字段来源 tag
2. 最近一次 AI 补全提示
3. 最近一次增量蒸馏提示
4. 手动校对痕迹提示

注意：

- 现在前端已经有“健康度”和“来源与证据”
- 但还没有真正的字段级来源历史
- 所以如果继续做，建议先做“轻量来源标签”，不要直接上复杂 revision system

### 方向 B：补作品页底部信息架构

如果你更想继续做作品页，建议下一步是：

1. 时间线做成更产品化的信息块，而不只是普通列表
2. 来源区补“当前使用中的书段”和“本轮是否换源”
3. 关系图区补“失败但不阻塞聊天”的更强提示
4. 最近会话卡片补“从哪个模式进入 / 最近一句是什么氛围”

## 6. 如果你准备继续做，建议先看的代码入口

### 做作品页

先看：

- `src/web/static/fragments/workflow-strip.html`
- `src/web/static/js/run-detail.js`
- `src/web/static/styles/workspace.css`

重点函数：

- `renderRunSummary`
- `renderWorkSummaryNarrative`
- `renderWorkPriorityReview`
- `renderCharacterReadiness`
- `renderWorkGraphSummary`
- `renderWorkSessionPreview`

### 做角色页

先看：

- `src/web/static/fragments/workflow-strip.html`
- `src/web/static/js/run-detail.js`
- `src/web/static/styles/workspace.css`

重点函数：

- `renderCharacterOverview`
- `buildCharacterOverviewHealthSnapshot`
- `renderCharacterOverviewHealthMetrics`
- `buildCharacterOverviewEvidenceSnapshot`
- `renderCharacterOverviewEvidenceMetrics`
- `renderCharacterOverviewKeyFields`
- `handleCharacterOverviewFieldAutofill`
- `openCharacterOverviewIncrementalDistill`

## 7. 当前实现时要注意的约定

### 静态资源版本号

前端改动后，一定要执行：

```powershell
py -3 scripts/web_asset_version.py --bump
```

不要手改三四处版本号，也不要用别的脚本替代这个动作。

### 回归命令

每次完成一轮后至少跑：

```powershell
py -3 scripts/dev_checks.py
```

如果只动了前端 JS，也可以先快速跑：

```powershell
node --check src/web/static/js/run-detail.js
node --check src/web/static/js/main.js
```

## 8. 当前这条分支适合怎么收

如果你准备继续沿这条分支做，建议保持现在这种提交粒度：

- 每次只收一个明确页面能力
- 每次都带静态资源版本 bump
- 每次都跑 `dev_checks`

这样后面回看历史非常清楚，也方便以后挑提交合并。

## 9. 一句话总结

这条分支现在已经把产品骨架搭出来了，接下来最值钱的不是再加新入口，而是把“角色资产为什么可信”这件事继续做深一点。
