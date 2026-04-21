from lab.client import ScriptedClient, reply
from lab.long_tasks import LONG_BY_ID, LONG_TASKS
from lab.tasks import TASKS
from lab.tools import execute
from lab.workflow import run_workflow
from lab.world import annual_bonus, convert_amount, find_department, find_employee, per_diem, years_between


def test_long_slice_does_not_change_the_frozen_44():
    assert len(LONG_TASKS) == 6
    assert len({task.id for task in LONG_TASKS}) == 6
    assert {task.id for task in LONG_TASKS}.isdisjoint({task.id for task in TASKS})
    assert {task.family for task in LONG_TASKS} == {"chain"}


def test_long_golds_are_computed_from_the_world():
    belov = find_employee("Белов Кирилл")
    novikova = find_employee("Новикова Дарья")
    gap = annual_bonus(belov["salary"], belov["department"]) - annual_bonus(novikova["salary"], novikova["department"])
    assert LONG_BY_ID["d01"].gold == convert_amount(gap, "RUB", "USD")
    orlov = find_employee("Орлов Денис")
    assert LONG_BY_ID["d02"].gold == convert_amount(annual_bonus(orlov["salary"], orlov["department"]), "RUB", "USD")
    anna = find_employee("Иванова Анна")
    boss2 = find_employee(find_employee(anna["manager"])["manager"])
    budget = find_department(boss2["department"])["budget"]
    assert LONG_BY_ID["d03"].gold == convert_amount(budget, "RUB", "USD")
    olga = find_employee("Смирнова Ольга")
    assert LONG_BY_ID["d04"].gold == convert_amount(olga["salary"] * 12, "RUB", "USD")
    morozov = find_employee("Морозов Артём")
    volkova = find_employee("Волкова Елена")
    assert LONG_BY_ID["d05"].gold == per_diem(volkova["city"], years_between(volkova["start"], "2026-10-11")) - per_diem(
        morozov["city"], years_between(morozov["start"], "2026-10-11")
    )
    head = find_employee(find_department("поддержка")["head"])
    assert LONG_BY_ID["d06"].gold == convert_amount(head["salary"], "RUB", "EUR")
    assert LONG_BY_ID["d06"].gold == 2800


def test_chain_reuses_the_compose_slot_and_can_finish_in_two_stages():
    client = ScriptedClient(
        [
            reply('{"lookups": [{"entity": "department", "name": "поддержка", "var": "dept"}]}'),
            reply(
                '{"lookups": [{"entity": "employee", "name": "Орлов Денис", "var": "emp"}], '
                '"convert": {"amount": "emp.salary", "from_currency": "RUB", "to_currency": "EUR"}}'
            ),
        ]
    )
    out = run_workflow(client, LONG_BY_ID["d06"], execute)
    assert out["pred"] == "2800"
    assert out["tool_calls"] == 3
    assert out["stop"] == "answer"
