import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import psutil
import requests

import main


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        for name, value in [('requests', requests), ('psutil', psutil), ('paused', False)]:
            patcher = patch.object(main, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_runtime_dependencies_import_without_starting_bot(self):
        self.assertEqual(len(main.run_imports()), 8)

    def test_paused_bot_waits_without_polling_client(self):
        main.paused = True
        with patch.object(main, 'run') as run, patch.object(
            main.time, 'sleep', side_effect=[None, KeyboardInterrupt]
        ) as sleep:
            main.run_bot()
        run.assert_not_called()
        self.assertEqual(sleep.call_args_list, [call(0.1), call(0.1)])

    def test_transient_client_errors_are_retried(self):
        for error, retry_delay in [(FileNotFoundError(), 10), (ConnectionError(), 1)]:
            with self.subTest(error=type(error).__name__), patch.object(
                main, 'run', side_effect=[error, KeyboardInterrupt]
            ) as run:
                main.run_bot()
                self.assertEqual(run.call_args_list, [call(0), call(retry_delay)])

    def test_missing_process_path_is_skipped(self):
        processes = [
            SimpleNamespace(info={'name': 'LeagueClientUx.exe', 'exe': None}),
            SimpleNamespace(info={'name': 'LeagueClientUx.exe', 'exe': r'C:\League\LeagueClientUx.exe'}),
        ]
        with patch.object(psutil, 'process_iter', return_value=processes), patch.object(
            main.os.path, 'exists', return_value=True
        ):
            self.assertEqual(main.find_lockfile(), r'C:\League\lockfile')

    def test_no_readable_process_path_returns_no_lockfile(self):
        process = SimpleNamespace(info={'name': 'LeagueClientUx.exe', 'exe': None})
        with patch.object(psutil, 'process_iter', return_value=[process]):
            self.assertIsNone(main.find_lockfile())

    def test_valid_lockfile(self):
        with tempfile.TemporaryDirectory() as directory:
            lockfile = Path(directory) / 'lockfile'
            lockfile.write_text('LeagueClient:123:2999:secret:https\n')
            self.assertEqual(main.read_lockfile(lockfile), ('2999', 'secret'))

    def test_incomplete_or_invalid_lockfile_is_recoverable(self):
        invalid_values = [
            '', 'LeagueClient:123', 'LeagueClient:123:abc:secret:https',
            'LeagueClient:123:0:secret:https', 'LeagueClient:123:65536:secret:https',
            'LeagueClient:123:2999::https', 'LeagueClient:123:１２３:secret:https',
            'LeagueClient:123:' + '9' * 5000 + ':secret:https',
        ]
        with tempfile.TemporaryDirectory() as directory:
            lockfile = Path(directory) / 'lockfile'
            for content in invalid_values:
                with self.subTest(content=content[:60]):
                    lockfile.write_text(content, encoding='utf-8')
                    with self.assertRaises(ConnectionError):
                        main.read_lockfile(lockfile)

    def test_unreadable_lockfile_is_recoverable(self):
        with patch('builtins.open', side_effect=PermissionError):
            with self.assertRaises(ConnectionError):
                main.read_lockfile('lockfile')

    def test_accept_success_has_timeout_and_minimizes(self):
        with patch.object(requests, 'post', return_value=Mock(status_code=204, text='')) as post, patch.object(
            main, 'minimize'
        ) as minimize, patch.object(main.time, 'sleep'), self.assertLogs(main.log, level='INFO') as logs:
            self.assertTrue(main.accept_match('2999', 'secret', None))
        self.assertEqual(post.call_args.kwargs['timeout'], 2)
        minimize.assert_called_once_with('League of Legends')
        self.assertTrue(any('Accepted!' in message for message in logs.output))

    def test_rejected_accept_never_reports_success_or_minimizes(self):
        for status in [400, 401, 500]:
            with self.subTest(status=status), patch.object(
                requests, 'post', return_value=Mock(status_code=status, text='failure')
            ), patch.object(main, 'minimize') as minimize, self.assertLogs(main.log) as logs:
                self.assertFalse(main.accept_match('2999', 'secret', None))
                minimize.assert_not_called()
                self.assertFalse(any('Accepted!' in message for message in logs.output))

    def test_accept_timeout_returns_failure(self):
        with patch.object(requests, 'post', side_effect=requests.Timeout), patch.object(
            main, 'minimize'
        ) as minimize:
            self.assertFalse(main.accept_match('2999', 'secret', None))
        minimize.assert_not_called()

    def test_simulated_ready_check_to_champion_select(self):
        with patch.object(main, 'find_lockfile', return_value='lockfile'), patch.object(
            main, 'read_lockfile', return_value=('2999', 'secret')
        ), patch.object(main, 'handle_window', return_value=None), patch.object(
            main, 'get_game_phase', side_effect=['ReadyCheck', 'ChampSelect', KeyboardInterrupt]
        ), patch.object(requests, 'post', return_value=Mock(status_code=204, text='')) as post, patch.object(
            main, 'minimize'
        ) as minimize, patch.object(main.time, 'sleep'):
            with self.assertRaises(KeyboardInterrupt):
                main.run()
        post.assert_called_once()
        self.assertEqual(minimize.call_count, 3)


if __name__ == '__main__':
    unittest.main()
