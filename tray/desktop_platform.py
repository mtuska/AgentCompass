"""Small OS boundary for desktop actions shared by the Tk windows."""
import os
import subprocess


def open_path(path):
    if os.name == 'nt':
        os.startfile(path)
    else:
        subprocess.run(['xdg-open', str(path)], check=True, timeout=15)


def startup_path():
    from pathlib import Path
    return Path.home() / '.config/autostart/agentcompass.desktop'


def startup_enabled():
    return startup_path().is_file()


def write_startup():
    from pathlib import Path
    entry = Path.home() / '.local/share/applications/agentcompass.desktop'
    if not entry.is_file():
        raise RuntimeError('Install the Linux desktop launcher first (packaging/install_linux.py).')
    target = startup_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(entry.read_text().replace(' --show\n', '\n'))


def remove_startup():
    startup_path().unlink(missing_ok=True)


def link_skills():
    result = subprocess.run(['agentcompass', 'setup', '--yes', '--no-usage'], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return ['AgentCompass host skills synchronized']
