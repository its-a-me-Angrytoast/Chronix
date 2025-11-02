"""AI client abstraction for Chronix.

Provides an async, production-capable HTTP adapter for AI providers with
deterministic mock fallbacks for local dev and tests. Supported providers:
 - GEMINI: provide GEMINI_API_URL and GEMINI_API_KEY
 - OPENAI-compatible: provide OPENAI_API_KEY and optional OPENAI_API_URL

If no provider is configured, the client returns deterministic mock responses
to keep tests and local development reliable.
"""
from __future__ import annotations

import os
import json
import asyncio
from typing import Optional, Dict, Any
import random

# optional aiohttp import; keep import-safe for environments without the lib
try:
    import aiohttp
    from aiohttp import ClientTimeout
    HAVE_AIOHTTP = True
except Exception:  # pragma: no cover - optional
    aiohttp = None
    ClientTimeout = None
    HAVE_AIOHTTP = False


def _has_gemini_config() -> bool:
    return bool(os.getenv("GEMINI_API_KEY")) and bool(os.getenv("GEMINI_API_URL"))


def _has_openai_config() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _mock_response(prompt: str, mode: str = "chat", temperature: float = 0.7, max_tokens: int = 256, seed: Optional[int] = None) -> Dict[str, Any]:
    rng = random.Random(seed if seed is not None else 0)
    short = prompt.strip().replace("\n", " ")[:160]
    variant = rng.randint(0, 9999)
    text = f"[Mock {mode} response #{variant}] {short}"
    return {"text": text, "meta": {"seed": seed, "temperature": temperature, "max_tokens": max_tokens}}


async def async_generate_text(prompt: str, mode: str = "chat", temperature: float = 0.7, max_tokens: int = 256, seed: Optional[int] = None, timeout: int = 10) -> Dict[str, Any]:
    """Asynchronously generate text using configured provider.

    Priority:
      1. GEMINI if configured
      2. OPENAI-compatible if configured
      3. Mock fallback
    """
    # mock fallback when no provider configured
    if not _has_gemini_config() and not _has_openai_config():
        return _mock_response(prompt, mode, temperature, max_tokens, seed)

    if not HAVE_AIOHTTP:
        raise RuntimeError("aiohttp is required for remote AI providers. Please install requirements.txt")

    # GEMINI provider (user-supplied URL)
    if _has_gemini_config():
        url = os.getenv("GEMINI_API_URL")
        key = os.getenv("GEMINI_API_KEY")
        payload = {"prompt": prompt, "temperature": temperature, "max_tokens": max_tokens, "mode": mode}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        timeout_obj = ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as sess:
            for attempt in range(2):
                try:
                    async with sess.post(url, json=payload, headers=headers) as resp:
                        txt = await resp.text()
                        try:
                            data = json.loads(txt)
                        except Exception:
                            data = {"raw": txt}
                        # attempt to extract a human-readable text field
                        if isinstance(data, dict):
                            if "candidates" in data and isinstance(data["candidates"], list) and data["candidates"]:
                                text = data["candidates"][0].get("text") or data["candidates"][0].get("content")
                            elif "output" in data and isinstance(data["output"], list) and data["output"]:
                                text = data["output"][0].get("content") if isinstance(data["output"][0], dict) else str(data["output"][0])
                            else:
                                text = data.get("text") or data.get("content") or json.dumps(data)
                        else:
                            text = str(data)
                        return {"text": text, "meta": {"provider": "gemini", "status": getattr(resp, 'status', None)}}
                except Exception as exc:
                    if attempt == 1:
                        return {"text": f"[fallback-mock] {prompt[:120]}", "meta": {"error": str(exc)}}
                    await asyncio.sleep(0.5)

    # OpenAI-compatible provider
    if _has_openai_config():
        key = os.getenv("OPENAI_API_KEY")
        url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": os.getenv("OPENAI_MODEL", "gpt-4o"), "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens}
        timeout_obj = ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as sess:
            try:
                async with sess.post(url, json=body, headers=headers) as resp:
                    data = await resp.json()
                    if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                        content = data["choices"][0].get("message", {}).get("content") or data["choices"][0].get("text")
                    else:
                        content = json.dumps(data)
                    return {"text": content, "meta": {"provider": "openai", "status": getattr(resp, 'status', None)}}
            except Exception as exc:
                return {"text": f"[fallback-mock] {prompt[:120]}", "meta": {"error": str(exc)}}


def generate_text(prompt: str, mode: str = "chat", temperature: float = 0.7, max_tokens: int = 256, seed: Optional[int] = None) -> Dict[str, Any]:
    """Synchronous wrapper around async_generate_text for compatibility.

    If no event loop is running, this executes the async function directly.
    In an already-running event loop, this will fall back to the deterministic
    mock to avoid deadlocks in synchronous contexts.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        if not (_has_gemini_config() or _has_openai_config()):
            return _mock_response(prompt, mode, temperature, max_tokens, seed)
        return asyncio.run(async_generate_text(prompt, mode, temperature, max_tokens, seed))
    else:
        return asyncio.run(async_generate_text(prompt, mode, temperature, max_tokens, seed))

