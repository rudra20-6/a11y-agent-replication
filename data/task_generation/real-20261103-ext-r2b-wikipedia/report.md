# Accessibility task report: https://en.wikipedia.org/wiki/Main_Page

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 0.

**What the site lets users do:** search for encyclopedia articles, view and interact with media files, adjust page appearance including text size, width, and color mode, view revision history of pages, access site statistics

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Search for 'Sovetsky Soyuz class' using the search bar and then click on the image 'Sovietsky Soyuz 1 June 1942.jpg' to view its file details.

_Not tested: reference agent could not complete the task (stuck: kept repeating the same actions with the same results (no progress))._

## Change the text size to 'Large' and the color mode to 'Dark' using the appearance settings, then search for 'English language'.

_Not tested: reference agent could not complete the task (stuck: The controls for changing text size and color mode are visible in the screenshot but are not present in the VISIBLE CONT)._

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user