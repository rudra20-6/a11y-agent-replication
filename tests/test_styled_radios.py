"""Offline check (no LLM) of D95: a radio whose real input is invisible and whose label draws the state (the GOV.UK
pattern) shows its drawn state to the clicking personas, and a click on its label is reported as a tick, not as
"nothing visible changed". A visible native checkbox keeps its state on the input, not on its label.

Usage: python tests/test_styled_radios.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.navigator import Navigator

APP = (ROOT / "tests" / "fixtures" / "govuk_like" / "radios.html").as_uri()
FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


def ref_of(s, text: str, tag: str) -> dict:
    return next(e for e in s.interactive_elements() if e["text"] == text and e["tag"] == tag)


def main() -> int:
    pool = BrowserPool()
    try:
        for mode in ("REF", "P3"):
            s = pool.session(Viewport(1280, 800) if mode == "REF" else Viewport(320, 800))
            s.goto(APP)
            s.settle(300)
            nav = Navigator(s, mode, None, 5)
            nav.observe()
            yes = ref_of(s, "Yes", "label")
            check(f"{mode}: the hidden radio's label is listed, unticked", not yes["checked"], yes)
            res, _ = nav.act({"type": "click", "ref": yes["ref"]})
            check(f"{mode}: clicking the label is reported as a tick", "it is now ticked" in res, res)
            check(f"{mode}: and not as 'nothing visible changed' only", "now ticked" in res, res)
            check(f"{mode}: the label now shows [checked]", ref_of(s, "Yes", "label")["checked"])
            res, _ = nav.act({"type": "click", "ref": ref_of(s, "No", "label")["ref"]})
            check(f"{mode}: picking No ticks No", "it is now ticked" in res and ref_of(s, "No", "label")["checked"], res)
            check(f"{mode}: and Yes is no longer shown ticked", not ref_of(s, "Yes", "label")["checked"])
            plain = [e for e in s.interactive_elements() if e["text"] == "Plain checkbox"]
            check(f"{mode}: a visible checkbox's label does not carry its state",
                  all(not e["checked"] for e in plain if e["tag"] == "label"), plain)
            lab = [e for e in plain if e["tag"] == "label"]
            if lab:   # v3 (D97): a visible tick is reported too (v2.5 reported only ticks drawn on a label)
                res, _ = nav.act({"type": "click", "ref": lab[0]["ref"]})
                check(f"{mode}: a visible checkbox's label click reports the tick", "it is now ticked" in res, res)
            s.close()
    finally:
        pool.close()
    print(f"FAILURES: {len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
