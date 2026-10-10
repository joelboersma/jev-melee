"""Frame-driven local match lifecycle, independent of the future Jev policy."""

import logging
import time
from dataclasses import dataclass
from typing import Callable

import melee

LOG = logging.getLogger(__name__)
ACTIVE_MENUS = {melee.Menu.IN_GAME, melee.Menu.SUDDEN_DEATH}
END_MENUS = {
    melee.Menu.POSTGAME_SCORES,
    melee.Menu.CHARACTER_SELECT,
    melee.Menu.STAGE_SELECT,
    melee.Menu.MAIN_MENU,
    melee.Menu.PRESS_START,
}


@dataclass(frozen=True)
class MatchConfig:
    bot_port: int = 1
    cpu_port: int = 2
    character: melee.Character = melee.Character.FOX
    opponent: melee.Character = melee.Character.MARTH
    stage: melee.Stage = melee.Stage.FINAL_DESTINATION
    cpu_level: int = 9
    matches: int | None = None
    state_timeout: float = 30.0
    menu_timeout: float = 120.0

    def __post_init__(self):
        if self.bot_port not in range(1, 5) or self.cpu_port not in range(1, 5):
            raise ValueError("Controller ports must be between 1 and 4.")
        if self.bot_port == self.cpu_port:
            raise ValueError("Bot and CPU must use different controller ports.")
        if self.cpu_level not in range(1, 10):
            raise ValueError("CPU level must be between 1 and 9.")
        if self.opponent == melee.Character.SHEIK:
            raise ValueError("Libmelee cannot force a CPU to select Sheik; use Zelda instead.")
        if self.matches is not None and self.matches < 1:
            raise ValueError("Match count must be positive.")
        if not (0 < self.state_timeout < float('inf')) or not (
            0 < self.menu_timeout < float('inf')
        ):
            raise ValueError("Timeouts must be finite and positive.")


def idle_policy(state: melee.GameState, controller: melee.Controller) -> None:
    """Replace this per-frame callback with the future System One policy."""
    controller.release_all()


class MatchLoop:
    def __init__(
        self,
        bot: melee.Controller,
        cpu: melee.Controller,
        config: MatchConfig,
        policy: Callable[[melee.GameState, melee.Controller], None] = idle_policy,
    ):
        self.bot = bot
        self.cpu = cpu
        self.config = config
        self.policy = policy
        self.bot_menu = melee.MenuHelper()
        self.cpu_menu = melee.MenuHelper()
        self.in_match = False
        self.started = 0
        self.completed = 0
        self.previous_menu = None

    def handle_frame(self, state: melee.GameState) -> bool:
        """Apply inputs for one observation; return False at the match limit."""
        menu = state.menu_state
        self.cpu.release_all()
        if menu in ACTIVE_MENUS:
            if not self.in_match:
                self.in_match = True
                self.started += 1
                LOG.info("Match %d started", self.started)
            # Clear menu inputs before handing control to the gameplay policy.
            self.bot.release_all()
            self.policy(state, self.bot)
        else:
            if self.in_match and menu in END_MENUS:
                self.in_match = False
                self.completed += 1
                LOG.info("Match %d finished", self.completed)
                self.bot.release_all()
                if self.config.matches is not None and self.completed >= self.config.matches:
                    return False

            if menu == melee.Menu.STAGE_SELECT and menu != self.previous_menu:
                # libmelee otherwise relies on observing precisely menu frame 0.
                # Keep frozen_stadium_selected: that toggle persists across games.
                self.bot_menu.stage_selected = False
                self.bot_menu.frames_on_stage = 0

            if menu == melee.Menu.CHARACTER_SELECT:
                self.cpu_menu.menu_helper_simple(
                    state, self.cpu, self.config.opponent, self.config.stage,
                    cpu_level=self.config.cpu_level, autostart=False,
                )
                opponent = state.players.get(self.config.cpu_port)
                ready = bool(
                    opponent is not None
                    and opponent.character == self.config.opponent
                    and opponent.coin_down
                    and opponent.controller_status == melee.ControllerStatus.CONTROLLER_CPU
                    and opponent.cpu_level == self.config.cpu_level
                    and not opponent.is_holding_cpu_slider
                )
                self.bot_menu.menu_helper_simple(
                    state, self.bot, self.config.character, self.config.stage,
                    autostart=ready,
                )
            elif menu == melee.Menu.STAGE_SELECT:
                if self.config.bot_port in state.players:
                    self.bot_menu.menu_helper_simple(
                        state, self.bot, self.config.character, self.config.stage,
                        autostart=True,
                    )
                else:
                    self.bot.release_all()
            elif menu == melee.Menu.POSTGAME_SCORES:
                # Both ports acknowledge results, then character selection repeats.
                self.bot_menu.skip_postgame(self.bot)
                self.cpu_menu.skip_postgame(self.cpu)
            elif menu in {melee.Menu.MAIN_MENU, melee.Menu.PRESS_START}:
                self.bot_menu.choose_versus_mode(state, self.bot)
            elif menu == melee.Menu.SLIPPI_ONLINE_CSS:
                raise RuntimeError("Expected local VS mode, but reached the online menu.")
            else:
                self.bot.release_all()

        if menu != self.previous_menu:
            LOG.debug("Menu: %s", menu.name)
        self.previous_menu = menu
        return True

    def run(self, console: melee.Console) -> int:
        last_state = time.monotonic()
        menus_since = last_state
        while True:
            state = console.step()  # libmelee flushes the previous frame's inputs.
            now = time.monotonic()
            if state is None:
                if now - last_state >= self.config.state_timeout:
                    raise RuntimeError("No Dolphin game state received before the timeout.")
                continue
            last_state = now
            if not self.handle_frame(state):
                return self.completed
            if state.menu_state in ACTIVE_MENUS:
                menus_since = now
            elif now - menus_since >= self.config.menu_timeout:
                raise RuntimeError(
                    f"Unable to start the next match within {self.config.menu_timeout:g}s "
                    f"(last menu: {state.menu_state.name})."
                )


def run_session(dolphin: str, iso: str, config: MatchConfig) -> int:
    """Own one emulator process and always tear it down, including on Ctrl+C."""
    console = melee.Console(
        path=dolphin,
        tmp_home_directory=True,
        copy_home_directory=False,
        fullscreen=False,
        blocking_input=True,
        polling_mode=True,
        polling_timeout=0.1,
        infinite_time=False,
        instant_match_restart=False,
        save_replays=False,
    )
    controllers = []
    try:
        # Register controller configuration before booting Dolphin.
        for port in (config.bot_port, config.cpu_port):
            controllers.append(melee.Controller(console, port, melee.ControllerType.STANDARD))
        LOG.info("Starting Dolphin for local VS matches")
        console.run(iso_path=iso)
        if not console.connect():
            raise RuntimeError("Could not connect to Slippi Dolphin. Check the build and ISO.")
        for controller in controllers:
            if not controller.connect():
                raise RuntimeError(f"Could not connect controller port {controller.port}.")
        return MatchLoop(*controllers, config).run(console)
    finally:
        # A closed emulator can leave broken controller pipes; still clean up all resources.
        for controller in controllers:
            try:
                controller.disconnect()
            except Exception:
                LOG.exception("Failed to disconnect controller port %d", controller.port)
        console.stop()
