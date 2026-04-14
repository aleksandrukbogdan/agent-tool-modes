import json

from lab.jsonutil import extract_json
from lab.limits import WORKFLOW_MODEL_CALLS
from lab.loop import guarded, preview
from lab.prompts import SYNTH_SYSTEM

_EMPLOYEE_FIELDS = {"name", "department", "salary", "city", "start", "start_year", "manager"}
_DEPT_FIELDS = {"name", "budget", "head", "city"}

_CALC = (
    "Из вопроса возьми выражение для calculate и верни только JSON {\"expression\": \"...\"}. "
    "Сам не вычисляй. Если выражение в вопросе обрезано или делит на ноль, всё равно передай его в инструмент как есть."
)
_LOOKUP = (
    "Верни только JSON {\"entity\": \"employee\" или \"department\", \"name\": \"...\", \"department\": \"\", \"field\": \"...\"}. "
    "field сотрудника: name, department, salary, city, start, start_year, manager. "
    "field отдела: name, budget, head, city. "
    "Имя сотрудника — именительный падеж «Фамилия Имя». Имя отдела — ключ: финансы, разработка, продажи, поддержка, управление."
)
_COMPOSE_1 = (
    "Верни только JSON {\"lookups\": [{\"entity\": \"employee\" или \"department\", \"name\": \"...\", \"department\": \"\", \"var\": \"emp\"}]}. "
    "Бери только сущности, чьи имена уже написаны в вопросе. Имена, которые появятся в ответе инструмента, не угадывай. "
    "var — латинский идентификатор. expression на этом шаге не пиши."
)
_COMPOSE_2 = (
    "Ниже данные lookups. Верни только JSON с дополнительными lookups, если нужно имя из этих данных, и полем expression. "
    "Ссылка на поле пишется как emp.salary. Арифметика целочисленная, деление через // или /. "
    "Пример формы: {\"lookups\": [], \"expression\": \"emp.salary * 12\"}. "
    "Если нужен выбор из двух констант, вместо expression дай if: "
    "{\"left\": \"emp.start_year\", \"op\": \"<=\", \"right\": 1, \"then\": 1, \"else\": 0}. "
    "op в if: > < >= <= ==. "
    "Для валюты вместо expression дай convert: "
    "{\"amount\": \"emp.salary\", \"from_currency\": \"RUB\", \"to_currency\": \"USD\"}. "
    "Числа из текста политики подставляй литералами."
)
_POLICY_1 = "Выбери подстроку для search_policy и верни только JSON {\"keyword\": \"...\"}."
_BRANCH_1 = _COMPOSE_1
_BRANCH_2 = (
    "По данным реши развилку. Сначала можно добавить lookups, если нужно имя из данных. Верни только JSON. "
    "Форма: {\"lookups\": [], \"left\": \"emp.salary\", \"op\": \">\", \"right\": 1, "
    "\"if_true\": {\"action\": \"const\", \"value\": \"да\"}, "
    "\"if_false\": {\"action\": \"convert\", \"amount\": \"emp.salary\", \"from_currency\": \"RUB\", \"to_currency\": \"USD\"}}. "
    "op один из > < >= <= ==. right — число, строка или путь var.field. "
    "action const.value — число или строка. action convert переводит amount."
)
_CONVERT = (
    "Верни только JSON {\"amount\": 0, \"from_currency\": \"RUB\", \"to_currency\": \"USD\"}. "
    "Валюту копируй из вопроса, даже если её нет среди RUB, USD, EUR, CNY."
)
_OPEN = (
    "Можно вызвать ровно один инструмент, повтора не будет. "
    "Верни только JSON {\"tool\": \"<имя>\", \"arguments\": {}}."
)


