"""Label check for the Ma11y task-path units: does each injected barrier actually reach each persona?

No model is involved. For every unit and persona, the gold path is replayed with plain pointer actions up to the first
step that touches the mutated element; that step is then performed the way the persona's harness performs it
(a11y_agent/navigator.py `act`):
  P1  activate through the accessibility tree: focus + Enter (Space on checkbox/radio) if the node is focusable;
      a DOM click if it has an interactive role but can't take focus; nothing if it has no interactive role.
      Fields: focus, Control+A, type, then Tab to leave the field.
  P2  keyboard only: Tab until focus is on the control (inside a grid or radio group, arrow keys move focus, which
      is done here by focusing the roving-tabindex cell); then Enter (Space on checkbox/radio). Fields: type, Tab.
  P3  mouse at 320 px: a real click at the middle of the control (Playwright), fields filled and committed as the
      harness does (fill, input, change).
Recorded: windows opened, form submits, whether focus reached and stayed on the control, and for P1 the accessibility
node of the control plus whether the mutated text or a column header appears in what P1 reads.

Usage: python experiments/ma11y_reach.py   (writes results/<date>/ma11y_reach.json; the paper's copy is data/ma11y_reach.json)
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.bench import CATALOGS, _visible_locator, do_step, install_mutant, load_mutants, load_tasks  # noqa: E402
from a11y_agent.benchserver import serve  # noqa: E402
from a11y_agent.browser import INTERACTIVE_ROLES, BrowserPool, Viewport  # noqa: E402
from a11y_agent.config import SETTINGS  # noqa: E402

COUNT_SUBMIT = """(() => { const o = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function () {
    try { sessionStorage.setItem('__submits', String(1 + Number(sessionStorage.getItem('__submits') || 0))); } catch (_) {}
    return o.apply(this, arguments); }; })();"""
IN_TARGET = "(e) => { const a = document.activeElement; return !!a && a !== document.body && (a === e || e.contains(a)); }"


def target(s, step):
    kind, arg = next(iter(step.items()))
    if kind == "click":
        return _visible_locator(s, arg).element_handle()
    return s.page.locator(arg[0]).first.element_handle()


def keyboard_step(s, persona, step, h, out):
    kind, arg = next(iter(step.items()))
    node = s.ax_of(h) or {}
    out["ax"] = {k: node.get(k) for k in ("role", "name")} | {"focusable": bool((node.get("props") or {}).get("focusable"))}
    if persona == "P1":
        if kind == "click" and node.get("role") not in INTERACTIVE_ROLES:
            out["can_act"] = "no interactive role: P1 can't activate it"
            return
        if not out["ax"]["focusable"]:
            if kind == "click":
                h.evaluate("e => e.click()")
                out["can_act"] = "dom click (interactive role, not focusable)"
                return
            out["can_act"] = "field can't take focus"
            return
        h.focus()
    else:   # P2: Tab until focus is on the control
        s.page.evaluate("() => { document.activeElement && document.activeElement.blur && document.activeElement.blur(); }")
        reached = False
        for _ in range(120):
            s.page.keyboard.press("Tab")
            if h.evaluate(IN_TARGET):
                reached = True
                break
        if not reached and node.get("role") in ("gridcell", "radio", "option") and h.evaluate("e => e.tabIndex === -1 || e.type === 'radio'"):
            h.focus()   # arrow keys move focus inside a grid / radio group
            reached = h.evaluate(IN_TARGET)
            out["via_arrows"] = True
        if not reached:
            out["can_act"] = "Tab never reaches it"
            return
    s.page.wait_for_timeout(150)
    out["focus_held"] = h.evaluate(IN_TARGET)
    if kind == "click":
        s.page.keyboard.press("Space" if node.get("role") in ("checkbox", "radio", "switch") else "Enter")
    else:
        s.page.keyboard.press("Control+A")
        s.page.keyboard.type(arg[1], delay=10)
        s.page.keyboard.press("Tab")   # leave the field
    out["can_act"] = "yes"


def pointer_step(s, step, out):
    kind, arg = next(iter(step.items()))
    if kind == "click":
        _visible_locator(s, arg).click(timeout=5000)
    else:
        loc = s.page.locator(arg[0]).first
        loc.click(timeout=5000)
        loc.fill(arg[1])
        loc.dispatch_event("input")
        loc.dispatch_event("change")
    out["can_act"] = "yes"


def check(pool, base, task, m, persona):
    vp = SETTINGS.zoom_viewport if persona == "P3" else SETTINGS.desktop
    s = pool.session(Viewport(*vp))
    out = {"unit": m.id, "persona": persona}
    popups = []
    try:
        s.ctx.add_init_script(COUNT_SUBMIT)
        install_mutant(s, m)
        s.ctx.on("page", lambda p: popups.append(1))
        s.goto(base + task.start)
        first = min(m.params.get("on_path_steps") or [0])
        for step in task.gold_path[:first]:
            do_step(s, step)
            s.settle(300)
        step = task.gold_path[first]
        s.page.evaluate("() => sessionStorage.setItem('__submits', '0')")
        h = target(s, step)
        out["step"] = first
        out["mutated_in_target"] = bool(h.evaluate("e => !!(e.closest('[data-mutated]') || e.querySelector('[data-mutated]'))"))
        if persona == "P1":
            tree = s.ax_tree(max_lines=100000).serialise()
            texts = [re.sub(r"<[^>]+>", " ", t.get("html", "")).strip() for t in m.params.get("targets", [])]
            out["p1_reads_mutated_text"] = [t for t in texts if t and len(t) < 40 and t in tree]
            out["p1_tree_has_columnheader"] = "columnheader" in tree
        if persona == "P3":
            pointer_step(s, step, out)
        else:
            keyboard_step(s, persona, step, h, out)
        s.page.wait_for_timeout(800)
        try:
            out["submits"] = int(s.page.evaluate("() => Number(sessionStorage.getItem('__submits') || 0)"))
        except Exception as e:
            out["submits"] = f"? {str(e)[:60]}"
        out["windows_opened"] = len(popups)
    except Exception as e:
        out["error"] = str(e).splitlines()[0][:160]
    finally:
        s.close()
    return out


def main():
    base, httpd = serve()
    pool = BrowserPool()
    tasks, muts = load_tasks(), load_mutants(CATALOGS["ma11y_path"])
    rows = []
    try:
        for m in muts.values():
            for p in ("P1", "P2", "P3"):
                r = check(pool, base, tasks[m.task], m, p)
                rows.append(r)
                print(json.dumps(r, ensure_ascii=False), flush=True)
    finally:
        pool.close()
        httpd.shutdown()
    out = ROOT / "results" / time.strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)
    (out / "ma11y_reach.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out / "ma11y_reach.json")


if __name__ == "__main__":
    main()
