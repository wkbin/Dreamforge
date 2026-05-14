# Manifest Compatibility Layer

更新时间：2026-05-14

## 目标

把旧 manifest、旧路径字符串、大小写差异、Windows / WSL / Linux 路径差异的兼容处理，集中到一个薄层里。

这层的职责不是修改业务语义，而是回答两个问题：

1. 这个旧值还能不能被安全识别成路径？
2. 这个旧路径在导入或运行时，能不能被安全重写到当前 run 目录？

## 当前位置

兼容层代码位于：

- [compat.py](d:/work2/Dreamforge/src/web/manifest/compat.py)

当前集中处理的能力有：

- `coerce_manifest_path`
  - 负责把旧 manifest 中的字符串路径、`Path`、以及无效旧值区分开
  - 会主动忽略空字符串、字典、列表、过长非法路径等旧残留
- `relative_to_run_dir`
  - 负责把真实文件路径转换成 run 目录下的相对路径
  - 容忍大小写差异、短路径差异、`realpath` 差异
- `rewrite_string_path`
  - 负责把导入包中的旧根路径改写到新 run 根目录
  - 兼容 Windows 正反斜杠混用
- `rewrite_run_root_paths`
  - 递归处理嵌套 dict / list 中的路径字符串

## 当前接入点

- [views.py](d:/work2/Dreamforge/src/web/manifest/views.py)
  - 用于 `file_urls` 构建时识别旧路径值
- [packages.py](d:/work2/Dreamforge/src/web/run_ops/packages.py)
  - 用于导入小说包后，把旧 run 根路径整体重写到新目录

## 后续收口方向

还没有完全收进这层的内容包括：

- 旧 manifest 字段级别的默认值修补
- package schema 的版本迁移策略
- 缺失 artifact 时的统一降级说明
- source-of-truth 字段与 derived 字段的彻底拆分

## 规则

后续如果再遇到 manifest 兼容问题，优先判断它属于哪一类：

1. 路径识别问题
2. 相对路径换算问题
3. 导入后路径重写问题
4. 字段语义迁移问题

前 3 类优先进入这层，别再散落到业务模块里各自兜底。
