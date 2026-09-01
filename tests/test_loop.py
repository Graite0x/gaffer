from goloops.loop import LoopResult, ModelTurn, ToolCall, ToolError, run_loop


class Scripted:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = list(turns)

    def __call__(self, messages: list[dict]) -> ModelTurn:
        return self.turns.pop(0)


class Echo:
    def execute(self, name: str, args: dict) -> str:
        if name == "boom":
            raise ToolError("boom")
        return f"{name}:{args.get('x', '')}"


def test_loop_ends_when_model_stops_asking() -> None:
    ask = Scripted(
        [
            ModelTurn(tool_calls=[ToolCall("1", "echo", {"x": "hi"})]),
            ModelTurn(text="done"),
        ]
    )
    messages: list[dict] = [{"role": "user", "content": "go"}]
    result = run_loop(ask, Echo(), messages, max_iterations=10)
    assert result.reply == "done"
    assert result.iterations == 2
    assert result.hit_limit is False
    assert result.tool_calls[0]["output"] == "echo:hi"


def test_loop_hits_iteration_cap() -> None:
    ask = Scripted(
        [ModelTurn(tool_calls=[ToolCall(str(i), "echo", {"x": i})]) for i in range(5)]
    )
    result = run_loop(ask, Echo(), [{"role": "user", "content": "go"}], max_iterations=3)
    assert result.hit_limit is True
    assert result.iterations == 3


def test_tool_error_is_not_swallowed() -> None:
    ask = Scripted([ModelTurn(tool_calls=[ToolCall("1", "boom", {})])])
    try:
        run_loop(ask, Echo(), [{"role": "user", "content": "go"}])
    except ToolError:
        return
    raise AssertionError("expected ToolError")


def test_result_type() -> None:
    assert LoopResult(reply="").reply == ""
