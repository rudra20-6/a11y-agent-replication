"""End-to-end: URL -> planner and validator -> reference run -> rule checks + persona agents (in parallel) -> end-state
check and stall judge -> report verifier -> report.

  1. Rule findings on the reference path carry their own evidence.
  2. A persona agent that does not finish while the reference did is first compared with the reference's end state. If
     it did not reach it, a rule finding for that persona is listed with the stall; otherwise the judge model labels the
     likely cause, and the stall is kept as Tier B agent evidence.
  3. Each problem a persona reported is checked against its own trace by the verifier and the trace filters.

Writes into the run directory: meta.json (status), events.jsonl (live), plan.json, results.json (updated after
every task), report.md (at the end).
"""

from __future__ import annotations

import json
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from .browser import BrowserPool, Viewport
from .checker import PROFILES, Finding, PathChecker, findings_to_dicts, select
from .config import RUNS, SETTINGS
from .events import NULL, EventLog
from . import llm as llmlib
from .llm import FALLBACKS, LLM, USAGE
from .navigator import Navigator, Outcome, effort, form_fields
from .planner import Plan, plan

JUDGE_SYSTEM = """You review accessibility test runs. A reference agent (sighted mouse user) completed a task. An agent
limited to one disability profile did not. Decide whether the failure is caused by the website (an accessibility barrier
for that profile) or by the agent (a mistake a competent user of that technology would not make). Be strict: call it a
barrier only if the observations show the site gave that user no workable way forward. Reply with ONE JSON object:
{"verdict": "barrier"|"agent_error", "step": <int>, "check": "Reach"|"Identify"|"Operate"|"Notice"|"Recover",
 "sc": "<WCAG SC or 'no SC'>", "explanation": "<one sentence a developer can act on>"}"""

# Step limits per agent. P1 and P2 get 35, like the reference agent: they move through a page one key press at a time,
# so a task takes them many more steps. P3 gets 25: it clicks controls directly, like the reference agent, and needs
# fewer steps than the keyboard-only agents. These are the limits used in every run in runs/ (see agent_start in
# events.jsonl).
AGENT_STEPS = {"P1": 35, "P2": 35, "P3": 25, "REF": 35}

# Problems a persona reported are checked against its own trace before they become findings.
VERIFY_SYSTEM = """You check problem reports from an accessibility test agent that used a website as one kind of user.
For each report you get the step where it was made: the agent's previous action, what the website gave back, what the
agent perceived, and its thinking. Decide whether the report describes something the WEBSITE did that makes the task
harder for a real person of that kind ("site"), or whether it is the agent's own mistake, a misunderstanding, a matter
of taste, or something the evidence does not show ("not_site"). Be strict: "site" needs the evidence to show it, and you
must be able to name the WCAG 2.2 success criterion the site fails there.
These are NOT site problems ("not_site"):
- the consequence of the agent's own wrong or incomplete input or action: an error message, an alert, a field left
  empty, a suggestion not picked. The site reporting an error the user made is the site working;
- recommended accessible behaviour: moving focus to an error message or error summary after a failed submit, moving
  focus to content the user asked for (a dialog, a new view, results), arrow keys inside a grid, list or radio group,
  Tab moving through a form in order;
- Enter in a text field, or in a combobox with no suggestion highlighted, submitting the form (and the form then
  reporting what is missing): that is standard behaviour; a suggestion is picked by highlighting it first;
- after a page or view change, no control having focus yet;
- effort that is normal for this way of using a page (tabbing past a few links, arrowing through a calendar);
- anything the evidence at this step contradicts (for example "I can't see focus" when what came back says focus is
  visibly on a control).
Things that ARE site problems when the evidence shows them include: a new tab or window, a reload or a move to another
page that the user did not ask for (after typing, choosing an option or moving focus); a control or text whose name,
label or reading makes no sense to this user; focus that is invisible or lands somewhere that makes no sense; a control
this user cannot reach or operate; content this user cannot perceive.
Reply with ONE JSON object: {"reports": [{"n": <report number>, "verdict": "site"|"not_site",
"check": "Reach"|"Identify"|"Operate"|"Notice"|"Recover", "sc": "<WCAG SC or 'no SC'>",
"explanation": "<one sentence a developer can act on>"}]}"""
MAX_REPORTS = 8   # per persona run; more than this is noise, and keeps the verifier prompt small


