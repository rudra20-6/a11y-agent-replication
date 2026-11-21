# Replication package: Task-Level Web Accessibility Testing with Constrained LLM Agents

This package contains the tool, the instrumented application, the task list, and the saved runs behind every number in
the paper. Every table can be recomputed from the saved runs without calling a model (section 2). The experiments can
also be rerun (section 3).

## 1. Contents

| Path | What it is |
|---|---|
| `a11y_agent/` | The tool: explorer, planner and validator (`planner.py`), reference and constrained agents (`navigator.py`), rule checks (`checker.py`, `page_helper.js`), verification, trace filters and tiers (`pipeline.py`), model access (`llm.py`, `providers.py`) |
| `a11y_agent/personas.yaml` | The knowledge and strategy cards of P1 (no vision), P2 (limited fine motor control) and P3 (low vision) |
| `agent_prompts.pdf` | The prompts of P1-P3 exactly as sent to the model (rebuilt by `experiments/export_prompts.py`) |
| `bench/app/` | BenchBook, the instrumented application (seven tasks) |
| `bench/mutants/ma11y.js`, `ma11y_path.yaml` | The ported Ma11y mutation operators and the 23 barriers placed on the task paths |
| `bench/tasks/benchbook.yaml` | The seven tasks with their scripted correct paths |
| `data/frozen_tasks.json` | The 27 live-site tasks on 13 sites used in every live run, with the planning session each came from |
| `data/task_generation/` | The planning sessions behind those tasks: the explored pages and task cards with validator verdicts (`plan.json`), the reference agent's attempt at each card (`results.json`), `meta.json`, `report.md` |
| `data/axe_ma11y_bench_path.json` | axe (and rule-check) results on every barrier, Ma11y's oracle |
| `data/ma11y_reach.json` | Reach test: whether each barrier fires when each agent performs the task step its own way |
| `data/clean_causes_gemma.md`, `data/clean_causes_mistral.md` | Manual classification of every kept report on the clean application, per model (the paper's table of false positives) |
| `runs/gemma/`, `runs/mistral/` | The saved runs of the paper, one folder per model (section 4) |
| `experiments/` | Scripts that produced the runs and the tables |
| `results/paper_tables.md` | Output of `experiments/paper_tables.py`: the paper's numbers recomputed from `runs/` |
| `tests/` | Unit tests of the harness (pages under `tests/fixtures/`) |
| `vendor/axe.min.js` | axe-core, used by the axe baseline |

## 2. Recompute the paper's numbers (no model calls)

Requires Python 3.11 or newer; the standard library is enough for this step.

```
python experiments/paper_tables.py
```

It prints, for each model, and writes to `results/paper_tables.md`:

| Paper | Output section |
|---|---|
| Table "Detected and testable pairs", RQ1 text, McNemar tests | RQ1: instrumented application |
| RQ2 clean-application rate, rule checks on the clean application | RQ2: clean application |
| RQ2 repeatability (agreement, Cohen's kappa), RQ3 findings, tier A, findings in both runs, findings by type and site category, table "Live-site findings reproduced in both runs" | RQ2/RQ3: live sites |
| Model calls | Cost |

RQ3 task generation (cards written, validator verdicts, cards the reference agent completed, and the verdict and source
of each of the 27 final tasks) comes from a separate script:

```
python experiments/task_generation.py
```

It counts the paper's 20 planning sessions. `data/task_generation/` also holds three further sessions from 3 Nov that
produced no final task; `--all` counts them too.

How the counts are made:

- **Pair**: a barrier together with one agent it affects. The affected agents per barrier are in
  `experiments/ma11y_relabel.py` (`LABELS`), each change from the pre-registered labels with its reason.
- **Testable**: the reference agent completed the task in that run (`invalid` is absent in the run's row).
- **Detected**: the agent stalled on the task or has a kept report at the barrier (`flagged_v3` in the run's rows).
- **Single LLM**: a pair counts when the model lists a problem for the affected group that it does not list on the
  clean application (`lenient_flagged`). axe: a new violation on the changed element (Ma11y's oracle, `axe_kill`).
- **Clean application**: an attempt is a false positive when it has at least one kept report. The three Mistral
  attempts whose report describes the application's one real barrier (the passenger form comes back empty after
  "Change passenger details") are excluded.
- **Live sites**: findings are the kept reports (`v3_live_summary.kept`); a finding is "in both runs" when the same
  agent reports the same problem on the same task in both runs (`v3_live_summary.same`).

## 3. Rerun the experiments

### 3.1 Setup

Requirements: Python 3.11 or newer (the paper's runs used 3.13), **Google Chrome** installed (the tool drives the
installed Chrome, because several live sites refuse Playwright's bundled Chromium), and an
[OpenRouter](https://openrouter.ai) API key with credit.

```
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env ; then set OPENROUTER_API_KEY in .env
```

Check the setup without calling a model (about 5 minutes):

```
python tests/test_gold.py --catalog ma11y_path     # every task's scripted path completes on BenchBook, and with a mouse
                                                   # under each of the 23 barriers (MP_F36_T3 breaks the path by design)
python experiments/ma11y_bench.py --placement path  # axe and the rule checks on every barrier
```

### 3.2 Smoke test (a few cents)

```
python experiments/reproduce.py --model gemma --smoke
```

It runs one barrier (focus indicator removed) with P2, one clean task with P1, the single-LLM baseline on one barrier,
and the four GOV.UK live tasks with P1, all with the paper's settings. Measured with Gemma: about 30 minutes and
US$0.04. Then `python experiments/paper_tables.py --new runs` should show the barrier detected (1/1).

### 3.3 Full reruns

`experiments/reproduce.py` sets the paper's configuration for the chosen model: the same model for every role,
OpenRouter's paid route only, temperature 0, no answer cache (`A11Y_NO_CACHE=1`), waiting out rate limits
(`A11Y_WAIT_FOR_QUOTA=1`), and per-unit traces (`A11Y_BENCH_LOG=1`).

```
python experiments/reproduce.py --model gemma   --setting all     # or: mistral
python experiments/reproduce.py --model gemma   --setting instrumented --runs 3
```

| Setting (`--setting`) | What it runs | Model calls per run | Time per run | Approx. cost per run |
|---|---|---|---|---|
| `axe` | axe and the rule checks on the 23 barriers (`ma11y_bench.py --placement path`) | 0 | 5 min | 0 |
| `baseline` | single LLM on every page state of every barrier's task (`llm_baseline.py --catalog ma11y_path`) | 192 | 15 min | US$0.05 |
| `instrumented` | the 23 barriers with P1-P3 (`full_bench.py --catalog ma11y_path`); 3 runs | Gemma 1,750; Mistral 2,200 | 35-100 min | US$0.40-0.50 |
| `clean` | the 7 clean tasks with P1-P3 (`full_bench.py --catalog dev --clean-only`); 3 runs | Gemma 320; Mistral 440 | 25-40 min | US$0.10 |
| `live` | the 27 frozen tasks on 13 sites with P1-P3 (`real_site_batch.py --frozen data/frozen_tasks.json`); 2 runs | Gemma 1,600; Mistral 1,500 | 1-2 h | US$0.35-0.65 |

Times and calls are those of the paper's runs; costs use OpenRouter's prices in November 2026 (about US$0.21 per 1,000
calls for Gemma and US$0.22-0.44 for Mistral). The whole study costs about US$2-3.50 per model.

Score the new runs (they are written to `runs/`):

```
python experiments/paper_tables.py --new runs
```

It groups the new files by the model recorded in them and prints the same tables as for the paper's runs
(`results/new_runs_tables.md`). Live-site numbers need two live runs.

### 3.4 What to expect

- **Instrumented and clean application.** BenchBook is local and fixed, so differences come only from the model. Calls
  use temperature 0, but hosted models are not bit-for-bit deterministic, so expect detections within one or two pairs
  of the paper's per run, and similar false-positive rates.
- **Live sites** change between visits (content, advertisements, pop-ups, redesigns). Some tasks may no longer be
  possible, and findings will differ. The paper reports how much two runs a day apart agree; a rerun months later will
  agree less.
- **Step limits.** The reference agent, P1 and P2 may take up to 35 steps per task, and P3 up to 25
  (`AGENT_STEPS` in `a11y_agent/pipeline.py`). P1 and P2 move through a page one key press at a time, so a task takes
  them many more steps. P3 clicks controls directly, like the reference agent, and needs fewer. Every saved run used
  these limits; each run's `events.jsonl` records them in its `agent_start` events.
- **Model availability.** If a model is withdrawn from OpenRouter, set any OpenRouter model ID in `experiments/reproduce.py`
  (`MODELS`), or set `A11Y_NAV_MODEL`, `A11Y_PLANNER_MODEL`, `A11Y_JUDGE_MODEL` and `A11Y_VALIDATOR_MODEL` and run the
  scripts in the table directly.

### 3.5 Other entry points

| Command | What it does |
|---|---|
| `python -m a11y_agent run <url> --tasks 2 --profiles P1,P2,P3` | The whole method on any site: explore, plan and validate tasks, reference run, P1-P3, verification, report in `runs/<timestamp>/report.md` |
| `python -m a11y_agent bench` | Serve BenchBook at http://127.0.0.1:8765/ to look at it in a browser |
| `python experiments/ma11y_reach.py` | Reach test behind the affected-agent labels (no model) |
| `python experiments/export_prompts.py` | Rebuild `agent_prompts.pdf` from the code |

## 4. The saved runs

| Setting | Gemma 4 26B A4B (`runs/gemma/`) | Mistral Small 3.2 24B (`runs/mistral/`) |
|---|---|---|
| Instrumented application, 3 runs | `full_bench_ma11y_path-20261106-{040620,044622,052859}.json` | `full_bench_ma11y_path-20261111-{025450,050022,122825}.json` |
| Clean application, 3 runs | `full_bench_dev-20261106-{061351,062129,062938}.json` | `full_bench_dev-20261111-{043607,063223,112309}.json` |
| Single-LLM baseline | `llm_baseline_ma11y_path_all-20261103-235234.json` | `llm_baseline_ma11y_path_all-20261111-124910.json` |
| Live sites, 2 runs | `real-20261106-v31s1-<site>/`, `real-20261106-v31s2-<site>/` | `real-2026111[23]-v31m1-<site>/`, `real-2026111[23]-v31m2-<site>/` |

- A `full_bench_*.json` file holds one row per barrier (or clean task) with each agent's outcome, the kept and rejected
  reports, the rule-check findings and the model usage. For the Mistral runs, the folder of the same name holds every
  agent's step trace per unit (`units/*.json`) and the event log (`events.jsonl`). The Gemma instrumented and clean
  runs were made before per-unit traces were saved, so only their JSON files exist.
- Mistral's third instrumented run (`122825`) resumed `070820` and redid only the units whose model calls had failed.
  Its JSON holds every unit; the traces of the units it did not redo, and the model calls they used, are in `070820`.
- A live-site folder holds `plan.json` (the tasks), `results.json` (every agent's trace, reports, verdicts and tiers),
  `events.jsonl` (every step and model call), `report.md` and `meta.json`. The `real_site_batch-*.json` files are the
  per-batch summaries.

## 5. Licence of third-party parts

`vendor/axe.min.js` is axe-core (Mozilla Public License 2.0). The Ma11y operators in `bench/mutants/ma11y.js` are
ported from the Ma11y tool. The live-site traces contain text from the public pages the agents visited.
