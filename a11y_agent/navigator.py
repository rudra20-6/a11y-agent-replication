"""LLM navigator: one step loop, parameterised by profile (what the agent may perceive and how it may act).

Reference: screenshot + every visible control (incl. clickable divs); pointer clicks and typing.
P1 screen reader: accessibility tree + focus + announcements only; keys, typing, and SR-style jumps to tree nodes.
P2 keyboard only: screenshot + visible text; focus is described only if it is visibly indicated; keys and typing only.
P3 400% zoom: 320 px screenshot + text in view; clicks only on controls inside the visible width; vertical scroll.
"""

from __future__ import annotations

import difflib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .browser import INTERACTIVE_ROLES, Session
from .llm import LLM

KEYS = {"Tab", "Shift+Tab", "Enter", " ", "Space", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
        "Home", "End", "PageUp", "PageDown", "Backspace", "Control+A"}

SYSTEM = """You are testing whether a person can complete a task on a website using a specific way of interacting.
You can ONLY use the observations and actions described for your profile. Do not assume anything you cannot perceive.
Never log in, never pay, never submit anything that creates an account, order or booking: if the next step would do
that, stop with "done" and say what you reached. Act like a real, reasonably skilled user of this interaction method.
A typed value often only takes effect when you leave the field (Tab) or press Enter. Before you say "done", check that
what the page shows now reflects every value the task asks for: a result that was already there before you changed
anything may be stale.
Reply with ONE JSON object: {"thought": "<one or two sentences>", "action": {...}} (add "problem": "..." only when
your profile asks you to report problems and you have one to report)."""

# v3 (D97): the persona agents are the testers. Besides doing the task they report what made it harder for someone like
# them, tied to the step where they noticed it, even when they finish. A finished task used to produce no agent evidence
# at all (Ma11y: new windows, pages changing on input, finished every time and never reported). The problem types are the
# ones screen-reader and keyboard users report most (WebAIM Screen Reader Survey #10), stated generally.
TESTER = """YOU ARE ALSO THE TESTER. Besides doing the task, notice what makes it harder for someone like you than it should
be. When the result of your last action, or what you perceive now, shows such a problem, add "problem": "<what the site
did, in your own words, as you perceived it>" to that reply; otherwise leave "problem" out. Typical problems people like
you report: the page, or a new window or tab, changed without you asking (for example when you typed, chose an option or
moved focus); something changed and you were not told; a control or text whose name or label makes no sense, or is read
or shown in a way you cannot make sense of; structure you cannot follow (headings, lists, tables without their headers);
something you cannot reach or operate the usual way; focus jumping somewhere unexpected; far more actions or key presses
than the task should need. Report only what the site did, not your own mistakes; report each problem once; never guess
at anything you cannot perceive."""

PROFILE_RULES = {
    "REF": """PROFILE: sighted mouse user. You see a screenshot and a list of the visible controls (ref, kind, text).
Actions: {"type":"click","ref":"el:N"} | {"type":"type","ref":"el:N","text":"..."} (clicks the field, replaces its text)
| {"type":"select","ref":"el:N","option":"<option text>"} (pick an option in a dropdown)
| {"type":"press","key":"Enter"} | {"type":"scroll","dir":"down"|"up"} | {"type":"done","answer":"..."} | {"type":"stuck","reason":"..."}""",
    "P1": """PROFILE: blind screen-reader user (like NVDA in Chrome). You perceive ONLY the accessibility tree below (what the
screen reader can read), where focus is, and what was announced. You cannot see the screen.
Actions: {"type":"press","key":"Tab|Shift+Tab|Enter|Space|Escape|ArrowDown|ArrowUp|ArrowLeft|ArrowRight|Home|End|Backspace|Control+A"}
| {"type":"type","text":"..."} (types into the focused field, at the cursor)
| {"type":"focus","ref":"ax:N"} (screen-reader quick navigation: move to a node listed with a ref; only works if it can take focus)
| {"type":"activate","ref":"ax:N"} (move to a control and press Enter/Space on it, as a screen-reader user would)
| {"type":"done","answer":"..."} | {"type":"stuck","reason":"what stops you"}
SKILLS (what experienced screen-reader users do): in an autocomplete/combobox, type, then ArrowDown to move through the
suggestions (listen to what is announced), then Enter to pick one. In a grid (e.g. a calendar), use arrow keys and Enter.
Radio buttons in a group: arrow keys move between them. To replace the text in a field, press Control+A, then type.
Check the tree after each action to confirm what changed.""",
    "P2": """PROFILE: sighted keyboard-only user (cannot use a mouse). You see the screen. You only know where keyboard focus is
if the screen shows a focus indicator (described to you only when one is visible).
You also get the list of controls visible on screen with their visible state ([checked] = ticked, pressed or selected).
Actions: {"type":"press","key":"Tab|Shift+Tab|Enter|Space|Escape|ArrowDown|ArrowUp|ArrowLeft|ArrowRight|Home|End|PageUp|PageDown|Backspace|Control+A"}
| {"type":"type","text":"..."} (types into the focused field, at the cursor) | {"type":"done","answer":"..."} | {"type":"stuck","reason":"..."}
SKILLS (what experienced keyboard users do): in an autocomplete/combobox, type, then ArrowDown to highlight a suggestion,
then Enter to pick it (Enter without a highlighted suggestion may submit the form). In a grid (e.g. a calendar) use arrow
keys and Enter. Radio buttons in a group: arrow keys move between them. Space or Enter toggles checkboxes and toggle
buttons, so pressing again undoes it: check the control's state before pressing again. To replace the text in a field,
press Control+A, then type. Error messages from an earlier attempt may stay on screen until you submit again.""",
    # Prompt-only personas (the "imagine you are..." baseline): they perceive and act exactly like REF and are only TOLD
    # who they are. Used to test whether a persona must be enforced by the harness.
    "P1T": None,
    "P2T": None,
    "P3": """PROFILE: low-vision user with the browser zoomed to 400% (the page is 320 px wide). You see only what fits on the
screen. You may scroll up/down, but scrolling sideways is very hard for you: anything off to the side does not exist for you.
Actions: {"type":"click","ref":"el:N"} (only controls listed as visible) | {"type":"type","ref":"el:N","text":"..."}
| {"type":"select","ref":"el:N","option":"<option text>"} (pick an option in a dropdown)
| {"type":"press","key":"Enter|Tab|Escape"} | {"type":"scroll","dir":"down"|"up"} | {"type":"done","answer":"..."} | {"type":"stuck","reason":"..."}""",
}

