"""Local SQLite store for print history, filament spools and file tags."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE prints (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    result TEXT,            -- finished | failed | cancelled | NULL while running
    seconds REAL,
    filament_g REAL
);
CREATE TABLE spools (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    material TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '',   -- RRGGBB
    brand TEXT NOT NULL DEFAULT '',
    initial_g REAL NOT NULL DEFAULT 1000,
    remaining_g REAL NOT NULL DEFAULT 1000,
    slot INTEGER                      -- global AMS tray index, or NULL
);
CREATE TABLE file_tags (path TEXT PRIMARY KEY, tags TEXT NOT NULL);
"""

_V2 = """
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY,
    position REAL NOT NULL,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    plate INTEGER NOT NULL DEFAULT 1,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | sent | done | failed | skipped
    added_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    interval_hours REAL NOT NULL,
    done_at_hours REAL NOT NULL DEFAULT 0,    -- total print hours when last done
    note TEXT NOT NULL DEFAULT ''
);
"""

# Starting points only; the intervals are editable. Check Bambu's wiki for your usage.
DEFAULT_MAINTENANCE = [
    ("Clean build plate (wash with soap and water)", 20, "Oils from fingers cause adhesion failures."),
    ("Empty purge waste bin / clean wiper", 25, "Waste builds up behind the printer after colour changes."),
    ("Clean and lubricate Y and Z rods", 200, "Wipe old grease off the carbon/steel rods first."),
    ("Inspect nozzle, hotend and cooling fans", 100, "Look for clogs, wear and dust."),
]


@dataclass
class Spool:
    id: int
    name: str
    material: str
    color: str
    brand: str
    initial_g: float
    remaining_g: float
    slot: int | None


