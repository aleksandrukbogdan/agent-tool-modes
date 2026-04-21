import json

from lab.client import ScriptedClient, reply
from lab.plan import run_plan
from lab.prompts import SYNTH_SYSTEM
from lab.tools import execute


def _call(name, arguments):
    body = json.dumps({"name": name, "arguments": arguments}, ensure_ascii=False)
    return reply("<tool_call>\n" + body + "\n</tool_call>")


def test_plan_runs_later_steps_only_when_the_inner_loop_does_not_answer():
    client = ScriptedClient(
        [
            reply(
                '{"steps": ['
                '{"tool": "lookup_employee", "goal": "карточка Анны"}, '
                '{"tool": "calculate", "goal": "годовая зарплата"}, '
                '{"tool": "convert_money", "goal": "перевод в доллары"}'
                "]}"
            ),
            _call("lookup_employee", {"name": "Иванова Анна"}),
            reply(""),
            _call("calculate", {"expression": "180000 * 12"}),
            reply(""),
            _call("convert_money", {"amount": 2160000, "from_currency": "RUB", "to_currency": "USD"}),
            reply("ANSWER: 23225"),
        ]
    )
    out = run_plan(client, "Годовая зарплата Ивановой Анны в долларах", execute)
    assert out["pred"] == "ANSWER: 23225"
    assert out["tool_calls"] == 3
    assert out["tool_errors"] == 0
    prompts = []
    for item in client.sent:
        for message in item["messages"]:
            content = message["content"]
            if "Предпочтительный инструмент" in content and content not in prompts:
                prompts.append(content)
    assert len(prompts) == 3
    assert "180000" in prompts[1]
    assert "годовая зарплата" in prompts[1]
    assert "2160000" in prompts[2]
    assert "перевод в доллары" in prompts[2]


def test_plan_replans_once_after_a_tool_error_and_keeps_the_observation():
    client = ScriptedClient(
        [
            reply('{"steps": [{"tool": "lookup_employee", "goal": "найти по фамилии"}]}'),
            _call("lookup_employee", {"name": "Нет Такой"}),
            _call("lookup_employee", {"name": "Нет Такой"}),
            reply('{"steps": [{"tool": "lookup_employee", "goal": "взять Смирнову Ольгу"}]}'),
            _call("lookup_employee", {"name": "Смирнова Ольга"}),
            reply("ANSWER: 190000"),
        ]
    )
    out = run_plan(client, "Месячная зарплата Смирновой Ольги", execute)
    assert out["pred"] == "ANSWER: 190000"
    assert out["tool_errors"] == 2
    replan = client.sent[3]["messages"][-1]["content"]
    assert "not_found" in replan
    assert "Составь новый план" in replan
    assert "190000" in client.sent[4]["messages"][-1]["content"]


def test_plan_synthesizes_when_the_step_budget_is_spent():
    client = ScriptedClient(
        [
            reply('{"steps": [{"tool": "calculate", "goal": "посчитать"}]}'),
            _call("calculate", {"expression": "2400 * 18"}),
            reply(""),
            reply("ANSWER: 43200"),
        ]
    )
    out = run_plan(client, "Сколько будет 2400 * 18?", execute, max_calls=4)
    assert out["pred"] == "ANSWER: 43200"
    assert out["stop"] == "answer"
    assert client.calls == 4
    synth = client.sent[-1]
    assert synth["messages"][0]["content"] == SYNTH_SYSTEM
    assert "43200" in synth["messages"][1]["content"]
