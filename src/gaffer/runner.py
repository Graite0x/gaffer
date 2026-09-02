"""Walk the graph. Each node is a loop in its own worktree, then a gate.

Fan-out is concurrent. Merge is serial. A failed gate never merges.
"""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from gaffer.beads import reopen as beads_reopen
from gaffer.dag import Node, waves
from gaffer.gate import RunState, promote, run_gate, unfinish
from gaffer.worktree import MergeAborted, Worktree, create, merge_or_abort, remove


@dataclass
class NodeResult:
    node_id: str
    ok: bool
    detail: str
    worktree: Worktree | None = None


@dataclass
class RunReport:
    results: list[NodeResult]
    waves: list[frozenset[str]]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)


def default_command(node: Node, template: str | None) -> str:
    if node.command:
        return node.command
    if template:
        return template.format(
            id=node.id,
            title=node.title,
            role=node.role or "",
        )
    return ""


def run_node_command(cwd: Path, command: str, env: dict[str, str] | None = None) -> NodeResult:
    if not command:
        return NodeResult("", False, "node has no command")
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        capture_output=True,
        env=merged,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0
    return NodeResult("", ok, output[-4000:] if output else f"exit {proc.returncode}")


def run_graph(
    nodes: list[Node],
    repo: Path,
    state: RunState,
    *,
    command_template: str | None = None,
    worktree_root: Path | None = None,
    max_parallel: int = 3,
    keep_worktrees: bool = False,
    execute=None,
) -> RunReport:
    """execute(node, wt) -> NodeResult overrides the default shell command."""
    repo = repo.resolve()
    worktree_root = (worktree_root or repo / ".gaffer" / "worktrees").resolve()
    index = {n.id: n for n in nodes}
    schedule = waves(nodes)
    results: list[NodeResult] = []
    succeeded = {n.id for n in nodes if n.done} | set(state.done)

    for wave in schedule:
        batch: list[Node] = []
        for nid in sorted(wave):
            node = index[nid]
            blocked = [dep for dep in node.depends_on if dep not in succeeded]
            if blocked:
                results.append(
                    NodeResult(
                        nid,
                        False,
                        "blocked by " + ", ".join(blocked),
                    )
                )
                continue
            batch.append(node)
        if not batch:
            continue
        executed = _run_wave(
            batch,
            repo,
            state,
            command_template,
            worktree_root,
            max_parallel,
            execute,
        )
        for result in executed:
            if result.ok and result.worktree is not None:
                result = _merge_one(result, repo, state)
            if result.ok:
                succeeded.add(result.node_id)
            results.append(result)
            if result.worktree is not None and not keep_worktrees:
                remove(result.worktree, force=True)
    results.sort(key=lambda r: r.node_id)
    return RunReport(results=results, waves=schedule)


def _run_wave(
    batch: list[Node],
    repo: Path,
    state: RunState,
    command_template: str | None,
    worktree_root: Path,
    max_parallel: int,
    execute,
) -> list[NodeResult]:
    if len(batch) == 1:
        return [
            _execute_one(
                batch[0], repo, state, command_template, worktree_root, execute
            )
        ]
    workers = min(max_parallel, len(batch))
    out: list[NodeResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                _execute_one,
                node,
                repo,
                state,
                command_template,
                worktree_root,
                execute,
            ): node.id
            for node in batch
        }
        for fut in as_completed(futs):
            out.append(fut.result())
    out.sort(key=lambda r: r.node_id)
    return out


def _execute_one(
    node: Node,
    repo: Path,
    state: RunState,
    command_template: str | None,
    worktree_root: Path,
    execute,
) -> NodeResult:
    if node.done or node.id in state.done:
        return NodeResult(node.id, True, "already done")

    branch = f"gaffer/{node.id}".replace(" ", "-")
    path = worktree_root / node.id
    try:
        wt = create(repo, branch, path)
    except Exception as exc:
        unfinish(state, node.id, f"worktree failed: {exc}")
        return NodeResult(node.id, False, str(exc))

    if execute is not None:
        result = execute(node, wt)
    else:
        command = default_command(node, command_template)
        result = run_node_command(
            wt.path,
            command,
            env={"GAFFER_NODE": node.id, "GAFFER_ROLE": node.role or ""},
        )
    result.node_id = node.id
    result.worktree = wt

    if not result.ok:
        unfinish(state, node.id, result.detail[-500:])
        beads_reopen(repo, node.id, result.detail[-200:])
        return result

    gate = run_gate(wt.path, node.gate)
    if not gate.ok:
        detail = f"gate failed: {gate.command}\n{gate.output[-1500:]}"
        unfinish(state, node.id, detail)
        beads_reopen(repo, node.id, "gate failed")
        return NodeResult(node.id, False, detail, wt)
    return result


def _merge_one(result: NodeResult, repo: Path, state: RunState) -> NodeResult:
    assert result.worktree is not None
    try:
        merge_or_abort(repo, result.worktree.branch)
    except MergeAborted as exc:
        unfinish(state, result.node_id, str(exc))
        beads_reopen(repo, result.node_id, str(exc))
        return NodeResult(result.node_id, False, str(exc), result.worktree)
    promote(state, result.node_id, "merged")
    return NodeResult(result.node_id, True, "merged", result.worktree)
