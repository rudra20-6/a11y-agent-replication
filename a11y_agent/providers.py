"""Rolling pool of free-tier LLM endpoints (D71). Calls rotate across every key that serves the requested model.

Keys go in a11y-agent/.env (git-ignored; never commit or print them):
  GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3 ...   Google AI Studio, one key per Google account
  OPENROUTER_API_KEY                                     OpenRouter (free model ids end in ':free')
  CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN           Cloudflare Workers AI; a second account is the same two
  CLOUDFLARE_ACCOUNT_ID_2 + CLOUDFLARE_API_TOKEN_2       names ending _2 (each id pairs with the token of its suffix)
  NVIDIA_API_KEY                                         NVIDIA NIM, build.nvidia.com ('nvapi-...')

A call names a canonical model (e.g. gemma-4-26b-a4b-it). Only endpoints serving exactly that model are used, so every
answer in an experiment comes from the same model. A11Y_ALLOW_MIXED=1 also lets other endpoints answer with their
substitute model (NIM has Gemma 4 31B, not 26B): for quick dashboard runs only; every substitution is counted in the
usage summary, and substitute answers are never written to the shared cache.

Pacing (requests per minute, per endpoint): A11Y_RPM (Google keys; measured limit 30), A11Y_RPM_OPENROUTER (documented
20/min and 50/day below $10 of credit), A11Y_RPM_CLOUDFLARE (documented 300/min; the real limit is 10,000 neurons a
day per account, about 11 benchmark units), A11Y_RPM_NIM (about 40/min, unofficial). A rate-limited endpoint cools
down for as long as the provider says (or 60 s; a daily cap: until it resets) while the others carry on.
"""

from __future__ import annotations

import base64
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from . import config as _config  # noqa: F401  loads .env into os.environ; the pool below reads the keys at import time

# Which canonical models each provider serves, under its own model id.
OPENROUTER_MODELS = {"gemma-4-26b-a4b-it": "google/gemma-4-26b-a4b-it:free", "gemma-4-31b-it": "google/gemma-4-31b-it:free",
                     # second model (11 Nov 2026): paid only, no free copy; run with A11Y_KEYS=openrouter_paid
                     "mistral-small-3.2-24b-instruct": "mistralai/mistral-small-3.2-24b-instruct",
                     "qwen3-vl-30b-a3b-instruct": "qwen/qwen3-vl-30b-a3b-instruct"}
# Paid route: A11Y_OPENROUTER_PAID=1 uses the same model without ":free" (no daily cap). Optionally,
# A11Y_OPENROUTER_PROVIDER=<provider slug> pins one OpenRouter provider with no fallback.
# Mixed (D92): A11Y_OPENROUTER_MIX=1 adds both, "openrouter" (free) and "openrouter_paid"; the free one is always
# preferred, and the paid one answers while the free one rests (its 20/min or 1,000/day limit).
OPENROUTER_PAID_MODELS = {k: v.removesuffix(":free") for k, v in OPENROUTER_MODELS.items()}
NIM_MODELS = {"gemma-4-31b-it": "google/gemma-4-31b-it"}
CLOUDFLARE_MODELS = {"gemma-4-26b-a4b-it": "@cf/google/gemma-4-26b-a4b-it"}
SUBSTITUTE = {"openrouter": lambda: os.environ.get("A11Y_OPENROUTER_MODEL") or "google/gemma-4-26b-a4b-it:free",
              "nim": lambda: os.environ.get("A11Y_NIM_MODEL") or "google/gemma-4-31b-it"}


