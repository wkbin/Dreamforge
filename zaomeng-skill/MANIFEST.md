# 打包清单

## 核心文档

- `README.md`
- `README_EN.md`
- `.metadata.json`
- `SKILL.md`
- `INSTALL.md`
- `PUBLISH.md`
- `requirements.txt`

## Helper 脚本

- `tools/init_host_run.py`
- `tools/update_run_progress.py`
- `tools/prepare_novel_excerpt.py`
- `tools/build_prompt_payload.py`
- `tools/materialize_persona_bundle.py`
- `tools/export_relation_graph.py`
- `tools/verify_host_workflow.py`
- `tools/build_scene_recommendation_payload.py`

## Prompt 模板

- `prompts/distill_prompt.md`
- `prompts/relation_prompt.md`
- `prompts/correction_prompt.md`

## 参考文件

- `references/output_schema.md`
- `references/capability_index.md`
- `references/chat_contract.md`
- `references/style_differ.md`
- `references/logic_constraint.md`
- `references/safety_policy.md`
- `references/validation_policy.md`

## 示例文件

- `examples/sample_input_excerpt.txt`
- `examples/sample_character_profile.md`
- `examples/sample_relations.md`
- `examples/test-prompts.json`
- `examples/scene_recommendation_context.example.json`
- `examples/host_workflow_example.md`

## 打包目标

- 提供宿主可直接调用的 skill 资产
- 以 `prompts`、`references`、`examples` 和 helper scripts 为核心
- 支持人物蒸馏、关系抽取、人物关系图谱和宿主驱动角色对话
