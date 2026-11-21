# Gemma 4 26B A4B, clean application: cause of every kept report (6 Nov 2026)

Source: runs/gemma/full_bench_dev-20261106-{061351,062129,062938}.json, tested tasks only (T1, T2, T3, T4 and T6 in
every run; the reference agent did not complete T5 and T7). 11 kept reports in 11 attempts, all Tier B.
Numbering (#) follows the dump order: run, task, agent, report. Each was checked against the agent's step trace and the
task definition in bench/tasks/benchbook.yaml.

| Row | Cause | Agent | Reports (#) | Count |
|---|---|---|---|---|
| R1 | Focus moved to the start of the new view's content after a page change (recommended behaviour) | P2 | 1, 4, 7, 8, 11 | 5 |
| R2 | Error caused by the agent's own input: the mobile number "98765 4321" is rejected, as the task expects | P3 | 2, 5, 9 | 3 |
| R3 | Announcement reported as unexpected, although the calculator announces its results when a field changes, as designed | P1 | 3, 10 | 2 |
| R4 | Date-picker dialog that the agent itself had opened covered a control | P3 | - | 0 |
| R5 | The agent's own selection reported as an unrequested change, or as having no effect | P2, P3 | - | 0 |
| R6 | Focus reported as invisible before any key was pressed | P2 | 6 | 1 |
| TRUE | Passenger form re-rendered empty after "Change passenger details" | - | - | 0 |

False: 11 reports in 11 of 45 tested attempts (24%; 95% CI 14-39%); per run 4/15, 3/15, 4/15.
Rows R1-R5 are the rows of the paper's Table III; R6 is its last row.

## The reports

| # | Run | Task | Agent | Step | Report (abridged) | Row |
|---|---|---|---|---|---|---|
| 1 | 061351 | T3 passenger details | P2 | 9 | After Enter, focus jumped to the start of the page content; the review screen does not show the email or mobile number | R1 |
| 2 | 061351 | T3 passenger details | P3 | 3 | The error "Enter a 10-digit mobile number" appeared without a clear notification or focus shift | R2 |
| 3 | 061351 | T4 SIP calculator | P1 | 3 | The results were announced as soon as focus moved to the next field | R3 |
| 4 | 061351 | T6 shop pincode | P2 | 11 | After Enter on the link, focus jumped to the start of the page content | R1 |
| 5 | 062129 | T3 passenger details | P3 | 3 | The error "Enter a 10-digit mobile number" was hard to associate with the field | R2 |
| 6 | 062129 | T4 SIP calculator | P2 | 0 | "I cannot see where the keyboard focus is" | R6 |
| 7 | 062129 | T6 shop pincode | P2 | 8 | After Enter on the link, focus jumped to the start of the page content | R1 |
| 8 | 062938 | T3 passenger details | P2 | 9 | After Enter, focus jumped to the start of the page content; the review page does not show the email or mobile number | R1 |
| 9 | 062938 | T3 passenger details | P3 | 3 | The error "Enter a 10-digit mobile number" was not clearly associated with the field | R2 |
| 10 | 062938 | T4 SIP calculator | P1 | 3 | The results were announced on moving focus to "Expected return rate", before the rate was entered | R3 |
| 11 | 062938 | T6 shop pincode | P2 | 12 | After Enter on the link, focus jumped to the start of the content | R1 |

## Notes

- R1: at the reported step, the harness feedback was "no control has focus (the page moved focus to the start of its
  content)". BenchBook moves focus to the new view's heading on every page change, which is the recommended pattern.
  #1 and #8 also say the review page omits the email and mobile number; the review page shows only the name by design,
  which is not a barrier.
- R2: the task asks for "98765 4321" first and, if it is rejected, a correction to 9876543210. P3 typed the first
  number (step 2) and clicked Continue (step 3); the error is the expected response to that input.
- R3: the result announced at step 3 ("Invested amount ... Total value ...") is the calculator's live region, which
  updates when a field changes, as designed.
- R6: the step-0 action was not carried out ("not allowed for this profile: Tab", a wrong action type), so no key had
  been pressed when P2 made the report. The focus check did not run (`focus_px` is empty), so the report stayed Tier B.
- No Gemma agent went back to the passenger form, so none met the clean application's one real barrier (see
  clean_causes_mistral.md, row TRUE).
