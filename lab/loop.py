import json

from lab.jsonutil import parse_arguments, parse_text_tool_calls


def preview(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return value[:1500]


def guarded(dispatch, name, arguments):
    try:
        result = dispatch(name, arguments)
    except Exception as exc:
        return {"ok": False, "error": "exception", "detail": f"{type(exc).__name__}: {exc}"}
    if not isinstance(result, dict) or "ok" not in result:
        return {"ok": False, "error": "bad_result", "detail": "инструмент вернул не объект"}
    return result


def coerce_calls(content, tool_calls):
    if tool_calls:
        return content, list(tool_calls)
    from lab.client import ToolCall

    parsed = parse_text_tool_calls(content or "")
    if not parsed:
        return content, []
    calls = [ToolCall(item["id"], item["name"], item["arguments"]) for item in parsed]
    return "", calls


def assistant_message(content, calls, raw_message):
    if raw_message and raw_message.get("tool_calls"):
        return {"role": "assistant", "content": raw_message.get("content") or "", "tool_calls": raw_message["tool_calls"]}
    message = {"role": "assistant", "content": content or ""}
    if calls:
        message["tool_calls"] = [
            {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
            for call in calls
        ]
    return message


def run_tool_loop(client, messages, dispatch, max_steps, tools=None):
    # tools оставлен в сигнатуре для совместимости тестов. Этот vLLM отвергает поле tools:
    # процесс запущен без --enable-auto-tool-choice и --tool-call-parser.
    del tools
    trace = []
    tool_calls = 0
    tool_errors = 0
    for _ in range(max_steps):
        completion = client.complete(messages, tools=None, json_mode=False)
        content, calls = coerce_calls(completion.content, completion.tool_calls)
        trace.append(
            {
                "kind": "model",
                "preview": preview(content if content else completion.content),
                "tool_names": [call.name for call in calls],
            }
        )
        if not calls:
            return {"pred": content or "", "stop": "answer", "trace": trace, "tool_calls": tool_calls, "tool_errors": tool_errors}
        notes = []
        for call in calls:
            tool_calls += 1
            arguments, error = parse_arguments(call.arguments)
            if error:
                result = {"ok": False, "error": error, "detail": preview(call.arguments)}
            elif not call.name:
                result = {"ok": False, "error": "unknown_tool", "detail": ""}
            else:
                result = guarded(dispatch, call.name, arguments)
            if not result.get("ok"):
                tool_errors += 1
            trace.append(
                {
                    "kind": "tool",
                    "name": call.name,
                    "ok": bool(result.get("ok")),
                    "error": result.get("error") or "",
                    "preview": preview(result),
                }
            )
            notes.append(call.name + ": " + json.dumps(result, ensure_ascii=False))
        if completion.tool_calls:
            messages.append(assistant_message(content, calls, completion.raw_message))
            for call, note in zip(calls, notes):
                messages.append({"role": "tool", "tool_call_id": call.id, "content": note.split(": ", 1)[1]})
        else:
            messages.append({"role": "assistant", "content": completion.content or ""})
            messages.append({"role": "user", "content": "Наблюдения:\n" + "\n".join(notes)})
    return {"pred": "", "stop": "step_limit", "trace": trace, "tool_calls": tool_calls, "tool_errors": tool_errors}