PROFILE_RULES["P1T"] = PROFILE_RULES["REF"] + """
PERSONA: You are a blind person who uses a screen reader (like NVDA). You cannot see the screen and you cannot use a mouse.
Behave exactly as such a person would: use only what a screen reader would read out to you, and the keyboard."""
PROFILE_RULES["P2T"] = PROFILE_RULES["REF"] + """
PERSONA: You have a motor impairment and cannot use a mouse; you use only the keyboard. Behave exactly as such a person would."""
# How each profile perceives and acts. Prompt-only personas get REF's perception and actions (only their prompt differs).
MODE = {"P1T": "REF", "P2T": "REF"}

# Persona-driven context (P1.1, D23/D24): P1–P3 get their context from the persona cards in personas.yaml. The action
# formats stay as written above, because the harness enforces exactly those actions.
PERSONAS = yaml.safe_load((Path(__file__).parent / "personas.yaml").read_text(encoding="utf-8"))


def _actions_part(rule: str) -> str:
    i = rule.index("Actions:")
    j = rule.find("SKILLS", i)
    return rule[i:j if j > 0 else None].strip()


for _pid, _c in PERSONAS.items():
    PROFILE_RULES[_pid] = (f"AGENT PERSONA {_pid} v{_c['version']}: {_c['name']} ({_c['criterion']}).\n"
                           f"WHAT YOU PERCEIVE: {_c['perceive']}\n"
                           f"WHY THE USUAL WAY OF USING A WEBSITE FAILS HERE: {_c['usual_way_fails']}\n"
                           f"{_actions_part(PROFILE_RULES[_pid])}\n"
                           f"WHAT EXPERIENCED USERS DO: {_c['strategies']}\n{_c['do_not_assume']}\n\n{TESTER}")

# v3 (D97): a screen reader reads a word written with spaces between its letters ("S e a r c h") letter by letter; the
# model read it as the word (Ma11y F32, missed in 3/3 seeds). P1 is told how it is spoken.
SPACED = re.compile(r"(?<![\w])((?:[A-Za-z] ){2,}[A-Za-z])(?![\w])")
# ... and a name that is nothing but spaced single characters ("2 1", a date written with a space) is read character by
# character too: "two, one", not "twenty-one".
SPACED_NAME = re.compile(r'"((?:[A-Za-z0-9] )+[A-Za-z0-9])"')


def spoken(text: str) -> str:
    say = lambda s: f"{s} [spoken letter by letter: {', '.join(s.split())}]"
    text = SPACED.sub(lambda m: say(m.group(1)), text)
    return SPACED_NAME.sub(lambda m: f'"{m.group(1)}"' if "spoken letter" in m.group(0) else f'"{say(m.group(1))}"', text)


@dataclass
class Step:
    i: int
    observation: str
    thought: str
    action: dict
    result: str
    url: str
    target_selector: str | None = None
    t: float = field(default_factory=time.time)
    fallback: str | None = None   # how a click/type was rescued: "re-found", "direct click", "escape" (comma separated)
    problem: str | None = None    # v3 (D97): what the persona reported as a problem at this step, in its own words
    probe: dict | None = None     # benchmark only: what the harness probe saw at this step (e.g. the barrier was touched)
    target: str | None = None     # v3 (D97): what the action was done on, as the persona knew it (role and name)
    focus_px: str | None = None   # v3.1 (D109): P2 pixel check where focus went: 'visible', 'invisible' or None (not checked)


def effort(steps: list) -> dict:
    """Effort of a run (D26): actions taken and key presses, so a finished task can still show what it cost."""
    return {"actions": len([s for s in steps if s.action.get("type") not in ("done", "stuck")]),
            "key_presses": sum(1 for s in steps if s.action.get("type") == "press")}


@dataclass
class Outcome:
    profile: str
    status: str            # done / stuck / max_steps / error
    answer: str
    steps: list
    reason: str = ""
    tool_error: bool = False   # status "error" because the model/API call failed (says nothing about the site or the agent)
    evidence: dict = field(default_factory=dict)   # v2: start/end page text and URL, answer values never perceived
    debrief: list = field(default_factory=list)    # v3 (D97): [{step, problem}] the persona listed after the task


NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _as_dict(x) -> dict:
    """Model replies are JSON but not always the right shape (Flipkart: "action" came back as a string)."""
    return x if isinstance(x, dict) else {}


# v2.4 (D86, H10): the values of the visible form fields, so a persona's end state can be compared with the sighted
# user's on what the task changed (the field values), not on which page it ended.
FIELDS_JS = """() => { const out = {};
  for (const e of document.querySelectorAll('input, select, textarea')) {
    const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    if (e.type === 'hidden' || cs.display === 'none' || cs.visibility === 'hidden' || (r.width === 0 && r.height === 0)) continue;
    const k = e.id || e.name || e.getAttribute('aria-label') || e.getAttribute('placeholder');
    if (!k) continue;
    out[k] = (e.type === 'checkbox' || e.type === 'radio') ? String(e.checked) : String(e.value || '').trim().toLowerCase();
  }
  return out; }"""


def form_fields(session) -> dict:
    try:
        return session.page.evaluate(FIELDS_JS)
    except Exception:
        return {}


def numbers(text: str) -> set[str]:
    """Numbers of two or more digits, commas removed (₹5,61,695 -> 561695): the values an answer can be traced by."""
    return {n.replace(",", "") for n in NUM_RE.findall(text or "") if len(n.replace(",", "").split(".")[0]) >= 2}


SCROLL_JS = """d => { const y = window.scrollY; window.scrollBy(0, d); if (window.scrollY !== y) return true;
  const box = [...document.querySelectorAll('body *')].filter(e => { const s = getComputedStyle(e);
      return /(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 4 && e.clientHeight > 0; })
    .sort((a, b) => b.clientHeight * b.clientWidth - a.clientHeight * a.clientWidth)[0];
  if (!box) return false; const t = box.scrollTop; box.scrollBy(0, d); return box.scrollTop !== t; }"""

CSS_PATH_JS ="""e => { if (!e || e.nodeType !== 1) return null;
  if (e.id && document.querySelectorAll('#' + CSS.escape(e.id)).length === 1) return '#' + CSS.escape(e.id);
  const parts = []; let n = e;
  while (n && n.nodeType === 1 && n !== document.documentElement) {
    let p = n.tagName.toLowerCase();
    if (n.id && document.querySelectorAll('#' + CSS.escape(n.id)).length === 1) { parts.unshift('#' + CSS.escape(n.id)); break; }
    if (!n.parentElement) break;   // detached by a re-render (v3.1, D102: "Cannot read properties of null")
    const sib = [...n.parentElement.children].filter(x => x.tagName === n.tagName);
    if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(n) + 1})`;
    parts.unshift(p); n = n.parentElement;
  }
  return parts.join(' > ');
}"""

