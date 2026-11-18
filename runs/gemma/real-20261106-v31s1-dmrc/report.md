# Accessibility task report: https://www.delhimetrorail.com/

Model: gemma-4-26b-a4b-it. Pages explored: 0. Tasks: 1. Findings: 4.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Use the search bar to find information about 'lost and found' services.

Sighted reference user finished in 8 steps. Persona agents: P1: done, P2: stuck, P3: max_steps.

- _Unconfirmed: the P3 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._
- **P1 · Notice the change · 4.1.3** (step 4, degrades): button "": the page changed but a screen-reader user isn't told
- **P1 · Notice the change · 4.1.3** (step 6, degrades): button "खोया और पाया": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.4.7** (step 2, blocks): a "खोया - पाया": keyboard focus is invisible on this control
- **P2 · Get to it · 2.4.7** (step 2, blocks) (agent stall, corroborated by a step check): task: task stalled: a "खोया - पाया": keyboard focus is invisible on this control

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P3**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P3 step 3 (execute): Locator.click: Timeout 8000ms exceeded.

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user