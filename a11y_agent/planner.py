"""Planner: given only a URL, explore the app (safely, within a budget) and write tasks a real user would do.

Exploration never submits forms and never clicks anything that looks like login, pay, buy, or delete. It follows
same-site links (including client-side #/routes) and records, per page, the forms, widgets and controls it finds.
The LLM then turns that inventory into task cards. A second LLM call per task (validate_tasks) checks each card:
is it typical, feasible on the pages seen, free of login/payment, concrete, checkable, and is its sequence of steps
consistent with those pages? Invalid cards are dropped and kept in Plan.rejected_tasks. The app profile (which
features each page has) decides which specialist checks will run.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from urllib.parse import urldefrag, urljoin, urlparse

from .browser import Session
from .llm import LLM

DANGER = re.compile(r"\b(log ?in|sign ?in|sign ?up|register|pay|buy now|place order|checkout|delete|remove account|logout|log out|subscribe)\b", re.I)

INVENTORY_JS = """() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const txt = (e) => (e.innerText || e.value || e.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 60);
  const label = (e) => (e.labels && e.labels[0] ? e.labels[0].innerText : (e.getAttribute('aria-label') || e.placeholder || e.name || '')).replace(/\\s+/g, ' ').trim().slice(0, 50);
  const forms = [...document.querySelectorAll('form, [role=search], [role=form]')].filter(vis).slice(0, 6).map(f => ({
    fields: [...f.querySelectorAll('input:not([type=hidden]), select, textarea, [role=combobox], [role=slider]')].filter(vis).slice(0, 12)
      .map(i => ({ kind: i.getAttribute('role') || i.type || i.tagName.toLowerCase(), label: label(i) })),
    buttons: [...f.querySelectorAll('button, input[type=submit]')].filter(vis).slice(0, 4).map(txt) }));
  const widgets = {
    date_picker: !!document.querySelector('[role=grid], input[type=date], [class*=calendar i], [class*=datepicker i], [aria-haspopup=dialog]'),
    combobox: !!document.querySelector('[role=combobox], [aria-autocomplete], datalist'),
    slider: !!document.querySelector('[role=slider], input[type=range]'),
    dialog: !!document.querySelector('[role=dialog], dialog'),
    tabs: !!document.querySelector('[role=tablist]'),
    seat_or_grid_map: document.querySelectorAll('button, [role=button], [role=gridcell]').length > 25,
    colour_legend: !!document.querySelector('[class*=legend i], [aria-label*=legend i]'),
    live_regions: document.querySelectorAll('[aria-live]:not([aria-live=off]), [role=status], [role=alert]').length,
    filters: !!document.querySelector('fieldset input[type=checkbox], [class*=filter i] input[type=checkbox]'),
    images: document.querySelectorAll('main img, img').length,
  };
  const headings = [...document.querySelectorAll('h1, h2, h3')].filter(vis).slice(0, 12).map(h => h.innerText.replace(/\\s+/g, ' ').trim().slice(0, 80));
  const links = [...document.querySelectorAll('a[href]')].filter(vis).slice(0, 120).map(a => ({ text: txt(a), href: a.getAttribute('href') }));
  const buttons = [...document.querySelectorAll('button, [role=button]')].filter(vis).slice(0, 40).map(txt).filter(Boolean);
  return { title: document.title, headings, forms, widgets, links, buttons, text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 1500) };
}"""

PLAN_SYSTEM = """You plan accessibility tests. Given an inventory of a web application, list what it lets users do,
then write concrete tasks that a typical user would want to complete. Tasks must be completable WITHOUT logging in,
paying, or creating anything, and must stop before any such step. Prefer tasks that pass through forms, pickers,
filters, multi-step flows and anything interactive, because those are where barriers hide. Prefer complete
journeys over single clicks: e.g. search, then pick a result, then go on to the next form, stopping only before
login/payment. Give realistic test data (real city names that the site offers, plausible numbers). Any date must be
AFTER the date shown as TODAY below. Never use a date in the past. Reply with ONE JSON object:
{"capabilities": ["..."], "tasks": [{"id": "t1", "goal": "<instruction to a user, one or two sentences, including the test data>",
"start_url": "<url from the inventory>", "success": "<what the screen shows when the task is done>",
"stop_before": "<the step you must not take, if any>", "features": ["form"|"combobox"|"date_picker"|"slider"|"filters"|"dialog"|"seat_or_grid_map"|"colour_coded"|"error_handling"|"dynamic_results"|"images"]}]}"""

VALIDATE_SYSTEM = """You check ONE task card that was written for an accessibility test of a website. A sighted reference user
and then users of assistive technology will carry out the task, and their results are compared. If the task itself is
wrong, that comparison means nothing, so be strict and literal.

