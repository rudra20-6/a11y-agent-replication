"""Rule-based baselines: axe on load (what scanners do today) and axe at every state of a task path."""

from __future__ import annotations

from .browser import Session
from .config import VENDOR

AXE_JS = (VENDOR / "axe.min.js").read_text(encoding="utf-8")


def axe_run(session: Session) -> list[dict]:
    if not session.page.evaluate("() => !!window.axe"):
        session.page.add_script_tag(content=AXE_JS)
    return session.page.evaluate("""async () => {
      const r = await axe.run(document, { resultTypes: ['violations', 'incomplete'] });
      const pack = (v, kind) => ({ id: v.id, kind, impact: v.impact, help: v.help,
        targets: v.nodes.map(n => n.target.join(' ')).slice(0, 20) });
      return [...r.violations.map(v => pack(v, 'violation')), ...r.incomplete.map(v => pack(v, 'needs-review'))];
    }""")


def axe_on_load(session: Session, url: str) -> list[dict]:
    session.goto(url)
    return axe_run(session)


def merge(results: list[list[dict]]) -> list[dict]:
    """Union of axe results across states, keyed by rule + target."""
    seen, out = set(), []
    for res in results:
        for v in res:
            for t in v["targets"] or [""]:
                key = (v["id"], v["kind"], t)
                if key not in seen:
                    seen.add(key)
                    out.append({"id": v["id"], "kind": v["kind"], "impact": v["impact"], "target": t})
    return out
