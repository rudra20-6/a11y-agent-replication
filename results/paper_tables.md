# Numbers recomputed from runs/gemma and runs/mistral (the paper runs)

## Gemma 4 26B A4B

### RQ1: instrumented application (detected/testable pairs)

| Barrier type | Run 1 | Run 2 | Run 3 | Single LLM | axe |
|---|---|---|---|---|---|
| Unrequested new window or reload | 7/8 | 8/8 | 8/9 | 2/8 | 0/8 |
| Control not usable by keyboard | 4/4 | 4/4 | 4/4 | 2/4 | 0/4 |
| Tab order changed | 1/2 | 0/2 | 1/1 | 1/2 | 2/2 |
| Focus indicator removed | 1/1 | 1/1 | 1/1 | 0/1 | 0/1 |
| All | 13/15 | 13/15 | 14/15 | 5/15 | 2/15 |

- detections by reports (rest by stalls): 8, 9, 9
- exact McNemar, method vs single LLM, per run: p = 0.0078, 0.0215, 0.0117
- missed pairs per run: [('MP_F36_T6', 'P3'), ('MP_F44_T5', 'P2')]; [('MP_F44_T5', 'P2'), ('MP_F44_T6', 'P2')]; [('MP_F36_T6', 'P2')]

### RQ2: clean application

- tested attempts with a false positive (kept report): 11/45 (24%; 95% CI 14%-39%); false findings: 11; reports of the real passenger-form barrier: 0
- the same count over all 63 attempts, untested tasks included: 11/63
- rule checks on the clean application: 0, 0, 0 violations per run
- cause of every report (manual review): data/clean_causes_*.md

### RQ2/RQ3: live sites (27 frozen tasks, two runs)

- tasks tested (reference agent completed): 21/27 and 23/27
- same outcome (completed or not) in both runs: 98% of 60 attempts (Cohen's kappa 0.97)
- findings: 44 and 53; tier A: 10 and 14 (from the focus check: 8 and 12)
- findings made in both runs for the same task and agent: 17
- by type, both runs: focus lost or moved 26; other 24; invisible keyboard focus 20; covers a control (400%) 14; new tab or reload 5; name or label 4; announcement or error 4
- made in both runs, by agent and type: P2 invisible keyboard focus 7; P3 covers a control (400%) 4; P1 focus lost or moved 2; P3 other 1; P1 new tab or reload 1; P1 other 1; P2 focus lost or moved 1
- Indian government: 33 findings in 13 tested tasks (2.5 per tested task), tier A 9
- Indian commerce, health and finance: 48 findings in 17 tested tasks (2.8 per tested task), tier A 15
- accessibility-focused (GOV.UK, NHS, Wikipedia): 16 findings in 14 tested tasks (1.1 per tested task), tier A 0

### Cost

- model calls: instrumented + clean 6,196, live 3,197 (together 9,393); single-LLM baseline 192

## Mistral Small 3.2 24B

### RQ1: instrumented application (detected/testable pairs)

| Barrier type | Run 1 | Run 2 | Run 3 | Single LLM | axe |
|---|---|---|---|---|---|
| Unrequested new window or reload | 9/9 | 9/9 | 8/9 | 0/9 | -- |
| Control not usable by keyboard | 4/4 | 4/4 | 4/4 | 0/4 | -- |
| Tab order changed | 1/1 | 1/1 | 1/1 | 0/1 | -- |
| Focus indicator removed | 1/1 | 1/1 | 1/1 | 0/1 | -- |
| All | 15/15 | 15/15 | 14/15 | 0/15 | -- |

-- : axe uses no model; its result is the same for both (shown for the first model).

- detections by reports (rest by stalls): 9, 10, 10
- exact McNemar, method vs single LLM, per run: p = 0.0001, 0.0001, 0.0001
- missed pairs per run: []; []; [('MP_F36_T6', 'P3')]

### RQ2: clean application

- tested attempts with a false positive (kept report): 22/39 (56%; 95% CI 41%-71%); false findings: 50; reports of the real passenger-form barrier: 3
- the same count over all 63 attempts, untested tasks included: 22/63
- rule checks on the clean application: 0, 0, 0 violations per run
- cause of every report (manual review): data/clean_causes_*.md

### RQ2/RQ3: live sites (27 frozen tasks, two runs)

- tasks tested (reference agent completed): 18/27 and 17/27
- same outcome (completed or not) in both runs: 93% of 45 attempts (Cohen's kappa 0.87)
- findings: 117 and 133; tier A: 4 and 18 (from the focus check: 0 and 10)
- findings made in both runs for the same task and agent: 18
- by type, both runs: other 148; name or label 27; covers a control (400%) 27; announcement or error 25; invisible keyboard focus 13; focus lost or moved 6; new tab or reload 4
- made in both runs, by agent and type: P3 covers a control (400%) 5; P1 announcement or error 3; P3 name or label 3; P2 other 3; P1 name or label 1; P3 new tab or reload 1; P1 other 1; P3 other 1
- Indian government: 50 findings in 7 tested tasks (7.1 per tested task), tier A 6
- Indian commerce, health and finance: 122 findings in 15 tested tasks (8.1 per tested task), tier A 16
- accessibility-focused (GOV.UK, NHS, Wikipedia): 78 findings in 13 tested tasks (6.0 per tested task), tier A 0

### Cost

- model calls: instrumented + clean 7,996, live 3,027 (together 11,023); single-LLM baseline 192

