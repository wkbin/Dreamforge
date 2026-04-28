#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from src.core.config import Config
from src.core.path_provider import PathProvider
from src.utils.file_utils import load_markdown_data


class RuleBook:
    """Loads editable rule assets from local markdown files."""

    FILE_MAP = {
        "distillation": "distillation_rules.md",
        "speaker": "speaker_rules.md",
        "relationships": "relationship_rules.md",
        "persona": "persona_rules.md",
    }

    def __init__(
        self,
        config: Config,
        *,
        path_provider: PathProvider,
        base_dir: Optional[str | Path] = None,
    ):
        if config is None or path_provider is None:
            raise ValueError("RuleBook requires injected config and path_provider")
        self.config = config
        self.path_provider = path_provider
        self.base_dir = Path(base_dir) if base_dir else self.path_provider.rules_root()
        self._sections = self._load_sections()

    def section(self, name: str) -> Dict[str, Any]:
        value = self._sections.get(name, {})
        return dict(value) if isinstance(value, dict) else {}

    def reload(self) -> None:
        self._sections = self._load_sections()

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.section(section).get(key, default)

    def _load_sections(self) -> Dict[str, Dict[str, Any]]:
        sections: Dict[str, Dict[str, Any]] = {}
        for section_name, filename in self.FILE_MAP.items():
            path = self.base_dir / filename
            payload = load_markdown_data(path, default={}) or {}
            sections[section_name] = payload if isinstance(payload, dict) else {}
        return sections
