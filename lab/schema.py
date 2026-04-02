def validate(schema, arguments):
    if not isinstance(arguments, dict):
        return "arguments должны быть объектом"
    if schema.get("type") not in (None, "object"):
        return "схема поддерживает только object"
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    additional = schema.get("additionalProperties", True)
    for key in required:
        if key not in arguments:
            return f"нет поля {key}"
    for key, value in arguments.items():
        if key not in properties:
            if additional is False:
                return f"лишнее поле {key}"
            continue
        error = _check(properties[key], value, key)
        if error:
            return error
    return None


def _check(spec, value, key):
    expected = spec.get("type")
    if expected == "string":
        if not isinstance(value, str):
            return f"{key} должен быть string"
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{key} должен быть integer"
    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{key} должен быть number"
    elif expected == "boolean":
        if not isinstance(value, bool):
            return f"{key} должен быть boolean"
    elif expected is not None:
        return f"неподдержанный тип {expected}"
    if "enum" in spec and value not in spec["enum"]:
        return f"{key} не из enum"
    return None


def to_openai(spec):
    return {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["parameters"],
        },
    }