# The field a typed text goes into when a pointer user clicks this element: itself if it takes text, the control of a
# label, or the one field inside a small box around it.
FILLABLE_JS = """e => { const ok = x => x && (['INPUT', 'TEXTAREA'].includes(x.tagName) || x.isContentEditable);
  if (ok(e)) return e;
  if (e.tagName === 'LABEL' && ok(e.control)) return e.control;
  const f = e.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea, [contenteditable=true]');
  return f.length === 1 ? f[0] : e; }"""

# What a user would find if they clicked the middle of the element: is it on top, disabled, or covered by something else?
HIT_TEST_JS = """e => {
  if (!e.isConnected) return {state: 'gone'};
  if (e.disabled === true || e.getAttribute('aria-disabled') === 'true') return {state: 'disabled'};
  const r = e.getBoundingClientRect();
  if (r.width <= 0 || r.height <= 0 || getComputedStyle(e).visibility === 'hidden') return {state: 'hidden'};
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) return {state: 'offscreen'};
  const hit = document.elementFromPoint(x, y);
  if (!hit) return {state: 'offscreen'};
  if (hit === e || e.contains(hit) || (e.labels && [...e.labels].some(l => l === hit || l.contains(hit)))) return {state: 'on_top'};
  const clean = t => (t || '').replace(/\\s+/g, ' ').trim();
  const dlg = hit.closest('[role=dialog],[role=alertdialog],[aria-modal=true],dialog');
  let text = clean(hit.getAttribute('aria-label') || hit.innerText);
  if (!text && dlg) text = clean(dlg.getAttribute('aria-label') || (dlg.querySelector('h1,h2,h3,[role=heading]') || {}).innerText || dlg.innerText);
  return {state: 'covered', by: {tag: hit.tagName.toLowerCase(), text: text.slice(0, 60),
                                 role: hit.getAttribute('role') || (dlg ? (dlg.getAttribute('role') || 'dialog') : '')}};
}"""


