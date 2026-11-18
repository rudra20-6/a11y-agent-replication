"""Build the human rating kit for the live-site study (paper plan: rating, triage test I1, reference check I4).

Writes results/rating_kit/:
- tasks.csv            one row per tested task x persona (P1-P3): rate by doing the task yourself, BEFORE looking at
                       any tool output. Columns to fill: finished (y/n), where_stuck, barrier, wcag, minutes.
- findings.csv         every distinct rule finding and tier-B agent finding on the tested tasks, in a fixed random
                       order, with NO information about whether a persona agent stalled or confirmed it (the triage
                       test compares those groups, so raters must not see them). Columns to fill: real (y/n/unsure),
                       blocks_task (y/n/unsure), note.
- reference_check.csv  one row per tested task: the sighted agent's answer and its final screenshot. Fill:
                       really_finished (y/n), note.
- KEY_findings.csv     the hidden key (finding id -> source, tier, agent corroboration). Do not open while rating.
- RATING_GUIDE.md      instructions.

Only runs counted in REPEATS.md are used (valid, not lost to outages), and only tasks that were tested.
Usage: python experiments/make_rating_kit.py
"""
import csv
import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))

from compare_runs import API_LOSS, EXCLUDE, NAME  # noqa: E402

OUT = ROOT / "results" / "rating_kit"
PERSONA = {"P1": "screen reader (NVDA + Chrome, no looking at the screen)", "P2": "keyboard only (no mouse, no touchpad)",
           "P3": "400% browser zoom (Ctrl + until 400%), mouse allowed, no sideways scrolling"}


