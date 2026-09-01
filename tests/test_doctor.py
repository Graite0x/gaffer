from goloops.doctor import format_report, inspect


def test_doctor_marks_ours_slots(tmp_path) -> None:
    slots = {s.id: s for s in inspect(tmp_path)}
    assert slots["G1"].status == "ours"
    assert slots["L2"].status == "ours"
    assert slots["L5"].status == "ours"
    report = format_report(list(slots.values()))
    assert "G1" in report
    assert "unfinish" in report
