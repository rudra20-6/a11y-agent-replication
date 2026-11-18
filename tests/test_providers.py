"""Offline check (no network, no keys) of the rolling key pool (D71): rotation, cool-down on 429, same-model rule,
substitutes only when mixing is allowed, and that substitute answers never enter the shared cache.

Usage: python tests/test_providers.py      (prints FAILURES: 0 when everything holds)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import a11y_agent.llm as llm
from a11y_agent.providers import Endpoint, Pool

FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


class Fake(Endpoint):
    """Answers from a script: 'ok', '429', '500'."""
    def __init__(self, name, kind, script, rpm=6000):
        super().__init__(name, kind, "k-" + name, rpm)
        self.script, self.calls = list(script), []

    def call(self, model, system, prompt, images, temperature, json_mode):
        self.calls.append(model)
        r = self.script.pop(0) if self.script else "ok"
        if r == "429":
            raise RuntimeError("Error code: 429 - rate limited, retry in 30s")
        if r == "500":
            raise RuntimeError("Error code: 500 - INTERNAL")
        if r == "timeout":
            raise RuntimeError("The read operation timed out")
        if r == "leaked":
            raise RuntimeError("403 PERMISSION_DENIED. Your API key was reported as leaked. Please use another API key.")
        if r == "daily":
            raise RuntimeError("Error code: 429 - 4006: you have used up your daily free allocation of 10,000 neurons")
        return '{"from": "%s", "model": "%s"}' % (self.name, model), 10, 5


def make_llm(endpoints, model="gemma-4-26b-a4b-it"):
    m = llm.LLM.__new__(llm.LLM)
    m.pool, m.model, m.role, m.use_cache = Pool(endpoints), model, "test", True
    return m


def main():
    llm.CACHE = Path(tempfile.mkdtemp())   # keep the real cache untouched
    os.environ.pop("A11Y_ALLOW_MIXED", None)

    a, b = Fake("gemini#1", "gemini", []), Fake("gemini#2", "gemini", [])
    m = make_llm([a, b])
    who = [m.json("s", f"p{i}")["from"] for i in range(4)]
    check("two keys for the same model take turns", who == ["gemini#1", "gemini#2", "gemini#1", "gemini#2"], who)

    a, b = Fake("gemini#1", "gemini", ["429"]), Fake("gemini#2", "gemini", [])
    m = make_llm([a, b])
    r = m.json("s", "q")
    check("a 429 on one key moves the call to the other at once", r["from"] == "gemini#2", r)
    check("the rate-limited key rests (cool-down set)", a.cooldown_until > 0, a.cooldown_until)
    r2 = m.json("s", "q2")
    check("while it rests, calls go to the other key", r2["from"] == "gemini#2", r2)

    a, o = Fake("gemini#1", "gemini", ["500"]), Fake("openrouter", "openrouter", [])
    m = make_llm([a, o])
    r = m.json("s", "z")
    check("OpenRouter serves the same Gemma 4 26B and is used on a 500",
          r["from"] == "openrouter" and r["model"] == "google/gemma-4-26b-a4b-it:free", r)

    n = Fake("nim", "nim", [])
    m = make_llm([n])
    try:
        m.json("s", "x")
        check("without mixing, NIM (no Gemma 4 26B) is never used", False, "it answered")
    except RuntimeError as e:
        check("without mixing, NIM (no Gemma 4 26B) is never used", "no API key configured" in str(e), e)

    os.environ["A11Y_ALLOW_MIXED"] = "1"
    llm.USAGE.by_endpoint.clear()
    m = make_llm([n])
    r = m.json("s", "mixed")
    check("with A11Y_ALLOW_MIXED=1, NIM answers with its substitute model", r["model"] == "google/gemma-4-31b-it", r)
    check("the substitution is named in the usage summary",
          any("substitute" in k for k in llm.USAGE.summary().get("endpoints", {})), llm.USAGE.summary())
    check("a substitute answer is not written to the shared cache", not (llm.CACHE / f"{m._key('s', 'mixed', [])}.json").exists())
    os.environ.pop("A11Y_ALLOW_MIXED")

    a, b = Fake("gemini#1", "gemini", []), Fake("gemini#2", "gemini", [])
    m = make_llm([a, b])
    m.json("s", "cached")
    before = len(a.calls) + len(b.calls)
    m.json("s", "cached")
    check("an exact answer is cached and reused for the same prompt", len(a.calls) + len(b.calls) == before)

    # --- Cloudflare (D72): two accounts
    import time
    from a11y_agent.providers import endpoints_from_env
    saved = dict(os.environ)
    try:
        for k in [k for k in os.environ if k.startswith(("CLOUDFLARE_", "GEMINI_", "OPENROUTER_", "NVIDIA_"))]:
            del os.environ[k]
        os.environ.update({"CLOUDFLARE_ACCOUNT_ID": "acct1", "CLOUDFLARE_API_TOKEN": "tok1",
                           "CLOUDFLARE_ACCOUNT_ID_2": "acct2", "CLOUDFLARE_API_TOKEN_2": "tok2",
                           "CLOUDFLARE_ACCOUNT_ID_3": "acct3",                      # no token: skipped
                           "CLOUDFLARE_ACCOUNT_ID_4": "acct1", "CLOUDFLARE_API_TOKEN_4": "tok4"})  # same account again: skipped
        eps = endpoints_from_env()
    finally:
        os.environ.clear()
        os.environ.update(saved)
    check("two Cloudflare accounts become two endpoints, each with its own account id",
          [(e.name, e.account, e.key) for e in eps] == [("cloudflare#1", "acct1", "tok1"), ("cloudflare#2", "acct2", "tok2")],
          [(e.name, e.account) for e in eps])

    cf = Fake("cloudflare#1", "cloudflare", [])
    check("Cloudflare serves Gemma 4 26B under its own id",
          cf.model_for("gemma-4-26b-a4b-it", False) == ("@cf/google/gemma-4-26b-a4b-it", True), cf.model_for("gemma-4-26b-a4b-it", False))
    check("Cloudflare never substitutes another model, even with mixing on", cf.model_for("gemma-4-31b-it", True) is None)

    a, c1, c2 = Fake("gemini#1", "gemini", []), Fake("cloudflare#1", "cloudflare", ["daily"]), Fake("cloudflare#2", "cloudflare", [])
    m = make_llm([c1, c2])
    r = m.json("s", "capped")
    check("an account over its daily allowance hands the call to the other account", r["from"] == "cloudflare#2", r)
    rest = c1.cooldown_until - time.time()
    expected = min(3600, llm._secs_to_utc_midnight())   # the real time left, so the test holds at any hour
    check("and rests up to an hour before trying again (the allowance comes back gradually, D83)", abs(rest - expected) < 15,
          (rest, expected))

    # --- health (2 Nov): a key that times out must not keep winning ties
    g1, g2, c1 = Fake("gemini#1", "gemini", ["timeout"]), Fake("gemini#2", "gemini", ["timeout"]), Fake("cloudflare#1", "cloudflare", [])
    m = make_llm([g1, g2, c1])
    r = m.json("s", "slow-google")
    check("after two keys time out, the third answers in the same call", r["from"] == "cloudflare#1", r)
    check("a timed-out key rests at least 5 minutes", g1.cooldown_until - time.time() > 290 and g2.cooldown_until - time.time() > 290,
          (g1.cooldown_until - time.time(), g2.cooldown_until - time.time()))
    m.json("s", "next-step")
    check("the next call goes straight to the healthy key (no new timeout)", len(g1.calls) == 1 and len(g2.calls) == 1,
          (len(g1.calls), len(g2.calls), len(c1.calls)))

    a, b = Fake("gemini#1", "gemini", []), Fake("cloudflare#1", "cloudflare", [])
    a.fails = 2   # recovered from its rest but failed recently
    m = make_llm([a, b])
    check("between ready keys, the one with fewer recent failures is chosen", m.json("s", "tie")["from"] == "cloudflare#1")
    m.pool.ok(a)
    check("a success clears a key's failure count", a.fails == 0)

    # --- a revoked key (2 Nov: Google's 403 "reported as leaked") must not take every retry
    bad, g = Fake("gemini#3", "gemini", ["leaked"] * 20), Fake("gemini#1", "gemini", [])
    g.fails = 2   # the healthy key had recent failures, so the bad one won the pick before the fix
    m = make_llm([bad, g])
    r = m.json("s", "revoked")
    check("a 403 key hands the call to another key", r["from"] == "gemini#1", r)
    check("and is set aside for days, so it isn't picked again", bad.cooldown_until - time.time() > 6 * 24 * 3600 and len(bad.calls) == 1,
          (bad.cooldown_until - time.time(), len(bad.calls)))

    # --- D87: paid OpenRouter route
    o = Fake("openrouter", "openrouter", [])
    check("an OpenRouter id (vendor/model) is served as named, e.g. for the second-model diagnostic",
          o.model_for("google/gemini-3.8-flash", False) == ("google/gemini-3.8-flash", True))
    check("a Google key does not claim to serve an OpenRouter id", Fake("gemini#1", "gemini", []).model_for("google/gemini-3.8-flash", False) is None)
    import a11y_agent.providers as prov
    saved = {k: os.environ.get(k) for k in ("OPENROUTER_API_KEY", "A11Y_OPENROUTER_PAID", "A11Y_OPENROUTER_MIX",
                                             "A11Y_OPENROUTER_PROVIDER", "A11Y_KEYS")}
    os.environ.update(OPENROUTER_API_KEY="test-key", A11Y_OPENROUTER_PROVIDER="example-provider", A11Y_KEYS="openrouter,openrouter_paid")
    os.environ.pop("A11Y_OPENROUTER_MIX", None)
    os.environ["A11Y_OPENROUTER_PAID"] = "1"
    (o,) = prov.endpoints_from_env()
    check("with A11Y_OPENROUTER_PAID=1 Gemma is the paid id (no :free), pinned",
          o.model_for("gemma-4-26b-a4b-it", False) == ("google/gemma-4-26b-a4b-it", True) and o.pin == "example-provider")

    # --- D92: free OpenRouter first, paid only while the free one rests
    os.environ.pop("A11Y_OPENROUTER_PAID")
    os.environ["A11Y_OPENROUTER_MIX"] = "1"
    eps = {e.name: e for e in prov.endpoints_from_env()}
    check("mix: a free and a paid OpenRouter endpoint", set(eps) == {"openrouter", "openrouter_paid"}, set(eps))
    check("mix: the free one asks for :free and is not pinned",
          eps["openrouter"].model_for("gemma-4-26b-a4b-it", False)[0].endswith(":free") and not eps["openrouter"].pin)
    check("mix: the paid one asks for the paid id, pinned",
          eps["openrouter_paid"].model_for("gemma-4-26b-a4b-it", False)[0] == "google/gemma-4-26b-a4b-it"
          and eps["openrouter_paid"].pin == "example-provider")
    pool = prov.Pool(list(eps.values()))
    first = pool.acquire("gemma-4-26b-a4b-it")[0].name
    check("mix: the free one is used first", first == "openrouter", first)
    nxt = pool.acquire("gemma-4-26b-a4b-it")[0].name   # free one's next slot is 6 s away (10/min): don't wait for it
    check("mix: overflow goes to the paid one instead of waiting", nxt == "openrouter_paid", nxt)
    pool.cool(eps["openrouter"], 3 * 3600)   # its 1,000/day used up
    check("mix: the paid one answers while the free one rests", pool.acquire("gemma-4-26b-a4b-it")[0].name == "openrouter_paid")
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    # --- D82: a reply with a second JSON object after the first is read, not rejected
    pj = llm.parse_json
    check("two JSON objects back to back: the first is used", pj('{"a": 1}{"b": 2}') == {"a": 1})
    check("an object followed by text and another object", pj('{"action": {"type": "click"}}\nThen: {"x": 1}') == {"action": {"type": "click"}})
    check("leading prose, then the object", pj('I will click.\n{"a": 1}') == {"a": 1})
    check("a fenced block still wins", pj('{"draft": 1}\n```json\n{"final": 2}\n```') == {"final": 2})
    try:
        pj("no json here")
        check("text with no object still raises", False)
    except Exception:
        check("text with no object still raises", True)

    # --- D81: a prompt too big for Google's per-minute token allowance goes to a key that can take it
    g, c = Fake("gemini#1", "gemini", []), Fake("cloudflare#1", "cloudflare", [])
    g.max_input_tokens = 12000
    m = make_llm([g, c])
    big = "x" * 60000   # ~17,000 tokens, like the validator's prompt
    check("a validator-sized prompt skips the Google key", m.json("s", big)["from"] == "cloudflare#1")
    check("a normal prompt can still use the Google key", "gemini#1" in {m.json("s", f"small{i}")["from"] for i in range(3)})
    c.cooldown_until = time.time() + 3600   # Cloudflare out for an hour: don't wait, try Google and let the caller cope
    check("if no key that fits is free within 10 min, the call isn't held up", m.json("s", big + "y")["from"] == "gemini#1")
    c.cooldown_until = time.time() + 3       # free in moments (anything under 10 min): worth waiting for
    e, _, _ = m.pool.acquire("gemma-4-26b-a4b-it", tokens=17000)
    check("if one that fits is free soon, the call waits for it", e.name == "cloudflare#1", e.name)

    # --- D77: a key that hangs on screenshots stays in use for text
    g, c = Fake("gemini#1", "gemini", ["timeout"]), Fake("cloudflare#1", "cloudflare", [])
    m = make_llm([g, c])
    r = m.json("s", "with-screenshot", images=[b"png"])
    check("a screenshot call that times out moves to the next key", r["from"] == "cloudflare#1", r)
    check("that key is marked text-only, not rested", g.no_images_until > time.time() + 1700 and g.cooldown_until <= time.time(),
          (g.no_images_until - time.time(), g.cooldown_until - time.time()))
    who = {m.json("s", f"shot{i}", images=[b"png"])["from"] for i in range(3)}
    check("later screenshot calls skip it", who == {"cloudflare#1"}, who)
    who = {m.json("s", f"text{i}")["from"] for i in range(4)}
    check("text calls still use it", "gemini#1" in who, who)
    c.no_images_until = time.time() + 1800   # every key marked: use them anyway rather than deadlock
    check("if every key is marked, screenshots still go somewhere", "from" in m.json("s", "all-marked", images=[b"png"]))

    good, bad = Fake("cloudflare#1", "cloudflare", []), Fake("gemini#1", "gemini", ["timeout"])
    good.fails, good.cooldown_until = 3, time.time() + 900
    p = Pool([good, bad])
    alive = p.preflight("gemma-4-26b-a4b-it", b"png")
    check("preflight lists only keys that answered the screenshot", alive == ["cloudflare#1"], alive)
    check("preflight clears the rest of a key that answered", good.fails == 0 and good.cooldown_until == 0.0)
    check("preflight marks a key that failed as text-only", bad.no_images_until > time.time())
    p.preflight("gemma-4-26b-a4b-it", b"png")
    check("and doesn't probe it again while marked", len(bad.calls) == 1, len(bad.calls))

    print(f"FAILURES: {len(FAILURES)}")


if __name__ == "__main__":
    main()
