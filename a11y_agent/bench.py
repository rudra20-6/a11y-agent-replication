"""Benchmark plumbing: gold tasks, mutants, gold-path replay. Only experiments use this; the tool itself never does."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .browser import Session
from .config import BENCH

MUTANTS_JS = (BENCH / "mutants" / "mutants.js").read_text(encoding="utf-8")
# Extra operator files are appended when present; each file applies only the ops it defines and ignores the rest.
_HELDOUT = BENCH / "mutants" / "heldout.js"
if _HELDOUT.exists():
    MUTANTS_JS += "\n" + _HELDOUT.read_text(encoding="utf-8")
# Ma11y's 25 operators (ISSTA 2024, MIT licence), ported to run in the page; each picks its own target.
MA11Y_JS = (BENCH / "mutants" / "ma11y.js").read_text(encoding="utf-8")
MUTANTS_JS += "\n" + MA11Y_JS
CATALOGS = {"dev": BENCH / "mutants" / "catalog.yaml", "heldout": BENCH / "mutants" / "heldout.yaml",
            "ma11y": BENCH / "mutants" / "ma11y.yaml", "ma11y_path": BENCH / "mutants" / "ma11y_path.yaml"}


@dataclass
class GoldTask:
    id: str
    start: str
    goal: str
    success: str
    gold_path: list = field(default_factory=list)


@dataclass
class Mutant:
    id: str
    op: str
    task: str
    affects: list
    may_affect: list
    check: str
    sc: str
    severity: str
    axe_expected: str
    params: dict


def load_tasks(path: Path = BENCH / "tasks" / "benchbook.yaml") -> dict[str, GoldTask]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {t["id"]: GoldTask(**t) for t in data["tasks"]}


def load_mutants(path: Path = BENCH / "mutants" / "catalog.yaml") -> dict[str, Mutant]:
    out = {}
    for m in yaml.safe_load(path.read_text(encoding="utf-8"))["mutants"]:
        meta = {k: m.pop(k) for k in ("id", "task", "affects", "may_affect", "check", "sc", "severity", "axe_expected")}
        out[meta["id"]] = Mutant(op=m["op"], params=m, **meta)
    return out


def install_mutant(session: Session, mutant: Mutant | None) -> None:
    """Must be called before navigation: the mutant script runs on every new document."""
    if mutant is None:
        return
    session.ctx.add_init_script(f"window.__MUTANTS = {json.dumps([mutant.params])};")
    session.ctx.add_init_script(MUTANTS_JS)


# Scoring probe: did the agent's action at a step involve the mutated element (clicked, focused, typed into or
# a key pressed on it, or a small control containing it)? Kept in sessionStorage, so a reload caused by the barrier
# (e.g. a form that submits on change) doesn't lose it. Benchmark instrumentation only: the agents never see it.
PROBE_JS = """(() => { if (window.__mutProbe) return; window.__mutProbe = true;
  const hit = (t) => { if (!t || t.nodeType !== 1) return false;
    for (const m of document.querySelectorAll('[data-mutated]')) {
      if (m === t || m.contains(t)) return true;
      if (t !== document.body && t !== document.documentElement && t.contains(m) && t.querySelectorAll('*').length < 30) return true;
    }
    return false; };
  for (const ev of ['click', 'focusin', 'input', 'change', 'keydown'])
    document.addEventListener(ev, (e) => { try { if (hit(e.target)) sessionStorage.setItem('__mutTouched', '1'); } catch (_) {} }, true);
})();"""


def install_probe(session: Session) -> None:
    session.ctx.add_init_script(PROBE_JS)


def read_probe(session: Session) -> dict:
    """What happened since the last read (then reset)."""
    return session.page.evaluate("() => { let t = false; try { t = sessionStorage.getItem('__mutTouched') === '1'; "
                                 "sessionStorage.removeItem('__mutTouched'); } catch (_) {} return {touched: t}; }")


def succeeded(session: Session, task: GoldTask) -> bool:
    try:
        return bool(session.page.evaluate(task.success))
    except Exception:
        return False


def _visible_locator(session: Session, css: str):
    page = session.page
    loc = page.locator(css).first
    if loc.count() and loc.is_visible():
        return loc
    # The target may have been replaced by a look-alike (e.g. a button turned into a div): use what a
    # sighted mouse user would click, i.e. the visible element showing the same text.
    text = loc.text_content() if loc.count() else None
    if text and text.strip():
        alt = page.get_by_text(text.strip(), exact=True).locator("visible=true").first
        if alt.count():
            return alt
    raise RuntimeError(f"nothing visible to click for {css}")


def resolve_target(session: Session, step: dict):
    """ElementHandle of the control a gold step acts on (None for key presses and waits)."""
    kind, arg = next(iter(step.items()))
    if kind == "click":
        return _visible_locator(session, arg).element_handle()
    if kind == "fill":
        return session.page.locator(arg[0]).first.element_handle()
    return None


def do_step(session: Session, step: dict) -> None:
    kind, arg = next(iter(step.items()))
    if kind == "click":
        _visible_locator(session, arg).click(timeout=5000)
    elif kind == "fill":
        session.page.locator(arg[0]).first.fill(arg[1], timeout=5000)
        session.page.locator(arg[0]).first.dispatch_event("input")
    elif kind == "press":
        session.page.keyboard.press(arg)
    elif kind == "wait":
        session.page.wait_for_timeout(int(arg))


def replay_gold(session: Session, task: GoldTask, on_state=None) -> list[dict]:
    """Run the gold path with pointer actions. on_state(i, step) is called after each step settles."""
    log = []
    for i, step in enumerate(task.gold_path):
        do_step(session, step)
        session.settle(300)
        log.append({"i": i, "step": step})
        if on_state:
            on_state(i, step)
    return log
