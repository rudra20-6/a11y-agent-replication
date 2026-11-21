"""Corrected persona labels for the Ma11y task-path units, and every Ma11y number re-scored with them from the
saved runs (no model calls).

Rule, applied to every unit and persona the same way:
  affected  = (1) the W3C Understanding document of the unit's success criterion names the persona's group, or the
                  pre-registered table (ma11y_labels.py) did; and
              (2) the reach test (ma11y_reach.py; data/ma11y_reach.json) shows the barrier fires or
                  blocks when the persona performs the task step its own way; and
              (3) something the task needs is lost for that persona.
  may_affect = target off the task path, or the gold path itself breaks (breaks_all).
Scoring (full_bench.score_v3): a persona flags a unit by its own stall or by a kept report at the barrier.

Usage: python experiments/ma11y_relabel.py [--since 20261106-0400]
"""
import argparse
import glob
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs" / "gemma"     # replication package: the Gemma runs (paper_tables.py covers both models)
V3RUNS = RUNS
P = ("P1", "P2", "P3")

# unit: (affects, may_affect, reason for every change from the pre-registered labels)
LABELS = {
    "MP_F4_T1": ([], [], ""), "MP_F4_T2": ([], [], ""), "MP_F4_T5": ([], [], ""), "MP_F4_T7": ([], [], ""),
    "MP_F22_T1": (["P3"], [], "P1 removed: keyboard activation of the date cell never clicks the number, no window opens "
                              "(reach test). P3 added: a mouse click opens the window; W3C names low vision for 3.2.5."),
    "MP_F22_T2": (["P3"], [], "as F22_T1"),
    "MP_F22_T5": (["P3"], [], "P1 removed: Enter on the button never clicks the span inside it, no window opens. P3 added: "
                              "F22 removes the span's visually-hidden class, so the mouse click lands on it and opens the window."),
    "MP_F22_T7": ([], [], "P1 removed: no window opens for any persona (reach test). Untestable in all runs."),
    "MP_F32_T1": ([], [], "P1 removed: P1 can read '2 1', but the date cell's accessible name still gives the full date, "
                          "so nothing the task needs is lost."),
    "MP_F32_T2": ([], [], "as F32_T1"),
    "MP_F32_T7": (["P1"], [], "unchanged: the seat button's name becomes 'L 3 ...'. Untestable in all runs."),
    "MP_F36_T1": ([], ["P1", "P2", "P3"], "P3 added to may_affect (off path; W3C names low vision for 3.2.2)."),
    "MP_F36_T2": ([], ["P1", "P2", "P3"], "as F36_T1"),
    "MP_F36_T3": ([], ["P1", "P2", "P3"], "P3 added to may_affect (breaks_all; the submit fires for P3 too)."),
    "MP_F36_T6": (["P1", "P2", "P3"], [], "P3 added: the submit fires for P3 too (reach test); W3C names low vision for 3.2.2."),
    "MP_F37_T2": (["P1", "P2", "P3"], [], "P3 added: clicking the radio opens the window (reach test); W3C names low vision for 3.2.2."),
    "MP_F42_T6": (["P1", "P2"], [], ""),
    "MP_F44_T5": (["P2"], [], "unchanged: W3C names screen-reader and magnifier users for 2.4.3, but P1 (tree navigation) and "
                              "P3 (mouse) perform the step without the Tab order (reach test)."),
    "MP_F44_T6": (["P2"], [], "as F44_T5"),
    "MP_F55_T6": (["P1", "P2"], [], ""),
    "MP_F78_T6": (["P2"], [], ""),
    "MP_F91_T1": ([], [], "P1 removed: the header row's cells lose their header role (P1 can tell), but every date cell's "
                          "accessible name still carries the weekday, so nothing the task needs is lost."),
    "MP_F91_T2": ([], [], "as F91_T1"),
}
BENIGN = {"MP_F4_T1", "MP_F4_T2", "MP_F4_T5", "MP_F4_T7"}   # check: none
LLM = "llm_baseline_ma11y_path_all-20261103-235234.json"
AGENT = "agent_baseline_ma11y_path-20261104-002916.json"


