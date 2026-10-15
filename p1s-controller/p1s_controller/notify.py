"""Phone/chat notifications: Telegram, Discord, ntfy, or a generic webhook. Plain HTTPS POSTs, no dependencies."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field

KINDS = ("telegram", "discord", "ntfy", "webhook")
DEFAULT_EVENTS = ("finished", "failed", "cancelled", "paused")
ALL_EVENTS = ("started", "paused", "resumed", "finished", "failed", "cancelled")


@dataclass
class NotifyConfig:
    kind: str = ""        # one of KINDS, "" = off
    target: str = ""      # telegram chat id | ntfy topic URL
    secret: str = ""      # telegram bot token | discord/webhook URL | ntfy access token (optional)
    events: list[str] = field(default_factory=lambda: list(DEFAULT_EVENTS))

    @property
    def enabled(self) -> bool:
        return self.kind in KINDS and bool(self.secret or (self.kind == "ntfy" and self.target))

    def wants(self, event: str) -> bool:
        return self.enabled and event in self.events


def build_request(cfg: NotifyConfig, title: str, text: str) -> urllib.request.Request:
    headers = {"User-Agent": "p1s-controller"}
    if cfg.kind == "telegram":
        url = f"https://api.telegram.org/bot{cfg.secret}/sendMessage"
        body = json.dumps({"chat_id": cfg.target, "text": f"{title}\n{text}"}).encode()
        headers["Content-Type"] = "application/json"
    elif cfg.kind == "discord":
        url, body = cfg.secret, json.dumps({"content": f"**{title}**\n{text}"}).encode()
        headers["Content-Type"] = "application/json"
    elif cfg.kind == "ntfy":
        url, body = cfg.target, text.encode()
        headers["Title"] = title.encode("ascii", "replace").decode()
        if cfg.secret:
            headers["Authorization"] = f"Bearer {cfg.secret}"
    elif cfg.kind == "webhook":
        url, body = cfg.secret, json.dumps({"title": title, "text": text}).encode()
        headers["Content-Type"] = "application/json"
    else:
        raise ValueError("Notifications are off")
    if not url.lower().startswith("https://"):
        raise ValueError("Notification URLs must be https://")
    return urllib.request.Request(url, data=body, headers=headers, method="POST")


def send(cfg: NotifyConfig, title: str, text: str, timeout: float = 10.0) -> None:
    """Send one message. Raises on any failure so the caller can show it."""
    with urllib.request.urlopen(build_request(cfg, title, text), timeout=timeout) as resp:
        if resp.status >= 300:
            raise OSError(f"Server answered {resp.status}")
