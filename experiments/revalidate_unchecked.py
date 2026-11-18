"""Validate, after the fact, the tasks a run kept as `unchecked` because the validator call failed (D81).

The validator only needs the task card and the pages the explorer saw, and every run saves both in plan.json, so the
check can be made later with the same prompt and model. The verdict is stored next to the original under
`post_validation` (the original `validation` is left as it was); the run date is passed as "today", as in the run.
A task judged invalid here is excluded from the analysis like any other invalid task.

Usage: python experiments/revalidate_unchecked.py [--runs "runs/real-2026110[23]-*"] [--dry-run]
"""
import argparse
import glob
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11y_agent.config import SETTINGS  # noqa: E402
from a11y_agent.llm import LLM  # noqa: E402
from a11y_agent.planner import validate_tasks  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "runs" / "real-2026110[23]-*"))
    ap.add_argument("--dry-run", action="store_true", help="list the unchecked tasks, call nothing")
    a = ap.parse_args()
    llm = LLM(SETTINGS.planner_model, role="validator", use_cache=False)
    for plan_path in sorted(Path(p) / "plan.json" for p in glob.glob(a.runs)):
        if not plan_path.exists():
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        todo = [t for t in plan.get("tasks", []) if (t.get("validation") or {}).get("verdict") == "unchecked"
                and "post_validation" not in t]
        if not todo:
            continue
        run_date = plan_path.parent.name.split("-")[1]          # real-YYYYMMDD-...
        today = f"{run_date[:4]}-{run_date[4:6]}-{run_date[6:]}"
        print(f"{plan_path.parent.name}: {len(todo)} unchecked: " + "; ".join(t["goal"][:60] for t in todo), flush=True)
        if a.dry_run:
            continue
        checked = validate_tasks([{k: v for k, v in t.items() if k != "validation"} for t in todo], plan["pages"], llm,
                                 today=today, site_url=plan.get("url", ""))
        for t, c in zip(todo, checked):
            t["post_validation"] = {**(c.get("validation") or {}), "checked_at": time.strftime("%Y-%m-%d %H:%M")}
            print(f"   {t['post_validation'].get('verdict'):10} {t['goal'][:70]}", flush=True)
        plan_path.write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
