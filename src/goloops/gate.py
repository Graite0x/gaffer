"""The only thing allowed to promote — and the thing that can take done back.

A node that fails its gate is not merged. A node already marked done can
be un-finished. A system that can only promote is a burndown chart.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class GateResult:
    ok: bool
    command: str
    output: str = ""
    returncode: int = 0


@dataclass
class RunState:
    """On-disk ledger. Code writes this, not a model."""

    path: Path
    done: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    notes: dict[str, str] = field(default_factory=dict)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "done": sorted(self.done),
            "failed": sorted(self.failed),
            "notes": self.notes,
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "RunState":
        if not path.exists():
            return cls(path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            path=path,
            done=set(data.get("done") or []),
            failed=set(data.get("failed") or []),
            notes=dict(data.get("notes") or {}),
        )


def run_gate(cwd: Path, commands: Iterable[str]) -> GateResult:
    """Run each command. First failure wins. Empty gate is a pass."""
    for command in commands:
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            env=os.environ.copy(),
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return GateResult(
                ok=False,
                command=command,
                output=output,
                returncode=proc.returncode,
            )
    return GateResult(ok=True, command=" && ".join(commands) or "(none)")


def promote(state: RunState, node_id: str, note: str = "") -> None:
    state.failed.discard(node_id)
    state.done.add(node_id)
    if note:
        state.notes[node_id] = note
    state.save()


def unfinish(state: RunState, node_id: str, reason: str = "taken back") -> None:
    """The one test: can the system take done back?"""
    state.done.discard(node_id)
    state.failed.add(node_id)
    state.notes[node_id] = reason
    state.save()
