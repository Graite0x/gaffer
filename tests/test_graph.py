from pathlib import Path

from goloops.graph import dump_markdown, from_json, from_markdown, load


def test_markdown_checklist() -> None:
    nodes = from_markdown(
        """
# Graph
- [ ] [T001] Scaffold
- [P] [T002] Wire -> T001
- [x] [T003] Already -> T001
"""
    )
    assert [n.id for n in nodes] == ["T001", "T002", "T003"]
    assert nodes[1].parallel is True
    assert nodes[1].depends_on == ("T001",)
    assert nodes[2].done is True


def test_json_nodes() -> None:
    nodes = from_json(
        """
        {"nodes": [
          {"id": "T001", "title": "A", "gate": "npm test"},
          {"id": "T002", "depends_on": ["T001"], "parallel": true, "role": "review"}
        ]}
        """
    )
    assert nodes[0].gate == ("npm test",)
    assert nodes[1].depends_on == ("T001",)
    assert nodes[1].role == "review"


def test_load_json_file(tmp_path: Path) -> None:
    path = tmp_path / "graph.json"
    path.write_text('[{"id": "A", "title": "one"}]', encoding="utf-8")
    assert load(path)[0].id == "A"


def test_roundtrip_markdown() -> None:
    nodes = from_markdown("- [P] [T002] Wire -> T001 T000\n- [ ] [T001] First\n")
    text = dump_markdown(nodes)
    again = from_markdown(text)
    assert [(n.id, n.parallel, n.depends_on) for n in again] == [
        (n.id, n.parallel, n.depends_on) for n in nodes
    ]