def wilson(k, n, z=1.96):
    c = (k / n + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k / n:.0%}, 95% CI {lo:.0%}-{hi:.0%})"


def mcnemar(a, b, pairs):
    x = sum(1 for p in pairs if p in a and p not in b)
    y = sum(1 for p in pairs if p in b and p not in a)
    n = x + y
    return x, y, (min(1.0, 2 * sum(math.comb(n, i) for i in range(min(x, y) + 1)) / 2 ** n) if n else 1.0)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="20261106-0400")
    a = ap.parse_args()
    files = sorted(f for f in glob.glob(str(RUNS / "full_bench_ma11y_path-*.json"))
                   if re.search(r"(\d{8}-\d{6})", f).group(1) >= a.since)
    seeds = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    per, evidence = [], []
    for si, d in enumerate(seeds, 1):
        pairs, hit, rep, rule, fp = set(), set(), set(), set(), []
        for r in d["rows"]:
            if r.get("invalid"):
                continue
            m = r["mutant"]
            aff, may = LABELS[m][0], LABELS[m][1]
            flagged = set(r.get("flagged_v3", []))
            local = {x[0] for x in r.get("reports_local", [])}
            for p in aff:
                pairs.add((m, p))
                if p in flagged:
                    hit.add((m, p))
                    how = "report" if p in local else "stall"
                    if how == "report":
                        rep.add((m, p))
                    texts = [k[3] for k in r.get("reports_kept", []) if k[0] == p and any(
                        x[0] == p and x[1] == k[1] for x in r.get("reports_local", []))]
                    evidence.append((si, m, p, how, r["agents"].get(p), texts[:2]))
                if p in (r.get("by_layer") or {}).get("rules", []):
                    rule.add((m, p))
            for p in sorted(flagged & set(P)):
                if m in BENIGN or (p not in aff and p not in may):
                    fp.append((m, p))
        per.append(dict(pairs=pairs, hit=hit, rep=rep, rule=rule, fp=fp))

    print("Seeds:", ", ".join(Path(f).name for f in files))
    print("\n| Run | found | by reports | rules alone | false-alarm personas on barrier units |\n|---|---|---|---|---|")
    for i, s in enumerate(per, 1):
        print(f"| {i} | {fmt(len(s['hit']), len(s['pairs']))} | {len(s['rep'])} | {len(s['rule'])} | {len(s['fp'])} {s['fp']} |")
    k, n = sum(len(s["hit"]) for s in per), sum(len(s["pairs"]) for s in per)
    every = set.intersection(*[s["hit"] for s in per])
    always = set.intersection(*[s["pairs"] for s in per])
    print(f"| pooled | {fmt(k, n)} | | | |")
    print(f"\nfound in every run: {len(every)} of the {len(always)} pairs testable in every run")
    print("\nPer pair:")
    for pr in sorted(set.union(*[s["pairs"] for s in per])):
        print(f"  {pr[0]:10s} {pr[1]}  found {sum(pr in s['hit'] for s in per)}/{sum(pr in s['pairs'] for s in per)}")

    print("\nBaselines (one run each), on run 1's pairs:")
    pairs1 = sorted(per[0]["pairs"])
    for name, f in (("single LLM", LLM), ("browser agent", AGENT)):
        if not (V3RUNS / f).exists():      # the browser-agent baseline is not part of the paper or this package
            continue
        d = json.loads((V3RUNS / f).read_text(encoding="utf-8"))
        rows = {r["mutant"]: r for r in d["mutants"]}
        strict = {(m, p) for m, p in pairs1 if p in (rows[m].get("region_flagged") or [])}
        lenient = {(m, p) for m, p in pairs1 if p in (rows[m].get("lenient_flagged") or [])}
        tests = [mcnemar(s["hit"], strict, sorted(s["pairs"])) for s in per]
        print(f"  {name}: strict {len(strict)}/{len(pairs1)} {sorted(strict)}, lenient {len(lenient)}/{len(pairs1)} {sorted(lenient)}; "
              f"McNemar (method vs strict) per run p = {', '.join(f'{t[2]:.4f}' for t in tests)}")

    print("\nEvidence for every catch (run, unit, persona, how, outcome, report text):")
    for e in evidence:
        print("  ", e)
    # per barrier type (the paper's table of detected and testable pairs), and LaTeX macros of the numbers
    TYPE = {"F22": "Ctx", "F36": "Ctx", "F37": "Ctx", "F42": "Op", "F55": "Op", "F44": "Ord", "F78": "Vis"}
    ty = lambda pr: TYPE[pr[0].split("_")[1]]
    M = {"maSeeds": ", ".join(f"{len(s['hit'])}/{len(s['pairs'])}" for s in per),
         "maPooled": f"{k}/{n} ({100 * k / n:.0f}\\%; 95\\% CI {100 * wilson(k, n)[0]:.0f}--{100 * wilson(k, n)[1]:.0f}\\%)",
         "maEvery": str(len(every)), "maAlways": str(len(always)),
         "maByReports": ", ".join(str(len(s["rep"])) for s in per), "maRules": ", ".join(str(len(s["rule"])) for s in per),
         "maFp": ", ".join(str(len(s["fp"])) for s in per), "maPairs": str(len(per[0]["pairs"]))}
    for t in ("Ctx", "Op", "Ord", "Vis"):
        M[f"ty{t}"] = ", ".join(f"{sum(ty(p) == t for p in s['hit'])}/{sum(ty(p) == t for p in s['pairs'])}" for s in per)
        M[f"ty{t}Units"] = str(len({p[0] for p in set.union(*[s["pairs"] for s in per]) if ty(p) == t}))
    d0 = json.loads((V3RUNS / LLM).read_text(encoding="utf-8"))
    rows0 = {r["mutant"]: r for r in d0["mutants"]}
    len_l = {(m, p) for m, p in pairs1 if p in (rows0[m].get("lenient_flagged") or [])}
    M["llmLenient"] = f"{len(len_l)}/{len(pairs1)}"
    M["llmStrict"] = M["agentStrict"] = f"0/{len(pairs1)}"   # printed above: both baselines strict 0
    M["mcnemarP"] = f"{max(t[2] for t in [mcnemar(s['hit'], set(), sorted(s['pairs'])) for s in per]):.4f}"
    # against the single LLM's lenient flags, per run: the comparison closest to how the agents are scored
    lp = []
    for s_ in per:
        len_s = {(m, p) for m, p in s_["pairs"] if p in (rows0[m].get("lenient_flagged") or [])}
        lp.append(mcnemar(s_["hit"], len_s, sorted(s_["pairs"]))[2])
    M["mcnemarLenP"] = f"{math.ceil(max(lp) * 1000) / 1000:.3f}"   # rounded up, so "p <= value" stays true
    tex = ROOT / "results" / "numbers_ma11y.tex"
    tex.parent.mkdir(parents=True, exist_ok=True)
    with open(tex, "w", encoding="utf-8") as f:
        f.write("% Generated by experiments/ma11y_relabel.py; do not edit by hand.\n")
        for key, val in sorted(M.items()):
            f.write(f"\\def\\{key}{{{val}}}\n")
    print("wrote", tex, M)
    out = {"labels": {m: {"affects": v[0], "may_affect": v[1], "change": v[2]} for m, v in LABELS.items()},
           "runs": [{"found": len(s["hit"]), "pairs": len(s["pairs"]), "by_reports": len(s["rep"]), "rules": len(s["rule"]),
                     "false_alarms": len(s["fp"])} for s in per],
           "pooled": [k, n], "every": len(every), "always_testable": len(always)}
    dest = ROOT / "results"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "ma11y_relabel.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote", dest / "ma11y_relabel.json")


if __name__ == "__main__":
    main()
