#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""zaomeng CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.core.config import Config
from src.core.host_llm_adapter import HostProvidedLLM
from src.core.logging_utils import setup_logging
from src.core.runtime_factory import RuntimeDependencyOverrides, RuntimeParts, build_runtime_parts
from src.core.exceptions import ZaomengError
from src.modules.chat_engine import ChatEngine  # Backward-compatible patch target for tests/tools.
from src.utils.file_utils import (
    load_text_argument,
    normalize_character_name,
    novel_id_from_input,
    parse_character_argument,
    save_markdown_data,
)


@dataclass
class ChatIntent:
    mode: str
    controlled_character: str = ""
    target_characters: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    self_profile: dict[str, str] = field(default_factory=dict)
    message: str = ""
    setup_only: bool = False


class ZaomengCLI:
    ACT_SETUP_PATTERNS = (
        r"让我扮演",
        r"我来扮演",
        r"我要扮演",
        r"我扮演",
        r"我想代入",
        r"让我代入",
        r"代入.+群聊",
        r"作为.+参与",
        r"你扮演",
        r"你来扮演",
        r"进入.+act",
        r"进入.+行动模式",
        r"开启.+act",
        r"切换到.+act",
        r"我说一句",
        r"回一句",
        r"一问一答",
        r"对聊",
        r"你来回我",
        r"你让.+回我",
        r"你驱动",
    )
    OBSERVE_SETUP_PATTERNS = (
        r"进入.+群聊模式",
        r"开启.+群聊模式",
        r"进入.+observe",
        r"切换到.+observe",
        r"开始群聊",
        r"让.+群聊",
        r"多人聊天",
    )
    INSERT_SETUP_PATTERNS = (
        r"让我以我自己进入",
        r"让我以自己进入",
        r"我想以我自己进入",
        r"我想进入.+和.+聊天",
        r"把我放进",
        r"让我进入.+场景",
        r"我本人进入",
        r"我自己进入",
    )
    ACT_MODE_HINTS = (
        "act",
        "行动模式",
        "扮演",
        "代入",
        "我说一句",
        "回一句",
        "回我",
        "回复我",
        "接我的话",
        "一问一答",
        "对聊",
    )
    OBSERVE_MODE_HINTS = ("群聊模式", "observe", "围绕", "各说一句", "大家聊", "让大家", "多人聊", "群聊")
    INSERT_MODE_HINTS = ("我自己", "我本人", "外来者", "进入场景", "进入小说", "把我放进", "和他们聊天")

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        runtime_parts_builder: Callable[[Optional[Config]], RuntimeParts] = build_runtime_parts,
        host_context: Any = None,
    ) -> None:
        self._runtime_parts_builder = runtime_parts_builder
        self._host_context = host_context
        self.parts = self._build_runtime_parts(config or Config())
        self.config = self.parts.config
        setup_logging(self.config)
        self.path_provider = self.parts.path_provider
        self.rulebook = self.parts.rulebook
        self.parser = self._create_parser()

    @classmethod
    def from_host_context(
        cls,
        context: Any,
        *,
        config: Optional[Config] = None,
        runtime_parts_builder: Callable[[Optional[Config]], RuntimeParts] = build_runtime_parts,
    ) -> "ZaomengCLI":
        return cls(config=config, runtime_parts_builder=runtime_parts_builder, host_context=context)

    def _build_runtime_parts(self, config: Config) -> RuntimeParts:
        if self._host_context is None:
            return self._runtime_parts_builder(config)
        if self._runtime_parts_builder is build_runtime_parts:
            return self._runtime_parts_builder(config, host_context=self._host_context)
        host_llm = HostProvidedLLM.from_host_context(self._host_context)
        return self._runtime_parts_builder(
            config,
            overrides=RuntimeDependencyOverrides(llm=host_llm),
        )

    def _fresh_runtime_parts(self) -> RuntimeParts:
        if self._host_context is None and self._runtime_parts_builder is build_runtime_parts:
            return self.parts.fork()
        return self._build_runtime_parts(self.config)

    def _build_chat_engine(self) -> ChatEngine:
        parts = self._fresh_runtime_parts()
        return parts.create_chat_engine()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description=(
                "zaomeng: local rule-based novel character tooling. "
                "Not a general-purpose LLM chatbot."
            ),
            epilog="See README.md for project overview and usage notes.",
        )
        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        distill_parser = subparsers.add_parser(
            "distill",
            help="Distill character profiles from a novel",
            description=(
                "Distill character profiles from a novel.\n\n"
                "Interaction rule:\n"
                "  - By default this command asks for cost confirmation.\n"
                "  - In tool-driven or non-interactive runs, use `--force` after the user has agreed.\n"
                "  - Use `--characters` when the user already knows the target roles."
            ),
            formatter_class=argparse.RawTextHelpFormatter,
        )
        distill_parser.add_argument("--novel", "-n", required=True, help="Novel file path (.txt or .epub)")
        distill_parser.add_argument("--characters", "-c", help="Comma-separated target character names")
        distill_parser.add_argument(
            "--characters-file",
            help="UTF-8 text file containing target character names (newline/comma separated)",
        )
        distill_parser.add_argument("--output", "-o", help="Optional output directory override")
        distill_parser.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Skip cost confirmation for non-interactive runs",
        )

        chat_parser = subparsers.add_parser(
            "chat",
            help="Run constrained roleplay chat via CLI",
            description=(
                "Run constrained roleplay chat.\n\n"
                "Important:\n"
                "  - This is an LLM-first character chat workflow.\n"
                "  - The runtime prepares persona, relation, and scene constraints for generation.\n"
                "  - For agent use, default to `--message`.\n"
                "  - Do not rebuild chat manually from source files.\n\n"
                "Prerequisites:\n"
                "  1. Run `distill` first so character profiles exist.\n"
                "  2. Run `extract` first if you want relation-aware replies.\n"
                "  3. `--mode auto` can infer act/observe/insert from natural language setup requests.\n\n"
                "Usage modes:\n"
                "  - Interactive: omit `--message` and chat in the terminal.\n"
                "  - Single-turn: pass `--message` to run one turn and exit.\n"
                "  - Setup-only: pass a natural language mode request and zaomeng will create a session."
            ),
            epilog=(
                "Inline commands in interactive mode:\n"
                "  /save\n"
                "  /reflect\n"
                "  /correct 角色|对象|原句|修正句|原因\n"
                "  /quit"
            ),
            formatter_class=argparse.RawTextHelpFormatter,
        )
        chat_parser.add_argument("--novel", "-n", required=True, help="Novel path or novel name")
        chat_parser.add_argument(
            "--mode",
            "-m",
            choices=["auto", "observe", "act", "insert"],
            default="auto",
            help="`auto` infers act/observe/insert from natural language setup requests",
        )
        chat_parser.add_argument("--character", "-c", help="Controlled character in act mode")
        chat_parser.add_argument("--session", "-s", help="Restore an existing session ID")
        chat_parser.add_argument("--message", help="Run a single non-interactive turn and exit")
        chat_parser.add_argument("--message-file", help="UTF-8 text file containing one chat request/message")
        chat_parser.add_argument(
            "--session-summary-out",
            help="Optional JSON file path for a host-facing session summary snapshot",
        )
        chat_parser.add_argument(
            "--chat-result-out",
            help="Optional JSON file path for a host-facing chat result payload",
        )
        chat_parser.add_argument(
            "--chat-status-out",
            help="Optional JSON file path for a host-facing chat status payload",
        )
        chat_parser.add_argument("--self-name", help="Display name when using insert mode")
        chat_parser.add_argument("--self-identity", help="Scene identity when using insert mode")
        chat_parser.add_argument(
            "--self-style",
            choices=["natural", "immersive", "probing"],
            help="Interaction style for insert mode",
        )
        chat_parser.add_argument(
            "--self-impact",
            choices=["light", "scene", "relationship"],
            help="How much the self-insert participant may influence the scene",
        )

        view_parser = subparsers.add_parser("view", help="View a distilled character profile")
        view_parser.add_argument("--character", "-c", required=True, help="Character name")
        view_parser.add_argument("--novel", "-n", help="Optional novel path/name for scoping")

        correct_parser = subparsers.add_parser("correct", help="Persist a correction example")
        correct_parser.add_argument("--session", "-s", required=True, help="Session ID")
        correct_parser.add_argument("--message", "-m", required=True, help="Original message")
        correct_parser.add_argument("--corrected", "-c", required=True, help="Corrected message")
        correct_parser.add_argument("--character", "-r", help="Character name")
        correct_parser.add_argument("--target", "-t", help="Target character name")
        correct_parser.add_argument("--reason", help="Correction reason")

        extract_parser = subparsers.add_parser(
            "extract",
            help="Extract relationship graph from a novel",
            description=(
                "Extract a relationship graph from a novel.\n\n"
                "Interaction rule:\n"
                "  - By default this command asks for cost confirmation.\n"
                "  - In tool-driven or non-interactive runs, use `--force` after the user has agreed.\n"
                "  - Run `distill` first if you also need character profiles for chat."
            ),
            formatter_class=argparse.RawTextHelpFormatter,
        )
        extract_parser.add_argument("--novel", "-n", required=True, help="Novel file path")
        extract_parser.add_argument("--characters", "-c", help="Comma-separated target character names")
        extract_parser.add_argument(
            "--characters-file",
            help="UTF-8 text file containing target character names (newline/comma separated)",
        )
        extract_parser.add_argument("--output", "-o", help="Optional output path override")
        extract_parser.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Skip cost confirmation for non-interactive runs",
        )

        return parser

    def run(self) -> None:
        args = self.parser.parse_args()
        if not args.command:
            self.parser.print_help()
            return

        try:
            if args.command == "distill":
                self._handle_distill(args)
            elif args.command == "chat":
                self._handle_chat(args)
            elif args.command == "view":
                self._handle_view(args)
            elif args.command == "correct":
                self._handle_correct(args)
            elif args.command == "extract":
                self._handle_extract(args)
            else:
                raise ValueError(f"Unknown command: {args.command}")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(0)
        except Exception as exc:
            print(f"Error: {exc}")
            sys.exit(1)

    def _handle_distill(self, args: argparse.Namespace) -> None:
        print("=== Character Distillation ===")
        if args.force:
            print("Confirmation: skipped via --force")
        else:
            print("This command is confirmation-gated. Use --force only after confirming with the user.")
        parts = self._fresh_runtime_parts()
        self._require_generation_llm(parts, "distill")
        distiller = parts.distiller

        if not args.force:
            cost_estimate = distiller.estimate_cost(args.novel)
            print(f"Estimated cost: ${cost_estimate:.2f} USD")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm != "y":
                print("Operation cancelled.")
                return

        characters = parse_character_argument(args.characters, args.characters_file) or None
        output_dir = args.output or str(Path(self.config.get_path("characters")) / novel_id_from_input(args.novel))

        print(f"Processing novel: {args.novel}")
        result = distiller.distill(
            args.novel,
            characters,
            output_dir,
            progress_callback=self._print_distill_progress,
        )

        print(f"\nDone. Extracted {len(result)} characters:")
        for char_name in result:
            print(f"  - {char_name}")

        print("\n正在生成人物关系图谱...")
        extractor = parts.extractor
        relations = extractor.extract(
            args.novel,
            characters=characters,
            progress_callback=self._print_relation_progress,
        )
        novel_id = novel_id_from_input(args.novel)
        graph_path = self.path_provider.visualization_file(novel_id, ".html")
        print(f"\n关系图谱已生成，共 {len(relations)} 条关系。")
        print(f"图谱链接: {graph_path}")
        print("你现在可以查看关系图谱，或进入 act 模式 / observe 模式继续。")

    def _handle_chat(self, args: argparse.Namespace) -> None:
        print("=== Chat Engine ===")
        engine = self._build_chat_engine()
        self._require_generation_llm(engine, "chat")
        session: Optional[dict] = None

        if args.session:
            session = engine.restore_session(args.session)
            print(f"Restored session: {session['title']}")
            if session.get("mode") == "insert":
                profile = session.get("state", {}).get("self_insert", {})
                print(
                    "Reusing self insert card: "
                    f"{profile.get('display_name', '你')} | "
                    f"{profile.get('scene_identity', '外来访客')} | "
                    f"{profile.get('interaction_style', 'immersive')} | "
                    f"{profile.get('plot_agency', 'light')}"
                )
        elif args.novel:
            print(f"Loading scoped profiles for: {args.novel}")

        args.message = load_text_argument(args.message, getattr(args, "message_file", None))
        args.character = load_text_argument(args.character)
        intent = self._resolve_chat_intent(engine, args, session)

        if session is None:
            session = engine.create_session(args.novel, intent.mode)
        session["mode"] = intent.mode
        self._apply_chat_session_state(engine, session, intent)

        if args.message:
            if intent.setup_only:
                engine._save_session(session)
                self._print_setup_confirmation(session, intent)
                summary = self._write_session_summary(engine, session, args.session_summary_out)
                self._write_chat_outputs(
                    session,
                    args,
                    action="setup",
                    summary=summary,
                    responses=[],
                    success=True,
                )
                return

            responses = self._run_single_chat_turn(
                engine,
                session,
                intent.mode,
                intent.controlled_character,
                intent.message,
            )
            for speaker, message in responses:
                print(f"{speaker}: {message}")
            engine.print_turn_cost()
            engine.print_correction_hint(session)
            summary = self._write_session_summary(engine, session, args.session_summary_out, latest_responses=responses)
            self._write_chat_outputs(
                session,
                args,
                action="single_turn",
                summary=summary,
                responses=responses,
                success=True,
            )
            return

        print("This is an interactive command. Prepare your first user turn before entering the session.")
        summary = self._write_session_summary(engine, session, args.session_summary_out)
        self._write_chat_outputs(
            session,
            args,
            action="interactive_ready",
            summary=summary,
            responses=[],
            success=True,
        )
        if intent.mode == "act":
            role = intent.controlled_character or "<character>"
            print(f"Mode: act | Controlled role: {role}")
            print("Starter input example: 我先表态，你们再接。")
            if not intent.controlled_character:
                raise ValueError("--character is required in act mode unless the request names the role.")
            engine.act_mode(session, intent.controlled_character)
            return

        if intent.mode == "insert":
            card = session.get("state", {}).get("self_insert", {})
            print(f"Mode: insert | Self name: {card.get('display_name', '你')}")
            print("Starter input example: 初来乍到，我能否先在这里坐一会儿？")
            engine.insert_mode(session)
            return

        print("Mode: observe")
        print("Starter input example: 请让大家围绕这件事各说一句。")
        print("Inline commands: /save /reflect /correct /quit")
        engine.observe_mode(session)

    @staticmethod
    def _run_single_chat_turn(
        engine: ChatEngine,
        session: dict,
        mode: str,
        controlled_character: str,
        message: str,
    ) -> list[tuple[str, str]]:
        if mode == "act":
            if not controlled_character:
                raise ValueError("--character is required in act mode")
            return engine.act_once(session, controlled_character, message)
        if mode == "insert":
            return engine.insert_once(session, message)
        return engine.observe_once(session, message)

    def _resolve_chat_intent(
        self,
        engine: ChatEngine,
        args: argparse.Namespace,
        session: Optional[dict],
    ) -> ChatIntent:
        text = load_text_argument(args.message)
        candidates = session.get("characters", []) if session else self._load_candidate_names(engine, args.novel)
        explicit_mode = "" if args.mode == "auto" else args.mode
        inferred_mode = self._infer_chat_mode(text)

        mode = explicit_mode or ""
        if not mode and args.character:
            mode = "act"
        if not mode:
            mode = inferred_mode or (session.get("mode") if session else "observe")

        ordered_mentions = engine._mentioned_characters(text, candidates) if text and candidates else []
        controlled = self._resolve_character_reference(engine, args.character, candidates)
        controlled = controlled or self._infer_controlled_character(mode, text, ordered_mentions, candidates, session)
        self_profile = self._build_self_insert_profile(args, text, session) if mode == "insert" else {}

        if mode == "observe" and not explicit_mode and inferred_mode == "act":
            mode = "act"
            controlled = controlled or self._infer_controlled_character(mode, text, ordered_mentions, candidates, session)

        targets = self._infer_target_characters(mode, controlled, ordered_mentions, candidates, session)
        participants = self._infer_participants(mode, controlled, targets, ordered_mentions)
        setup_only = self._is_setup_only_request(text, mode, controlled, targets)

        return ChatIntent(
            mode=mode,
            controlled_character=controlled,
            target_characters=targets,
            participants=participants,
            self_profile=self_profile,
            message="" if setup_only else text,
            setup_only=setup_only,
        )

    def _apply_chat_session_state(self, engine: ChatEngine, session: dict, intent: ChatIntent) -> None:
        state = session.setdefault("state", {})
        state.setdefault("focus_targets", {})

        should_scope_participants = bool(intent.participants) and (
            intent.setup_only or not session.get("history")
        )
        if should_scope_participants:
            session["characters"] = list(intent.participants)
            state["selected_characters"] = list(intent.participants)
            state["relation_matrix"] = engine._build_relation_matrix(intent.participants, session.get("novel_id"))

        if intent.controlled_character:
            state["controlled_character"] = intent.controlled_character

        if intent.controlled_character and len(intent.target_characters) == 1:
            state["focus_targets"][intent.controlled_character] = intent.target_characters[0]

        if intent.mode == "insert":
            state["self_insert"] = self._merge_self_insert_profile(
                state.get("self_insert", {}),
                intent.self_profile,
            )

    @staticmethod
    def _print_setup_confirmation(session: dict, intent: ChatIntent) -> None:
        print(f"Session ready: {session['id']}")
        print(f"Mode: {intent.mode}")
        if intent.controlled_character:
            print(f"Controlled role: {intent.controlled_character}")
        if intent.target_characters:
            print(f"Primary target: {', '.join(intent.target_characters)}")
        if intent.participants:
            print(f"Participants: {', '.join(intent.participants)}")
        if intent.mode == "insert":
            profile = session.get("state", {}).get("self_insert", {})
            print(
                "Self insert card: "
                f"{profile.get('display_name', '你')} | "
                f"{profile.get('scene_identity', '外来访客')} | "
                f"{profile.get('interaction_style', 'immersive')} | "
                f"{profile.get('plot_agency', 'light')}"
            )
            print("Next step: send one line as yourself, and the cast will reply from inside the scene.")
            for line in ZaomengCLI._self_insert_onboarding_lines(profile):
                print(line)

    @staticmethod
    def _load_candidate_names(engine: ChatEngine, novel: str) -> list[str]:
        profiles = engine._load_character_profiles(novel_id=novel_id_from_input(novel))
        return list(profiles.keys())

    def _infer_chat_mode(self, text: str) -> str:
        if not text:
            return ""
        lowered = text.lower()
        if any(token in text for token in self.INSERT_MODE_HINTS):
            return "insert"
        if any(token in lowered for token in ("act模式", "进入act", "切换到act", " act ")):
            return "act"
        if any(token in text for token in self.ACT_MODE_HINTS):
            return "act"
        if any(token in text for token in self.OBSERVE_MODE_HINTS):
            return "observe"
        return ""

    def _infer_controlled_character(
        self,
        mode: str,
        text: str,
        ordered_mentions: list[str],
        candidates: list[str],
        session: Optional[dict],
    ) -> str:
        if mode != "act":
            return ""
        if len(ordered_mentions) >= 2 and any(
            token in text for token in ("让我扮演", "我来扮演", "我要扮演", "我扮演", "我想代入", "让我代入", "聊天", "对话", "对聊", "群聊", "act")
        ):
            return ordered_mentions[0]
        if len(ordered_mentions) == 1 and any(token in text for token in ("扮演", "饰演", "由我", "我来", "代入", "作为")):
            return ordered_mentions[0]
        if len(ordered_mentions) == 1 and any(token in text for token in ("我说一句", "回一句", "回我")) and len(candidates) == 2:
            target = ordered_mentions[0]
            return next((name for name in candidates if name != target), "")
        if session:
            stored = session.get("state", {}).get("controlled_character", "")
            if stored in candidates:
                return stored
        return ""

    @staticmethod
    def _infer_target_characters(
        mode: str,
        controlled: str,
        ordered_mentions: list[str],
        candidates: list[str],
        session: Optional[dict],
    ) -> list[str]:
        if mode != "act":
            return ordered_mentions

        targets = [name for name in ordered_mentions if name != controlled]
        if targets:
            return targets

        if controlled and session:
            remembered = session.get("state", {}).get("focus_targets", {}).get(controlled, "")
            if remembered in candidates:
                return [remembered]
        return []

    @staticmethod
    def _infer_participants(
        mode: str,
        controlled: str,
        targets: list[str],
        ordered_mentions: list[str],
    ) -> list[str]:
        if mode == "act":
            participants: list[str] = []
            if controlled:
                participants.append(controlled)
            for name in targets:
                if name not in participants:
                    participants.append(name)
            return participants
        if mode == "insert":
            return ordered_mentions
        return ordered_mentions

    def _is_setup_only_request(
        self,
        text: str,
        mode: str,
        controlled: str,
        targets: list[str],
    ) -> bool:
        if not text:
            return False
        if mode == "act":
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.ACT_SETUP_PATTERNS):
                return True
            if "模式" in text and controlled:
                return True
            if controlled and targets and any(token in text for token in ("聊天", "对话", "互动", "群聊")):
                return True
        if mode == "observe":
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.OBSERVE_SETUP_PATTERNS):
                return True
        if mode == "insert":
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.INSERT_SETUP_PATTERNS):
                return True
            if targets and any(token in text for token in ("进入", "场景", "小说", "群聊", "聊天")):
                return True
        return False

    def _build_self_insert_profile(
        self,
        args: argparse.Namespace,
        text: str,
        session: Optional[dict],
    ) -> dict[str, str]:
        existing = dict(session.get("state", {}).get("self_insert", {})) if session else {}
        inferred_name = ChatEngine._extract_self_insert_name(text)
        inferred_identity = ChatEngine._extract_self_insert_identity(text)
        display_name = (
            load_text_argument(getattr(args, "self_name", ""))
            or inferred_name
            or existing.get("display_name", "")
            or ChatEngine.SELF_INSERT_DEFAULT_NAME
        )
        scene_identity = (
            load_text_argument(getattr(args, "self_identity", ""))
            or inferred_identity
            or existing.get("scene_identity", "")
            or ChatEngine.SELF_INSERT_DEFAULT_IDENTITY
        )
        interaction_style = load_text_argument(getattr(args, "self_style", "")) or existing.get("interaction_style", "")
        plot_agency = load_text_argument(getattr(args, "self_impact", "")) or existing.get("plot_agency", "")

        if not interaction_style:
            interaction_style = "probing" if "试探" in text else "immersive"
        if not plot_agency:
            plot_agency = "scene" if "推进" in text or "剧情" in text else "light"

        return {
            "display_name": display_name,
            "scene_identity": scene_identity,
            "interaction_style": interaction_style,
            "plot_agency": plot_agency,
        }

    @staticmethod
    def _merge_self_insert_profile(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, str]:
        merged = {
            "display_name": ChatEngine.SELF_INSERT_DEFAULT_NAME,
            "scene_identity": ChatEngine.SELF_INSERT_DEFAULT_IDENTITY,
            "interaction_style": "immersive",
            "plot_agency": "light",
        }
        for source in (base or {}, incoming or {}):
            for key in merged:
                value = str(source.get(key, "")).strip() if isinstance(source, dict) else ""
                if value:
                    merged[key] = value
        return merged

    @staticmethod
    def _self_insert_onboarding_lines(profile: dict[str, Any]) -> list[str]:
        display_name = str(profile.get("display_name", "")).strip()
        scene_identity = str(profile.get("scene_identity", "")).strip()
        missing_name = display_name in {"", ChatEngine.SELF_INSERT_DEFAULT_NAME}
        missing_identity = scene_identity in {"", ChatEngine.SELF_INSERT_DEFAULT_IDENTITY}
        if not missing_name and not missing_identity:
            return []

        hints = ["First-time insert hint:"]
        if missing_name:
            hints.append("- You can name yourself in-scene, for example: “我叫阿青。”")
        if missing_identity:
            hints.append("- You can also define your scene identity, for example: “我是初到贾府的新客。”")
        hints.append("- You can do this naturally in your next line; no separate command is required.")
        return hints

    @staticmethod
    def _write_session_summary(
        engine: ChatEngine,
        session: dict[str, Any],
        output_path: Optional[str],
        *,
        latest_responses: Optional[list[tuple[str, str]]] = None,
    ) -> dict[str, Any]:
        summary = engine.build_session_summary(session, latest_responses=latest_responses)
        if not output_path:
            return summary
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Session summary: {output}")
        return summary

    @staticmethod
    def _write_chat_outputs(
        session: dict[str, Any],
        args: argparse.Namespace,
        *,
        action: str,
        summary: dict[str, Any],
        responses: list[tuple[str, str]],
        success: bool,
    ) -> None:
        response_items = [{"speaker": speaker, "message": message} for speaker, message in responses]
        result_payload = {
            "kind": "zaomeng_chat_result",
            "action": action,
            "success": bool(success),
            "mode": summary.get("mode", session.get("mode", "")),
            "session_id": summary.get("session_id", session.get("id", "")),
            "novel_id": summary.get("novel_id", session.get("novel_id", "")),
            "participants": list(summary.get("participants", [])),
            "responses": response_items,
            "summary": summary,
            "updated_at": int(time.time()),
        }
        status_payload = {
            "kind": "host_capability_status",
            "capability": "chat",
            "status": "complete" if success else "error",
            "success": bool(success),
            "message": f"chat {action} completed" if success else f"chat {action} failed",
            "inputs": {
                "mode": session.get("mode", ""),
                "novel": session.get("novel", ""),
                "session_id": session.get("id", ""),
            },
            "outputs": {
                "session_summary_out": str(getattr(args, "session_summary_out", "") or ""),
                "chat_result_out": str(getattr(args, "chat_result_out", "") or ""),
                "responses_count": len(response_items),
            },
            "updated_at": int(time.time()),
        }

        result_path = getattr(args, "chat_result_out", None)
        if result_path:
            output = Path(result_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Chat result: {output}")
            status_payload["outputs"]["chat_result_out"] = str(output)

        status_path = getattr(args, "chat_status_out", None)
        if status_path:
            output = Path(status_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Chat status: {output}")

    @staticmethod
    def _resolve_character_reference(engine: ChatEngine, raw_name: Optional[str], candidates: list[str]) -> str:
        if not raw_name:
            return ""
        if not candidates:
            return normalize_character_name(raw_name)
        try:
            return engine._resolve_character_name(raw_name, candidates)
        except ValueError:
            return ""

    def _handle_view(self, args: argparse.Namespace) -> None:
        novel_id = novel_id_from_input(args.novel) if args.novel else None
        engine = self._build_chat_engine()
        profiles = engine._load_character_profiles(novel_id=novel_id)
        normalized = normalize_character_name(args.character)
        if normalized not in profiles:
            normalized = None

        if not normalized:
            scope = f" under novel '{novel_id}'" if novel_id else ""
            print(f"Profile not found for {args.character}{scope}.")
            return
        data = profiles[normalized]

        print(f"=== {args.character} ===")
        if data.get("novel_id"):
            print(f"Novel: {data['novel_id']}")
        print(f"Traits: {', '.join(data.get('core_traits', []))}")
        print(f"Speech: {data.get('speech_style', '')}")
        print("\nValues:")
        for dim, value in data.get("values", {}).items():
            print(f"  {dim}: {value}/10")
        if data.get("typical_lines"):
            print("\nTypical lines:")
            for line in data["typical_lines"][:5]:
                print(f"  - {line}")
        if data.get("evidence"):
            print("\nEvidence:")
            for key, value in data["evidence"].items():
                print(f"  {key}: {value}")

    def _handle_correct(self, args: argparse.Namespace) -> None:
        print("=== Save Correction ===")
        corrections_dir = Path(self.config.get_path("corrections"))
        corrections_dir.mkdir(parents=True, exist_ok=True)

        correction = {
            "session_id": args.session,
            "character": args.character or "unknown",
            "target": args.target or "",
            "original_message": args.message,
            "corrected_message": args.corrected,
            "reason": args.reason or "",
            "timestamp": int(time.time()),
        }

        filename = f"correction_{args.session}_{correction['timestamp']}.md"
        filepath = corrections_dir / filename
        save_markdown_data(
            filepath,
            correction,
            title="CORRECTION",
            summary=[
                f"- character: {correction['character']}",
                f"- target: {correction['target']}",
                f"- reason: {correction['reason']}",
            ],
        )

        print(f"Saved correction: {filepath}")

    def _handle_extract(self, args: argparse.Namespace) -> None:
        print("=== Relationship Extraction ===")
        if args.force:
            print("Confirmation: skipped via --force")
        else:
            print("This command is confirmation-gated. Use --force only after confirming with the user.")
        parts = self._fresh_runtime_parts()
        self._require_generation_llm(parts, "extract")
        extractor = parts.extractor

        if not args.force:
            cost_estimate = extractor.estimate_cost(args.novel)
            print(f"Estimated cost: ${cost_estimate:.2f} USD")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm != "y":
                print("Operation cancelled.")
                return

        output_path = args.output
        characters = parse_character_argument(args.characters, args.characters_file) or None
        result = extractor.extract(
            args.novel,
            output_path,
            characters=characters,
            progress_callback=self._print_relation_progress,
        )

        print(f"\nDone. Extracted {len(result)} relationships:")
        for rel_key in list(result.keys())[:5]:
            print(f"  - {rel_key}")
        novel_id = novel_id_from_input(args.novel)
        graph_path = self.path_provider.visualization_file(novel_id, ".html")
        print(f"图谱链接: {graph_path}")
        print("你现在可以查看关系图谱，或进入 act 模式 / observe 模式继续。")

    @staticmethod
    def _print_distill_progress(stage: str, payload: dict[str, Any]) -> None:
        if stage == "text_loaded":
            print(f"已载入文本，分为 {payload.get('chunk_count', 0)} 个片段。")
            return
        if stage == "characters_ready":
            total = int(payload.get("total", 0))
            names = ", ".join(payload.get("characters", []))
            print(f"已锁定 {total} 个待蒸馏角色：{names}")
            return
        if stage == "drafting_character":
            print(
                f"正在整理角色素材 {payload.get('index', 0)}/{payload.get('total', 0)}："
                f"{payload.get('character', '')}"
            )
            return
        if stage == "refining_character":
            print(
                f"正在蒸馏角色 {payload.get('index', 0)}/{payload.get('total', 0)}："
                f"{payload.get('character', '')}"
            )
            return
        if stage == "character_done":
            print(
                f"已完成 {payload.get('index', 0)}/{payload.get('total', 0)}："
                f"{payload.get('character', '')}"
            )
            return
        if stage == "distill_done":
            print(f"人物蒸馏完成，共 {payload.get('total', 0)} 个角色。")

    @staticmethod
    def _print_relation_progress(stage: str, payload: dict[str, Any]) -> None:
        if stage == "text_loaded":
            print(f"关系抽取已载入文本，分为 {payload.get('chunk_count', 0)} 个片段。")
            return
        if stage == "characters_ready":
            print(f"关系抽取范围已确定，共 {payload.get('total', 0)} 个角色。")
            return
        if stage == "scanning_chunk":
            print(f"正在分析关系片段 {payload.get('index', 0)}/{payload.get('total', 0)}...")
            return
        if stage == "rendering_graph":
            print(f"正在生成人物关系图谱，共 {payload.get('relation_count', 0)} 条关系。")
            return
        if stage == "graph_done":
            print(f"人物关系图谱生成完毕：{payload.get('html_path', '')}")

    @staticmethod
    def _require_generation_llm(target: Any, operation: str) -> None:
        llm = getattr(target, "llm", None)
        if llm is None and hasattr(target, "create_chat_engine"):
            llm = getattr(target, "llm", None)
        if llm is None:
            llm = getattr(target, "parts", None)
        if llm is not None and hasattr(llm, "llm"):
            llm = llm.llm
        if llm is None or not getattr(llm, "is_generation_enabled", lambda: False)():
            raise ZaomengError(
                f"{operation} now requires an available LLM. "
                "Reuse the host model when running inside OpenClaw/Hermes/other agents, "
                "or configure OpenAI/Anthropic/Ollama for direct CLI runs."
            )


def main() -> None:
    ZaomengCLI().run()


if __name__ == "__main__":
    main()
