# Accessibility task report: https://www.nhs.uk/health-assessment-tools/calculate-your-body-mass-index/calculate-bmi-for-adults

Model: gemma-4-26b-a4b-it. Pages explored: 15. Tasks: 2. Findings: 0.

**What the site lets users do:** Calculate BMI for adults and children/teenagers, Search for health conditions, symptoms, and medicines, Manage website cookie preferences, Browse health information via Health A to Z, Access information on mental health, healthy living, and social care

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Use the search bar on the homepage to search for 'diabetes', then select the first relevant search result to view its information.

Sighted reference user finished in 6 steps. Persona agents: P1: done, P2: done, P3: done.

No barriers found for this task.


## Navigate to the adult BMI calculator and confirm that you are 18 or over to reach the measurement input stage.

Sighted reference user finished in 4 steps. Persona agents: P1: done, P2: done, P3: max_steps.

No barriers found for this task.

- _Unconfirmed: the P3 agent did not finish (max_steps: ran out of steps). No rule-based evidence, so this is not counted as a barrier; check it by hand._

Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):
- **P3**: the persona could not finish the task (no rule-based evidence; agent: max_steps: ran out of steps)

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user