class Ctx:
    def __init__(self, client, dispatch):
        self.client = client
        self.dispatch = dispatch
        self.trace = []
        self.tool_calls = 0
        self.tool_errors = 0
        self.stop = "answer"

    def ask(self, messages, json_mode=True):
        if self.client.calls >= WORKFLOW_MODEL_CALLS:
            self.stop = "step_limit"
            return None
        completion = self.client.complete(messages, tools=None, json_mode=json_mode)
        self.trace.append({"kind": "model", "preview": preview(completion.content), "tool_names": []})
        return completion

    def tool(self, name, arguments):
        self.tool_calls += 1
        result = guarded(self.dispatch, name, arguments)
        if not result.get("ok"):
            self.tool_errors += 1
        self.trace.append(
            {
                "kind": "tool",
                "name": name,
                "ok": bool(result.get("ok")),
                "error": result.get("error") or "",
                "preview": preview(result),
            }
        )
        return result


def recover_kind(question):
    folded = question.casefold()
    if "переведи" in folded:
        return "convert"
    if "посчитай" in folded:
        return "calc"
    return "lookup"


def run_workflow(client, task, dispatch):
    ctx = Ctx(client, dispatch)
    family = recover_kind(task.question) if task.family == "recover" else task.family
    if family == "calc":
        pred = run_calc(ctx, task.question, repair_answer=task.family == "recover")
    elif family == "lookup":
        pred = run_lookup(ctx, task.question, repair_answer=task.family == "recover")
    elif family == "convert":
        pred = run_convert(ctx, task.question, repair_answer=True)
    elif family in ("compose", "chain"):
        pred = run_compose(ctx, task.question)
    elif family == "policy":
        pred = run_policy(ctx, task.question)
    elif family == "branch":
        pred = run_branch(ctx, task.question)
    elif family == "open":
        pred = run_open(ctx, task.question)
    else:
        pred = ""
        ctx.stop = "error"
    return {
        "pred": pred or "",
        "stop": ctx.stop,
        "trace": ctx.trace,
        "tool_calls": ctx.tool_calls,
        "tool_errors": ctx.tool_errors,
    }


def ask_obj(ctx, messages):
    completion = ctx.ask(messages)
    if completion is None:
        return None
    obj, err = extract_json(completion.content)
    if err is None:
        return obj
    retry = messages + [
        {"role": "assistant", "content": completion.content or ""},
        {"role": "user", "content": "Нужен один JSON-объект без markdown. " + err},
    ]
    completion = ctx.ask(retry)
    if completion is None:
        return None
    obj, err = extract_json(completion.content)
    if err is not None:
        ctx.stop = "error"
        return None
    return obj


def run_calc(ctx, question, repair_answer):
    messages = [{"role": "system", "content": _CALC}, {"role": "user", "content": question}]
    obj = ask_obj(ctx, messages)
    if obj is None:
        return ""
    if not isinstance(obj, dict) or not isinstance(obj.get("expression"), str):
        ctx.stop = "error"
        return ""
    result = ctx.tool("calculate", {"expression": obj["expression"]})
    if result.get("ok"):
        return str(result["data"]["value"])
    note = "Исправь JSON. Ошибка инструмента: " + preview(result)
    if repair_answer:
        note += " Если вопрос задаёт запасной ответ, верни {\"answer\": <число или строка>}."
    else:
        note += " Верни {\"expression\": \"...\"}."
    repaired = ask_obj(ctx, _follow(messages, obj, note))
    if not isinstance(repaired, dict):
        return ""
    if repair_answer and "answer" in repaired and "expression" not in repaired:
        return const_text(repaired["answer"])
    if not isinstance(repaired.get("expression"), str):
        ctx.stop = "error"
        return ""
    result = ctx.tool("calculate", {"expression": repaired["expression"]})
    if not result.get("ok"):
        ctx.stop = "error"
        return ""
    return str(result["data"]["value"])


