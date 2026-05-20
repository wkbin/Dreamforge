# 发布回归 Gate（跨平台）

更新时间：2026-05-20

## 目的

把“跨平台主流程实机回归”从口头清单变成发版前硬 gate。  
默认流程下，未完成签核会阻断 `release_skill.py` 打包发布链路。

## 覆盖范围

必须覆盖以下平台与主流程：

- 平台：Windows / WSL / Linux / Termux
- 主流程：install / update / run / import_export

## 签核文件

路径：`docs/release-regression-signoff.json`

字段要求：

- `release_tag`：本次发布 tag，例如 `v2026.05.16`
- `checked_at`：签核日期（`YYYY-MM-DD`）
- `checked_by`：至少一位签核人
- `platforms.<platform>.<check>`：必须全部为 `pass`

允许值：`pass` / `fail` / `pending`

## 校验命令

```bash
python scripts/release_regression_gate.py --release-tag v2026.05.16
```

如不传 `--release-tag`，只校验字段完整性与 `pass` 状态。

## 与发布流程的关系

- `scripts/dev_checks.py` 默认会执行该 gate
- `scripts/dev_checks.py --smoke-only` 不执行该 gate（用于开发期快速回归）
- `scripts/release_skill.py` 默认调用 `dev_checks.py`，因此会自动带上该 gate

