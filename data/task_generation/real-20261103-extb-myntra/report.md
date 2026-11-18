# Accessibility task report: https://www.myntra.com/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 1. Findings: 9.

**What the site lets users do:** Browse fashion categories for Men, Women, Kids, Home, and Beauty, Filter products by brand, category, price, color, and discount range, Search for specific brands like Nike, Tommy Hilfiger, or Titan, View product details and pricing, Navigate through specialized fashion feeds like Myntra Studio, Explore specific product sub-categories like Western Wear or Personal Care

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Navigate to the Women's Western Wear section, filter for the brand 'H&M', and browse for 'Tops' in the color 'White'.

Sighted reference user finished in 7 steps. Persona agents: P1: stuck, P2: max_steps, P3: max_steps.

- **P1 · Know what it is · 1.1.1** (step 0, degrades): image in main content: image has no text alternative
- **P1 · Know what it is · 2.4.6, 2.4.4** (step 0, degrades): a "": 2 links share the name "WOMEN"
- **P1 · Get to it · 4.1.2, 2.1.1** (step 1, blocks): a "": not exposed as a control a screen reader can activate
- **P2 · Get to it · 2.1.1** (step 1, blocks): a "": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 980 px of content in a 320 px window
- **P3 · Get to it · 1.4.10** (step 1, blocks): a "": control is outside the visible width at 400% zoom
- **P1 · Get to it · 4.1.2, 2.1.1** (step 1, blocks) (agent stall, corroborated by a step check): task: task stalled: a "": not exposed as a control a screen reader can activate
- **P2 · Get to it · 2.1.1** (step 1, blocks) (agent stall, corroborated by a step check): task: task stalled: a "": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: page: needs sideways scrolling at 400% zoom: 980 px of content in a 320 px window

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P1 step 1 (execute): Locator.click: Timeout 8000ms exceeded.
- P2 step 1 (execute): Locator.click: Timeout 8000ms exceeded.
- P3 step 1 (execute): Locator.click: Timeout 8000ms exceeded.

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user