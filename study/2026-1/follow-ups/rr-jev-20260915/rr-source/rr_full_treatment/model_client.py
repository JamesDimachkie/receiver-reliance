"""Bounded local Ollama calls; no remote routing or model acquisition."""
from __future__ import annotations

import json
import time
import urllib.request

from .host_facts import canonical, sha

BASE = "http://127.0.0.1:11434"
MODEL = "qwen3:14b"
MODEL_DIGEST = "bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8"
OPTIONS = {"temperature": 0, "num_ctx": 8192, "num_predict": 1536}


class InvalidModelResponse(RuntimeError):
    def __init__(self, message, raw_response):
        super().__init__(message)
        self.raw_response = raw_response


def get(path: str) -> dict:
    if path not in ("/api/tags", "/api/version", "/api/ps"):
        raise ValueError("Unregistered local metadata endpoint")
    with urllib.request.urlopen(BASE + path, timeout=15) as response:
        return json.loads(response.read())


def verify_model() -> dict:
    matches = [row for row in get("/api/tags")["models"] if row["name"] == MODEL]
    if len(matches) != 1 or matches[0]["digest"] != MODEL_DIGEST:
        raise RuntimeError("Installed model differs from the declared model")
    return {"version": get("/api/version"), "model": matches[0]}


def request_bytes(messages: list[dict], seed: int) -> bytes:
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise ValueError("Explicit nonnegative 31-bit decoding seed required")
    return canonical({"model": MODEL, "messages": messages, "stream": False,
                      "format": "json", "think": True, "keep_alive": "30m",
                      "options": {**OPTIONS, "seed": seed}})


def call(raw_request: bytes) -> dict:
    """One attempt only. Preserve the exact request and HTTP response separately."""
    start = time.time_ns()
    started = time.perf_counter_ns()
    request = urllib.request.Request(BASE + "/api/chat", data=raw_request,
                                    headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        raw_response = response.read(2_000_001)
    if len(raw_response) > 2_000_000:
        raise InvalidModelResponse("Local model response exceeded the prospective byte cap", raw_response)
    try:
        result = json.loads(raw_response)
    except (ValueError, TypeError) as error:
        raise InvalidModelResponse('Model returned an invalid response document', raw_response) from error
    if result.get("done") is not True or result.get("model") != MODEL:
        raise InvalidModelResponse("Incomplete or unexpected local model response", raw_response)
    text = result.get("message", {}).get("content")
    if type(text) is not str:
        raise InvalidModelResponse("Missing model response content", raw_response)
    return {"raw_request": raw_request, "raw_response": raw_response,
            "request_sha256": sha(raw_request), "response_sha256": sha(raw_response),
            "started_at_ns": start, "finished_at_ns": time.time_ns(),
            "wall_ns": time.perf_counter_ns() - started, "text": text,
            "metrics": {key: result.get(key) for key in
                        ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
                         "eval_count", "eval_duration", "done_reason")}}