class Database:
    def __init__(self, path: str | Path = ":memory:"):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version < SCHEMA_VERSION:
            if version == 0:
                self.conn.executescript(_SCHEMA)
            self.conn.executescript(_V2)
            self.conn.executemany("INSERT INTO maintenance (name, interval_hours, note) VALUES (?,?,?)",
                                  DEFAULT_MAINTENANCE)
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.conn.commit()
        elif version > SCHEMA_VERSION:
            raise RuntimeError("Database was created by a newer version of this app.")

    def close(self) -> None:
        self.conn.close()

    # --- prints ------------------------------------------------------------
    def start_print(self, name: str, started_at: float | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO prints (name, started_at) VALUES (?, ?)", (name, started_at or time.time())
        )
        self.conn.commit()
        return cur.lastrowid

    def finish_print(self, print_id: int, result: str, filament_g: float | None = None,
                     name: str | None = None, ended_at: float | None = None) -> None:
        ended_at = ended_at or time.time()
        row = self.conn.execute("SELECT started_at FROM prints WHERE id = ?", (print_id,)).fetchone()
        if row is None:
            return
        self.conn.execute(
            "UPDATE prints SET ended_at=?, result=?, seconds=?, filament_g=?, name=COALESCE(?, name) WHERE id=?",
            (ended_at, result, ended_at - row["started_at"], filament_g, name, print_id),
        )
        self.conn.commit()

    def list_prints(self, limit: int = 200) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM prints ORDER BY started_at DESC, id DESC LIMIT ?", (limit,)).fetchall()

    def stats(self) -> dict:
        row = self.conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(result='finished') AS finished,
                      SUM(result='failed') AS failed,
                      SUM(result='cancelled') AS cancelled,
                      COALESCE(SUM(seconds), 0) AS seconds,
                      COALESCE(SUM(CASE WHEN result='finished' THEN filament_g END), 0) AS grams
               FROM prints WHERE result IS NOT NULL"""
        ).fetchone()
        done = (row["finished"] or 0) + (row["failed"] or 0) + (row["cancelled"] or 0)
        return {
            "total": row["total"],
            "finished": row["finished"] or 0,
            "failed": row["failed"] or 0,
            "cancelled": row["cancelled"] or 0,
            "seconds": row["seconds"],
            "grams": row["grams"],
            "success_rate": (row["finished"] or 0) / done if done else None,
        }

    # --- spools ------------------------------------------------------------
    def add_spool(self, name: str, material: str = "", color: str = "", brand: str = "",
                  initial_g: float = 1000, remaining_g: float | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO spools (name, material, color, brand, initial_g, remaining_g) VALUES (?,?,?,?,?,?)",
            (name, material, color.lstrip("#").upper(), brand, initial_g,
             initial_g if remaining_g is None else remaining_g),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_spools(self) -> list[Spool]:
        return [Spool(**dict(r)) for r in self.conn.execute("SELECT * FROM spools ORDER BY id")]

    def set_remaining(self, spool_id: int, grams: float) -> None:
        self.conn.execute("UPDATE spools SET remaining_g=? WHERE id=?", (max(0.0, grams), spool_id))
        self.conn.commit()

    def delete_spool(self, spool_id: int) -> None:
        self.conn.execute("DELETE FROM spools WHERE id=?", (spool_id,))
        self.conn.commit()

    def assign_slot(self, spool_id: int, slot: int | None) -> None:
        """Put a spool in an AMS slot; a slot holds at most one spool."""
        if slot is not None:
            self.conn.execute("UPDATE spools SET slot=NULL WHERE slot=?", (slot,))
        self.conn.execute("UPDATE spools SET slot=? WHERE id=?", (slot, spool_id))
        self.conn.commit()

    def deduct_usage(self, usage: dict[int, float]) -> None:
        """Subtract grams used per AMS slot from the spool assigned to that slot."""
        for slot, grams in usage.items():
            self.conn.execute(
                "UPDATE spools SET remaining_g = MAX(0, remaining_g - ?) WHERE slot=?", (grams, slot)
            )
        self.conn.commit()

    def spool_for_slot(self, slot: int) -> Spool | None:
        row = self.conn.execute("SELECT * FROM spools WHERE slot=?", (slot,)).fetchone()
        return Spool(**dict(row)) if row else None

    # --- print queue ---------------------------------------------------------
    def queue_add(self, path: str, name: str, plate: int = 1, note: str = "") -> int:
        pos = self.conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM queue").fetchone()[0]
        cur = self.conn.execute("INSERT INTO queue (position, path, name, plate, note, added_at) VALUES (?,?,?,?,?,?)",
                                (pos, path, name, plate, note, time.time()))
        self.conn.commit()
        return cur.lastrowid

    def queue_list(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM queue ORDER BY position").fetchall()

    def queue_next(self) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM queue WHERE status='pending' ORDER BY position LIMIT 1").fetchone()

    def queue_sent(self) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM queue WHERE status='sent' ORDER BY position LIMIT 1").fetchone()

    def queue_set_status(self, job_id: int, status: str) -> None:
        self.conn.execute("UPDATE queue SET status=? WHERE id=?", (status, job_id))
        self.conn.commit()

    def queue_remove(self, job_id: int) -> None:
        self.conn.execute("DELETE FROM queue WHERE id=?", (job_id,))
        self.conn.commit()

    def queue_clear_finished(self) -> None:
        self.conn.execute("DELETE FROM queue WHERE status IN ('done', 'failed', 'skipped')")
        self.conn.commit()

    def queue_move(self, job_id: int, delta: int) -> None:
        """Move a pending job up (-1) or down (+1) among the pending jobs."""
        rows = [r for r in self.queue_list() if r["status"] == "pending"]
        ids = [r["id"] for r in rows]
        if job_id not in ids:
            return
        i = ids.index(job_id)
        j = i + delta
        if not 0 <= j < len(ids):
            return
        a, b = rows[i]["position"], rows[j]["position"]
        self.conn.execute("UPDATE queue SET position=? WHERE id=?", (b, ids[i]))
        self.conn.execute("UPDATE queue SET position=? WHERE id=?", (a, ids[j]))
        self.conn.commit()

    # --- maintenance -----------------------------------------------------------
    def print_hours(self) -> float:
        row = self.conn.execute("SELECT COALESCE(SUM(seconds), 0) FROM prints WHERE result IS NOT NULL").fetchone()
        return row[0] / 3600

    def maintenance_list(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM maintenance ORDER BY id").fetchall()

    def maintenance_add(self, name: str, interval_hours: float, note: str = "") -> int:
        cur = self.conn.execute("INSERT INTO maintenance (name, interval_hours, done_at_hours, note) VALUES (?,?,?,?)",
                                (name, interval_hours, self.print_hours(), note))
        self.conn.commit()
        return cur.lastrowid

    def maintenance_done(self, task_id: int) -> None:
        self.conn.execute("UPDATE maintenance SET done_at_hours=? WHERE id=?", (self.print_hours(), task_id))
        self.conn.commit()

    def maintenance_set_interval(self, task_id: int, hours: float) -> None:
        self.conn.execute("UPDATE maintenance SET interval_hours=? WHERE id=?", (max(1.0, hours), task_id))
        self.conn.commit()

    def maintenance_delete(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM maintenance WHERE id=?", (task_id,))
        self.conn.commit()

    # --- file tags ---------------------------------------------------------
    def get_tags(self, path: str) -> str:
        row = self.conn.execute("SELECT tags FROM file_tags WHERE path=?", (path,)).fetchone()
        return row["tags"] if row else ""

    def set_tags(self, path: str, tags: str) -> None:
        tags = tags.strip()
        if tags:
            self.conn.execute("INSERT OR REPLACE INTO file_tags (path, tags) VALUES (?, ?)", (path, tags))
        else:
            self.conn.execute("DELETE FROM file_tags WHERE path=?", (path,))
        self.conn.commit()
