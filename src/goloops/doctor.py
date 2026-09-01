"""One-screen inventory of the ten slots. We implement G1/G2/L2/L5.

The rest are optional CLIs or plugins. Staffing all 203 roles into
context is how you burn the window serena is supposed to protect.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from goloops import beads, worktree


@dataclass(frozen=True)
class Slot:
    id: str
    layer: str
    name: str
    status: str
    detail: str


def _which(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _cloud_beads(root: Path) -> bool:
    beads_dir = root / ".beads"
    if not beads_dir.exists():
        return False
    home = Path.home()
    suspects = [
        home / "Library" / "Mobile Documents",
        home / "Dropbox",
        home / "Library" / "CloudStorage",
    ]
    try:
        resolved = beads_dir.resolve()
    except OSError:
        return False
    return any(_is_relative_to(resolved, s) for s in suspects if s.exists())


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def inspect(root: Path | None = None) -> list[Slot]:
    root = (root or Path.cwd()).resolve()
    claude = _which("claude")
    serena = _which("serena", "serena-agent")
    wt = worktree.wt_available()
    git = worktree.git_available()
    bd = beads.available()
    plugin_dir = Path.home() / ".claude" / "plugins"
    has_superpowers = _has_name(plugin_dir, "superpowers")
    has_review = _has_name(plugin_dir, "review-loop", "claude-review-loop")
    has_research = _has_name(plugin_dir, "insane-research")
    has_workshop = bool(_which("workshop")) or (root / ".workshop").exists()
    roles = (root / ".goloops" / "roles").is_dir() or (root / ".claude" / "agents").is_dir()

    slots = [
        Slot("G1", "graph", "Orchestrate", "ours", "goloops walks the DAG. No model in the scheduler."),
        Slot(
            "G2",
            "graph",
            "Fan out in isolation",
            "ok" if git else "missing",
            "wt on PATH" if wt else ("git worktree" if git else "git not on PATH"),
        ),
        Slot(
            "G3",
            "graph",
            "Give each node a role",
            "ok" if roles else "optional",
            "roles dir present" if roles else "no .goloops/roles — install only the roles you will use",
        ),
        Slot(
            "G4",
            "graph",
            "A graph that already ships",
            "ok" if has_research else "optional",
            "insane-research plugin" if has_research else "not installed (research-shaped example, not required)",
        ),
        Slot(
            "L1",
            "loop",
            "Memory",
            _beads_status(bd, root),
            _beads_detail(bd, root),
        ),
        Slot("L2", "loop", "The loop core", "ours", "goloops.loop — ends when tools stop, cap 10."),
        Slot(
            "L3",
            "loop",
            "Context",
            "ok" if serena else "optional",
            serena or "serena not on PATH — discovery will burn whole-file reads",
        ),
        Slot(
            "L4",
            "loop",
            "Skills",
            "ok" if has_superpowers else "optional",
            "superpowers plugin" if has_superpowers else "persuasion, not a syscall — L5 is enforcement",
        ),
        Slot(
            "L5",
            "loop",
            "The gate",
            "ours",
            "goloops gate + unfinish"
            + (" · review-loop plugin" if has_review else ""),
        ),
        Slot(
            "L6",
            "loop",
            "Proof",
            "ok" if has_workshop else "optional",
            "workshop present" if has_workshop else "no eval loop — you can feel better without knowing",
        ),
    ]
    if claude:
        slots.append(
            Slot("cli", "node", "Claude Code", "ok", claude)
        )
    else:
        slots.append(
            Slot("cli", "node", "Claude Code", "optional", "claude not on PATH — set node.command")
        )
    return slots


def _has_name(root: Path, *needles: str) -> bool:
    if not root.exists():
        return False
    try:
        names = {p.name.lower() for p in root.rglob("*") if p.is_dir()}
    except OSError:
        return False
    return any(n.lower() in names for n in needles)


def _beads_status(bd: bool, root: Path) -> str:
    if _cloud_beads(root):
        return "trap"
    return "ok" if bd else "optional"


def _beads_detail(bd: bool, root: Path) -> str:
    if _cloud_beads(root):
        return "disk I/O trap: .beads/ looks cloud-synced — move it off iCloud/Dropbox"
    if bd:
        return shutil.which("bd") or "bd"
    return "bd not on PATH — RunState still takes done back"


def format_report(slots: list[Slot]) -> str:
    lines = [
        "THE GRAPH                         THE LOOP",
        "coordinate the fleet              make one node trustworthy",
        "",
    ]
    graph = [s for s in slots if s.layer == "graph"]
    loop = [s for s in slots if s.layer == "loop"]
    others = [s for s in slots if s.layer not in {"graph", "loop"}]
    width = 33
    for i in range(max(len(graph), len(loop))):
        left = _cell(graph[i], width) if i < len(graph) else " " * width
        right = _cell(loop[i], 40) if i < len(loop) else ""
        lines.append(f"{left}  {right}".rstrip())
    if others:
        lines.append("")
        for slot in others:
            lines.append(_cell(slot, 70))
    lines.append("")
    lines.append("ours = this repo. optional = call the upstream CLI/plugin.")
    lines.append("The one test: goloops unfinish <id>")
    return "\n".join(lines) + "\n"


def _cell(slot: Slot, width: int) -> str:
    mark = {
        "ours": "●",
        "ok": "●",
        "optional": "○",
        "missing": "×",
        "trap": "!",
    }.get(slot.status, "?")
    text = f"{slot.id} {mark} {slot.name}"
    return text[:width].ljust(width)
