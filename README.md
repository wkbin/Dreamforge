# 造梦.skill

本项目是一个本地规则引擎驱动的小说角色工具链，不依赖 OpenAI 或其他云模型。  
核心能力：人物蒸馏、关系提取、沉浸式群聊、OOC 纠错与反思。

## 一行安装（GitHub）

仓库发布到 GitHub 后，可直接用 Skills CLI 安装：

```bash
npx skills add wkbin/Dreamforge
```

要求：仓库包含 `skills/zaomeng-skill/SKILL.md`（本仓库已提供）。

## 快速开始（本地运行）

```bash
pip install -r requirements.txt
```

复制配置文件：

```bash
cp config.yaml.example config.yaml
```

Windows 可用：

```powershell
Copy-Item config.yaml.example config.yaml
```

## CLI 用法

```bash
# 人物蒸馏（自动提取主要角色）
py -m src.core.main distill --novel data/sample_novel.txt --force

# 指定角色蒸馏
py -m src.core.main distill --novel 红楼梦.txt --characters 林黛玉,贾宝玉 --force

# 关系提取
py -m src.core.main extract --novel data/sample_novel.txt --force

# 群聊（旁观 / 代入）
py -m src.core.main chat --novel 红楼梦 --mode observe
py -m src.core.main chat --novel 红楼梦 --mode act --character 林黛玉

# 查看角色档案
py -m src.core.main view --character 林黛玉

# 手动纠错
py -m src.core.main correct --session <ID> --message "<原句>" --corrected "<修正句>" --character 林黛玉
```

群聊内联命令：`/save` ` /reflect` ` /correct 角色|原句|修正句` ` /quit`

## 安装到 OpenClaw / Hermes

方式 1：使用安装脚本

```bash
py scripts/install_skill.py --openclaw-dir <openclaw-skills-root> --hermes-dir <hermes-skills-root>
```

方式 2：手动拷贝

- OpenClaw: `openclaw-skill/SKILL.md` -> `<openclaw-skills-root>/zaomeng-skill/SKILL.md`
- Hermes: `hermes-skill/SKILL.md` -> `<hermes-skills-root>/zaomeng-skill/SKILL.md`

## 数据输出

- `data/characters/`：角色心智档案 JSON
- `data/relations/`：关系网 JSON
- `data/sessions/`：群聊会话 JSON
- `data/corrections/`：纠错记录 JSON

## 技术说明

- 运行模式：`local-rule-engine`（默认）
- 支持输入：`.txt` / `.epub`
- Python：3.10+

## 项目结构（核心）

```text
src/core/main.py            # CLI 入口
src/modules/distillation.py # 人物蒸馏
src/modules/relationships.py# 关系提取
src/modules/chat_engine.py  # 群聊引擎
src/modules/reflection.py   # 反思与纠错
skills/zaomeng-skill/       # Skills CLI 安装入口
openclaw-skill/             # OpenClaw 适配
hermes-skill/               # Hermes 适配
```

## License

MIT

## Acknowledgements

- Thanks to [`alchaincyf/nuwa-skill`](https://github.com/alchaincyf/nuwa-skill) for open-sourcing a clear skill packaging pattern (`SKILL.md + references + examples`) that informed this project's ClawHub publish bundle design.
- This project adapts those publishing/organization ideas to Dreamforge's local-rule-engine character distillation workflow.

## 发布前检查清单

- 仓库已包含 `skills/zaomeng-skill/SKILL.md`
- `README.md` 中的一行安装命令已使用你的真实仓库路径
- `requirements.txt` 不包含云模型 SDK（当前已移除 `openai`）
- `config.yaml.example` 为本地引擎配置且不含敏感信息
- `data/` 下无隐私数据、无大体积临时文件（建议仅保留样例）
- `py -m src.core.main --help` 可正常运行
- `py -m src.core.main distill --novel data/sample_novel.txt --force` 可正常运行
- `py -m src.core.main extract --novel data/sample_novel.txt --force` 可正常运行
- `py scripts/install_skill.py --help` 可正常运行
- 仓库已设置开源许可证（MIT）
