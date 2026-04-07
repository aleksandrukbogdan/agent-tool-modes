from lab.jsonutil import extract_json, parse_text_tool_calls


def test_extract_json_from_fence():
    obj, err = extract_json('текст\n```json\n{"expression": "1+1"}\n```')
    assert err is None
    assert obj["expression"] == "1+1"


def test_qwen_json_tool_call():
    text = '<tool_call>\n{"name": "calculate", "arguments": {"expression": "2+2"}}\n</tool_call>'
    calls = parse_text_tool_calls(text)
    assert calls[0]["name"] == "calculate"
    assert '"2+2"' in calls[0]["arguments"] or "2+2" in calls[0]["arguments"]


def test_qwen_parameter_tool_call():
    text = "<tool_call>\n<function=calculate>\n<parameter=expression>\n2+2\n</parameter>\n</function>\n</tool_call>"
    calls = parse_text_tool_calls(text)
    assert calls[0]["name"] == "calculate"
    assert "2+2" in calls[0]["arguments"]
