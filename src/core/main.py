#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Backward-compatible CLI wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.core.cli_app import ChatIntent, ZaomengCLI as _SharedZaomengCLI
from src.modules.chat_engine import ChatEngine  # Backward-compatible patch target for tests/tools.


class ZaomengCLI(_SharedZaomengCLI):
    def _build_chat_engine(self) -> ChatEngine:
        parts = self._fresh_runtime_parts()
        return ChatEngine(
            self.config,
            llm=parts.llm,
            reflection=parts.reflection,
            speaker=parts.speaker,
            distiller=parts.distiller,
            rulebook=parts.rulebook,
            path_provider=parts.path_provider,
        )


def main() -> None:
    ZaomengCLI().run()


__all__ = ["ChatEngine", "ChatIntent", "ZaomengCLI", "main"]


if __name__ == "__main__":
    main()
