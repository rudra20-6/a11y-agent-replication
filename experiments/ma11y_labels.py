"""Label the Ma11y barriers before any tool runs on them.

For each of Ma11y's 25 operators and each of BenchBook's 7 tasks, the gold (sighted mouse) path is replayed with the
operator injected (bench/mutants/ma11y.js). What gets recorded, mechanically:

1. **applied**: did the operator find a target on any page state of the task? Units where it didn't are dropped.
2. **on_path**: is the gold path's next control the mutated element, or inside it, or containing it?
3. **path_ok**: does the gold path still complete the task?

**Ground truth per unit:**
- **affects:** the personas that the operator's WCAG failure concerns, from the fixed table below, when the target is
  on the task path; empty when it is off the path.
- **may_affect:** the same personas when the target is off the path. A report there is not a false positive, and not
  required.
- **severity:** `breaks_all` when even the gold path fails (not an accessibility barrier specific to a persona);
  `blocks` when on the path and the check is Reach/Operate/Identify; otherwise `degrades`.
- **axe_expected:** `caught` exactly when Ma11y's own oracle (src/tool-runner/oracle/failure-mapping.js) lists an axe
  rule for the failure.

The table and these rules were fixed before any run.

Placements:
- **page** (default): Ma11y's own rule, the first matching element on each page state. Comparable to the Ma11y paper,
  but the target is usually header, footer or navigation, so few units fall on a task path.
- **path**: the same conditions and mutation, restricted to elements that are a gold-path control, inside one, or
  contain one. Page-wide operators (F24, F25, F77) don't apply. This measures what task-level testing is for.

Usage: python experiments/ma11y_labels.py [--placement page|path]
  (writes bench/mutants/ma11y.yaml or ma11y_path.yaml)
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.bench import MUTANTS_JS, do_step, load_tasks, resolve_target, succeeded  # noqa: E402
from a11y_agent.benchserver import serve  # noqa: E402
from a11y_agent.browser import BrowserPool, Viewport  # noqa: E402
from a11y_agent.config import BENCH, SETTINGS  # noqa: E402

# failure: (name, WCAG SC, our check, personas the failure concerns)
#   P1 screen reader, P2 keyboard only, P3 400% zoom, P4 colour vision, P5 voice control; [] = none of our personas.
# Grounded in each persona card's "typical barriers" and "rule checks" (a11y_agent/personas.yaml).
TABLE = {
    "F2":  ("Replace Header with Paragraph", "1.3.1", "Identify", ["P1"]),
    "F3":  ("Replace Image with Div", "1.1.1", "Identify", ["P1"]),
    "F4":  ("Make Text Blink", "2.2.2", "none", []),
    "F9":  ("Change Context on Blur", "3.2.5", "Notice", ["P1", "P2"]),
    "F22": ("Change Context on Click", "3.2.5", "Notice", ["P1"]),
    "F24": ("Change Foreground Color", "1.4.3", "none", []),            # contrast is not modelled by P3 (zoom only)
    "F25": ("Change Page Title", "2.4.2", "Identify", ["P1"]),
    "F30": ("Change Image Alt Text", "1.1.1", "Identify", ["P1"]),
    "F32": ("Add Space Between Characters", "1.3.2", "Identify", ["P1", "P5"]),
    "F36": ("Change Context on Input", "3.2.2", "Notice", ["P1", "P2"]),
    "F37": ("Change Context on Selection", "3.2.2", "Notice", ["P1", "P2"]),
    "F42": ("Replace Anchor Text with Span", "1.3.1, 2.1.1, 4.1.2", "Reach", ["P1", "P2", "P5"]),
    "F44": ("Change Tab Index Order", "2.4.3", "Reach", ["P2"]),
    "F54": ("Change Device-Specific Pointer", "2.1.1", "Operate", ["P2"]),
    "F55": ("Remove Focus from Anchor Text", "2.1.1, 2.4.7, 3.2.1", "Reach", ["P1", "P2"]),
    "F65": ("Remove Image Alt Text", "1.1.1", "Identify", ["P1"]),
    "F68": ("Remove Input Names", "1.3.1, 4.1.2", "Identify", ["P1", "P5"]),
    "F73": ("Remove Anchor Text Decorations", "1.4.1", "Identify", ["P4"]),
    "F77": ("Make Duplicate Ids", "4.1.1", "none", []),                 # 4.1.1 is obsolete in WCAG 2.2
    "F78": ("Remove Outline from Anchor Text", "2.4.7", "Reach", ["P2"]),
    "F80": ("Change Input Font Size", "1.4.4", "none", []),             # pt sizes scale with page zoom, so P3 is unaffected
    "F89": ("Remove Anchor Text Identifier", "2.4.4, 4.1.2", "Identify", ["P1", "P5"]),
    "F91": ("Replace Table Headers with Table Data", "1.3.1", "Identify", ["P1"]),
    "F94": ("Change Paragraph Font Size", "1.4.4", "Reach", ["P3"]),    # vh units don't grow with zoom
    "F96": ("Change Button Label", "2.5.3", "Identify", ["P5"]),
}
AXE_RULE = {"F44": "tabindex", "F65": "image-alt", "F68": "label", "F73": "link-in-text-block", "F77": "duplicate-id",
            "F89": "link-name"}   # Ma11y failure-mapping.js, Axe column; every other failure maps to ''


def gold_css(task) -> list[str]:
    """The CSS selectors of the controls a task's gold path acts on. Playwright's :has-text() is not CSS, so it is
    dropped (the selector then matches every element of that kind, e.g. every fare's radio)."""
    out = []
    for step in task.gold_path:
        kind, arg = next(iter(step.items()))
        css = arg if kind == "click" else (arg[0] if kind == "fill" else None)
        if css:
            out.append(re.sub(r":has\(label:has-text\([^)]*\)\)", "", re.sub(r":has-text\([^)]*\)", "", css)))
    return out


def unit_params(task, failure, placement):
    m = {"op": "ma11y", "failure": failure}
    if placement == "path":
        m.update(placement="path", path=gold_css(task))
    return m


def label(pool, base, task, failure, placement="page"):
    s = pool.session(Viewport(*SETTINGS.desktop))
    try:
        s.ctx.add_init_script(f"window.__MUTANTS = [{json.dumps(unit_params(task, failure, placement))}];")
        s.ctx.add_init_script(MUTANTS_JS)   # already includes ma11y.js
        s.goto(base + task.start)
        on_path, path_ok, error = [], True, ""
        for i, step in enumerate(task.gold_path):
            try:
                el = resolve_target(s, step)
                if el is not None and el.evaluate(
                        "e => !!(e.closest('[data-ma11y]') || e.querySelector('[data-ma11y]'))"):
                    on_path.append(i)
                do_step(s, step)
                s.settle(300)
            except Exception as e:   # the gold path itself breaks under this mutation
                path_ok, error = False, f"step {i}: {str(e).splitlines()[0][:120]}"
                break
        if path_ok:
            path_ok = succeeded(s, task)
            if not path_ok:
                error = "gold path ran but the task's success condition is false"
        log = s.page.evaluate("window.__MA11Y_LOG || []")
        return {"applied": bool(log), "on_path_steps": on_path, "path_ok": path_ok, "path_error": error,
                "targets": [{"route": x["route"], "tag": x["tag"], "html": x["html"][:160]} for x in log][:6]}
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", choices=["page", "path"], default="page")
    placement = ap.parse_args().placement
    base, httpd = serve()
    pool = BrowserPool()
    tasks = load_tasks()
    units, skipped = [], []
    try:
        for failure, (name, sc, check, personas) in TABLE.items():
            for tid, task in tasks.items():
                r = label(pool, base, task, failure, placement)
                tag = f"{failure:4s} {tid:22s}"
                if not r["applied"]:
                    skipped.append(f"{failure}/{tid}")
                    print(f"{tag} not applicable", flush=True)
                    continue
                on = bool(r["on_path_steps"])
                if not r["path_ok"]:
                    severity = "breaks_all"
                elif on and personas:
                    severity = "blocks" if check in ("Reach", "Operate", "Identify") else "degrades"
                else:
                    severity = "degrades" if personas else "none"
                units.append({
                    "id": f"{'MP' if placement == 'path' else 'M'}_{failure}_{tid.split('_')[0]}", **unit_params(task, failure, placement),
                    "name": name,
                    "task": tid, "check": check, "sc": sc,
                    "affects": personas if (on and r["path_ok"]) else [],
                    "may_affect": [] if (on and r["path_ok"]) else personas,
                    "severity": severity, "axe_expected": "caught" if failure in AXE_RULE else "missed",
                    "axe_rule": AXE_RULE.get(failure, ""), "on_path": on, "on_path_steps": r["on_path_steps"],
                    "path_ok": r["path_ok"], "path_error": r["path_error"], "targets": r["targets"]})
                print(f"{tag} applied  on_path={on!s:5s} path_ok={r['path_ok']!s:5s} affects={','.join(units[-1]['affects']) or '-'}"
                      f"  first target: {r['targets'][0]['tag']} {r['targets'][0]['html'][:60]!r}", flush=True)
    finally:
        pool.close()
        httpd.shutdown()
    out = BENCH / "mutants" / ("ma11y_path.yaml" if placement == "path" else "ma11y.yaml")
    header = (f"# Ma11y benchmark labels, {placement} placement. GENERATED by experiments/ma11y_labels.py from the gold paths, before any\n"
              "# tool was run on these units. Do not edit by hand: change the rules in the script and regenerate.\n"
              f"# {len(units)} applicable units of 25 operators x 7 tasks; not applicable: {len(skipped)}.\n")
    out.write_text(header + yaml.safe_dump({"mutants": units, "not_applicable": skipped}, sort_keys=False, allow_unicode=True,
                                            width=200), encoding="utf-8")
    on = [u for u in units if u["affects"]]
    print(f"\n{len(units)} applicable units; {len(on)} with the target on the task path (scored for task-level recall, "
          f"{sum(len(u['affects']) for u in on)} persona pairs); {sum(u['severity'] == 'breaks_all' for u in units)} break the gold path; "
          f"{len(skipped)} operator-task pairs not applicable. Wrote {out}")


if __name__ == "__main__":
    main()