def run_lookup(ctx, question, repair_answer):
    messages = [{"role": "system", "content": _LOOKUP}, {"role": "user", "content": question}]
    obj = ask_obj(ctx, messages)
    if obj is None:
        return ""
    status, value = take_lookup(ctx, obj, allow_answer=False)
    if status == "ok":
        return value
    note = "Повтори lookup. Причина: " + detail_text(value)
    if repair_answer:
        note += " Если вопрос задаёт ответ на эту ошибку, можно вернуть {\"answer\": ...} без entity."
    repaired = ask_obj(ctx, _follow(messages, obj, note))
    status, value = take_lookup(ctx, repaired, allow_answer=repair_answer)
    if status != "ok":
        ctx.stop = "error"
        return ""
    return value


def run_convert(ctx, question, repair_answer):
    messages = [{"role": "system", "content": _CONVERT}, {"role": "user", "content": question}]
    obj = ask_obj(ctx, messages)
    result = _convert(ctx, obj)
    if result is not None and result.get("ok"):
        return str(result["data"]["value"])
    note = "Инструмент валют вернул ошибку: " + preview(result)
    if repair_answer:
        note += " Если вопрос задаёт ответ на эту ошибку, верни {\"answer\": ...}."
    repaired = ask_obj(ctx, _follow(messages, obj, note))
    if isinstance(repaired, dict) and "answer" in repaired and "amount" not in repaired:
        return const_text(repaired["answer"])
    result = _convert(ctx, repaired)
    if result is None or not result.get("ok"):
        ctx.stop = "error"
        return ""
    return str(result["data"]["value"])


def run_compose(ctx, question):
    messages = [{"role": "system", "content": _COMPOSE_1}, {"role": "user", "content": question}]
    scope = {}
    used = fill_lookups(ctx, messages, scope)
    if used is None:
        return ""
    follow = _follow(messages, used, _COMPOSE_2 + "\nДанные:\n" + json.dumps(scope, ensure_ascii=False))
    return finish_expr(ctx, follow, scope)


def run_policy(ctx, question):
    messages = [{"role": "system", "content": _POLICY_1}, {"role": "user", "content": question}]
    obj = ask_obj(ctx, messages)
    result = _policy(ctx, obj)
    if result is None or not result.get("ok") or not result["data"]["items"]:
        obj = ask_obj(ctx, _follow(messages, obj, "search_policy ничего не нашёл или отверг запрос. Верни другой keyword."))
        result = _policy(ctx, obj)
        if result is None or not result.get("ok") or not result["data"]["items"]:
            ctx.stop = "error"
            return ""
    follow = _follow(messages, obj, _COMPOSE_2 + "\nПолитика:\n" + json.dumps(result["data"]["items"], ensure_ascii=False))
    return finish_expr(ctx, follow, {})


def run_branch(ctx, question):
    messages = [{"role": "system", "content": _BRANCH_1}, {"role": "user", "content": question}]
    scope = {}
    used = fill_lookups(ctx, messages, scope)
    if used is None:
        return ""
    follow = _follow(messages, used, _BRANCH_2 + "\nДанные:\n" + json.dumps(scope, ensure_ascii=False))
    return finish_branch(ctx, follow, scope)


def run_open(ctx, question):
    messages = [{"role": "system", "content": _OPEN}, {"role": "user", "content": question}]
    obj = ask_obj(ctx, messages)
    if not isinstance(obj, dict) or not isinstance(obj.get("tool"), str):
        ctx.stop = "error"
        return ""
    arguments = obj.get("arguments") if isinstance(obj.get("arguments"), dict) else {}
    result = ctx.tool(obj["tool"], arguments)
    completion = ctx.ask(
        [
            {"role": "system", "content": SYNTH_SYSTEM},
            {
                "role": "user",
                "content": question + "\nНаблюдение одного инструмента:\n" + json.dumps(result, ensure_ascii=False),
            },
        ],
        json_mode=False,
    )
    if completion is None:
        return ""
    return completion.content or ""


