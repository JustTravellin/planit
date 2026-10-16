"""Typed view of the printer's status reports.

The printer publishes a full report on request and then only the fields that
changed, so we merge every incoming report into the previous one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXTERNAL_SPOOL = 254


@dataclass
class AmsTray:
    ams_id: int
    slot: int  # 0-3 within the unit
    material: str = ""
    color: str = ""  # "RRGGBB"
    remain: int = -1  # percent; -1 = unknown
    brand: str = ""

    @property
    def global_index(self) -> int:
        return self.ams_id * 4 + self.slot

    @property
    def empty(self) -> bool:
        return not self.material


@dataclass
class PrinterState:
    raw: dict[str, Any] = field(default_factory=dict)
    modules: dict[str, str] = field(default_factory=dict)  # firmware module name -> version

    def update(self, report: dict[str, Any]) -> None:
        """Merge a status report (the full MQTT JSON payload) into the state."""
        section = report.get("print")
        if isinstance(section, dict):
            _merge(self.raw, section)
        info = report.get("info")
        if isinstance(info, dict) and isinstance(info.get("module"), list):
            for mod in info["module"]:
                if isinstance(mod, dict) and mod.get("name"):
                    self.modules[str(mod["name"])] = str(mod.get("sw_ver", ""))

    # --- print job -------------------------------------------------------
    @property
    def gcode_state(self) -> str:
        return str(self.raw.get("gcode_state", "UNKNOWN"))

    @property
    def percent(self) -> int:
        return int(self.raw.get("mc_percent", 0) or 0)

    @property
    def remaining_minutes(self) -> int:
        return int(self.raw.get("mc_remaining_time", 0) or 0)

    @property
    def layer(self) -> int:
        return int(self.raw.get("layer_num", 0) or 0)

    @property
    def total_layers(self) -> int:
        return int(self.raw.get("total_layer_num", 0) or 0)

    @property
    def job_name(self) -> str:
        return str(self.raw.get("subtask_name") or self.raw.get("gcode_file") or "")

    @property
    def speed_level(self) -> int:
        return int(self.raw.get("spd_lvl", 2) or 2)

    # --- temperatures / fans --------------------------------------------
    @property
    def nozzle_temp(self) -> float:
        return float(self.raw.get("nozzle_temper", 0) or 0)

    @property
    def nozzle_target(self) -> float:
        return float(self.raw.get("nozzle_target_temper", 0) or 0)

    @property
    def bed_temp(self) -> float:
        return float(self.raw.get("bed_temper", 0) or 0)

    @property
    def bed_target(self) -> float:
        return float(self.raw.get("bed_target_temper", 0) or 0)

    @property
    def chamber_temp(self) -> float:
        return float(self.raw.get("chamber_temper", 0) or 0)

    @property
    def fans(self) -> dict[str, int]:
        return {
            "part": _int(self.raw.get("cooling_fan_speed")),
            "aux": _int(self.raw.get("big_fan1_speed")),
            "chamber": _int(self.raw.get("big_fan2_speed")),
        }

    # --- health ------------------------------------------------------------
    @property
    def print_error(self) -> int:
        return _int(self.raw.get("print_error"))

    @property
    def hms_codes(self) -> list[str]:
        """Active HMS entries as 'XXXX_XXXX_XXXX_XXXX' (the form Bambu's wiki uses)."""
        out = []
        for item in self.raw.get("hms") or []:
            attr, code = _int(item.get("attr")), _int(item.get("code"))
            out.append(f"{attr >> 16:04X}_{attr & 0xFFFF:04X}_{code >> 16:04X}_{code & 0xFFFF:04X}")
        return out

    @property
    def wifi_dbm(self) -> int | None:
        raw = str(self.raw.get("wifi_signal", "")).lower().replace("dbm", "").strip()
        try:
            return int(raw)
        except ValueError:
            return None

    # --- lights -----------------------------------------------------------
    @property
    def chamber_light_on(self) -> bool | None:
        for item in self.raw.get("lights_report", []) or []:
            if item.get("node") == "chamber_light":
                return item.get("mode") == "on"
        return None

    # --- AMS --------------------------------------------------------------
    @property
    def ams_trays(self) -> list[AmsTray]:
        out: list[AmsTray] = []
        units = (self.raw.get("ams") or {}).get("ams") or []
        for unit in units:
            ams_id = _int(unit.get("id"))
            for tray in unit.get("tray") or []:
                out.append(
                    AmsTray(
                        ams_id=ams_id,
                        slot=_int(tray.get("id")),
                        material=str(tray.get("tray_type", "") or ""),
                        color=str(tray.get("tray_color", "") or "")[:6],
                        remain=_int(tray.get("remain"), -1),
                        brand=str(tray.get("tray_sub_brands", "") or ""),
                    )
                )
        return out

    @property
    def active_tray(self) -> int | None:
        """Global tray index currently loaded, or None if unknown/unloaded."""
        value = (self.raw.get("ams") or {}).get("tray_now")
        if value in (None, "", "255"):
            return None
        return _int(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _merge(dst: dict, src: dict) -> None:
    for key, value in src.items():
        if key == "ams" and isinstance(value, dict) and isinstance(dst.get(key), dict):
            _merge_ams(dst[key], value)
        elif isinstance(value, dict) and isinstance(dst.get(key), dict):
            _merge(dst[key], value)
        else:
            dst[key] = value


def _merge_ams(dst: dict, src: dict) -> None:
    """AMS reports carry lists of units/trays; merge those by id, not by position."""
    for key, value in src.items():
        if key == "ams" and isinstance(value, list):
            units = {str(u.get("id")): u for u in dst.get("ams", [])}
            for unit in value:
                uid = str(unit.get("id"))
                if uid in units:
                    merged_trays = {str(t.get("id")): t for t in units[uid].get("tray", [])}
                    for tray in unit.get("tray", []) or []:
                        tid = str(tray.get("id"))
                        merged_trays[tid] = {**merged_trays.get(tid, {}), **tray}
                    units[uid] = {**units[uid], **unit, "tray": sorted(merged_trays.values(), key=lambda t: str(t.get("id")))}
                else:
                    units[uid] = unit
            dst["ams"] = sorted(units.values(), key=lambda u: str(u.get("id")))
        else:
            dst[key] = value
