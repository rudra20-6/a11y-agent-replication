# Accessibility task report: https://www.gov.uk/calculate-your-holiday-entitlement

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 0.

**What the site lets users do:** Calculate statutory holiday entitlement, Search for government services and information, Manage cookie preferences, Browse employment and benefits information

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Calculate holiday entitlement for a standard employee by clicking 'Start now' and selecting 'No' to the question 'Does the employee work irregular hours or for part of the year?'

Sighted reference user finished in 10 steps. Persona agents: P1: done, P2: max_steps, P3: done.

No barriers found for this task.

- _Unconfirmed: the P2 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P2**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)

## Search for 'maternity pay' using the search box on the GOV.UK homepage to find relevant guidance.

Sighted reference user finished in 8 steps. Persona agents: P1: done, P2: done, P3: done.

No barriers found for this task, but some parts did not run (see tool errors below).


Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P2**: said done but ended in a different state than the sighted user (different page, 52% of what the task produced is there)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P1 step 0 (resolve): Locator.element_handle: Timeout 8000ms exceeded.
- P2 step 0 (resolve): Locator.element_handle: Timeout 8000ms exceeded.
- P3 step 0 (resolve): Locator.element_handle: Timeout 8000ms exceeded.

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user