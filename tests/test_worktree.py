import subprocess
from pathlib import Path

import pytest

from gaffer.worktree import MergeAborted, create, merge_or_abort, remove


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def test_create_and_merge(git_repo: Path) -> None:
    wt = create(git_repo, "gaffer/T001", git_repo.parent / "wt-T001")
    (wt.path / "leaf.txt").write_text("x\n", encoding="utf-8")
    _git(wt.path, "add", "leaf.txt")
    _git(wt.path, "commit", "-m", "leaf")
    merge_or_abort(git_repo, wt.branch)
    assert (git_repo / "leaf.txt").read_text(encoding="utf-8") == "x\n"
    remove(wt, force=True)


def test_conflict_aborts_and_leaves_repo_clean(git_repo: Path) -> None:
    wt = create(git_repo, "gaffer/T001", git_repo.parent / "wt-T001")
    (wt.path / "README").write_text("agent\n", encoding="utf-8")
    _git(wt.path, "add", "README")
    _git(wt.path, "commit", "-m", "agent")
    (git_repo / "README").write_text("human\n", encoding="utf-8")
    _git(git_repo, "add", "README")
    _git(git_repo, "commit", "-m", "human")
    with pytest.raises(MergeAborted, match="Merge aborted due to conflicts"):
        merge_or_abort(git_repo, wt.branch)
    status = _git(git_repo, "status", "--porcelain")
    assert status.stdout == ""
    assert (git_repo / "README").read_text(encoding="utf-8") == "human\n"
    remove(wt, force=True)
