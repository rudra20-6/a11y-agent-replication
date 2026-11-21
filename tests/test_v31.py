"""Offline checks (no LLM):
- a page that reloads itself while handling a field's change is recorded (unloadCause), a normal submit is not.
- the P2 pixel check says 'visible' when a ring or highlight appears where focus went, 'invisible' when nothing does.
- own_mistake() recognises the agent's own input mistakes, and leaves a real site report alone.

Usage: python tests/test_v31.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.navigator import Navigator
from a11y_agent.pipeline import own_mistake, tool_focus_check

FIX = ROOT / "tests" / "fixtures" / "govuk_like"
FAILURES: list[str] = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


def pixels(s, frm, to):
    """Focus `frm`, snapshot as the navigator does before an action, focus `to`, run the pixel check."""
    s.page.focus(frm)
    s.settle(100)
    nav = SimpleNamespace(s=s, PX_BEFORE_JS=Navigator.PX_BEFORE_JS, PX_AFTER_JS=Navigator.PX_AFTER_JS)
    nav._px_before = Navigator._px_snapshot(nav)
    s.page.focus(to)
    s.settle(150)
    return Navigator._focus_pixels(nav)


def main() -> int:
    pool = BrowserPool()
    try:
        s = pool.session(Viewport(1280, 800))
        s.goto((FIX / "change.html").as_uri())
        s.settle(200)
        s.page.focus("#title")
        check("a heading the page focused (tabindex=-1) is not a control", s.page.evaluate(Navigator.CONTROL_JS) is False)
        s.page.focus("#q")
        check("a text field is a control", s.page.evaluate(Navigator.CONTROL_JS) is True)
        s.js("unloadCause", True)
        s.page.focus("#pin")
        s.page.keyboard.type("500032", delay=10)
        s.page.keyboard.press("Tab")
        s.page.wait_for_load_state("load")
        s.settle(300)
        got = s.js("unloadCause", True)
        check("reload from a field's change is recorded", got and got.get("leftField") is not None, got)
        s.page.focus("#q")
        s.page.keyboard.type("shoes", delay=10)
        s.page.keyboard.press("Enter")
        s.page.wait_for_load_state("load")
        s.settle(300)
        got = s.js("unloadCause", True)
        check("Enter submitting a search form is not recorded", got and got.get("leftField") is None, got)
        s.close()

        s = pool.session(Viewport(1280, 800))
        s.goto((FIX / "focus.html").as_uri())
        s.settle(200)
        check("box-shadow ring appears -> visible", pixels(s, "#n3", "#ring") == "visible")
        check("highlighted option -> visible", pixels(s, "#n3", "#o1") == "visible")
        check("link with outline removed -> invisible", pixels(s, "#n1", "#n2") == "invisible", pixels(s, "#n1", "#n2"))
        check("button with outline removed -> invisible", pixels(s, "#n3", "#bare") == "invisible")
        s.close()
    finally:
        pool.close()

    r = lambda **k: {"problem": "", "action": "", "result": "", "prev_action": None, "prev_result": "", **k}
    check("typing while focus is on an alert", own_mistake(r(problem="the text I typed did not appear in the field",
          action='{"type": "type", "text": "500032"}', prev_result="ok; focus now visibly on: alert There is a problem")) is not None)
    check("focus moved to the error after the agent's failed submit", own_mistake(r(
          problem="focus jumped to an alert instead of staying in the text field", action='{"type": "press", "key": "Enter"}',
          result="ok; focus now visibly on: alert There is a problem Enter a 6-digit pincode")) is not None)
    check("typed onto an existing value", own_mistake(r(problem="the field became 25000 instead of 5000",
          action='{"type": "type", "text": "5000"}', result='ok; the field now contains "25000"')) is not None)
    check("a real overlay report is left alone", own_mistake(r(
          problem="A 'Login' overlay covers the search input, preventing me from interacting with it",
          action='{"type": "type", "ref": "el:6", "text": "Running Shoes"}', result="can't click input")) is None)
    check("tool check confirms an invisible-focus report",
          tool_focus_check({"profile": "P2", "problem": "I cannot see where the keyboard focus is", "focus_px": ["invisible"]}) == "invisible")
    check("tool check contradicts when focus was seen",
          tool_focus_check({"profile": "P2", "problem": "I can't see where focus is", "focus_px": ["visible"]}) == "visible")
    print(f"FAILURES: {len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
