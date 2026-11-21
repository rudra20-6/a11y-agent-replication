"""RQ1/RQ2 on BenchBook: the full method (reference run, rule checks, agents P1-P3, verifier, end-state check and stall
judge), run end to end on the tasks of the clean app and under every barrier of a catalog.

The paper's score (score_v3, saved as flagged_v3/tp_v3/fp_v3): a persona flags a barrier by its own stall or by a kept
problem report that points at the barrier. The paper's numbers are computed from the saved runs by
experiments/paper_tables.py, with the affected-agent labels in experiments/ma11y_relabel.py (LABELS). The other fields
(tp/fp from rule findings, *_ab with agent-only evidence) are earlier scores kept in the output for completeness.
--personas limits both the run and the labels to those personas.

Usage: python experiments/full_bench.py [--catalog ma11y_path|dev] [--clean-only [--clean-tasks ID,ID]] [--only ID,ID]
                                        [--personas P1,P2,P3] [--resume FILE [--redo-errors]]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

from a11y_agent.bench import CATALOGS, install_mutant, install_probe, load_mutants, load_tasks, read_probe
from a11y_agent.benchserver import serve
from a11y_agent.config import RUNS, SETTINGS
from a11y_agent.events import EventLog
from a11y_agent.llm import LLM, USAGE, QuotaExhausted
from a11y_agent.pipeline import run_task

PERSONAS = ("P1", "P2", "P3")


def fkey(f):
    return (f["profile"], f["check"], (f["message"] or "").split(":")[0], f["target"])


def traces(rec):
    """Each agent's steps, kept for analysing stalls and false "done"s (what it saw, did and got back)."""
    return {p: {"status": v.get("status"), "reason": v.get("reason"), "answer": v.get("answer"), "effort": v.get("effort"),
                "steps": [{"i": x["i"], "action": x["action"], "thought": (x.get("thought") or "")[:200], "result": (x["result"] or "")[:300], "url": x.get("url"),
                           "obs": (x.get("observation") or "")[:800], "problem": x.get("problem"), "probe": x.get("probe")}
                          for x in v.get("steps", [])]}
            for p, v in rec.get("profiles", {}).items()}


