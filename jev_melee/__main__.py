"""Run with: python -m jev_melee --dolphin PATH --iso PATH."""

import argparse
import logging
from pathlib import Path

import melee
from melee.slippstream import EnetDisconnected

from .loop import MatchConfig, run_session

CHARACTERS = [
    "MARIO", "FOX", "CPTFALCON", "DK", "KIRBY", "BOWSER", "LINK", "SHEIK",
    "NESS", "PEACH", "POPO", "PIKACHU", "SAMUS", "YOSHI", "JIGGLYPUFF",
    "MEWTWO", "LUIGI", "MARTH", "ZELDA", "YLINK", "DOC", "FALCO", "PICHU",
    "GAMEANDWATCH", "GANONDORF", "ROY",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeated local Melee matches against a CPU.")
    parser.add_argument("--dolphin", required=True, type=Path, help="Slippi Dolphin folder or executable")
    parser.add_argument("--iso", required=True, type=Path, help="Melee NTSC 1.02 game image")
    parser.add_argument("--character", type=str.upper, choices=CHARACTERS, default="FOX")
    parser.add_argument("--opponent", type=str.upper,
                        choices=[name for name in CHARACTERS if name != "SHEIK"], default="MARTH")
    parser.add_argument("--stage", type=str.upper,
                        choices=[stage.name for stage in melee.Stage if stage != melee.Stage.NO_STAGE],
                        default="FINAL_DESTINATION")
    parser.add_argument("--cpu-level", type=int, default=9)
    parser.add_argument("--bot-port", type=int, default=1)
    parser.add_argument("--cpu-port", type=int, default=2)
    parser.add_argument("--matches", type=int, help="Stop after this many finished games; default: forever")
    parser.add_argument("--state-timeout", type=float, default=30.0)
    parser.add_argument("--menu-timeout", type=float, default=120.0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.dolphin.exists():
        parser.error("Dolphin path does not exist.")
    if not args.iso.is_file():
        parser.error("Game image path must point to a file.")
    try:
        config = MatchConfig(
            bot_port=args.bot_port, cpu_port=args.cpu_port,
            character=melee.Character[args.character], opponent=melee.Character[args.opponent],
            stage=melee.Stage[args.stage], cpu_level=args.cpu_level, matches=args.matches,
            state_timeout=args.state_timeout, menu_timeout=args.menu_timeout,
        )
    except ValueError as error:
        parser.error(str(error))
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        run_session(str(args.dolphin.resolve()), str(args.iso.resolve()), config)
    except KeyboardInterrupt:
        logging.info("Stopped by user")
    except EnetDisconnected:
        logging.error("Dolphin disconnected from the game-state stream.")
        return 1
    except (OSError, RuntimeError, ValueError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
