#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
造梦.skill 项目测试
"""

import os
import sys
from pathlib import Path


def test_project_structure():
    """测试项目结构"""
    
    root = Path.cwd()
    print("=== 造梦.skill 项目结构测试 ===")
    
    # 必需的文件
    required_files = [
        "README.md",
        "requirements.txt",
        "src/core/main.py",
        "src/core/config.py",
        "src/core/llm_client.py"
    ]
    
    all_pass = True
    
    for file in required_files:
        file_path = root / file
        if file_path.exists():
            print(f"[OK] {file}")
        else:
            print(f"[MISSING] {file} (缺失)")
            all_pass = False
    
    # 必需的目录
    required_dirs = [
        "data/characters",
        "data/relations",
        "data/sessions",
        "data/corrections",
        "src/core",
        "src/modules",
        "src/utils",
        "tests"
    ]
    
    for dir_path in required_dirs:
        dir_full = root / dir_path
        if dir_full.exists() and dir_full.is_dir():
            print(f"[OK] {dir_path}/")
        else:
            print(f"[MISSING] {dir_path}/ (缺失)")
            all_pass = False
    
    # 检查 Python 模块
    init_files = [
        "src/__init__.py",
        "src/core/__init__.py",
        "src/modules/__init__.py",
        "src/utils/__init__.py"
    ]
    
    for init_file in init_files:
        init_path = root / init_file
        if init_path.exists():
            print(f"[OK] {init_file}")
        else:
            print(f"[WARN] {init_file} (建议创建)")
    
    print("\n=== 测试结果 ===")
    if all_pass:
        print("[OK] 项目结构完整")
        return True
    else:
        print("[FAIL] 项目结构不完整，请检查缺失的文件/目录")
        return False


def test_imports():
    """测试模块导入"""
    print("\n=== 模块导入测试 ===")
    
    # 添加 src 到 Python 路径
    src_path = Path.cwd() / "src"
    sys.path.insert(0, str(src_path))
    
    try:
        # 测试导入核心模块
        import src.core.config
        print("[OK] src.core.config 导入成功")
        
        import src.core.llm_client
        print("[OK] src.core.llm_client 导入成功")
        
        import src.core.main
        print("[OK] src.core.main 导入成功")
        
        print("[OK] 所有模块导入成功")
        return True
        
    except ImportError as e:
        print(f"[FAIL] 导入失败: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] 其他错误: {e}")
        return False


def main():
    """主测试函数"""
    print("造梦.skill - 项目测试套件")
    print("=" * 40)
    
    # 测试项目结构
    structure_ok = test_project_structure()
    
    # 测试模块导入
    imports_ok = test_imports()
    
    print("\n" + "=" * 40)
    print("最终结果:")
    
    if structure_ok and imports_ok:
        print("[OK] 所有测试通过！项目结构完整。")
        print("\n下一步:")
        print("1. 复制配置文件: cp config.yaml.example config.yaml")
        print("2. 编辑 config.yaml，确认本地引擎配置")
        print("3. 安装依赖: pip install -r requirements.txt")
        print("4. 运行项目: python -m src.core.main --help")
        return 0
    else:
        print("[FAIL] 测试失败，请修复问题后重试。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
