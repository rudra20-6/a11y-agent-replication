"""Offline check (no LLM) on GOV.UK-style markup:
the sighted user clicks a radio's visible label (the hidden radio is what gets checked), then submits the form (a full
page load, which a screen reader announces by itself). An accessible page: no persona should get a finding.
Also: what sighted agents are offered to click inside a <main tabindex=-1>.

Usage: python tests/test_real_site_fixes.py      (prints FAILURES: 0 when everything holds)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.benchserver import serve
from a11y_agent.browser import BrowserPool
from a11y_agent.checker import PathChecker
from a11y_agent.pipeline import _execute, _resolve

FAILURES: list[str] = []


def check(name: str, cond: bool, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   -> {detail}"), flush=True)
    if not cond:
        FAILURES.append(name)


def main():
    base, httpd = serve(directory=ROOT / "tests" / "fixtures" / "govuk_like")
    pool = BrowserPool()
    try:
        steps = [{"click": "label[for=yes]"}, {"click": "#continue"}]
        pc = PathChecker(pool)
        for p in ("P1", "P2", "P3", "P5"):
            fs = pc.run_profile(p, base + "index.html", steps, _resolve, _execute)
            check(f"{p}: no findings on an accessible radio + submit", not fs, [(f.check, f.message) for f in fs])
        check("no tool errors", not pc.tool_errors, pc.tool_errors)
        s = pool.session(__import__("a11y_agent.browser", fromlist=["Viewport"]).Viewport(1280, 800))
        s.goto(base + "index.html")
        h = _resolve(s, {"click": "label[for=yes]"})
        check("a label resolves to its radio", h.evaluate("e => e.id") == "yes")
        h = _resolve(s, {"click": "#continue"})
        check("a button resolves to itself", h.evaluate("e => e.id") == "continue")
        # A clickable-looking div inside <main tabindex=-1> must be listed for sighted agents; main and h1 must not
        s.goto(base + "divbutton.html")
        els = [(e["tag"], e["text"]) for e in s.interactive_elements(False)]
        check("a pointer-cursor div inside <main tabindex=-1> is offered to sighted agents", ("div", "Continue") in els, els)
        check("<main>/<h1> with tabindex=-1 are not offered as controls", not any(t in ("main", "h1") for t, _ in els), els)
        # Scrolling after typing in a number field scrolls the page and leaves the value alone
        from a11y_agent.navigator import Navigator
        nav = Navigator(s, "P3", None, 5)
        s.goto(base + "scroll.html")
        obs, _ = nav.observe()
        ref = next(l.split()[0].strip("[]") for l in obs.splitlines() if "el:" in l and "number" in l.lower())
        nav.act({"type": "type", "ref": ref, "text": "5000"})
        nav.act({"type": "scroll", "dir": "down"})
        y, v = s.page.evaluate("[window.scrollY, document.querySelector('#amt').value]")
        check("scroll after typing a number moves the page and keeps the value", y > 0 and v == "5000", (y, v))
        s.close()
    finally:
        pool.close()
        httpd.shutdown()

    # A page load that times out is retried
    from a11y_agent.browser import Session

    class SlowPage:
        def __init__(self, fails):
            self.fails, self.calls, self.waited = fails, 0, 0

        def goto(self, url, **kw):
            self.calls += 1
            if self.calls <= self.fails:
                raise RuntimeError('Page.goto: Timeout 60000ms exceeded.\nCall log:\n  - navigating to "x"')

        def wait_for_timeout(self, ms):
            self.waited += ms

    fake = type("S", (), {"settle": lambda self, ms=None: None})()
    fake.page = SlowPage(1)
    Session.goto(fake, "https://example.org/")
    check("a page load that times out once is retried and succeeds", fake.page.calls == 2 and fake.page.waited >= 15000,
          (fake.page.calls, fake.page.waited))
    fake.page = SlowPage(5)
    try:
        Session.goto(fake, "https://example.org/")
        gave_up = False
    except RuntimeError:
        gave_up = True
    check("after three timeouts it gives up (the error is recorded as a tool error)", gave_up and fake.page.calls == 3,
          fake.page.calls)
    print(f"FAILURES: {len(FAILURES)}")


if __name__ == "__main__":
    main()
