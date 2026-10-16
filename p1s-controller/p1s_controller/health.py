"""Turns state changes into alerts: printer-reported errors and a few sanity checks."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .state import PrinterState

LOW_FILAMENT_PERCENT = 10
TEMP_DEVIATION = 20  # degrees C away from target while printing
WEAK_WIFI_DBM = -75


@dataclass
class Alert:
    severity: str  # error | warning
    title: str
    detail: str = ""
    time: float = field(default_factory=time.time)


class HealthMonitor:
    def __init__(self, clock: Callable[[], float] = time.time):
        self.clock = clock
        self._hms: set[str] = set()
        self._error = 0
        self._low: set[int] = set()
        self._temp_warned = False
        self._wifi_warned = False

    def observe(self, state: PrinterState) -> list[Alert]:
        alerts: list[Alert] = []
        now = self.clock()

        codes = set(state.hms_codes)
        for code in sorted(codes - self._hms):
            alerts.append(Alert("error", f"Printer reported HMS {code}",
                                "Search this code on wiki.bambulab.com for what it means.", now))
        self._hms = codes

        err = state.print_error
        if err and err != self._error:
            alerts.append(Alert("error", f"Print error 0x{err:08X}",
                                "The printer stopped or paused with an error. Check its screen.", now))
        self._error = err

        active = state.active_tray
        for tray in state.ams_trays:
            idx = tray.global_index
            if tray.empty or tray.remain < 0:
                continue
            if idx == active and tray.remain < LOW_FILAMENT_PERCENT and idx not in self._low:
                self._low.add(idx)
                alerts.append(Alert("warning", f"Filament low in AMS{tray.ams_id + 1} slot {tray.slot + 1}",
                                    f"{tray.remain}% left on a {tray.material} spool.", now))
            elif tray.remain >= LOW_FILAMENT_PERCENT + 5:
                self._low.discard(idx)

        printing = state.gcode_state == "RUNNING" and state.layer >= 2
        if printing and state.nozzle_target:
            off = abs(state.nozzle_temp - state.nozzle_target)
            if off > TEMP_DEVIATION and not self._temp_warned:
                self._temp_warned = True
                alerts.append(Alert("warning", "Nozzle temperature is off target",
                                    f"{state.nozzle_temp:.0f} C vs target {state.nozzle_target:.0f} C.", now))
            elif off < TEMP_DEVIATION / 2:
                self._temp_warned = False

        dbm = state.wifi_dbm
        if dbm is not None:
            if dbm < WEAK_WIFI_DBM and not self._wifi_warned:
                self._wifi_warned = True
                alerts.append(Alert("warning", "Weak Wi-Fi signal", f"{dbm} dBm; uploads and the camera may drop.", now))
            elif dbm > WEAK_WIFI_DBM + 5:
                self._wifi_warned = False
        return alerts
