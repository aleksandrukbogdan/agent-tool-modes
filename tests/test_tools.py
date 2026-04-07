from lab.tools import execute


def test_calculate_floor_div_and_rejects_names():
    assert execute("calculate", {"expression": "10 / 4"})["data"]["value"] == 2
    assert execute("calculate", {"expression": "(28 + 3) * 1200"})["data"]["value"] == 37200
    bad = execute("calculate", {"expression": "salary * 12"})
    assert bad["ok"] is False
    assert bad["error"] == "forbidden"


def test_division_by_zero_and_syntax_are_errors():
    assert execute("calculate", {"expression": "10 / 0"})["error"] == "division_by_zero"
    assert execute("calculate", {"expression": "180000 +"})["error"] == "syntax"


def test_ambiguous_surname_and_department_filter():
    ambiguous = execute("lookup_employee", {"name": "Иванов"})
    assert ambiguous["error"] == "ambiguous"
    assert {row["name"] for row in ambiguous["candidates"]} == {"Иванов Сергей", "Иванова Анна"}
    exact = execute("lookup_employee", {"name": "Иванов", "department": "разработка"})
    assert exact["data"]["city"] == "Москва"
    assert exact["data"]["name"] == "Иванов Сергей"
    full = execute("lookup_employee", {"name": "Иванова Анна"})
    assert full["data"]["department"] == "финансы"


def test_missing_employee_currency_and_schema():
    assert execute("lookup_employee", {"name": "Пушкин Александр"})["error"] == "not_found"
    assert execute("convert_money", {"amount": 100, "from_currency": "FOO", "to_currency": "RUB"})["error"] == "unknown_currency"
    assert execute("calculate", {})["error"] == "schema"
    assert execute("nope", {})["error"] == "unknown_tool"
    assert execute("years_between", {"start": "2024-04-01", "end": "2026-10-11"})["data"]["value"] == 2


def test_policy_search_finds_perdiem_text():
    found = execute("search_policy", {"keyword": "суточные"})
    assert found["ok"] is True
    assert "1200" in found["data"]["items"][0]["text"]
    assert execute("search_policy", {"keyword": ""})["error"] == "empty_keyword"
