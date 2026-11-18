"""Offline check (no LLM) of D104: P2 is told focus is visible when the page draws any indicator (a box-shadow ring, a
ring on the label of a hidden radio, a highlighted option), and invisible when nothing distinguishes the focused
control (outline removed, nothing else). BenchBook's own focus styles must stay visible.

Usage: python tests/test_focus_shown.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.browser import BrowserPool, Viewport

PAGE = (ROOT / "tests" / "fixtures" / "govuk_like" / "focus.html").as_uri()
APP = (ROOT / "bench" / "app" / "index.html").as_uri()
FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


def main() -> int:
    pool = BrowserPool()
    try:
        s = pool.session(Viewport(1280, 800))
        s.goto(PAGE)
        s.settle(200)
        for sel, want, what in (("#ring", True, "a box-shadow ring"), ("#o1", True, "a highlighted option"),
                                ("#yes", True, "a ring on a hidden radio's label"), ("#n2", False, "a link with its outline removed"),
                                ("#bare", False, "a button with its outline removed and no neighbour")):
            s.page.focus(sel)
            got = s.js("focusShown")
            check(f"focus shown for {what}: {want}", got is want, got)
        s.page.evaluate("() => document.activeElement.blur()")
        check("nothing focused -> None", s.js("focusShown") is None)
        s.close()

        s = pool.session(Viewport(1280, 800))
        s.goto(APP + "#/flights")
        s.settle(400)
        s.page.keyboard.press("Tab")
        s.page.keyboard.press("Tab")
        check("BenchBook: focus on its controls is shown", s.js("focusShown") is True, s.focus_info())
        s.close()
    finally:
        pool.close()
    print(f"FAILURES: {len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
