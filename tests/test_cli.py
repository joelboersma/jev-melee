import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev_melee.__main__ import load_paths, main


class ConfigTests(unittest.TestCase):
    def test_relative_paths_and_windows_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'dolphin': 'dolphin', 'iso': 'Melee.iso'}), encoding='utf-8-sig')
            self.assertEqual(load_paths(path), {
                'dolphin': path.parent / 'dolphin', 'iso': path.parent / 'Melee.iso',
            })

    def test_invalid_config_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            for value in ([], {'iso': ''}, {'dolphin': 42}, {'iso': None}):
                with self.subTest(value=value):
                    path.write_text(json.dumps(value), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        load_paths(path)

    def test_default_config_and_cli_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dolphin = root / 'dolphin'
            dolphin.mkdir()
            iso = root / 'Melee.iso'
            iso.touch()
            replacement = root / 'other.iso'
            replacement.touch()
            config_path = root / 'jev-melee.local.json'
            config_path.write_text(json.dumps({'dolphin': str(dolphin), 'iso': str(iso)}))
            # Substitute only the default config path without changing process cwd.
            real_load = load_paths
            with patch('jev_melee.__main__.load_paths', side_effect=lambda p: real_load(config_path)), \
                    patch('jev_melee.__main__.Path.exists', return_value=True), \
                    patch('jev_melee.__main__.run_session') as run:
                with patch('sys.argv', ['jev_melee']):
                    self.assertEqual(main(), 0)
                    self.assertEqual(run.call_args.args[:2], (str(dolphin), str(iso)))
                with patch('sys.argv', ['jev_melee', '--iso', str(replacement)]):
                    self.assertEqual(main(), 0)
                    self.assertEqual(run.call_args.args[:2], (str(dolphin), str(replacement)))

    def test_explicit_config_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dolphin').mkdir()
            (root / 'Melee.iso').touch()
            path = root / 'config.json'
            path.write_text(json.dumps({'dolphin': 'dolphin', 'iso': 'Melee.iso'}))
            with patch('sys.argv', ['jev_melee', '--config', str(path)]), \
                    patch('jev_melee.__main__.run_session') as run:
                self.assertEqual(main(), 0)
                self.assertEqual(run.call_args.args[:2], (str(root / 'dolphin'), str(root / 'Melee.iso')))

    def test_missing_and_malformed_config_report_cli_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            for contents in (None, '{broken json'):
                with self.subTest(contents=contents):
                    if contents is not None:
                        path.write_text(contents)
                    with patch('sys.argv', ['jev_melee', '--config', str(path)]), \
                            contextlib.redirect_stderr(io.StringIO()) as errors, \
                            self.assertRaises(SystemExit) as exit_result:
                        main()
                    self.assertEqual(exit_result.exception.code, 2)
                    self.assertIn('Could not load', errors.getvalue())


if __name__ == '__main__':
    unittest.main()
