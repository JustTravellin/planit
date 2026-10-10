from __future__ import annotations

import time


def fmt_minutes(minutes: int) -> str:
    h, m = divmod(max(0, int(minutes)), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def fmt_seconds(seconds: float) -> str:
    return fmt_minutes(int(seconds // 60))


def eta_clock(minutes_left: int, now: float | None = None) -> str:
    return time.strftime("%H:%M", time.localtime((now or time.time()) + minutes_left * 60))
