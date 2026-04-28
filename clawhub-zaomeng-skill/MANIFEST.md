# 打包清单

## 核心文件

- `README.md`
- `README_EN.md`
- `SKILL.md`
- `INSTALL.md`
- `PUBLISH.md`
- `runtime/zaomeng_cli.py`
- `runtime/src/core/__init__.py`
- `runtime/src/core/cli_app.py`
- `runtime/requirements.txt`
- `runtime/src/core/main.py`
- `runtime/src/core/config.py`
- `runtime/src/core/contracts.py`
- `runtime/src/core/llm_client.py`
- `runtime/src/core/logging_setup.py`
- `runtime/src/core/path_provider.py`
- `runtime/src/core/runtime_parts.py`
- `runtime/src/core/rulebook.py`
- `runtime/src/modules/__init__.py`
- `runtime/src/modules/distillation.py`
- `runtime/src/modules/relationships.py`
- `runtime/src/modules/chat_engine.py`
- `runtime/src/modules/reflection.py`
- `runtime/src/modules/speaker.py`
- `runtime/src/utils/__init__.py`
- `runtime/src/utils/file_utils.py`
- `runtime/src/utils/text_parser.py`
- `runtime/src/utils/token_counter.py`

## 参考文件

- `references/output_schema.md`
- `references/style_differ.md`
- `references/logic_constraint.md`
- `references/safety_policy.md`
- `references/validation_policy.md`

## 运行时规则文件

- `runtime/rules/distillation_rules.md`
- `runtime/rules/relationship_rules.md`
- `runtime/rules/speaker_rules.md`
- `runtime/rules/persona_rules.md`

## Prompt 模板

- `prompts/distill_prompt.md`
- `prompts/relation_prompt.md`
- `prompts/correction_prompt.md`

## 示例文件

- `examples/sample_input_excerpt.txt`
- `examples/sample_character_profile.md`
- `examples/sample_relations.md`
- `examples/test-prompts.json`

## 打包目标

- 提供一个内嵌最小运行时的自包含 skill 包
- 不要求运行时再去下载外部仓库
- 运行时入口本地打包；prompt 与 references 主要用于约束和说明，而不是替代引擎本身
