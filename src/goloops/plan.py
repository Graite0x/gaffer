"""Turn one line of intent into a graph the scheduler can walk.

The model proposes. The code accepts or rejects. Same contract as the gate:
nothing enters the graph that `waves()` cannot walk, and a plan that fails
review is not written to disk.

Two upstreams, both MIT, both credited in NOTICE:

  · github/spec-kit  — the phase order and the task line format.
    Setup -> Foundational (blocking) -> work in priority order -> Polish,
    written as `- [ ] [T001] Title`, with `[P]` marking "different files,
    no dependencies, safe to run at the same time". goloops already parsed
    that line, so a tasks.md from spec-kit runs here without a converter.

  · ObedienceAdara/supervisor — the planner shape: ask the model for
    structured JSON rather than prose to scrape, keep no fixed task count,
    and fall back to a deterministic template when no model is available.

What is deliberately not here: this module never calls an API. It prints a
prompt for the agent you already pay for, and it reads the answer back.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace

from goloops.dag import CycleError, Node, detect_cycle, waves

# spec-kit phase order. Foundational blocks everything after it.
PHASES = ("setup", "foundational", "work", "polish")

_FENCE = re.compile(r"```(?:json)?\s*(?P<body>[\[{].*?[\]}])\s*```", re.S)
_BARE = re.compile(r"(?P<body>[\[{].*[\]}])", re.S)


def prompt(idea: str, *, repo: str | None = None, gate: str | None = None) -> str:
    """The text you hand to Claude Code, Codex or any agent that can read.

    Asks for JSON, not markdown: structured output is cheaper to validate
    than hoping a model reproduces a heading byte for byte.
    """
    where = f"\nRepository: {repo}" if repo else ""
    check = gate or "the project's own test command"
    return f"""Break this down into an ordered task graph.

Goal: {idea}{where}

Return ONLY a JSON array. No prose, no fences. Each element:

  {{"id": "T001",
    "title": "what to do, with the file path",
    "depends_on": ["T000"],
    "parallel": false,
    "phase": "setup|foundational|work|polish",
    "command": "shell command that performs this task",
    "gate": ["shell command that proves it worked"]}}

Rules:
- Order by phase: setup, then foundational, then work, then polish.
  Foundational blocks every later task — nothing in work may start until it lands.
- Mark "parallel": true ONLY when the task touches different files from its
  siblings in the same wave and shares no dependency with them.
- Every task needs a gate that exits non-zero on failure. Use {check}.
  A gate that cannot fail is not a gate.
- As many tasks as the work actually needs. Do not pad to a round number.
- ids are T001, T002, ... in dependency order.
"""


def parse(raw: str) -> list[Node]:
    """Read a plan back from a model's answer, fenced or bare."""
    match = _FENCE.search(raw) or _BARE.search(raw)
    if not match:
        raise ValueError("no JSON found in the answer")
    data = json.loads(match.group("body"))
    items = data["nodes"] if isinstance(data, dict) and "nodes" in data else data
    if not isinstance(items, list) or not items:
        raise ValueError("plan must be a non-empty JSON array")

    nodes: list[Node] = []
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError("each task must be an object with an id")
        deps = item.get("depends_on") or item.get("deps") or []
        if isinstance(deps, str):
            deps = [p for p in re.split(r"[,\s]+", deps) if p]
        gate = item.get("gate") or []
        if isinstance(gate, str):
            gate = [gate]
        phase = str(item.get("phase") or "").strip().lower()
        nodes.append(
            Node(
                id=str(item["id"]),
                title=str(item.get("title") or item["id"]),
                depends_on=tuple(str(d) for d in deps),
                parallel=bool(item.get("parallel")),
                role=str(item["role"]) if item.get("role") else None,
                command=str(item["command"]) if item.get("command") else None,
                gate=tuple(str(g) for g in gate),
                extra={"phase": phase} if phase in PHASES else {},
            )
        )
    return nodes