def reported_problems(out: Outcome) -> list[dict]:
    """The problems a persona reported while acting (on a step) and in its debrief after the task (citing a step), with
    the evidence of that step: its action and result, the previous action and result, what the persona perceived and
    thought there. Repeats of the same text are dropped."""
    seen, found = set(), []
    by_i = {s.i: k for k, s in enumerate(out.steps)}
    items = [(s.i, s.problem, "during") for s in out.steps if s.problem] + \
            [(d["step"], d["problem"], "debrief") for d in (out.debrief or []) if d.get("step") in by_i]
    for i, problem, when in items:
        key = re.sub(r"\W+", " ", problem.lower()).strip()[:60]
        if key in seen:
            continue
        seen.add(key)
        k = by_i[i]
        st, prev = out.steps[k], (out.steps[k - 1] if k else None)
        on = lambda x: f" (on {x.target})" if x and x.target else ""
        found.append({"step": i, "problem": problem, "when": when, "thought": st.thought,
                      "action": json.dumps(st.action) + on(st), "result": st.result,
                      "prev_action": (json.dumps(prev.action) + on(prev)) if prev else None, "prev_result": prev.result if prev else "",
                      "observation": st.observation[:1500],
                      "focus_px": [x.focus_px for x in (st, prev) if x is not None and getattr(x, "focus_px", None)]})
    return found[:MAX_REPORTS]


def own_submit(r: dict) -> bool:
    """A check on the agent, not the site: the report is about an error that appeared when the agent pressed Enter
    straight after typing, with no arrow key to highlight a suggestion. That submits the form, and the form saying what
    is missing is the site working."""
    a, prev = str(r.get("action") or ""), str(r.get("prev_action") or "")
    erred = re.search(r"\b(alert|error|there is a problem|invalid|required)\b", (r.get("result") or "").lower())
    return a.startswith('{"type": "press", "key": "Enter"}') and prev.startswith('{"type": "type"') and bool(erred)


FOCUS_REPORT = re.compile(r"(can.?t|cannot|could not|not|no)\b.{0,30}\b(see|visible|tell)\b.{0,40}focus|focus\b.{0,30}\b"
                          r"(invisible|not visible|disappear|hidden)|where (the )?(keyboard )?focus (is|went)|focus indicator",
                          re.I)


def own_mistake(r: dict) -> str | None:
    """Trace filters: checks on the agent, not the site, from its own steps. Returns the reason, or None."""
    a, prev = str(r.get("action") or ""), str(r.get("prev_action") or "")
    res, pres, prob = (r.get("result") or "").lower(), (r.get("prev_result") or "").lower(), r.get("problem", "").lower()
    alert = re.compile(r"\b(alert|error|there is a problem|invalid|required)\b")
    if own_submit(r):
        return ("the agent's own action: Enter straight after typing submits the form (no suggestion highlighted), and "
                "the form reported what was missing")
    # typing while focus was not in a text field (on an alert, a link, a slider, a button...)
    if (a.startswith('{"type": "type"')
            and re.search(r"focus( now visibly on)?: (alert|link|button|slider|checkbox|radio|dropdown|heading|gridcell|page)"
                          r"|no control has focus", pres)
            and re.search(r"(typ|text|field|value|appear)", prob)):
        return "the agent typed while focus was not in a text field"
    # typing into a field that already had a value, without clearing it, and blaming the result
    m = re.search(r'the field now contains "([^"]*)"', res)
    typed = re.search(r'"text": "([^"]*)"', a)
    if m and typed and m.group(1) != typed.group(1) and m.group(1).endswith(typed.group(1)):
        return "the agent typed into a field that already had a value without clearing it first"
    # focus moving to an error message or summary after the agent's own failed submit: recommended behaviour
    if ((re.search(r"focus\b.{0,40}\b(jump|mov|went|stuck|land)", prob) or re.search(r"\b(took|takes|grabbed|stole)\b.{0,10}focus", prob))
            and re.search(r"(alert|error|problem)", prob) and (alert.search(res) or alert.search(pres))):
        return "moving focus to an error message after a failed submit is the recommended pattern"
    # the agent typed into something that is not a field (a hint, a label's text), and the tool said so
    if (a.startswith('{"type": "type"') and re.search(r"(not an? (input|text field|field)|isn.?t a (text )?field|can.?t (receive|take) text"
                                                      r"|not .{0,20}(input|field).{0,30}(type|typing))", prob)
            and re.search(r"(can.?t|cannot|not|error|no such)", res[:120])):
        return "the agent tried to type into an element that is not a field; the tool told it so"
    # an error or alert the agent's own submit caused, reported as appearing 'immediately' or 'instead of'
    submit_like = re.compile(r'"type": "(press", "key": "enter|activate|click)')
    if (re.search(r"(alert|error|there is a problem)", prob) and re.search(r"(immediately|before i|instead of|unexpected)", prob)
            and ((submit_like.search(a.lower()) and alert.search(res)) or (submit_like.search(prev.lower()) and alert.search(pres)))):
        return "the error appeared because the agent submitted the form before filling it in"
    # a date picker or calendar the agent itself opened covering the page
    if re.search(r"cover|obscur|overlay", prob) and re.search(r"date ?picker|calendar", prob):
        return "a date picker the agent opened covers the page while it is open: normal behaviour"
    return None


def tool_focus_check(r: dict) -> str | None:
    """For a keyboard persona's report that focus can't be seen, the pixel check made at that step (or the
    one before): 'invisible' confirms it, 'visible' contradicts it. None when not checked or not such a report."""
    if r.get("profile") != "P2" or not FOCUS_REPORT.search(r.get("problem", "")):
        return None
    px = r.get("focus_px") or []
    return "invisible" if "invisible" in px else ("visible" if "visible" in px else None)


