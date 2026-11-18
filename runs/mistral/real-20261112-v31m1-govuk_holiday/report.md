# Accessibility task report: https://www.gov.uk/calculate-your-holiday-entitlement

Model: mistral-small-3.2-24b-instruct. Pages explored: 0. Tasks: 4. Findings: 0.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Start the holiday entitlement calculator and select 'Yes' to indicate that the employee works irregular hours.

Sighted reference user finished in 29 steps. Persona agents: P1: done, P2: stuck, P3: done.

No barriers found for this task.

- _Unconfirmed: the P2 agent did not finish (stuck: The cookie consent banner does not provide a keyboard-accessible way to dismiss it, trapping focus a). No rule-based evidence, so this is not counted as a barrier; check it by hand._

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P1**: said done but ended in a different state than the sighted user (21% of what the task produced is on its screen; fields set differently: response-0, response-1)
- **P2**: the persona could not finish the task (no rule-based evidence; agent: stuck: The cookie consent banner does not provide a keyboard-accessible way to dismiss it, trapping focus a)

## Search for 'National Insurance' using the search bar on the GOV.UK homepage.

Sighted reference user finished in 4 steps. Persona agents: P1: done, P2: max_steps, P3: done.

No barriers found for this task.

- _Unconfirmed: the P2 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P2**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)

## Calculate holiday entitlement for a standard employee by clicking 'Start now' and selecting 'No' to the question 'Does the employee work irregular hours or for part of the year?'

_Not tested: reference agent could not complete the task (stuck: No controls related to holiday entitlement calculation are visible on the current page.)._

## Search for 'maternity pay' using the search box on the GOV.UK homepage to find relevant guidance.

Sighted reference user finished in 3 steps. Persona agents: P1: done, P2: done, P3: done.

No barriers found for this task.


Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P1**: said done but ended in a different state than the sighted user (26% of what the task produced is on its screen)

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user