"""The prompts of the constrained agents P1, P2 and P3 (method v3.1), taken from the code itself (a11y_agent/navigator.py
and personas.yaml), so the PDF shows exactly what the model receives. Renders HTML to PDF with headless Chrome.
Usage: python experiments/export_prompts.py [out.pdf]   (default: agent_prompts.pdf in the repository root)
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from a11y_agent.navigator import PROFILE_RULES, SYSTEM, Navigator  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "agent_prompts.pdf"
NAMES = {"P1": "P1, no vision (screen reader)", "P2": "P2, limited fine motor control (keyboard only)",
         "P3": "P3, low vision (400% zoom)"}
OBS = {"P1": "the accessibility tree (roles, names, states, values, each control with a ref ax:N), where focus is, and "
             "what was announced since the last action. No screenshot.",
       "P2": "a screenshot, the visible text, and the visible controls with their visible state; the focused element "
             "only when the page draws a visible focus indicator.",
       "P3": "a screenshot 320 CSS px wide, the text in view, and the controls fully inside the visible width (refs el:N)."}


def block(title, text, note=""):
    n = f'<p class="note">{html.escape(note)}</p>' if note else ""
    return f"<h3>{html.escape(title)}</h3>{n}<pre>{html.escape(text)}</pre>"


def ph(s):   # placeholders filled in at run time
    return f"«{s}»"


parts = ["<h1>Prompts of the constrained agents P1, P2 and P3</h1>",
         "<p>Text in «guillemets» is filled in at run time. The harness, not the prompt, enforces what each agent perceives "
         "and which actions it can take; the prompt describes them and adds the strategies of an experienced user. "
         "Every call asks for one JSON object (JSON output mode, temperature 0).</p>",
         block("System message, common to all three personas (P1, P2, P3), sent with every step", SYSTEM)]

for p in ("P1", "P2", "P3"):
    step = (f"{PROFILE_RULES[p]}\n\nTASK: {ph('task goal')}\n\nYOUR PREVIOUS ACTIONS:\n"
            f"{ph('the last 10 steps: number, action as JSON -> what happened [you reported: ...]')}\n\n"
            f"CURRENT OBSERVATION:\n{ph('observation, see above')}\n\n"
            f"{ph('no-progress note, only when the last actions repeat with the same results')}What is your next action?")
    parts.append(f'<section><h2>{html.escape(NAMES[p])}</h2>')
    parts.append(f'<p class="note"><b>Observation</b> («observation» below): {html.escape(OBS[p])}</p>')
    parts.append(block("User message (every step)", step))
    parts.append("</section>")

done_check = (f"{ph('the agent block of P1, P2 or P3, as above')}\n\nTASK: {ph('task goal')}\n\nCURRENT OBSERVATION:\n"
              f"{ph('observation')}\n\nYou said you are done (answer: {ph('answer')}). Before finishing, compare what the "
              "page shows now with every value and step the task asks for. If all of it is reflected, reply with done "
              "again. If not, reply with your next action.")
no_progress = ("NOTE: your recent actions keep repeating with the same results, so they are not getting you anywhere. "
               "If the task is already complete, reply with done. Otherwise try a different approach.")
debrief = (f"{ph('the agent block of P1, P2 or P3, as above')}\n\nTASK: {ph('task goal')}\n\nYOUR STEPS:\n"
           f"{ph('every step: number, action as JSON -> what happened [you reported: ...]')}\n\n"
           + Navigator.DEBRIEF.format(status=ph("done / stuck / max_steps, with the reason")))
parts.append('<section><h2>Shared by all three agents</h2>')
parts.append(block("No-progress note (inserted into the step message)", no_progress,
                   "Added before \"What is your next action?\" when the recent actions repeat with the same results."))
parts.append(block("Done check (user message; with the common system message)", done_check,
                   "Sent once, the first time the agent replies \"done\"."))
parts.append(block("Debrief, system message", Navigator.DEBRIEF_SYSTEM, "Sent once after the task ends."))
parts.append(block("Debrief, user message", debrief))
parts.append("</section>")

css = """@page{size:A4 landscape;margin:11mm 13mm}
body{font-family:'Segoe UI',Arial,sans-serif;font-size:10pt;color:#111;line-height:1.35}
h1{font-size:16pt;margin:0 0 6px} h2{font-size:13pt;margin:18px 0 4px;border-bottom:1.5px solid #333;padding-bottom:2px}
h3{font-size:10.5pt;margin:10px 0 3px} p{margin:4px 0} .note{color:#444;font-size:9pt}
pre{font-family:Consolas,'Courier New',monospace;font-size:7.6pt;line-height:1.25;white-space:pre-wrap;word-wrap:break-word;
    background:#f4f4f4;border:1px solid #ccc;border-radius:3px;padding:6px 8px;margin:2px 0 6px}
section{break-before:page} code{font-size:9pt}"""
page = OUT.with_suffix(".html")
page.write_text(f"<html><head><meta charset='utf-8'><title>Agent prompts</title><style>{css}</style></head>"
                f"<body>{''.join(parts)}</body></html>", encoding="utf-8")
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page()
    pg.goto(page.as_uri())
    pg.pdf(path=str(OUT), format="A4", landscape=True, print_background=True, display_header_footer=True, header_template="<span></span>",
           footer_template="<div style='font-size:8px;width:100%;text-align:center'><span class='pageNumber'></span></div>")
    b.close()
page.unlink()
print("wrote", OUT)
