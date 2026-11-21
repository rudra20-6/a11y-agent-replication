"""Thin LLM wrapper: JSON answers, optional images, retries, optional on-disk answer cache (A11Y_NO_CACHE=1 turns it
off), token accounting. Endpoints are set up in providers.py."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import random
import re
import time
from collections import defaultdict
from pathlib import Path

from .config import RUNS, SETTINGS

CACHE = RUNS / ".cache" / "llm"


class LLMError(RuntimeError):
    pass


class QuotaExhausted(LLMError):
    """Every endpoint for this model is rate limited for a long time: retrying won't help until the limit lifts."""


class Usage:
    def __init__(self):
        self.by_role = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "cached": 0})
        self.by_endpoint: dict = {}
        self._lock = threading.Lock()

    def add(self, role: str, inp: int, out: int, cached: bool) -> None:
        with self._lock:
            self._add(role, inp, out, cached)

    def _add(self, role: str, inp: int, out: int, cached: bool) -> None:
        r = self.by_role[role]
        r["calls"] += 1
        r["cached"] += int(cached)
        if not cached:
            r["input"] += inp
            r["output"] += out

    def served(self, endpoint: str, model: str, exact: bool) -> None:
        with self._lock:
            k = endpoint if exact else f"{endpoint} (substitute: {model})"
            self.by_endpoint[k] = self.by_endpoint.get(k, 0) + 1

    def summary(self) -> dict:
        out = {k: dict(v) for k, v in self.by_role.items()}
        if self.by_endpoint:
            out["endpoints"] = dict(self.by_endpoint)  # which endpoint answered how many calls
        return out


USAGE = Usage()
FALLBACKS: list = []  # (role, primary model, fallback model) each time the primary was overloaded

# Live reporting. The pipeline sets ON_EVENT (its EventLog.emit) and tags each thread with context(task=, profile=),
# so a slow or retried call shows up in the run log as "REF on t1 is waiting / retrying", not as silence.
ON_EVENT = None
_CTX = threading.local()


def context(**kw) -> None:
    _CTX.data = kw


def _emit(kind: str, **data) -> None:
    if ON_EVENT is None:
        return
    try:
        ON_EVENT(kind, **{**getattr(_CTX, "data", {}), **data})
    except Exception:
        pass


def _estimate_tokens(system: str, prompt: str, images: list[bytes]) -> int:
    """Rough input size, erring high: ~3.5 characters per token, plus ~300 tokens per screenshot."""
    return int((len(system) + len(prompt)) / 3.5) + 300 * len(images)


def _reason(msg: str) -> str:
    """Short, readable cause of a failed call."""
    for code, text in (("429", "rate limited (429)"), ("504", "server timeout (504)"), ("503", "server overloaded (503)"),
                       ("500", "server error (500)"), ("timed out", "no reply within 120 s"), ("Expecting", "unreadable reply")):
        if code in msg:
            return text
    return msg.splitlines()[0][:80] if msg else "unknown error"


