# Accessibility task report: https://www.indiapost.gov.in/

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 7.

**What the site lets users do:** Track shipment status using consignment or money order numbers, Locate post offices by pincode, state, or district, Calculate postage for letters and parcels, Download e-receipts for postal articles, View details of various banking and insurance schemes, Explore philately services and stamp collections, Access and view digital eBooks (Dak Samvaad), Learn about the DIGIPIN geo-coded addressing system

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Calculate the postage cost for a 250g letter being sent from Mumbai (400001) to Chennai (600001).

Sighted reference user finished in 6 steps. Persona agents: P1: done, P2: stuck, P3: done.

No barriers found for this task, but some parts did not run (see tool errors below).

- _Unconfirmed: the P2 agent did not finish (stuck: kept repeating the same actions with the same results (no progress)). No rule-based evidence, so this is not counted as a barrier; check it by hand._

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P2**: the persona could not finish the task (no rule-based evidence; agent: stuck: kept repeating the same actions with the same results (no progress))

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P1 step 2 (execute): Locator.click: Timeout 8000ms exceeded.
- P2 step 2 (execute): Locator.click: Timeout 8000ms exceeded.
- P3 step 2 (execute): Locator.click: Timeout 8000ms exceeded.

## Locate a post office in the Bangalore area by entering the pincode 560001 and completing the captcha verification.

Sighted reference user finished in 34 steps. Persona agents: P1: tool error, P2: max_steps, P3: done.

- **P1 · Notice the change · 4.1.2** (step 2, degrades): button "Search": its look changed (e.g. selected) but no state is exposed
- **P1 · Get to it · 4.1.2, 2.1.1** (step 7, blocks): a "": not exposed as a control a screen reader can activate
- **P2 · Get to it · 2.4.11** (step 1, degrades): input "Enter Captcha": focused control is hidden under Cookie Settings.
- **P2 · Get to it · 2.4.11** (step 3, degrades): svg[button] "": focused control is hidden under By clicking accept, you agree to the pol
- **P2 · Get to it · 2.1.1** (step 7, blocks): a "": can't be reached with the keyboard (Tab never lands on it)
- **P3 · Get to it · 1.4.10** (step 6, blocks): page: needs sideways scrolling at 400% zoom: 330 px of content in a 320 px window
- **P2 · Get to it · 2.1.1** (step 7, blocks) (agent stall, corroborated by a step check): task: task stalled: a "": can't be reached with the keyboard (Tab never lands on it)

Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it were not checked for that profile; after an agent error, that profile's agent did not finish its run because the model/API failed, so that profile was not tested by an agent):
- P2 step 7 (execute): Locator.click: Timeout 8000ms exceeded.
- P1 step 0 (agent): model call failed after 18 tries: 403 PERMISSION_DENIED. {'error': {'code': 403, 'message': 'Your API key was reported a

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user