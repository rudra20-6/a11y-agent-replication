# Accessibility task report: https://www.indiapost.gov.in/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 1. Findings: 3.

**What the site lets users do:** Track consignment or money order status, Locate post offices by pincode, state, or district, Calculate postage for domestic and international mail, Download e-receipts, Access information on insurance and banking schemes, Explore philately and stamp services, View official documents and eBooks, View organizational structure and leadership details, View performance milestones and statistics

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Calculate the postage for a domestic letter weighing 250 grams from origin pincode 110001 to destination pincode 400001.

Sighted reference user finished in 8 steps. Persona agents: P1: done, P2: max_steps, P3: done.

- **P1 · Notice the change · 4.1.3** (step 5, degrades): button "Calculate Postage": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.4.11** (step 4, degrades): input "Weight (gms)*": focused control is hidden under By clicking accept, you agree to the pol
- **P2 · Get to it · 2.4.11** (step 4, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Weight (gms)*": focused control is hidden under By clicking accept, you agree to the pol

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user