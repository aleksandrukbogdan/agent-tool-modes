import json
import re


def extract_json(text):
    if not text:
        return None, "пустой ответ"
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S | re.I)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    if start < 0:
        return None, "нет объекта"
    obj, end = _balanced(cleaned, start)
    if obj is None:
        return None, "объект не закрыт"
    try:
        value = json.loads(obj)
    except json.JSONDecodeError:
        return None, "невалидный json"
    if not isinstance(value, dict):
        return None, "json не объект"
    return value, None


def _balanced(text, start):
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1], i + 1
    return None, None


def parse_arguments(raw):
    if isinstance(raw, dict):
        return raw, None
    if not isinstance(raw, str):
        return None, "arguments_type"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None, "arguments_json"
    if not isinstance(value, dict):
        return None, "arguments_type"
    return value, None


def parse_text_tool_calls(content):
    if not content or "<tool_call>" not in content:
        return []
    calls = []
    for block in re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.S):
        call = _parse_block(block, len(calls))
        if call is not None:
            calls.append(call)
    return calls


def _parse_block(block, index):
    obj, err = extract_json(block)
    if err is None and "name" in obj:
        arguments = obj.get("arguments", {})
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)
        return {"id": f"text_{index}", "name": str(obj["name"]), "arguments": arguments}
    fn = re.search(r"<function=([^>\n]+)>", block)
    if not fn:
        return {
            "id": f"text_{index}",
            "name": "",
            "arguments": block.strip(),
        }
    name = fn.group(1).strip()
    params = {}
    for pname, pvalue in re.findall(r"<parameter=([^>\n]+)>\s*(.*?)\s*</parameter>", block, re.S):
        params[pname.strip()] = _coerce_param(pvalue.strip())
    return {
        "id": f"text_{index}",
        "name": name,
        "arguments": json.dumps(params, ensure_ascii=False),
    }


def _coerce_param(value):
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    lowered = value.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value