@dataclass
class Endpoint:
    name: str                 # "gemini#1", "cloudflare#2", "nim": shown in logs and the usage summary, never the key
    kind: str                 # gemini | openrouter | cloudflare | nim
    key: str = field(repr=False)
    rpm: float
    account: str = ""         # Cloudflare account id (part of its URL, not a secret)
    next_slot: float = 0.0
    cooldown_until: float = 0.0
    fails: int = 0            # consecutive server errors/timeouts; reset by a success
    no_images_until: float = 0.0   # failed a screenshot call: text only until then (D77)
    max_input_tokens: int = 0      # largest single prompt this key can take (0: no limit we know of) (D81)
    paid: bool = False             # OpenRouter paid model ids (no ":free"); used only when free ones rest (D92)
    pin: str = ""                  # OpenRouter host pinned with no fallback (D87, D91)
    _client: object = field(default=None, repr=False)
    _no_json_mode: bool = False

    def model_for(self, canonical: str, allow_mixed: bool) -> tuple[str, bool] | None:
        """(the provider's model id, whether it is the same model) or None if this endpoint can't serve it."""
        if self.kind == "gemini":
            return None if "/" in canonical else (canonical, True)   # vendor/model ids are OpenRouter's
        if self.kind == "openrouter" and "/" in canonical:   # an OpenRouter id (vendor/model) is served as named (D87)
            return canonical, True
        served = {"openrouter": OPENROUTER_PAID_MODELS if self.paid else OPENROUTER_MODELS, "nim": NIM_MODELS, "cloudflare": CLOUDFLARE_MODELS}[self.kind].get(canonical)
        if served:
            return served, True
        sub = SUBSTITUTE.get(self.kind)   # Cloudflare has no substitute: it answers only with the model asked for
        return (sub(), False) if (allow_mixed and sub) else None

    def call(self, model: str, system: str, prompt: str, images: list[bytes], temperature: float,
             json_mode: bool) -> tuple[str, int, int]:
        """Returns (text, input tokens, output tokens). Raises the provider's error; the caller classifies it."""
        if self.kind == "gemini":
            from google import genai
            from google.genai import types
            if self._client is None:
                # Without a timeout a stuck HTTP call can hang a run forever (it happened once); 120 s per call.
                self._client = genai.Client(api_key=self.key, http_options=types.HttpOptions(timeout=120_000))
            parts = [types.Part.from_text(text=prompt)] + [types.Part.from_bytes(data=i, mime_type="image/png") for i in images]
            config = types.GenerateContentConfig(system_instruction=system, temperature=temperature,
                                                 response_mime_type="application/json" if json_mode else None)
            resp = self._client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                                                        config=config)
            um = resp.usage_metadata
            return (resp.text or "", getattr(um, "prompt_token_count", 0) or 0,
                    (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0))

        from openai import OpenAI
        if self._client is None:
            base = {"openrouter": "https://openrouter.ai/api/v1",
                    "cloudflare": f"https://api.cloudflare.com/client/v4/accounts/{self.account}/ai/v1",
                    "nim": "https://integrate.api.nvidia.com/v1"}[self.kind]
            headers = {"X-Title": "a11y-agent research"} if self.kind == "openrouter" else None
            self._client = OpenAI(base_url=base, api_key=self.key, timeout=120, max_retries=0, default_headers=headers)
        content = [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(i).decode()}} for i in images]
        # 11 Nov 2026: Novita (Qwen3-VL) rejects a plain-string user message that contains any URL (400 "invalid
        # request"), but accepts the same text as a text part. A11Y_TEXT_AS_PARTS=1 sends text-only prompts that way;
        # the text the model reads is identical. Off by default, so the Gemma runs are unchanged.
        parts = bool(images) or os.environ.get("A11Y_TEXT_AS_PARTS") == "1"
        kw = dict(model=model, temperature=temperature, max_tokens=4096,
                  messages=[{"role": "system", "content": system}, {"role": "user", "content": content if parts else prompt}])
        if json_mode and not self._no_json_mode:
            kw["response_format"] = {"type": "json_object"}
        if self.kind == "openrouter" and self.pin:
            kw["extra_body"] = {"provider": {"order": [self.pin], "allow_fallbacks": False}}
        try:
            resp = self._client.chat.completions.create(**kw)
        except Exception as e:
            if "response_format" in kw and "400" in str(e):  # the endpoint doesn't take JSON mode: ask in plain text
                self._no_json_mode = True
                kw.pop("response_format")
                resp = self._client.chat.completions.create(**kw)
            else:
                raise
        u = resp.usage
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        return text, getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0


