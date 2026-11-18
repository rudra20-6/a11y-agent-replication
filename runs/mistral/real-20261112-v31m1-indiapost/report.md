# Accessibility task report: https://www.indiapost.gov.in/

Model: mistral-small-3.2-24b-instruct. Pages explored: 0. Tasks: 3. Findings: 5.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Calculate the postage for a domestic letter weighing 250 grams from origin pincode 110001 to destination pincode 400001.

_Not tested: reference agent could not complete the task (max_steps: ran out of steps)._

## Calculate the postage cost for a 250g letter being sent from Mumbai (400001) to Chennai (600001).

Sighted reference user finished in 7 steps. Persona agents: P1: stuck, P2: max_steps, P3: stuck.

- _Unconfirmed: the P1 agent did not finish (stuck: kept repeating the same actions with the same results (no progress)). No rule-based evidence, so this is not counted as a barrier; check it by hand._
- **P2 · Get to it · 2.4.11** (step 2, degrades): input[combobox] "Origin Pincode or Location*": focused control is hidden under This website uses cookies to provide a b
- **P2 · Get to it · 2.4.11** (step 5, degrades): button "Calculate Postage": focused control is hidden under This website uses cookies to provide a b
- **P3 · Get to it · 1.4.10, 2.4.11** (step 3, blocks): input[combobox] "Destination Pincode or Location*": control is covered by another element at 400% zoom (320 px), so it can't be clicked
- **P2 · Get to it · 2.4.11** (step 5, blocks) (agent stall, corroborated by a step check): task: task stalled: button "Calculate Postage": focused control is hidden under This website uses cookies to provide a b
- **P3 · Get to it · 1.4.10, 2.4.11** (step 3, blocks) (agent stall, corroborated by a step check): task: task stalled: input[combobox] "Destination Pincode or Location*": control is covered by another element at 400% zoom (320 px), so it can't be clicked

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P1**: the persona could not finish the task (no rule-based evidence; agent: stuck: kept repeating the same actions with the same results (no progress))

## Locate a post office in the Bangalore area by entering the pincode 560001 and completing the captcha verification.

_Not tested: reference agent could not complete the task (max_steps: ran out of steps)._

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user