def verify_reports(llm: LLM, profile: str, goal: str, reports: list[dict]) -> list[dict]:
    """One verifier call per persona run; each report gets verdict/check/sc/explanation ("not_site" if unanswered)."""
    if not reports:
        return []
    body = "\n\n".join(f"REPORT {n}: \"{r['problem']}\" (step {r['step']})\nprevious action: {r['prev_action'] or '(none)'}"
                       f"\nwhat came back: {r['prev_result'][:400]}\nwhat it perceived before step {r['step']}:\n{r['observation']}"
                       f"\nagent's thinking at step {r['step']}: {r['thought'][:300]}"
                       f"\naction at step {r['step']}: {r.get('action')}\nwhat came back: {(r.get('result') or '')[:400]}"
                       for n, r in enumerate(reports, 1))
    v = llm.json(VERIFY_SYSTEM, f"PROFILE: {profile} ({PERSONA_NAMES_SHORT.get(profile, profile)})\nTASK: {goal}\n\n{body}")
    got = {int(x.get("n", 0)): x for x in (v.get("reports") or []) if isinstance(x, dict) and str(x.get("n", "")).isdigit()}
    out = []
    for n, r in enumerate(reports, 1):
        x = got.get(n, {})
        verdict, sc = x.get("verdict", "not_site"), str(x.get("sc") or "no SC")
        if verdict == "site" and not re.search(r"\d\.\d+\.\d+", sc):
            verdict = "not_site"   # a site problem must name the success criterion it fails
        tool = None
        mistake = own_mistake(r)
        if verdict == "site" and mistake:
            verdict, x = "not_site", {**x, "explanation": mistake}
        px = tool_focus_check({**r, "profile": profile})
        if px == "invisible" and not mistake:   # the tool saw nothing change where focus went: confirmed
            sc = sc if (verdict == "site" and re.search(r"\d\.\d+\.\d+", sc)) else "2.4.7"
            verdict, tool = "site", "checked by the tool: nothing visible changed where focus moved"
            x = {**x, "check": "Notice", "explanation": x.get("explanation") or "Keyboard focus is not visible on this control."}
        elif px == "visible" and verdict == "site":
            verdict, x = "not_site", {**x, "explanation": "the tool saw a visible change where focus moved"}
        out.append({"profile": profile, "step": r["step"], "problem": r["problem"], "verdict": verdict,
                    "check": x.get("check", "Notice"), "sc": sc, "explanation": x.get("explanation", ""), "tool": tool})
    return out


PERSONA_NAMES_SHORT = {"P1": "blind screen-reader user", "P2": "sighted keyboard-only user, no mouse",
                       "P3": "low-vision user at 400% zoom"}


def path_from_reference(outcome: Outcome) -> list[dict]:
    """Turn the reference agent's recorded actions into replayable steps for the checker."""
    steps = []
    for st in outcome.steps:
        a = st.action
        if "escape" in (st.fallback or ""):  # the sighted agent dismissed a popup before this click; replays must too
            steps.append({"press": "Escape"})
        if not st.result.startswith("ok"):
            continue
        if a.get("type") == "click" and st.target_selector:
            steps.append({"click": st.target_selector})
        elif a.get("type") == "type" and st.target_selector:
            steps.append({"fill": [st.target_selector, a.get("text", "")]})
        elif a.get("type") == "select" and st.target_selector:
            steps.append({"select": [st.target_selector, a.get("option", "")]})
        elif a.get("type") == "press":
            steps.append({"press": a.get("key")})
    return steps


# A sighted user clicks a radio's or checkbox's visible label; a persona operates the control the label is tied to, so
# that control is what gets checked.
LABEL_TO_CONTROL = "e => { const l = e.closest('label'); return l && l.control && !e.closest('a, button, input, select, textarea') ? l.control : e; }"


def _resolve(s, step):
    kind, arg = next(iter(step.items()))
    if kind == "click":
        h = s.page.locator(arg).first.element_handle(timeout=8000)
        return h.evaluate_handle(LABEL_TO_CONTROL).as_element() or h
    if kind in ("fill", "select"):
        return s.page.locator(arg[0]).first.element_handle(timeout=8000)
    return None


def _execute(s, step):
    kind, arg = next(iter(step.items()))
    if kind == "click":
        s.page.locator(arg).first.click(timeout=8000)
    elif kind == "fill":
        loc = s.page.locator(arg[0]).first
        loc.click(timeout=8000)
        loc.fill(arg[1], timeout=8000)
        loc.dispatch_event("input")
    elif kind == "select":
        s.page.locator(arg[0]).first.select_option(label=arg[1], timeout=8000)
    elif kind == "press":
        s.page.keyboard.press(arg)


def _control_name(target: str) -> str:
    """The quoted name in a finding's target (button "Apply" -> apply), lower-cased; '' if it has none."""
    m = re.search(r'"([^"]{2,60})"', target or "")
    return m.group(1).strip().lower() if m else ""


