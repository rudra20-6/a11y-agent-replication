# Accessibility task report: https://www.icicibank.com/calculator/home-loan-emi-calculator

Model: mistral-small-3.2-24b-instruct. Pages explored: 0. Tasks: 1. Findings: 2.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Calculate the monthly EMI for a home loan of ₹50,00,000 with an interest rate of 8.5% and a tenure of 20 years.

Sighted reference user finished in 4 steps. Persona agents: P1: max_steps, P2: max_steps, P3: done.

- _Unconfirmed: the P1 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._
- **P2 · Get to it · 2.1.1** (step 0, blocks): input "": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: input "": can't be reached with the keyboard (Tab never lands on it)

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P1**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)
- **P3**: said done but ended in a different state than the sighted user (0% of what the task produced is on its screen; fields set differently: Amount, Interest Rate, rangeSliderVal)

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user