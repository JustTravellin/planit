from p1s_controller.db import Database
from p1s_controller.history import HistoryRecorder
from p1s_controller.state import PrinterState


def st(gcode_state, name="benchy"):
    s = PrinterState()
    s.update({"print": {"gcode_state": gcode_state, "subtask_name": name}})
    return s


def make():
    db = Database()
    t = [1000.0]
    rec = HistoryRecorder(db, clock=lambda: t[0])
    return db, rec, t


def test_full_print_with_deduction():
    db, rec, t = make()
    s = db.add_spool("Red", initial_g=500)
    db.assign_slot(s, 1)
    rec.set_expected_usage({1: 20.0})
    assert rec.observe(st("IDLE")) is None
    assert rec.observe(st("RUNNING")) == "started"
    t[0] += 600
    assert rec.observe(st("PAUSE")) == "paused"
    assert rec.observe(st("RUNNING")) == "resumed"
    t[0] += 600
    assert rec.observe(st("FINISH")) == "finished"
    row = db.list_prints()[0]
    assert row["result"] == "finished" and row["seconds"] == 1200 and row["filament_g"] == 20.0
    assert db.spool_for_slot(1).remaining_g == 480.0


def test_failed_and_cancelled_do_not_deduct():
    db, rec, t = make()
    s = db.add_spool("Red", initial_g=500)
    db.assign_slot(s, 0)
    rec.set_expected_usage({0: 50.0})
    rec.observe(st("IDLE"))
    rec.observe(st("RUNNING"))
    assert rec.observe(st("FAILED")) == "failed"
    rec.observe(st("IDLE"))
    rec.set_expected_usage({0: 50.0})
    rec.observe(st("RUNNING"))
    assert rec.observe(st("IDLE")) == "cancelled"
    assert db.spool_for_slot(0).remaining_g == 500
    assert [r["result"] for r in db.list_prints()] == ["cancelled", "failed"]


def test_attach_mid_print_records_without_event():
    db, rec, t = make()
    assert rec.observe(st("RUNNING")) is None
    assert rec.observe(st("FINISH")) == "finished"
    assert len(db.list_prints()) == 1


def test_unknown_state_ignored_and_repeats_silent():
    db, rec, t = make()
    assert rec.observe(PrinterState()) is None
    rec.observe(st("IDLE"))
    assert rec.observe(st("IDLE")) is None
    assert db.list_prints() == []