def judge_stall(llm: LLM, profile: str, goal: str, ref: Outcome, out: Outcome, det: list[Finding]) -> dict | None:
    near = [f for f in det if f.profile == profile and f.severity == "blocks"] or [f for f in det if f.profile == profile]
    if near:
        # Corroboration is task-level (any rule finding for this persona on the task), and is also
        # reported step-local: the finding names a control the agent was dealing with in its last 4 steps.
        recent = " ".join(f"{json.dumps(s.action)} {s.result} {s.observation[:600]}" for s in out.steps[-4:]).lower()
        local = [g for g in near if _control_name(g.target) and _control_name(g.target) in recent]
        f = local[0] if local else near[0]
        return {"verdict": "barrier", "corroborated": True, "local": bool(local), "check": f.check, "sc": f.sc, "step": f.step,
                "explanation": f"{f.target}: {f.message}"}
    last = "\n\n".join(f"step {s.i}: did {json.dumps(s.action)} -> {s.result}\nthought: {s.thought}\nsaw: {s.observation[:1500]}"
                       for s in out.steps[-4:])
    ref_path = "\n".join(f"{s.i}. {json.dumps(s.action)}" for s in ref.steps)
    prompt = (f"PROFILE: {profile}\nTASK: {goal}\nREFERENCE PATH (succeeded):\n{ref_path}\n\n"
              f"PROFILE AGENT OUTCOME: {out.status} ({out.reason})\nLAST STEPS OF THE PROFILE AGENT:\n{last}")
    v = llm.json(JUDGE_SYSTEM, prompt)
    v["corroborated"] = False
    return v if v.get("verdict") == "barrier" else None


def _agent(task: dict, profile: str, llm: LLM, ev: EventLog, prepare=None, probe=None) -> Outcome:
    """One agent in its own browser (Playwright objects can't be shared across threads). probe(session) -> dict is
    benchmark instrumentation, recorded on every step (None on real sites)."""
    pool = BrowserPool()
    try:
        vp = Viewport(*SETTINGS.zoom_viewport) if profile == "P3" else Viewport(*SETTINGS.desktop)
        s = pool.session(vp)
        if prepare:
            prepare(s)

        shot = f"{task['id']}_{profile}"

        def on_step(st):
            if probe:
                try:
                    st.probe = probe(s)
                except Exception:
                    st.probe = None
            extra = {"fallback": st.fallback} if st.fallback else {}  # a rescued click shows in the log
            if st.problem:   # recorded in the event log
                extra["problem"] = st.problem[:200]
            ev.emit("agent_step", task=task["id"], profile=profile, i=st.i, action=st.action, result=st.result[:160],
                    thought=st.thought[:200], shot=ev.snapshot(s, shot), **extra)

        llmlib.context(task=task["id"], profile=profile)  # model calls from this thread are logged as this agent's
        ev.emit("agent_start", task=task["id"], profile=profile, max_steps=AGENT_STEPS.get(profile, 25))
        nav = Navigator(s, profile, llm, AGENT_STEPS.get(profile, 25), on_step)
        out = nav.run(task["goal"], task["start_url"])
        if profile in ("P1", "P2", "P3"):
            llmlib.context(task=task["id"], profile=profile, stage="debrief")
            out.debrief = nav.debrief(task["goal"], out)
            for d in out.debrief:
                ev.emit("agent_debrief", task=task["id"], profile=profile, step=d["step"], problem=d["problem"][:200])
        try:   # where the persona ended up, so its "done" can be checked against the sighted user's end state
            end_text, end_url = s.visible_text(False, 8000), s.page.url
        except Exception:
            end_text, end_url = "", ""
        out.evidence = {"start_text": nav.start_text, "end_text": end_text, "end_url": end_url,
                        "start_fields": nav.start_fields, "end_fields": form_fields(s),
                        "unperceived": nav.unperceived(out.answer, task["goal"]) if out.status == "done" else []}
        snapped = ev.snapshot(s, shot)
        s.close()
        ev.emit("agent_done", task=task["id"], profile=profile, status=out.status, steps=len(out.steps),
                reason=out.reason[:200], answer=out.answer[:200], shot=snapped, tool_error=out.tool_error)
        return out
    finally:
        pool.close()


def _check_profile(task: dict, steps: list, profile: str, ev: EventLog, prepare=None) -> tuple[list[Finding], list[dict]]:
    pool = BrowserPool()
    try:
        ev.emit("checks_start", task=task["id"], profile=profile, n=len(steps))
        checker = PathChecker(pool)
        fs = checker.run_profile(profile, task["start_url"], steps, _resolve, _execute, prepare,
                                 progress=lambda i, n: ev.emit("checks_step", task=task["id"], profile=profile, i=i, n=n))
        for f in fs:
            evidence = json.dumps(f.evidence, default=str)
            ev.emit("finding", task=task["id"], profile=f.profile, check=f.check, sc=f.sc, step=f.step,
                    severity=f.severity, target=f.target, message=f.message,
                    evidence=json.loads(evidence) if len(evidence) < 600 else "(large)")
        for e in checker.tool_errors:
            ev.emit("tool_error", task=task["id"], **e)
        ev.emit("checks_done", task=task["id"], profile=profile, findings=len(fs), tool_errors=len(checker.tool_errors))
        return fs, checker.tool_errors
    finally:
        pool.close()


