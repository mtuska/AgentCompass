#!/usr/bin/env python3
"""Install a built AgentCompass wheel into a private Linux desktop environment."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def desktop_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--autostart', action='store_true', help='Start the tray at graphical login')
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('Linux only')
    wheel = args.wheel.resolve(strict=True)
    uv = shutil.which('uv')
    if not uv:
        parser.error('Install uv first: https://docs.astral.sh/uv/getting-started/installation/')
    # uv-managed Python includes Tk on distributions whose system Python omits it.
    home = Path.home()
    environment = home / '.local/share/agentcompass-desktop'
    if not (environment / 'bin/python').exists():
        subprocess.run([uv, 'venv', '--python', '3.13', '--managed-python', str(environment)], check=True)
    python = environment / 'bin/python'
    subprocess.run([uv, 'pip', 'install', '--python', str(python), '--reinstall-package', 'agentcompass', f'{wheel}[tray]'], check=True)
    subprocess.run([str(python), '-I', '-c', 'import tkinter; from PySide6.QtWidgets import QSystemTrayIcon'], check=True)
    bindir = home / '.local/bin'
    bindir.mkdir(parents=True, exist_ok=True)
    launcher = bindir / 'agentcompass-tray'
    target = environment / 'bin/agentcompass-tray'
    if launcher.exists() or launcher.is_symlink():
        if not launcher.is_symlink() or launcher.readlink() != target:
            parser.error(f'{launcher} already exists and belongs to another installation')
    else:
        launcher.symlink_to(target)
    icon = home / '.local/share/icons/hicolor/128x128/apps/agentcompass.png'
    icon.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(python), '-I', '-c',
        'import sys; from agentcompass import locations; sys.path.insert(0,str(locations.package_dir()/"data/tray")); import ui_theme; ui_theme.compass_image(128).save(sys.argv[1])', str(icon)], check=True)
    entry = ('[Desktop Entry]\nType=Application\nName=AgentCompass\n'
             'Comment=Agent routing, model settings and subscription quotas\n'
             f'Exec={desktop_quote(launcher)} --show\nIcon=agentcompass\n'
             'Terminal=false\nCategories=Development;Utility;\nStartupWMClass=AgentCompass\n')
    applications = home / '.local/share/applications'
    applications.mkdir(parents=True, exist_ok=True)
    (applications / 'agentcompass.desktop').write_text(entry)
    if args.autostart:
        autostart = home / '.config/autostart'
        autostart.mkdir(parents=True, exist_ok=True)
        (autostart / 'agentcompass.desktop').write_text(entry.replace(' --show\n', '\n'))
    print(f'Installed {launcher}\nOpen AgentCompass from your application menu, or run: agentcompass-tray --show')


if __name__ == '__main__':
    main()
