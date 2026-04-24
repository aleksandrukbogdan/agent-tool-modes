import hashlib
import json
import os
import time
from pathlib import Path

from lab.client import ChatClient, discover_model
from lab.limits import PLAN_MODEL_CALLS, REACT_STEPS, WORKFLOW_MODEL_CALLS
from lab.metrics import summarize
from lab.plan import run_plan
from lab.prompts import REACT_SYSTEM
from lab.react import run_react
from lab.report import SYSTEMS, write_json
from lab.score import match_answer
from lab.tasks import TASKS
from lab.tools import execute
from lab.workflow import run_workflow

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "dev.json"


def tasks_fingerprint(tasks=None):
    rows = TASKS if tasks is None else tasks
    blob = json.dumps(
        [{"id": task.id, "family": task.family, "question": task.question, "gold": task.gold} for task in rows],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def run_dev(
    base_url=None,
    model=None,
    systems=SYSTEMS,
    limit=0,
    resume=False,
    tasks=None,
    report_path=None,
    failures_name="failures.jsonl",
):
    base_url = base_url or os.environ.get("AGENT_BASE_URL", "http://10.109.50.250:1212/v1")
    model = model or os.environ.get("AGENT_MODEL") or discover_model(base_url)
    task_list = list(TASKS if tasks is None else tasks)
    report_path = Path(report_path) if report_path else REPORT
    selected = list(task_list)
    if limit:
        selected = selected[:limit]
    client = ChatClient(base_url, model)
    library = None
    if "react_lg" in systems:
        from lab.library import LangGraphReact

        library = LangGraphReact(base_url, model)
    previous = {}
    if resume and report_path.exists():
        previous = json.loads(report_path.read_text(encoding="utf-8")).get("systems", {})
    systems_out = {}
    for name in systems:
        done = {row["id"]: row for row in previous.get(name, {}).get("tasks", [])} if resume else {}
        rows = []
        for task in selected:
            if task.id in done:
                rows.append(done[task.id])
                print(f"{task.id} {name} cached", flush=True)
                continue
            try:
                row = run_task(name, task, client, library)
            except Exception as exc:
                row = {
                    "id": task.id,
                    "family": task.family,
                    "question": task.question,
                    "gold": task.gold,
                    "pred": "",
                    "ok": False,
                    "prompt_tokens": client.prompt_tokens,
                    "completion_tokens": client.completion_tokens,
                    "latency_s": 0.0,
                    "model_calls": client.calls,
                    "tool_calls": 0,
                    "tool_errors": 0,
                    "stop": "error",
                    "trace": [{"kind": "model", "preview": f"{type(exc).__name__}: {exc}"[:1500], "tool_names": []}],
                }
            rows.append(row)
            mark = "OK" if row["ok"] else "MISS"
            print(
                f"{task.id} {name} {mark} calls={row['model_calls']} tools={row['tool_calls']} "
                f"tok={row['prompt_tokens'] + row['completion_tokens']} lat={row['latency_s']:.2f}",
                flush=True,
            )
            systems_out[name] = {**summarize(rows), "tasks": rows}
            _write(model, base_url, systems_out, task_list, report_path, partial=True)
        systems_out[name] = {**summarize(rows), "tasks": rows}
    payload = _payload(model, base_url, systems_out, task_list, partial=False)
    write_json(report_path, payload)
    _write_failures(payload, task_list, ROOT / "reports" / failures_name)
    return payload


def run_task(name, task, client, library):
    client.reset_usage()
    started = time.perf_counter()
    if name == "workflow":
        out = run_workflow(client, task, execute)
    elif name == "react":
        out = run_react(client, task.question, execute, max_steps=REACT_STEPS)
    elif name == "plan":
        out = run_plan(client, task.question, execute, max_calls=PLAN_MODEL_CALLS)
    elif name == "react_lg":
        out = library.run(task.question)
    else:
        raise ValueError(name)
    latency = time.perf_counter() - started
    pred = out.get("pred") or ""
    row = {
        "id": task.id,
        "family": task.family,
        "question": task.question,
        "gold": task.gold,
        "pred": pred,
        "ok": match_answer(pred, task.gold),
        "prompt_tokens": out.get("prompt_tokens", client.prompt_tokens),
        "completion_tokens": out.get("completion_tokens", client.completion_tokens),
        "latency_s": latency,
        "model_calls": out.get("model_calls", client.calls),
        "tool_calls": out.get("tool_calls", 0),
        "tool_errors": out.get("tool_errors", 0),
        "stop": out.get("stop", ""),
        "trace": out.get("trace", []),
    }
    if "checkpoints" in out:
        row["checkpoints"] = out["checkpoints"]
        row["thread_id"] = out["thread_id"]
    return row


def _payload(model, base_url, systems_out, task_list, partial):
    return {
        "model": model,
        "base_url": base_url,
        "temperature": 0,
        "seed": 42,
        "n_tasks": len(task_list),
        "tasks_sha256": tasks_fingerprint(task_list),
        "prompt_sha256": hashlib.sha256(REACT_SYSTEM.encode("utf-8")).hexdigest(),
        "limits": {
            "react_steps": REACT_STEPS,
            "plan_model_calls": PLAN_MODEL_CALLS,
            "workflow_model_calls": WORKFLOW_MODEL_CALLS,
        },
        "partial": partial,
        "systems": systems_out,
    }


def _write(model, base_url, systems_out, task_list, report_path, partial):
    write_json(report_path, _payload(model, base_url, systems_out, task_list, partial))


def _write_failures(payload, task_list, path):
    lines = []
    systems = payload["systems"]
    ids = [task.id for task in task_list]
    for task_id in ids:
        row = {"id": task_id}
        failed = False
        for name, block in systems.items():
            found = next((item for item in block["tasks"] if item["id"] == task_id), None)
            if found is None:
                continue
            row[name] = {
                "ok": found["ok"],
                "pred": found["pred"],
                "gold": found["gold"],
                "stop": found["stop"],
                "tool_errors": found["tool_errors"],
            }
            if not found["ok"]:
                failed = True
        if failed:
            lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
