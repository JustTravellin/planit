"""Turns a stream of printer states into print-history rows and user-facing events."""
from __future__ import annotations

import time
from typing import Callable

from .db import Database
from .state import PrinterState

ACTIVE = {"PREPARE", "RUNNING", "PAUSE"}


class HistoryRecorder:
    def __init__(self, db: Database, clock: Callable[[], float] = time.time):
        self.db = db
        self.clock = clock
        self._prev: str | None = None
        self._current_id: int | None = None
        self._expected: dict[int, float] = {}
        self._pending_name: str | None = None

    def set_expected_usage(self, usage: dict[int, float], name: str | None = None) -> None:
        """Remember per-slot filament use for a print started from this app."""
        self._expected = dict(usage)
        self._pending_name = name

    def observe(self, state: PrinterState) -> str | None:
        """Feed each new state. Returns an event name when something notable happened:
        started, paused, resumed, finished, failed or cancelled."""
        cur = state.gcode_state
        if cur == "UNKNOWN":
            return None
        prev, self._prev = self._prev, cur
        if prev is None:
            if cur in ACTIVE:  # app attached mid-print
                self._start(state)
            return None
        if prev == cur:
            return None
        if cur in ("PREPARE", "RUNNING") and prev not in ACTIVE:
            self._start(state)
            return "started"
        if cur == "PAUSE" and prev in ("PREPARE", "RUNNING"):
            return "paused"
        if cur == "RUNNING" and prev == "PAUSE":
            return "resumed"
        if prev in ACTIVE and cur in ("FINISH", "FAILED", "IDLE"):
            result = {"FINISH": "finished", "FAILED": "failed", "IDLE": "cancelled"}[cur]
            self._end(state, result)
            return result
        return None

    def _start(self, state: PrinterState) -> None:
        name = state.job_name or self._pending_name or "Unnamed print"
        self._current_id = self.db.start_print(name, self.clock())

    def _end(self, state: PrinterState, result: str) -> None:
        grams = sum(self._expected.values()) if self._expected else None
        if self._current_id is not None:
            self.db.finish_print(self._current_id, result, grams if result == "finished" else None,
                                 name=state.job_name or None, ended_at=self.clock())
        if result == "finished" and self._expected:
            self.db.deduct_usage(self._expected)
        self._current_id = None
        self._expected = {}
        self._pending_name = None
