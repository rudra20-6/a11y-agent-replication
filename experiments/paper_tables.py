"""Recompute the paper's numbers from the saved runs in runs/gemma and runs/mistral. No model is called.

  RQ1  detected / testable pairs per run and barrier type, single-LLM and axe baselines, exact McNemar test
  RQ2  clean-application attempts with a false positive (kept reports), and live-site repeatability
  RQ3  live-site findings, tier A, findings made in both runs, findings by type and by site category

Usage: python experiments/paper_tables.py            (prints Markdown; also writes results/paper_tables.md)
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))
from ma11y_relabel import LABELS  # noqa: E402  affected agents per barrier (W3C documentation + reach test)
from v3_live_summary import kept as live_kept, same  # noqa: E402

P = ("P1", "P2", "P3")
MODELS = {
    "Gemma 4 26B A4B": {
        "dir": ROOT / "runs" / "gemma",
        "bench": ["20261106-040620", "20261106-044622", "20261106-052859"],
        "clean": ["20261106-061351", "20261106-062129", "20261106-062938"],
        "llm": "llm_baseline_ma11y_path_all-20261103-235234.json",
        "live": ("v31s1", "v31s2"),
    },
    "Mistral Small 3.2 24B": {
        "dir": ROOT / "runs" / "mistral",
        "bench": ["20261111-025450", "20261111-050022", "20261111-122825"],
        "clean": ["20261111-043607", "20261111-063223", "20261111-112309"],
        "llm": "llm_baseline_ma11y_path_all-20261111-124910.json",
        "live": ("v31m1", "v31m2"),
        # run 3 (122825) resumed 070820 and redid only the units that had failed; its rows hold every unit, but its
        # usage counts only the redone ones, so the calls of 070820 belong to run 3 as well
        "extra_calls": ["full_bench_ma11y_path-20261111-070820.json"],
    },
}
TYPE = {"F22": "Unrequested new window or reload", "F36": "Unrequested new window or reload",
        "F37": "Unrequested new window or reload", "F42": "Control not usable by keyboard",
        "F55": "Control not usable by keyboard", "F44": "Tab order changed", "F78": "Focus indicator removed"}
TYPES = list(dict.fromkeys(TYPE.values()))
SITE_GROUP = {"govuk_holiday": "accessibility-focused (GOV.UK, NHS, Wikipedia)", "nhs_bmi": "accessibility-focused (GOV.UK, NHS, Wikipedia)",
              "wikipedia": "accessibility-focused (GOV.UK, NHS, Wikipedia)", "indiapost": "Indian government",
              "uidai": "Indian government", "passportseva": "Indian government", "dmrc": "Indian government"}


def ty(pair):
    return TYPE[pair[0].split("_")[1]]


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0
    c = (k / n + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k / n:.0%}; 95% CI {lo:.0%}-{hi:.0%})" if n else "0/0"


def mcnemar(a, b, pairs):
    """Exact two-sided McNemar test on the discordant pairs."""
    x = sum(1 for p in pairs if p in a and p not in b)
    y = sum(1 for p in pairs if p in b and p not in a)
    n = x + y
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(x, y) + 1)) / 2 ** n) if n else 1.0


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def kind(p):
    import re
    t = p.lower()
    if re.search(r"(can.?t|cannot|not|no) (see|visible).*focus|focus (indicator )?(is )?(not visible|invisible|disappear)|where (the )?(keyboard )?focus is|focus indicator", t):
        return "invisible keyboard focus"
    if re.search(r"focus (was )?(lost|jumped|moved|went)|no control has focus|focus .*page itself|focus .*top of the page|lost focus", t):
        return "focus lost or moved"
    if re.search(r"cover|overlay|obscur", t):
        return "covers a control (400%)"
    if re.search(r"new (browser )?tab|reload", t):
        return "new tab or reload"
    if re.search(r"announc|alert|error message", t):
        return "announcement or error"
    if re.search(r"label|name|no (visible )?text|unlabel", t):
        return "name or label"
    return "other"


def rq1(m, L, show_axe=True):
    runs = []
    for st in m["bench"]:
        d = load(m["dir"] / f"full_bench_ma11y_path-{st}.json")
        pairs, hit, rep = set(), set(), set()
        for r in d["rows"]:
            if r.get("invalid"):                       # the reference agent did not complete the task: untestable
                continue
            local = {x[0] for x in r.get("reports_local", [])}
            for p in LABELS[r["mutant"]][0]:
                pairs.add((r["mutant"], p))
                if p in r.get("flagged_v3", []):       # a stall, or a kept report at the barrier
                    hit.add((r["mutant"], p))
                    if p in local:
                        rep.add((r["mutant"], p))
        runs.append(dict(pairs=pairs, hit=hit, rep=rep, calls=(d.get("usage") or {})))
    pairs1 = sorted(runs[0]["pairs"])
    llm_rows = {r["mutant"]: r for r in load(m["dir"] / m["llm"])["mutants"]} if m.get("llm") else {}
    llm = {(u, p) for u, p in pairs1 if u in llm_rows and p in (llm_rows[u].get("lenient_flagged") or [])}
    axe_rows = {r["unit"]: r for r in load(ROOT / "data" / "axe_ma11y_bench_path.json")["rows"]}
    axe = {(u, p) for u, p in pairs1 if axe_rows[u]["axe_kill"]}
    L += ["| Barrier type | " + " | ".join(f"Run {i}" for i in range(1, len(runs) + 1)) + " | Single LLM | axe |",
          "|---" * (len(runs) + 3) + "|"]
    for t in TYPES + ["All"]:
        f = (lambda q: True) if t == "All" else (lambda q, t=t: ty(q) == t)
        cells = [f"{sum(map(f, s['hit']))}/{sum(map(f, s['pairs']))}" for s in runs]
        n1 = sum(map(f, pairs1))
        axe_cell = f"{sum(map(f, axe))}/{n1}" if show_axe else "--"
        L.append(f"| {t} | " + " | ".join(cells) + f" | {sum(map(f, llm))}/{n1} | {axe_cell} |")
    if not show_axe:
        L += ["", "-- : axe uses no model; its result is the same for both (shown for the first model)."]
    L += ["", "- detections by reports (rest by stalls): " + ", ".join(str(len(s["rep"])) for s in runs),
          "- exact McNemar, method vs single LLM, per run: p = "
          + ", ".join(f"{mcnemar(s['hit'], {q for q in llm if q in s['pairs']}, sorted(s['pairs'])):.4f}" for s in runs),
          "- missed pairs per run: " + "; ".join(str(sorted(s["pairs"] - s["hit"])) for s in runs), ""]


# Attempts whose only kept report describes the clean application's one real barrier (the passenger form comes back
# empty after "Change passenger details", SC 3.3.7). Manual review: data/clean_causes_mistral.md. Not false positives.
TRUE_REPORTS = {("20261111-043607", "T3_passenger_details", "P1"), ("20261111-063223", "T2_flight_cheapest", "P3"),
                ("20261111-112309", "T2_flight_cheapest", "P3")}


def rq2_clean(m, L):
    n = n_all = false_att = false_rep = true_rep = 0
    for st in m["clean"]:
        d = load(m["dir"] / f"full_bench_dev-{st}.json")
        for task, v in d["clean"].items():
            ran = [p for p in P if p in (v.get("traces") or {})] or list(P)   # agents that ran (all three in the paper)
            n_all += len(ran)
            if v.get("invalid"):                       # reference agent did not complete the task: not tested
                continue
            for p in ran:
                n += 1
                mine = [x for x in v.get("agent_reports", []) if x.get("kept") and x["profile"] == p]
                if (st, task, p) in TRUE_REPORTS:
                    true_rep += len(mine)
                    continue
                false_att += bool(mine)
                false_rep += len(mine)
    L += [f"- tested attempts with a false positive (kept report): {pct(false_att, n)}; false findings: {false_rep}; "
          f"reports of the real passenger-form barrier: {true_rep}",
          f"- the same count over all {n_all} attempts, untested tasks included: {false_att}/{n_all}",
          "- rule checks on the clean application: "
          + ", ".join(str(sum(len(v.get("findings", [])) for v in load(m["dir"] / f"full_bench_dev-{st}.json")["clean"].values()))
                      for st in m["clean"]) + " violations per run",
          "- cause of every report (manual review): data/clean_causes_*.md", ""]


def calls(m, L):
    def nav_calls(u):
        return sum(v.get("calls", 0) for v in (u or {}).values() if isinstance(v, dict) and "calls" in v)
    bench = sum(nav_calls(load(m["dir"] / f"full_bench_{c}-{st}.json").get("usage"))
                for c, sts in (("ma11y_path", m["bench"]), ("dev", m["clean"])) for st in sts) \
        + sum(nav_calls(load(m["dir"] / f).get("usage")) for f in m.get("extra_calls", []))
    # live: one llm_start event per model call in each site's event log (the usage block in a live results.json is a
    # running total of its batch process, so it is not summed)
    live_n = sum(sum(1 for line in (d / "events.jsonl").open(encoding="utf-8") if '"kind": "llm_start"' in line)
                 for t in m["live"] for d in m["dir"].glob(f"real-*-{t}-*") if (d / "events.jsonl").exists())
    llm_u = load(m["dir"] / m["llm"]).get("usage") or {}
    llm_n = nav_calls(llm_u) or sum(v for v in (llm_u.get("endpoints") or {}).values())
    L += [f"- model calls: instrumented + clean {bench:,}, live {live_n:,} (together {bench + live_n:,}); "
          f"single-LLM baseline {llm_n:,}", ""]


def live(m, L):
    def runs(tag):
        out = {}
        for d in sorted(m["dir"].glob(f"real-*-{tag}-*")):
            f = d / "results.json"
            if f.exists():
                out[d.name.split(f"-{tag}-", 1)[1]] = load(f)["results"]
        return out
    A, B = (runs(t) for t in m["live"])
    tested = lambda S: sum(1 for res in S.values() for r in res if not r.get("invalid"))
    pairs = []
    for site in A:
        ra, rb = {r["task"]["id"]: r for r in A[site]}, {r["task"]["id"]: r for r in B.get(site, [])}
        for t, r in ra.items():
            if r.get("invalid") or t not in rb or rb[t].get("invalid"):
                continue
            for p in P:
                x, y = r.get("profiles", {}).get(p), rb[t].get("profiles", {}).get(p)
                if isinstance(x, dict) and isinstance(y, dict) and not x.get("tool_error") and not y.get("tool_error"):
                    pairs.append((x["status"] == "done", y["status"] == "done"))
    n = len(pairs)
    po = sum(x == y for x, y in pairs) / n if n else 0
    pa, pb = (sum(x for x, _ in pairs) / n, sum(y for _, y in pairs) / n) if n else (0, 0)
    pe = pa * pb + (1 - pa) * (1 - pb)
    kap = (po - pe) / (1 - pe) if pe < 1 else 1.0
    ka = [x for s in A for x in live_kept(A[s])]
    kb = [x for s in B for x in live_kept(B[s])]
    both = []
    for site in A:
        xb, used = live_kept(B.get(site, [])), set()
        for t, x in live_kept(A[site]):
            j = next((j for j, (t2, y) in enumerate(xb) if j not in used and t2 == t and same(x, y)), None)
            if j is not None:
                used.add(j)
                both.append((site, t, x["profile"], kind(x["problem"])))
    tier = lambda K: sum(1 for _, x in K if x.get("tier") == "A")
    focus = lambda K: sum(1 for _, x in K if x.get("tool"))
    L += [f"- tasks tested (reference agent completed): {tested(A)}/27 and {tested(B)}/27",
          f"- same outcome (completed or not) in both runs: {po:.0%} of {n} attempts (Cohen's kappa {kap:.2f})",
          f"- findings: {len(ka)} and {len(kb)}; tier A: {tier(ka)} and {tier(kb)} (from the focus check: {focus(ka)} and {focus(kb)})",
          f"- findings made in both runs for the same task and agent: {len(both)}",
          "- by type, both runs: " + "; ".join(f"{k} {v}" for k, v in Counter(kind(x['problem']) for _, x in ka + kb).most_common())]
    by = Counter((p, k) for _, _, p, k in both)
    L.append("- made in both runs, by agent and type: " + "; ".join(f"{p} {k} {v}" for (p, k), v in by.most_common()))
    grp = {}
    for S in (A, B):
        for site, res in S.items():
            g = grp.setdefault(SITE_GROUP.get(site, "Indian commerce, health and finance"), Counter())
            g["tested"] += sum(1 for r in res if not r.get("invalid"))
            K = live_kept(res)
            g["findings"] += len(K)
            g["tierA"] += sum(1 for _, x in K if x.get("tier") == "A")
    for g, c in grp.items():
        L.append(f"- {g}: {c['findings']} findings in {c['tested']} tested tasks "
                 f"({c['findings'] / max(1, c['tested']):.1f} per tested task), tier A {c['tierA']}")
    L.append("")


def discover(folder: Path) -> dict:
    """New runs (from experiments/reproduce.py) in one folder, grouped by the model recorded in each file."""
    import re
    stamp = lambda f: re.search(r"(\d{8}-\d{6})", f.name).group(1)
    out = {}
    for f in sorted(folder.glob("full_bench_*-*.json")):
        d = load(f)
        m = out.setdefault(d.get("model", "?"), {"dir": folder, "bench": [], "clean": [], "llm": None, "live": ()})
        if f.name.startswith("full_bench_ma11y_path-") and d.get("rows"):
            m["bench"].append(stamp(f))
        elif f.name.startswith("full_bench_dev-") and d.get("clean") and not d.get("rows"):
            m["clean"].append(stamp(f))
    for f in sorted(folder.glob("llm_baseline_ma11y_path_all-*.json")):
        out.setdefault(load(f).get("model", "?"), {"dir": folder, "bench": [], "clean": [], "llm": None, "live": ()})["llm"] = f.name
    tags = {}
    for d in sorted(folder.glob("real-*-*")):
        if (d / "meta.json").exists() and (d / "results.json").exists():
            tag = re.match(r"real-\d{8}-(.+)-[a-z0-9_]+$", d.name)
            if tag:
                tags.setdefault(load(d / "meta.json").get("model", "?"), []).append(tag.group(1))
    for model, ts in tags.items():
        uniq = list(dict.fromkeys(ts))
        if len(uniq) >= 2:
            out.setdefault(model, {"dir": folder, "bench": [], "clean": [], "llm": None, "live": ()})["live"] = tuple(uniq[:2])
    return out


def main():
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", default="", help="score new runs in this folder (e.g. runs) instead of the paper's runs")
    a = ap.parse_args()
    models = discover(Path(a.new)) if a.new else MODELS
    L = [f"# Numbers recomputed from {a.new or 'runs/gemma and runs/mistral (the paper runs)'}", ""]
    for i, (name, m) in enumerate(models.items()):
        L += [f"## {name}", ""]
        if m["bench"]:
            L += ["### RQ1: instrumented application (detected/testable pairs)", ""]
            rq1(m, L, show_axe=(i == 0))
        if m["clean"]:
            L += ["### RQ2: clean application", ""]
            rq2_clean(m, L)
        if m["live"]:
            L += ["### RQ2/RQ3: live sites (27 frozen tasks, two runs)", ""]
            live(m, L)
        if m["bench"] and m["clean"] and m["live"] and m.get("llm"):
            L += ["### Cost", ""]
            calls(m, L)
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / ("paper_tables.md" if not a.new else "new_runs_tables.md")).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