def run_task(task: dict, profiles=PROFILES, llm: LLM | None = None, prepare=None, agents: bool = True,
             ev: EventLog = NULL, specialists: dict | None = None, probe=None) -> dict:
    """specialists: the planner's on/off map of check groups for this site; None keeps every check."""
    llm = llm or LLM(role="nav")
    rec = {"task": task, "reference": None, "profiles": {}, "findings": []}
    ev.emit("task_start", task=task["id"], goal=task["goal"])

    ref = _agent(task, "REF", llm, ev, prepare)
    rec["reference"] = {"status": ref.status, "answer": ref.answer, "tool_error": ref.tool_error,
                        "steps": [asdict(x) for x in ref.steps]}
    if ref.status != "done":
        if ref.tool_error:  # the model/API failed: nothing was learned about the task or the site
            rec["invalid"] = f"not tested: the model/API failed during the reference run: {ref.reason[:120]}"
            err = {"profile": "REF", "step": len(ref.steps), "where": "agent", "error": ref.reason[:200]}
            rec["tool_errors"] = [err]
            ev.emit("tool_error", task=task["id"], **err)
        else:
            rec["invalid"] = f"reference agent could not complete the task ({ref.status}: {ref.reason[:120]})"
        ev.emit("task_invalid", task=task["id"], reason=rec["invalid"], tool_error=ref.tool_error)
        return rec

    steps = path_from_reference(ref)
    agent_profiles = [p for p in profiles if p in ("P1", "P2", "P3")] if agents else []
    with ThreadPoolExecutor(max_workers=len(profiles) + len(agent_profiles)) as ex:
        check_futs = {p: ex.submit(_check_profile, task, steps, p, ev, prepare) for p in profiles}
        agent_futs = {p: ex.submit(_agent, task, p, llm, ev, prepare, probe) for p in agent_profiles}
        det: list[Finding] = []
        for p, fut in check_futs.items():
            try:
                fs, errs = fut.result()
                det += fs
                rec.setdefault("tool_errors", []).extend(errs)
            except Exception as e:
                rec.setdefault("tool_errors", []).append({"profile": p, "step": -1, "where": "checks", "error": str(e)[:200]})
                ev.emit("error", task=task["id"], profile=p, where="checks", error=str(e)[:200])
        det, dropped = select(det, specialists)
        if dropped:
            rec["filtered_out"] = findings_to_dicts(dropped)
            ev.emit("filtered", task=task["id"], n=len(dropped), specialists_off=[k for k, v in specialists.items() if not v])
        outcomes = {}
        for p, fut in agent_futs.items():
            try:
                outcomes[p] = fut.result()
            except Exception as e:  # the agent itself crashed (browser, page): a tool problem, not a stall
                rec.setdefault("tool_errors", []).append({"profile": p, "step": -1, "where": "agent", "error": str(e)[:200]})
                ev.emit("error", task=task["id"], profile=p, where="agent", error=str(e)[:200])
    rec["findings"] += findings_to_dicts(det)

    for p, out in outcomes.items():
        rec["profiles"][p] = {"status": out.status, "reason": out.reason, "answer": out.answer, "tool_error": out.tool_error,
                              "effort": effort(out.steps), "reference_effort": effort(ref.steps), "debrief": out.debrief,
                              "steps": [asdict(x) for x in out.steps]}
        if out.tool_error:
            # The model/API failed mid-run. That says nothing about the site, so it is neither judged nor a finding.
            err = {"profile": p, "step": len(out.steps), "where": "agent", "error": out.reason[:200]}
            rec.setdefault("tool_errors", []).append(err)
            ev.emit("tool_error", task=task["id"], **err)
        elif out.status != "done" and (st := end_state(ref, out)) and st["matches"] and st["cover"] >= 0.8:
            # The persona reached the sighted user's end state but didn't say "done" before its step limit. That is a
            # finished task, not a barrier.
            rec["profiles"][p].update(status="done", done_unsaid=True, end_state=st)
            ev.emit("judge", task=task["id"], profile=p, verdict="reached the end state without saying done", corroborated=None,
                    explanation=f"cover {st['cover']:.0%}")
        elif out.status != "done":
            llmlib.context(task=task["id"], profile=p, stage="judge")
            try:
                v = judge_stall(llm, p, task["goal"], ref, out, det)
            except Exception as e:
                v = None
                ev.emit("error", task=task["id"], profile=p, where="judge", error=str(e)[:200])
            ev.emit("judge", task=task["id"], profile=p, verdict=(v or {}).get("verdict", "agent_error"),
                    corroborated=(v or {}).get("corroborated"), explanation=(v or {}).get("explanation", "")[:200])
            if v and v.get("corroborated"):
                rec["findings"].append({"profile": p, "check": v.get("check", "Reach"), "sc": v.get("sc", "no SC"),
                                        "step": v.get("step", -1), "target": "task",
                                        "message": "task stalled: " + v.get("explanation", ""), "severity": "blocks",
                                        "evidence": {"source": "agent", "corroborated": True, "local": v.get("local"),
                                                     "agent_reason": out.reason}})
            else:
                # Without rule-based evidence a stall is not a rule-backed finding; it is kept with the judge's verdict.
                rec.setdefault("unconfirmed_stalls", []).append({"profile": p, "agent_status": out.status,
                                                                 "agent_reason": out.reason, "judge": v})
                # reported as Tier B agent evidence
                _agent_finding(rec, ev, task, p, "Reach", "the persona could not finish the task (no rule-based evidence; "
                               f"agent: {out.status}: {out.reason[:100]})", {"judge": v})
        else:
            for f in done_checks(ref, out):
                _agent_finding(rec, ev, task, p, f["check"], f["message"], f["evidence"])
    # What each persona reported as a problem, checked against its own trace. Kept reports are agent findings
    # in their own right; a rule finding for the same persona naming the same control only marks one as rule-confirmed.
    for p, out in outcomes.items():
        if out.tool_error:
            continue
        reports = reported_problems(out)
        if not reports:
            continue
        llmlib.context(task=task["id"], profile=p, stage="verify")
        try:
            checked = verify_reports(llm, p, task["goal"], reports)
        except Exception as e:
            ev.emit("error", task=task["id"], profile=p, where="verify", error=str(e)[:200])
            checked = [{"profile": p, "step": r["step"], "problem": r["problem"], "verdict": "unverified"} for r in reports]
        for r, src in zip(checked, reports):
            r["when"] = src["when"]
        for r in checked:
            text = (r["problem"] + " " + r.get("explanation", "")).lower()
            rule = next((f for f in det if f.profile == p and _control_name(f.target) and _control_name(f.target) in text), None)
            r["kept"] = r["verdict"] == "site"
            r["tier"] = "A" if r["kept"] and (rule or r.get("tool")) else "B"   # Tier A: a rule check on the same control, or the focus check
            r["rule"] = f"{rule.check} {rule.sc}: {rule.target}" if rule else None
            rec.setdefault("agent_reports", []).append(r)
            ev.emit("agent_report", task=task["id"], profile=p, step=r["step"], verdict=r["verdict"], tier=r["tier"],
                    problem=r["problem"][:200])
    ev.emit("task_done", task=task["id"], findings=len(rec["findings"]), agent_findings=len(rec.get("agent_findings", [])),
            agent_reports=sum(1 for r in rec.get("agent_reports", []) if r.get("kept")))
    return rec


