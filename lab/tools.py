import ast
import operator

from lab.schema import validate
from lab.world import (
    EMPLOYEES,
    POLICIES,
    convert_amount,
    find_department,
    fold,
    public_employee,
    years_between,
)

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_MAX_ABS = 10**18

SPECS = [
    {
        "name": "lookup_employee",
        "description": (
            "Карточка сотрудника: отдел, месячная зарплата, город, дата выхода, год выхода, руководитель. "
            "Имя передавай в именительном падеже, лучше «Фамилия Имя». "
            "Фамилия с женским окончанием «а» считается той же основой: «Иванов» находит и «Иванова». "
            "Если основа совпала у нескольких людей и отдел не задан, вернётся ошибка ambiguous и список кандидатов."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Фамилия или «Фамилия Имя» в именительном падеже"},
                "department": {"type": "string", "description": "Отдел, если нужно снять неоднозначность. Можно пустую строку."},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lookup_department",
        "description": (
            "Карточка отдела: годовой бюджет, руководитель, город. "
            "Имя отдела ровно одно из: финансы, разработка, продажи, поддержка, управление."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Имя отдела"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_employees",
        "description": "Список сотрудников одного отдела: имя, месячная зарплата, город, дата выхода, руководитель.",
        "parameters": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "Имя отдела"},
            },
            "required": ["department"],
            "additionalProperties": False,
        },
    },
    {
        "name": "calculate",
        "description": (
            "Целочисленное выражение из чисел, скобок и операций + - * / // %. "
            "/ и // дают целочисленное частное, дробная часть отбрасывается в сторону минус бесконечности. "
            "Имена и вызовы функций запрещены. Деление на ноль — ошибка division_by_zero."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Выражение, не длиннее 200 символов"},
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
    },
    {
        "name": "convert_money",
        "description": (
            "Переводит целую сумму между RUB, USD, EUR и CNY через рубли. "
            "Курс хранится в инструменте, в описании его нет. Дробная часть отбрасывается. "
            "Неизвестная валюта — ошибка unknown_currency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Сумма в валюте from_currency"},
                "from_currency": {"type": "string", "description": "RUB, USD, EUR или CNY"},
                "to_currency": {"type": "string", "description": "RUB, USD, EUR или CNY"},
            },
            "required": ["amount", "from_currency", "to_currency"],
            "additionalProperties": False,
        },
    },
    {
        "name": "years_between",
        "description": (
            "Число полных лет между датами start и end в формате ГГГГ-ММ-ДД. "
            "Год, который ещё не наступил к дате end, не считается. end раньше start — ошибка."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
            "required": ["start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_policy",
        "description": (
            "Ищет пункты регламента по подстроке в тексте. "
            "Оттуда берутся дни отпуска, процент премии и ставки суточных. Пустой запрос — ошибка."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Подстрока, например отпуск, премия или суточные"},
            },
            "required": ["keyword"],
            "additionalProperties": False,
        },
    },
]

SPEC_BY_NAME = {spec["name"]: spec for spec in SPECS}


def last_stem(name):
    parts = fold(name).split()
    if not parts:
        return ""
    last = parts[0]
    if last.endswith("а") and len(last) > 3:
        return last[:-1]
    return last


def match_employees(name, department=""):
    query = fold(name).strip(".,")
    if not query:
        return []
    exact = [employee for employee in EMPLOYEES if fold(employee["name"]) == query]
    if len(exact) == 1:
        found = exact
    else:
        stem = last_stem(query)
        found = [employee for employee in EMPLOYEES if last_stem(employee["name"]) == stem]
    if department:
        dept = fold(department)
        found = [employee for employee in found if fold(employee["department"]) == dept]
    return found


def lookup_employee(arguments):
    found = match_employees(arguments.get("name", ""), arguments.get("department") or "")
    if not found:
        return {"ok": False, "error": "not_found", "detail": "сотрудник не найден"}
    if len(found) > 1:
        return {
            "ok": False,
            "error": "ambiguous",
            "detail": "несколько сотрудников",
            "candidates": [public_employee(employee) for employee in found],
        }
    return {"ok": True, "data": public_employee(found[0])}


