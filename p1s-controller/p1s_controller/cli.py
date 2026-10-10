"""Command-line front end: `p1s setup | status | watch | pause | resume | stop | light | speed | send | print`."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import commands, config, ftps, threemf
from .mqtt_client import MqttClient
from .state import PrinterState


def _summary(s: PrinterState) -> str:
    lines = [
        f"State:    {s.gcode_state}  {s.percent}%  layer {s.layer}/{s.total_layers}  {s.remaining_minutes} min left",
        f"Job:      {s.job_name or '-'}",
        f"Nozzle:   {s.nozzle_temp:.0f}/{s.nozzle_target:.0f} C   Bed: {s.bed_temp:.0f}/{s.bed_target:.0f} C   Chamber: {s.chamber_temp:.0f} C",
        f"Light:    {s.chamber_light_on}   Speed level: {s.speed_level}",
        f"Fans:     {s.fans}",
    ]
    active = s.active_tray
    for t in s.ams_trays:
        marker = "*" if t.global_index == active else " "
        label = f"{t.material} #{t.color} {t.remain}%" if not t.empty else "empty"
        lines.append(f"AMS{t.ams_id + 1} slot {t.slot + 1}{marker}: {label}")
    return "\n".join(lines)


def _connect(control: bool) -> MqttClient:
    cfg = config.load()
    if cfg is None:
        sys.exit("No printer configured. Run `p1s setup` first.")
    client = MqttClient(cfg.ip, cfg.serial, cfg.access_code, allow_control=control)
    client.connect()
    return client


def _confirm(prompt: str, yes: bool) -> None:
    if yes:
        return
    if input(f"{prompt} [y/N] ").strip().lower() != "y":
        sys.exit("Cancelled.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="p1s")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="save printer IP, serial and LAN access code")
    s.add_argument("--ip", required=True)
    s.add_argument("--serial", required=True)
    s.add_argument("--code", required=True, help="LAN access code from the printer's screen")

    sub.add_parser("status", help="print a one-off status summary")
    sub.add_parser("watch", help="print status every few seconds")
    for name in ("pause", "resume", "stop"):
        c = sub.add_parser(name)
        c.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    l = sub.add_parser("light")
    l.add_argument("state", choices=["on", "off"])
    sp = sub.add_parser("speed")
    sp.add_argument("level", choices=list(commands.SPEED_LEVELS))
    f = sub.add_parser("inspect", help="show what's inside a .gcode.3mf and the suggested AMS mapping")
    f.add_argument("file", type=Path)
    for name in ("send", "print"):
        c = sub.add_parser(name, help="upload a .gcode.3mf" + (" and start it" if name == "print" else ""))
        c.add_argument("file", type=Path)
        c.add_argument("--yes", action="store_true")
        if name == "print":
            c.add_argument("--ams-map", help="comma-separated global tray indexes per filament, e.g. 0,1 (overrides the suggestion)")

    args = p.parse_args(argv)

    if args.cmd == "setup":
        config.save(config.PrinterConfig(args.ip, args.serial, args.code))
        print("Saved.")
        return

    if args.cmd == "inspect":
        info = threemf.read(args.file)
        print(f"Plate {info.plate}: {info.print_seconds // 60} min, {info.weight_grams:.1f} g")
        for fil in info.filaments:
            print(f"  filament {fil.index}: {fil.material} #{fil.color} {fil.used_grams:.1f} g")
        return

    needs_control = args.cmd in {"pause", "resume", "stop", "light", "speed", "print"}
    client = _connect(control=needs_control)
    try:
        if args.cmd == "status":
            print(_summary(client.state))
        elif args.cmd == "watch":
            while True:
                print("\033[2J\033[H" + _summary(client.state), flush=True)
                time.sleep(3)
        elif args.cmd in {"pause", "resume", "stop"}:
            _confirm(f"{args.cmd.title()} the current print?", args.yes)
            client.send(getattr(commands, args.cmd)())
        elif args.cmd == "light":
            client.send(commands.light(args.state == "on"))
        elif args.cmd == "speed":
            client.send(commands.print_speed(args.level))
        elif args.cmd in {"send", "print"}:
            info = threemf.read(args.file)
            cfg = config.load()
            name = ftps.upload(cfg.ip, cfg.access_code, args.file)
            print(f"Uploaded {name}.")
            if args.cmd == "print":
                if args.ams_map:
                    mapping = [int(x) for x in args.ams_map.split(",")]
                else:
                    suggested = threemf.suggest_ams_mapping(info.filaments, client.state.ams_trays)
                    if None in suggested:
                        sys.exit(f"No matching filament loaded for every colour ({suggested}). Pass --ams-map.")
                    mapping = suggested
                _confirm(f"Start printing {name} with AMS mapping {mapping}?", args.yes)
                client.send(commands.project_file(name, plate=info.plate, ams_mapping=mapping))
                print("Print started.")
        time.sleep(0.5)  # let queued publishes flush
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
