"""Offline check (no LLM, no network) that a tool failure is never read as a stuck agent or a site problem:
  1. a model/API failure ends a persona run with status "error" and tool_error True; other endings keep tool_error False
  2. run_task records such a persona as a tool error and never sends it to judge_stall; a REF failure is "not tested"
  3. one failed screenshot gives "no image" instead of an exception

Usage: python tests/test_tool_errors.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent import pipeline
from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.llm import LLMError, QuotaExhausted
from a11y_agent.navigator import Navigator, Outcome, Step

FIXTURE = (ROOT / "tests" / "fixtures" / "overlay.html").as_uri()
FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


class FailingLLM:
    def __init__(self, exc):
        self.exc, self.calls = exc, 0

    def json(self, *a, **k):
        self.calls += 1
        raise self.exc


class StuckLLM:
    def json(self, *a, **k):
        return {"thought": "no way forward", "action": {"type": "stuck", "reason": "nothing to press"}}


class Events:
    """Stands in for EventLog."""

    def __init__(self):
        self.events = []

    def emit(self, kind, **kw):
        self.events.append((kind, kw))

    def snapshot(self, session, name):
        return False

    def of(self, kind):
        return [kw for k, kw in self.events if k == kind]


def part1_navigator(pool):
    for profile in ("REF", "P1", "P2", "P3"):
        s = pool.session(Viewport(320, 640) if profile == "P3" else Viewport(1280, 800))
        for exc in (LLMError("model call failed after 8 tries: 503"), QuotaExhausted("gemma: quota exhausted")):
            llm = FailingLLM(exc)
            out = Navigator(s, profile, llm, 3).run("any task", FIXTURE)
            check(f"{profile}: {type(exc).__name__} -> status error, tool_error True",
                  out.status == "error" and out.tool_error is True and out.reason and llm.calls == 1, (out.status, out.tool_error, out.reason))
        out = Navigator(s, profile, StuckLLM(), 3).run("any task", FIXTURE)
        check(f"{profile}: a genuine 'stuck' is not a tool error", out.status == "stuck" and out.tool_error is False, (out.status, out.tool_error))
        s.close()


def fake_pipeline(outcomes, judge_calls, check_calls):
    """Replace the browser-driven parts of run_task."""
    def _agent(task, profile, llm, ev, prepare=None, probe=None):
        r = outcomes[profile]
        if isinstance(r, Exception):
            raise r
        return r

    def _check_profile(task, steps, profile, ev, prepare=None):
        check_calls.append(profile)
        return [], []

    def judge_stall(llm, profile, goal, ref, out, det):
        judge_calls.append(profile)
        return None   # "agent error": the judge's verdict for a plain stall

    pipeline._agent, pipeline._check_profile, pipeline.judge_stall = _agent, _check_profile, judge_stall


def part2_run_task():
    orig = pipeline._agent, pipeline._check_profile, pipeline.judge_stall
    task = {"id": "t1", "goal": "find something", "start_url": "http://x"}
    click = Step(0, "", "", {"type": "click", "ref": "el:1"}, "ok", "http://x", "#go")
    ref_done = Outcome("REF", "done", "ok", [click])
    api_down = "model call failed after 8 tries: 503 UNAVAILABLE"
    try:
        # A: P1's model call failed, P2 finished
        judge, checks, ev = [], [], Events()
        fake_pipeline({"REF": ref_done, "P1": Outcome("P1", "error", "", [click, click], api_down, tool_error=True),
                       "P2": Outcome("P2", "done", "fine", [click])}, judge, checks)
        rec_a = pipeline.run_task(task, ("P1", "P2"), llm=object(), ev=ev)
        errs = rec_a.get("tool_errors", [])
        check("A: persona LLM failure lands in tool_errors with the checker's shape",
              errs == [{"profile": "P1", "step": 2, "where": "agent", "error": api_down}], errs)
        check("A: judge_stall is never called for it", judge == [], judge)
        check("A: not an unconfirmed stall and not a finding", "unconfirmed_stalls" not in rec_a and rec_a["findings"] == [], rec_a)
        check("A: a tool_error event is emitted", [e["profile"] for e in ev.of("tool_error")] == ["P1"], ev.events)
        check("A: the profile record says tool_error", rec_a["profiles"]["P1"]["tool_error"] is True and rec_a["profiles"]["P2"]["tool_error"] is False)
        check("A: the rule checks still ran for both profiles", sorted(checks) == ["P1", "P2"], checks)

        # B: a plain stall (not an LLM failure) goes to the judge
        judge, checks, ev = [], [], Events()
        fake_pipeline({"REF": ref_done, "P1": Outcome("P1", "stuck", "", [click], "cannot reach it"),
                       "P2": Outcome("P2", "error", "", [click], "something else", tool_error=False)}, judge, checks)
        rec_b = pipeline.run_task(task, ("P1", "P2"), llm=object(), ev=ev)
        check("B: stuck and non-LLM errors are still judged", sorted(judge) == ["P1", "P2"], judge)
        check("B: they are recorded as unconfirmed stalls, not tool errors",
              len(rec_b.get("unconfirmed_stalls", [])) == 2 and not rec_b.get("tool_errors"), rec_b)

        # C: the reference run's model call failed: the task was not tested
        judge, checks, ev = [], [], Events()
        fake_pipeline({"REF": Outcome("REF", "error", "", [], api_down, tool_error=True)}, judge, checks)
        rec_c = pipeline.run_task(task, ("P1", "P2"), llm=object(), ev=ev)
        check("C: REF tool error -> invalid says the model/API failed",
              rec_c.get("invalid", "").startswith("not tested: the model/API failed during the reference run: model call failed"), rec_c.get("invalid"))
        check("C: not described as the agent failing the task", "could not complete" not in rec_c["invalid"])
        check("C: REF tool error is also in tool_errors, nothing else ran", rec_c["tool_errors"][0]["profile"] == "REF" and checks == [] and judge == [], rec_c)
        check("C: task_invalid event carries tool_error", ev.of("task_invalid")[0].get("tool_error") is True, ev.events)

        # C2: an ordinary REF failure keeps the usual wording
        fake_pipeline({"REF": Outcome("REF", "stuck", "", [click], "no button")}, [], [])
        rec_c2 = pipeline.run_task(task, ("P1",), llm=object(), ev=Events())
        check("C2: ordinary REF stall keeps the usual wording", rec_c2["invalid"].startswith("reference agent could not complete the task"), rec_c2["invalid"])

        # D: a persona agent that crashes (not an LLM failure) is also a tool problem, never a stall
        judge, checks, ev = [], [], Events()
        fake_pipeline({"REF": ref_done, "P1": RuntimeError("browser crashed"), "P2": Outcome("P2", "done", "ok", [click])}, judge, checks)
        rec_d = pipeline.run_task(task, ("P1", "P2"), llm=object(), ev=ev)
        check("D: a crashed persona agent is a tool error and not judged",
              rec_d.get("tool_errors") == [{"profile": "P1", "step": -1, "where": "agent", "error": "browser crashed"}] and judge == [], rec_d.get("tool_errors"))

        # E: the report shows them
        pl = SimpleNamespace(pages=[], capabilities=["search"])
        md = pipeline.report_md("http://x", pl, [rec_a, rec_c, rec_d])
        check("E: report lists the agent tool error and labels the profile", "Tool errors" in md and "P1 step 2 (agent): model call failed" in md and "P1: tool error" in md, md)
        check("E: report does not call it a barrier or an unconfirmed stall", "Unconfirmed" not in md.split("## ")[1], md)
        check("E: report says the reference run's task was not tested, without doubling it",
              "Not tested: the model/API failed during the reference run" in md and "Not tested: not tested" not in md, md)
    finally:
        pipeline._agent, pipeline._check_profile, pipeline.judge_stall = orig


def part3_screenshot(pool):
    s = pool.session(Viewport(1280, 800))
    s.goto(FIXTURE)
    real = s.page.screenshot
    calls = []

    def always_fails(**kw):
        calls.append(kw.get("timeout"))
        raise TimeoutError("Page.screenshot: Timeout 10000ms exceeded.\nCall log:\n  - waiting for fonts to load...")

    s.page.screenshot = always_fails
    png = s.screenshot()
    check("screenshot: two failures -> b'' (no exception), one retry, a timeout is passed", png == b"" and len(calls) == 2 and all(calls), (png[:5], calls))
    check("screenshot: the reason is kept", "fonts" in s.screenshot_error or "Timeout" in s.screenshot_error, s.screenshot_error)
    for profile in ("REF", "P2"):
        obs, images = Navigator(s, profile, None, 1).observe()
        check(f"{profile}: observe without a screenshot sends no image and says so", images == [] and "screenshot unavailable" in obs, (images, obs[:200]))
    obs, images = Navigator(s, "P1", None, 1).observe()
    check("P1: unaffected (it never gets a screenshot)", images == [] and "screenshot unavailable" not in obs)

    state = {"n": 0}

    def fails_once(**kw):
        state["n"] += 1
        if state["n"] == 1:
            raise TimeoutError("first one times out")
        return real(**kw)

    s.page.screenshot = fails_once
    png = s.screenshot()
    check("screenshot: the retry can succeed", png[:4] == b"\x89PNG" and state["n"] == 2, (png[:4], state))
    obs, images = Navigator(s, "REF", None, 1).observe()
    check("REF: a working screenshot is sent", len(images) == 1 and "screenshot unavailable" not in obs)
    s.page.screenshot = real
    s.close()


def main() -> int:
    part2_run_task()
    pool = BrowserPool()
    try:
        part1_navigator(pool)
        part3_screenshot(pool)
    finally:
        pool.close()
    print("FAILURES:", len(FAILURES))
    return len(FAILURES)


def test_tool_errors():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
