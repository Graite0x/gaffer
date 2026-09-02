"""Per-node git worktree. Merge only if a dry-run applies cleanly.

If it would not apply, abort with 'Merge aborted due to conflicts' and
leave the repo unmerged. Same safety contract as agent-worktree; we
shell out to `wt` when it is on PATH, otherwise raw git.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class MergeAborted(RuntimeError):
    """Dry-run merge found conflicts. Repo is not left half-merged."""


@dataclass(frozen=True)
class Worktree:
    repo: Path
    path: Path
    branch: str
    base: str


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        text=True,
        capture_output=True,
    )


def git_available() -> bool:
    return shutil.which("git") is not None


def wt_available() -> bool:
    return shutil.which("wt") is not None


def create(
    repo: Path,
    branch: str,
    path: Path,
    base: str = "HEAD",
) -> Worktree:
    repo = repo.resolve()
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", branch, str(path), base)
    return Worktree(repo=repo, path=path, branch=branch, base=base)


def remove(wt: Worktree, *, force: bool = False) -> None:
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(wt.path))
    _git(wt.repo, *args, check=False)
    _git(wt.repo, "branch", "-D", wt.branch, check=False)


def merge_or_abort(repo: Path, source: str, target: str | None = None) -> None:
    """Dry-run, then merge. On conflict: abort and restore HEAD."""
    repo = repo.resolve()
    if target is None:
        target = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    original = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if original != target:
        _git(repo, "checkout", target)

    dry = _git(repo, "merge", "--no-ff", "--no-commit", source, check=False)
    if dry.returncode != 0:
        _git(repo, "merge", "--abort", check=False)
        if original != target:
            _git(repo, "checkout", original, check=False)
        raise MergeAborted("Merge aborted due to conflicts")

    # Dry-run applied. Drop it and do the real merge so we never sit mid-merge.
    _git(repo, "merge", "--abort", check=False)
    real = _git(repo, "merge", "--no-ff", "--no-edit", source, check=False)
    if real.returncode != 0:
        _git(repo, "merge", "--abort", check=False)
        if original != target:
            _git(repo, "checkout", original, check=False)
        raise MergeAborted("Merge aborted due to conflicts")
    if original != target:
        _git(repo, "checkout", original, check=False)
