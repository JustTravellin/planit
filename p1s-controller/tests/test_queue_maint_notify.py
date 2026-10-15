import json
import zipfile

import pytest

from p1s_controller import config, maintenance, notify
from p1s_controller.db import Database


def test_queue_order_move_and_status():
    db = Database()
    a, b, c = (db.queue_add(f"/x/{n}.gcode.3mf", n) for n in "abc")
    assert [r["name"] for r in db.queue_list()] == ["a", "b", "c"]
    db.queue_move(c, -1)
    assert [r["name"] for r in db.queue_list()] == ["a", "c", "b"]
    db.queue_move(a, -1)  # already first: no change
    assert db.queue_next()["name"] == "a"
    db.queue_set_status(a, "sent")
    assert db.queue_sent()["name"] == "a" and db.queue_next()["name"] == "c"
    db.queue_set_status(a, "done")
    db.queue_clear_finished()
    assert [r["name"] for r in db.queue_list()] == ["c", "b"]


def test_old_database_is_migrated(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE prints (id INTEGER PRIMARY KEY, name TEXT, started_at REAL, ended_at REAL, "
                       "result TEXT, seconds REAL, filament_g REAL); PRAGMA user_version = 1;")
    conn.commit()
    conn.close()
    db = Database(path)
    assert db.queue_list() == [] and len(db.maintenance_list()) == 4


def test_maintenance_hours_and_due():
    db = Database()
    pid = db.start_print("x", started_at=1)
    db.finish_print(pid, "finished", ended_at=21 * 3600 + 1)  # 21 print hours
    by_name = {t.name.split(" (")[0]: t for t in maintenance.statuses(db)}
    plate = by_name["Clean build plate"]
    assert plate.overdue and plate.text.startswith("Overdue")
    assert [t.name for t in maintenance.due(db)] == [plate.name]
    db.maintenance_done(plate.id)
    assert maintenance.due(db) == []
    db.maintenance_set_interval(plate.id, 22)
    assert maintenance.statuses(db)[0].soon is False


@pytest.mark.parametrize("kind,secret,target,check", [
    ("telegram", "123:abc", "42", lambda r, b: r.full_url == "https://api.telegram.org/bot123:abc/sendMessage" and b["chat_id"] == "42"),
    ("discord", "https://discord.com/api/webhooks/1/x", "", lambda r, b: "Print finished" in b["content"]),
    ("webhook", "https://example.com/hook", "", lambda r, b: b["title"] == "Print finished"),
])
def test_notify_requests(kind, secret, target, check):
    req = notify.build_request(notify.NotifyConfig(kind, target, secret), "Print finished", "Benchy done")
    assert check(req, json.loads(req.data))


def test_ntfy_and_https_only():
    req = notify.build_request(notify.NotifyConfig("ntfy", "https://ntfy.sh/mytopic", "tok"), "Done", "ok")
    assert req.data == b"ok" and req.get_header("Authorization") == "Bearer tok" and req.get_header("Title") == "Done"
    with pytest.raises(ValueError, match="https"):
        notify.build_request(notify.NotifyConfig("webhook", "", "http://insecure"), "t", "x")
    assert not notify.NotifyConfig("telegram", "1", "").enabled and notify.NotifyConfig("ntfy", "https://x/y").enabled
    assert notify.NotifyConfig("webhook", "", "https://x", ["failed"]).wants("failed")
    assert not notify.NotifyConfig("webhook", "", "https://x", ["failed"]).wants("finished")


def test_send_raises_on_failure(monkeypatch):
    class Resp:
        status = 500
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda *a, **k: Resp())
    with pytest.raises(OSError):
        notify.send(notify.NotifyConfig("webhook", "", "https://x"), "t", "x")


def test_notify_config_roundtrip_without_keyring(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_keyring", lambda: None)
    config.save_notify(notify.NotifyConfig("discord", "", "https://discord.com/api/webhooks/1/x", ["failed"]), tmp_path)
    loaded = config.load_notify(tmp_path)
    assert (loaded.kind, loaded.secret, loaded.events) == ("discord", "https://discord.com/api/webhooks/1/x", ["failed"])
    assert config.load_notify(tmp_path / "none").kind == ""
