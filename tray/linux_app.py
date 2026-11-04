"""Linux StatusNotifier tray; reuses AgentCompass's Tk dashboard and collectors.

Qt provides a native menu on KDE/Wayland (the XEmbed-only pystray backend does
not). No optional Windows services are started. All children belong to this tray.
"""
from __future__ import annotations

import argparse
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

import component_launch
import ui_theme

STATE = Path.home() / '.agent-compass'


def stop_child(proc):
    """Terminate only a process group created by this tray, then reap it."""
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)
    except ProcessLookupError:
        proc.wait(timeout=3)


class LinuxTray:
    def __init__(self, app, server, collect=True):
        self.app, self.server = app, server
        self.children = {}
        self.started = {}
        self.collect = collect
        self.stopping = False
        image = io.BytesIO()
        ui_theme.compass_image(64).save(image, format='PNG')
        pixmap = QPixmap()
        pixmap.loadFromData(image.getvalue())
        self.icon = QSystemTrayIcon(QIcon(pixmap), app)
        app.setWindowIcon(self.icon.icon())
        self.menu = QMenu()
        self.menu.addAction('Open AgentCompass', self.open_panel)
        self.menu.addAction('Refresh subscription quotas', self.refresh_usage)
        self.status = self.menu.addAction('Reading quota cache…')
        self.status.setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction('Open logs', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(STATE))))
        self.menu.addAction('Quit AgentCompass', app.quit)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.activate)
        self.server.newConnection.connect(self.connection)
        app.aboutToQuit.connect(self.shutdown)
        self.icon.show()
        self.timer = QTimer(app)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.tick()

    def activate(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_panel()

    def connection(self):
        socket = self.server.nextPendingConnection()
        if socket:
            self.open_panel()
            socket.disconnectFromServer()
            socket.deleteLater()

    def launch(self, name, script, *args):
        proc = self.children.get(name)
        if proc is not None and proc.poll() is None:
            return proc
        with (STATE / f'linux-{name}.log').open('ab') as log:
            proc = subprocess.Popen(component_launch.command(script, *args),
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                    start_new_session=True)
        self.children[name] = proc
        self.started[name] = time.monotonic()
        return proc

    def open_panel(self):
        proc = self.children.get('dashboard')
        if proc is not None and proc.poll() is None:
            # A request file also works while Tk is still starting; an early
            # SIGUSR1 would terminate Python before its handler was installed.
            (STATE / 'linux-dashboard-raise').touch()
            return
        self.launch('dashboard', 'router_window')

    def refresh_usage(self):
        self.launch('usage', 'usage_collect')
        self.status.setText('Refreshing subscription quotas…')

    def tick(self):
        if self.stopping:
            return
        for name in ('usage', 'capacity'):
            proc = self.children.get(name)
            if proc is not None and proc.poll() is None and time.monotonic() - self.started[name] > 240:
                stop_child(proc)
                self.icon.showMessage('AgentCompass', f'{name} refresh timed out; see logs.')
            if self.collect and time.monotonic() - self.started.get(name, -300) >= 300:
                self.launch(name, 'usage_collect' if name == 'usage' else 'capacity_stats',
                            *(() if name == 'usage' else ('--once', '--quiet')))
        try:
            data = json.loads((STATE / 'usage-cache.json').read_text())
            summaries = []
            for name, row in data.get('providers', {}).items():
                values = [w['used_pct'] for w in row.get('windows', [])
                          if isinstance(w.get('used_pct'), (int, float))]
                if values:
                    summaries.append(f'{name}: {max(values):.0f}% used')
            self.icon.setToolTip('AgentCompass\n' + '\n'.join(summaries))
            busy = any(p is not None and p.poll() is None for n, p in self.children.items() if n != 'dashboard')
            self.status.setText('Refreshing…' if busy else 'Quota cache loaded' if summaries else 'No quota readings yet')
        except (OSError, ValueError, TypeError):
            self.status.setText('No quota cache — refresh to collect')

    def shutdown(self):
        self.stopping = True
        self.timer.stop()
        for proc in self.children.values():
            stop_child(proc)
        self.icon.hide()
        self.server.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='AgentCompass Linux tray and dashboard')
    parser.add_argument('--show', action='store_true', help='Open the dashboard immediately')
    parser.add_argument('--no-collect', action='store_true', help='Do not start periodic collectors')
    parser.add_argument('--quit-after', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    STATE.mkdir(parents=True, exist_ok=True)
    app = QApplication([sys.argv[0]])
    app.setApplicationName('AgentCompass')
    app.setDesktopFileName('agentcompass')
    app.setQuitOnLastWindowClosed(False)
    address = str(STATE / 'linux-tray.socket')
    lock = (STATE / 'linux-tray.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        peer = QLocalSocket()
        peer.connectToServer(address)
        if not peer.waitForConnected(2000):
            print('AgentCompass is starting; try again shortly.', file=sys.stderr)
            return 1
        peer.disconnectFromServer()
        return 0
    lock.seek(0)
    lock.truncate()
    lock.write(str(os.getpid()))
    lock.flush()
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, 'AgentCompass', 'This desktop does not expose a system tray. Enable a StatusNotifier/AppIndicator tray and try again.')
        return 1
    QLocalServer.removeServer(address)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(address):
        raise RuntimeError(server.errorString())
    controller = LinuxTray(app, server, collect=not args.no_collect)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    if args.show:
        controller.open_panel()
    if args.quit_after is not None:
        QTimer.singleShot(int(args.quit_after * 1000), app.quit)
    try:
        return app.exec()
    finally:
        controller.shutdown()
        lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
