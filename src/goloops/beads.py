"""Optional memory. Shells out to `bd` when it is on PATH.

If beads is missing we degrade to the on-disk RunState. Cloud-synced
`.beads/` directories (iCloud, Dropbox) are a known trap — doctor flags them.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def available() -> bool:
    return shutil.which("bd") is not None


def ready(cwd: Path, limit: int = 20) -> str:
    return _bd(cwd, "ready", f"--limit={limit}")


def remember(cwd: Path, insight: str) -> str:
    return _bd(cwd, "remember", insight)


def prime(cwd: Path) -> str:
    return _bd(cwd, "prime")


def reopen(cwd: Path, issue_id: str, reason: str) -> str:
    """Take done back in beads, if beads is installed."""
    if not available():
        return ""
    # Prefer explicit reopen; fall back to update --status open.
    out = _bd(cwd, "reopen", issue_id, "--reason", reason, check=False)
    if out is not None:
        return out
    return _bd(cwd, "update", issue_id, "--status", "open") or ""


def _bd(cwd: Path, *args: str, check: bool = True) -> str | None:
    if not available():
        return "" if check else None
    proc = subprocess.run(
        ["bd", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        if check:
            return (proc.stdout or "") + (proc.stderr or "")
        return None
    return proc.stdout or ""
