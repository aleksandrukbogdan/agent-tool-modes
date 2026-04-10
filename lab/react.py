from lab.limits import REACT_STEPS
from lab.loop import run_tool_loop
from lab.prompts import REACT_SYSTEM


def run_react(client, question, dispatch, max_steps=REACT_STEPS):
    messages = [
        {"role": "system", "content": REACT_SYSTEM},
        {"role": "user", "content": question},
    ]
    return run_tool_loop(client, messages, dispatch, max_steps)
