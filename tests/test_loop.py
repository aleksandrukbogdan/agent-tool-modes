from lab.client import ScriptedClient, ToolCall, reply
from lab.loop import run_tool_loop
from lab.react import run_react
from lab.tools import execute


def test_text_tool_call_then_answer():
    client = ScriptedClient(
        [
            reply('<tool_call>\n{"name": "calculate", "arguments": {"expression": "2+2"}}\n</tool_call>'),
            reply("ANSWER: 4"),
        ]
    )
    out = run_tool_loop(client, [{"role": "user", "content": "сколько"}], execute, 4)
    assert out["pred"] == "ANSWER: 4"
    assert out["tool_calls"] == 1
    assert out["tool_errors"] == 0
    assert out["stop"] == "answer"


def test_bad_arguments_and_unknown_tool_do_not_crash():
    client = ScriptedClient(
        [
            reply("", [ToolCall("1", "calculate", "{")]),
            reply("", [ToolCall("2", "missing", "{}")]),
            reply("ANSWER: 0"),
        ]
    )
    out = run_tool_loop(client, [{"role": "user", "content": "x"}], execute, 4)
    assert out["stop"] == "answer"
    assert out["tool_errors"] == 2
    assert {item["error"] for item in out["trace"] if item["kind"] == "tool"} == {"arguments_json", "unknown_tool"}


def test_exception_becomes_observation():
    def boom(name, arguments):
        raise RuntimeError("boom")

    client = ScriptedClient(
        [
            reply("", [ToolCall("1", "calculate", '{"expression": "1+1"}')]),
            reply("ANSWER: 0"),
        ]
    )
    out = run_tool_loop(client, [{"role": "user", "content": "x"}], boom, 4)
    assert out["tool_errors"] == 1
    assert out["trace"][1]["error"] == "exception"
    assert "boom" in out["trace"][1]["preview"]


def test_step_limit_stops_without_an_answer():
    call = reply("", [ToolCall("1", "calculate", '{"expression": "1+1"}')])
    client = ScriptedClient([call, reply("", [ToolCall("2", "calculate", '{"expression": "1+1"}')])])
    out = run_tool_loop(client, [{"role": "user", "content": "x"}], execute, 2)
    assert out["stop"] == "step_limit"
    assert out["pred"] == ""
    assert out["tool_calls"] == 2


def test_react_sees_only_the_question():
    client = ScriptedClient([reply("ANSWER: 43200")])
    out = run_react(client, "Сколько будет 2400 * 18?", execute)
    assert out["pred"] == "ANSWER: 43200"
    assert client.sent[0]["messages"][1]["content"] == "Сколько будет 2400 * 18?"
    assert "calc" not in client.sent[0]["messages"][1]["content"]
