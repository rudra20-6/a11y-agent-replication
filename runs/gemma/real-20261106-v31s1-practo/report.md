# Accessibility task report: https://www.practo.com/hyderabad/dentist

Model: gemma-4-26b-a4b-it. Pages explored: 0. Tasks: 1. Findings: 9.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Filter the list of dentists in Hyderabad to show only female doctors with 10+ years of experience.

Sighted reference user finished in 7 steps. Persona agents: P1: stuck, P2: stuck, P3: max_steps.

- **P2 · Use it · 2.1.1** (step 0, blocks): li[option] "": ArrowDown does nothing inside this widget
- **P1 · Use it · 2.1.1** (step 0, blocks): li[option] "": ArrowDown does nothing inside this widget
- **P2 · Use it · 2.1.1** (step 1, blocks): li[option] "Female Doctor": ArrowDown does nothing inside this widget
- **P1 · Use it · 2.1.1** (step 1, blocks): li[option] "Female Doctor": ArrowDown does nothing inside this widget
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 1200 px of content in a 320 px window
- **P3 · Get to it · 1.4.10** (step 3, blocks): li[option] "": control is outside the visible width at 400% zoom
- **P1 · Use it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: li[option] "": ArrowDown does nothing inside this widget
- **P2 · Use it · 2.1.1** (step 1, blocks) (agent stall, corroborated by a step check): task: task stalled: li[option] "Female Doctor": ArrowDown does nothing inside this widget
- **P3 · Get to it · 1.4.10** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: page: needs sideways scrolling at 400% zoom: 1200 px of content in a 320 px window

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P2 step 4 (check): ElementHandle.evaluate: Execution context was destroyed, most likely because of a navigation
- P3 step 4 (resolve): ElementHandle.evaluate_handle: Execution context was destroyed, most likely because of a navigation

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user