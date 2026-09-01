"""Deterministic DAG walk. No model in the coordination loop.

Ready nodes marked parallel batch into one frozenset. The rest run
one at a time. Cycle detection is a hard error, not a retry.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class CycleError(ValueError):
    """Graph has a cycle or a missing dependency."""


@dataclass(frozen=True)
class Node:
    id: str
    title: str
    depends_on: tuple[str, ...] = ()
    parallel: bool = False
    role: str | None = None
    command: str | None = None
    gate: tuple[str, ...] = ()
    done: bool = False
    extra: dict[str, str] = field(default_factory=dict, hash=False)


def _index(nodes: list[Node]) -> dict[str, Node]:
    seen: dict[str, Node] = {}
    for node in nodes:
        if node.id in seen:
            raise CycleError(f"duplicate node id: {node.id}")
        seen[node.id] = node
    for node in nodes:
        for dep in node.depends_on:
            if dep not in seen:
                raise CycleError(f"{node.id} depends on missing node {dep}")
    return seen


def detect_cycle(nodes: list[Node]) -> list[str] | None:
    """Return one cycle path (ids) or None."""
    index = _index(nodes)
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def walk(nid: str) -> list[str] | None:
        if nid in visited:
            return None
        if nid in visiting:
            start = stack.index(nid)
            return stack[start:] + [nid]
        visiting.add(nid)
        stack.append(nid)
        for dep in index[nid].depends_on:
            hit = walk(dep)
            if hit:
                return hit
        stack.pop()
        visiting.remove(nid)
        visited.add(nid)
        return None

    for nid in index:
        hit = walk(nid)
        if hit:
            return hit
    return None


def waves(nodes: list[Node]) -> list[frozenset[str]]:
    """Topological waves. Parallel-ready nodes share a wave; serial ones do not."""
    cycle = detect_cycle(nodes)
    if cycle:
        raise CycleError("cycle: " + " -> ".join(cycle))

    remaining = {n.id: n for n in nodes if not n.done}
    done = {n.id for n in nodes if n.done}
    out: list[frozenset[str]] = []

    while remaining:
        ready = [
            n
            for n in remaining.values()
            if all(dep in done for dep in n.depends_on)
        ]
        if not ready:
            raise CycleError(
                "no ready nodes; blocked: " + ", ".join(sorted(remaining))
            )
        parallel = [n for n in ready if n.parallel]
        if parallel:
            batch = frozenset(n.id for n in parallel)
            out.append(batch)
            for n in parallel:
                del remaining[n.id]
                done.add(n.id)
            continue
        nxt = sorted(ready, key=lambda n: n.id)[0]
        out.append(frozenset({nxt.id}))
        del remaining[nxt.id]
        done.add(nxt.id)
    return out
