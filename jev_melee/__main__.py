"""Run with: python -m jev_melee --dolphin PATH --iso PATH."""

import argparse
import json
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


def load_paths(path: Path) -> dict[str, Path]:
    """Load saved paths, interpreting relative paths beside the config file."""
    with path.open(encoding="utf-8-sig") as config_file:
        data = json.load(config_file)
    if not isinstance(data, dict):
        raise ValueError("Config must be a JSON object containing dolphin and/or iso paths.")
    paths = {}
    for key in ("dolphin", "iso"):
        if key not in data:
            continue
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Config '{key}' must be a nonempty path string.")
        saved_path = Path(value).expanduser()
        paths[key] = saved_path if saved_path.is_absolute() else path.parent / saved_path
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeated local Melee matches against a CPU.")
    parser.add_argument("--config", type=Path,
                        help="Path config file (default: jev-melee.local.json in the current directory)")
    parser.add_argument("--dolphin", type=Path, help="Slippi Dolphin folder or executable; overrides config")
    parser.add_argument("--iso", type=Path, help="Melee NTSC 1.02 game image; overrides config")
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
    config_path = args.config if args.config is not None else Path("jev-melee.local.json")
    saved_paths = {}
    if args.config is not None or config_path.exists():
        try:
            saved_paths = load_paths(config_path)
        except (OSError, ValueError) as error:
            parser.error(f"Could not load {config_path}: {error}")
    args.dolphin = args.dolphin if args.dolphin is not None else saved_paths.get("dolphin")
    args.iso = args.iso if args.iso is not None else saved_paths.get("iso")
    for key in ("dolphin", "iso"):
        if getattr(args, key) is None:
            parser.error(f"Provide --{key} or save '{key}' in {config_path}.")
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
