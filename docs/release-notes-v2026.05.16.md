# Zaomeng v2026.05.16 发布说明

发布日期：2026-05-16

## 本次亮点

- 新增角色别名知识库，支持 canonical 与 alias 双向匹配。
- 修复 skill / host / web 在角色名归一化上的一致性问题。
- 补充发布回归测试与安装脚本防护测试，覆盖更新与别名关键路径。

## 变更明细

- `feat(skill): add character alias knowledge base for bidirectional name matching` (`f6bd767`)
- `fix(skill): align host/web and skill-side normalization, add normalized alias lookup` (`823e68e`)
- `Merge pull request #14 from buyaoxiangtale/feat/character-alias-knowledge-base` (`391f510`)
- `test(release): add regression checklist and alias/install guard tests` (`f2d5c18`)

## 新贡献者

- @buyaoxiangtale 首次贡献（PR [#14](https://github.com/wkbin/zaomeng/pull/14)）

## 完整对比

- [v2026.05.14...v2026.05.16](https://github.com/wkbin/zaomeng/compare/v2026.05.14...v2026.05.16)
