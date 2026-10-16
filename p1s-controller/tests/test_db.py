from p1s_controller.db import Database


def test_print_lifecycle_and_stats():
    db = Database()
    a = db.start_print("benchy", 1000)
    db.finish_print(a, "finished", 12.5, ended_at=4600)
    b = db.start_print("fail", 5000)
    db.finish_print(b, "failed", None, ended_at=5100)
    s = db.stats()
    assert s["total"] == 2 and s["finished"] == 1 and s["failed"] == 1
    assert s["seconds"] == 3700 and s["grams"] == 12.5
    assert s["success_rate"] == 0.5
    assert [r["name"] for r in db.list_prints()] == ["fail", "benchy"]


def test_stats_empty():
    assert Database().stats()["success_rate"] is None


def test_spools_slots_and_deduction():
    db = Database()
    red = db.add_spool("Red PLA", "PLA", "#ff0000", initial_g=1000)
    blue = db.add_spool("Blue PLA", "PLA", "0000FF", initial_g=500)
    db.assign_slot(red, 0)
    db.assign_slot(blue, 1)
    db.assign_slot(blue, 0)  # steals slot 0 from red
    spools = {s.id: s for s in db.list_spools()}
    assert spools[red].slot is None and spools[blue].slot == 0
    assert spools[red].color == "FF0000"
    db.deduct_usage({0: 120.0, 3: 50.0})
    assert db.spool_for_slot(0).remaining_g == 380.0
    db.deduct_usage({0: 9999})
    assert db.spool_for_slot(0).remaining_g == 0


def test_tags():
    db = Database()
    db.set_tags("a.3mf", "  gift, pla ")
    assert db.get_tags("a.3mf") == "gift, pla"
    db.set_tags("a.3mf", "")
    assert db.get_tags("a.3mf") == ""


def test_persists_and_versioned(tmp_path):
    p = tmp_path / "x.db"
    db = Database(p)
    db.add_spool("s")
    db.close()
    assert len(Database(p).list_spools()) == 1
