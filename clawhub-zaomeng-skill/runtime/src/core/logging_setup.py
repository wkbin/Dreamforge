#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Optional

from src.core.config import Config


def setup_logging(config: Optional[Config] = None) -> None:
    resolved_config = config or Config()
    system_config = resolved_config.get("system", {}) if isinstance(resolved_config.get("system", {}), dict) else {}
    level_name = str(system_config.get("log_level", "INFO")).strip().upper() or "INFO"
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root_logger.addHandler(handler)

    root_logger.setLevel(level)
