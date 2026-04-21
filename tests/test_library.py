import json

import pytest

pytest.importorskip("langgraph")

from lab.client import ScriptedClient, reply
from lab.library import run_graph
from lab.prompts import REACT_SYSTEM
from lab.tools import execute


def _call(name, arguments):
    body = json.dumps({"name": name, "arguments": arguments}, ensure_ascii=False)
    return reply("<tool_call>\n" + body + "\n</tool_call>")


def _chain_replies():
    return [
        _call("lookup_employee", {"name": "Иванова Анна"}),
        _call("lookup_employee", {"name": "Петров Игорь"}),
        _call("lookup_employee", {"name": "Соколова Мария"}),
        _call("lookup_department", {"name": "управление"}),
        _call("convert_money", {"amount": 2100000, "from_currency": "RUB", "to_currency": "USD"}),
        reply("ANSWER: 22580"),
    ]


def _messages():
    return [
        {"role": "system", "content": REACT_SYSTEM},
        {"role": "user", "content": "бюджет отдела руководителя руководителя Ивановой Анны в долларах"},
    ]


def test_langgraph_state_graph_parses_text_tool_call():
    client = ScriptedClient(
        [
            reply('<tool_call>\n{"name": "calculate", "arguments": {"expression": "2+2"}}\n</tool_call>'),
            reply("ANSWER: 4"),
        ]
    )
    out = run_graph(
        client,
        [
            {"role": "system", "content": REACT_SYSTEM},
            {"role": "user", "content": "сколько будет 2+2"},
        ],
        execute,
    )
    assert out["pred"] == "ANSWER: 4"
    assert out["tool_calls"] == 1
    assert out["tool_errors"] == 0
    assert "Наблюдения:" in client.sent[1]["messages"][-1]["content"]
    assert '"value": 4' in client.sent[1]["messages"][-1]["content"]
    assert out["checkpoints"] >= 2
    assert out["next"] == []
    assert out["thread_id"] == "main"


def test_checkpoint_keeps_each_step_of_a_long_dialogue():
    client = ScriptedClient(_chain_replies())
    out = run_graph(client, _messages(), execute, thread_id="chain")
    assert out["pred"] == "ANSWER: 22580"
    assert out["stop"] == "answer"
    assert out["tool_calls"] == 5
    assert out["tool_errors"] == 0
    assert out["checkpoints"] >= 11
    snapshot = out["app"].get_state({"configurable": {"thread_id": "chain"}})
    assert snapshot.values["steps"] == 6
    assert snapshot.next == ()


def test_interrupt_before_tools_resumes_the_same_thread():
    client = ScriptedClient(_chain_replies())
    paused = run_graph(
        client,
        _messages(),
        execute,
        thread_id="resume",
        interrupt_before=["tools"],
    )
    assert paused["stop"] == "interrupt"
    assert paused["next"] == ["tools"]
    assert paused["pred"] == ""
    assert client.calls == 1
    seen = {paused["checkpoints"]}
    out = paused
    while out["next"] == ["tools"]:
        out = run_graph(
            client,
            _messages(),
            execute,
            checkpointer=paused["checkpointer"],
            thread_id="resume",
            interrupt_before=["tools"],
            resume=True,
        )
        seen.add(out["checkpoints"])
    assert out["pred"] == "ANSWER: 22580"
    assert out["tool_calls"] == 5
    assert out["stop"] == "answer"
    assert max(seen) > paused["checkpoints"]
    history = list(out["app"].get_state_history({"configurable": {"thread_id": "resume"}}))
    assert len(history) == out["checkpoints"]
    assert any(item.next == ("tools",) for item in history)
