from pathlib import Path

from goloops.gate import RunState, promote, run_gate, unfinish


def test_empty_gate_passes(tmp_path: Path) -> None:
    assert run_gate(tmp_path, []).ok is True


def test_first_failure_wins(tmp_path: Path) -> None:
    result = run_gate(tmp_path, ["true", "false", "true"])
    assert result.ok is False
    assert result.command == "false"


def test_unfinish_takes_done_back(tmp_path: Path) -> None:
    state = RunState.load(tmp_path / "state.json")
    promote(state, "T001", "merged")
    assert "T001" in state.done
    unfinish(state, "T001", "gate lied")
    again = RunState.load(tmp_path / "state.json")
    assert "T001" not in again.done
    assert "T001" in again.failed
    assert again.notes["T001"] == "gate lied"
