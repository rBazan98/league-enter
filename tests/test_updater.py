import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import psutil
import requests
from packaging.version import Version

import main


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="league update's ")
        self.addCleanup(directory.cleanup)
        self.target = Path(directory.name) / 'league-enter.exe'
        self.target.write_bytes(b'old executable')
        self.temporary_download = Path(str(self.target) + '.new')
        self.args = ['123', str(self.target), 'https://example.invalid/league-enter.exe']
        self.process = self.start_patch(psutil, 'Process').return_value
        self.download = self.start_patch(
            main.urllib.request, 'urlopen', return_value=io.BytesIO(b'new executable')
        )
        self.launch = self.start_patch(main.subprocess, 'Popen')
        self.start_patch(main.time, 'sleep')
        self.start_patch(main.sys, 'executable', str(Path(directory.name) / 'league-updater.exe'))
        self.kill = self.start_patch(main.os, 'kill', side_effect=AssertionError('Must not kill processes'))

    def start_patch(self, target, name, *args, **kwargs):
        patcher = patch.object(target, name, *args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def test_successful_update_waits_without_killing_and_replaces_executable(self):
        self.assertEqual(main.run_updater(self.args), 0)
        self.process.wait.assert_called_once_with(timeout=30)
        self.kill.assert_not_called()
        self.process.kill.assert_not_called()
        self.process.terminate.assert_not_called()
        self.download.assert_called_once_with(self.args[2], timeout=30)
        self.assertEqual(self.target.read_bytes(), b'new executable')
        self.assertFalse(self.temporary_download.exists())
        self.assertEqual(self.launch.call_args_list[0].args, ([str(self.target)],))

    def test_already_exited_process_can_be_updated(self):
        psutil.Process.side_effect = psutil.NoSuchProcess(123)
        self.assertEqual(main.run_updater(self.args), 0)
        self.assertEqual(self.target.read_bytes(), b'new executable')

    def test_wait_timeout_preserves_original_and_does_not_download(self):
        self.process.wait.side_effect = psutil.TimeoutExpired(30, pid=123)
        self.assertEqual(main.run_updater(self.args), 1)
        self.assertEqual(self.target.read_bytes(), b'old executable')
        self.download.assert_not_called()
        self.launch.assert_not_called()

    def test_access_denied_preserves_original(self):
        psutil.Process.side_effect = psutil.AccessDenied(123)
        self.assertEqual(main.run_updater(self.args), 1)
        self.assertEqual(self.target.read_bytes(), b'old executable')
        self.download.assert_not_called()

    def test_invalid_arguments_never_touch_processes_or_download(self):
        for args in [[], ['123'], ['bad', *self.args[1:]], ['0', *self.args[1:]], ['-1', *self.args[1:]]]:
            with self.subTest(args=args):
                self.assertEqual(main.run_updater(args), 1)
        psutil.Process.assert_not_called()
        self.download.assert_not_called()
        self.launch.assert_not_called()

    def test_download_timeout_preserves_original(self):
        self.download.side_effect = TimeoutError('download timed out')
        self.assertEqual(main.run_updater(self.args), 1)
        self.assertEqual(self.target.read_bytes(), b'old executable')
        self.assertFalse(self.temporary_download.exists())
        self.launch.assert_not_called()

    def test_partial_download_is_removed_and_original_is_preserved(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = [b'partial executable', OSError('connection lost')]
        self.download.return_value = response
        self.assertEqual(main.run_updater(self.args), 1)
        self.assertEqual(self.target.read_bytes(), b'old executable')
        self.assertFalse(self.temporary_download.exists())
        self.launch.assert_not_called()

    def test_failed_replacement_preserves_original_and_cleans_download(self):
        with patch.object(main.os, 'replace', side_effect=PermissionError('file locked')):
            self.assertEqual(main.run_updater(self.args), 1)
        self.assertEqual(self.target.read_bytes(), b'old executable')
        self.assertFalse(self.temporary_download.exists())
        self.launch.assert_not_called()

    def test_failed_updated_executable_launch_returns_error(self):
        self.launch.side_effect = OSError('cannot launch')
        self.assertEqual(main.run_updater(self.args), 1)
        self.assertTrue(self.target.exists())
        self.assertEqual(self.launch.call_count, 1)

    def test_cleanup_launch_failure_does_not_hide_successful_update(self):
        self.launch.side_effect = [Mock(), OSError('cannot schedule cleanup')]
        self.assertEqual(main.run_updater(self.args), 0)
        self.assertEqual(self.target.read_bytes(), b'new executable')

    def test_offer_update_launches_helper_without_shell(self):
        with patch('builtins.input', return_value='y'), patch.object(
            main, 'get_real_exe_path', return_value=str(self.target)
        ), patch.object(main.shutil, 'copy2'), self.assertRaises(SystemExit):
            main.offer_update('v2.0.0')
        args = self.launch.call_args.args[0]
        self.assertEqual(args[0], str(self.target.with_name('league-updater.exe')))
        self.assertEqual(args[1], '--update')
        self.assertEqual(args[3], str(self.target))
        self.assertFalse(self.launch.call_args.kwargs.get('shell', False))

    def test_failed_helper_launch_does_not_exit_current_program(self):
        self.launch.side_effect = OSError('cannot launch helper')
        with patch('builtins.input', return_value='y'), patch.object(main.shutil, 'copy2'):
            self.assertIsNone(main.offer_update('v2.0.0'))

    def test_executable_path_does_not_rewrite_mei_directory_names(self):
        executable = str(self.target.parent / '_MEI_saved' / 'league-enter.exe')
        with patch.object(main.sys, 'executable', executable):
            self.assertEqual(main.get_real_exe_path(), executable)


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.keyboard = Mock()
        dependencies = (Version, psutil, requests, self.keyboard, Mock(), Mock(), Mock(), Mock())
        for name, value in zip(
            ['Version', 'psutil', 'requests', 'keyboard', 'gw', 'win32gui', 'win32con', 'urllib3'], dependencies
        ):
            patcher = patch.object(main, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.imports = self.start_patch(main, 'run_imports', return_value=dependencies)
        self.latest = self.start_patch(main, 'get_latest_version', return_value=None)
        self.bot = self.start_patch(main, 'run_bot')
        self.offer = self.start_patch(main, 'offer_update')
        self.start_patch(main.sys, 'frozen', False, create=True)

    def start_patch(self, target, name, *args, **kwargs):
        patcher = patch.object(target, name, *args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def test_update_exit_codes_never_fall_through_into_bot(self):
        for status in [0, 1]:
            with self.subTest(status=status), patch.object(main.sys, 'frozen', True), patch.object(
                main, 'run_updater', return_value=status
            ) as updater:
                self.assertEqual(main.main(['--update', '123', 'target', 'url']), status)
                updater.assert_called_once_with(['123', 'target', 'url'])
        self.imports.assert_not_called()
        self.latest.assert_not_called()
        self.keyboard.add_hotkey.assert_not_called()
        self.bot.assert_not_called()

    def test_update_mode_is_rejected_when_running_source(self):
        with patch.object(main, 'run_updater') as updater:
            self.assertEqual(main.main(['--update', '123', 'target', 'url']), 1)
        updater.assert_not_called()
        self.imports.assert_not_called()
        self.bot.assert_not_called()

    def test_normal_startup_registers_hotkey_and_enters_mocked_bot(self):
        self.assertEqual(main.main([]), 0)
        self.keyboard.add_hotkey.assert_called_once_with('ctrl+p', main.toggle_pause)
        self.bot.assert_called_once_with()

    def test_source_never_offers_executable_update_for_renamed_interpreter(self):
        self.latest.return_value = 'v999.0.0'
        with patch.object(main.sys, 'executable', r'C:\Python\python3.exe'):
            self.assertEqual(main.main([]), 0)
        self.offer.assert_not_called()

    def test_frozen_executable_is_detected_by_flag_not_filename(self):
        self.latest.return_value = 'v999.0.0'
        with patch.object(main.sys, 'frozen', True), patch.object(main.sys, 'executable', r'C:\App\python.exe'):
            self.assertEqual(main.main([]), 0)
        self.offer.assert_called_once_with('v999.0.0')

    def test_startup_import_failure_returns_error_without_running_bot(self):
        self.imports.side_effect = ImportError('missing dependency')
        self.assertEqual(main.main([]), 1)
        self.keyboard.add_hotkey.assert_not_called()
        self.bot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
