"""Offline check (no LLM) of how Navigator.act clicks on a messy page: a popup that covers the page, references that go
stale when the page re-renders, a control Playwright cannot get stable, a disabled control.

Usage: python tests/test_click_fallbacks.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.navigator import Navigator, Outcome, Step
from a11y_agent.pipeline import path_from_reference

FIXTURE = (ROOT / "tests" / "fixtures" / "overlay.html").as_uri()
FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


def ref_of(nav: Navigator, kind: str, text: str) -> str:
    """The el: ref of the control the agent would see listed as `kind "text"`."""
    return next(r for r, k in nav.known.items() if k["kind"] == kind and k["text"] == text)


def text_of(s, sel: str) -> str:
    return s.page.inner_text(sel).strip()


def modal_open(s) -> bool:
    return s.page.is_visible("#backdrop")


def fresh(pool, profile: str, open_modal: bool, width: int = 1280, height: int = 800):
    s = pool.session(Viewport(width, height))
    s.goto(FIXTURE)
    s.page.evaluate(f"setModal({str(open_modal).lower()})")
    nav = Navigator(s, profile, None, 5)
    nav.observe()   # the agent always looks before it acts; this is what remembers what each el:N was
    return s, nav


def main() -> int:
    pool = BrowserPool()
    try:
        # --- a popup covers the Search button ---------------------------------------------------------------
        s, nav = fresh(pool, "REF", True)
        res, _ = nav.act({"type": "click", "ref": ref_of(nav, "button", "Search")})
        check("REF: covered click -> Escape, retry works", res.startswith("ok") and "pressed Escape" in res, res)
        check("REF: the search really happened and the popup is gone", text_of(s, "#status") == "searched 1" and not modal_open(s))
        check("REF: Step.fallback names the escape", nav.fallback == "escape", nav.fallback)
        s.close()

        s, nav = fresh(pool, "P3", True, 320, 640)
        res, _ = nav.act({"type": "click", "ref": ref_of(nav, "button", "Search")})
        check("P3: covered click is refused and says what covers it", res.startswith("can't click") and "<div>" in res and "Login or Create Account" in res, res)
        check("P3: nothing was clicked through and no Escape was pressed", text_of(s, "#status") == "not searched" and modal_open(s) and nav.fallback is None)
        res, _ = nav.act({"type": "click", "ref": ref_of(nav, "button", "Close")})
        check("P3: closing the popup like a user works, then the search works", res.startswith("ok") and not modal_open(s), res)
        nav.observe()
        res, _ = nav.act({"type": "click", "ref": ref_of(nav, "button", "Search")})
        check("P3: click after the popup is closed needs no fallback", res.startswith("ok") and nav.fallback is None and text_of(s, "#status") == "searched 1", res)
        s.close()

        s, nav = fresh(pool, "REF", True)
        res, _ = nav.act({"type": "click", "ref": ref_of(nav, "button", "Close")})
        check("REF: the popup's own close button clicks normally", res.startswith("ok") and nav.fallback is None and not modal_open(s), res)
        s.close()

        # --- stale references after a re-render -------------------------------------------------------------
        for profile, size in (("REF", (1280, 800)), ("P3", (320, 640))):
            s, nav = fresh(pool, profile, False, *size)
            old = ref_of(nav, "button", "Apply")
            s.page.evaluate("renderList(1)")
            res, sel = nav.act({"type": "click", "ref": old})
            check(f"{profile}: stale ref is re-found", res.startswith("ok") and "re-found after the page re-rendered" in res, res)
            check(f"{profile}: the re-found control was clicked, and recorded", text_of(s, "#applied") == "applied 1" and nav.fallback == "re-found" and bool(sel), (nav.fallback, sel))
            s.close()

        s, nav = fresh(pool, "REF", False)
        old = ref_of(nav, "button", "Apply")
        s.page.evaluate("renderList(2)")
        res, _ = nav.act({"type": "click", "ref": old})
        check("REF: two look-alikes -> clear message, nothing clicked", res.startswith("no such control") and "2 controls" in res and text_of(s, "#applied") == "applied 0", res)
        s.page.evaluate("renderList(0)")
        res, _ = nav.act({"type": "click", "ref": old})
        check("REF: no look-alike -> clear message", res.startswith("no such control") and "nothing like it" in res, res)
        res, _ = nav.act({"type": "click", "ref": "el:99999"})
        check("REF: a ref that was never listed is just 'no such control'", res == "no such control", res)
        s.close()

        s, nav = fresh(pool, "REF", False)
        old = ref_of(nav, "input", "Name")
        s.page.evaluate("renderList(1)")
        res, _ = nav.act({"type": "type", "ref": old, "text": "Asha"})
        check("REF: typing into a stale field re-finds it", res.startswith("ok") and "re-found" in res and s.page.input_value("#name") == "Asha", res)
        s.close()

        # --- Playwright cannot click, but the control is on top and enabled --------------------------------------
        s, nav = fresh(pool, "REF", False)
        res, _ = nav.act({"type": "click", "ref": ref_of(nav, "button", "Moving")})
        check("REF: unstable (animated) control gets the direct-click fallback", "clicked (fallback: direct click)" in res and res.startswith("ok"), res)
        check("REF: the fallback click took effect and is recorded", text_of(s, "#movedlog") == "moved 1" and nav.fallback == "direct click", (nav.fallback, text_of(s, "#movedlog")))
        s.close()

        # --- a disabled control is not clicked through ------------------------------------------------------------
        s, nav = fresh(pool, "REF", False)
        res, _ = nav.act({"type": "click", "ref": ref_of(nav, "button", "Pay now")})
        check("REF: disabled control is reported, not forced", res.startswith("can't click") and "disabled" in res, res)
        s.close()
    finally:
        pool.close()

    # --- the reference path must replay the Escape the sighted agent pressed --------------------------------------
    steps = [Step(0, "", "", {"type": "click", "ref": "el:1"}, "ok; pressed Escape first because <div> covered it", "u", "#search", fallback="escape"),
             Step(1, "", "", {"type": "click", "ref": "el:2"}, "ok", "u", "#next")]
    path = path_from_reference(Outcome("REF", "done", "", steps))
    check("path_from_reference replays the Escape before the click", path == [{"press": "Escape"}, {"click": "#search"}, {"click": "#next"}], path)

    print("FAILURES:", len(FAILURES))
    return len(FAILURES)


def test_click_fallbacks():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