def fill_lookups(ctx, messages, scope):
    obj = ask_obj(ctx, messages)
    if not isinstance(obj, dict):
        return None
    status, detail = apply_lookups(ctx, obj, scope)
    if status == "ok":
        return obj
    scope.clear()
    obj = ask_obj(ctx, _follow(messages, obj, "Исправь lookups. Причина: " + detail_text(detail)))
    if not isinstance(obj, dict):
        return None
    status, detail = apply_lookups(ctx, obj, scope)
    if status != "ok":
        ctx.stop = "error"
        return None
    return obj


def finish_expr(ctx, messages, scope):
    return _finish(ctx, messages, scope, apply_finish)


def finish_branch(ctx, messages, scope):
    return _finish(ctx, messages, scope, apply_branch)


def _finish(ctx, messages, scope, apply):
    base = dict(scope)
    obj = ask_obj(ctx, messages)
    if not isinstance(obj, dict):
        return ""
    status, value = apply(ctx, obj, scope)
    if status == "ok":
        return value
    scope.clear()
    scope.update(base)
    repaired = ask_obj(ctx, _follow(messages, obj, "Исправь JSON. Причина: " + detail_text(value)))
    if not isinstance(repaired, dict):
        return ""
    status, value = apply(ctx, repaired, scope)
    if status != "ok":
        ctx.stop = "error"
        return ""
    return value


def apply_lookups(ctx, obj, scope):
    rows = obj.get("lookups") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        return "bad", "нужен список lookups"
    for row in rows:
        if not isinstance(row, dict):
            return "bad", "lookup не объект"
        var = row.get("var")
        name = row.get("name")
        if not isinstance(var, str) or not var.isidentifier() or not isinstance(name, str) or not name.strip():
            return "bad", "var или name"
        department = row.get("department") or ""
        if not isinstance(department, str):
            return "bad", "department"
        entity = row.get("entity")
        if entity == "employee":
            args = {"name": name}
            if department:
                args["department"] = department
            result = ctx.tool("lookup_employee", args)
        elif entity == "department":
            result = ctx.tool("lookup_department", {"name": name})
        else:
            return "bad", "entity"
        if not result.get("ok"):
            return "bad", result
        scope[var] = result["data"]
    return "ok", None


def apply_finish(ctx, obj, scope):
    if obj.get("lookups"):
        status, detail = apply_lookups(ctx, obj, scope)
        if status != "ok":
            return "bad", detail
    if isinstance(obj.get("expression"), str):
        result = eval_expression(ctx, obj["expression"], scope)
        if not result.get("ok"):
            return "bad", result
        return "ok", str(result["data"]["value"])
    if isinstance(obj.get("if"), dict):
        return apply_choice(obj["if"], scope)
    if isinstance(obj.get("convert"), dict):
        text = eval_action(ctx, {"action": "convert", **obj["convert"]}, scope)
        if text is None:
            return "bad", "convert"
        return "ok", text
    return "bad", "нет expression"


def apply_branch(ctx, obj, scope):
    if obj.get("lookups"):
        status, detail = apply_lookups(ctx, obj, scope)
        if status != "ok":
            return "bad", detail
    try:
        left = materialize(scope, obj.get("left"))
        right = materialize(scope, obj.get("right"))
    except KeyError as exc:
        return "bad", str(exc)
    op = obj.get("op")
    if op not in (">", "<", ">=", "<=", "=="):
        return "bad", "op"
    if op != "==" and not _ints(left, right):
        return "bad", "type"
    passed = _compare(left, right, op)
    action = obj.get("if_true") if passed else obj.get("if_false")
    text = eval_action(ctx, action, scope)
    if text is None:
        return "bad", "action"
    return "ok", text


def apply_choice(spec, scope):
    try:
        left = materialize(scope, spec.get("left"))
        right = materialize(scope, spec.get("right"))
    except KeyError as exc:
        return "bad", str(exc)
    op = spec.get("op")
    if op not in (">", "<", ">=", "<=", "=="):
        return "bad", "op"
    if op != "==" and not _ints(left, right):
        return "bad", "type"
    passed = _compare(left, right, op)
    value = spec.get("then") if passed else spec.get("else")
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return "bad", "then/else"
    return "ok", const_text(value)