def lookup_department(arguments):
    department = find_department(arguments.get("name", ""))
    if department is None:
        return {"ok": False, "error": "not_found", "detail": "отдел не найден"}
    return {"ok": True, "data": dict(department)}


def list_employees(arguments):
    department = find_department(arguments.get("department", ""))
    if department is None:
        return {"ok": False, "error": "not_found", "detail": "отдел не найден"}
    rows = [public_employee(employee) for employee in EMPLOYEES if employee["department"] == department["name"]]
    return {"ok": True, "data": {"department": department["name"], "employees": rows}}


def calculate(arguments):
    expression = arguments.get("expression", "")
    if not isinstance(expression, str) or not expression.strip():
        return {"ok": False, "error": "syntax", "detail": "пустое выражение"}
    if len(expression) > 200:
        return {"ok": False, "error": "syntax", "detail": "выражение длиннее 200 символов"}
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return {"ok": False, "error": "syntax", "detail": "выражение не разобрано"}
    try:
        value = _eval(tree.body)
    except ZeroDivisionError:
        return {"ok": False, "error": "division_by_zero", "detail": "деление на ноль"}
    except ValueError as exc:
        return {"ok": False, "error": "forbidden", "detail": str(exc)}
    if isinstance(value, bool) or not isinstance(value, int):
        return {"ok": False, "error": "forbidden", "detail": "результат не целое число"}
    if abs(value) > _MAX_ABS:
        return {"ok": False, "error": "overflow", "detail": "слишком большое число"}
    return {"ok": True, "data": {"value": value}}


def _eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int):
            raise ValueError("допустимы только целые литералы")
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Div):
        left = _eval(node.left)
        right = _eval(node.right)
        if type(node.op) is ast.Div:
            if right == 0:
                raise ZeroDivisionError
            return left // right
        return _OPS[type(node.op)](left, right)
    raise ValueError("допустимы только числа и + - * / // %")


def convert_money(arguments):
    amount = arguments["amount"]
    src = arguments["from_currency"]
    dst = arguments["to_currency"]
    if src.upper() not in ("RUB", "USD", "EUR", "CNY") or dst.upper() not in ("RUB", "USD", "EUR", "CNY"):
        return {"ok": False, "error": "unknown_currency", "detail": f"{src}->{dst}"}
    return {"ok": True, "data": {"value": convert_amount(amount, src, dst)}}


def years_between_tool(arguments):
    if years_between(arguments["start"], arguments["start"]) is None:
        return {"ok": False, "error": "bad_date", "detail": arguments["start"]}
    if years_between(arguments["end"], arguments["end"]) is None:
        return {"ok": False, "error": "bad_date", "detail": arguments["end"]}
    value = years_between(arguments["start"], arguments["end"])
    if value < 0:
        return {"ok": False, "error": "order", "detail": "end раньше start"}
    return {"ok": True, "data": {"value": value}}


def search_policy(arguments):
    keyword = fold(arguments.get("keyword", ""))
    if not keyword:
        return {"ok": False, "error": "empty_keyword", "detail": "пустой запрос"}
    items = [{"id": policy["id"], "text": policy["text"]} for policy in POLICIES if keyword in fold(policy["text"])]
    return {"ok": True, "data": {"items": items}}


_IMPL = {
    "lookup_employee": lookup_employee,
    "lookup_department": lookup_department,
    "list_employees": list_employees,
    "calculate": calculate,
    "convert_money": convert_money,
    "years_between": years_between_tool,
    "search_policy": search_policy,
}


def execute(name, arguments):
    spec = SPEC_BY_NAME.get(name)
    if spec is None:
        return {"ok": False, "error": "unknown_tool", "detail": name}
    error = validate(spec["parameters"], arguments)
    if error:
        return {"ok": False, "error": "schema", "detail": error}
    try:
        result = _IMPL[name](arguments)
    except Exception as exc:
        return {"ok": False, "error": "exception", "detail": f"{type(exc).__name__}: {exc}"}
    if not isinstance(result, dict) or "ok" not in result:
        return {"ok": False, "error": "bad_result", "detail": "инструмент вернул не объект"}
    return result
