import json
from typing import TypedDict

from lab.client import ChatClient
from lab.jsonutil import parse_arguments
from lab.limits import REACT_STEPS
from lab.loop import coerce_calls, guarded, preview
from lab.prompts import REACT_SYSTEM
from lab.tools import execute


class LoopState(TypedDict):
    messages: list
    steps: int
    pred: str
    trace: list
    tool_calls: int
    tool_errors: int
    pending: list


class LangGraphReact:
    # Тот же текстовый протокол, что у своего ReAct, но цикл собран как StateGraph.
    # create_react_agent здесь не используется: он шлёт поле tools, а этот vLLM его отвергает.
    # Чекпоинт пишется после каждого узла. На одном saver висит много thread_id.

    def __init__(self, base_url, model_name, checkpointer=None):
        self.base_url = base_url
        self.model_name = model_name
        self.checkpointer = checkpointer if checkpointer is not None else _memory_saver()
        self._threads = 0

    def run(self, question, thread_id=None):
        self._threads += 1
        thread_id = thread_id or f"q{self._threads}"
        client = ChatClient(self.base_url, self.model_name)
        out = run_graph(
            client,
            [
                {"role": "system", "content": REACT_SYSTEM},
                {"role": "user", "content": question},
            ],
            execute,
            checkpointer=self.checkpointer,
            thread_id=thread_id,
        )
        return {
            "pred": out["pred"],
            "stop": out["stop"],
            "trace": out["trace"],
            "tool_calls": out["tool_calls"],
            "tool_errors": out["tool_errors"],
            "checkpoints": out["checkpoints"],
            "thread_id": out["thread_id"],
            "prompt_tokens": client.prompt_tokens,
            "completion_tokens": client.completion_tokens,
            "model_calls": client.calls,
        }


def _memory_saver():
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()


def run_graph(
    client,
    messages,
    dispatch,
    max_steps=REACT_STEPS,
    *,
    checkpointer=None,
    thread_id="main",
    interrupt_before=None,
    resume=False,
):
    from langgraph.graph import END, START, StateGraph

    def agent(state):
        if state["steps"] >= max_steps:
            return {"pending": [], "pred": state.get("pred") or ""}
        completion = client.complete(state["messages"], tools=None, json_mode=False)
        content, calls = coerce_calls(completion.content, completion.tool_calls)
        trace = list(state["trace"])
        trace.append(
            {
                "kind": "model",
                "preview": preview(content if content else completion.content),
                "tool_names": [call.name for call in calls],
            }
        )
        if not calls:
            return {
                "steps": state["steps"] + 1,
                "pred": content or "",
                "trace": trace,
                "pending": [],
            }
        pending = [{"id": call.id, "name": call.name, "arguments": call.arguments} for call in calls]
        messages_out = list(state["messages"])
        messages_out.append({"role": "assistant", "content": completion.content or ""})
        return {
            "messages": messages_out,
            "steps": state["steps"] + 1,
            "trace": trace,
            "pending": pending,
            "pred": "",
        }

    def tools(state):
        messages_out = list(state["messages"])
        trace = list(state["trace"])
        tool_calls = state["tool_calls"]
        tool_errors = state["tool_errors"]
        notes = []
        for call in state["pending"]:
            tool_calls += 1
            arguments, error = parse_arguments(call["arguments"])
            if error:
                result = {"ok": False, "error": error, "detail": preview(call["arguments"])}
            elif not call["name"]:
                result = {"ok": False, "error": "unknown_tool", "detail": ""}
            else:
                result = guarded(dispatch, call["name"], arguments)
            if not result.get("ok"):
                tool_errors += 1
            trace.append(
                {
                    "kind": "tool",
                    "name": call["name"],
                    "ok": bool(result.get("ok")),
                    "error": result.get("error") or "",
                    "preview": preview(result),
                }
            )
            notes.append(call["name"] + ": " + json.dumps(result, ensure_ascii=False))
        messages_out.append({"role": "user", "content": "Наблюдения:\n" + "\n".join(notes)})
        return {
            "messages": messages_out,
            "trace": trace,
            "tool_calls": tool_calls,
            "tool_errors": tool_errors,
            "pending": [],
        }

    def route(state):
        if state.get("pending"):
            return "tools"
        return END

    graph = StateGraph(LoopState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    if checkpointer is None:
        checkpointer = _memory_saver()
    compile_kwargs = {"checkpointer": checkpointer}
    if interrupt_before:
        compile_kwargs["interrupt_before"] = list(interrupt_before)
    app = graph.compile(**compile_kwargs)
    config = {
        "recursion_limit": max_steps * 4 + 4,
        "configurable": {"thread_id": thread_id},
    }
    initial = {
        "messages": messages,
        "steps": 0,
        "pred": "",
        "trace": [],
        "tool_calls": 0,
        "tool_errors": 0,
        "pending": [],
    }
    state = app.invoke(None if resume else initial, config)
    snapshot = app.get_state(config)
    history = list(app.get_state_history(config))
    pred = (state or {}).get("pred") or ""
    nxt = list(snapshot.next or ())
    if nxt:
        stop = "interrupt"
    elif pred.strip():
        stop = "answer"
    else:
        stop = "step_limit"
    return {
        "pred": pred,
        "stop": stop,
        "trace": (state or {}).get("trace") or [],
        "tool_calls": (state or {}).get("tool_calls") or 0,
        "tool_errors": (state or {}).get("tool_errors") or 0,
        "checkpoints": len(history),
        "thread_id": thread_id,
        "next": nxt,
        "checkpointer": checkpointer,
        "app": app,
    }
