"""Load a graph from JSON or a bernstein-style markdown checklist."""

from __future__ import annotations

import json
import re
from pathlib import Path

from gaffer.dag import Node

_ITEM = re.compile(
    r"""
    ^\s*-\s+
    \[
      (?P<mark>[ xX]|P)
    \]
    \s*
    \[
      (?P<id>[A-Za-z0-9._-]+)
    \]
    \s+
    (?P<title>.+?)
    (?:
        \s*->\s*
        (?P<deps>.+?)
    )?
    \s*$
    """,
    re.VERBOSE,
)


def load(path: str | Path) -> list[Node]:
    raw = Path(path).read_text(encoding="utf-8")
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return from_json(raw)
    return from_markdown(raw)


def from_json(raw: str) -> list[Node]:
    data = json.loads(raw)
    items = data["nodes"] if isinstance(data, dict) and "nodes" in data else data
    if not isinstance(items, list):
        raise ValueError("graph JSON must be a list or {\"nodes\": [...]}")
    return [_node_from_dict(item) for item in items]


def from_markdown(raw: str) -> list[Node]:
    nodes: list[Node] = []
    for line in raw.splitlines():
        if line.strip().startswith("#") or not line.strip():
            continue
        match = _ITEM.match(line)
        if not match:
            continue
        mark = match.group("mark")
        deps_raw = match.group("deps") or ""
        deps = tuple(
            part.strip()
            for part in re.split(r"[,\s]+", deps_raw)
            if part.strip()
        )
        nodes.append(
            Node(
                id=match.group("id"),
                title=match.group("title").strip(),
                depends_on=deps,
                parallel=mark == "P",
                done=mark.lower() == "x",
            )
        )
    if not nodes:
        raise ValueError("no checklist nodes found")
    return nodes


def _node_from_dict(item: object) -> Node:
    if not isinstance(item, dict):
        raise ValueError("each node must be an object")
    nid = str(item["id"])
    title = str(item.get("title") or nid)
    deps = item.get("depends_on") or item.get("deps") or []
    if isinstance(deps, str):
        dep_tuple = tuple(part.strip() for part in re.split(r"[,\s]+", deps) if part.strip())
    else:
        dep_tuple = tuple(str(d) for d in deps)
    gate = item.get("gate") or []
    if isinstance(gate, str):
        gate_tuple = (gate,)
    else:
        gate_tuple = tuple(str(g) for g in gate)
    extra = {
        str(k): str(v)
        for k, v in item.items()
        if k
        not in {
            "id",
            "title",
            "depends_on",
            "deps",
            "parallel",
            "role",
            "command",
            "gate",
            "done",
        }
        and v is not None
        and not isinstance(v, (dict, list))
    }
    return Node(
        id=nid,
        title=title,
        depends_on=dep_tuple,
        parallel=bool(item.get("parallel")),
        role=str(item["role"]) if item.get("role") else None,
        command=str(item["command"]) if item.get("command") else None,
        gate=gate_tuple,
        done=bool(item.get("done")),
        extra=extra,
    )


def dump_markdown(nodes: list[Node]) -> str:
    lines = ["# Graph", ""]
    for node in nodes:
        mark = "x" if node.done else ("P" if node.parallel else " ")
        line = f"- [{mark}] [{node.id}] {node.title}"
        if node.depends_on:
            line += " -> " + " ".join(node.depends_on)
        lines.append(line)
    lines.append("")
    return "\n".join(lines)
