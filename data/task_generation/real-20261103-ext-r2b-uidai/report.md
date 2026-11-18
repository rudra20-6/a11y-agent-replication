# Accessibility task report: https://uidai.gov.in/en/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 4.

**What the site lets users do:** Access Aadhaar services such as downloading Aadhaar, checking update status, and ordering PVC cards, Locate Aadhaar Enrolment Centres and Seva Kendras, Browse official documents, circulars, handbooks, and legal notifications, Watch instructional how-to videos for various Aadhaar applications, View real-time Aadhaar statistics and trends through the Aadhaar Dashboard, Search for answers to common queries in the FAQ section

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Use the document filters to find 'Circulars' published on December 15, 2026.

_Not tested: reference agent could not complete the task (max_steps: ran out of steps)._

## Navigate through the 'How to Videos' section using the pagination links to view the second page of tutorials.

Sighted reference user finished in 3 steps. Persona agents: P1: done, P2: stuck, P3: done.

- **P1 · Notice the change · 4.1.3** (step 0, degrades): a "2": the page changed but a screen-reader user isn't told
- **P1 · Notice the change · 4.1.2** (step 0, degrades): a "2": its look changed (e.g. selected) but no state is exposed
- **P2 · Get to it · 2.4.7** (step 0, blocks): a "2": keyboard focus is invisible on this control
- **P2 · Get to it · 2.4.7** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: a "2": keyboard focus is invisible on this control

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user