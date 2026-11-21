"""The deterministic methods (our rule checks, axe) on the Ma11y barriers. No model is called.

For each labelled unit (bench/mutants/ma11y.yaml or ma11y_path.yaml) and each task's clean app:
- **axe**, on load and at every gold-path state. Ma11y's oracle: a mutant is **killed** when axe reports a violation on
  the mutated element (the node, or an ancestor or descendant of it, carries data-ma11y) that the clean run of the
  same task doesn't have.
- **Our rule checks** along the gold path, every persona. A finding is new if the clean run lacks it. Ma11y's oracle,
  adapted, since a finding records a step and a readable target rather than a node: a new finding **kills** the mutant
  when it is at a step whose control is the mutated element (on_path_steps), or its target names the mutated
  element's text (**strict**), or, since page-level findings (e.g. "image in main content") record no element, it cites
  one of the operator's WCAG criteria (**sc**: the only difference from the clean run is the mutation). Both counts
  are reported. Task-level recall: the personas with a new finding, against the unit's `affects`.
- False alarms: new findings for personas outside affects + may_affect.

Usage: python experiments/ma11y_bench.py [--placement page|path] [--only ID,ID]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.baselines import axe_run  # noqa: E402
from a11y_agent.bench import CATALOGS, do_step, install_mutant, load_mutants, load_tasks, resolve_target  # noqa: E402
from a11y_agent.benchserver import serve  # noqa: E402
from a11y_agent.browser import BrowserPool, Viewport  # noqa: E402
from a11y_agent.checker import PathChecker, findings_to_dicts  # noqa: E402
from a11y_agent.config import BENCH, RUNS, SETTINGS  # noqa: E402

ON_MUTANT_JS = """(targets) => targets.map((t) => {
  try { const e = document.querySelector(t); return !!(e && (e.closest('[data-ma11y]') || e.querySelector('[data-ma11y]'))); }
  catch (err) { return false; }
})"""


def axe_states(pool, base, task, mutant=None):
    """axe violations at load and after every gold step: [(rule id, target, on the mutated element?)]."""
    s = pool.session(Viewport(*SETTINGS.desktop))
    out = []
    try:
        install_mutant(s, mutant)
        s.goto(base + task.start)

        def snap():
            for v in axe_run(s):
                if v["kind"] != "violation":
                    continue
                flags = s.page.evaluate(ON_MUTANT_JS, v["targets"]) if mutant else [False] * len(v["targets"])
                out.extend((v["id"], t, bool(f)) for t, f in zip(v["targets"], flags))
        snap()
        for step in task.gold_path:
            try:
                do_step(s, step)
                s.settle(300)
            except Exception:
                break   # the mutation broke the gold path; what was seen so far still counts
            snap()
    finally:
        s.close()
    return out


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip().lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", choices=["page", "path"], default="page")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    cat = BENCH / "mutants" / ("ma11y_path.yaml" if a.placement == "path" else "ma11y.yaml")
    muts = load_mutants(cat)
    if a.only:
        muts = {k: v for k, v in muts.items() if k in a.only.split(",")}
    base, httpd = serve()
    pool = BrowserPool()
    checker = PathChecker(pool)
    tasks = load_tasks()
    used = sorted({m.task for m in muts.values()})
    clean_rules, clean_axe = {}, {}
    rows = []
    try:
        for tid in used:
            t = tasks[tid]
            clean_rules[tid] = checker.run(base + t.start, t.gold_path, resolve_target, do_step)
            clean_axe[tid] = {(r, tg) for r, tg, _ in axe_states(pool, base, t)}
            print(f"clean {tid:22s} rule findings {len(clean_rules[tid])}, axe violations {len(clean_axe[tid])}", flush=True)
        for m in muts.values():
            t = tasks[m.task]
            p = m.params
            # mutated element's text, from the labelling run (first target's html)
            texts = [norm(x.get("html", ""))[:40] for x in p.get("targets", [])]
            try:
                fs = checker.run(base + t.start, t.gold_path, resolve_target, do_step, prepare=lambda s, m=m: install_mutant(s, m))
            except Exception as e:   # one unit must not end the run; recorded as a tool error
                checker.tool_errors.append({"unit": m.id, "where": "run", "error": str(e)[:200]})
                fs = []
            ck = {f.key() for f in clean_rules[m.task]}
            new = [f for f in fs if f.key() not in ck]
            on_steps = set(p.get("on_path_steps", []))
            rule_kill = [f for f in new if f.step in on_steps or any(tx and tx[:20] in norm(f.target) for tx in texts)]
            op_sc = {x.strip() for x in str(m.sc).split(",") if x.strip()}
            rule_kill_sc = [f for f in new if f in rule_kill or op_sc & {x.strip() for x in str(f.sc).split(",")}]
            flagged = sorted({f.profile for f in new})
            tp = sorted(set(flagged) & set(m.affects))
            fp = sorted(set(flagged) - set(m.affects) - set(m.may_affect))
            try:
                ax = axe_states(pool, base, t, m)
            except Exception as e:
                checker.tool_errors.append({"unit": m.id, "where": "axe", "error": str(e)[:200]})
                ax = []
            axe_new = {(r, tg) for r, tg, on in ax if on and (r, tg) not in clean_axe[m.task]}
            row = {"unit": m.id, "failure": p.get("failure"), "task": m.task, "on_path": p.get("on_path"),
                   "severity": m.severity, "affects": m.affects, "may_affect": m.may_affect,
                   "axe_expected": m.axe_expected, "axe_rule_expected": p.get("axe_rule", ""),
                   "axe_kill": bool(axe_new), "axe_rules": sorted({r for r, _ in axe_new}),
                   "rules_kill": bool(rule_kill), "rules_kill_sc": bool(rule_kill_sc), "rules_flagged": flagged, "rules_tp": tp, "rules_fp": fp,
                   "rules_new": findings_to_dicts(new)[:12]}
            rows.append(row)
            print(f"{m.id:16s} path={str(row['on_path'])[0]} axe={'K' if row['axe_kill'] else '-'}{','.join(row['axe_rules'])[:28]:28s} "
                  f"rules={'K' if row['rules_kill'] else ('k' if row['rules_kill_sc'] else '-')} flagged={','.join(flagged) or '-':10s} affects={','.join(m.affects) or '-':9s} "
                  f"fp={','.join(fp) or '-'}", flush=True)
    finally:
        pool.close()
        httpd.shutdown()
    n = len(rows)
    on = [r for r in rows if r["affects"]]
    pairs = sum(len(r["affects"]) for r in on)
    summary = {
        "placement": a.placement, "units": n,
        "axe_killed": sum(r["axe_kill"] for r in rows), "rules_killed_strict": sum(r["rules_kill"] for r in rows),
        "rules_killed_sc": sum(r["rules_kill_sc"] for r in rows),
        "either_killed_sc": sum(r["rules_kill_sc"] or r["axe_kill"] for r in rows),
        "on_path_units": len(on), "persona_pairs": pairs, "rules_pairs_found": sum(len(r["rules_tp"]) for r in on),
        "rules_false_alarm_personas": sum(len(r["rules_fp"]) for r in rows),
        "clean_rule_findings": {k: len(v) for k, v in clean_rules.items()},
        "rule_tool_errors": len(checker.tool_errors),
    }
    out = RUNS / f"ma11y_bench_{a.placement}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows, "tool_errors": checker.tool_errors,
                               "clean_rules": {k: findings_to_dicts(v) for k, v in clean_rules.items()}}, indent=1), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
