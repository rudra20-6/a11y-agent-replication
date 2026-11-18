"""Offline check (no LLM) of D88: the keyboard persona P2 is told when the control it pressed changes how it looks
(a bus seat turns green when selected), is told nothing when a Tab moves focus away, and is not told ARIA states.

Usage: python tests/test_p2_look_change.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.navigator import Navigator

APP = (ROOT / "bench" / "app" / "index.html").as_uri() + "#/seats"
FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


def main() -> int:
    pool = BrowserPool()
    try:
        s = pool.session(Viewport(1280, 800))
        s.goto(APP)
        s.settle(400)
        nav = Navigator(s, "P2", None, 5)
        nav.observe()
        s.page.focus("[data-seat=L3]")
        res, _ = nav.act({"type": "press", "key": "Enter"})
        check("P2: Enter on a seat reports that it now looks different", "now looks different" in res, res)
        check("P2: the change names the background", "background" in res, res)
        check("P2: no ARIA state leaks", "pressed" not in res, res)
        res, _ = nav.act({"type": "press", "key": "Tab"})
        check("P2: a Tab (focus moves on) reports no look change", "now looks different" not in res, res)
        res, _ = nav.act({"type": "press", "key": "Shift+Tab"})
        check("P2: coming back to the selected seat reports no change", "now looks different" not in res, res)
        s.close()

        s = pool.session(Viewport(1280, 800))
        s.goto(APP)
        s.settle(400)
        nav = Navigator(s, "P1", None, 5)
        nav.observe()
        s.page.focus("[data-seat=L3]")
        res, _ = nav.act({"type": "press", "key": "Enter"})
        check("P1: unchanged (hears the pressed state, no look change)", "pressed=true" in res and "looks different" not in res, res)
        s.close()
    finally:
        pool.close()
    print(f"FAILURES: {len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
