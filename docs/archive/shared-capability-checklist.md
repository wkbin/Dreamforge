# Shared Capability Checklist

更新时间：2026-05-14

这份清单用来约束 Web UI 与 skill 的能力不要继续漂移。
原则很简单：凡是“对话主流程会感知到”的能力，都要显式检查两边有没有一起跟上。

## 1. 会话状态结构

- [x] canonical session state
- [x] `scene`
- [x] `presence`
- [x] `progression`
- [x] `relations`
- [x] `characters.snapshots`
- [x] `signals`
- [x] `memory.summary`

检查要求：

- 新增字段时，Web UI 序列化和 skill 侧消费都要检查
- 旧字段兼容只允许走 canonical 映射，不允许两边各打补丁

## 2. 对话推进能力

- [x] 场景推荐
- [x] 下一幕转场提示
- [x] 会话级关系增量
- [x] 角色快照
- [x] 事件信号 `event_signals`
- [x] 对话压缩摘要
- [x] 旁观模式剧情推动
- [x] 时间推进 / 离场回场基础链路

检查要求：

- 如果 Web UI 改了提示词结构，skill 侧共享逻辑也要同步检查
- 如果 skill 新增了运行时字段，Web UI 的运行态总览和调试视图也要能看见

## 3. 小说资产能力

- [x] run package schema version
- [x] 导入小说包
- [x] 导出小说包
- [x] 内置小说目录
- [x] 旧 manifest / 路径兼容层

检查要求：

- Web UI 导出的包必须能被 skill 接受
- skill 产出的包 / 运行结果必须能被 Web UI 正确展示
- 缺 graph、缺 payload、旧 Windows 路径都要走同一套兼容原则

## 4. 明确不下放到 skill 的能力

以下能力默认仅保留在宿主或 Web UI 侧，不应继续下沉到 skill 包里：

- 联网抓取补全
- 本地浏览器 headless 渲染图谱
- 宿主级安装 / 更新脚本
- Web UI 专属交互状态与按钮反馈

## 5. 每次改动前后的核对动作

### 改动前

- 这次改动属于会话状态、提示词、资产格式，还是 UI 交互
- 是否会影响 skill 侧输入 / 输出结构
- 是否会引入新的兼容字段

### 改动后

- Web UI 流程是否还能读旧数据
- skill 侧是否还能读新输出
- 测试里是否至少补一条跨边界回归
- 文档是否需要补到 `data-dictionary` / `manifest-compatibility` / 本清单