You get: TODAY (the date), SITE EXPLORED (the start URL), INVENTORY (one entry per page the explorer visited: headings,
forms with their fields and buttons, widgets, links, buttons, a text excerpt) and the TASK CARD (id, goal, start_url,
success, stop_before, features). Judge the card against the inventory. Do not assume the site has anything the inventory
does not show.

What the inventory cannot show: the explorer only follows links. It never submits a form, never logs in and never pays.
So a page that exists only after a form is submitted (search results, the next step of a booking, a review page) is NOT
in the inventory. A task may use such a page when the visible pages make it plausible, for example a search form that is
followed by results. A step that leads into pages you cannot see is "unknown", not "no". A step is "no" only when the
inventory shows that it cannot work.

First write steps_outline: the steps a user takes to complete the task, starting at start_url, 3 to 10 short steps in
plain words, for example ["open the flight search", "type the origin city", "pick the departure date", "press Search",
"open the cheapest result"]. Write the steps the goal needs; do not repair the goal here.

Then answer six questions. Each answer is {"answer": "yes" or "no", "reason": "<at most 25 words, specific>"}.
1. typical: Is this something a real visitor of this kind of site would plausibly come to do? Answer "no" for busywork
   or trivia that nobody does on such a site (counting words, reading the page source).
2. feasible_here: Do the explored pages show what the task needs (for example a search form with the fields the goal
   mentions), or a clear link to it? Answer "no" if the needed feature is missing, if start_url is not on the explored
   site, or if the task is about another site.
3. no_login_or_payment: Can the task be completed without logging in, paying, creating an account, or submitting
   anything that cannot be undone (placing an order, confirming a booking, sending a message)? Answer "no" if the goal
   contains such a step. Also answer "no" if the task runs up to such a step and neither stop_before nor the goal itself
   names the step at which to stop.
4. concrete: Does the goal contain the specific test data a user would have to enter or choose (cities, dates, amounts,
   names, a product)? Any date must be after TODAY: a date on or before TODAY is "no". Wording such as "some flights",
   "a product" or "a date" with no actual value is "no".
5. checkable: Does success say what the screen shows when the task is done, so that someone looking at the final screen
   could tell whether the task succeeded? An empty success, or one like "it works", is "no".
6. sequence_valid: Walk through steps_outline against the inventory. "yes" if every step is possible with the pages and
   controls the inventory shows. "no" if a step needs a control or page that the inventory shows to be somewhere else or
   absent (for example choosing a seat on a search results page when seats are chosen on their own page), or if the order
   cannot work. "unknown" if the later steps happen on pages you cannot see because they come after a form submission and
   nothing visible contradicts them; say that in the reason. Only this question may be answered "unknown".

verdict:
- "valid": questions 1 to 5 are "yes" and question 6 is "yes" or "unknown".
- "fix": the task is typical and feasible and needs no login or payment, but the card has a fixable problem: a past date,
  missing test data, a success that cannot be checked, a missing stop_before, or steps in the wrong place. Give corrected_task.
- "invalid": the task is not typical, or not feasible on this site, or the goal itself requires a login, a payment or an
  irreversible submit. corrected_task is null.

