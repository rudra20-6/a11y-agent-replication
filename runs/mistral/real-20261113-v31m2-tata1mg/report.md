# Accessibility task report: https://www.1mg.com/

Model: mistral-small-3.2-24b-instruct. Pages explored: 0. Tasks: 4. Findings: 21.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Navigate to the Lab Tests page and select the 'Thyroid' category to view specific thyroid test packages.

Sighted reference user finished in 4 steps. Persona agents: P1: done, P2: stuck, P3: stuck.

- _Unconfirmed: the P3 agent did not finish (stuck: kept repeating the same actions with the same results (no progress)). No rule-based evidence, so this is not counted as a barrier; check it by hand._
- **P1 · Notice the change · 4.1.3** (step 2, degrades): div[button] "Thyroid": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.1.1** (step 0, blocks): div[button] "Thyroid": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: div[button] "Thyroid": can't be reached with the keyboard (Tab never lands on it)

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P3**: the persona could not finish the task (no rule-based evidence; agent: stuck: kept repeating the same actions with the same results (no progress))

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P2 step 0 (execute): Locator.click: Timeout 8000ms exceeded.
- P3 step 0 (resolve): Locator.element_handle: Timeout 8000ms exceeded.

## Open the 'All filters' dialog on the Sexual Wellness top picks page and select 'Condoms' to refine the results.

Sighted reference user finished in 6 steps. Persona agents: P1: stuck, P2: max_steps, P3: done.

- **P1 · Notice the change · 4.1.3** (step 0, degrades): div[button] "All filters": the page changed but a screen-reader user isn't told
- **P1 · Get to it · 4.1.2, 2.1.1** (step 1, blocks): div "Product Form": not exposed as a control a screen reader can activate
- **P1 · Know what it is · 2.4.6, 2.4.4** (step 2, degrades): input "Condom": 7 checkboxs share the name "checbox"
- **P2 · Get to it · 2.1.1** (step 1, blocks): div "Product Form": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.4.7** (step 2, blocks): input "Condom": keyboard focus is invisible on this control
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 612 px of content in a 320 px window
- **P1 · Get to it · 4.1.2, 2.1.1** (step 1, blocks) (agent stall, corroborated by a step check): task: task stalled: div "Product Form": not exposed as a control a screen reader can activate
- **P2 · Get to it · 2.4.7** (step 2, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Condom": keyboard focus is invisible on this control

## Navigate to the Lab Tests page, select the 'Full Body Packages' category, and click on the 'Comprehensive Gold Full Body Checkup' package to view its details.

_Not tested: reference agent could not complete the task (stuck: kept repeating the same actions with the same results (no progress))._

## Navigate to the Sexual Wellness category, open the 'All filters' dialog, and select 'Condoms' to filter the product list.

Sighted reference user finished in 27 steps. Persona agents: P1: max_steps, P2: stuck, P3: stuck.

- **P1 · Notice the change · 4.1.3** (step 0, degrades): div[button] "All filters": the page changed but a screen-reader user isn't told
- **P1 · Know what it is · 2.4.6, 2.4.4** (step 1, degrades): input "Durex": 14 checkboxs share the name "checbox"
- **P1 · Notice the change · 4.1.3** (step 5, degrades): div[button] "Sort": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.1.1** (step 1, blocks): input "Durex": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 3, blocks): button "": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 4, blocks): button "See all": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 612 px of content in a 320 px window
- **P1 · Notice the change · 4.1.3** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: div[button] "All filters": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.1.1** (step 1, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Durex": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: page: needs sideways scrolling at 400% zoom: 612 px of content in a 320 px window

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user