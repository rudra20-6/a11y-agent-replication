# Accessibility task report: https://www.passportindia.gov.in/

Model: mistral-small-3.2-24b-instruct. Pages explored: 0. Tasks: 2. Findings: 0.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Navigate to the Tatkaal Passport information page and find the heading 'Documents Required for Tatkaal Application'.

_Not tested: reference agent could not complete the task (max_steps: ran out of steps)._

## Browse through the latest news and circulars by using the pagination buttons to view different sets of updates. Click on button '2' and then button '3'.

_Not tested: reference agent could not complete the task (stuck: No numbered pagination buttons (e.g., '1', '2', '3') are visible on the page to click. Only year-based buttons (2021, 20)._

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user