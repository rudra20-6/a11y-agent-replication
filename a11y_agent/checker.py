"""Deterministic rule checks per user group (no LLM).

Given a task path (steps that a pointer user performs), we replay it once per profile. Before each step we check
the control the step needs (can this profile reach / identify / operate it?); after each step we check what
changed (was this profile told? can they recover from an error?). Site-agnostic: steps come with their own
resolve/execute functions.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from .browser import INTERACTIVE_ROLES, BrowserPool, Session, Viewport
from .config import SETTINGS

PROFILES = ("P1", "P2", "P3", "P4", "P5")
GENERIC_ALT = {"image", "img", "picture", "photo", "graphic", "icon", "banner", "thumbnail", "spacer", "untitled"}
STATE_KEYS = ("pressed", "checked", "selected", "expanded", "valuetext", "value")


@dataclass
class Finding:
    profile: str
    check: str          # Reach / Identify / Operate / Notice / Recover
    sc: str             # WCAG success criteria, or "no SC"
    step: int
    target: str         # human-readable description of the control or region
    message: str
    severity: str       # blocks / degrades
    evidence: dict = field(default_factory=dict)

    def key(self) -> tuple:
        return (self.profile, self.check, self.message.split(":")[0], self.target)


def specialists_of(f: Finding) -> set[str]:
    """Which planner specialists (planner.specialists_for) cover a finding. A finding is kept if any of them is on."""
    if f.check == "Identify" and f.profile == "P4":
        return {"Colour"}
    if f.check == "Identify" and f.sc.startswith("1.1.1"):
        return {"Identify-semantic"}
    if f.check == "Identify":
        return {"Identify-names"}
    if f.check == "Recover" and f.profile == "P4":
        return {"Recover", "Colour"}
    return {f.check}


def select(findings: list[Finding], specialists: dict | None) -> tuple[list[Finding], list[Finding]]:
    """Split findings into (kept, filtered out) by the specialists the planner switched on for this site."""
    if not specialists:
        return findings, []
    kept = [f for f in findings if any(specialists.get(k, True) for k in specialists_of(f))]
    return kept, [f for f in findings if f not in kept]


def words(text: str) -> list[str]:
    return [w for w in re.split(r"[^0-9a-zऀ-ॿ]+", (text or "").lower()) if w]


def reddish(css: str) -> bool:
    m = re.findall(r"[\d.]+", css or "")
    if len(m) < 3:
        return False
    r, g, b = (float(x) for x in m[:3])
    return r > 150 and g < 110 and b < 110


def shape(text: str) -> str:
    """Visible text with digits masked: used to tell categories of sibling controls apart."""
    return re.sub(r"\d", "#", re.sub(r"\s+", " ", (text or "").lower())).strip()


def describe(s: Session, handle) -> str:
    try:
        w = handle.evaluate("e => window.__a11y.visibleWords(e)")
        tag = handle.evaluate("e => e.tagName.toLowerCase() + (e.getAttribute('role') ? '[' + e.getAttribute('role') + ']' : '')")
    except Exception:
        return "?"
    return f'{tag} "{(w or "")[:60]}"'


class PathChecker:
    def __init__(self, pool: BrowserPool):
        self.pool = pool
        # Steps the checker itself could not replay (selector gone, click timed out). These say nothing about the
        # site's accessibility, so they are kept apart from findings and never corroborate an agent stall.
        self.tool_errors: list[dict] = []

    # ----------------------------------------------------------------------------------------------- driver

    def run(self, start_url: str, steps: list, resolve: Callable, execute: Callable,
            profiles=PROFILES, prepare: Callable | None = None) -> list[Finding]:
        out: list[Finding] = []
        for p in profiles:
            out += self.run_profile(p, start_url, steps, resolve, execute, prepare)
        return out

    def run_profile(self, profile, start_url, steps, resolve, execute, prepare=None, progress=None) -> list[Finding]:
        """progress(i, n), if given, is called before each step (for progress events)."""
        vp = Viewport(*SETTINGS.zoom_viewport) if profile == "P3" else Viewport(*SETTINGS.desktop)
        s = self.pool.session(vp)
        if prepare:
            prepare(s)
        findings: list[Finding] = []
        seen_pages: set = set()
        try:
            s.goto(start_url)
            for i, step in enumerate(steps):
                if progress:
                    progress(i, len(steps))
                s.page.mouse.move(0, 0)
                try:
                    target = resolve(s, step)
                except Exception as e:
                    self.tool_errors.append({"profile": profile, "step": i, "where": "resolve", "error": str(e)[:200]})
                    break
                page_key = s.page.url
                try:
                    if page_key not in seen_pages:
                        seen_pages.add(page_key)
                        findings += self.page_checks(profile, s, i)
                    before = self.before(profile, s, target)
                    if target is not None:
                        findings += self.pre_checks(profile, s, i, step, target, before)
                except Exception as e:
                    # The page navigated away during a check (e.g. a form that submits itself when a field changes):
                    # record it and stop this persona's replay instead of losing the whole run.
                    self.tool_errors.append({"profile": profile, "step": i, "where": "check", "error": str(e)[:200]})
                    break
                t0 = s.now()
                try:
                    execute(s, step)
                except Exception as e:
                    msg = str(e)
                    # At 320 px the sighted user's control can sit under a fixed panel. The replay can't
                    # click it because something else is on top: that is evidence for the zoom persona, not a tool fault.
                    if profile == "P3" and target is not None and "intercepts pointer events" in msg:
                        by = re.search(r"<(\w+)[^>]*>", msg.split("intercepts pointer events")[0][-300:])
                        findings.append(Finding("P3", "Reach", "1.4.10, 2.4.11", i, describe(s, target),
                                                "control is covered by another element at 400% zoom (320 px), so it can't be clicked",
                                                "blocks", {"covered_by": by.group(1) if by else "", "error": msg[:160]}))
                    else:
                        self.tool_errors.append({"profile": profile, "step": i, "where": "execute", "error": msg[:200]})
                    break
                s.settle(300)
                findings += self.post_checks(profile, s, i, step, target, before, t0)
        finally:
            s.close()
        # one finding per (profile, check, kind, target)
        uniq, seen = [], set()
        for f in findings:
            if f.key() not in seen:
                seen.add(f.key())
                uniq.append(f)
        return uniq

    # ----------------------------------------------------------------------------------------------- state

    def before(self, profile, s: Session, target) -> dict:
        b = {"snap": s.js("mainSnapshot"), "errors": {e["text"] for e in s.js("visibleErrors")},
             "origin": s.page.evaluate("() => performance.timeOrigin")}
        if target is not None:
            b["desc"] = describe(s, target)  # before the step: a click that navigates detaches the element
            b["ax"] = s.ax_of(target)
            try:
                b["style"] = target.evaluate("e => { const x = getComputedStyle(e); return [x.backgroundColor, x.borderTopColor, x.color].join('|'); }")
            except Exception:
                b["style"] = None
        if profile == "P4":
            b["fields"] = {f["ref"]: f for f in s.js("fieldStyles")}
        return b

    # ----------------------------------------------------------------------------------------------- per page

    def page_checks(self, profile, s: Session, i) -> list[Finding]:
        out = []
        if profile == "P1":
            imgs = s.page.evaluate("""() => [...document.querySelectorAll('main img, [role=main] img')]
              .filter(e => e.getBoundingClientRect().width > 0 && e.getAttribute('aria-hidden') !== 'true' && e.getAttribute('role') !== 'presentation')
              .map(e => ({ alt: e.getAttribute('alt'), ref: window.__a11y.describeEl(e).ref }))""")
            for im in imgs:
                if im["alt"] is None:
                    out.append(Finding("P1", "Identify", "1.1.1", i, "image in main content", "image has no text alternative", "degrades", im))
                elif im["alt"].strip().lower() in GENERIC_ALT or re.search(r"\.(png|jpe?g|gif|webp|svg)$", im["alt"].strip().lower()):
                    out.append(Finding("P1", "Identify", "1.1.1", i, f'image alt="{im["alt"]}"', "image alternative says nothing about the image", "degrades", im))
        if profile == "P3":
            rf = s.js("reflow")
            if rf["needsSideScroll"]:
                out.append(Finding("P3", "Reach", "1.4.10", i, "page", f"needs sideways scrolling at 400% zoom: {rf['scrollWidth']} px of content in a {rf['viewport']} px window",
                                   "blocks", rf))
        return out

    # ----------------------------------------------------------------------------------------------- before a step

    def pre_checks(self, profile, s: Session, i, step, target, b) -> list[Finding]:
        kind = next(iter(step))
        desc = describe(s, target)
        ax = b.get("ax")
        out: list[Finding] = []

        if profile == "P1":
            interactive = ax and not ax["ignored"] and ax["role"] in INTERACTIVE_ROLES
            if not interactive:
                out.append(Finding("P1", "Reach", "4.1.2, 2.1.1", i, desc, "not exposed as a control a screen reader can activate",
                                   "blocks", {"ax_role": ax and ax["role"]}))
            elif not ax["name"]:
                out.append(Finding("P1", "Identify", "4.1.2, 1.3.1", i, desc, "control has no accessible name", "blocks", {"ax": ax}))
            else:
                tree = s.ax_tree(max_lines=100000)
                same = [n for n in tree.interactive() if n["role"] == ax["role"] and n["name"].strip().lower() == ax["name"].strip().lower()]
                if len(same) > 1:
                    out.append(Finding("P1", "Identify", "2.4.6, 2.4.4", i, desc, f'{len(same)} {ax["role"]}s share the name "{ax["name"][:60]}"',
                                       "degrades", {"count": len(same)}))

        if profile == "P2":
            info = target.evaluate("e => window.__a11y.describeEl(e)")
            reached, tabs, seen = target.evaluate("(e, w) => window.__a11y.focusMatches(e, w)", info["widget"]), 0, []
            unfocused = None if reached else target.evaluate("e => window.__a11y.styleSigOf(e)")
            while not reached and tabs < 80:
                s.page.keyboard.press("Tab")
                tabs += 1
                f = s.focus_info()
                ref = f and f["ref"]
                if ref in seen[-60:] and seen.count(ref) >= 2:
                    break  # cycled
                seen.append(ref)
                reached = target.evaluate("(e, w) => window.__a11y.focusMatches(e, w)", info["widget"])
            if not reached:
                out.append(Finding("P2", "Reach", "2.1.1", i, desc, "can't be reached with the keyboard (Tab never lands on it)",
                                   "blocks", {"tabs": tabs}))
            else:
                act = s.js("activeStyle")
                same_el = target.evaluate("e => document.activeElement === e")
                fv = {"unfocused": unfocused, "focused": act and act["sig"]}
                if act and unfocused and same_el and act["sig"] == unfocused and act["outlineNone"]:
                    out.append(Finding("P2", "Reach", "2.4.7", i, desc, "keyboard focus is invisible on this control", "blocks", fv))
                ob = s.js("focusObscured")
                if ob and ob.get("obscured"):
                    out.append(Finding("P2", "Reach", "2.4.11", i, desc, f"focused control is hidden under {ob.get('by')!s:.40}", "degrades", ob))
                role = (ax or {}).get("role", "")
                if info["widget"] and role in ("gridcell", "option", "ListBoxOption", "tab", "menuitem", "treeitem"):
                    out += self.key_probe(s, i, desc, info["widget"], role)

        if profile == "P3" and kind in ("click", "select"):
            hr = target.evaluate("""e => { const r = e.getBoundingClientRect(); window.scrollTo(window.scrollX, window.scrollY + r.top - innerHeight / 3);
                                         const q = e.getBoundingClientRect(); return { left: q.left, right: q.right, vw: innerWidth }; }""")
            if hr["left"] < -1 or hr["right"] > hr["vw"] + 1:
                out.append(Finding("P3", "Reach", "1.4.10", i, desc, "control is outside the visible width at 400% zoom", "blocks", hr))

        if profile == "P4" and kind == "click":
            sibs = s.js("siblingColours", target)
            groups: dict = {}
            for x in sibs:
                groups.setdefault(x["colour"], []).append(shape(x["words"]))
            colours = [c for c, members in groups.items() if len(members) >= 2]
            for a in range(len(colours)):
                for c in colours[a + 1:]:
                    if set(groups[colours[a]]) & set(groups[c]):
                        out.append(Finding("P4", "Identify", "1.4.1", i, desc,
                                           "options next to this control differ only by colour (same visible text and symbols)", "blocks",
                                           {"groups": {k: v[:3] for k, v in groups.items()}}))
                        break

        if profile == "P5":
            label = target.evaluate("e => window.__a11y.visibleWords(e)") or ""
            lw = words(label)
            name = (ax or {}).get("name", "") if ax and not ax["ignored"] else ""
            interactive = ax and not ax["ignored"] and ax["role"] in INTERACTIVE_ROLES
            if not lw:
                if not name:
                    out.append(Finding("P5", "Reach", "4.1.2", i, desc, "nothing to say: no visible label and no name", "blocks"))
            elif not interactive:
                out.append(Finding("P5", "Reach", "4.1.2", i, desc, f'"click {label[:40]}" finds no control (not exposed as one)', "blocks"))
            elif not set(lw) <= set(words(name)):
                out.append(Finding("P5", "Identify", "2.5.3", i, desc, f'visible label "{label[:40]}" is not in its name "{name[:40]}"', "blocks",
                                   {"label": label, "name": name}))
        return out

    def key_probe(self, s: Session, i, desc, widget_ref, role) -> list[Finding]:
        sig = """(w) => { const el = document.querySelector(`[data-aa-id="${w.slice(3)}"]`); const a = document.activeElement;
                   return [a && a.dataset ? a.dataset.aaId : '', el && el.getAttribute('aria-activedescendant'),
                           el ? [...el.querySelectorAll('[aria-selected=true]')].map(x => x.dataset.aaId || x.id).join() : ''].join('|'); }"""
        key = "ArrowDown" if role in ("option", "ListBoxOption", "treeitem", "menuitem") else "ArrowRight"
        before = s.page.evaluate(sig, widget_ref)
        s.page.keyboard.press(key)
        s.page.wait_for_timeout(200)
        after = s.page.evaluate(sig, widget_ref)
        if before == after:
            return [Finding("P2", "Operate", "2.1.1", i, desc, f"{key} does nothing inside this widget", "blocks", {"key": key}),
                    Finding("P1", "Operate", "2.1.1", i, desc, f"{key} does nothing inside this widget", "blocks", {"key": key, "via": "P2 probe"})]
        return []

    # ----------------------------------------------------------------------------------------------- after a step

    def post_checks(self, profile, s: Session, i, step, target, b, t0) -> list[Finding]:
        kind = next(iter(step))
        if kind in ("press", "wait") or profile in ("P3", "P5"):
            return []
        desc = b.get("desc") or (describe(s, target) if target is not None else "page")
        after = s.js("mainSnapshot")
        new_words = set(words(after["text"])) - set(words(b["snap"]["text"]))
        new_dialogs = [d for d in after["dialogs"] if d not in b["snap"]["dialogs"]]
        new_errors = [e for e in s.js("visibleErrors") if e["text"] not in b["errors"]]
        out: list[Finding] = []

        if profile == "P2" and new_dialogs and not any(s.js("focusInside", d) for d in new_dialogs):
            out.append(Finding("P2", "Notice", "2.4.3", i, desc, "a dialog opened but keyboard focus stayed behind it", "blocks"))

        if profile == "P4" and kind == "click":
            for f in s.js("fieldStyles"):
                old = b.get("fields", {}).get(f["ref"])
                newly_wrong = (f["invalid"] and not old["invalid"]) or (old["border"] != f["border"] and reddish(f["border"])) if old else False
                if newly_wrong and set(words(f["words"])) <= set(words(old["words"])):
                    out.append(Finding("P4", "Recover", "1.4.1, 3.3.1", i, describe(s, s.page.query_selector(f'[data-aa-id="{f["ref"][3:]}"]')),
                                       "field marked as wrong only by colour (no visible message)", "blocks", {"border": [old["border"], f["border"]]}))

        if profile != "P1" or kind == "fill":
            return out
        if s.page.evaluate("() => performance.timeOrigin") != b.get("origin"):
            return out  # a full page load: a screen reader announces the new page itself

        # Wait briefly for a polite announcement if something visible changed.
        significant = len(new_words) >= 3 or new_dialogs or after["hash"] != b["snap"]["hash"]
        anns = s.announcements(t0)
        deadline = time.time() + 1.5
        while significant and not anns and time.time() < deadline:
            s.page.wait_for_timeout(250)
            anns = s.announcements(t0)
        f = s.focus_info()
        focus_new = bool(f) and (any(s.js("focusInside", d) for d in new_dialogs) or
                                 bool(set(words(f.get("name", ""))) & new_words) or
                                 (after["hash"] != b["snap"]["hash"] and f.get("tag") in ("h1", "main")))

        if new_dialogs and not any(s.js("focusInside", d) for d in new_dialogs):
            out.append(Finding("P1", "Notice", "2.4.3", i, desc, "a dialog opened but focus stayed behind it", "blocks", {"dialogs": new_dialogs}))
            return out

        if new_errors:
            invalid_now = after["invalid"]
            told = bool(anns) or focus_new
            if not told or not invalid_now:
                missing = [m for m, ok in (("not announced", told), ("not tied to the field (no aria-invalid / description)", bool(invalid_now))) if not ok]
                out.append(Finding("P1", "Recover", "3.3.1, 4.1.3", i, desc, "error appeared but " + " and ".join(missing), "blocks",
                                   {"errors": [e["text"] for e in new_errors][:3], "announcements": anns[-3:]}))
            return out

        if significant and not anns and not focus_new:
            sev = "blocks" if new_dialogs else "degrades"
            out.append(Finding("P1", "Notice", "4.1.3", i, desc, "the page changed but a screen-reader user isn't told", sev,
                               {"new_words": sorted(new_words)[:12], "dialogs": new_dialogs}))

        # Visual-only state change on the control itself (e.g. a seat turns green but nothing says "selected").
        if target is not None and b.get("ax") and b.get("style"):
            try:
                connected = target.evaluate("e => e.isConnected")
            except Exception:
                connected = False
            if connected:
                if ax_role_of(b["ax"]) in ("textbox", "combobox", "searchbox"):
                    return out
                target.evaluate("e => e.blur()")
                style_after = target.evaluate("e => { const x = getComputedStyle(e); return [x.backgroundColor, x.borderTopColor, x.color].join('|'); }")
                ax_after = s.ax_of(target) or {}
                state_b = {k: b["ax"]["props"].get(k) for k in STATE_KEYS}
                state_a = {k: ax_after.get("props", {}).get(k) for k in STATE_KEYS}
                if style_after != b["style"] and state_a == state_b and ax_after.get("role") in ("button", "gridcell", "option", "tab", "menuitem", "link"):
                    out.append(Finding("P1", "Notice", "4.1.2", i, desc, "its look changed (e.g. selected) but no state is exposed", "degrades",
                                       {"style": [b["style"], style_after]}))
        return out


def ax_role_of(ax: dict | None) -> str:
    return (ax or {}).get("role", "")


def findings_to_dicts(fs: list[Finding]) -> list[dict]:
    return [asdict(f) for f in fs]
