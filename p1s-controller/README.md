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
| 3D plate view (model on the plate, fit check, sliced layer view), sidebar UI | Done; verified with real 3MF files (OpenGL). Sliced view only tested with synthetic G-code |
| **Slicing for the P1S** (Library, Slice section): runs the installed Bambu Studio's slicing engine headless with the stock P1S profiles, AMS spool to filament mapping, infill/walls/supports/plate/brim options, and slicing advice | Done; tested against a real Bambu Studio 02.08 install |
| Print queue (never auto-starts), maintenance reminders by print hours, Telegram/Discord/ntfy/webhook notifications | Done; tested with fakes. Real phone push not yet tried |
| Desktop window: dashboard, temperature graph, AMS, file library, layer preview, send-and-print, terminal, history, filament inventory, notifications | Done; tested offscreen with recorded data |
| Manual controls (jog, home, bed level, fans, extrude, AMS load/unload) | Done; tested offscreen against a fake printer connection |
| Health tab and alerts (HMS codes, print errors, low filament, temperature, Wi-Fi, firmware list) | Done; tested with recorded reports |
| Camera live view | Done; tested against a fake TLS server. **Unofficial protocol, untested on a real camera** |
| First-run setup wizard with step-by-step connection test | Done |
| Windows installer files (`packaging/`) | Written, **never built** (needs Windows) |
| Timelapse, camera failure detection | Not started |

**Nothing here has been run against a real printer yet.** Things most likely to need a fix on the first
real run: FTPS upload, the print-start (`project_file`) message, AMS load/unload, the camera stream,
and HMS data. HMS codes are shown raw (like `0300_0100_0001_0001`); search them on wiki.bambulab.com,
because the app has no code-to-text table it can trust.

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
pip install -e ".[ui,dev]"

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

## Building the Windows installer

On Windows, from the `p1s-controller` folder:

```
packaging\build_windows.bat
```

This installs PyInstaller, builds `dist\P1S Controller\`, and (if Inno Setup 6 is installed) writes
`dist\P1S-Controller-Setup.exe`. If the build fails, send me the error output.

## First test on a real printer

1. `pytest` should pass (62 tests).
2. `p1s-gui` opens the setup wizard on first run. Walk through it; the last page reads from the printer only.
3. Leave **Allow control** off. Check the Dashboard, AMS panel and Health tab against the printer's screen.
4. Press **Start camera** and confirm the picture.
5. Tick **Allow control**, then try, in this order: light, speed, a small jog on the Control tab, then send and
   print a small file from the Library with the plate clear. Stay at the printer.
6. Note anything that differs and report it.

## Tests

```
pytest
```


## Slicing

The Library tab slices `.3mf` projects and `.stl` files for the P1S. It does not contain its own slicing engine:
it drives the Bambu Studio you already have installed (set `P1S_SLICER` to its .exe if it is somewhere unusual),
so the G-code is what Bambu Studio itself would produce. The P1S uses the X1C process presets and P1S/X1C
filament presets; the app reads them from the install, picks the filament preset that matches each AMS spool,
and writes `<name>.gcode.3mf` next to the model. Bambu Studio is a separate program with its own licence.