corrected_task (only for "fix"): the whole repaired card with the same id and the fields goal, start_url, success,
stop_before, features. Change only what is needed. Use values the inventory supports (a start_url from the inventory, city
names the site's form offers, a date after TODAY). features uses only these values: form, combobox, date_picker, slider,
filters, dialog, seat_or_grid_map, colour_coded, error_handling, dynamic_results, images.

Reply with ONE JSON object and nothing else:
{"steps_outline": ["..."], "typical": {"answer": "", "reason": ""}, "feasible_here": {"answer": "", "reason": ""},
"no_login_or_payment": {"answer": "", "reason": ""}, "concrete": {"answer": "", "reason": ""},
"checkable": {"answer": "", "reason": ""}, "sequence_valid": {"answer": "", "reason": ""},
"verdict": "valid" | "fix" | "invalid", "corrected_task": null}"""

VALIDATION_CHECKS = ("typical", "feasible_here", "no_login_or_payment", "concrete", "checkable", "sequence_valid")
CARD_KEYS = ("id", "goal", "start_url", "success", "stop_before", "features")


@dataclass
class TaskCard:
    id: str
    goal: str
    start_url: str
    success: str
    stop_before: str = ""
    features: list = field(default_factory=list)


@dataclass
class Plan:
    url: str
    pages: list
    capabilities: list
    tasks: list
    specialists: dict
    # Cards the validator judged invalid (not typical, not feasible, or needing login/payment); may be missing in a plan.json.
    rejected_tasks: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        """Load a plan.json (rejected_tasks may be missing; unknown keys are ignored)."""
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


def same_site(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    if pa.netloc != pb.netloc:
        return False
    if pb.hostname in ("127.0.0.1", "localhost"):
        # A local copy of a site shares the server with other files: stay in its folder.
        return pa.path.startswith(pb.path.rsplit("/", 1)[0] + "/")
    return True


def explore(session: Session, url: str, budget: int = 12, on_page=None) -> list[dict]:
    """Breadth-first over same-site links; read-only. on_page(i, page) is called after each page is read."""
    queue, seen, pages = [url], set(), []
    while queue and len(pages) < budget:
        u = queue.pop(0)
        key = u if "#/" in u else urldefrag(u)[0]
        if key in seen:
            continue
        seen.add(key)
        try:
            session.goto(u)
            for attempt in range(3):  # a page that redirects while being read: wait, read again
                try:
                    inv = session.page.evaluate(INVENTORY_JS)
                    break
                except Exception as e:
                    if "Execution context was destroyed" not in str(e) or attempt == 2:
                        raise
                    session.settle(1000)
        except Exception as e:
            pages.append({"url": u, "error": str(e)[:120]})
            if on_page:
                on_page(len(pages), pages[-1])
            continue
        inv["url"] = session.page.url
        pages.append(inv)
        if on_page:
            on_page(len(pages), inv)
        for link in inv["links"]:
            href = link["href"] or ""
            if href.startswith(("mailto:", "tel:", "javascript:")) or DANGER.search(link["text"] or ""):
                continue
            nxt = urljoin(session.page.url, href)
            if href.startswith("#") and not href.startswith("#/"):
                continue  # in-page anchors, e.g. skip links
            if same_site(nxt, url) and nxt not in seen:
                queue.append(nxt)
    return pages


def specialists_for(features: set) -> dict:
    """Which specialist checks to switch on, from the features on the task paths."""
    on = {"Reach": True, "Identify-names": True}
    on["Identify-semantic"] = "images" in features
    on["Operate"] = bool(features & {"combobox", "date_picker", "slider", "seat_or_grid_map", "tabs", "dialog"})
    on["Notice"] = bool(features & {"dynamic_results", "dialog", "filters", "combobox", "date_picker"})
    on["Recover"] = bool(features & {"form", "error_handling"})
    on["Colour"] = bool(features & {"colour_coded", "seat_or_grid_map"})
    return on


def compact_inventory(pages: list[dict]) -> list[dict]:
    """The shortened page inventory that goes into the LLM prompts (task writing and task validation)."""
    return [{k: p.get(k) for k in ("url", "title", "headings", "forms", "widgets", "buttons")} |
            {"links": [l for l in (p.get("links") or []) if l["text"]][:40], "text": (p.get("text") or "")[:600]} for p in pages]


def make_validator_llm() -> LLM:
    """Role "validator" uses the navigation model unless A11Y_VALIDATOR_MODEL names another one (ideally a different
    model from the planner's, so the checker does not share the writer's blind spots)."""
    return LLM(model=os.environ.get("A11Y_VALIDATOR_MODEL") or None, role="validator")


def _read_check(reply: dict, name: str) -> tuple[str, str]:
    item = reply.get(name)
    answer, reason = (item.get("answer"), item.get("reason")) if isinstance(item, dict) else (item, "")
    a = {"yes": "yes", "true": "yes", "no": "no", "false": "no", "unknown": "unknown"}.get(str(answer).strip().lower())
    if a is None:
        raise ValueError(f"no usable answer for {name!r}")
    if a == "unknown" and name != "sequence_valid":
        a = "no"  # only the sequence check may be unknown; anything else that cannot be confirmed does not count as shown
    return a, " ".join(str(reason or "").split())[:240]


def _validate_one(card: dict, inventory: str, site: str, today: str, llm: LLM) -> dict:
    shown = {k: card.get(k, [] if k == "features" else "") for k in CARD_KEYS}
    prompt = (f"TODAY: {today}\nSITE EXPLORED: {site}\nINVENTORY (one entry per page visited):\n{inventory}\n\n"
              f"TASK CARD:\n{json.dumps(shown, ensure_ascii=False)}")
    try:
        reply = llm.json(VALIDATE_SYSTEM, prompt)
        checks, reasons = {}, {}
        for name in VALIDATION_CHECKS:
            checks[name], reasons[name] = _read_check(reply, name)
    except Exception as e:  # the plan stays usable; the card is marked as not validated
        return {**card, "validation": {"verdict": "unchecked", "error": f"validator call failed: {str(e)[:160]}"}}
    outline = reply.get("steps_outline")
    outline = [" ".join(str(x).split()) for x in outline if str(x).strip()][:12] if isinstance(outline, list) else []
    said = str(reply.get("verdict") or "").strip().lower()

    # The verdict follows from the checks; the model's own verdict only decides between fix and invalid.
    passes = all(checks[c] == "yes" for c in VALIDATION_CHECKS[:5]) and checks["sequence_valid"] in ("yes", "unknown")
    fixed = reply.get("corrected_task")
    fixed = ({k: fixed.get(k, card.get(k, [] if k == "features" else "")) for k in CARD_KEYS}
             if isinstance(fixed, dict) and fixed.get("goal") and fixed.get("success") else None)
    note = ""
    if fixed:
        fixed["id"] = card["id"]
        if not isinstance(fixed["features"], list):
            fixed["features"] = card.get("features", [])
        if not same_site(urljoin(site, fixed["start_url"] or ""), site):
            fixed["start_url"] = card["start_url"]  # a correction must stay on the explored site
        if all(fixed[k] == card.get(k) for k in CARD_KEYS):
            fixed, note = None, "the validator returned a corrected task identical to the original"
    if passes:
        verdict = "valid"
    elif checks["typical"] == "no" or checks["feasible_here"] == "no" or said == "invalid":
        verdict = "invalid"
    elif fixed:
        verdict = "fix"
    else:
        verdict, note = "invalid", note or "the validator found a fixable problem but gave no corrected task"
    validation = {"verdict": verdict, "checks": checks, "reasons": reasons, "steps_outline": outline}
    if said != verdict:
        validation["model_verdict"] = said or "none"  # the checks overruled what the model wrote in its verdict field
    if note:
        validation["note"] = note
    if verdict == "fix":
        original = {k: card.get(k) for k in CARD_KEYS}
        return {**fixed, "original": original, "validation": validation}
    return {**card, "validation": validation}


def validate_tasks(tasks: list, pages: list[dict], llm: LLM, today: str | None = None, site_url: str = "") -> list[dict]:
    """Check every task card against what the explorer saw (one LLM call per card, role "validator").

    Returns the cards in order, each with a `validation` dict {verdict, checks, reasons, steps_outline}. Verdicts:
    valid; fix (the card fields are replaced by the corrected ones and the old card is kept under `original`);
    invalid (the caller drops it); unchecked (the validator call failed, so the card is kept but flagged).
    `today` is a JS toDateString()-style date; it defaults to the system date."""
    today = today or datetime.date.today().strftime("%a %b %d %Y")
    site = site_url or next((p.get("url", "") for p in pages if p.get("url")), "")
    inventory = json.dumps(compact_inventory(pages), ensure_ascii=False)[:60000]
    cards = [asdict(t) if is_dataclass(t) else dict(t) for t in tasks]
    return [_validate_one(c, inventory, site, today, llm) for c in cards]


def plan(session: Session, url: str, llm: LLM, budget: int = 12, n_tasks: int = 4, on_page=None,
         validate: bool = True, validator_llm: LLM | None = None) -> Plan:
    pages = explore(session, url, budget, on_page)
    compact = compact_inventory(pages)
    today = session.page.evaluate("() => new Date().toDateString()")
    prompt = (f"TODAY: {today}\nSTART URL: {url}\nWrite {n_tasks} tasks. INVENTORY (one entry per page visited):\n"
              + json.dumps(compact, ensure_ascii=False)[:60000])
    answer = llm.json(PLAN_SYSTEM, prompt)
    tasks = [TaskCard(**{k: t.get(k, "" if k != "features" else []) for k in ("id", "goal", "start_url", "success", "stop_before", "features")})
             for t in answer.get("tasks", [])][:n_tasks]
    cards, rejected = [asdict(t) for t in tasks], []
    if validate and cards:
        checked = validate_tasks(cards, pages, validator_llm or make_validator_llm(), today, url)
        cards = [c for c in checked if c["validation"]["verdict"] != "invalid"]
        rejected = [c for c in checked if c["validation"]["verdict"] == "invalid"]
    feats = set().union(*[set(c.get("features") or []) for c in cards]) if cards else set()
    for p in pages:
        w = p.get("widgets") or {}
        feats |= {k for k, v in w.items() if v and k not in ("images", "live_regions")}
    return Plan(url, pages, answer.get("capabilities", []), cards, specialists_for(feats), rejected)
