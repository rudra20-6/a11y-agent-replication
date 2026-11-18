# Accessibility task report: https://www.flipkart.com/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 6.

**What the site lets users do:** Search for products, brands, and more using a global search bar, Browse various product categories including Mobiles, Electronics, Fashion, Beauty, and Home, Search for flights and travel options including one-way and round-trip journeys, Access specialized brand stores and curated collections like 'Gaming Laptops' or 'Fashion'

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Search for a round-trip flight from Mumbai to Delhi departing on November 15, 2026, and returning on November 22, 2026.

_Not tested: reference agent could not complete the task (stuck: kept repeating the same actions with the same results (no progress))._

## Search for 'Running Shoes' using the search bar and browse the resulting product list.

Sighted reference user finished in 8 steps. Persona agents: P1: done, P2: stuck, P3: done.

- **P2 · Get to it · 2.1.1** (step 0, blocks): span[button] "✕": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.4.7** (step 1, blocks): input "Search for Products, Brands and More": keyboard focus is invisible on this control
- **P2 · Get to it · 2.1.1** (step 2, blocks): button "": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 0, blocks): page: needs sideways scrolling at 400% zoom: 401 px of content in a 320 px window
- **P3 · Get to it · 1.4.10** (step 0, blocks): span[button] "✕": control is outside the visible width at 400% zoom
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: span[button] "✕": can't be reached with the keyboard (Tab never lands on it)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P3 step 0 (execute): Locator.click: Timeout 8000ms exceeded.

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user