def review(nodes: list[Node]) -> tuple[list[str], list[str]]:
    """(errors, warnings).

    Errors are structural: the scheduler cannot walk this, so it is not written.
    Warnings are about an unfinished plan — a scaffold has no commands yet and
    that is the point of a scaffold.

    A model is allowed to be wrong here. It is not allowed to be wrong past here.
    """
    problems: list[str] = []
    warnings: list[str] = []
    if not nodes:
        return ["plan is empty"], []

    try:
        waves(nodes)
    except CycleError as exc:
        problems.append(str(exc))

    ungated = [n.id for n in nodes if not n.gate]
    if ungated:
        warnings.append("no gate, cannot be proved done: " + ", ".join(sorted(ungated)))

    nocmd = [n.id for n in nodes if not n.command]
    if nocmd:
        warnings.append("no command, nothing to run: " + ", ".join(sorted(nocmd)))

    roots = [n.id for n in nodes if not n.depends_on]
    if not roots:
        problems.append("every task depends on another; nothing can start")

    # spec-kit: foundational blocks the phases after it
    index = {n.id: n for n in nodes}
    found = {n.id for n in nodes if n.extra.get("phase") == "foundational"}
    if found:
        for node in nodes:
            if node.extra.get("phase") in ("work", "polish"):
                if not _reaches(node, found, index):
                    problems.append(
                        f"{node.id} is {node.extra['phase']} but does not wait for foundational"
                    )

    # a parallel node that depends on its own wave-mate is not parallel
    for node in nodes:
        if node.parallel:
            for dep in node.depends_on:
                sib = index.get(dep)
                if sib is not None and sib.parallel:
                    problems.append(f"{node.id} is marked [P] but depends on [P] {dep}")
    return problems, warnings


def _reaches(node: Node, targets: set[str], index: dict[str, Node]) -> bool:
    seen: set[str] = set()
    stack = list(node.depends_on)
    while stack:
        nid = stack.pop()
        if nid in targets:
            return True
        if nid in seen:
            continue
        seen.add(nid)
        dep = index.get(nid)
        if dep is not None:
            stack.extend(dep.depends_on)
    return False


def scaffold(idea: str, *, fanout: int = 2, gate: str | None = None) -> list[Node]:
    """A plan with no model in it, in spec-kit's phase order.

    Not a guess at your work — a shape to edit. `doctor` has nothing to say
    about it and neither should you until you have replaced the titles.
    """
    fanout = max(1, min(fanout, 8))
    check = (gate,) if gate else ()
    nodes = [
        Node(
            id="T001",
            title=f"Setup: scaffold for {idea}",
            gate=check,
            extra={"phase": "setup"},
        ),
        Node(
            id="T002",
            title="Foundational: the piece every later task needs",
            depends_on=("T001",),
            gate=check,
            extra={"phase": "foundational"},
        ),
    ]
    work = []
    for i in range(fanout):
        nid = f"T{3 + i:03d}"
        work.append(nid)
        nodes.append(
            Node(
                id=nid,
                title=f"Work {chr(65 + i)}: independent slice, own files",
                depends_on=("T002",),
                parallel=True,
                gate=check,
                extra={"phase": "work"},
            )
        )
    nodes.append(
        Node(
            id=f"T{3 + fanout:03d}",
            title="Polish: integrate and prove the whole thing",
            depends_on=tuple(work),
            gate=check,
            extra={"phase": "polish"},
        )
    )
    return nodes


def to_json(nodes: list[Node]) -> str:
    out = []
    for node in nodes:
        item: dict[str, object] = {"id": node.id, "title": node.title}
        if node.depends_on:
            item["depends_on"] = list(node.depends_on)
        if node.parallel:
            item["parallel"] = True
        if node.role:
            item["role"] = node.role
        if node.command:
            item["command"] = node.command
        if node.gate:
            item["gate"] = list(node.gate)
        phase = node.extra.get("phase")
        if phase:
            item["phase"] = phase
        out.append(item)
    return json.dumps({"nodes": out}, indent=2) + "\n"


def explain(nodes: list[Node]) -> str:
    """The schedule in phases, so you can argue with it before it runs."""
    lines = []
    for phase in PHASES:
        members = [n for n in nodes if n.extra.get("phase") == phase]
        if not members:
            continue
        lines.append(f"{phase}:")
        for node in members:
            mark = "[P]" if node.parallel else "   "
            dep = (" -> " + " ".join(node.depends_on)) if node.depends_on else ""
            lines.append(f"  {mark} {node.id}  {node.title}{dep}")
    unphased = [n for n in nodes if n.extra.get("phase") not in PHASES]
    if unphased:
        lines.append("unphased:")
        for node in unphased:
            mark = "[P]" if node.parallel else "   "
            lines.append(f"  {mark} {node.id}  {node.title}")
    plan_waves = waves(nodes)
    lines.append("")
    lines.append(f"{len(nodes)} nodes, {len(plan_waves)} waves")
    return "\n".join(lines)


def renumber(nodes: list[Node]) -> list[Node]:
    """Give the plan T001.. ids in wave order, keeping dependencies intact."""
    order: list[str] = []
    for wave in waves(nodes):
        order.extend(sorted(wave))
    mapping = {old: f"T{i:03d}" for i, old in enumerate(order, start=1)}
    index = {n.id: n for n in nodes}
    return [
        replace(
            index[old],
            id=mapping[old],
            depends_on=tuple(mapping[d] for d in index[old].depends_on),
        )
        for old in order
    ]
