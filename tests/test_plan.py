from gaffer.dag import waves
from gaffer.graph import from_markdown, dump_markdown
from gaffer.plan import (
    explain,
    parse,
    prompt,
    renumber,
    review,
    scaffold,
    to_json,
)


def test_prompt_states_the_rules_that_matter():
    text = prompt("add rate limiting", repo="/tmp/x", gate="pytest -q")
    assert "add rate limiting" in text
    assert "/tmp/x" in text
    assert "pytest -q" in text
    assert "A gate that cannot fail is not a gate." in text
    assert "JSON" in text


def test_parse_reads_a_fenced_answer():
    raw = 'sure, here:\n```json\n[{"id":"A","title":"do it","command":"x","gate":["y"]}]\n```\nhope that helps'
    nodes = parse(raw)
    assert [n.id for n in nodes] == ["A"]
    assert nodes[0].command == "x"
    assert nodes[0].gate == ("y",)


def test_parse_reads_a_bare_array_and_a_nodes_object():
    assert len(parse('[{"id":"A","title":"a"}]')) == 1
    assert len(parse('{"nodes":[{"id":"A","title":"a"},{"id":"B","title":"b"}]}')) == 2


def test_parse_rejects_junk():
    for bad in ("no json here", "[]", '[{"title":"no id"}]'):
        try:
            parse(bad)
        except ValueError:
            continue
        raise AssertionError(f"should have rejected: {bad}")


def test_review_catches_a_cycle():
    nodes = parse(
        '[{"id":"A","depends_on":["B"],"command":"x","gate":["y"]},'
        ' {"id":"B","depends_on":["A"],"command":"x","gate":["y"]}]'
    )
    errors, _ = review(nodes)
    assert any("cycle" in e for e in errors)


def test_review_catches_work_that_skips_foundational():
    nodes = parse(
        '[{"id":"A","phase":"setup","command":"x","gate":["y"]},'
        ' {"id":"B","depends_on":["A"],"phase":"foundational","command":"x","gate":["y"]},'
        ' {"id":"C","depends_on":["A"],"phase":"work","command":"x","gate":["y"]}]'
    )
    errors, _ = review(nodes)
    assert any("does not wait for foundational" in e for e in errors)


def test_review_catches_parallel_depending_on_parallel():
    nodes = parse(
        '[{"id":"A","parallel":true,"command":"x","gate":["y"]},'
        ' {"id":"B","depends_on":["A"],"parallel":true,"command":"x","gate":["y"]}]'
    )
    errors, _ = review(nodes)
    assert any("marked [P] but depends on [P]" in e for e in errors)


def test_review_passes_a_sane_plan():
    nodes = parse(
        '[{"id":"A","phase":"setup","command":"x","gate":["y"]},'
        ' {"id":"B","depends_on":["A"],"phase":"foundational","command":"x","gate":["y"]},'
        ' {"id":"C","depends_on":["B"],"parallel":true,"phase":"work","command":"x","gate":["y"]},'
        ' {"id":"D","depends_on":["B"],"parallel":true,"phase":"work","command":"x","gate":["y"]}]'
    )
    errors, warnings = review(nodes)
    assert errors == []
    assert warnings == []


def test_missing_command_and_gate_are_warnings_not_errors():
    """A scaffold is unfinished on purpose. It must still be writable."""
    errors, warnings = review(scaffold("ship it"))
    assert errors == []
    assert any("no command" in w for w in warnings)


def test_scaffold_follows_the_phase_order():
    nodes = scaffold("ship it", fanout=3, gate="pytest -q")
    phases = [n.extra.get("phase") for n in nodes]
    assert phases[0] == "setup"
    assert phases[1] == "foundational"
    assert phases.count("work") == 3
    assert phases[-1] == "polish"
    assert all(n.gate == ("pytest -q",) for n in nodes)
    # the three work nodes share one wave, so four waves in total
    assert len(waves(nodes)) == 4


def test_scaffold_fanout_is_clamped():
    assert len([n for n in scaffold("x", fanout=99) if n.parallel]) == 8
    assert len([n for n in scaffold("x", fanout=0) if n.parallel]) == 1


def test_renumber_walks_in_wave_order_and_keeps_edges():
    nodes = parse(
        '[{"id":"zeta","depends_on":["alpha"],"command":"x","gate":["y"]},'
        ' {"id":"alpha","command":"x","gate":["y"]}]'
    )
    out = renumber(nodes)
    assert [n.id for n in out] == ["T001", "T002"]
    assert out[0].title == "alpha"
    assert out[1].depends_on == ("T001",)


def test_plan_round_trips_through_the_markdown_the_runner_reads():
    """The whole point: a plan becomes a graph gaffer already knows how to walk."""
    nodes = scaffold("ship it", fanout=2)
    reloaded = from_markdown(dump_markdown(nodes))
    assert [n.id for n in reloaded] == [n.id for n in nodes]
    assert [n.depends_on for n in reloaded] == [n.depends_on for n in nodes]
    assert [n.parallel for n in reloaded] == [n.parallel for n in nodes]


def test_to_json_is_parseable_again():
    nodes = scaffold("ship it", fanout=2, gate="pytest -q")
    assert [n.id for n in parse(to_json(nodes))] == [n.id for n in nodes]


def test_explain_groups_by_phase_and_counts_waves():
    text = explain(scaffold("ship it", fanout=2))
    for phase in ("setup:", "foundational:", "work:", "polish:"):
        assert phase in text
    assert "5 nodes, 4 waves" in text