class LLM:
    def __init__(self, model: str | None = None, role: str = "nav", use_cache: bool = True):
        from .providers import POOL
        if not POOL.endpoints:
            raise LLMError("No API key. Put OPENROUTER_API_KEY in .env at the package root (see .env.example).")
        self.pool = POOL
        self.model = model or {"judge": SETTINGS.judge_model, "planner": SETTINGS.planner_model}.get(role, SETTINGS.nav_model)
        self.role = role
        # A11Y_NO_CACHE=1 for repeat runs: otherwise identical prompts get the first run's answers back, and a "second
        # run" partly replays the first instead of being an independent sample.
        self.use_cache = use_cache and os.environ.get("A11Y_NO_CACHE") != "1"

    def _key(self, system: str, prompt: str, images: list[bytes]) -> str:
        h = hashlib.sha256()
        for part in (self.model, system, prompt, *[hashlib.sha256(i).hexdigest() for i in images]):
            h.update(part.encode("utf-8") if isinstance(part, str) else part)
        return h.hexdigest()

    def json(self, system: str, prompt: str, images: list[bytes] | None = None, temperature: float = 0.0,
             max_retries: int = 8, json_mode: bool = True) -> dict:
        """Ask for a JSON object. Falls back to the navigation model if this model stays overloaded.
        json_mode=False lets the model reason in plain text first; the last JSON object in the reply is used."""
        try:
            return self._json(system, prompt, images, temperature, max_retries, json_mode)
        except QuotaExhausted:
            raise
        except LLMError:
            fb = SETTINGS.nav_model
            if fb == self.model:
                raise
            FALLBACKS.append((self.role, self.model, fb))
            primary, self.model = self.model, fb
            try:
                return self._json(system, prompt, images, temperature, max_retries, json_mode)
            finally:
                self.model = primary

    def _json(self, system: str, prompt: str, images: list[bytes] | None, temperature: float, max_retries: int,
              json_mode: bool = True) -> dict:
        from .providers import AllCoolingDown

        images = images or []
        key = self._key(system, prompt, images)
        path = CACHE / f"{key}.json"
        if self.use_cache and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            USAGE.add(self.role, 0, 0, cached=True)
            return data["answer"]

        last, temp = None, temperature
        t_call = time.time()
        _emit("llm_start", role=self.role, model=self.model, prompt_kb=round(len(prompt) / 1024, 1), images=len(images))
        # With several endpoints, a rate-limited one is set aside and the next one tried at once.
        tries = max_retries + max(0, len(self.pool.endpoints) - 1)
        for attempt in range(tries):
            try:
                ep, served, exact = self.pool.acquire(self.model, on_wait=lambda s: _emit(
                    "llm_retry", role=self.role, attempt=attempt + 1, of=tries, reason="all keys rate limited", wait=round(s, 1)),
                    images=bool(images), tokens=_estimate_tokens(system, prompt, images))
            except AllCoolingDown as e:
                raise QuotaExhausted(str(e)) from e
            t_try = time.time()
            try:
                text, inp, out = ep.call(served, system, prompt, images, temp, json_mode)
                answer = parse_json(text)
                USAGE.add(self.role, inp, out, cached=False)
                USAGE.served(ep.name, served, exact)
                self.pool.ok(ep)
                if exact and self.use_cache:  # only the requested model's answers, and never from a no-cache run
                    CACHE.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"model": self.model, "endpoint": ep.name, "answer": answer, "tokens": [inp, out]},
                                               ensure_ascii=False), encoding="utf-8")
                if attempt or time.time() - t_call > 20:
                    _emit("llm_ok", role=self.role, secs=round(time.time() - t_call, 1), attempts=attempt + 1, endpoint=ep.name)
                return answer
            except Exception as e:  # rate limits, transient server errors, bad JSON
                last = e
                msg = str(e)
                wait = 0.0
                # A daily allocation message from Cloudflare: the endpoint is re-tried hourly.
                cf_daily = ep.kind == "cloudflare" and any(c in msg.lower() for c in ("4006", "daily allocation"))
                # A revoked or invalid key (401/403) never recovers: rest it so other endpoints take its calls.
                dead = len(self.pool.endpoints) > 1 and any(c in msg for c in (
                    "PERMISSION_DENIED", "API_KEY_INVALID", "API key not valid", "401"))
                if dead:
                    self.pool.cool(ep, 7 * 24 * 3600)
                elif "429" in msg or "RESOURCE_EXHAUSTED" in msg or cf_daily:
                    daily = "PerDay" in msg or "per-day" in msg or "per day" in msg.lower() or (
                        "limit: 0" in msg and "PerMinute" not in msg)
                    secs = min(3600.0, _secs_to_utc_midnight()) if cf_daily else (
                        _retry_seconds(msg) or _retry_after(e) or (3 * 3600 if daily else 60))
                    self.pool.cool(ep, secs)   # this endpoint rests for the time the provider asks
                else:
                    # Transient server errors (500/503/504, timeouts): with one endpoint, back off and retry; with
                    # several, rest this one briefly and move on.
                    transient = any(c in msg for c in ("500", "503", "504", "timed out", "Connection", "getaddrinfo"))
                    if len(self.pool.endpoints) > 1 and images and "timed out" in msg:
                        # An endpoint that times out on screenshots is kept for text calls; images go elsewhere.
                        self.pool.no_images(ep)
                    elif len(self.pool.endpoints) > 1 and transient:
                        self.pool.failed(ep, timeout="timed out" in msg)
                    else:
                        wait = 1.5 + random.random() if (transient and attempt < 3) else min(60, (2 ** attempt) * 3 + random.random())
                unreadable = isinstance(e, json.JSONDecodeError)   # at temperature 0 the same reply would come back
                if unreadable or "504" in msg or "timed out" in msg or ("500" in msg and attempt >= 2):
                    # A 504 (or a client timeout) on a long prompt repeats if the model makes the same long generation
                    # every time; at temperature 0 it does. Retry with a little randomness instead. Same for a 500 that
                    # survives the quick retries.
                    temp = max(temperature, 0.4)
                if attempt + 1 < tries:
                    _emit("llm_retry", role=self.role, attempt=attempt + 1, of=tries, reason=_reason(msg), endpoint=ep.name,
                          took=round(time.time() - t_try, 1), wait=round(wait, 1))
                    if wait:
                        time.sleep(wait)
        _emit("llm_failed", role=self.role, attempts=tries, reason=_reason(str(last)), secs=round(time.time() - t_call, 1))
        raise LLMError(f"model call failed after {tries} tries: {last}")

    def list_models(self) -> list[str]:
        """Models the first Google key can use."""
        from google import genai
        ep = next(e for e in self.pool.endpoints if e.kind == "gemini")
        client = genai.Client(api_key=ep.key)  # keep a reference: a client freed mid-listing closes its connection
        return [m.name for m in client.models.list()]


def _retry_seconds(msg: str) -> float | None:
    m = re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", msg)
    if not m:
        return None
    h, mi, se = m.group(1), m.group(2), m.group(3)
    return int(h or 0) * 3600 + int(mi or 0) * 60 + float(se)


def _secs_to_utc_midnight() -> float:
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    return (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - now).total_seconds() + 5


def _retry_after(e: Exception) -> float | None:
    """Seconds from an HTTP Retry-After header (OpenAI-compatible providers), if there is one."""
    try:
        v = e.response.headers.get("retry-after")
        return float(v) if v else None
    except Exception:
        return None


def _retry_hint(msg: str) -> str:
    s = _retry_seconds(msg)
    return f"retry in {int(s // 60)} min" if s else "see https://ai.dev/rate-limit"


def parse_json(text: str) -> dict:
    text = text.strip()
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if blocks:  # reasoning followed by a fenced JSON block: take the last one
        return json.loads(blocks[-1])
    if text.startswith("```"):
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as first_error:
        # The first complete object wins, whatever follows it: a reply can contain one JSON object followed by another.
        decoder = json.JSONDecoder()
        for m in re.finditer(r"\{", text):
            try:
                obj, _ = decoder.raw_decode(text, m.start())
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
        raise first_error
