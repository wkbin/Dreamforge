#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.config import Config
from src.core.llm_client import LLMClient
from src.core.path_provider import PathProvider
from src.core.rulebook import RuleBook
from src.modules.chat_engine import ChatEngine
from src.modules.distillation import NovelDistiller
from src.modules.reflection import ReflectionEngine
from src.modules.relationships import RelationshipExtractor
from src.modules.speaker import Speaker
from src.utils.token_counter import TokenCounter


@dataclass
class RuntimeParts:
    config: Config
    path_provider: PathProvider
    rulebook: RuleBook
    llm: LLMClient
    token_counter: TokenCounter
    reflection: ReflectionEngine
    distiller: NovelDistiller
    speaker: Speaker
    extractor: RelationshipExtractor
    _chat_engine: Optional[ChatEngine] = None

    def create_chat_engine(self) -> ChatEngine:
        if self._chat_engine is None:
            self._chat_engine = ChatEngine(
                self.config,
                llm=self.llm,
                reflection=self.reflection,
                speaker=self.speaker,
                distiller=self.distiller,
                rulebook=self.rulebook,
                path_provider=self.path_provider,
            )
        return self._chat_engine

    @property
    def chat_engine(self) -> ChatEngine:
        return self.create_chat_engine()

    @chat_engine.setter
    def chat_engine(self, value: Optional[ChatEngine]) -> None:
        self._chat_engine = value


def build_runtime_parts(config: Optional[Config] = None) -> RuntimeParts:
    resolved_config = config or Config()
    path_provider = PathProvider(resolved_config)
    rulebook = RuleBook(resolved_config, path_provider=path_provider)
    llm = LLMClient(resolved_config)
    token_counter = TokenCounter()
    reflection = ReflectionEngine(resolved_config, path_provider=path_provider)
    distiller = NovelDistiller(
        resolved_config,
        llm_client=llm,
        token_counter=token_counter,
        rulebook=rulebook,
        path_provider=path_provider,
    )
    speaker = Speaker(resolved_config, correction_service=reflection, rulebook=rulebook)
    extractor = RelationshipExtractor(
        resolved_config,
        llm_client=llm,
        token_counter=token_counter,
        distiller=distiller,
        rulebook=rulebook,
        path_provider=path_provider,
    )
    return RuntimeParts(
        config=resolved_config,
        path_provider=path_provider,
        rulebook=rulebook,
        llm=llm,
        token_counter=token_counter,
        reflection=reflection,
        distiller=distiller,
        speaker=speaker,
        extractor=extractor,
    )
