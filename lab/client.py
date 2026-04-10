import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class Completion:
    content: str
    tool_calls: list
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_message: dict = field(default_factory=dict)


class ChatClient:
    def __init__(self, base_url, model, timeout=120, temperature=0, seed=42):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.seed = seed
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.json_mode = True
        self.disable_thinking = "qwen3" in model.casefold()

    def reset_usage(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def complete(self, messages, tools=None, json_mode=False, max_tokens=1024):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            "seed": self.seed,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = False
        if json_mode and self.json_mode and not tools:
            payload["response_format"] = {"type": "json_object"}
        if self.disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        started = time.perf_counter()
        try:
            body = self._post(payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if json_mode and exc.code == 400 and "response_format" in detail:
                self.json_mode = False
                return self.complete(messages, tools=tools, json_mode=False, max_tokens=max_tokens)
            raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc
        except urllib.error.URLError as exc:
            if getattr(exc, "reason", None).__class__.__name__ == "TimeoutError":
                raise
            body = self._post(payload)
        _ = time.perf_counter() - started
        self.calls += 1
        message = body["choices"][0]["message"]
        usage = body.get("usage") or {}
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        calls = []
        for index, raw in enumerate(message.get("tool_calls") or []):
            function = raw.get("function") or {}
            arguments = function.get("arguments") if function.get("arguments") not in (None, "") else "{}"
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, ensure_ascii=False)
            calls.append(
                ToolCall(
                    id=raw.get("id") or f"call_{self.calls}_{index}",
                    name=function.get("name") or "",
                    arguments=arguments,
                )
            )
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        if not content and isinstance(message.get("reasoning"), str):
            content = message["reasoning"]
        return Completion(content, calls, prompt, completion, message)

    def _post(self, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def discover_model(base_url, timeout=15):
    request = urllib.request.Request(base_url.rstrip("/") + "/models")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    rows = body.get("data") or []
    if not rows:
        raise RuntimeError("vLLM не вернул ни одной модели")
    return rows[0]["id"]


class ScriptedClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.json_mode = True

    def reset_usage(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def complete(self, messages, tools=None, json_mode=False, max_tokens=1024):
        self.sent.append({"messages": messages, "tools": tools, "json_mode": json_mode})
        reply = self.replies.pop(0)
        self.calls += 1
        self.prompt_tokens += reply.prompt_tokens
        self.completion_tokens += reply.completion_tokens
        return reply


def reply(content, tool_calls=None, prompt_tokens=10, completion_tokens=5):
    calls = tool_calls or []
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in calls
        ]
    return Completion(content, calls, prompt_tokens, completion_tokens, message)
