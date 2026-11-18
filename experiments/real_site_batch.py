"""Run the full pipeline (URL only) on a list of real websites, one after another, for the empirical study.

Each site gets its own run directory under runs/ (so the dashboard lists it) and a line in a batch summary. A site
that fails doesn't stop the batch. The 7 held-out pilot sites are NOT in the default list: they run once, after the
blind answer key exists (D31, D36).

Usage: python experiments/real_site_batch.py [--tasks 2] [--sites name,name] [--personas P1,P2,P3] [--tag v2]
                                            [--walkthroughs results/<date>/walkthroughs]
With --walkthroughs, each finished site also gets a step-by-step walkthrough and a row in RUNS.md there.
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from a11y_agent.benchserver import serve
from a11y_agent.config import BENCH, RUNS
from a11y_agent.pipeline import run_url

SITES = {  # dev sites (D31) and independent references
    "dmrc": "https://www.delhimetrorail.com/",
    "practo": "https://www.practo.com/hyderabad/dentist",
    "indigo": "https://www.goindigo.in/",
    "flipkart": "https://www.flipkart.com/",
    "swiggy": "https://www.swiggy.com/",
    "w3c_bad_before": "https://www.w3.org/WAI/demos/bad/before/home.html",   # W3C demo with documented barriers
    "w3c_bad_after": "https://www.w3.org/WAI/demos/bad/after/home.html",     # its accessible version (false-alarm control)
    # The live W3C pages sit behind a Cloudflare bot check, so the same demo is also served locally from W3C's own
    # download (https://www.w3.org/WAI/demos/bad/bad.zip, extracted to bench/external/w3c_bad; not committed).
    "w3c_bad_before_local": "local:w3c_bad/before/home.html",
    "w3c_bad_after_local": "local:w3c_bad/after/home.html",
    "govuk_holiday": "https://www.gov.uk/calculate-your-holiday-entitlement",  # accessible service (false-alarm control)
    # Extension sites (D73): neither dev nor held-out; exploratory, chosen to cover the thesis's domains. Each was
    # checked to load headlessly without a bot wall on 2 Nov 2026 (HDFC timed out and was replaced by ICICI).
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
    """True once some key answers a screenshot call; False if the deadline passes first (D75, D77)."""
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


def write_walkthrough(wdir: Path, name: str, run_dir: Path, row: dict, tag: str = "") -> None:
    """The step-by-step walkthrough for this site, and one row in RUNS.md (the index of every walkthrough written)."""
    from experiments.make_walkthrough import walk_run
    wdir.mkdir(parents=True, exist_ok=True)
    fname = f"{run_dir.name.removeprefix('real-')}.md"   # unique per run: repeat runs of a site don't overwrite
    if (run_dir / "results.json").exists():
        walk_run(run_dir, wdir / fname)
        link = f"[{fname}]({fname})"
    else:
        link = "no walkthrough (no task was tested)"
    outcome = "; ".join(f"{', '.join(f'{p} {s}' for p, s in agents.items()) or 'not tested'}"
                        for agents in (row.get("agents") or {}).values()) or row.get("error", "")[:80] or "no task kept"
    index = wdir / "RUNS.md"
    if not index.exists():
        index.write_text(
            "# Walkthroughs written by the batch\n\n"
            "One row per site run, newest last. Generated automatically (experiments/real_site_batch.py --walkthroughs).\n\n"
            "| When | Site | Tasks tested | Rule findings | Agent-only | Agents (per tested task) | Walkthrough |\n"
            "|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with open(index, "a", encoding="utf-8") as f:
        f.write(f"| {time.strftime('%d %b %H:%M')} | {name}{f' ({tag})' if tag else ''} | {row.get('tested', 0)}/{row.get('tasks', 0)} | "
                f"{row.get('findings', '-')} | {row.get('agent_findings', '-')} | {outcome.replace('|', '/')} | {link} |\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=2)
    ap.add_argument("--sites", default="")
    ap.add_argument("--personas", default="P1,P2,P3,P4,P5", help="v2 runs the agent personas only: P1,P2,P3")
    ap.add_argument("--tag", default="", help="added to run folder names, e.g. v2")
    ap.add_argument("--walkthroughs", default="", help="folder for a walkthrough per site and the RUNS.md index")
    ap.add_argument("--until", default="", help="HH:MM (local time): start no new site after this")
    ap.add_argument("--preflight", action="store_true",
                    help="before each site, wait (re-checking every 10 min) until some key answers an image call")
    ap.add_argument("--frozen", default="",
                    help="results/frozen_tasks.json: test exactly these tasks per site (no planner); only its sites run")
    a = ap.parse_args()
    frozen = json.loads(Path(a.frozen).read_text(encoding="utf-8")) if a.frozen else {}
    names = a.sites.split(",") if a.sites else list(frozen or SITES)
    stamp = time.strftime("%Y%m%d")
    summary_path = RUNS / f"real_site_batch-{time.strftime('%Y%m%d-%H%M%S')}.json"
    summary = []
    local_base, httpd = serve(directory=BENCH / "external")
    for name in names:
        if a.until and time.strftime("%H:%M") >= a.until:
            print(f"stopping: it is past {a.until}, so {name} and the rest are not started", flush=True)
            break
        if a.preflight and not wait_for_keys(a.until):
            print(f"stopping: no key answered an image call before {a.until}; {name} and the rest are not started", flush=True)
            break
        out = RUNS / f"real-{stamp}-{a.tag + '-' if a.tag else ''}{name}"
        t0 = time.time()
        url = SITES[name].replace("local:", local_base)
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
        if a.walkthroughs:
            try:
                write_walkthrough(Path(a.walkthroughs), name, out, row, a.tag)
            except Exception as e:   # a walkthrough is a report; it must never stop the batch
                print(f"  (walkthrough for {name} failed: {str(e)[:120]})", flush=True)
        print(f"{name:16s} {row['status']:6s} tested {row.get('tested', 0)}/{row.get('tasks', 0)} tasks | findings {row.get('findings', '-')} "
              f"| tier B {row.get('agent_findings', '-')} | tool errors {row.get('tool_errors', '-')} | {row['minutes']} min "
              f"{row.get('error', '')[:120]}", flush=True)
    httpd.shutdown()
    print("summary:", summary_path)


if __name__ == "__main__":
    main()