class Navigator:
    def __init__(self, session: Session, profile: str, llm: LLM, max_steps: int = 25, on_step=None):
        self.s, self.profile, self.llm, self.max_steps = session, profile, llm, max_steps
        self.mode = MODE.get(profile, profile)   # perception/action profile; differs from profile only for prompt-only personas
        self.on_step = on_step
        self.history: list[Step] = []
        self.t_last = 0.0
        self.known: dict[str, dict] = {}   # el:N -> what the last observation said it was (to follow it across a re-render)
        self.fallback: str | None = None   # set by act() when a click/type needed a rescue (see Step.fallback)
        self._rescues: list[tuple[str, str]] = []   # (tag, text for the result) of this action's rescues
        self.perceived: set[str] = set()   # v2: every number this persona actually received (observations and feedback)
        self.start_text = ""
        self.start_fields: dict = {}
        # v3 (D97): context changes a user notices. A new tab or window, and a page load or route change of the main frame.
        self._popups: list = []
        self._navs = 0
        try:   # plain functions: Playwright inspects a handler's signature, which a builtin like list.append doesn't have
            session.ctx.on("page", self._on_page)
            session.page.on("framenavigated", self._on_nav)
        except Exception:
            pass

    def _on_page(self, page) -> None:
        self._popups.append(page)

    def _on_nav(self, frame) -> None:
        if frame == self.s.page.main_frame:
            self._navs += 1

    def unperceived(self, answer: str, goal: str) -> list[str]:
        """Values in the answer that this persona never perceived and the task didn't give: the model supplied them
        itself (28 Oct: a screen-reader agent 'read' a result hidden from screen readers by calculating it)."""
        return sorted(numbers(answer) - self.perceived - numbers(goal))

    # ------------------------------------------------------------------ observation

    def observe(self) -> tuple[str, list[bytes]]:
        s, p = self.s, self.mode
        head = f"URL: {s.page.url}\nTITLE: {s.page.title()}\n"
        if self.profile in ("P1", "P2", "P3"):
            # v3 (D97): a person feels the effort a task takes; the agent is shown its own count, so it can report it.
            e = effort(self.history)
            head += f"YOUR EFFORT SO FAR: {e['actions']} actions, {e['key_presses']} key presses\n"
        if p == "P1":
            tree = s.ax_tree(max_lines=600)
            f = s.focus_info()
            anns = s.announcements(self.t_last)
            return spoken(head + f"FOCUS: {f['name'] if f else 'page'} ({f['tag'] if f else ''})\n"
                          f"ANNOUNCED SINCE LAST ACTION: {[a['text'] for a in anns][-5:]}\n\nACCESSIBILITY TREE:\n{tree.serialise()}"), []
        shot = s.screenshot()
        if not shot:  # the browser could not take one (e.g. fonts never finished loading); the agent still gets text
            head += "(screenshot unavailable this step; use the control list and the text below)\n"
        images = [shot] if shot else []
        if p == "P2":
            f = s.focus_info()
            cue = "no visible focus indicator"
            if f and s.js("focusShown"):   # v3.1 (D104): any drawn indicator, as the rule check counts it
                cue = f'focus indicator visible on: {f["tag"]} "{f["name"]}"'
            # Sighted: sees the same controls and states as the mouse user, without click targets.
            controls = self._controls(s.interactive_elements(viewport_only=True), refs=False)
            return head + f"FOCUS: {cue}\nVISIBLE CONTROLS:\n{controls}\n\nVISIBLE TEXT:\n{s.visible_text(True, 2500)}", images
        els = self._pointer_els()
        self.known = {e["ref"]: {"kind": e["role"] or e["tag"], "type": e["type"] or "", "text": e["text"]} for e in els[:180]}
        try:   # what a scrollbar shows a sighted user: where on the page they are, and whether there is more below
            y, vh, dh = s.page.evaluate("() => [scrollY, innerHeight, document.documentElement.scrollHeight]")
            head += (f"PAGE POSITION: showing {int(y)}–{int(y + vh)} px of a {int(dh)} px page"
                     f"{' (more below)' if y + vh < dh - 4 else ' (end of page)'}\n")
        except Exception:
            pass
        return head + f"VISIBLE CONTROLS:\n{self._controls(els)}\n\nVISIBLE TEXT:\n{s.visible_text(p == 'P3', 2500)}", images

    def _pointer_els(self) -> list[dict]:
        """The controls a mouse user (REF) or a 400% zoom user (P3: only those inside the visible width) can click."""
        els = self.s.interactive_elements(viewport_only=(self.profile == "P3"))
        if self.profile == "P3":
            els = [e for e in els if e["rect"][0] >= -1 and e["rect"][0] + e["rect"][2] <= self.s.page.viewport_size["width"] + 1]
        return els

    @staticmethod
    def _controls(els: list[dict], refs: bool = True) -> str:
        return "\n".join(f'{e["ref"] + " " if refs else "- "}{e["role"] or e["tag"]}{"/" + e["type"] if e["type"] else ""} "{e["text"][:60]}"'
                         f'{" [checked]" if e["checked"] else ""}{" [disabled]" if e["disabled"] else ""}{" value=" + e["value"] if e["value"] else ""}'
                         for e in els[:180])

    # ------------------------------------------------------------------ actions

    def act(self, a: dict) -> tuple[str, str | None]:
        s, p, kind = self.s, self.mode, a.get("type")
        sel, ticked = None, ""
        self.fallback, self._rescues = None, []
        k = self.known.get(a.get("ref", "")) if a.get("ref", "").startswith("el:") else None
        self._target = f'{k["kind"]} "{k["text"][:60]}"' if k else None
        navs0, pops0 = self._navs, len(self._popups)
        try:   # v3.1 (D108): forget an unload record left by an earlier action
            s.js("unloadCause", True)
        except Exception:
            pass
        allowed = {"REF": {"click", "type", "select", "press", "scroll"}, "P1": {"press", "type", "focus", "activate"},
                   "P2": {"press", "type"}, "P3": {"click", "type", "select", "press", "scroll"}}[p]
        if kind not in allowed:
            return f"not allowed for this profile: {kind}", None
        # Sighted profiles notice what appears on screen after an action (a cart count, a confirmation line).
        seen_before = self._screen_lines() if p != "P1" else None
        if p == "P2":
            self._look_before()
            self._px_before = self._px_snapshot()
        self._focus_px = None
        if kind == "press":
            key = a.get("key", "")
            if key.lower() in ("ctrl+a", "control+a"):
                key = "Control+A"
            if key not in KEYS:
                return f"unknown key {key}", None
            s.page.keyboard.press("Space" if key in (" ", "Space") else key)
        elif kind == "type":
            if p in ("REF", "P3"):
                h, failure = self._resolve_el(a.get("ref", ""))
                if not h:
                    return failure.replace("no such control", "no such field"), None
                h, failure = self._click_like_user(a.get("ref", ""), h)
                if not h:
                    return failure, None
                # v3.1 (D102): a pointer user clicks a field's label, or the box around it, and types: the text goes into
                # the field. Typing into the label itself failed (31 "not an <input>" errors in the v2.4 Ma11y runs), and
                # v3 personas then reported the site's field as "not an input" (clean T3, T6).
                h = h.evaluate_handle(FILLABLE_JS).as_element() or h
                sel = h.evaluate(CSS_PATH_JS)
                h.fill(a.get("text", ""))
                h.dispatch_event("input")
                h.dispatch_event("change")   # a pointer user's next click leaves the field, which commits the value
            else:
                s.page.keyboard.type(a.get("text", ""), delay=20)
        elif kind == "select":  # a native dropdown: pointer users pick the option from the list it opens
            h, failure = self._resolve_el(a.get("ref", ""))
            if not h:
                return failure, None
            if h.evaluate("e => e.tagName") != "SELECT":
                return "that isn't a dropdown", None
            sel = h.evaluate(CSS_PATH_JS)
            h.select_option(label=a.get("option", ""))
        elif kind == "scroll":
            # Scroll the page, as the scrollbar, Page Down or a wheel over page content would. A wheel turned wherever the
            # pointer last was changed a focused number field instead (D68: SIP 5000 -> 4500 -> 4000; the page never
            # moved). If the window can't scroll, scroll the largest scrollable box (app shells that scroll a div).
            s.page.evaluate(SCROLL_JS, 500 if a.get("dir") == "down" else -500)
        elif kind == "click":
            h, failure = self._resolve_el(a.get("ref", ""))
            if not h:
                return failure, None
            pre = self._css_path(h)   # before the click: a click can remove its own target (a date cell closing its dialog)
            was = self._tick(h)
            h, failure = self._click_like_user(a.get("ref", ""), h)
            if not h:
                return failure, None
            sel = self._css_path(h) or pre   # may be a new element if it was re-found; the replayable path must match
            now = self._tick(h)
            if was is not None and now is not None and now != was:
                ticked = "; it is now ticked" if now else "; it is now unticked"
        elif kind in ("focus", "activate"):
            ref = a.get("ref", "")
            node = s.ax_tree(max_lines=100000).find(ref)
            self._target = f'{node["role"]} "{node["name"][:60]}"' if node else None
            if not node:
                return "that node isn't in the accessibility tree", None
            h = s.element_for_ref(ref)
            if not h:
                return "node not found", None
            focusable = bool(node["props"].get("focusable"))
            sel = h.evaluate(CSS_PATH_JS)
            if kind == "focus":
                if not focusable:
                    return "can't move focus there (the screen reader can read it but it can't take focus)", None
                h.focus()
            else:
                if node["role"] not in INTERACTIVE_ROLES:
                    return "that isn't announced as something you can activate", sel
                if focusable:
                    h.focus()
                    key = "Space" if node["role"] in ("checkbox", "radio", "switch") else "Enter"
                    s.page.keyboard.press(key)
                else:
                    # Screen readers in browse mode activate announced controls by sending a click (e.g. NVDA on a
                    # listbox option or grid cell). Only controls exposed with an interactive role get this.
                    h.evaluate("e => e.click()")
        s.settle(400)
        typed = self._field_value() if kind == "type" else ""
        res = ("ok" + "".join(text for _, text in self._rescues) + typed + ticked
               + self._context_change(kind, a.get("key", ""), navs0, pops0) + self._feedback() + self._screen_change(seen_before))
        return (spoken(res) if p == "P1" else res), sel

    def _context_change(self, kind: str, key: str, navs0: int, pops0: int) -> str:
        """v3 (D97): changes of context any user notices. A new tab opened by the page is reported and closed, so the run
        goes on in the original page. A page load or route change after typing, choosing an option or moving focus (not
        after Enter, Space, a click or activating a control) is reported as unrequested.
        v3.1 (D108): a reload the page started itself while handling a field's change (form.submit() called from the
        field's change/input handler) is reported whatever the action was: keyboard users commit a field by leaving it,
        with Tab, Enter or by activating the next control, and those were not reported (Ma11y F36 missed for P1/P2)."""
        notes = []
        for pg in self._popups[pops0:]:
            try:
                pg.wait_for_load_state("commit", timeout=3000)
            except Exception:
                pass
            notes.append(f"a new browser tab opened by itself ({(pg.url or 'blank')[:60]}); the test tool closed it and "
                         "you are back on this page")
            try:
                pg.close()
            except Exception:
                pass
        if self._navs > navs0:
            left = None
            try:
                left = (self.s.js("unloadCause", True) or {}).get("leftField")
            except Exception:
                pass
            quiet = kind in ("type", "select") or (kind == "press" and key not in ("Enter", " ", "Space"))
            if left is not None:
                notes.append(f"the page reloaded by itself when the value of the field \"{left[:40]}\" was committed "
                             "(as you typed or left it), although you did not submit anything or follow a link")
            elif quiet:
                notes.append("the page reloaded or moved to another address, although you did not submit anything or follow a link")
        return "".join("; " + n for n in notes)

    # v2.5 (D95): a styled radio/checkbox (GOV.UK pattern) hides its input and draws the tick on the label. That tick is
    # a visible change but not a text change, so a successful click on GOV.UK's "Yes" read as "nothing visible changed"
    # (frz1/frz2, t1). Only that case: a visible input already shows [checked] on itself in the controls list.
    # v3 (D97): every radio/checkbox click, the label or the input itself. A visible tick is a visible change too, and
    # without it P3 reported "nothing changed visually" after picking a fare (clean T2, 4 Nov).
    TICK_JS = """e => { const c = e.tagName === 'LABEL' ? e.control : e;
        return c && ['checkbox', 'radio'].includes(c.type) ? c.checked : null; }"""

    def _tick(self, h) -> bool | None:
        try:
            return h.evaluate(self.TICK_JS)
        except Exception:
            return None

    def _field_value(self) -> str:
        """What the focused field now contains. Field values are not part of the page text the change report compares, so
        without this a successful type looks like "nothing visible changed" and agents retype (seen 13 Oct, SIP task)."""
        try:
            v = self.s.page.evaluate("() => { const e = document.activeElement; return e && 'value' in e ? String(e.value) : null; }")
        except Exception:
            return ""
        return "" if v is None else f'; the field now contains "{v[:60]}"'

    # ------------------------------------------------------------------ clicking like a user on a real site

    def _rescue(self, tag: str, text: str) -> None:
        """Note that this action needed help (shown in the result, recorded in Step.fallback and the agent_step event)."""
        if any(t == tag for t, _ in self._rescues):
            return
        self._rescues.append((tag, text))
        self.fallback = ", ".join(t for t, _ in self._rescues)

    def _resolve_el(self, ref: str):
        """The element for an el: ref. If the page re-rendered and the ref is gone, look for the one control that was
        listed with the same role, type and text. Returns (handle, "") or (None, what to tell the agent)."""
        h = self.s.element_for_ref(ref)
        if h:
            return h, ""
        k = self.known.get(ref)
        if not k:
            return None, "no such control"
        label = f'{k["kind"]} "{k["text"][:40]}"'
        if not k["text"]:
            return None, f"no such control: {ref} is gone (the page changed) and it had no text to find it again by; read the new control list"
        same = [e for e in self._pointer_els() if (e["role"] or e["tag"], e["type"] or "", e["text"]) == (k["kind"], k["type"], k["text"])]
        if not same:
            return None, f"no such control: {ref} ({label}) is gone and nothing like it is visible on the page now (the page changed); read the new control list"
        if len(same) > 1:
            return None, (f"no such control: {ref} ({label}) is gone and {len(same)} controls on the page now look like it "
                          f"({', '.join(e['ref'] for e in same[:4])}); choose one from the new control list")
        h = self.s.element_for_ref(same[0]["ref"])
        if not h:
            return None, f"no such control: {ref} ({label}) is gone (the page changed); read the new control list"
        self._rescue("re-found", " (re-found after the page re-rendered)")
        return h, ""

    def _click_once(self, h) -> tuple[str, str]:
        """One click attempt. Returns (state, detail): clicked | gone | covered | blocked (nothing was clicked, detail says why)."""
        try:
            h.click(timeout=5000)
            return "clicked", ""
        except Exception as e:
            err = str(e).splitlines()[0][:100] if str(e) else type(e).__name__
        try:
            hit = h.evaluate(HIT_TEST_JS)
        except Exception:
            return "gone", err
        if hit["state"] == "gone":
            return "gone", err
        if hit["state"] == "on_top":
            # The control is where the user would click and nothing covers it, so Playwright failed for another reason
            # (an animation that never settles, say). A user clicking the visible control would succeed: do that.
            try:
                h.evaluate("e => e.click()")
            except Exception:
                return "gone", err
            self._rescue("direct click", "; clicked (fallback: direct click)")
            return "clicked", ""
        if hit["state"] == "covered":
            by = hit["by"]
            what = f'<{by["tag"]}>' + (f' {by["role"]}' if by["role"] else "") + (f' "{by["text"]}"' if by["text"] else "")
            return "covered", what
        return "blocked", {"disabled": "it is disabled", "hidden": "it is not visible",
                           "offscreen": "its middle is outside the visible part of the page"}.get(hit["state"], hit["state"])

    @staticmethod
    def _css_path(h) -> str | None:
        """Replayable selector for an element, or None if it is gone. Recording must never turn a successful action
        into an error (seen 28 Oct: a date-cell click worked, the dialog closed, and the step was logged as failed)."""
        try:
            return h.evaluate(CSS_PATH_JS)
        except Exception:
            return None

    def _click_like_user(self, ref: str, h):
        """Click h (the field, for typing). Returns (handle that was clicked, "") or (None, what to tell the agent).
        A click that fails is never forced through something that covers the control. REF (a sighted mouse user) presses
        Escape once if a popup covers it, the way a person would dismiss a popup, and tries again."""
        k = self.known.get(ref)
        name = f'{k["kind"]} "{k["text"][:40]}"' if k else "it"
        state, detail = self._click_once(h)
        if state == "gone":  # the page re-rendered while we were clicking: find the control again, once
            h, failure = self._resolve_el(ref)
            if not h:
                return None, failure
            state, detail = self._click_once(h)
        if state == "covered" and self.mode == "REF":
            self.s.page.keyboard.press("Escape")
            self._rescue("escape", f"; pressed Escape first because {detail} covered it")
            self.s.settle(400)
            h, failure = self._resolve_el(ref)   # closing the popup may have re-rendered the page
            if not h:
                return None, f"can't click {name}: {detail} covered it; pressed Escape and then it was gone ({failure})"
            state, detail = self._click_once(h)
            if state == "covered":
                return None, f"can't click {name}: {detail} still covers it after pressing Escape; close or dismiss that first"
        if state == "covered":
            return None, f"can't click {name}: {detail} covers it at that point, so a click would land on that instead; close or dismiss it first"
        if state == "gone":
            return None, f"can't click {name}: it disappeared when clicked (the page changed); read the new control list"
        if state == "blocked":
            return None, f"can't click {name}: {detail}"
        return h, ""

    def _screen_lines(self) -> list[str]:
        """Visible text as words (the page text comes back as one run, so changes are found word by word)."""
        try:
            return self.s.visible_text(self.mode in ("P2", "P3"), 8000).split()
        except Exception:
            return []

    def _screen_change(self, before: list[str] | None) -> str:
        if before is None:
            return ""
        after = self._screen_lines()
        spans = []
        for op, _, _, j1, j2 in difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes():
            if op in ("insert", "replace"):
                # a little context so "2 items" reads as "Cart: 2 items"
                spans.append(" ".join(after[max(0, j1 - 2):j2]))
        if not spans:
            return "; nothing visible changed"
        text = " | ".join(spans)
        return f"; newly visible: {text[:240]}{'...' if len(text) > 240 else ''}"

    # v2.4 (D86, N3): ARIA states are not visible on screen, so the sighted keyboard persona (P2) is not told them;
    # it still gets a native checkbox's or radio's checked state, which is drawn. P1 hears them, as a screen reader does.
    FOCUS_KIND_JS = """(aria) => { const e = document.activeElement;
      if (!e || e === document.body || e === document.documentElement) return null;
      const t = (e.getAttribute('type') || '').toLowerCase();
      const kind = e.getAttribute('role') || (e.tagName === 'INPUT' ? ({range: 'slider', checkbox: 'checkbox', radio: 'radio button',
        number: 'number field'}[t] || 'text field') : ({SELECT: 'dropdown', TEXTAREA: 'text field', BUTTON: 'button', A: 'link'}[e.tagName] || ''));
      const st = [];
      if (t === 'checkbox' || t === 'radio') st.push(e.checked ? 'checked' : 'not checked');
      if (aria) for (const a of ['aria-checked', 'aria-pressed', 'aria-selected', 'aria-expanded'])
        if (e.hasAttribute(a)) st.push(a.slice(5) + '=' + e.getAttribute(a));
      return {kind, state: st.join(', ')}; }"""

    def _focus_kind(self) -> str:
        """'slider ', 'checkbox (checked) ' ... for the focused control, so a persona knows WHAT it is on (13/28 Oct: a
        keyboard agent typed into a slider 30 times, and toggled a checkbox back and forth, without knowing either)."""
        try:
            k = self.s.page.evaluate(self.FOCUS_KIND_JS, self.mode != "P2")
        except Exception:
            return ""
        if not k or not k["kind"]:
            return ""
        return f"{k['kind']}{' (' + k['state'] + ')' if k['state'] else ''} "

    # v2.4 (D88): without ARIA states, P2 pressed Enter on a bus seat 20 times and was told "nothing visible changed",
    # although the seat turns solid green when selected (clean T7, 3 Nov). A sighted user sees the control they pressed
    # change colour, so P2 is told when the still-focused control's drawn style changes. Focus styles are unchanged
    # because focus stays on it; a Tab moves focus away, so nothing is reported then.
    LOOK_JS = """(phase) => { const sig = el => { const c = getComputedStyle(el);
        return {background: c.backgroundColor, text: c.color, border: c.borderTopColor + ' ' + c.borderTopWidth,
                weight: c.fontWeight, shadow: c.boxShadow, underline: c.textDecorationLine}; };
      const e = document.activeElement;
      if (phase === 'before') { window.__a11yLook = e && e !== document.body ? {e, s: sig(e)} : null; return null; }
      const L = window.__a11yLook; window.__a11yLook = null;
      if (!L || L.e !== e || !e.isConnected) return null;
      const now = sig(e);
      return Object.keys(now).filter(k => now[k] !== L.s[k]).map(k => k + ' ' + L.s[k] + ' -> ' + now[k]); }"""

    def _look_before(self):
        try:
            self.s.page.evaluate(self.LOOK_JS, "before")
        except Exception:
            pass

    def _look_change(self) -> str:
        try:
            ch = self.s.page.evaluate(self.LOOK_JS, "after")
        except Exception:
            return ""
        return f" (it now looks different: {'; '.join(ch)[:160]})" if ch else ""

    @staticmethod
    def _name(n: str) -> str:
        """v3 (D97): a long name is cut here (and at 80 characters by the page helper); say so, or the persona reports our
        cut as the site's (GOV.UK v3s1: 'You have accepted additional cookies. You can chan' read as a truncated message)."""
        n = n or ""
        return n if len(n) < 78 else n[:100] + " [...shortened by the test tool, not the site]"

    # v3.1 (D109): pixel evidence for P2's focus feedback. The style rule (focusShown) misses indicators drawn in other
    # ways; a sighted keyboard user sees whatever changed on screen where focus went.
    PX_BEFORE_JS = "() => { window.__aaPrevActive = document.activeElement; return {sx: scrollX, sy: scrollY}; }"
    PX_AFTER_JS = """() => { const e = document.activeElement; if (!e || e === document.body || e === document.documentElement) return null;
        const r = e.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height, sx: scrollX, sy: scrollY,
        vw: innerWidth, vh: innerHeight, same: e === window.__aaPrevActive}; }"""

    # Is the focused element a control a keyboard user operates (2.4.7's "keyboard operable user interface")? A heading,
    # region or error summary given tabindex=-1 so the page can move focus there is not.
    CONTROL_JS = """() => { const e = document.activeElement; if (!e || e === document.body) return null;
        const t = e.tagName.toLowerCase(), role = (e.getAttribute('role') || '').toLowerCase();
        if (['a', 'button', 'input', 'select', 'textarea', 'summary', 'iframe'].includes(t) && !(t === 'a' && !e.hasAttribute('href'))) return true;
        if (['button', 'link', 'checkbox', 'radio', 'tab', 'option', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'combobox',
             'textbox', 'searchbox', 'slider', 'spinbutton', 'switch', 'listbox', 'gridcell', 'treeitem', 'grid', 'tree',
             'tablist', 'menu', 'menubar', 'radiogroup'].includes(role)) return true;
        if (e.isContentEditable) return true;
        return e.tabIndex >= 0 && e.getAttribute('tabindex') !== null && e.getAttribute('tabindex') !== '-1'; }"""

    def _px_snapshot(self):
        try:
            meta = self.s.page.evaluate(self.PX_BEFORE_JS)
            return self.s.page.screenshot(timeout=5000), meta
        except Exception:
            return None

    def _focus_pixels(self) -> str | None:
        """'visible' if the area around the newly focused control changed visibly with the key press (a ring at its edge
        or a changed background), 'invisible' if it didn't, None if it can't be told (focus didn't move, the control
        is very large, or the area wasn't on screen before)."""
        import io
        import numpy as np
        from PIL import Image
        b = getattr(self, "_px_before", None)
        try:
            r = self.s.page.evaluate(self.PX_AFTER_JS)
            if not b or not r:
                return None
            if r["same"]:
                return getattr(self, "_px_last", None)
            if r["w"] < 2 or r["h"] < 2 or r["w"] * r["h"] > 0.4 * r["vw"] * r["vh"]:
                return None
            png1 = self.s.page.screenshot(timeout=5000)
        except Exception:
            return None
        png0, m0 = b
        im0 = np.asarray(Image.open(io.BytesIO(png0)).convert("RGB")).astype(np.int16)
        im1 = np.asarray(Image.open(io.BytesIO(png1)).convert("RGB")).astype(np.int16)
        if im0.shape != im1.shape:
            return None
        k = im1.shape[1] / max(1, r["vw"])
        pad, edge = 6, 3
        x0, y0 = int((r["x"] - pad) * k), int((r["y"] - pad) * k)
        x1, y1 = int((r["x"] + r["w"] + pad) * k), int((r["y"] + r["h"] + pad) * k)
        dx, dy = int((r["sx"] - m0["sx"]) * k), int((r["sy"] - m0["sy"]) * k)   # where the same content was before
        H, W = im1.shape[:2]
        x0, y0, x1, y1 = max(x0, 0, -dx), max(y0, 0, -dy), min(x1, W, W - dx), min(y1, H, H - dy)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        A, B = im1[y0:y1, x0:x1], im0[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
        changed = np.abs(A - B).max(axis=2) > 48
        ix0, iy0 = int((r["x"] + edge) * k) - x0, int((r["y"] + edge) * k) - y0
        ix1, iy1 = int((r["x"] + r["w"] - edge) * k) - x0, int((r["y"] + r["h"] - edge) * k) - y0
        band = np.ones(changed.shape, bool)
        inner = None
        if ix1 - ix0 > 2 and iy1 - iy0 > 2:
            ix0, iy0 = max(ix0, 0), max(iy0, 0)
            band[iy0:iy1, ix0:ix1] = False
            inner = (slice(iy0, iy1), slice(ix0, ix1))
        ring = changed[band].mean() if band.any() else 0.0
        fill = float(np.abs(A[inner].reshape(-1, 3).mean(0) - B[inner].reshape(-1, 3).mean(0)).mean()) if inner and A[inner].size else 0.0
        self._px_last = "visible" if ring >= 0.2 or fill >= 20 else "invisible"
        return self._px_last

    def _feedback(self) -> str:
        """What the user could notice right after the action: focus (if perceivable) and new announcements."""
        try:
            f = self.s.focus_info()
            what = self._focus_kind()   # kind and state: screen readers announce them, sighted users see them
            if self.mode == "P1":
                anns = [a["text"] for a in self.s.announcements(self.t_last)][-2:]
                return f"; focus: {what}{self._name(f['name']) if f else 'page'}" + (f"; announced: {anns}" if anns else "")
            if self.mode == "P2":
                if f and self.s.js("focusShown"):   # v3.1 (D104): outline, ring, label ring or a highlight
                    self._focus_px = "visible"
                    return f"; focus now visibly on: {what}{self._name(f['name'])}{self._look_change()}"
                if not f:   # v3 (D97): nothing focused (e.g. after a page change) is not an invisible focus indicator
                    return "; no control has focus (focus is on the page itself)"
                if self.s.page.evaluate(self.CONTROL_JS) is False:
                    # v3.1 (D109): the page moved focus to a heading or a region (tabindex=-1) after a page change: the
                    # recommended pattern, and not a control, so 2.4.7 doesn't ask for an indicator (smoke, 6 Nov:
                    # BenchBook's h1 focus was "confirmed" as invisible focus on 3 clean tasks).
                    return "; no control has focus (the page moved focus to the start of its content)"
                # v3.1 (D109): the style rule saw no indicator; compare what the screen showed around the newly focused
                # control before and after the key press. A ring or highlight that appeared is visible focus.
                self._focus_px = self._focus_pixels()
                if self._focus_px == "visible":
                    return f"; focus now visibly on: {what}{self._name(f['name'])} (it now looks different around it)"
                return "; you cannot see where focus is"
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------ loop

    NUDGE_AFTER, GIVE_UP_AFTER = 3, 6   # identical (action, result) steps in a row: tell the agent, then end the run

    def _repeats(self) -> int:
        """How many of the latest steps repeat the same action with the same result. A Tab that moves focus gives a new
        result each time, so moving through a page never counts as repetition."""
        n, h = 0, self.history
        while n < len(h) and h[-1 - n].action == h[-1].action and h[-1 - n].result == h[-1].result:
            n += 1
        return n

    CYCLE_NUDGE, CYCLE_GIVE_UP = 6, 10   # back-and-forth: the last N steps use at most 2 actions and give at most 2 results

    def _cycle(self) -> int:
        """Length of the latest run of steps that only alternate between two actions with two outcomes (a checkbox
        toggled on and off, scrolling up and down). 28 Oct: a keyboard agent toggled 'Shoes' 33 times this way."""
        h, n = self.history, 0
        acts, res = [], []
        while n < len(h):
            st = h[-1 - n]
            a, r = json.dumps(st.action, sort_keys=True), st.result
            if (a not in acts and len(acts) == 2) or (r not in res and len(res) == 2):
                break
            acts += [a] if a not in acts else []
            res += [r] if r not in res else []
            n += 1
        return n

    def _no_progress(self) -> tuple[bool, bool]:
        """(nudge, give up)"""
        r, c = self._repeats(), self._cycle()
        return r >= self.NUDGE_AFTER or c >= self.CYCLE_NUDGE, r >= self.GIVE_UP_AFTER or c >= self.CYCLE_GIVE_UP

    def _no_progress_note(self) -> str:
        if self.history and self._no_progress()[0]:
            return ("NOTE: your recent actions keep repeating with the same results, so they are not getting you anywhere. "
                    "If the task is already complete, reply with done. Otherwise try a different approach.\n\n")
        return ""

    # v3 (D97): after the task, the persona looks back over its own steps and lists what the site did to it. While acting,
    # the model never filled the optional "problem" field, not even when told "a new browser tab opened by itself" or "the
    # page reloaded although you did not submit anything" (smoke run, 4 Nov). A debrief is a separate, focused question.
    DEBRIEF_SYSTEM = ("You used a website as the person described in your profile, to do a task, and now report on it as an "
                      "accessibility tester. Reply with ONE JSON object.")
    DEBRIEF = """The task is over ({status}). Looking back at your steps above, list every problem the website caused someone
like you during it: something that happened without you asking (a new tab or window, the page reloading or moving on when
you typed, chose an option or moved focus), a change you were not told about, a name, label or text you could not make sense
of as you perceived it, structure you could not follow, something you could not reach or operate the usual way, focus
jumping somewhere unexpected, far more actions or key presses than the task should need. Give the number of the step where
it happened. Only what the site did, not your own mistakes: an error message after you typed or picked something wrong
is the site working, and so is focus moving to an error message or to content you asked for. Reply with {{"problems": [{{"step": <int>, "problem": "<what
the site did, as you perceived it>"}}]}}, with an empty list if there were none."""

    def debrief(self, goal: str, out: Outcome) -> list[dict]:
        if self.profile not in ("P1", "P2", "P3") or not out.steps or out.tool_error:
            return []
        steps = "\n".join(f"{s.i}. {json.dumps(s.action)} -> {s.result[:240]}" + (f" [you reported: {s.problem[:100]}]" if s.problem else "")
                          for s in out.steps)
        prompt = (f"{PROFILE_RULES[self.profile]}\n\nTASK: {goal}\n\nYOUR STEPS:\n{steps}\n\n"
                  + self.DEBRIEF.format(status=f"{out.status}{': ' + out.reason[:100] if out.reason else ''}"))
        try:
            got = _as_dict(self.llm.json(self.DEBRIEF_SYSTEM, prompt)).get("problems") or []
        except Exception:
            return []
        valid = {s.i for s in out.steps}
        items = []
        for x in got if isinstance(got, list) else []:
            x = _as_dict(x)
            try:
                i = int(x.get("step"))
            except (TypeError, ValueError):
                continue
            text = str(x.get("problem") or "").strip()[:400]
            if i in valid and text:
                items.append({"step": i, "problem": text})
        return items[:8]

    def run(self, goal: str, start_url: str | None = None) -> Outcome:
        if start_url:
            self.s.goto(start_url)
        try:
            self.start_text = self.s.visible_text(False, 8000)
        except Exception:
            self.start_text = ""
        self.start_fields = form_fields(self.s)
        confirmed = False
        for i in range(self.max_steps):
            obs, images = self.observe()
            self.perceived |= numbers(obs)
            hist ="\n".join(f"{h.i}. {json.dumps(h.action)} -> {h.result}" + (f" [you reported: {h.problem[:100]}]" if h.problem else "")
                            for h in self.history[-10:])
            prompt = (f"{PROFILE_RULES[self.profile]}\n\nTASK: {goal}\n\nYOUR PREVIOUS ACTIONS:\n{hist or '(none)'}\n\n"
                      f"CURRENT OBSERVATION:\n{obs}\n\n{self._no_progress_note()}What is your next action?")
            try:
                reply = _as_dict(self.llm.json(SYSTEM, prompt, images))
            except Exception as e:
                return Outcome(self.profile, "error", "", self.history, str(e)[:200], tool_error=True)  # the model/API failed
            a = _as_dict(reply.get("action"))
            if not a.get("type"):
                try:
                    retry = prompt + '\n\nYour last reply had no "action". Reply again with {"thought": ..., "action": {...}}.'
                    reply = _as_dict(self.llm.json(SYSTEM, retry, images, temperature=0.2))
                    a = _as_dict(reply.get("action"))
                except Exception:
                    a = {}
            problem = str(reply.get("problem") or "").strip()[:400] or None   # v3 (D97)
            if a.get("type") == "done" and not confirmed:
                # Agents claim success they don't have (T4: a stale result read as the answer). One check, once.
                confirmed = True
                obs2, images2 = self.observe()
                self.perceived |= numbers(obs2)
                check = (f"{PROFILE_RULES[self.profile]}\n\nTASK: {goal}\n\nCURRENT OBSERVATION:\n{obs2}\n\n"
                         f"You said you are done (answer: {a.get('answer', '')!r}). Before finishing, compare what the page "
                         "shows now with every value and step the task asks for. If all of it is reflected, reply with done "
                         "again. If not, reply with your next action.")
                try:
                    r2 = _as_dict(self.llm.json(SYSTEM, check, images2))
                    a = _as_dict(r2.get("action")) or a
                    problem = problem or str(r2.get("problem") or "").strip()[:400] or None
                except Exception:
                    pass
            self.t_last = self.s.now()
            if a.get("type") == "done":
                self.history.append(Step(i, obs[:2000], reply.get("thought", ""), a, "done", self.s.page.url, problem=problem))
                return Outcome(self.profile, "done", a.get("answer", ""), self.history)
            if a.get("type") == "stuck":
                self.history.append(Step(i, obs[:2000], reply.get("thought", ""), a, "stuck", self.s.page.url, problem=problem))
                return Outcome(self.profile, "stuck", "", self.history, a.get("reason", ""))
            self.fallback = None
            try:
                result, sel = self.act(a)
            except Exception as e:
                result, sel = f"error: {str(e).splitlines()[0][:120]}", None
            self.perceived |= numbers(result)
            self.history.append(Step(i, obs[:2000], reply.get("thought", ""), a, result, self.s.page.url, sel,
                                     fallback=self.fallback, problem=problem, target=getattr(self, "_target", None),
                                     focus_px=getattr(self, "_focus_px", None)))
            if self._no_progress()[1]:
                if self.on_step:
                    self.on_step(self.history[-1])
                return Outcome(self.profile, "stuck", "", self.history,
                               "kept repeating the same actions with the same results (no progress)")
            if self.on_step:
                self.on_step(self.history[-1])
        return Outcome(self.profile, "max_steps", "", self.history, "ran out of steps")
