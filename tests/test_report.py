import json
from pathlib import Path

from lab.metrics import summarize
from lab.report import markdown_table, parse_main_table, table_matches


def test_median_of_even_length_is_the_mean_of_two_central_values():
    rows = []
    for latency, ok in ((1.0, True), (3.0, False), (4.0, True), (10.0, True)):
        rows.append(
            {
                "family": "calc",
                "ok": ok,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "latency_s": latency,
                "model_calls": 2,
                "tool_calls": 1,
                "tool_errors": 0,
            }
        )
    stats = summarize(rows)
    assert stats["success"] == 0.75
    assert stats["median_latency_s"] == 3.5
    assert stats["mean_total_tokens"] == 15
    assert stats["by_family"]["calc"]["n"] == 4


def test_readme_table_is_checked_to_the_printed_digits():
    report = {
        "systems": {
            "workflow": {
                "success": 0.75,
                "mean_total_tokens": 15.04,
                "mean_latency_s": 1.2346,
                "mean_model_calls": 2.0,
                "mean_tool_calls": 1.0,
            }
        }
    }
    readme = markdown_table(report) + "\n"
    assert table_matches(readme, report) == []
    broken = readme.replace("0.7500", "0.7501")
    assert table_matches(broken, report)


def test_readme_table_matches_saved_report():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    report = json.loads((root / "reports" / "dev.json").read_text(encoding="utf-8"))
    problems = table_matches(readme, report)
    assert not problems, problems
    parsed = parse_main_table(readme)
    assert set(parsed) >= set(report["systems"])
