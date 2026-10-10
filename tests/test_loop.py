import unittest
from unittest.mock import Mock, patch

import melee

from jev_melee.loop import MatchConfig, MatchLoop, run_session


def state(menu, frame=1, players=None):
    return melee.GameState(menu_state=menu, frame=frame, players=players or {})


class MatchLoopTests(unittest.TestCase):
    def setUp(self):
        self.bot = Mock(port=1)
        self.cpu = Mock(port=2)
        self.policy = Mock()
        self.loop = MatchLoop(self.bot, self.cpu, MatchConfig(), self.policy)
        self.loop.bot_menu = Mock()
        self.loop.cpu_menu = Mock()

    def test_two_matches_and_repeated_results_count_once(self):
        for menu in (
            melee.Menu.IN_GAME, melee.Menu.IN_GAME, melee.Menu.SUDDEN_DEATH,
            melee.Menu.POSTGAME_SCORES, melee.Menu.POSTGAME_SCORES,
            melee.Menu.CHARACTER_SELECT, melee.Menu.STAGE_SELECT,
            melee.Menu.IN_GAME, melee.Menu.POSTGAME_SCORES,
        ):
            self.assertTrue(self.loop.handle_frame(state(menu)))
        self.assertEqual((self.loop.started, self.loop.completed), (2, 2))
        self.assertEqual(self.policy.call_count, 4)
        self.assertEqual(self.loop.bot_menu.skip_postgame.call_count, 3)
        self.assertEqual(self.loop.cpu_menu.skip_postgame.call_count, 3)

    def test_cpu_must_be_ready_before_autostart(self):
        opponent = melee.PlayerState(character=melee.Character.MARTH)
        observation = state(melee.Menu.CHARACTER_SELECT, players={2: opponent})
        self.loop.handle_frame(observation)
        self.assertFalse(self.loop.bot_menu.menu_helper_simple.call_args.kwargs['autostart'])
        opponent.coin_down = True
        opponent.controller_status = melee.ControllerStatus.CONTROLLER_CPU
        opponent.cpu_level = 9
        self.loop.handle_frame(observation)
        self.assertTrue(self.loop.bot_menu.menu_helper_simple.call_args.kwargs['autostart'])
        self.assertFalse(self.loop.cpu_menu.menu_helper_simple.call_args.kwargs['autostart'])

    def test_stage_selection_resets_even_when_frame_zero_was_missed(self):
        self.loop.bot_menu = melee.MenuHelper()
        self.loop.bot_menu.stage_selected = True
        self.loop.bot_menu.frames_on_stage = 50
        self.loop.bot_menu.frozen_stadium_selected = True
        with patch.object(self.loop.bot_menu, 'menu_helper_simple') as helper:
            self.loop.handle_frame(state(melee.Menu.STAGE_SELECT, 55, {1: melee.PlayerState()}))
            self.assertFalse(self.loop.bot_menu.stage_selected)
            self.assertEqual(self.loop.bot_menu.frames_on_stage, 0)
            self.assertTrue(self.loop.bot_menu.frozen_stadium_selected)
            self.assertTrue(helper.call_args.kwargs['autostart'])

    def test_limit_stops_before_starting_another_match(self):
        self.loop.config = MatchConfig(matches=1)
        self.loop.handle_frame(state(melee.Menu.IN_GAME))
        self.assertFalse(self.loop.handle_frame(state(melee.Menu.POSTGAME_SCORES)))
        self.loop.bot_menu.skip_postgame.assert_not_called()

    def test_initial_results_are_not_a_completed_match(self):
        self.loop.handle_frame(state(melee.Menu.POSTGAME_SCORES))
        self.assertEqual(self.loop.completed, 0)

    def test_unknown_observation_does_not_end_match(self):
        self.loop.handle_frame(state(melee.Menu.IN_GAME))
        self.loop.handle_frame(state(melee.Menu.UNKNOWN_MENU))
        self.assertEqual(self.loop.completed, 0)
        self.loop.handle_frame(state(melee.Menu.CHARACTER_SELECT))
        self.assertEqual(self.loop.completed, 1)

    def test_title_screen_navigation(self):
        observation = state(melee.Menu.PRESS_START)
        self.loop.handle_frame(observation)
        self.loop.bot_menu.choose_versus_mode.assert_called_once_with(observation, self.bot)

    def test_policy_receives_neutral_controller(self):
        self.bot.release_all.side_effect = lambda: setattr(self.bot, 'neutral', True)
        self.policy.side_effect = lambda s, c: self.assertTrue(c.neutral)
        self.loop.handle_frame(state(melee.Menu.IN_GAME))
        self.policy.assert_called_once()

    def test_missing_frames_timeout(self):
        console = Mock()
        console.step.return_value = None
        with patch('jev_melee.loop.time.monotonic', side_effect=[0, 1, 31]):
            with self.assertRaisesRegex(RuntimeError, 'No Dolphin game state'):
                self.loop.run(console)

    def test_menu_timeout_even_with_live_frames(self):
        console = Mock()
        console.step.return_value = state(melee.Menu.UNKNOWN_MENU)
        with patch('jev_melee.loop.time.monotonic', side_effect=[0, 121]):
            with self.assertRaisesRegex(RuntimeError, 'Unable to start'):
                self.loop.run(console)

    def test_gameplay_is_not_subject_to_menu_timeout(self):
        self.loop.config = MatchConfig(matches=1)
        console = Mock()
        console.step.side_effect = [state(melee.Menu.IN_GAME), state(melee.Menu.POSTGAME_SCORES)]
        with patch('jev_melee.loop.time.monotonic', side_effect=[0, 1000, 1001]):
            self.assertEqual(self.loop.run(console), 1)

    def test_invalid_config(self):
        for kwargs in ({'cpu_port': 1}, {'bot_port': 0}, {'cpu_level': 10},
                       {'matches': 0}, {'state_timeout': 0}, {'menu_timeout': float('nan')},
                       {'opponent': melee.Character.SHEIK}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MatchConfig(**kwargs)

    def test_real_menu_helper_starts_ready_match(self):
        self.loop.bot_menu = melee.MenuHelper()
        self.loop.cpu_menu = melee.MenuHelper()
        bot_player = melee.PlayerState(character=melee.Character.FOX, coin_down=True)
        cpu_player = melee.PlayerState(
            character=melee.Character.MARTH, coin_down=True, cpu_level=9,
            controller_status=melee.ControllerStatus.CONTROLLER_CPU,
        )
        self.bot.prev.button = {melee.Button.BUTTON_B: False}
        self.cpu.prev.button = {melee.Button.BUTTON_B: False}
        self.loop.handle_frame(state(melee.Menu.CHARACTER_SELECT, 21, {1: bot_player, 2: cpu_player}))
        self.bot.press_button.assert_called_once_with(melee.Button.BUTTON_START)
        self.cpu.press_button.assert_not_called()

    def test_real_menu_helper_reselects_stage_for_next_match(self):
        self.loop.bot_menu = melee.MenuHelper()
        self.bot.prev.button = {melee.Button.BUTTON_START: False}
        self.loop.bot_menu.frozen_stadium_selected = True
        player = melee.PlayerState()
        player.cursor.x, player.cursor.y = 6.7, -9
        observation = state(melee.Menu.STAGE_SELECT, 55, {1: player})
        self.loop.handle_frame(observation)
        self.assertTrue(self.loop.bot_menu.stage_selected)
        self.loop.handle_frame(state(melee.Menu.IN_GAME))
        self.loop.handle_frame(state(melee.Menu.POSTGAME_SCORES))
        self.loop.handle_frame(observation)
        self.assertEqual(self.bot.press_button.call_args_list.count(
            unittest.mock.call(melee.Button.BUTTON_A)), 2)


class SessionTests(unittest.TestCase):
    def test_cleanup_on_startup_failure_and_interrupt(self):
        for failure in ('connection', 'controller', 'interrupt'):
            with self.subTest(failure=failure), patch('jev_melee.loop.melee.Console') as constructor, \
                    patch('jev_melee.loop.melee.Controller') as controller_class, \
                    patch('jev_melee.loop.MatchLoop') as loop_class:
                console = constructor.return_value
                console.connect.return_value = failure != 'connection'
                bot, cpu = Mock(port=1), Mock(port=2)
                bot.connect.return_value = failure != 'controller'
                cpu.connect.return_value = True
                controller_class.side_effect = [bot, cpu]
                loop_class.return_value.run.side_effect = KeyboardInterrupt
                error = KeyboardInterrupt if failure == 'interrupt' else RuntimeError
                with self.assertRaises(error):
                    run_session('dolphin', 'melee.iso', MatchConfig())
                bot.disconnect.assert_called_once()
                cpu.disconnect.assert_called_once()
                console.stop.assert_called_once()
                self.assertTrue(constructor.call_args.kwargs['tmp_home_directory'])


if __name__ == '__main__':
    unittest.main()
