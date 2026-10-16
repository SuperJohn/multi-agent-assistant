"""LLM backends. Simulated (default, zero keys), local Ollama, or any OpenAI-compatible endpoint.

Real backends fall back to the scripted output on any error, so a demo never breaks.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.request

OLLAMA_URL = os.environ.get("MAA_OLLAMA_URL", "http://localhost:11434")


def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=1.5) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []


def available_modes() -> dict[str, bool]:
    return {
        "simulated": True,
        "ollama": bool(ollama_models()),
        "openai": bool(os.environ.get("MAA_OPENAI_BASE_URL") and os.environ.get("MAA_OPENAI_API_KEY")),
    }


class LLM:
    def __init__(self, mode: str = "simulated", speed: float = 1.0):
        self.mode = mode
        self.speed = speed  # 0 = instant (tests), 1 = realistic pacing

    async def think(self, seconds: float) -> None:
        if self.speed > 0:
            await asyncio.sleep(seconds * self.speed)

    async def complete(self, system: str, prompt: str, scripted: str) -> str:
        if self.mode == "simulated":
            await self.think(0.8 + min(len(scripted), 400) / 250)
            return scripted
        try:
            return await asyncio.to_thread(self._call, system, prompt)
        except Exception as exc:  # graceful degradation
            return f"{scripted}\n\n(fallback: {self.mode} unavailable: {type(exc).__name__})"

    def _call(self, system: str, prompt: str) -> str:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        if self.mode == "ollama":
            model = os.environ.get("MAA_OLLAMA_MODEL") or (ollama_models() or ["llama3.2"])[0]
            r = _post(f"{OLLAMA_URL}/api/chat", {"model": model, "messages": msgs, "stream": False,
                                                 "options": {"num_predict": 220}}, timeout=120)
            return r["message"]["content"].strip()
        if self.mode == "openai":
            base = os.environ["MAA_OPENAI_BASE_URL"].rstrip("/")
            r = _post(f"{base}/chat/completions",
                      {"model": os.environ.get("MAA_OPENAI_MODEL", "gpt-4o-mini"), "messages": msgs, "max_tokens": 300},
                      headers={"Authorization": f"Bearer {os.environ['MAA_OPENAI_API_KEY']}"})
            return r["choices"][0]["message"]["content"].strip()
        raise ValueError(f"unknown mode {self.mode}")
