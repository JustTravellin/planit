# p1s-controller

A local-only (no cloud account) controller for the Bambu Lab P1S with AMS.
It does not slice. Slice in Bambu Studio or OrcaSlicer, export the plate as
`.gcode.3mf`, and this app sends it to the printer and monitors the print over
your LAN.

## Status

| Piece | State |
|---|---|
| MQTT status and commands (pause/resume/stop, light, speed, temps, G-code) | Done, tested against recorded messages |
| FTPS upload | Done, **not yet tested on a real printer** |
| `.gcode.3mf` reader and AMS slot suggestion | Done |
| CLI | Done |
| Desktop window (dashboard, temperature graph, AMS, file library, layer preview, send-and-print, terminal, history, filament inventory, notifications) | Done, tested offscreen with recorded data; **not yet run against a real printer** |
| Windows installer (PyInstaller), camera view and timelapse, camera failure detection | Not started |

The protocol layer follows the community-documented local protocol
(OpenBambuAPI). It was written without access to a real printer, so the first run
on yours is the real test. Message shapes, especially `project_file` and the
AMS mapping, may need small fixes.

## Desktop window

```
pip install -e ".[ui]"
p1s-gui
```

Tabs: **Dashboard** (live state, temperature graph, AMS spools, controls), **Library**
(your `.gcode.3mf` files with thumbnails, tags, search, a layer-by-layer G-code preview,
and a send dialog that maps filaments to AMS slots and shows pre-flight warnings),
**Terminal** (G-code console), **History** (every print with duration, filament and
success rate), **Filament** (spool inventory, drawn down automatically when a print started
from this app finishes) and **Settings**.

The window connects read-only. Tick **Allow control** in the toolbar before pausing,
stopping, changing temperatures or sending a print.

## One-time printer setup

1. On the printer: Settings, WLAN, turn on **LAN Only Mode** (and Developer Mode if
   your firmware offers it). Note the printer's IP address, the **LAN access
   code**, and the serial number (Settings, Device).
2. Keep your PC and printer on the same network.

## Install and use

```
cd p1s-controller
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"

p1s setup --ip 192.168.1.50 --serial 01P00A000000000 --code 12345678
p1s status                      # read-only
p1s watch
p1s inspect benchy.gcode.3mf    # filaments, time, weight
p1s send benchy.gcode.3mf       # upload only
p1s print benchy.gcode.3mf      # upload, map to AMS, ask to confirm, start
p1s pause | resume | stop
p1s light on|off
p1s speed silent|standard|sport|ludicrous
```

Commands that change printer state ask for confirmation (`--yes` skips it), and
connections are read-only unless the command needs control.

The access code is stored in your OS keyring when one is available, otherwise in
a user-only config file. It is never written to the repo.

## Tests

```
pytest
```
