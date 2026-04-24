#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""zaomeng CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.core.config import Config
from src.modules.chat_engine import ChatEngine
from src.modules.distillation import NovelDistiller
from src.modules.relationships import RelationshipExtractor
from src.utils.file_utils import find_character_file, novel_id_from_input


class ZaomengCLI:
    def __init__(self) -> None:
        self.config = Config()
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="zaomeng: local novel character distillation and chat tooling",
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
        distill_parser.add_argument("--output", "-o", help="Optional output directory override")
        distill_parser.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Skip cost confirmation for non-interactive runs",
        )

        chat_parser = subparsers.add_parser(
            "chat",
            help="Start an interactive or single-turn multi-character chat session",
            description=(
                "Start a chat session.\n\n"
                "Prerequisites:\n"
                "  1. Run `distill` first so character profiles exist.\n"
                "  2. Run `extract` first if you want relation-aware replies.\n"
                "  3. In `act` mode, pass `--character` for the role you control.\n\n"
                "Usage modes:\n"
                "  - Interactive: omit `--message` and chat in the terminal.\n"
                "  - Single-turn: pass `--message` to run one turn and exit.\n\n"
                "Starter inputs:\n"
                "  observe: 请让大家围绕这件事各说一句。\n"
                "  act: 我先表态，你们再接。"
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
        chat_parser.add_argument("--mode", "-m", choices=["observe", "act"], default="observe")
        chat_parser.add_argument("--character", "-c", help="Controlled character in act mode")
        chat_parser.add_argument("--session", "-s", help="Restore an existing session ID")
        chat_parser.add_argument(
            "--message",
            help="Run a single non-interactive turn and exit",
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
        distiller = NovelDistiller(self.config)

        if not args.force:
            cost_estimate = distiller.estimate_cost(args.novel)
            print(f"Estimated cost: ${cost_estimate:.2f} USD")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm != "y":
                print("Operation cancelled.")
                return

        characters = [item.strip() for item in args.characters.split(",")] if args.characters else None
        output_dir = args.output or str(Path(self.config.get_path("characters")) / novel_id_from_input(args.novel))

        print(f"Processing novel: {args.novel}")
        result = distiller.distill(args.novel, characters, output_dir)

        print(f"\nDone. Extracted {len(result)} characters:")
        for char_name in result:
            print(f"  - {char_name}")

    def _handle_chat(self, args: argparse.Namespace) -> None:
        print("=== Chat Engine ===")
        engine = ChatEngine(self.config)

        if args.session:
            session = engine.restore_session(args.session)
            print(f"Restored session: {session['title']}")
        else:
            print(f"Loading scoped profiles for: {args.novel}")
            session = engine.create_session(args.novel, args.mode)
        session["mode"] = args.mode

        if args.message:
            responses = self._run_single_chat_turn(engine, session, args)
            for speaker, message in responses:
                print(f"{speaker}: {message}")
            engine.print_turn_cost()
            return

        print("This is an interactive command. Prepare your first user turn before entering the session.")
        if args.mode == "act":
            role = args.character or "<character>"
            print(f"Mode: act | Controlled role: {role}")
            print("Starter input example: 我先表态，你们再接。")
            if not args.character:
                raise ValueError("--character is required in act mode")
            engine.act_mode(session, args.character)
            return

        print("Mode: observe")
        print("Starter input example: 请让大家围绕这件事各说一句。")
        print("Inline commands: /save /reflect /correct /quit")
        engine.observe_mode(session)

    @staticmethod
    def _run_single_chat_turn(
        engine: ChatEngine,
        session: dict,
        args: argparse.Namespace,
    ) -> list[tuple[str, str]]:
        if args.mode == "act":
            if not args.character:
                raise ValueError("--character is required in act mode")
            return engine.act_once(session, args.character, args.message)
        return engine.observe_once(session, args.message)

    def _handle_view(self, args: argparse.Namespace) -> None:
        characters_root = self.config.get_path("characters")
        novel_id = novel_id_from_input(args.novel) if args.novel else None
        matches = find_character_file(characters_root, args.character, novel_id=novel_id)

        if not matches:
            scope = f" under novel '{novel_id}'" if novel_id else ""
            print(f"Profile not found for {args.character}{scope}.")
            return
        if len(matches) > 1:
            print("Multiple profiles matched. Please pass --novel to disambiguate:")
            for item in matches:
                print(f"  - {item}")
            return

        with matches[0].open("r", encoding="utf-8") as handle:
            data = json.load(handle)

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

        filename = f"correction_{args.session}_{correction['timestamp']}.json"
        filepath = corrections_dir / filename
        with filepath.open("w", encoding="utf-8") as handle:
            json.dump(correction, handle, ensure_ascii=False, indent=2)

        print(f"Saved correction: {filepath}")

    def _handle_extract(self, args: argparse.Namespace) -> None:
        print("=== Relationship Extraction ===")
        if args.force:
            print("Confirmation: skipped via --force")
        else:
            print("This command is confirmation-gated. Use --force only after confirming with the user.")
        extractor = RelationshipExtractor(self.config)

        if not args.force:
            cost_estimate = extractor.estimate_cost(args.novel)
            print(f"Estimated cost: ${cost_estimate:.2f} USD")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm != "y":
                print("Operation cancelled.")
                return

        output_path = args.output
        result = extractor.extract(args.novel, output_path)

        print(f"\nDone. Extracted {len(result)} relationships:")
        for rel_key in list(result.keys())[:5]:
            print(f"  - {rel_key}")


def main() -> None:
    ZaomengCLI().run()


if __name__ == "__main__":
    main()
