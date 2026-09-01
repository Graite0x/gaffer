from pathlib import Path

from goloops.cli import main


def test_init_waves_unfinish(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert (tmp_path / "graph.md").exists()
    assert main(["waves"]) == 0
    assert main(["doctor"]) == 0
    assert main(["unfinish", "T001", "--reason", "no"]) == 0
    assert main(["status"]) == 0
    state = (tmp_path / ".goloops" / "state.json").read_text(encoding="utf-8")
    assert "T001" in state


def test_waves_prints_parallel(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "graph.md").write_text(
        "- [ ] [A] first\n- [P] [B] two -> A\n- [P] [C] three -> A\n",
        encoding="utf-8",
    )
    assert main(["waves"]) == 0
    out = capsys.readouterr().out
    assert "parallel: B, C" in out
