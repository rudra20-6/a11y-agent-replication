# Accessibility task report: https://www.passportindia.gov.in/

Model: gemma-4-26b-a4b-it. Pages explored: 0. Tasks: 2. Findings: 4.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Navigate to the Tatkaal Passport information page and find the heading 'Documents Required for Tatkaal Application'.

Sighted reference user finished in 11 steps. Persona agents: P1: max_steps, P2: max_steps, P3: max_steps.

- _Unconfirmed: the P3 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._
- **P1 · Know what it is · 4.1.2, 1.3.1** (step 1, blocks): input "Search": control has no accessible name
- **P2 · Get to it · 2.4.7** (step 5, blocks): a "Tatkaal Passports": keyboard focus is invisible on this control
- **P1 · Know what it is · 4.1.2, 1.3.1** (step 1, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Search": control has no accessible name
- **P2 · Get to it · 2.4.7** (step 5, blocks) (agent stall, corroborated by a step check): task: task stalled: a "Tatkaal Passports": keyboard focus is invisible on this control

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P3**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P3 step 1 (execute): Locator.click: Timeout 8000ms exceeded.

## Browse through the latest news and circulars by using the pagination buttons to view different sets of updates. Click on button '2' and then button '3'.

_Not tested: reference agent could not complete the task (max_steps: ran out of steps)._

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user