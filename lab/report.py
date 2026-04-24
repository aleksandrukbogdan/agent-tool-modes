import json
from pathlib import Path

SYSTEMS = ("workflow", "react", "plan", "react_lg")

METRIC_COLUMNS = (
    ("success", 4),
    ("mean_total_tokens", 1),
    ("mean_latency_s", 3),
    ("mean_model_calls", 2),
    ("mean_tool_calls", 2),
)


def write_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_main_table(text):
    lines = text.splitlines()
    header_i = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "success" in line and "mean_latency_s" in line:
            header_i = i
            break
    if header_i is None:
        raise AssertionError("в README нет таблицы метрик")
    rows = {}
    for line in lines[header_i + 2 :]:
        if not line.strip().startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        rows[cells[0]] = {
            "success": float(cells[1]),
            "mean_total_tokens": float(cells[2]),
            "mean_latency_s": float(cells[3]),
            "mean_model_calls": float(cells[4]),
            "mean_tool_calls": float(cells[5]),
        }
    return rows


def table_matches(readme, report):
    parsed = parse_main_table(readme)
    problems = []
    for name in SYSTEMS:
        if name not in report["systems"]:
            continue
        if name not in parsed:
            problems.append(f"нет строки {name}")
            continue
        block = report["systems"][name]
        for key, digits in METRIC_COLUMNS:
            got = parsed[name][key]
            expected = round(block[key], digits)
            if round(got, digits) != expected:
                problems.append(f"{name} {key}: в README {got}, в отчёте {expected}")
    return problems


def markdown_table(report):
    header = "| система | success | mean_total_tokens | mean_latency_s | mean_model_calls | mean_tool_calls |"
    sep = "| --- | --- | --- | --- | --- | --- |"
    lines = [header, sep]
    for name in SYSTEMS:
        block = report["systems"].get(name)
        if block is None:
            continue
        cells = [name]
        for key, digits in METRIC_COLUMNS:
            cells.append(f"{block[key]:.{digits}f}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
