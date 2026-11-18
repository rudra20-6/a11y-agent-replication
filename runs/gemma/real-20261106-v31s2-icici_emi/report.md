# Accessibility task report: https://www.icicibank.com/calculator/home-loan-emi-calculator

Model: gemma-4-26b-a4b-it. Pages explored: 0. Tasks: 1. Findings: 7.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Calculate the monthly EMI for a home loan of ₹50,00,000 with an interest rate of 8.5% and a tenure of 20 years.

Sighted reference user finished in 17 steps. Persona agents: P1: max_steps, P2: max_steps, P3: done.

- **P1 · Notice the change · 4.1.3** (step 3, degrades): button "VIEW AMORTIZATION SCHEDULE": the page changed but a screen-reader user isn't told
- **P1 · Notice the change · 4.1.3** (step 4, degrades): button "": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.1.1** (step 0, blocks): input "": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 5, blocks): button "": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 4, blocks): button "": control is outside the visible width at 400% zoom
- **P1 · Notice the change · 4.1.3** (step 3, blocks) (agent stall, corroborated by a step check): task: task stalled: button "VIEW AMORTIZATION SCHEDULE": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: input "": can't be reached with the keyboard (Tab never lands on it)

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P3**: said done but ended in a different state than the sighted user (0% of what the task produced is on its screen; fields set differently: Interest Rate, rangeSliderVal)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P1 step 12 (resolve): Locator.element_handle: Timeout 8000ms exceeded.
- P2 step 12 (resolve): Locator.element_handle: Timeout 8000ms exceeded.
- P3 step 11 (execute): Locator.click: Timeout 8000ms exceeded.

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user