def valid_runs():
    for d in sorted(glob.glob(str(ROOT / "runs" / "real-2026*"))):
        p = Path(d)
        m = NAME.match(p.name)
        if not m or m["date"] < "20261030" or p.name in EXCLUDE:
            continue
        try:
            meta = json.loads((p / "meta.json").read_text(encoding="utf-8"))
            res = json.loads((p / "results.json").read_text(encoding="utf-8"))["results"]
            plan = json.loads((p / "plan.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        if meta.get("status") != "done" or m["site"].startswith("w3c"):   # W3C runs locally and has W3C's own key
            continue
        if res and all(r.get("invalid") and any(x in r["invalid"] for x in API_LOSS) for r in res):
            continue
        yield p, m["site"], res, plan


def post_invalid(plan, goal):
    for t in plan.get("tasks", []):
        if t.get("goal") == goal and (t.get("post_validation") or {}).get("verdict") == "invalid":
            return True
    return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks, findings, refs = [], {}, []
    for run_dir, site, res, plan in valid_runs():
        for r in res:
            if r.get("invalid"):
                continue
            goal = r["task"]["goal"]
            excluded = post_invalid(plan, goal)
            tid = f"{run_dir.name.removeprefix('real-')}/{r['task']['id']}"
            start = r["task"].get("start_url", "")
            refs.append({"task_id": tid, "site": site, "start_url": start, "goal": goal,
                         "sighted_agent_answer": (r["reference"].get("answer") or "")[:300],
                         "final_screenshot": f"runs/{run_dir.name}/live/ (REF, last image)", "excluded_by_validator": excluded,
                         "really_finished": "", "note": ""})
            for p in ("P1", "P2", "P3"):
                st = (r.get("profiles", {}).get(p) or {}).get("status", "")
                tasks.append({"task_id": tid, "site": site, "persona": p, "how": PERSONA[p], "start_url": start, "goal": goal,
                              "excluded_by_validator": excluded,
                              # A: the persona agent stalled here, so the paper needs to know if a person would too
                              "priority": "A" if st in ("stuck", "max_steps") else "B",
                              "finished": "", "where_stuck": "", "barrier": "", "wcag": "", "minutes": ""})
            stalled = {p for p, v in r.get("profiles", {}).items() if v.get("status") in ("stuck", "max_steps")}
            for f in r.get("findings", []) + r.get("agent_findings", []):
                if f.get("target") == "task" and (f.get("evidence") or {}).get("source") == "agent" and f.get("tier") != "B":
                    continue   # the "task stalled" summary line duplicates a rule finding
                key = (site, goal[:80], f["profile"], f.get("target", ""), f["message"].split(":")[0])
                e = findings.setdefault(key, {"site": site, "start_url": start, "goal": goal, "persona": f["profile"],
                                              "wcag": f.get("sc", ""), "control": f.get("target", ""),
                                              "what_the_tool_says": f["message"][:220], "step": f.get("step", -1),
                                              "source": "agent" if f.get("tier") == "B" else "rule",
                                              "persona_agent_stalled": False, "runs": 0})
                e["runs"] += 1
                e["persona_agent_stalled"] |= f["profile"] in stalled
    rows = list(findings.values())
    rng = random.Random(20261104)
    rng.shuffle(rows)
    second = set(rng.sample(range(len(rows)), k=round(0.4 * len(rows))))
    for i, r in enumerate(rows, 1):
        r["finding_id"] = f"F{i:03d}"
        r["second_rater"] = "y" if (i - 1) in second else ""

    def write(name, data, cols):
        with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    write("tasks.csv", tasks, ["task_id", "priority", "site", "persona", "how", "start_url", "goal", "excluded_by_validator",
                               "finished", "where_stuck", "barrier", "wcag", "minutes"])
    blind = [{**r, "real": "", "blocks_task": "", "note": ""} for r in rows]
    write("findings.csv", blind, ["finding_id", "second_rater", "site", "start_url", "goal", "persona", "wcag", "control",
                                  "what_the_tool_says", "real", "blocks_task", "note"])
    write("KEY_findings.csv", rows, ["finding_id", "source", "persona_agent_stalled", "runs", "step"])
    write("reference_check.csv", refs, ["task_id", "site", "start_url", "goal", "sighted_agent_answer", "final_screenshot",
                                        "excluded_by_validator", "really_finished", "note"])
    (OUT / "RATING_GUIDE.md").write_text(GUIDE.format(n_tasks=len(tasks), n_find=len(rows), n_ref=len(refs)), encoding="utf-8")
    print(f"tasks.csv: {len(tasks)} task x persona rows; findings.csv: {len(rows)} findings "
          f"({sum(r['source'] == 'rule' for r in rows)} rule, {sum(r['source'] == 'agent' for r in rows)} agent-only); "
          f"reference_check.csv: {len(refs)} tasks. Wrote {OUT}")


GUIDE = """# Rating guide (live-site study)

Thank you for rating. Your judgements are the ground truth for the paper, so please follow the order below.

## Setup
- **Chrome**, and **NVDA** (free): https://www.nvaccess.org/download/. Use NVDA's default settings. Insert+Q quits.
- WCAG 2.2 quick reference: https://www.w3.org/WAI/WCAG22/quickref/

## Part 1: do the tasks yourself (tasks.csv, {n_tasks} rows). Do this BEFORE looking at findings.csv
Do every **priority A** row (where the tool's persona agent got stuck); B rows if time allows. For each row, open start_url and try to do the goal as the persona says:
- **P1 screen reader:** NVDA on, eyes off the screen (or the screen turned off), keyboard only.
- **P2 keyboard only:** no mouse or touchpad, only Tab, Shift+Tab, arrows, Enter, Space, Escape.
- **P3 400% zoom:** Ctrl and + until the browser says 400%. A mouse is fine. Don't scroll sideways; if you have to, write that down.

Then fill in:
- **finished:** y or n.
- **where_stuck:** the step and the control.
- **barrier:** in your own words.
- **wcag:** if you know it.
- **minutes:** how long it took.

Stop after 10 minutes and mark it n. Never submit real data or pay: stop at the last step before that and count
reaching it as finished.

## Part 2: judge the tool's findings (findings.csv, {n_find} rows)
For each finding, go to the page and the control it names. Mark:
- **real:** y if the problem the tool describes is really there for that persona, n if not, unsure otherwise.
- **blocks_task:** y if this problem alone would stop that persona from finishing the goal, n if it only slows or
  annoys them.

The rows are shuffled on purpose, and the file doesn't say how the tool found each one. Please don't open
KEY_findings.csv.

## Part 3: did the sighted agent really finish? (reference_check.csv, {n_ref} rows)
Look at the sighted agent's answer and its last screenshot (folder given). Mark really_finished y or n.

## Second rater
Rate only the findings.csv rows with second_rater = y (about 40%), alone, without seeing the first rater's answers.
"""


if __name__ == "__main__":
    main()
