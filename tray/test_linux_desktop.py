"""Linux regression coverage: real child lifecycle and portable launch commands."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import component_launch


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux desktop')
class LinuxDesktopTests(unittest.TestCase):
    def test_component_uses_current_interpreter(self):
        command = component_launch.command('router_window', '--page', 'quota')
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]).name, 'router_window.py')
        self.assertEqual(command[2:], ['--page', 'quota'])

    def test_stop_owned_process(self):
        from linux_app import stop_child
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            stop_child(proc)
            self.assertIsNotNone(proc.poll())
            stop_child(proc)  # repeated shutdown is safe
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_open_path_uses_argument_array(self):
        import desktop_platform
        with mock.patch.object(desktop_platform.subprocess, 'run') as run:
            desktop_platform.open_path('/tmp/a file;echo no.txt')
        run.assert_called_once_with(['xdg-open', '/tmp/a file;echo no.txt'], check=True, timeout=15)

    def test_tray_shutdown_cleans_children_and_socket(self):
        from linux_app import LinuxTray
        tray = LinuxTray.__new__(LinuxTray)
        tray.timer, tray.icon, tray.server = mock.Mock(), mock.Mock(), mock.Mock()
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        tray.children = {'usage': proc}
        try:
            tray.shutdown()
            self.assertIsNotNone(proc.poll())
            tray.timer.stop.assert_called_once()
            tray.server.close.assert_called_once()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


if __name__ == '__main__':
    unittest.main()
