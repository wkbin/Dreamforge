# zaomeng

[中文](README.zh.md) | [English](README.en.md)

本地小说人物蒸馏、关系抽取和角色群聊工具链。当前版本基于本地规则引擎运行，不依赖云端模型或 API Key。

## 快速开始

```bash
pip install -r requirements.txt
cp config.yaml.example config.yaml
python -m src.core.main distill --novel data/sample_novel.txt --force
python -m src.core.main extract --novel data/sample_novel.txt --force
```

Windows 复制配置文件：

```powershell
Copy-Item config.yaml.example config.yaml
```

## 快速接入

仓库地址：

```text
https://github.com/wkbin/zaomeng.git
```

### 接入 OpenClaw

推荐安装：

```bash
openclaw skills install wkbin/zaomeng-skill
```

仓库内脚本安装（适用于本地开发或未接入 ClawHub 的环境）：

```bash
python scripts/install_skill.py --openclaw-dir <openclaw-skills-root>
```

手动安装，二选一：

```bash
# 方式 1：克隆仓库后复制
git clone https://github.com/wkbin/zaomeng.git
mkdir -p <openclaw-skills-root>/zaomeng-skill
cp zaomeng/openclaw-skill/SKILL.md <openclaw-skills-root>/zaomeng-skill/SKILL.md
```

```bash
# 方式 2：直接下载单文件
mkdir -p <openclaw-skills-root>/zaomeng-skill
curl -L https://raw.githubusercontent.com/wkbin/zaomeng/main/openclaw-skill/SKILL.md -o <openclaw-skills-root>/zaomeng-skill/SKILL.md
```

OpenClaw 中对应的命令映射：

```bash
python -m src.core.main distill --novel <path> [--characters A,B] [--force]
python -m src.core.main extract --novel <path> [--force]
python -m src.core.main chat --novel <path-or-name> --mode observe|act [--character <name>]
python -m src.core.main view --character <name> [--novel <path-or-name>]
python -m src.core.main correct --session <id> --message <raw> --corrected <fixed>
```

同一套 `zaomeng-skill` 也可用于 Hermes Agent，命令映射保持一致，无需再单独维护一套接入说明。

### 接入你自己的项目

推荐使用 ClawHub CLI：

```bash
npx clawhub@latest install zaomeng-skill
```

如果你的项目已经有 `skills/` 目录，也可以使用仓库内安装脚本：

```bash
python scripts/install_skill.py --skills-dir <your-skills-root>
```

如果你想直接装进项目根目录：

```bash
python scripts/install_skill.py --project-root <your-project-root>
```

如果你想自定义 skill 名称：

```bash
python scripts/install_skill.py --project-root <your-project-root> --skill-name zaomeng-skill
```

如果你不想运行安装脚本，也可以手动接入：

```bash
# 方式 1：克隆仓库后复制整个通用 skill 目录
git clone https://github.com/wkbin/zaomeng.git
mkdir -p <your-project-root>/skills
cp -r zaomeng/skills/zaomeng-skill <your-project-root>/skills/
```

```bash
# 方式 2：只下载单文件版本
mkdir -p <your-project-root>/skills/zaomeng-skill
curl -L https://raw.githubusercontent.com/wkbin/zaomeng/main/skills/zaomeng-skill/SKILL.md -o <your-project-root>/skills/zaomeng-skill/SKILL.md
```

## 核心命令

```bash
python -m src.core.main distill --novel data/sample_novel.txt --force
python -m src.core.main distill --novel data/sample_novel.txt --characters 林黛玉,贾宝玉 --force
python -m src.core.main extract --novel data/sample_novel.txt --force
python -m src.core.main chat --novel data/sample_novel.txt --mode observe
python -m src.core.main chat --novel data/sample_novel.txt --mode act --character 林黛玉
python -m src.core.main view --character 林黛玉 --novel data/sample_novel.txt
python -m src.core.main correct --session <ID> --message "<原句>" --corrected "<修正句>" --character 林黛玉
```

群聊内联命令：

- `/save`
- `/reflect`
- `/correct 角色|对象|原句|修正句|原因`
- `/quit`

## 输出目录

当前版本按小说隔离产物，避免多本小说串档：

- `data/characters/<novel_id>/`
- `data/relations/<novel_id>/`
- `data/sessions/`
- `data/corrections/`

例如 `data/sample_novel.txt` 的默认输出为：

- `data/characters/sample_novel/*.json`
- `data/relations/sample_novel/sample_novel_relations.json`

## 当前实现说明

- 输入格式支持 `.txt` 和 `.epub`
- 角色蒸馏会写入 `novel_id`、`source_path` 和基础证据计数
- 关系抽取只为同句共现的角色对建立关系
- 群聊会优先加载指定小说命名空间下的人物与关系文件

## 项目结构

```text
src/core/main.py
src/modules/distillation.py
src/modules/relationships.py
src/modules/chat_engine.py
src/modules/reflection.py
src/modules/speaker.py
src/utils/
tests/test_relation_behavior.py
```

## License

MIT
