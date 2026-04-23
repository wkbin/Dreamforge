# 造梦.skill (Zaomeng Skill)

本地规则引擎的小说角色工具链。  
不用云模型，不要 API Key，直接产出角色档案、关系网和角色群聊约束。

## 30 秒上手

```bash
pip install -r requirements.txt
cp config.yaml.example config.yaml
py -m src.core.main distill --novel data/sample_novel.txt --force
py -m src.core.main extract --novel data/sample_novel.txt --force
```

Windows 配置文件复制：

```powershell
Copy-Item config.yaml.example config.yaml
```

## 一行安装（Skills CLI）

```bash
npx skills add wkbin/Dreamforge
```

要求：仓库包含 `skills/zaomeng-skill/SKILL.md`（本仓库已提供）。

## 你可以用它做什么

1. 小说人物蒸馏：从 `.txt/.epub` 自动提取主角人设 JSON。  
2. 关系网构建：按角色对生成 `trust/affection/power_gap` 等关系参数。  
3. 角色群聊模拟：支持旁观/代入，并用纠错记忆降低 OOC 漂移。

## 常用命令

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

方式 1：安装脚本

```bash
py scripts/install_skill.py --openclaw-dir <openclaw-skills-root> --hermes-dir <hermes-skills-root>
```

方式 2：手动拷贝

- OpenClaw: `openclaw-skill/SKILL.md` -> `<openclaw-skills-root>/zaomeng-skill/SKILL.md`
- Hermes: `hermes-skill/SKILL.md` -> `<hermes-skills-root>/zaomeng-skill/SKILL.md`

## 输出目录

- `data/characters/`：角色心智档案 JSON
- `data/relations/`：关系网 JSON
- `data/sessions/`：群聊会话 JSON
- `data/corrections/`：纠错记录 JSON

## 技术信息

- 运行模式：`local-rule-engine`
- 输入格式：`.txt` / `.epub`
- Python：3.10+

## 核心结构

```text
src/core/main.py             # CLI 入口
src/modules/distillation.py  # 人物蒸馏
src/modules/relationships.py # 关系提取
src/modules/chat_engine.py   # 群聊引擎
src/modules/reflection.py    # 反思与纠错
skills/zaomeng-skill/        # Skills CLI 安装入口
clawhub-zaomeng-skill/       # ClawHub 发布包
openclaw-skill/              # OpenClaw 适配
hermes-skill/                # Hermes 适配
```

## Acknowledgements

- Thanks to [`alchaincyf/nuwa-skill`](https://github.com/alchaincyf/nuwa-skill) for open-sourcing a clear skill packaging pattern (`SKILL.md + references + examples`) that informed this project's ClawHub publish bundle design.

## License

MIT

