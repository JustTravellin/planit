"""Builders for the JSON payloads the P1S accepts on device/<serial>/request.

These follow the community-documented local protocol (see OpenBambuAPI). Each
function only builds a dict; sending is done by MqttClient, which also enforces
the read-only guard.
"""
from __future__ import annotations

from typing import Any

_seq = 0


def _next_seq() -> str:
    global _seq
    _seq += 1
    return str(_seq)


def pushall() -> dict[str, Any]:
    """Ask the printer for a full status report."""
    return {"pushing": {"sequence_id": _next_seq(), "command": "pushall"}}


def get_version() -> dict[str, Any]:
    return {"info": {"sequence_id": _next_seq(), "command": "get_version"}}


def pause() -> dict[str, Any]:
    return {"print": {"sequence_id": _next_seq(), "command": "pause"}}


def resume() -> dict[str, Any]:
    return {"print": {"sequence_id": _next_seq(), "command": "resume"}}


def stop() -> dict[str, Any]:
    return {"print": {"sequence_id": _next_seq(), "command": "stop"}}


def gcode_line(lines: str) -> dict[str, Any]:
    """Send raw G-code. Newline-terminate each line."""
    if not lines.endswith("\n"):
        lines += "\n"
    return {"print": {"sequence_id": _next_seq(), "command": "gcode_line", "param": lines}}


SPEED_LEVELS = {"silent": 1, "standard": 2, "sport": 3, "ludicrous": 4}


def print_speed(level: int | str) -> dict[str, Any]:
    if isinstance(level, str):
        level = SPEED_LEVELS[level.lower()]
    if level not in (1, 2, 3, 4):
        raise ValueError("speed level must be 1-4")
    return {"print": {"sequence_id": _next_seq(), "command": "print_speed", "param": str(level)}}


def set_nozzle_temp(celsius: int) -> dict[str, Any]:
    _check_temp(celsius, 300)
    return gcode_line(f"M104 S{celsius}")


def set_bed_temp(celsius: int) -> dict[str, Any]:
    _check_temp(celsius, 120)
    return gcode_line(f"M140 S{celsius}")


def _check_temp(celsius: int, limit: int) -> None:
    if not 0 <= celsius <= limit:
        raise ValueError(f"temperature must be between 0 and {limit} C")


def light(on: bool, node: str = "chamber_light") -> dict[str, Any]:
    if node not in ("chamber_light", "work_light"):
        raise ValueError("node must be chamber_light or work_light")
    return {
        "system": {
            "sequence_id": _next_seq(),
            "command": "ledctrl",
            "led_node": node,
            "led_mode": "on" if on else "off",
            "led_on_time": 500,
            "led_off_time": 500,
            "loop_times": 0,
            "interval_time": 0,
        }
    }


def project_file(
    file_name: str,
    *,
    plate: int = 1,
    ams_mapping: list[int] | None = None,
    use_ams: bool = True,
    bed_leveling: bool = True,
    flow_calibration: bool = True,
    vibration_calibration: bool = True,
    timelapse: bool = False,
    bed_type: str = "auto",
) -> dict[str, Any]:
    """Start a print from a .gcode.3mf already uploaded to the printer's SD card/storage."""
    subtask = file_name
    for suffix in (".gcode.3mf", ".3mf"):
        if subtask.endswith(suffix):
            subtask = subtask[: -len(suffix)]
            break
    return {
        "print": {
            "sequence_id": _next_seq(),
            "command": "project_file",
            "param": f"Metadata/plate_{plate}.gcode",
            "project_id": "0",
            "profile_id": "0",
            "task_id": "0",
            "subtask_id": "0",
            "subtask_name": subtask,
            "file": "",
            "url": f"file:///sdcard/{file_name}",
            "md5": "",
            "timelapse": timelapse,
            "bed_type": bed_type,
            "bed_leveling": bed_leveling,
            "flow_cali": flow_calibration,
            "vibration_cali": vibration_calibration,
            "layer_inspect": False,
            "use_ams": use_ams,
            "ams_mapping": ams_mapping or [],
        }
    }


# --- manual controls ----------------------------------------------------------
MAX_JOG_MM = 100
FAN_PINS = {"part": 1, "aux": 2, "chamber": 3}
MIN_EXTRUDE_TEMP = 170


def home() -> dict[str, Any]:
    return gcode_line("G28")


def auto_bed_level() -> dict[str, Any]:
    return gcode_line("G29")


def move(axis: str, mm: float, feed: int = 3000) -> dict[str, Any]:
    """Relative jog of one axis. Restores absolute mode afterwards."""
    axis = axis.upper()
    if axis not in ("X", "Y", "Z"):
        raise ValueError("axis must be X, Y or Z")
    if mm == 0 or abs(mm) > MAX_JOG_MM:
        raise ValueError(f"move must be non-zero and at most {MAX_JOG_MM} mm")
    max_feed = 1200 if axis == "Z" else 9000
    if not 60 <= feed <= max_feed:
        raise ValueError(f"feed rate for {axis} must be between 60 and {max_feed} mm/min")
    return gcode_line(f"G91\nG1 {axis}{mm:g} F{feed}\nG90")


def set_fan(name: str, percent: int) -> dict[str, Any]:
    if name not in FAN_PINS:
        raise ValueError("fan must be part, aux or chamber")
    if not 0 <= percent <= 100:
        raise ValueError("fan speed must be 0-100%")
    return gcode_line(f"M106 P{FAN_PINS[name]} S{round(percent * 255 / 100)}")


def extrude(mm: float, nozzle_temp: float, feed: int = 300) -> dict[str, Any]:
    """Extrude (positive) or retract (negative) filament. Refused with a cold nozzle."""
    if nozzle_temp < MIN_EXTRUDE_TEMP:
        raise ValueError(f"nozzle is too cold to extrude ({nozzle_temp:.0f} C, need {MIN_EXTRUDE_TEMP}+)")
    if mm == 0 or abs(mm) > 50:
        raise ValueError("extrude length must be non-zero and at most 50 mm")
    return gcode_line(f"M83\nG1 E{mm:g} F{feed}")


def ams_load(tray: int, nozzle_temp: int = 220) -> dict[str, Any]:
    """Load filament from a global AMS tray index (ams*4+slot). Shape from community docs; unverified."""
    if not 0 <= tray <= 15:
        raise ValueError("tray must be 0-15")
    return {"print": {"sequence_id": _next_seq(), "command": "ams_change_filament", "target": tray,
                      "curr_temp": nozzle_temp, "tar_temp": nozzle_temp}}


def ams_unload(nozzle_temp: int = 220) -> dict[str, Any]:
    """Unload whatever is loaded (target 255). Shape from community docs; unverified."""
    return {"print": {"sequence_id": _next_seq(), "command": "ams_change_filament", "target": 255,
                      "curr_temp": nozzle_temp, "tar_temp": nozzle_temp}}
