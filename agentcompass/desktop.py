"""Installed Linux desktop entry point; tray sources remain real files in wheels."""
from pathlib import Path
import runpy
import sys
from agentcompass import locations


def main():
    if not sys.platform.startswith('linux'):
        raise SystemExit('Use the Windows tray installer on Windows.')
    root = locations.checkout_root()
    tray = root / 'tray' if root else locations.package_dir() / 'data' / 'tray'
    if not (tray / 'linux_app.py').is_file():
        raise SystemExit('Tray files are missing; reinstall agentcompass[tray].')
    sys.path.insert(0, str(tray))
    runpy.run_path(str(tray / 'linux_app.py'), run_name='__main__')
