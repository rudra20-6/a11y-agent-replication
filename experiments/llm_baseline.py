"""Baseline 3 (Research_Plan §5.2): a single LLM reads the page and lists barriers for the task.

It sees what a person reading the page source would: the HTML (every element numbered with data-k), the page's CSS,
and Chrome's accessibility tree. Two variants, like the axe baselines: on load, and at every state of the gold path
(one call per state, findings merged).

Scoring is per profile, like our checks, and stricter than the axe scoring (which counts any new violation):
  strict   a mutant is detected for profile P if a P finding points at an element inside the mutated region
           (mutant.sel). P in may_affect is tolerated; any other profile pointing into the region is a false positive.
  lenient  profiles mentioned anywhere in the mutant run but not in the clean run of the same task (no localisation).
Every finding on the clean app counts as a false alarm (BenchBook is built to be accessible); so does any finding
that points into a benign mutant's region.

Prompt history (12 Oct 2026, tuned on ONE barrier, C1 on T6, then frozen): (1) "barriers that stop or seriously slow
down the task", JSON mode; (2) "block or make it harder"; (3) plus a "checked" field to make it look first; (4) plain
-text reasoning before the JSON, and "problems the user runs into while doing the task". Gemma 4 26B returned no
barriers for C1 under all four. We stopped there so the baseline is not tuned to the benchmark; (4) is what runs.

Usage: python experiments/llm_baseline.py [--states load|all] [--only ID,ID] [--catalog dev|heldout]
Set A11Y_RPM if another LLM job is running at the same time (the free tier allows ~30 calls a minute in total).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from a11y_agent.bench import CATALOGS, do_step, install_mutant, load_mutants, load_tasks
from a11y_agent.benchserver import serve
from a11y_agent.browser import BrowserPool, Viewport
from a11y_agent.config import RUNS, SETTINGS
from a11y_agent.llm import LLM, USAGE, LLMError, QuotaExhausted

PROFILES = ("P1", "P2", "P3", "P4", "P5")
ERRORS: list[dict] = []  # states the model never answered (API errors): reported, not scored as "no barriers"

SYSTEM = """You are an accessibility auditor. You get one state of a web page: its HTML (every element carries a
data-k number), its CSS, and Chrome's accessibility tree. A user is trying to do the TASK below. List the accessibility
problems on this page that such a user runs into while doing the task (blocking it or making it harder), for any of
these users:
P1 screen reader user (blind), P2 keyboard-only user, P3 user at 400% zoom (page 320 px wide),
P4 colour-blind user, P5 voice-control user (says "click <visible label>").
Go through the page first: images, form fields and their labels, buttons and links, widgets and their keyboard
handling, focus styles, colours, error messages, and what changes after actions. Then report only barriers you can
point to on this page. An empty list is a valid answer.
Think it through in plain text first. Then end your reply with ONE JSON object in a ```json block:
{"checked": "<two or three sentences: what you looked at>",
 "barriers": [{"k": <data-k of the element, or null>, "profiles": ["P1", ...],
  "check": "Reach"|"Identify"|"Operate"|"Notice"|"Recover", "why": "<one sentence>"}]}"""

DUMP_JS = """() => {
  let k = 0;
  for (const e of document.body.querySelectorAll('*')) e.setAttribute('data-k', String(++k));
  const clone = document.body.cloneNode(true);
  clone.querySelectorAll('script, noscript, svg *').forEach(e => e.remove());
  // BenchBook's own markers would give the answer away
  clone.querySelectorAll('*').forEach(e => [...e.attributes].forEach(at => { if (at.name.startsWith('data-mut')) e.removeAttribute(at.name); }));
  const html = clone.outerHTML.replace(/\\s+/g, ' ');
  let css = '';
  for (const sh of document.styleSheets) { try { for (const r of sh.cssRules) css += r.cssText + '\\n'; } catch (e) {} }
  return { html, css };
}"""

IN_REGION_JS = """([k, sel]) => {
  const e = document.querySelector(`[data-k="${k}"]`);
  if (!e) return false;
  try { return !!(e.closest(sel) || e.querySelector(sel)); } catch (err) { return false; }
}"""


def audit(llm, s, task, state):
    dump = s.page.evaluate(DUMP_JS)
    tree = s.ax_tree(max_lines=300).serialise()
    prompt = (f"TASK: {task.goal}\nPAGE STATE: {state}\nURL: {s.page.url}\n\nHTML:\n{dump['html'][:16000]}\n\n"
              f"CSS:\n{dump['css'][:5000]}\n\nACCESSIBILITY TREE:\n{tree}")
    out = llm.json(SYSTEM, prompt, json_mode=False)
    barriers = [b for b in (out.get("barriers") or []) if isinstance(b, dict)]
    for b in barriers:
        b["profiles"] = [p for p in (b.get("profiles") or []) if p in PROFILES]
        b["state"] = state
    return barriers


def run_config(llm, pool, base, task, mutant, all_states):
    """Audit the start state (and every gold-path state if all_states). Region checks happen in the same state."""
    s = pool.session(Viewport(*SETTINGS.desktop))
    install_mutant(s, mutant)
    sel = mutant.params.get("sel") if mutant else None
    found = []
    try:
        s.goto(base + task.start)
        states = [("load", None)] + ([(f"after step {i}", st) for i, st in enumerate(task.gold_path)] if all_states else [])
        for name, step in states:
            if step is not None:
                do_step(s, step)
                s.settle(300)
            try:
                bs = audit(llm, s, task, name)
            except LLMError as e:
                ERRORS.append({"task": task.id, "mutant": mutant.id if mutant else None, "state": name, "error": str(e)[:200]})
                print(f"  API error at {task.id} / {mutant.id if mutant else 'clean'} / {name}: {str(e)[:80]}", flush=True)
                continue
            for b in bs:
                b["in_region"] = bool(sel and b.get("k") is not None and s.page.evaluate(IN_REGION_JS, [b["k"], sel]))
                found.append(b)
    finally:
        s.close()
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", choices=("load", "all"), default="all")
    ap.add_argument("--only", default="", help="comma-separated mutant ids (default: all)")
    ap.add_argument("--catalog", choices=tuple(CATALOGS), default="dev")
    a = ap.parse_args()
    all_states = a.states == "all"
    base, httpd = serve()
    pool = BrowserPool()
    llm = LLM(role="baseline")
    tasks, muts = load_tasks(), load_mutants(CATALOGS[a.catalog])
    if a.only:
        muts = {k: v for k, v in muts.items() if k in a.only.split(",")}
    out_path = RUNS / f"llm_baseline_{a.catalog}_{a.states}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    clean, rows = {}, []

    def save():
        out_path.write_text(json.dumps({"states": a.states, "model": llm.model, "clean": clean, "mutants": rows,
                                        "usage": USAGE.summary(), "api_errors": ERRORS}, indent=1, ensure_ascii=False), encoding="utf-8")

    try:
        for tid in sorted({m.task for m in muts.values()}):
            clean[tid] = run_config(llm, pool, base, tasks[tid], None, all_states)
            print(f"clean {tid:22s} findings: {len(clean[tid])}", flush=True)
            save()
        for m in muts.values():
            fs = run_config(llm, pool, base, tasks[m.task], m, all_states)
            region = sorted({p for b in fs if b["in_region"] for p in b["profiles"]})
            benign = m.check == "none"
            tp = [] if benign else sorted(set(region) & set(m.affects))
            fp = region if benign else sorted(set(region) - set(m.affects) - set(m.may_affect))
            clean_profiles = {p for b in clean[m.task] for p in b["profiles"]}
            lenient = sorted({p for b in fs for p in b["profiles"]} - clean_profiles)
            rows.append({"mutant": m.id, "affects": m.affects, "region_flagged": region, "tp": tp, "fp": fp,
                         "missed": [] if benign else sorted(set(m.affects) - set(region)),
                         "lenient_flagged": lenient, "findings": fs})
            print(f"{m.id:24s} affects={','.join(m.affects) or '-':10s} in-region={','.join(region) or '-':14s} "
                  f"TP={','.join(tp) or '-':8s} FP={','.join(fp) or '-':8s} lenient={','.join(lenient) or '-'}", flush=True)
            save()
    except QuotaExhausted as e:
        print("STOPPED:", e)
    finally:
        pool.close()
        httpd.shutdown()
        save()
    real = [r for r in rows if r["affects"]]
    pairs = sum(len(r["affects"]) for r in real)
    print(f"\nstrict recall: {sum(len(r['tp']) for r in real)}/{pairs}   lenient recall: "
          f"{sum(len(set(r['lenient_flagged']) & set(r['affects'])) for r in real)}/{pairs}   "
          f"FP profiles on mutants: {sum(len(r['fp']) for r in rows)}   "
          f"findings on clean app: {sum(len(v) for v in clean.values())}   states lost to API errors: {len(ERRORS)}"
          f"\nusage: {USAGE.summary()}\nlog: {out_path}")


if __name__ == "__main__":
    main()
