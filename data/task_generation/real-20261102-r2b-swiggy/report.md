# Accessibility task report: https://www.swiggy.com/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 1. Findings: 9.

**What the site lets users do:** Search for restaurants and specific food items, Browse grocery categories through Instamart, Discover dining out options and restaurant details via Dineout, Filter restaurants by cuisine, rating, and dietary preferences, View restaurant menus, photos, and available offers, Access help, support, and corporate information

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Search for 'Korean Noodles' in the search bar and select a restaurant from the results to view its menu.

Sighted reference user finished in 7 steps. Persona agents: P1: done, P2: stuck, P3: max_steps.

- **P1 · Notice the change · 4.1.3** (step 2, degrades): a "Melt N Munch 4.1 (30) • 30-40 MINS": the page changed but a screen-reader user isn't told
- **P1 · Notice the change · 4.1.3** (step 3, degrades): button "View full menu": the page changed but a screen-reader user isn't told
- **P2 · Get to it · 2.4.7** (step 2, blocks): a "Melt N Munch 4.1 (30) • 30-40 MINS": keyboard focus is invisible on this control
- **P2 · Get to it · 2.4.7** (step 3, blocks): button "View full menu": keyboard focus is invisible on this control
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 1240 px of content in a 320 px window
- **P3 · Get to it · 1.4.10** (step 2, blocks): a "Melt N Munch 4.1 (30) • 30-40 MINS": control is outside the visible width at 400% zoom
- **P3 · Get to it · 1.4.10** (step 3, blocks): button "View full menu": control is outside the visible width at 400% zoom
- **P2 · Get to it · 2.4.7** (step 2, blocks) (agent stall, corroborated by a step check): task: task stalled: a "Melt N Munch 4.1 (30) • 30-40 MINS": keyboard focus is invisible on this control
- **P3 · Get to it · 1.4.10** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: page: needs sideways scrolling at 400% zoom: 1240 px of content in a 320 px window

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P1**: said done but ended in a different state than the sighted user (different page, 37% of what the task produced is there)

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user