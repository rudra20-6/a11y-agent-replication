# Accessibility task report: https://www.flipkart.com/

Model: gemma-4-26b-a4b-it. Pages explored: 0. Tasks: 3. Findings: 8.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Search for 'Running Shoes' using the search bar and browse the resulting product list.

Sighted reference user finished in 5 steps. Persona agents: P1: done, P2: stuck, P3: done.

- **P2 · Get to it · 2.4.7** (step 1, blocks): input "Search for Products, Brands and More": keyboard focus is invisible on this control
- **P2 · Get to it · 2.4.11** (step 1, degrades): input "Search for Products, Brands and More": focused control is hidden under ✕ Login Get access to your Orders, Wishl
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 343 px of content in a 320 px window
- **P2 · Get to it · 2.4.7** (step 1, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Search for Products, Brands and More": keyboard focus is invisible on this control

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P2 step 1 (execute): Locator.click: Timeout 8000ms exceeded.
- P3 step 1 (execute): Locator.click: Timeout 8000ms exceeded.

## Search for 'Gaming Laptops' using the search bar and browse the results.

Sighted reference user finished in 5 steps. Persona agents: P1: done, P2: max_steps, P3: done.

- **P1 · Get to it · 4.1.2, 2.1.1** (step 0, blocks): span "": not exposed as a control a screen reader can activate
- **P2 · Get to it · 2.1.1** (step 0, blocks): span "": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 343 px of content in a 320 px window
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: span "": can't be reached with the keyboard (Tab never lands on it)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P1 step 0 (execute): Locator.click: Timeout 8000ms exceeded.
- P2 step 0 (execute): Locator.click: Timeout 8000ms exceeded.
- P3 step 0 (execute): Locator.click: Timeout 8000ms exceeded.

## Navigate to the Fashion category and then select 'Casual shoes' to browse the collection.

_Not tested: reference agent could not complete the task (max_steps: ran out of steps)._

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user