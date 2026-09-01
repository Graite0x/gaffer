"""goloops — graph on top, loop underneath."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from goloops import __version__
from goloops.dag import CycleError, waves
from goloops.doctor import format_report, inspect
from goloops.gate import RunState, unfinish
from goloops.graph import load
from goloops.runner import run_graph

DEFAULT_GRAPH_NAMES = ("graph.md", "graph.json", ".goloops/graph.md", ".goloops/graph.json")
STATE_NAME = ".goloops/state.json"

EXAMPLE_GRAPH = """# Graph of loops
# [ ] serial   [P] parallel wave   [x] already done
# deps after ->

- [ ] [T001] First node writes a file
- [P] [T002] Parallel sibling A -> T001
- [P] [T003] Parallel sibling B -> T001
- [ ] [T004] Merge point -> T002 T003
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="goloops",
        description="Schedule a fleet. Run each node as a loop. Take done back.",
    )
    parser.add_argument("--version", action="version", version=f"goloops {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="write graph.md and .goloops/")
    p_init.add_argument("root", nargs="?", default=".")

    p_doc = sub.add_parser("doctor", help="G1–G4 / L1–L6 inventory")
    p_doc.add_argument("root", nargs="?", default=".")

    p_waves = sub.add_parser("waves", help="print the schedule, do not run")
    p_waves.add_argument("graph", nargs="?", default=None)

    p_run = sub.add_parser("run", help="walk the graph")
    p_run.add_argument("graph", nargs="?", default=None)
    p_run.add_argument("--cmd", dest="template", default=None, help="command template if a node has none")
    p_run.add_argument("--max-parallel", type=int, default=3)
    p_run.add_argument("--keep-worktrees", action="store_true")
    p_run.add_argument("--repo", default=".")

    p_un = sub.add_parser("unfinish", help="take done back")
    p_un.add_argument("node_id")
    p_un.add_argument("--reason", default="taken back")
    p_un.add_argument("--repo", default=".")

    p_st = sub.add_parser("status", help="what's done, failed, next")
    p_st.add_argument("graph", nargs="?", default=None)
    p_st.add_argument("--repo", default=".")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            return cmd_init(Path(args.root))
        if args.cmd == "doctor":
            print(format_report(inspect(Path(args.root))), end="")
            return 0
        if args.cmd == "waves":
            return cmd_waves(_resolve_graph(args.graph))
        if args.cmd == "run":
            return cmd_run(args)
        if args.cmd == "unfinish":
            return cmd_unfinish(Path(args.repo), args.node_id, args.reason)
        if args.cmd == "status":
            return cmd_status(Path(args.repo), _find_graph(args.graph))
    except CycleError as exc:
        print(f"goloops: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"goloops: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"goloops: {exc}", file=sys.stderr)
        return 2
    return 1


def cmd_init(root: Path) -> int:
    root = root.resolve()
    goloops = root / ".goloops"
    goloops.mkdir(parents=True, exist_ok=True)
    (goloops / "roles").mkdir(exist_ok=True)
    graph = root / "graph.md"
    if not graph.exists():
        graph.write_text(EXAMPLE_GRAPH, encoding="utf-8")
    state = RunState.load(root / STATE_NAME)
    state.save()
    print(f"wrote {graph}")
    print(f"wrote {state.path}")
    print("next: goloops waves && goloops doctor")
    return 0


def cmd_waves(graph: Path) -> int:
    nodes = load(graph)
    schedule = waves(nodes)
    print(f"{len(nodes)} nodes, {len(schedule)} waves")
    for i, wave in enumerate(schedule, 1):
        kind = "parallel" if len(wave) > 1 else "serial"
        print(f"  {i}. {kind}: " + ", ".join(sorted(wave)))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    graph = _resolve_graph(args.graph)
    nodes = load(graph)
    state = RunState.load(repo / STATE_NAME)
    report = run_graph(
        nodes,
        repo,
        state,
        command_template=args.template,
        max_parallel=args.max_parallel,
        keep_worktrees=args.keep_worktrees,
    )
    for result in report.results:
        mark = "ok" if result.ok else "FAIL"
        print(f"  {mark}  {result.node_id}  {result.detail.splitlines()[0][:80]}")
    print(f"{'green' if report.ok else 'blocked'}: {sum(r.ok for r in report.results)}/{len(report.results)}")
    return 0 if report.ok else 1


def cmd_unfinish(repo: Path, node_id: str, reason: str) -> int:
    repo = repo.resolve()
    state = RunState.load(repo / STATE_NAME)
    unfinish(state, node_id, reason)
    from goloops.beads import reopen

    reopen(repo, node_id, reason)
    print(f"took back {node_id}: {reason}")
    return 0


def cmd_status(repo: Path, graph: Path | None) -> int:
    repo = repo.resolve()
    state = RunState.load(repo / STATE_NAME)
    print(f"done    {', '.join(sorted(state.done)) or '—'}")
    print(f"failed  {', '.join(sorted(state.failed)) or '—'}")
    if graph is not None:
        nodes = load(graph)
        pending = [n.id for n in nodes if n.id not in state.done and not n.done]
        print(f"next    {', '.join(pending) or '—'}")
    for nid, note in sorted(state.notes.items()):
        print(f"  {nid}: {note.splitlines()[0][:80]}")
    return 0


def _find_graph(given: str | None) -> Path | None:
    try:
        return _resolve_graph(given)
    except FileNotFoundError:
        return None


def _resolve_graph(given: str | None) -> Path:
    if given:
        path = Path(given)
        if not path.exists():
            raise FileNotFoundError(path)
        return path
    for name in DEFAULT_GRAPH_NAMES:
        path = Path(name)
        if path.exists():
            return path
    raise FileNotFoundError(
        "no graph.md / graph.json — run goloops init or pass a path"
    )


if __name__ == "__main__":
    raise SystemExit(main())
