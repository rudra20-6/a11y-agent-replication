"""Rerun the paper's experiments with the paper's settings, for one model.

    python experiments/reproduce.py --model gemma --smoke              # cheap check that everything works (a few cents)
    python experiments/reproduce.py --model gemma --setting instrumented --runs 3
    python experiments/reproduce.py --model mistral --setting all

Settings: instrumented (BenchBook with the 23 barriers), clean (BenchBook without barriers), baseline (single LLM),
axe (axe and the rule checks, no model), live (the 27 frozen live-site tasks), all (everything above).
Needs OPENROUTER_API_KEY in .env (or the environment). New runs are written to runs/; score them with
python experiments/paper_tables.py --new runs
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = {"gemma": "gemma-4-26b-a4b-it", "mistral": "mistral-small-3.2-24b-instruct"}
AGENTS = "P1,P2,P3"


def env_for(model: str) -> dict:
    """The environment of the paper's runs: one model for every role, OpenRouter's paid route only, no answer cache."""
    m = MODELS[model]
    e = dict(os.environ)
    e.update({
        "PYTHONIOENCODING": "utf-8",
        "A11Y_NAV_MODEL": m, "A11Y_PLANNER_MODEL": m, "A11Y_JUDGE_MODEL": m, "A11Y_VALIDATOR_MODEL": m,
        "A11Y_OPENROUTER_PAID": "1", "A11Y_KEYS": "openrouter", "A11Y_RPM_OPENROUTER": e.get("A11Y_RPM_OPENROUTER", "120"),
        "A11Y_NO_CACHE": "1",          # every call goes to the model (no replay of earlier answers)
        "A11Y_WAIT_FOR_QUOTA": "1",    # wait out rate limits instead of failing the unit
        "A11Y_BENCH_LOG": "1",         # per-unit traces and event log next to each instrumented/clean run
    })
    if model == "mistral":
        e["A11Y_TEXT_AS_PARTS"] = "1"  # Mistral's endpoint expects text inside a content-parts list
    return e


def run(cmd: list[str], env: dict) -> None:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT, env=env)
    print(f"  exit {r.returncode}, {(time.time() - t0) / 60:.1f} min", flush=True)
    if r.returncode:
        sys.exit(r.returncode)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=tuple(MODELS), required=True)
    ap.add_argument("--setting", choices=("instrumented", "clean", "baseline", "axe", "live", "all"), default="all")
    ap.add_argument("--runs", type=int, default=0, help="repetitions (default: 3 for instrumented/clean, 2 for live)")
    ap.add_argument("--smoke", action="store_true",
                    help="one barrier, one clean task, one baseline unit and one live site with one agent, to check the setup")
    a = ap.parse_args()
    env = env_for(a.model)
    if not env.get("OPENROUTER_API_KEY") and not (ROOT / ".env").exists():
        sys.exit("Set OPENROUTER_API_KEY in .env (copy .env.example) or in the environment.")
    tag = {"gemma": "g", "mistral": "m"}[a.model]
    if a.smoke:
        run(["experiments/full_bench.py", "--catalog", "ma11y_path", "--personas", "P2", "--only", "MP_F78_T6"], env)
        run(["experiments/full_bench.py", "--catalog", "dev", "--clean-only", "--clean-tasks", "T1_flight_search",
             "--personas", "P1"], env)
        run(["experiments/llm_baseline.py", "--catalog", "ma11y_path", "--only", "MP_F78_T6"], env)
        run(["experiments/real_site_batch.py", "--frozen", "data/frozen_tasks.json", "--sites", "govuk_holiday",
             "--personas", "P1", "--tag", f"smoke{tag}"], env)
        return
    todo = ("axe", "baseline", "instrumented", "clean", "live") if a.setting == "all" else (a.setting,)
    for s in todo:
        if s == "axe":
            run(["experiments/ma11y_bench.py", "--placement", "path"], env)
        elif s == "baseline":
            run(["experiments/llm_baseline.py", "--catalog", "ma11y_path", "--states", "all"], env)
        elif s == "instrumented":
            for _ in range(a.runs or 3):
                run(["experiments/full_bench.py", "--catalog", "ma11y_path", "--personas", AGENTS], env)
        elif s == "clean":
            for _ in range(a.runs or 3):
                run(["experiments/full_bench.py", "--catalog", "dev", "--clean-only", "--personas", AGENTS], env)
        elif s == "live":
            for i in range(1, (a.runs or 2) + 1):
                run(["experiments/real_site_batch.py", "--frozen", "data/frozen_tasks.json", "--personas", AGENTS,
                     "--tag", f"r{tag}{i}"], env)


if __name__ == "__main__":
    main()
