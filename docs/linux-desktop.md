# Linux tray and dashboard

The Linux desktop uses Qt's StatusNotifier system tray integration and the existing
Tk dashboard. KDE Plasma on Wayland is supported (Tk uses XWayland). Other desktops
need a StatusNotifier/AppIndicator tray. Windows still uses the original pystray app.

## Build and install

From this fork's `codex/linux-tray` branch, with [uv](https://docs.astral.sh/uv/) installed:

```bash
uv build --wheel
python3 packaging/install_linux.py dist/agentcompass-0.3.8-py3-none-any.whl
agentcompass-tray --show
```

The installer uses a uv-managed Python with Tk, installs the wheel and Linux tray
extras into `~/.local/share/agentcompass-desktop`, and adds a launcher under
`~/.local/bin` plus an **AgentCompass** application-menu entry. It does not replace
an existing `agentcompass` router installation or modify its provider credentials.
Install/setup the router first if necessary, as described in the main README.

For automatic startup, add `--autostart` to the installer command, or enable it in
the dashboard's System options. Without it, the tray starts only when opened.
Repeated launches activate the existing dashboard instead of starting a second tray.

## Included

- Native tray menu, dashboard activation, quota refresh, log-folder access and Quit.
- Existing decision console, quota/worker display, model settings, scoring controls,
  language selection and classifier configuration.
- Quota collection and capacity statistics every five minutes while the tray runs.
- Single-instance protection and cleanup of dashboard/collector children on Quit.
- Desktop login startup through an XDG autostart entry.

The optional Windows service bridges (Usage Float, EasyTier and browser gateway
supervisors) are not ported. The Integrations page explains this; the Linux tray
never downloads or starts them. There is no Windows-installer self-update control
on Linux: build and reinstall a newer fork wheel to update the desktop. Existing
CLI update controls remain available, but updates to provider tools are separate
from updating this desktop app.

Logs: `~/.agent-compass/linux-dashboard.log`, `linux-usage.log`, and
`linux-capacity.log`. The tray does not launch model workers by itself.

## Development and tests

```bash
uv venv --python 3.13 --managed-python
uv pip install --python .venv/bin/python '.[tray]' pytest
.venv/bin/python tray/linux_app.py --show
.venv/bin/python -m pytest tray/test_linux_desktop.py tray/test_component_launch.py \
  tray/test_router_window.py tray/test_router_data_models.py tray/test_radar_chart.py \
  tray/test_owned_process.py agentcompass/test_packaging.py
```

GUI tests need a graphical session. `--no-collect --quit-after 10` on
`tray/linux_app.py` permits a bounded tray smoke test without quota collection.

## Remove the desktop

Quit it from the tray first. Remove these desktop-only paths:

- `~/.local/bin/agentcompass-tray`
- `~/.local/share/agentcompass-desktop`
- `~/.local/share/applications/agentcompass.desktop`
- `~/.local/share/icons/hicolor/128x128/apps/agentcompass.png`
- `~/.config/autostart/agentcompass.desktop` (if enabled)

Keep `~/.agent-compass`: it contains the shared router settings and history.
