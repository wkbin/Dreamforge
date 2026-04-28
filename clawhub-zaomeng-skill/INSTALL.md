# 安装说明

这是一份面向打包校验和环境确认的安装说明。

它不是主要的用户使用指南。  
用户使用方式优先看 `README.md`；宿主和 agent 的执行规则优先看 `SKILL.md`。

## 当前打包形态

这个 bundle 已经内嵌最小可运行的 zaomeng 运行时。

- 不再把运行时克隆外部仓库作为主路径
- 默认通过包内运行时入口执行

## 本目录应包含的关键文件

- `README.md`
- `README_EN.md`
- `SKILL.md`
- `MANIFEST.md`
- `PUBLISH.md`
- `runtime/zaomeng_cli.py`
- `runtime/src/...`
- `runtime/requirements.txt`
- `references/output_schema.md`
- `references/style_differ.md`
- `references/logic_constraint.md`
- `references/safety_policy.md`
- `references/validation_policy.md`
- `examples/sample_input_excerpt.txt`
- `examples/sample_character_profile.md`
- `examples/sample_relations.md`
- `examples/test-prompts.json`

## 运行时依赖

- 必需：`PyYAML`
- 可选：`tiktoken`
- 可选：`ebooklib`，仅在读取 `.epub` 小说时需要

## 运行建议

- Windows / PowerShell 优先使用 `py -3 runtime/zaomeng_cli.py ...`
- 默认运行时数据目录为 `runtime/data/`
- 包内 prompt 与 references 主要用于约束与说明，不应用来替代引擎入口
- 当前运行时结构按两层组织：
  - runtime 自持薄 wrapper：`runtime/src/core/main.py`、`runtime/src/core/runtime_factory.py`、`runtime/src/core/logging_utils.py`
  - 共享实现镜像：`runtime/src/core/cli_app.py`、`runtime/src/core/runtime_parts.py`、`runtime/src/core/logging_setup.py` 及 `modules/`、`utils/` 下的共享业务模块

## 快速校验清单

1. `SKILL.md` frontmatter 合法。
2. `runtime/zaomeng_cli.py` 可以启动。
3. 输出字段符合 `references/output_schema.md`。
4. 安全与校验相关规则文件齐全。
