# Accessibility task report: https://www.nhs.uk/health-assessment-tools/calculate-your-body-mass-index/calculate-bmi-for-adults

Model: gemma-4-26b-a4b-it. Pages explored: 0. Tasks: 3. Findings: 4.

**What the site lets users do:** 

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Use the search bar on the homepage to search for information about 'Diabetes'.

Sighted reference user finished in 3 steps. Persona agents: P1: done, P2: done, P3: done.

No barriers found for this task.


## Use the search bar on the homepage to search for 'diabetes', then select the first relevant search result to view its information.

Sighted reference user finished in 5 steps. Persona agents: P1: done, P2: done, P3: stuck.

No barriers found for this task.

- _Unconfirmed: the P3 agent did not finish (stuck: kept repeating the same actions with the same results (no progress)). No rule-based evidence, so this is not counted as a barrier; check it by hand._

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P1**: said done but ended in a different state than the sighted user (100% of what the task produced is on its screen; fields set differently: search-field)
- **P2**: said done but ended in a different state than the sighted user (100% of what the task produced is on its screen; fields set differently: search-field)
- **P3**: the persona could not finish the task (no rule-based evidence; agent: stuck: kept repeating the same actions with the same results (no progress))

## Navigate to the adult BMI calculator and confirm that you are 18 or over to reach the measurement input stage.

Sighted reference user finished in 12 steps. Persona agents: P1: done, P2: done, P3: max_steps.

- _Unconfirmed: the P3 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._
- **P1 · Notice the change · 4.1.2** (step 1, degrades): a[button] "": its look changed (e.g. selected) but no state is exposed
- **P1 · Notice the change · 4.1.2** (step 4, degrades): button "": its look changed (e.g. selected) but no state is exposed
- **P1 · Recover from errors · 3.3.1, 4.1.3** (step 5, blocks): button "": error appeared but not tied to the field (no aria-invalid / description)
- **P2 · Get to it · 2.1.1** (step 8, blocks): label "": can't be reached with the keyboard (Tab never lands on it)

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P1**: said done but ended in a different state than the sighted user (11% of what the task produced is on its screen)
- **P2**: said done but ended in a different state than the sighted user (15% of what the task produced is on its screen)
- **P3**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user