def _gemini_keys() -> list[str]:
    keys = [os.environ.get("GEMINI_API_KEY", "")]
    keys += [os.environ[k] for k in sorted(os.environ, key=lambda k: int(re.sub(r"\D", "", k) or 0))
             if re.fullmatch(r"GEMINI_API_KEY_\d+", k)]
    seen, out = set(), []
    for k in (k.strip() for k in keys):
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def endpoints_from_env() -> list[Endpoint]:
    gem_rpm = float(os.environ.get("A11Y_RPM") or 28)
    # Google's free tier allows 16,000 input tokens per minute per key for Gemma (quota
    # GenerateContentInputTokensPerModelPerMinute-FreeTier, seen 3 Nov). The validator's ~59 KB prompt is over that on
    # its own, so Google refused it every time; such calls go to the other providers (D81).
    gem_max = int(os.environ.get("A11Y_GEMINI_MAX_INPUT") or 12000)
    eps = [Endpoint(f"gemini#{i}", "gemini", k, gem_rpm, max_input_tokens=gem_max) for i, k in enumerate(_gemini_keys(), 1)]
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        key, pin = os.environ["OPENROUTER_API_KEY"].strip(), os.environ.get("A11Y_OPENROUTER_PROVIDER", "").strip()
        rpm = float(os.environ.get("A11Y_RPM_OPENROUTER") or 18)
        if os.environ.get("A11Y_OPENROUTER_MIX") == "1":
            eps.append(Endpoint("openrouter", "openrouter", key, float(os.environ.get("A11Y_RPM_OPENROUTER_FREE") or 10)))
            eps.append(Endpoint("openrouter_paid", "openrouter", key, rpm, paid=True, pin=pin))
        elif os.environ.get("A11Y_OPENROUTER_PAID") == "1":
            eps.append(Endpoint("openrouter", "openrouter", key, rpm, paid=True, pin=pin))
        else:
            eps.append(Endpoint("openrouter", "openrouter", key, rpm))
    cf_rpm = float(os.environ.get("A11Y_RPM_CLOUDFLARE") or 100)
    seen_accounts = set()
    for suffix in [""] + sorted({m.group(0) for k in os.environ if (m := re.search(r"_\d+$", k)) and k.startswith("CLOUDFLARE_")}):
        acct = os.environ.get(f"CLOUDFLARE_ACCOUNT_ID{suffix}", "").strip()
        token = os.environ.get(f"CLOUDFLARE_API_TOKEN{suffix}", "").strip()
        if acct and token and acct not in seen_accounts:   # an id without its token (or the reverse) is skipped
            seen_accounts.add(acct)
            eps.append(Endpoint(f"cloudflare#{len(seen_accounts)}", "cloudflare", token, cf_rpm, account=acct))
    if os.environ.get("NVIDIA_API_KEY", "").strip():
        eps.append(Endpoint("nim", "nim", os.environ["NVIDIA_API_KEY"].strip(), float(os.environ.get("A11Y_RPM_NIM") or 35)))
    # A11Y_KEYS=gemini#1,cloudflare#3,...: this process uses only these keys, so two batches can run side by side
    # without sharing rate limits (D79). Names are numbered before filtering, so they match across processes.
    only = {n.strip() for n in os.environ.get("A11Y_KEYS", "").split(",") if n.strip()}
    return [e for e in eps if e.name in only] if only else eps


def probe_png() -> bytes:
    """A real page screenshot (1280 px wide) for checking that a key answers image calls (D75-D77). A 32x32 test image
    is not enough: on 2 Nov Google's Gemma answered it in 5 s while every real screenshot, even at 40 KB, timed out."""
    return (Path(__file__).parent / "probe_screenshot.png").read_bytes()


class AllCoolingDown(RuntimeError):
    """Every endpoint for this model is rate limited for a long time (e.g. all daily caps used)."""


