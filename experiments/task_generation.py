"""RQ3 task generation: the planning sessions behind the 27 live tasks (data/task_generation/) and what happened to
every task card the planner wrote. No model is called.

For each session: the cards the validator kept (plan.json "tasks", with verdict valid / fix / unchecked when the
validator call failed), the cards it dropped ("rejected_tasks"), a later validation of unchecked cards
("post_validation", made with experiments/revalidate_unchecked.py), and whether the reference agent completed each
kept card in that session (results.json). Then the verdict and source of each of the 27 frozen tasks.

The paper counts 20 planning sessions. Three further sessions (NOT_COUNTED) are in data/task_generation/ for
completeness; none of them produced a final task. --all counts them too.

Usage: python experiments/task_generation.py [--all]
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TG = ROOT / "data" / "task_generation"
NOT_COUNTED = ("real-20261103-ext-r2b-wikipedia", "real-20261103-extb-myntra", "real-20261103-r2c-practo")


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    every = "--all" in sys.argv
    frozen = load(ROOT / "data" / "frozen_tasks.json")
    sources = {t["frozen_from"].split("/")[0] for e in frozen.values() for t in e["tasks"]}
    final = {(t["frozen_from"].split("/")[0], t["goal"].strip()) for e in frozen.values() for t in e["tasks"]}
    final_goals = {g.lower() for _, g in final}
    verdict, completed, kept_n, dropped_n, rows, fate = Counter(), 0, 0, 0, [], Counter()
    sessions = sorted(d for d in TG.iterdir() if (d / "plan.json").exists() and (every or d.name not in NOT_COUNTED))
    for d in sessions:
        plan, res = load(d / "plan.json"), load(d / "results.json")["results"]
        by_goal = {r["task"]["goal"].strip(): r for r in res}
        kept, dropped = plan.get("tasks", []), plan.get("rejected_tasks", [])
        kept_n += len(kept)
        dropped_n += len(dropped)
        done = 0
        fate["dropped by the validator"] += len(dropped)
        for t in kept:
            verdict[(t.get("validation") or {}).get("verdict") or "none"] += 1
            g = t["goal"].strip()
            r = by_goal.get(g)
            ok = bool(r and not r.get("invalid"))
            done += ok
            pv = (t.get("post_validation") or {}).get("verdict")
            fate["final task" if (d.name, g) in final else
                 "reference agent did not complete it in its session" if not ok else
                 "removed: judged invalid by the later validation" if pv == "invalid" else
                 "removed: same goal as a final task" if g.lower() in final_goals else "other"] += 1
        completed += done
        rows.append(f"| {d.name} | {len(kept) + len(dropped)} | {len(kept)} | {len(dropped)} | {done} | "
                    f"{'yes' if d.name in sources else ''} |")
    print(f"# Task generation\n\n{len(sessions)} planning sessions on "
          f"{len({load(d / 'plan.json')['url'] for d in sessions})} sites.\n")
    print(f"- cards written: {kept_n + dropped_n}; dropped by the validator: {dropped_n}; kept: {kept_n}")
    print(f"- kept cards by validator verdict: valid {verdict['valid']}, repaired (fix) {verdict['fix']}, "
          f"unchecked (validator call failed) {verdict['unchecked']}")
    print(f"- kept cards the reference agent completed in their session: {completed} of {kept_n}")
    print("- what happened to every card: " + "; ".join(f"{k} {n}" for k, n in fate.most_common()))
    if not every:
        print(f"- not counted (data included; --all counts them): {', '.join(NOT_COUNTED)}")
    print()
    print("| Session | Cards | Kept | Dropped | Reference completed | Source of a final task |\n|---|---|---|---|---|---|")
    print("\n".join(rows))
    print("\n## The 27 final tasks (data/frozen_tasks.json)\n")
    print("| Site | Task | Source session | Validator | Later validation |\n|---|---|---|---|---|")
    tally = Counter()
    for site, e in frozen.items():
        for t in e["tasks"]:
            run = t["frozen_from"].split("/")[0]
            card = next((c for c in load(TG / run / "plan.json").get("tasks", [])
                         if c["goal"].strip() == t["goal"].strip()), {})
            v = (card.get("validation") or {}).get("verdict", "?")
            pv = (card.get("post_validation") or {}).get("verdict", "")
            tally[pv or v] += 1
            print(f"| {site} | {t['id']} | {run} | {v} | {pv} |")
    print("\nFinal verdict per task (later validation where the first call failed): "
          + ", ".join(f"{k} {n}" for k, n in tally.most_common()))


if __name__ == "__main__":
    main()
