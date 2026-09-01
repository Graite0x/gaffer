from pathlib import Path

from goloops.dag import Node
from goloops.gate import RunState
from goloops.runner import NodeResult, run_graph
from goloops.worktree import Worktree


def _commit(wt: Worktree, name: str) -> NodeResult:
    path = wt.path / f"{name}.txt"
    path.write_text(name + "\n", encoding="utf-8")
    import subprocess

    subprocess.run(["git", "add", path.name], cwd=wt.path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", name], cwd=wt.path, check=True, capture_output=True
    )
    return NodeResult(name, True, "committed", wt)


def test_gate_failure_does_not_merge(git_repo: Path) -> None:
    nodes = [
        Node(
            id="T001",
            title="fail gate",
            gate=("false",),
        )
    ]
    state = RunState.load(git_repo / ".goloops" / "state.json")

    def execute(node: Node, wt: Worktree) -> NodeResult:
        return _commit(wt, node.id)

    report = run_graph(nodes, git_repo, state, execute=execute)
    assert report.ok is False
    assert "T001" in state.failed
    assert not (git_repo / "T001.txt").exists()


def test_green_node_merges_and_can_be_taken_back(git_repo: Path) -> None:
    nodes = [Node(id="T001", title="ok", gate=("test -f T001.txt",))]
    state = RunState.load(git_repo / ".goloops" / "state.json")

    def execute(node: Node, wt: Worktree) -> NodeResult:
        return _commit(wt, node.id)

    report = run_graph(nodes, git_repo, state, execute=execute)
    assert report.ok is True
    assert (git_repo / "T001.txt").read_text(encoding="utf-8") == "T001\n"
    assert "T001" in state.done
    from goloops.gate import unfinish

    unfinish(state, "T001", "review said no")
    assert "T001" not in state.done


def test_failed_node_blocks_dependents(git_repo: Path) -> None:
    seen: list[str] = []
    nodes = [
        Node(id="A", title="A", gate=("false",)),
        Node(id="B", title="B", depends_on=("A",)),
    ]
    state = RunState.load(git_repo / ".goloops" / "state.json")

    def execute(node: Node, wt: Worktree) -> NodeResult:
        seen.append(node.id)
        return _commit(wt, node.id)

    report = run_graph(nodes, git_repo, state, execute=execute)
    assert report.ok is False
    assert seen == ["A"]
    assert [r.node_id for r in report.results] == ["A", "B"]
    assert "blocked by A" in report.results[1].detail
    assert not (git_repo / "A.txt").exists()


def test_dependency_order(git_repo: Path) -> None:
    seen: list[str] = []
    nodes = [
        Node(id="A", title="A"),
        Node(id="B", title="B", depends_on=("A",)),
    ]
    state = RunState.load(git_repo / ".goloops" / "state.json")

    def execute(node: Node, wt: Worktree) -> NodeResult:
        seen.append(node.id)
        return _commit(wt, node.id)

    report = run_graph(nodes, git_repo, state, execute=execute)
    assert report.ok is True
    assert seen == ["A", "B"]
    assert (git_repo / "B.txt").exists()
