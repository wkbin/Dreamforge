#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""zaomeng CLI entrypoint."""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.core.config import Config
from src.core.logging_utils import setup_logging
from src.core.runtime_factory import RuntimeParts, build_runtime_parts
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
    message: str = ""
    setup_only: bool = False


class ZaomengCLI:
    ACT_SETUP_PATTERNS = (
        r"让我扮演",
        r"我来扮演",
        r"我要扮演",
        r"我扮演",
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
    ACT_MODE_HINTS = (
        "act",
        "行动模式",
        "扮演",
        "我说一句",
        "回一句",
        "回我",
        "回复我",
        "接我的话",
        "一问一答",
        "对聊",
    )
    OBSERVE_MODE_HINTS = ("群聊模式", "observe", "围绕", "各说一句", "大家聊", "让大家", "多人聊", "群聊")

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        runtime_parts_builder: Callable[[Optional[Config]], RuntimeParts] = build_runtime_parts,
    ) -> None:
        self._runtime_parts_builder = runtime_parts_builder
        self.parts = self._runtime_parts_builder(config or Config())
        self.config = self.parts.config
        setup_logging(self.config)
        self.path_provider = self.parts.path_provider
        self.rulebook = self.parts.rulebook
        self.parser = self._create_parser()

    def _fresh_runtime_parts(self) -> RuntimeParts:
        return self._runtime_parts_builder(self.config)

    def _build_chat_engine(self) -> ChatEngine:
        parts = self._fresh_runtime_parts()
        return parts.create_chat_engine()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description=(
                "zaomeng: local rule-based novel character tooling. "
                "Not a general-purpose LLM chatbot."
            ),
            epilog="See PROJECT.md for project notes.",
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
                "  - This is a local rule-based character engine.\n"
                "  - It is not a general-purpose LLM chatbot.\n"
                "  - For agent use, default to `--message`.\n"
                "  - Do not rebuild chat manually from source files.\n\n"
                "Prerequisites:\n"
                "  1. Run `distill` first so character profiles exist.\n"
                "  2. Run `extract` first if you want relation-aware replies.\n"
                "  3. `--mode auto` can infer act/observe from natural language setup requests.\n\n"
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
            choices=["auto", "observe", "act"],
            default="auto",
            help="`auto` infers act/observe from natural language setup requests",
        )
        chat_parser.add_argument("--character", "-c", help="Controlled character in act mode")
        chat_parser.add_argument("--session", "-s", help="Restore an existing session ID")
        chat_parser.add_argument("--message", help="Run a single non-interactive turn and exit")
        chat_parser.add_argument("--message-file", help="UTF-8 text file containing one chat request/message")

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
        distiller = self._fresh_runtime_parts().distiller

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
        result = distiller.distill(args.novel, characters, output_dir)

        print(f"\nDone. Extracted {len(result)} characters:")
        for char_name in result:
            print(f"  - {char_name}")

    def _handle_chat(self, args: argparse.Namespace) -> None:
        print("=== Chat Engine ===")
        engine = self._build_chat_engine()
        session: Optional[dict] = None

        if args.session:
            session = engine.restore_session(args.session)
            print(f"Restored session: {session['title']}")
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
            return

        print("This is an interactive command. Prepare your first user turn before entering the session.")
        if intent.mode == "act":
            role = intent.controlled_character or "<character>"
            print(f"Mode: act | Controlled role: {role}")
            print("Starter input example: 我先表态，你们再接。")
            if not intent.controlled_character:
                raise ValueError("--character is required in act mode unless the request names the role.")
            engine.act_mode(session, intent.controlled_character)
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

    @staticmethod
    def _load_candidate_names(engine: ChatEngine, novel: str) -> list[str]:
        profiles = engine._load_character_profiles(novel_id=novel_id_from_input(novel))
        return list(profiles.keys())

    def _infer_chat_mode(self, text: str) -> str:
        if not text:
            return ""
        lowered = text.lower()
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
            token in text for token in ("让我扮演", "我来扮演", "我要扮演", "我扮演", "聊天", "对话", "对聊", "act")
        ):
            return ordered_mentions[0]
        if len(ordered_mentions) == 1 and any(token in text for token in ("扮演", "饰演", "由我", "我来")):
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
            if controlled and targets and any(token in text for token in ("聊天", "对话", "互动")):
                return True
        if mode == "observe":
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.OBSERVE_SETUP_PATTERNS):
                return True
        return False

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
        extractor = self._fresh_runtime_parts().extractor

        if not args.force:
            cost_estimate = extractor.estimate_cost(args.novel)
            print(f"Estimated cost: ${cost_estimate:.2f} USD")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm != "y":
                print("Operation cancelled.")
                return

        output_path = args.output
        characters = parse_character_argument(args.characters, args.characters_file) or None
        result = extractor.extract(args.novel, output_path, characters=characters)

        print(f"\nDone. Extracted {len(result)} relationships:")
        for rel_key in list(result.keys())[:5]:
            print(f"  - {rel_key}")


def main() -> None:
    ZaomengCLI().run()


if __name__ == "__main__":
    main()
