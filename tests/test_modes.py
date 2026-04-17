from lab.client import ScriptedClient, ToolCall, reply
from lab.plan import run_plan
from lab.score import match_answer
from lab.tasks import TASK_BY_ID
from lab.tools import execute
from lab.workflow import recover_kind, run_workflow


def _run(task_id, replies):
    client = ScriptedClient(replies)
    out = run_workflow(client, TASK_BY_ID[task_id], execute)
    return client, out


def test_calc_workflow_copies_expression():
    client, out = _run("c01", [reply('{"expression": "2400 * 18"}')])
    assert out["pred"] == "43200"
    assert out["tool_calls"] == 1
    assert client.calls == 1
    assert client.sent[0]["messages"][1]["content"] == TASK_BY_ID["c01"].question


def test_recover_calc_uses_the_fallback_after_division_by_zero():
    _, out = _run("r03", [reply('{"expression": "10 / 0"}'), reply('{"answer": 0}')])
    assert out["pred"] == "0"
    assert out["tool_errors"] == 1


def test_ambiguous_lookup_is_retried_once():
    _, out = _run(
        "r01",
        [
            reply('{"entity": "employee", "name": "Иванов", "field": "city"}'),
            reply('{"entity": "employee", "name": "Иванов Сергей", "department": "разработка", "field": "city"}'),
        ],
    )
    assert out["pred"] == "Москва"
    assert out["tool_errors"] == 1


def test_compose_second_slot_sees_the_department_head():
    client, out = _run(
        "a04",
        [
            reply('{"lookups": [{"entity": "department", "name": "разработка", "var": "dept"}]}'),
            reply(
                '{"lookups": [{"entity": "employee", "name": "Орлов Денис", "var": "emp"}], '
                '"expression": "dept.budget - emp.salary * 12"}'
            ),
        ],
    )
    assert out["pred"] == "5740000"
    assert "Орлов Денис" in client.sent[1]["messages"][-1]["content"]


def test_policy_expression_uses_the_retrieved_rate():
    _, out = _run(
        "p03",
        [
            reply('{"keyword": "суточные"}'),
            reply('{"lookups": [], "expression": "1200 * 4"}'),
        ],
    )
    assert out["pred"] == "4800"


def test_branch_compares_after_lookup():
    _, out = _run(
        "b03",
        [
            reply('{"lookups": [{"entity": "department", "name": "поддержка", "var": "dept"}]}'),
            reply(
                '{"left": "dept.budget", "op": "<", "right": 2000000, '
                '"if_true": {"action": "const", "value": "малый"}, '
                '"if_false": {"action": "const", "value": "крупный"}}'
            ),
        ],
    )
    assert out["pred"] == "малый"


def test_open_fallback_calls_one_tool_and_stops():
    client, out = _run(
        "o01",
        [
            reply('{"tool": "lookup_department", "arguments": {"name": "продажи"}}'),
            reply("ANSWER: 1"),
        ],
    )
    assert out["tool_calls"] == 1
    assert client.calls == 2
    assert client.sent[1]["json_mode"] is False
    assert match_answer(out["pred"], TASK_BY_ID["o01"].gold) is False


def test_recover_router_is_keyword_based():
    assert recover_kind(TASK_BY_ID["r03"].question) == "calc"
    assert recover_kind(TASK_BY_ID["r04"].question) == "convert"
    assert recover_kind(TASK_BY_ID["r05"].question) == "lookup"


def test_compose_convert_and_policy_if_and_string_branch():
    _, money = _run(
        "a07",
        [
            reply('{"lookups": [{"entity": "employee", "name": "Петров Игорь", "var": "emp"}]}'),
            reply('{"lookups": [], "convert": {"amount": "emp.salary", "from_currency": "RUB", "to_currency": "USD"}}'),
        ],
    )
    assert money["pred"] == "2688"
    _, vacation = _run(
        "p02",
        [
            reply('{"keyword": "отпуск"}'),
            reply(
                '{"lookups": [{"entity": "employee", "name": "Орлов Денис", "var": "emp"}], '
                '"if": {"left": "emp.start_year", "op": "<=", "right": 2018, "then": 31, "else": 28}}'
            ),
        ],
    )
    assert vacation["pred"] == "31"
    _, same = _run(
        "b04",
        [
            reply('{"lookups": [{"entity": "employee", "name": "Иванов Сергей", "var": "emp"}]}'),
            reply(
                '{"lookups": [{"entity": "department", "name": "разработка", "var": "dept"}], '
                '"left": "emp.manager", "op": "==", "right": "dept.head", '
                '"if_true": {"action": "const", "value": "да"}, "if_false": {"action": "const", "value": "нет"}}'
            ),
        ],
    )
    assert same["pred"] == "да"


def test_plan_executes_a_calculated_step():
    client = ScriptedClient(
        [
            reply('{"steps": [{"tool": "calculate", "goal": "посчитать выражение"}]}'),
            reply("", [ToolCall("c1", "calculate", '{"expression": "2400 * 18"}')]),
            reply("ANSWER: 43200"),
        ]
    )
    out = run_plan(client, TASK_BY_ID["c01"].question, execute)
    assert match_answer(out["pred"], 43200)
    assert out["tool_calls"] == 1
    assert "calc" not in client.sent[0]["messages"][-1]["content"]