class Pool:
    def __init__(self, endpoints: list[Endpoint] | None = None):
        self.endpoints = endpoints if endpoints is not None else endpoints_from_env()
        self._lock = threading.Lock()

    @property
    def allow_mixed(self) -> bool:
        return os.environ.get("A11Y_ALLOW_MIXED", "") == "1"

    def acquire(self, canonical: str, on_wait=None, images: bool = False, tokens: int = 0) -> tuple[Endpoint, str, bool]:
        """Block until some endpoint serving `canonical` may be called; reserve its next slot (pacing). A call with
        images skips keys that recently failed a screenshot call, unless every key has (D77). A prompt of about
        `tokens` input tokens skips keys that can't take one that big, unless none that can will be free within 10 min
        (then it is tried anyway and the caller handles the failure, e.g. the validator marks the task unchecked) (D81)."""
        while True:
            with self._lock:
                now = time.time()
                cands = [(e, m) for e in self.endpoints if (m := e.model_for(canonical, self.allow_mixed))]
                if not cands:
                    raise RuntimeError(f"no API key configured that serves {canonical} (see a11y_agent/providers.py)")
                if images:
                    cands = [(e, m) for e, m in cands if e.no_images_until <= now] or cands
                if tokens:
                    fits = [(e, m) for e, m in cands if not e.max_input_tokens or e.max_input_tokens >= tokens]
                    if fits and min(e.cooldown_until for e, _ in fits) - now < 600:
                        cands = fits
                ready = [(e, m) for e, m in cands if e.cooldown_until <= now]
                if ready:
                    # Same-model endpoints first; then the healthiest (fewest recent failures); then the one whose next
                    # pacing slot comes soonest. Without the health term a key that times out kept winning ties
                    # (2 Nov: each step lost ~10 min to two Google keys timing out while Cloudflare answered in 2 s).
                    # Free before paid (D92): a paid key counts as 2 s later, so a free key is used whenever its next
                    # pacing slot is that close, and the paid one takes only the overflow and the free key's rests.
                    e, (served, exact) = min(ready, key=lambda x: (not x[1][1], x[0].fails,
                                                                   max(x[0].next_slot, now) + (2.0 if x[0].paid else 0.0)))
                    slot = max(e.next_slot, now)
                    e.next_slot = slot + 60.0 / e.rpm
                    wait, cool = slot - now, 0.0
                else:
                    cool = min(e.cooldown_until for e, _ in cands) - now
            if ready:
                if wait > 0:
                    time.sleep(wait)
                return e, served, exact
            if cool > 600 and os.environ.get("A11Y_WAIT_FOR_QUOTA") != "1":
                raise AllCoolingDown(f"every endpoint for {canonical} is rate limited for {int(cool // 60)}+ min")
            # With A11Y_WAIT_FOR_QUOTA=1 (unattended batches) a long rest is waited out in 60 s slices instead, so the
            # batch resumes when a daily allowance resets rather than failing every remaining site.
            if on_wait:
                on_wait(cool)
            time.sleep(min(cool, 60) + 0.1)

    def cool(self, e: Endpoint, seconds: float) -> None:
        with self._lock:
            e.cooldown_until = max(e.cooldown_until, time.time() + seconds)

    def failed(self, e: Endpoint, timeout: bool = False) -> float:
        """A server error or timeout: rest the key for longer each time it fails in a row (10 s, 30 s, 90 s ... 15 min).
        A timeout rests it at least 5 min: it cost 120 s and the next call would likely hang too."""
        with self._lock:
            e.fails += 1
            secs = min(900.0, 10.0 * 3 ** (e.fails - 1))
            if timeout:
                secs = max(secs, 300.0)
            e.cooldown_until = max(e.cooldown_until, time.time() + secs)
            return secs

    def ok(self, e: Endpoint) -> None:
        with self._lock:
            e.fails = 0

    def no_images(self, e: Endpoint, seconds: float = 1800.0) -> None:
        """This key timed out on a screenshot: keep it for text calls, send images elsewhere for a while (D77)."""
        with self._lock:
            e.no_images_until = max(e.no_images_until, time.time() + seconds)

    def preflight(self, canonical: str, image: bytes) -> list[str]:
        """Which endpoints answer a screenshot call right now (every persona except P1 sends screenshots). Probed in
        parallel, since a failing key takes the full 120 s timeout. A key that answers is cleared of earlier failures
        and rests, so the run uses it at once; one that fails is kept for text only for 30 min and isn't re-probed until
        then (D77). 2 Nov: Google answered text but timed out on every real screenshot."""
        now = time.time()
        todo = [(e, m[0]) for e in self.endpoints
                if (m := e.model_for(canonical, False)) and e.no_images_until <= now]

        def probe(item):
            e, model = item
            try:
                e.call(model, "Reply with JSON only.", 'Return {"ok": true}.', [image], 0.0, True)
                return True
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=max(1, len(todo))) as ex:
            answered = list(ex.map(probe, todo))
        alive = []
        for (e, _), good in zip(todo, answered):
            if good:
                with self._lock:
                    e.fails, e.cooldown_until, e.no_images_until = 0, 0.0, 0.0
                alive.append(e.name)
            else:
                self.no_images(e)
        return alive

    def describe(self) -> list[str]:
        return [f"{e.name} ({e.kind}, {e.rpm:g}/min)" for e in self.endpoints]


POOL = Pool()
