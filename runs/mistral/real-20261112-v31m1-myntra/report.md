# Accessibility task report: https://www.myntra.com/

Model: mistral-small-3.2-24b-instruct. Pages explored: 0. Tasks: 1. Findings: 16.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Go to the Personal Care section and filter the results to show only 'Lipstick' from the brand 'Maybelline'.

Sighted reference user finished in 10 steps. Persona agents: P1: max_steps, P2: max_steps, P3: done.

- **P1 · Get to it · 4.1.2, 2.1.1** (step 0, blocks): input "Lipstick(22889)": not exposed as a control a screen reader can activate
- **P1 · Get to it · 4.1.2, 2.1.1** (step 1, blocks): input "lorshel(8967)": not exposed as a control a screen reader can activate
- **P1 · Get to it · 4.1.2, 2.1.1** (step 2, blocks): input "THE RUPAWAT Perfumery House(8248)": not exposed as a control a screen reader can activate
- **P1 · Get to it · 4.1.2, 2.1.1** (step 3, blocks): span "CLEAR ALL": not exposed as a control a screen reader can activate
- **P1 · Get to it · 4.1.2, 2.1.1** (step 4, blocks): span "": not exposed as a control a screen reader can activate
- **P1 · Notice the change · 4.1.3** (step 4, degrades): span "": the page changed but a screen-reader user isn't told
- **P1 · Get to it · 4.1.2, 2.1.1** (step 8, blocks): input "Lipstick(22852)": not exposed as a control a screen reader can activate
- **P1 · Notice the change · 4.1.3** (step 8, degrades): input "Lipstick(22852)": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.1.1** (step 0, blocks): input "Lipstick(22889)": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 1, blocks): input "": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 2, blocks): input "THE RUPAWAT Perfumery House(8248)": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 3, blocks): span "": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 8, blocks): input "Lipstick(22852)": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 980 px of content in a 320 px window
- **P1 · Get to it · 4.1.2, 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Lipstick(22889)": not exposed as a control a screen reader can activate
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Lipstick(22889)": can't be reached with the keyboard (Tab never lands on it)

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user