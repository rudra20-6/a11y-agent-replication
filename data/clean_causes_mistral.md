# Mistral Small 3.2 24B, clean application: cause of every kept report (11 Nov 2026)

Source: runs/full_bench_dev-20261111-{043607,063223,112309}.json, tested tasks only. 53 kept reports in 25 attempts.
Numbering (#) follows the dump order: run, task, agent, report. Each was checked against the trace, the step
screenshots (live/steps) and bench/app/app.js.

| Row | Cause | Agent | Reports (#) | Count |
|---|---|---|---|---|
| R1 | Focus moved to a new view's heading or to an error summary after a failed submission (recommended behaviour) | P2 | 7, 25, 26, 27, 28, 43, 44, 45, 46, 47 | 10 |
| R2 | Error caused by the agent's own input: wrong value despite the visible hint, or correction typed while focus was outside the field, then the unchanged value resubmitted | P1, P2, P3 | P2: 8, 9, 10, 11, 12, 29, 30, 48, 49, 50; P3: 13, 31; P1: 42 | 13 |
| R3 | Announcement reported as missing, although the focused element's name gave the date, fare or "(cheapest)", or errors were announced on submission as designed | P1 | 1, 2, 19, 32, 33, 22, 37; 40, 41 | 9 |
| R4 | Date-picker dialog that the agent itself had opened covered the search button | P3 | 3, 4, 5, 20, 21, 34, 35, 36 | 8 |
| R5 | The agent's own selection reported as an unrequested change, or as having no effect | P2, P3 | P2: 14, 15, 16, 51, 23, 38; P3: 17, 18, 52, 53 | 10 |
| TRUE | Passenger form re-rendered empty after "Change passenger details" (app.js, route /passenger; WCAG 2.2 SC 3.3.7 Redundant Entry) | P1, P3 | 6, 24, 39 | 3 |

False: 50 reports in 22 of 39 tested attempts (56%; 95% CI 41-71%); per run 6/12, 7/12, 9/15.
The 3 true reports are the only report in their attempts (r1 T3 P1, r2 T2 P3, r3 T2 P3).
#41 is a side effect of the TRUE defect (the form came back empty, so the resubmission raised errors) but its text
blames the error timing, which is as designed; counted false.
Harness note: for #23, #38 (combobox highlight) and #17, #18, #52, #53 (seat selected at 320 px) the step feedback said
"nothing visible changed" although the screenshot showed the change; the agent had the screenshot.
Gemma's 11 (runs 20261106-061351/062129/062938) contain no report of the TRUE defect: no Gemma agent went back to the form.