def _agent_finding(rec, ev, task, profile, check, message, evidence) -> None:
    """Tier B: evidence from the persona agent alone. Kept apart from the rule-backed findings (tier A), so
    both can be reported and scored separately."""
    f = {"profile": profile, "check": check, "sc": "no SC", "step": -1, "target": "task", "message": message,
         "severity": "blocks", "tier": "B", "evidence": {"source": "agent", **evidence}}
    rec.setdefault("agent_findings", []).append(f)
    ev.emit("agent_finding", task=task["id"], profile=profile, check=check, message=message[:200])


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^0-9a-z₹,]+", (text or "").lower()) if len(w) >= 3}


def _page(url: str) -> tuple[str, str]:
    u = urlparse(url or "")
    return u.path, u.fragment.split("?")[0]


def end_state(ref: Outcome, out: Outcome) -> dict | None:
    """Does the persona end where the sighted user's task ended? Compared on what the task changed:
    the words it produced on screen (cover), and the form fields the reference changed (their end values). Which page
    each ended on is reported but not used: the same result can be reached from a different page (e.g. added to the
    cart from the list instead of the product page). None when the reference produced too little to compare."""
    e, r = out.evidence or {}, ref.evidence or {}
    produced = _words(r.get("end_text")) - _words(r.get("start_text"))
    rs, re_ = r.get("start_fields") or {}, r.get("end_fields") or {}
    changed = {k: v for k, v in re_.items() if rs.get(k) != v}
    pe = e.get("end_fields") or {}
    mismatch = sorted(k for k, v in changed.items() if k in pe and pe[k] != v)
    if len(produced) < 3 and not changed:
        return None
    cover = len(produced & _words(e.get("end_text"))) / len(produced) if len(produced) >= 3 else 1.0
    return {"cover": round(cover, 2), "field_mismatch": mismatch[:8], "same_page": _page(r.get("end_url")) == _page(e.get("end_url")),
            "missing": sorted(produced - _words(e.get("end_text")))[:12], "matches": cover >= 0.5 and not mismatch}


