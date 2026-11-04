"""Installed Linux desktop entry point; tray sources remain real files in wheels."""
from pathlib import Path
import os
import runpy
import sys
from agentcompass import locations


def main():
    if not sys.platform.startswith('linux'):
        raise SystemExit('Use the Windows tray installer on Windows.')
    # Desktop sessions do not run shell profiles (notably Linuxbrew's shellenv).
    # Keep the user's PATH precedence, then include conventional CLI install roots.
    entries = os.environ.get('PATH', '').split(os.pathsep)
    for directory in (Path.home() / '.local/bin', Path.home() / '.grok/bin',
                      Path.home() / '.npm-global/bin', Path.home() / '.linuxbrew/bin',
                      Path('/home/linuxbrew/.linuxbrew/bin')):
        if directory.is_dir() and str(directory) not in entries:
            entries.append(str(directory))
    os.environ['PATH'] = os.pathsep.join(entries)
    root = locations.checkout_root()
    tray = root / 'tray' if root else locations.package_dir() / 'data' / 'tray'
    if not (tray / 'linux_app.py').is_file():
        raise SystemExit('Tray files are missing; reinstall agentcompass[tray].')
    sys.path.insert(0, str(tray))
    runpy.run_path(str(tray / 'linux_app.py'), run_name='__main__')
