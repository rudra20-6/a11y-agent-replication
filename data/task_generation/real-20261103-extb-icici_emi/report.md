# Accessibility task report: https://www.icicibank.com/calculator/home-loan-emi-calculator

Model: gemma-4-26b-a4b-it. Pages explored: 1. Tasks: 2. Findings: 2.

**What the site lets users do:** Calculate Home Loan EMI, Adjust loan amount and interest rate using sliders or text inputs, View detailed amortization schedules, Access accessibility settings, Navigate to related loan tools like eligibility and prepayment calculators

**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at every step of the sighted path, rule checks ask, for each persona:

- **Get to it** (Reach): can this persona get to the control the next step needs?
- **Know what it is** (Identify): can they tell what the control is and what state it's in?
- **Use it** (Operate): does it work with their way of interacting?
- **Notice the change** (Notice): are they told, or can they see, what changed?
- **Recover from errors** (Recover): can they find, understand and fix a mistake?

A persona agent that gets stuck counts as a barrier only when a step check backs it up.

## Calculate the monthly EMI for a home loan of ₹50,00,000 with an interest rate of 8.5% and a tenure of 20 years.

Sighted reference user finished in 8 steps. Persona agents: P1: done, P2: max_steps, P3: done.

- **P2 · Get to it · 2.1.1** (step 0, blocks): input "": can't be reached with the keyboard (Tab never lands on it)
- **P2 · Get to it · 2.1.1** (step 0, blocks) (agent stall, corroborated by a step check): task: task stalled: input "": can't be reached with the keyboard (Tab never lands on it)

## Set a loan amount of ₹75,00,000 at a 9% interest rate for 15 years and click on 'VIEW AMORTIZATION SCHEDULE' to see the repayment breakdown.

_Not tested: reference agent could not complete the task (stuck: The '15 Years' duration button is visible in the screenshot but is not listed in the visible controls, so I cannot inter)._

---
P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user