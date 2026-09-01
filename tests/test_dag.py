from goloops.dag import CycleError, Node, detect_cycle, waves


def n(nid: str, *deps: str, parallel: bool = False, done: bool = False) -> Node:
    return Node(id=nid, title=nid, depends_on=deps, parallel=parallel, done=done)


def test_serial_waves_are_singletons() -> None:
    schedule = waves([n("A"), n("B", "A"), n("C", "B")])
    assert schedule == [frozenset({"A"}), frozenset({"B"}), frozenset({"C"})]


def test_parallel_ready_nodes_share_a_wave() -> None:
    schedule = waves(
        [n("A"), n("B", "A", parallel=True), n("C", "A", parallel=True), n("D", "B", "C")]
    )
    assert schedule[0] == frozenset({"A"})
    assert schedule[1] == frozenset({"B", "C"})
    assert schedule[2] == frozenset({"D"})


def test_cycle_is_a_hard_error() -> None:
    nodes = [n("A", "B"), n("B", "A")]
    assert detect_cycle(nodes) is not None
    try:
        waves(nodes)
    except CycleError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("expected CycleError")


def test_missing_dep_is_a_hard_error() -> None:
    try:
        waves([n("A", "ghost")])
    except CycleError as exc:
        assert "ghost" in str(exc)
    else:
        raise AssertionError("expected CycleError")


def test_duplicate_id_is_a_hard_error() -> None:
    try:
        waves([n("A"), n("A")])
    except CycleError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected CycleError")


def test_already_done_nodes_are_skipped() -> None:
    schedule = waves([n("A", done=True), n("B", "A")])
    assert schedule == [frozenset({"B"})]


def test_serial_and_parallel_ready_do_not_share_a_wave() -> None:
    schedule = waves([n("P", parallel=True), n("S")])
    assert schedule[0] == frozenset({"P"})
    assert schedule[1] == frozenset({"S"})
