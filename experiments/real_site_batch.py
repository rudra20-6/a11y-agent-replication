"""Run the full pipeline (URL only) on a list of real websites, one after another, for the empirical study.

Each site gets its own run directory under runs/ and a line in a batch summary. A site that fails doesn't stop the
batch.

Usage: python experiments/real_site_batch.py [--frozen data/frozen_tasks.json] [--tasks 2] [--sites name,name]
                                            [--personas P1,P2,P3] [--tag NAME]
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from a11y_agent.config import RUNS
from a11y_agent.pipeline import run_url

SITES = {  # the 13 live sites of the paper
    "dmrc": "https://www.delhimetrorail.com/",
    "practo": "https://www.practo.com/hyderabad/dentist",
    "flipkart": "https://www.flipkart.com/",
    "swiggy": "https://www.swiggy.com/",
    "govuk_holiday": "https://www.gov.uk/calculate-your-holiday-entitlement",  # accessibility-focused
    "indiapost": "https://www.indiapost.gov.in/",                      # government: postal services
    "uidai": "https://uidai.gov.in/en/",                               # government: Aadhaar (English pages)
    "passportseva": "https://www.passportindia.gov.in/",              # government: passports
    "tata1mg": "https://www.1mg.com/",                                 # health: online pharmacy
    "icici_emi": "https://www.icicibank.com/calculator/home-loan-emi-calculator",  # banking: EMI calculator
    "myntra": "https://www.myntra.com/",                               # e-commerce: fashion
    "wikipedia": "https://en.wikipedia.org/wiki/Main_Page",            # accessible control
    "nhs_bmi": "https://www.nhs.uk/health-assessment-tools/calculate-your-body-mass-index/calculate-bmi-for-adults",  # accessible control
}


def wait_for_keys(until: str) -> bool:
    """True once some endpoint answers a screenshot call; False if the deadline passes first."""
    from a11y_agent.config import SETTINGS
    from a11y_agent.providers import POOL, probe_png
    while True:
        alive = POOL.preflight(SETTINGS.nav_model, probe_png())
        text_only = [e.name for e in POOL.endpoints if e.no_images_until > time.time()]
        if alive:
            print(f"{time.strftime('%H:%M')} preflight: answering screenshots: {', '.join(alive)}"
                  + (f"; text only: {', '.join(text_only)}" if text_only else ""), flush=True)
            return True
        if until and time.strftime("%H:%M") >= until:
            return False
        print(f"{time.strftime('%H:%M')} preflight: no key answers an image call; checking again in 10 min", flush=True)
        time.sleep(600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=2)
    ap.add_argument("--sites", default="")
    ap.add_argument("--personas", default="P1,P2,P3", help="the agents to run")
    ap.add_argument("--tag", default="", help="added to run folder names, e.g. r1")
    ap.add_argument("--until", default="", help="HH:MM (local time): start no new site after this")
    ap.add_argument("--preflight", action="store_true",
                    help="before each site, wait (re-checking every 10 min) until the model answers an image call")
    ap.add_argument("--frozen", default="",
                    help="data/frozen_tasks.json: test exactly these tasks per site (no planner); only its sites run")
    a = ap.parse_args()
    frozen = json.loads(Path(a.frozen).read_text(encoding="utf-8")) if a.frozen else {}
    names = a.sites.split(",") if a.sites else list(frozen or SITES)
    stamp = time.strftime("%Y%m%d")
    summary_path = RUNS / f"real_site_batch-{time.strftime('%Y%m%d-%H%M%S')}.json"
    summary = []
    for name in names:
        if a.until and time.strftime("%H:%M") >= a.until:
            print(f"stopping: it is past {a.until}, so {name} and the rest are not started", flush=True)
            break
        if a.preflight and not wait_for_keys(a.until):
            print(f"stopping: the model answered no image call before {a.until}; {name} and the rest are not started", flush=True)
            break
        out = RUNS / f"real-{stamp}-{a.tag + '-' if a.tag else ''}{name}"
        t0 = time.time()
        url = SITES[name]
        row = {"site": name, "url": url, "run_dir": str(out)}
        try:
            run_url(url, a.tasks, profiles=tuple(a.personas.split(",")), out_dir=out, agents=True, frozen=frozen.get(name))
            rp = out / "results.json"   # absent when the planner kept no task: a result, not a crash
            res = json.loads(rp.read_text(encoding="utf-8"))["results"] if rp.exists() else []
            row.update(status="done", tasks=len(res), tested=sum(1 for r in res if not r.get("invalid")),
                       findings=sum(len(r.get("findings", [])) for r in res),
                       unconfirmed=sum(len(r.get("unconfirmed_stalls", [])) for r in res),
                       agent_findings=sum(len(r.get("agent_findings", [])) for r in res),
                       agents={r["task"]["goal"][:60]: {p: v["status"] for p, v in r.get("profiles", {}).items()} for r in res},
                       tool_errors=sum(len(r.get("tool_errors", [])) for r in res),
                       not_tested=[r.get("invalid") for r in res if r.get("invalid")])
        except Exception as e:
            row.update(status="failed", error=str(e)[:300], trace=traceback.format_exc()[-600:])
        row["minutes"] = round((time.time() - t0) / 60, 1)
        summary.append(row)
        summary_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{name:16s} {row['status']:6s} tested {row.get('tested', 0)}/{row.get('tasks', 0)} tasks | findings {row.get('findings', '-')} "
              f"| agent-only {row.get('agent_findings', '-')} | tool errors {row.get('tool_errors', '-')} | {row['minutes']} min "
              f"{row.get('error', '')[:120]}", flush=True)
    print("summary:", summary_path)


if __name__ == "__main__":
    main()
