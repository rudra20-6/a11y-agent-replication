# Accessibility task report: https://uidai.gov.in/en/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 1.

**What the site lets users do:** Access Aadhaar services including Download Aadhaar, Update Aadhaar, Check Aadhaar Status, Order PVC Card, Generate VID, and Retrieve Lost UID, View Aadhaar statistics and trends via the Aadhaar Dashboard, Download official documents, handbooks, circulars, and enrolment forms, Watch instructional videos for Aadhaar App services and use cases, Read frequently asked questions (FAQs) regarding Aadhaar services, Learn about UIDAI's vision, mission, and organizational structure

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Navigate to the Documents page and use the category selection to filter for 'Enrolment & Updates' to find specific official forms.

Sighted reference user finished in 5 steps. Persona agents: P1: done, P2: max_steps, P3: done.

- _Unconfirmed: the P2 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._
- **P1 · Notice the change · 4.1.3** (step 2, degrades): button "Apply": the page changed but a screen-reader user isn't told

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P2**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P3 step 2 (resolve): Locator.element_handle: Timeout 8000ms exceeded.

## Navigate to the Aadhaar Dashboard to view the monthly Aadhaar volumes and statistical trends across different sectors.

Sighted reference user finished in 1 steps. Persona agents: P1: done, P2: done, P3: done.

No barriers found for this task.


---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user