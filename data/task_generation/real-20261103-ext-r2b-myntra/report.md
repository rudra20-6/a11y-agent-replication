# Accessibility task report: https://www.myntra.com/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 8.

**What the site lets users do:** filtering products, navigating categories, browsing product grids

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Navigate to the Men's fashion store and filter the products to show only the brand 'Roadster' in the color 'Black'.

_Not tested: reference agent could not complete the task (stuck: kept repeating the same actions with the same results (no progress))._

## Go to the Personal Care section and filter the results to show only 'Lipstick' from the brand 'Maybelline'.

Sighted reference user finished in 16 steps. Persona agents: P1: stuck, P2: max_steps, P3: done.

- **P1 · Get to it · 4.1.2, 2.1.1** (step 0, blocks): input "Lipstick(19980)": not exposed as a control a screen reader can activate
- **P1 · Notice the change · 4.1.3** (step 0, degrades): input "Lipstick(19980)": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.1.1** (step 0, blocks): input "Lipstick(19980)": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 1, blocks): a "Maybelline Lipstick": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 980 px of content in a 320 px window
- **P3 · Get to it · 1.4.10** (step 1, blocks): a "Maybelline Lipstick": control is outside the visible width at 400% zoom
- **P1 · Get to it · 4.1.2, 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Lipstick(19980)": not exposed as a control a screen reader can activate
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: input "Lipstick(19980)": can't be reached with the keyboard (Tab never lands on it)

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P3**: said done but ended in a different state than the sighted user (different page, 42% of what the task produced is there)

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user