# Release Regression Checklist

更新时间：2026-05-16

这份清单用于正式发版前的人工回归。目标是用最少步骤覆盖最容易出事故的路径：安装更新、启动链路、对话主流程、旁观模式、以及 skill 关键输入输出。

## 1. 发版前准备

- [ ] `git status --short` 为空（工作区干净）
- [ ] `git log -1 --oneline` 已确认目标提交
- [ ] `py -3 -m pytest -q` 全量通过
- [ ] 记录待发布版本号（`src/web/static/version.txt`）

## 2. 安装与更新链路

- [ ] 全新安装：`curl -fsSL https://raw.githubusercontent.com/wkbin/zaomeng/main/scripts/install.sh | bash`
- [ ] 启动命令可用：`zaomeng` 可拉起 Web UI
- [ ] 更新命令可用：`zaomeng update` 能正确显示本地/远端版本
- [ ] 已是最新版时，`zaomeng update` 会输出 “无需更新” 并正常退出
- [ ] 卸载命令可用：`zaomeng uninstall`
- [ ] Termux 场景额外确认：启动时不出现 `env: 'exec': No such file or directory`

## 3. Web UI 主流程

- [ ] 首页可正常加载，静态资源版本号与发布版本一致
- [ ] 新建 run 流程可走通（上传小说/选择角色/生成 payload）
- [ ] 角色蒸馏完成后可查看人物资料与关系图
- [ ] 运行详情页无明显空白区/按钮失效/控制台报错

## 4. 对话与旁观模式

- [ ] `act` 模式可正常发言、续聊、停止
- [ ] `insert` 模式可正常走自我身份卡与场景进入
- [ ] `observe` 模式关键回归：
- [ ] 不出现重复的“按提示推进”按钮
- [ ] 快捷按钮禁用态与发送中状态一致
- [ ] 系统提示会随剧情推进更新，不会长期卡在开场提示
- [ ] 场景切换后可继续推进，不会异常中断

## 5. Skill / Prompt 关键一致性

- [ ] alias 输入可双向匹配（canonical -> alias、alias -> canonical）
- [ ] `requested_characters / matched_characters / missing_characters` 返回 canonical 名称
- [ ] 长文本分块与合并流程可正常工作
- [ ] `run_manifest.json` 关键字段完整（`progress` / `capabilities` / `artifacts` / `quality`）

## 6. 发布后抽检

- [ ] 从干净环境执行一次 `zaomeng update` + `zaomeng` 启动验证
- [ ] 抽查 1 个旁观会话，确认提示推进行为正常
- [ ] 抽查 1 个别名案例，确认匹配与输出格式正确