def done_checks(ref: Outcome, out: Outcome) -> list[dict]:
    """Checks on a persona that says "done":
    - provenance: its answer holds values it never perceived (and the task didn't give), so the model supplied them;
    - end state: most of what the reference's task produced on screen (words that appeared between its start and end
      page) is missing from the persona's end page, or a field the reference changed holds a different value."""
    found, e, r = [], out.evidence or {}, ref.evidence or {}
    if e.get("unperceived"):
        found.append({"check": "Notice", "message": "answered with values it never perceived: " + ", ".join(e["unperceived"][:5]),
                      "evidence": {"unperceived": e["unperceived"]}})
    st = end_state(ref, out)
    if st and not st["matches"]:
        why = f"{st['cover']:.0%} of what the task produced is on its screen"
        if st["field_mismatch"]:
            why += f"; fields set differently: {', '.join(st['field_mismatch'][:3])}"
        found.append({"check": "Reach", "message": f"said done but ended in a different state than the sighted user ({why})",
                      "evidence": st})
    return found


def _write_meta(run_dir: Path, **kw) -> None:
    p = run_dir / "meta.json"
    meta = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    meta.update(kw)
    p.write_text(json.dumps(meta, indent=1), encoding="utf-8")


def run_url(url: str, n_tasks: int = 4, profiles=PROFILES, out_dir: Path | None = None, agents: bool = True,
            all_checks: bool = False, frozen: dict | None = None) -> Path:
    """frozen: {url, specialists, tasks} from results/frozen_tasks.json. The planner is skipped and exactly these tasks
    are tested, so repeat runs test the same tasks (no exploring, no new task cards, no validator)."""
    out_dir = out_dir or RUNS / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    ev = EventLog(out_dir)
    _write_meta(out_dir, url=url, tasks=n_tasks, profiles=list(profiles), agents=agents, all_checks=all_checks, status="running",
                stage="planning", started=time.time(), model=SETTINGS.nav_model)
    llm = LLM(role="nav")
    llmlib.ON_EVENT = ev.emit  # retries, slow calls and failures appear in the run log
    results: list = []
    try:
        ev.emit("plan_start", url=url, budget=SETTINGS.explore_budget)
        pool = BrowserPool()
        s = pool.session(Viewport(*SETTINGS.desktop))
        llmlib.context(profile="planner", stage="planning")

        def on_page(i, page):
            ev.emit("explore_page", i=i, of=SETTINGS.explore_budget, url=page.get("url", ""),
                    title=(page.get("title") or page.get("error") or "")[:100], shot=ev.snapshot(s, "planner"))

        try:
            if frozen:
                pl = Plan(url=url, pages=[], capabilities=[], tasks=[dict(t) for t in frozen["tasks"]],
                          specialists=dict(frozen["specialists"]))
                _write_meta(out_dir, frozen_tasks=[t.get("frozen_from", "") for t in pl.tasks])
            else:
                pl = plan(s, url, LLM(role="planner"), SETTINGS.explore_budget, n_tasks, on_page=on_page)
        finally:  # a failed plan (e.g. no network) must not leave Playwright running: every later site would fail
            try:
                s.close()
            finally:
                pool.close()
        (out_dir / "plan.json").write_text(json.dumps(asdict(pl), indent=1, ensure_ascii=False), encoding="utf-8")
        ev.emit("plan_done", pages=len(pl.pages), tasks=[t["goal"] for t in pl.tasks], specialists=pl.specialists)
        for i, t in enumerate(pl.tasks):
            _write_meta(out_dir, stage=f"task {i + 1}/{len(pl.tasks)}")
            try:
                rec = run_task(t, profiles, llm, agents=agents, ev=ev, specialists=None if all_checks else pl.specialists)
                # A task lost because the model/API failed says nothing about the site, so wait (up to 30 min) until the
                # model answers image calls and run it once more. On by default; A11Y_TASK_RETRY=0 turns it off.
                if (os.environ.get("A11Y_TASK_RETRY", "1") == "1" and "model/API failed" in (rec.get("invalid") or "")
                        and _wait_for_image_calls(ev, t["id"], 30)):
                    rec = run_task(t, profiles, llm, agents=agents, ev=ev, specialists=None if all_checks else pl.specialists)
                    rec["retried_after_api_failure"] = True
                results.append(rec)
            except Exception as e:  # one broken task must not lose the others
                results.append({"task": t, "invalid": f"run failed: {str(e)[:200]}", "profiles": {}, "findings": []})
                ev.emit("error", task=t["id"], where="task", error=traceback.format_exc()[-400:])
            _save(out_dir, url, results)
        (out_dir / "report.md").write_text(report_md(url, pl, results), encoding="utf-8")
        _write_meta(out_dir, status="done", stage="done", ended=time.time())
        ev.emit("run_done", findings=sum(len(r["findings"]) for r in results))
    except Exception as e:
        _save(out_dir, url, results)
        _write_meta(out_dir, status="failed", stage="failed", ended=time.time(), error=str(e)[:300])
        ev.emit("run_failed", error=str(e)[:300])
        raise
    return out_dir


