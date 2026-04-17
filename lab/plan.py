import json

from lab.jsonutil import extract_json
from lab.limits import PLAN_INNER, PLAN_MAX_STEPS, PLAN_MODEL_CALLS
from lab.loop import preview, run_tool_loop
from lab.prompts import EXEC_SYSTEM, SYNTH_SYSTEM, plan_system


def run_plan(client, question, dispatch, max_calls=PLAN_MODEL_CALLS):
    trace = []
    observations = []
    messages = [
        {"role": "system", "content": plan_system()},
        {"role": "user", "content": question},
    ]
    steps = ask_steps(client, messages, max_calls, trace)
    if not steps:
        return _done("", "error", trace, observations)
    final = ""
    executed = 0
    index = 0
    replanned = False
    while executed < PLAN_MAX_STEPS and index < len(steps) and client.calls < max_calls:
        step = steps[index]
        inner = min(PLAN_INNER, max_calls - client.calls)
        outcome = run_tool_loop(
            client,
            [
                {"role": "system", "content": EXEC_SYSTEM},
                {"role": "user", "content": _step_text(question, observations, step)},
            ],
            dispatch,
            inner,
        )
        trace.extend(outcome["trace"])
        observations.extend(_observations(outcome["trace"]))
        executed += 1
        if outcome["stop"] == "answer" and outcome["pred"].strip():
            final = outcome["pred"]
            break
        if outcome["tool_errors"] and not replanned and client.calls < max_calls:
            replanned = True
            extra = ask_steps(
                client,
                [
                    {"role": "system", "content": plan_system()},
                    {
                        "role": "user",
                        "content": question
                        + "\nИнструмент вернул ошибку. Составь новый план только для оставшейся работы.\n"
                        + json.dumps(observations, ensure_ascii=False),
                    },
                ],
                max_calls,
                trace,
            )
            if extra:
                steps = extra
                index = 0
                continue
        index += 1
    if not final and client.calls < max_calls:
        completion = client.complete(
            [
                {"role": "system", "content": SYNTH_SYSTEM},
                {"role": "user", "content": question + "\nНаблюдения:\n" + json.dumps(observations, ensure_ascii=False)},
            ],
            tools=None,
            json_mode=False,
        )
        trace.append({"kind": "model", "preview": preview(completion.content), "tool_names": []})
        final = completion.content or ""
    stop = "answer" if final.strip() else "step_limit"
    return _done(final, stop, trace, observations)


def ask_steps(client, messages, max_calls, trace):
    if client.calls >= max_calls:
        return None
    completion = client.complete(messages, tools=None, json_mode=True)
    trace.append({"kind": "model", "preview": preview(completion.content), "tool_names": []})
    steps = _steps(extract_json(completion.content)[0])
    if steps:
        return steps
    if client.calls >= max_calls:
        return None
    retry = messages + [
        {"role": "assistant", "content": completion.content or ""},
        {"role": "user", "content": "Нужен JSON {\"steps\": [{\"tool\": \"имя\", \"goal\": \"цель\"}]} из 1–6 шагов."},
    ]
    completion = client.complete(retry, tools=None, json_mode=True)
    trace.append({"kind": "model", "preview": preview(completion.content), "tool_names": []})
    return _steps(extract_json(completion.content)[0])


def _steps(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("steps"), list) or not obj["steps"]:
        return None
    steps = []
    for row in obj["steps"][:PLAN_MAX_STEPS]:
        if not isinstance(row, dict) or not isinstance(row.get("tool"), str) or not isinstance(row.get("goal"), str):
            return None
        steps.append({"tool": row["tool"], "goal": row["goal"]})
    return steps or None


def _observations(trace):
    rows = []
    for item in trace:
        if item["kind"] == "tool":
            rows.append({"tool": item["name"], "ok": item["ok"], "error": item["error"], "result": item["preview"]})
    return rows


def _step_text(question, observations, step):
    return (
        f"Вопрос: {question}\nНаблюдения: {json.dumps(observations, ensure_ascii=False)}\n"
        f"Шаг: {step['goal']}\nПредпочтительный инструмент: {step['tool']}"
    )


def _done(pred, stop, trace, observations):
    tool_calls = sum(1 for item in trace if item["kind"] == "tool")
    tool_errors = sum(1 for item in trace if item["kind"] == "tool" and not item["ok"])
    return {
        "pred": pred,
        "stop": stop,
        "trace": trace,
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "observations": observations,
    }