def eval_action(ctx, action, scope):
    if not isinstance(action, dict):
        return None
    if action.get("action") == "const":
        if isinstance(action.get("value"), bool) or not isinstance(action.get("value"), (int, str)):
            return None
        return const_text(action["value"])
    if action.get("action") == "convert":
        try:
            amount = materialize(scope, action.get("amount"))
        except KeyError:
            return None
        if not _ints(amount):
            return None
        result = ctx.tool(
            "convert_money",
            {
                "amount": amount,
                "from_currency": action.get("from_currency"),
                "to_currency": action.get("to_currency"),
            },
        )
        if not result.get("ok"):
            return None
        return str(result["data"]["value"])
    return None


def eval_expression(ctx, expression, scope):
    try:
        rewritten = substitute(expression, scope)
    except (KeyError, TypeError) as exc:
        return {"ok": False, "error": "subst", "detail": str(exc)}
    return ctx.tool("calculate", {"expression": rewritten})


def substitute(expression, scope):
    import re

    def repl(match):
        value = resolve_path(scope, match.group(0))
        if not _ints(value):
            raise TypeError(match.group(0))
        return str(value)

    return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b", repl, expression)


def materialize(scope, value):
    if isinstance(value, str) and "." in value:
        return resolve_path(scope, value)
    return value


def resolve_path(scope, path):
    var, field = path.split(".", 1)
    if var not in scope or not isinstance(scope[var], dict) or field not in scope[var]:
        raise KeyError(path)
    return scope[var][field]


def take_lookup(ctx, obj, allow_answer):
    if not isinstance(obj, dict):
        return "bad", "не объект"
    if allow_answer and "answer" in obj and "entity" not in obj:
        return "ok", const_text(obj["answer"])
    entity = obj.get("entity")
    field = obj.get("field")
    allowed = _EMPLOYEE_FIELDS if entity == "employee" else _DEPT_FIELDS if entity == "department" else None
    if allowed is None or field not in allowed or not isinstance(obj.get("name"), str):
        return "bad", "entity/field"
    if entity == "employee":
        args = {"name": obj["name"]}
        if obj.get("department"):
            args["department"] = obj["department"]
        result = ctx.tool("lookup_employee", args)
    else:
        result = ctx.tool("lookup_department", {"name": obj["name"]})
    if not result.get("ok"):
        return "bad", result
    value = result["data"].get(field)
    if value is None:
        return "bad", "пустое поле"
    return "ok", const_text(value)


def _convert(ctx, obj):
    if not isinstance(obj, dict):
        return None
    if not isinstance(obj.get("amount"), int) or isinstance(obj.get("amount"), bool):
        return ctx.tool(
            "convert_money",
            {"amount": obj.get("amount"), "from_currency": obj.get("from_currency"), "to_currency": obj.get("to_currency")},
        )
    return ctx.tool(
        "convert_money",
        {
            "amount": obj["amount"],
            "from_currency": obj.get("from_currency") or "",
            "to_currency": obj.get("to_currency") or "",
        },
    )


def _policy(ctx, obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("keyword"), str):
        return None
    return ctx.tool("search_policy", {"keyword": obj["keyword"]})


def _follow(messages, obj, note):
    dumped = json.dumps(obj, ensure_ascii=False) if isinstance(obj, dict) else str(obj)
    return messages + [
        {"role": "assistant", "content": dumped},
        {"role": "user", "content": note},
    ]


def const_text(value):
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def detail_text(value):
    if isinstance(value, str):
        return value
    return preview(value)


def _compare(left, right, op):
    return {">": left > right, "<": left < right, ">=": left >= right, "<=": left <= right, "==": left == right}[op]


def _ints(*values):
    return all(isinstance(value, int) and not isinstance(value, bool) for value in values)
