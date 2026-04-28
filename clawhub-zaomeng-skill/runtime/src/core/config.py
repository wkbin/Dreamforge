#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载、验证和管理项目配置
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """配置管理类"""

    SUPPORTED_PROVIDERS = (
        "local-rule-engine",
        "openai",
        "openai-compatible",
        "anthropic",
        "ollama",
    )
    
    DEFAULT_CONFIG = {
        "llm": {
            "provider": "local-rule-engine",
            "model": "local-rule-engine",
            "temperature": 0.0,
            "max_tokens": 0,
            "base_url": "",
            "api_key": "",
            "api_key_env": "",
            "timeout_seconds": 120,
        },
        "engine": {
            "name": "local-rule-engine",
            "pseudo_cost_per_1k_tokens_usd": 0.001
        },
        "cost_control": {
            "daily_budget_usd": 10.0,
            "enable_cost_warning": True,
            "warning_threshold": 0.8
        },
        "text_processing": {
            "chunk_size_tokens": 8000,
            "chunk_overlap_tokens": 200,
            "min_sentence_length": 10
        },
        "distillation": {
            "max_characters": 10,
            "min_appearances": 3,
            "traits_max_count": 10,
            "values_dimensions": [
                "勇气", "智慧", "善良", "忠诚", "野心", 
                "正义", "自由", "责任"
            ]
        },
        "relationships": {
            "dimensions": [
                "trust", "affection", "power_gap", 
                "conflict_point", "typical_interaction"
            ]
        },
        "chat_engine": {
            "max_history_turns": 10,
            "max_speakers_per_turn": 4,
            "token_limit_per_turn": 500,
            "enable_cost_display": True,
            "generation_mode": "auto",
            "enable_turn_interactions": True,
            "allow_character_silence": True,
            "min_reply_relevance": 4,
            "llm_history_messages": 8,
        },
        "paths": {
            "characters": "data/characters",
            "relations": "data/relations",
            "sessions": "data/sessions",
            "corrections": "data/corrections",
            "logs": "logs",
            "rules": "rules"
        },
        "system": {
            "log_level": "INFO",
            "enable_auto_save": True,
            "backup_interval_hours": 24
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径，如为None则自动查找
        """
        self.config_path = self._find_config(config_path)
        self.project_root = self._resolve_project_root()
        self.config = self._load_config()
        self._ensure_paths()

    def _resolve_project_root(self) -> Path:
        """解析项目根目录，避免输出路径依赖当前工作目录。"""
        if self.config_path:
            return self.config_path.parent.resolve()
        return Path(__file__).resolve().parents[2]
        
    def _find_config(self, config_path: Optional[str]) -> Optional[Path]:
        """查找配置文件"""
        if config_path and os.path.exists(config_path):
            return Path(config_path)
        
        # 查找可能的配置文件位置
        possible_paths = [
            "config.yaml",
            "config.yml",
            "config/config.yaml",
            os.path.expanduser("~/.zaomeng/config.yaml")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return Path(path)
        
        return None
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if self.config_path:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
            except Exception as e:
                print(f"警告: 无法加载配置文件 {self.config_path}: {e}")
                config = {}
        else:
            config = {}
        
        # 合并默认配置
        merged_config = self._merge_dicts(self.DEFAULT_CONFIG, config)
        
        # 验证必需配置
        self._validate_config(merged_config)
        
        return merged_config
    
    def _merge_dicts(self, base: Dict, overlay: Dict) -> Dict:
        """深度合并两个字典"""
        result = base.copy()
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _validate_config(self, config: Dict[str, Any]):
        """验证配置"""
        provider = str(config.get("llm", {}).get("provider", "local-rule-engine")).strip().lower()
        if provider not in self.SUPPORTED_PROVIDERS:
            print(
                "警告: 未识别的 llm.provider="
                f"{provider}，当前支持: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )
    
    def _ensure_paths(self):
        """确保所有必需的目录存在"""
        for path_key in ["characters", "relations", "sessions", "corrections", "logs", "rules"]:
            path = self.get_path(path_key)
            os.makedirs(path, exist_ok=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_path(self, path_key: str) -> str:
        """获取路径配置，转换为绝对路径"""
        relative_path = self.get(f"paths.{path_key}")
        if not relative_path:
            return ""
        
        # 如果是绝对路径，直接返回
        if os.path.isabs(relative_path):
            return relative_path
        
        # 否则相对于配置文件所在目录或项目根目录
        return str((self.project_root / relative_path).resolve())
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取 LLM 配置"""
        return self.get("llm", {})
    
    def get_distillation_config(self) -> Dict[str, Any]:
        """获取蒸馏配置"""
        return self.get("distillation", {})
    
    def get_cost_config(self) -> Dict[str, Any]:
        """获取成本控制配置"""
        return self.get("cost_control", {})
    
    def save(self, path: Optional[str] = None):
        """保存配置到文件"""
        save_path = Path(path) if path else self.config_path
        
        if not save_path:
            save_path = Path("config.yaml")
        
        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
        
        print(f"配置已保存到: {save_path}")
    
    def update(self, updates: Dict[str, Any]):
        """更新配置"""
        self.config = self._merge_dicts(self.config, updates)
    
    def get_supported_models(self) -> list:
        """保留兼容接口，返回支持的 provider 列表"""
        return list(self.SUPPORTED_PROVIDERS)
    
    def set_api_key(self, api_key: str):
        """兼容旧接口；本地模式不需要 API key"""
        self.config["llm"]["api_key"] = api_key
    
    def set_model(self, model: str):
        """设置引擎名（兼容旧接口）"""
        self.config["llm"]["model"] = model