def run(base, task, mutant, llm, tag, personas=PERSONAS, ev=None, unit_dir=None):
    t = {"id": tag, "goal": task.goal, "start_url": base + task.start}
    t0 = time.time()
    def prepare(s, m=mutant):
        install_probe(s)   # on clean runs too, so both are instrumented the same way
        install_mutant(s, m)
    extra = {"ev": ev} if ev is not None else {}
    rec = run_task(t, personas, llm, prepare=prepare, agents=True, probe=read_probe, **extra)
    rec["secs"] = round(time.time() - t0)
    if unit_dir:   # A11Y_BENCH_LOG=1: the full record of the unit, untruncated
        unit_dir.mkdir(parents=True, exist_ok=True)
        (unit_dir / f"{tag}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return rec


def _letters(t: str) -> str:
    return re.sub(r"[^a-z]", "", (t or "").lower())


def mutated_texts(m) -> list[str]:
    """The visible text of the mutated element(s), letters only (to match a report that quotes it, e.g. F32)."""
    out = []
    for t in (m.params.get("targets") or []):
        txt = _letters(re.sub(r"<[^>]+>", " ", t.get("html", "")))
        if len(txt) >= 3:
            out.append(txt)
    return out


def stalled(rec, personas) -> list[str]:
    return sorted(p for p, v in rec.get("profiles", {}).items()
                  if p in personas and v.get("status") != "done" and not v.get("tool_error"))


def local_reports(m, rec, personas) -> list[dict]:
    """Kept problem reports that point at the barrier: the action at the reported step or the one before it
    involved the mutated element (benchmark probe), or the report quotes the mutated element's text."""
    texts = mutated_texts(m) if m else []
    hits = []
    for r in rec.get("agent_reports", []):
        if not r.get("kept") or r["profile"] not in personas:
            continue
        steps = {x["i"]: x for x in rec["profiles"].get(r["profile"], {}).get("steps", [])}
        touched = any(((steps.get(i) or {}).get("probe") or {}).get("touched") for i in (r["step"] - 1, r["step"]))
        quoted = any(t in _letters(r["problem"]) for t in texts)
        if touched or quoted:
            hits.append({**r, "touched": touched, "quoted": quoted})
    return hits


def score_v3(m, rec, personas, benign, affects) -> dict:
    """The paper's score, agent-originated only: a persona is flagged by its own stall (task level) or by a
    kept problem report that points at the barrier. Rules play no part; rule confirmation is reported separately."""
    loc = local_reports(m, rec, personas)
    flagged = sorted(set(stalled(rec, personas)) | {r["profile"] for r in loc})
    tp = [] if benign else sorted(set(flagged) & set(affects))
    fp = flagged if benign else sorted(set(flagged) - set(affects) - set(m.may_affect))
    return {"tp_v3": tp, "fp_v3": fp, "flagged_v3": flagged,
            "tp_v3_reports": [] if benign else sorted({r["profile"] for r in loc} & set(affects)),
            "reports_kept": [(r["profile"], r["step"], r["tier"], r["problem"][:120]) for r in rec.get("agent_reports", []) if r.get("kept")],
            "reports_local": [(r["profile"], r["step"], r["tier"], "touched" if r["touched"] else "quoted") for r in loc]}


def score(m, rec, clean, personas=PERSONAS):
    if rec.get("invalid"):
        return {"mutant": m.id, "invalid": rec["invalid"]}
    ck = {fkey(f) for f in clean.get("findings", [])}
    new = [f for f in rec["findings"] if fkey(f) not in ck]
    flagged = sorted({f["profile"] for f in new})
    by_layer = {"rules": sorted({f["profile"] for f in new if not (f.get("evidence") or {}).get("source") == "agent"}),
                "agent_stall": sorted({f["profile"] for f in new if (f.get("evidence") or {}).get("source") == "agent"})}
    benign = m.check == "none"
    affects = [p for p in m.affects if p in personas]
    flagged = [p for p in flagged if p in personas]
    tp = [] if benign else sorted(set(flagged) & set(affects))
    fp = flagged if benign else sorted(set(flagged) - set(affects) - set(m.may_affect))
    # with agent-only evidence too (stall without rule evidence, end-state mismatch, made-up answer)
    flagged_b = sorted(set(flagged) | {f["profile"] for f in rec.get("agent_findings", []) if f["profile"] in personas})
    tp_b = [] if benign else sorted(set(flagged_b) & set(affects))
    fp_b = flagged_b if benign else sorted(set(flagged_b) - set(affects) - set(m.may_affect))
    v3 = score_v3(m, rec, personas, benign, affects)
    return {"mutant": m.id, "affects": affects, **v3, "tp_ab": tp_b, "fp_ab": fp_b, "flagged_ab": flagged_b,
            "agent_findings": [(f["profile"], f["message"][:120]) for f in rec.get("agent_findings", [])], "flagged": flagged, "tp": tp, "fp": fp, "by_layer": by_layer,
            "missed": [] if benign else sorted(set(affects) - set(flagged)),
            "agents": {p: v["status"] + (" (tool error)" if v.get("tool_error") else "") for p, v in rec["profiles"].items()},
            "unconfirmed": [u["profile"] for u in rec.get("unconfirmed_stalls", [])],
            "tool_errors": len(rec.get("tool_errors", [])), "secs": rec.get("secs")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", choices=tuple(CATALOGS), default="dev")
    ap.add_argument("--only", default="")
    ap.add_argument("--clean-only", action="store_true",
                    help="run only the 7 clean tasks (agent competence and the false-stall base rate), no barriers")
    ap.add_argument("--personas", default=",".join(PERSONAS), help="e.g. P1,P2,P3 for the agent personas only")
    ap.add_argument("--resume", default="", help="a previous full_bench json: units already in it are not run again")
    ap.add_argument("--redo-errors", action="store_true",
                    help="with --resume: run again the units where the model/API failed (an agent or the reference run) "
                         "or a rule-check replay hit a tool error")
    ap.add_argument("--clean-tasks", default="", help="with --clean-only: run only these clean tasks (comma-separated ids)")
    a = ap.parse_args()
    personas = tuple(a.personas.split(","))
    tasks, muts = load_tasks(), load_mutants(CATALOGS[a.catalog])
    if a.clean_tasks:   # run only these clean tasks
        tasks = {k: v for k, v in tasks.items() if k in a.clean_tasks.split(",")}
    if a.only:
        muts = {k: v for k, v in muts.items() if k in a.only.split(",")}
    if a.clean_only:
        muts = {}
    base, httpd = serve()
    llm = LLM(role="nav")
    path = RUNS / f"full_bench_{a.catalog}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    ev, unit_dir = None, None
    if os.environ.get("A11Y_BENCH_LOG") == "1":   # event log, screenshots and full unit records
        run_dir = path.with_suffix("")
        run_dir.mkdir(parents=True, exist_ok=True)
        ev, unit_dir = EventLog(run_dir), run_dir / "units"
    clean, rows, raw = {}, [], {}
    if a.resume:   # finished units from an interrupted run; their findings are all scoring needs
        old = json.loads(Path(a.resume).read_text(encoding="utf-8"))
        clean = {k: {"findings": v["findings"], "invalid": v.get("invalid"), "unconfirmed_stalls": v.get("unconfirmed", []), "agent_findings": v.get("agent_findings", []),
                     "agent_reports": v.get("agent_reports", []),
                     "profiles": {p: {"status": st} for p, st in v.get("agents", {}).items()}, "traces": v.get("traces")}
                 for k, v in old["clean"].items()}
        rows, raw = old["rows"], old.get("raw", {})
        if a.redo_errors:  # API failures and tool errors say nothing about the site: run again, not scored as misses
            api = lambda st, inv: "error" in " ".join(st) or "model/API failed" in (inv or "")
            redo_clean = [k for k, v in clean.items() if api([x["status"] for x in v["profiles"].values()], v.get("invalid"))]
            redo = [r["mutant"] for r in rows if api(list(r.get("agents", {}).values()), r.get("invalid")) or r.get("tool_errors")]
            clean = {k: v for k, v in clean.items() if k not in redo_clean}
            rows = [r for r in rows if r["mutant"] not in redo]
            raw = {k: v for k, v in raw.items() if k not in redo}
            print(f"redo after API errors: clean {redo_clean}, barriers {redo}", flush=True)
        print(f"resumed from {a.resume}: {len(clean)} clean units, {len(rows)} barrier units", flush=True)

    def save():
        path.write_text(json.dumps({"model": SETTINGS.nav_model, "clean": {k: {"findings": v.get("findings", []), "invalid": v.get("invalid"),
                                    "unconfirmed": v.get("unconfirmed_stalls", []), "agent_findings": v.get("agent_findings", []), "agent_reports": v.get("agent_reports", []),
                                    "agents": {p: x["status"] for p, x in v.get("profiles", {}).items()},
                                    "traces": v.get("traces") or traces(v)}
                                    for k, v in clean.items()}, "rows": rows, "raw": raw, "usage": USAGE.summary()},
                                   indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    try:
        for tid in (sorted(tasks) if a.clean_only else sorted({m.task for m in muts.values()})):
            if tid in clean:
                continue
            clean[tid] = run(base, tasks[tid], None, llm, f"clean_{tid}", personas, ev, unit_dir)
            c = clean[tid]
            kept = [(r["profile"], r["problem"][:60]) for r in c.get("agent_reports", []) if r.get("kept")]
            print(f"clean {tid:22s} findings {len(c.get('findings', []))} | unconfirmed {len(c.get('unconfirmed_stalls', []))} | "
                  f"reports kept {len(kept)} {kept} | "
                  f"agents {[(p, v['status']) for p, v in c.get('profiles', {}).items()]} | {c.get('invalid') or ''} {c['secs']}s", flush=True)
            save()
        done = {r['mutant'] for r in rows}
        for m in muts.values():
            if m.id in done:
                continue
            rec = run(base, tasks[m.task], m, llm, m.id, personas, ev, unit_dir)
            raw[m.id] = {"findings": rec.get("findings", []), "unconfirmed": rec.get("unconfirmed_stalls", []),
                         "tool_errors": rec.get("tool_errors", []), "agent_findings": rec.get("agent_findings", []), "agent_reports": rec.get("agent_reports", []),
                         "invalid": rec.get("invalid"), "traces": traces(rec)}
            r = score(m, rec, clean[m.task], personas)
            rows.append(r)
            print(f"{m.id:24s} affects={','.join(m.affects) or '-':10s} flagged={','.join(r.get('flagged', [])) or '-':14s} "
                  f"TP={','.join(r.get('tp', [])) or '-':10s} FP={','.join(r.get('fp', [])) or '-':8s} "
                  f"rules={','.join(r.get('by_layer', {}).get('rules', [])) or '-'} stall={','.join(r.get('by_layer', {}).get('agent_stall', [])) or '-'} "
                  f"A+B={','.join(r.get('tp_ab', [])) or '-'} FP_AB={','.join(r.get('fp_ab', [])) or '-'} "
                  f"V3={','.join(r.get('tp_v3', [])) or '-'} FP_V3={','.join(r.get('fp_v3', [])) or '-'} "
                  f"local={r.get('reports_local') or '-'} "
                  f"{r.get('invalid') or ''} {r.get('secs')}s", flush=True)
            save()
    except QuotaExhausted as e:
        print("STOPPED:", e)
    finally:
        httpd.shutdown()
        save()
    real = [r for r in rows if r.get("affects")]
    pairs = sum(len(r["affects"]) for r in real)
    print(f"\nrecall {sum(len(r['tp']) for r in real)}/{pairs} persona-barrier pairs | FP personas on barriers "
          f"{sum(len(r.get('fp', [])) for r in rows)} | findings on clean app {sum(len(c.get('findings', [])) for c in clean.values())} | "
          f"invalid runs {sum(1 for r in rows if r.get('invalid'))}\n"
          f"tier A+B: recall {sum(len(r.get('tp_ab', [])) for r in real)}/{pairs} | FP personas on barriers "
          f"{sum(len(r.get('fp_ab', [])) for r in rows)} | agent findings on clean app "
          f"{sum(len(c.get('agent_findings', [])) for c in clean.values())}\n"
          f"paper score (a stall, or a kept report at the barrier): recall {sum(len(r.get('tp_v3', [])) for r in real)}/{pairs} "
          f"(by reports {sum(len(r.get('tp_v3_reports', [])) for r in real)}) | FP personas on barriers "
          f"{sum(len(r.get('fp_v3', [])) for r in rows)} | kept reports on clean app "
          f"{sum(1 for c in clean.values() for x in c.get('agent_reports', []) if x.get('kept'))}\n"
          f"usage: {USAGE.summary()}\nlog: {path}")


if __name__ == "__main__":
    main()