def _wait_for_image_calls(ev: EventLog, task_id: str, max_minutes: int) -> bool:
    """Probe every 5 min until the model answers an image call; False if it doesn't within max_minutes."""
    from .providers import POOL, probe_png
    deadline = time.time() + max_minutes * 60
    while True:
        alive = POOL.preflight(SETTINGS.nav_model, probe_png())
        if alive:
            ev.emit("task_retry", task=task_id, reason="model/API failed; retrying the task", keys=", ".join(alive))
            return True
        if time.time() > deadline:
            ev.emit("task_retry", task=task_id, reason=f"no key answered an image call within {max_minutes} min; not retried")
            return False
        time.sleep(300)


def _save(out_dir: Path, url: str, results: list) -> None:
    (out_dir / "results.json").write_text(json.dumps({"url": url, "results": results, "usage": USAGE.summary(),
                                                      "model_fallbacks": FALLBACKS},
                                                     indent=1, ensure_ascii=False, default=str), encoding="utf-8")


# Step checks as people read them. Internal codes stay the same so stored results keep scoring the same way.
CHECK_QUESTION = {
    "Reach": "Get to it: can this persona get to the control the next step needs?",
    "Identify": "Know what it is: can they tell what the control is and what state it's in?",
    "Operate": "Use it: does it work with their way of interacting?",
    "Notice": "Notice the change: are they told, or can they see, what changed?",
    "Recover": "Recover from errors: can they find, understand and fix a mistake?",
}
CHECK_LABEL = {k: v.split(":")[0] for k, v in CHECK_QUESTION.items()}
PERSONA_NAMES = ("P1 screen-reader user (no vision) · P2 keyboard user without fine motor control · "
                 "P3 low vision at 400% zoom · P4 colour-vision deficiency · P5 voice-control user")


def report_md(url, pl, results) -> str:
    total = sum(len(r["findings"]) for r in results)
    lines = [f"# Accessibility task report: {url}", "",
             f"Model: {SETTINGS.nav_model}. Pages explored: {len(pl.pages)}. Tasks: {len(results)}. Findings: {total}.", "",
             f"**What the site lets users do:** {', '.join(pl.capabilities)}", "",
             "**How to read this.** Each task is checked at two levels. *Task level:* a sighted mouse user does the task "
             "first; then each agent persona tries it with only what that person can perceive and do. *Step level:* at "
             "every step of the sighted path, rule checks ask, for each persona:", ""]
    lines += [f"- **{q.split(':')[0]}** ({k}):{q.split(':', 1)[1]}" for k, q in CHECK_QUESTION.items()]
    lines += ["", "A persona agent that gets stuck counts as a barrier only when a step check backs it up.", ""]
    for r in results:
        t = r["task"]
        lines += [f"## {t['goal']}", ""]
        if r.get("invalid"):
            inv = r["invalid"]
            lines += [f"_{inv[:1].upper() + inv[1:]}._" if inv.lower().startswith("not tested") else f"_Not tested: {inv}._", ""]
            continue
        prof = ", ".join(f"{p}: {'tool error' if v.get('tool_error') else v['status']}" for p, v in r["profiles"].items()) or "not run"
        lines += [f"Sighted reference user finished in {len(r['reference']['steps'])} steps. Persona agents: {prof}.", ""]
        if not r["findings"]:
            lines += ["No barriers found for this task" + (", but some parts did not run (see tool errors below)." if r.get("tool_errors") else "."), ""]
        for u in r.get("unconfirmed_stalls", []):
            lines.append(f"- _Unconfirmed: the {u['profile']} agent did not finish ({u['agent_status']}: {u['agent_reason'][:100]}). "
                         "No rule-based evidence, so this is not counted as a barrier; check it by hand._")
        for f in r["findings"]:
            corr = (f.get("evidence") or {}).get("corroborated")
            tag = " (agent stall, corroborated by a step check)" if corr else ""
            lines.append(f"- **{f['profile']} · {CHECK_LABEL.get(f['check'], f['check'])} · {f['sc']}** (step {f['step']}, {f['severity']}){tag}: {f['target']}: {f['message']}")
        if r.get("agent_findings"):
            lines += ["", "Agent evidence (tier B, lower confidence: the persona agent alone, without a rule check behind it):"]
            lines += [f"- **{f['profile']}**: {f['message']}" for f in r["agent_findings"]]
        if r.get("tool_errors"):
            lines += ["", "Tool errors (the tool failed, not the site; these are not findings. After a checker error the steps after it "
                          "were not checked for that profile; after an agent error, that profile's agent did not finish its run because "
                          "the model/API failed, so that profile was not tested by an agent):"]
            lines += [f"- {e['profile']} step {e['step']} ({e['where']}): {(e['error'].splitlines() or [''])[0][:120]}" for e in r["tool_errors"]]
        lines.append("")
    lines += ["---", PERSONA_NAMES]
    return "\n".join(lines)
