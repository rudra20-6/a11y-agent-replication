"""Method v3 (D97) on the frozen live tasks: what the persona agents reported, per site, and which reports recur.

For each seed tag (default v3s1, v3s2) it reads runs/real-*-<tag>-<site>/results.json and counts, per site:
  - kept reports (the verifier's "site" verdict), rule-confirmed (tier A) vs agent only (tier B);
  - stalls (the persona could not finish);
  - AGREED reports (D101): kept in both seeds for the same task and persona, with the same WCAG SC (first criterion) and
    the same control acted on at the reported step, or similar wording (word overlap >= 0.3).
Reports that may be harness artefacts (D101: a name the harness cut at 50 characters read as the site's truncation)
are flagged for manual review, not removed.

Writes results/<date>/v3_live_summary.md.   Usage: python experiments/v3_live_summary.py [--a v3s1 --b v3s2]
"""
import argparse
import re
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
ARTEFACT = re.compile(r"truncat|cut off|cuts off|cut-off|mid-word", re.I)


def load(tag):
    out = {}
    for d in sorted(RUNS.glob(f"real-*-{tag}-*")):
        f = d / "results.json"
        if f.exists():
            site = d.name.split(f"-{tag}-", 1)[1]
            out[site] = json.loads(f.read_text(encoding="utf-8"))["results"]
    return out


def words(t):
    return {w for w in re.findall(r"[a-z]{3,}", (t or "").lower())}


def sc1(sc):
    m = re.search(r"\d\.\d+\.\d+", sc or "")
    return m.group(0) if m else ""


def kept(res):
    """[(task_id, report with its target)] for the kept reports of one site run."""
    out = []
    for r in res:
        for x in r.get("agent_reports", []):
            if x.get("kept"):
                steps = {s["i"]: s for s in r.get("profiles", {}).get(x["profile"], {}).get("steps", [])}
                tgt = (steps.get(x["step"]) or {}).get("target") or (steps.get(x["step"] - 1) or {}).get("target") or ""
                out.append((r["task"]["id"], {**x, "target": tgt}))
    return out


def same(a, b):
    if a["profile"] != b["profile"] or sc1(a.get("sc")) != sc1(b.get("sc")):
        return False
    if a["target"] and a["target"] == b["target"]:
        return True
    wa, wb = words(a["problem"]), words(b["problem"])
    return bool(wa | wb) and len(wa & wb) / len(wa | wb) >= 0.3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="v3s1")
    ap.add_argument("--b", default="v3s2")
    a = ap.parse_args()
    A, B = load(a.a), load(a.b)
    sites = sorted(set(A) | set(B))
    L = [f"# Method v3 on the frozen live tasks: agent reports ({a.a} vs {a.b})", "",
         "| Site | kept reports A | B | rule-confirmed A/B | stalls A/B | agreed in both | possible artefacts |", "|---|---|---|---|---|---|---|"]
    agreed_all, flagged = [], []
    tot = {"ka": 0, "kb": 0, "ag": 0}
    for s in sites:
        ka, kb = kept(A.get(s, [])), kept(B.get(s, []))
        stall = lambda res: sum(1 for r in res for p in r.get("profiles", {}).values() if p.get("status") != "done" and not p.get("tool_error"))
        ag = []
        used = set()
        for t, x in ka:
            for j, (u, y) in enumerate(kb):
                if j not in used and t == u and same(x, y):
                    ag.append((t, x, y))
                    used.add(j)
                    break
        art = [(t, x) for t, x in ka + kb if ARTEFACT.search(x["problem"])]
        flagged += [(s, t, x) for t, x in art]
        agreed_all += [(s, t, x, y) for t, x, y in ag]
        tot["ka"] += len(ka); tot["kb"] += len(kb); tot["ag"] += len(ag)
        L.append(f"| {s} | {len(ka)} | {len(kb)} | {sum(x['tier'] == 'A' for _, x in ka)}/{sum(x['tier'] == 'A' for _, x in kb)} | "
                 f"{stall(A.get(s, []))}/{stall(B.get(s, []))} | {len(ag)} | {len(art)} |")
    L += ["", f"Total kept: {tot['ka']} ({a.a}), {tot['kb']} ({a.b}); agreed in both seeds: {tot['ag']}.", "",
          "## Reports agreed in both seeds", ""]
    for s, t, x, y in agreed_all:
        L.append(f"- **{s}/{t} {x['profile']}** (WCAG {sc1(x.get('sc')) or '?'}, tier {x['tier']}/{y['tier']}): {x['problem'][:200]}"
                 f"  \n  _seed 2:_ {y['problem'][:160]}")
    L += ["", "## Possible harness artefacts (review by hand; D101)", ""]
    L += [f"- {s}/{t} {x['profile']} step {x['step']}: {x['problem'][:200]}" for s, t, x in flagged] or ["- none"]
    out = ROOT / "results" / time.strftime("%Y-%m-%d") / "v3_live_summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:len(sites) + 6]))


if __name__ == "__main__":
    main()
