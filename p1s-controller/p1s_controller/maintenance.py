"""Which maintenance tasks are due, judged by printing hours recorded in this app's history."""
from __future__ import annotations

from dataclasses import dataclass

from .db import Database

DUE_SOON = 0.9  # warn at 90% of the interval


@dataclass
class TaskStatus:
    id: int
    name: str
    note: str
    interval: float
    since: float  # print hours since last done

    @property
    def fraction(self) -> float:
        return self.since / self.interval if self.interval else 0.0

    @property
    def overdue(self) -> bool:
        return self.since >= self.interval

    @property
    def soon(self) -> bool:
        return self.fraction >= DUE_SOON

    @property
    def text(self) -> str:
        left = self.interval - self.since
        return f"Overdue by {-left:.1f} h" if left <= 0 else f"Due in {left:.1f} h"


def statuses(db: Database) -> list[TaskStatus]:
    total = db.print_hours()
    return [TaskStatus(r["id"], r["name"], r["note"], r["interval_hours"], max(0.0, total - r["done_at_hours"]))
            for r in db.maintenance_list()]


def due(db: Database) -> list[TaskStatus]:
    return [t for t in statuses(db) if t.soon]
