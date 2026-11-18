"""Offline check (no LLM) of method v3 (D97):
- every persona is told when the page opens a new tab, and when the page reloads after typing or a focus move;
- P1 is told that letter-spaced text is spoken letter by letter;
- the persona's "problem" lands on its step, repeats are dropped, and the verifier's verdicts are attached;
- the benchmark probe records that an action involved the mutated element.

Usage: python tests/test_v3_reports.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.bench import install_probe, read_probe
from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.navigator import Navigator, Outcome, Step, spoken
from a11y_agent.pipeline import own_submit, reported_problems, verify_reports

APP = (ROOT / "tests" / "fixtures" / "govuk_like" / "context.html").as_uri()
FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


class StubLLM:
    """Answers the verifier: report 1 is the site's doing, report 2 is not; nothing for any other."""
    def json(self, system, prompt, images=None, temperature=None):
        return {"reports": [{"n": 1, "verdict": "site", "check": "Notice", "sc": "3.2.2", "explanation": "x"},
                            {"n": 2, "verdict": "not_site"}]}


def main() -> int:
    check("spoken: spaced letters are marked", "spoken letter by letter: S, e, a, r, c, h" in spoken('text "S e a r c h"'))
    check("spoken: ordinary words untouched", spoken("Search flights A to B") == "Search flights A to B")
    check("spoken: a name of spaced characters ('2 1') is marked", "spoken letter by letter: 2, 1" in spoken('text "2 1"'))
    check("spoken: page numbers in a longer name untouched", spoken('link "Page 1 2 3"') == 'link "Page 1 2 3"')

    pool = BrowserPool()
    try:
        s = pool.session(Viewport(1280, 800))
        install_probe(s)
        s.goto(APP)
        s.settle(300)
        nav = Navigator(s, "REF", None, 5)
        nav.observe()
        opener = next(e for e in s.interactive_elements() if e["text"] == "21")
        res, _ = nav.act({"type": "click", "ref": opener["ref"]})
        check("REF: a click that opens a tab is reported", "new browser tab opened" in res, res)
        check("REF: the tab was closed again", len(s.ctx.pages) == 1, len(s.ctx.pages))
        check("probe: the opener is not the mutated element", read_probe(s) == {"touched": False})
        btn = next(e for e in s.interactive_elements() if e["text"] == "Plain button")
        nav.act({"type": "click", "ref": btn["ref"]})
        check("probe: clicking the mutated element is recorded", read_probe(s) == {"touched": True})
        check("probe: and reset after reading", read_probe(s) == {"touched": False})
        s.close()

        s = pool.session(Viewport(1280, 800))
        s.goto(APP)
        s.settle(300)
        nav = Navigator(s, "P2", None, 5)
        nav.observe()
        s.page.focus("#q")
        nav.act({"type": "type", "text": "110001"})
        res, _ = nav.act({"type": "press", "key": "Tab"})
        check("P2: a reload after a Tab (change submits) is reported", "page reloaded" in res, res)
        res, _ = nav.act({"type": "press", "key": "Tab"})
        check("P2: an ordinary Tab reports no context change", "page reloaded" not in res and "new browser tab" not in res, res)
        nav.history = [Step(0, "", "", {"type": "press", "key": "Tab"}, "ok", "u"), Step(1, "", "", {"type": "type", "text": "x"}, "ok", "u")]
        obs, _ = nav.observe()   # effort is counted from the run's history (filled by run(), set here by hand)
        check("P2: sees its effort", "YOUR EFFORT SO FAR: 2 actions, 1 key presses" in obs, obs[:200])
        s.close()

        s = pool.session(Viewport(320, 640))   # v3.1 (D102): P3 types after clicking a label or the box around a field
        s.goto((ROOT / "tests" / "fixtures" / "govuk_like" / "fields.html").as_uri())
        s.settle(300)
        nav = Navigator(s, "P3", None, 5)
        nav.observe()
        lab = next(e for e in s.interactive_elements() if e["tag"] == "label" and e["text"] == "Mobile number")
        res, _ = nav.act({"type": "type", "ref": lab["ref"], "text": "9876543210"})
        check("P3: typing on a label fills its field", s.page.input_value("#mob") == "9876543210", res)
        box = next(e for e in s.interactive_elements() if e["tag"] == "div")
        res, _ = nav.act({"type": "type", "ref": box["ref"], "text": "500032"})
        check("P3: typing on the box around one field fills it", s.page.input_value("#pin") == "500032", res)
        s.close()

        s = pool.session(Viewport(1280, 800))
        s.goto(APP)
        s.settle(300)
        nav = Navigator(s, "P1", None, 5)
        obs, _ = nav.observe()
        check("P1: letter-spaced text is spoken letter by letter", "spoken letter by letter" in obs)
        s.close()
    finally:
        pool.close()

    st = lambda i, prob, res="ok": Step(i, f"obs {i}", f"thought {i}", {"type": "press", "key": "Tab"}, res, "u", problem=prob)
    out = Outcome("P2", "done", "x", [st(0, None, "ok; the page reloaded"), st(1, "The page reloaded when I left the field"),
                                      st(2, "the page reloaded when I left the field!"), st(3, "Focus jumped to the footer")])
    reps = reported_problems(out)
    check("reports: one per distinct problem, on its step", [r["step"] for r in reps] == [1, 3], reps)
    check("reports: carry the previous action's result", reps[0]["prev_result"] == "ok; the page reloaded", reps[0])
    class DebriefLLM:
        def json(self, system, prompt, images=None, temperature=None):
            return {"problems": [{"step": 0, "problem": "The page reloaded when I left the field"},
                                 {"step": 99, "problem": "a step that does not exist"}, {"step": 3, "problem": ""},
                                 {"step": 2, "problem": "The tab order jumped to the footer"}]}
    from types import SimpleNamespace
    nav = Navigator(SimpleNamespace(), "P2", DebriefLLM(), 5)
    deb = nav.debrief("find the post office", out)
    check("debrief: only real steps with text are kept", deb == [{"step": 0, "problem": "The page reloaded when I left the field"},
                                                                  {"step": 2, "problem": "The tab order jumped to the footer"}], deb)
    check("debrief: REF has none", Navigator(SimpleNamespace(), "REF", DebriefLLM(), 5).debrief("x", out) == [])
    out.debrief = deb
    merged = reported_problems(out)
    check("reports: debrief items join, repeats of a step problem dropped",
          [(r["step"], r["when"]) for r in merged] == [(1, "during"), (3, "during"), (2, "debrief")], merged)
    check("reports: carry the cited step's own result", merged[2]["result"] == "ok", merged[2])
    v = verify_reports(StubLLM(), "P2", "find the post office", reps)
    check("verify: verdicts attached in order", [x["verdict"] for x in v] == ["site", "not_site"], v)
    check("verify: SC and check from the verifier", v[0]["sc"] == "3.2.2" and v[0]["check"] == "Notice", v[0])
    enter = '{"type": "press", "key": "Enter"}'
    check("own submit: Enter right after typing, then an error alert", own_submit(
        {"action": enter, "prev_action": '{"type": "type", "text": "Delhi"}', "result": "ok; focus now visibly on: alert There is a problem"}))
    check("own submit: not after an arrow key", not own_submit(
        {"action": enter, "prev_action": '{"type": "press", "key": "ArrowDown"}', "result": "ok; alert There is a problem"}))
    check("own submit: not without an error", not own_submit(
        {"action": enter, "prev_action": '{"type": "type", "text": "x"}', "result": "ok; the page reloaded"}))
    print(f"FAILURES: {len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
