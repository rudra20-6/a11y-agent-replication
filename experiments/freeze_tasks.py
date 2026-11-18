"""Freeze the live-site task list (paper plan, 4 Nov): every task tested in a counted run, minus those the validator
later ruled invalid, de-duplicated by goal per site. Repeat runs with `real_site_batch.py --frozen` then test the SAME
tasks, so run-to-run agreement measures the method, not the planner.

Writes results/frozen_tasks.json: {site: {url, specialists, tasks: [task cards], sources: [run folders]}}.
specialists is the OR of the source plans' (a check family planned for any source run is kept).
Usage: python experiments/freeze_tasks.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))

from make_rating_kit import post_invalid, valid_runs  # noqa: E402

OUT = ROOT / "results" / "frozen_tasks.json"
CARD = ("goal", "start_url", "success", "stop_before", "features")


def main():
    sites: dict[str, dict] = {}
    for run_dir, site, res, plan in valid_runs():
        for r in res:
            if r.get("invalid") or post_invalid(plan, r["task"]["goal"]):
                continue
            e = sites.setdefault(site, {"url": plan["url"], "specialists": {}, "tasks": [], "sources": []})
            for k, v in (plan.get("specialists") or {}).items():
                e["specialists"][k] = bool(e["specialists"].get(k)) or bool(v)
            if run_dir.name not in e["sources"]:
                e["sources"].append(run_dir.name)
            goal = r["task"]["goal"].strip()
            if any(t["goal"].strip().lower() == goal.lower() for t in e["tasks"]):
                continue
            e["tasks"].append({"id": f"t{len(e['tasks']) + 1}", **{k: r["task"].get(k, "") for k in CARD},
                               "frozen_from": f"{run_dir.name}/{r['task']['id']}"})
    OUT.write_text(json.dumps(sites, indent=1, ensure_ascii=False), encoding="utf-8")
    n = sum(len(e["tasks"]) for e in sites.values())
    print(f"{n} tasks on {len(sites)} sites -> {OUT}")
    for s, e in sites.items():
        print(f"  {s:14s} {len(e['tasks'])}  " + " | ".join(t["goal"][:50] for t in e["tasks"]))


if __name__ == "__main__":
    main()
