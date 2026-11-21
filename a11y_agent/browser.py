"""Browser session: Playwright page plus the CDP calls the profiles need.

Everything here is site-agnostic. Elements are referred to by `ref` strings:
- "ax:<backendNodeId>" for accessibility-tree nodes (what a screen reader sees)
- "el:<n>" for DOM elements tagged by our in-page helper (what a sighted user sees)
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .config import SETTINGS

HELPER_JS = (Path(__file__).parent / "page_helper.js").read_text(encoding="utf-8")


@dataclass
class Viewport:
    width: int
    height: int


class BrowserPool:
    """One Playwright + browser process, shared by many sessions."""

    def __init__(self, headless: bool | None = None):
        self._pw = sync_playwright().start()
        kwargs = {"headless": SETTINGS.headless if headless is None else headless,
                  "args": ["--disable-blink-features=AutomationControlled"]}
        if SETTINGS.browser_channel:
            kwargs["channel"] = SETTINGS.browser_channel
        self.browser: Browser = self._pw.chromium.launch(**kwargs)

    def session(self, viewport: Viewport, vision_deficiency: str | None = None) -> "Session":
        ctx = self.browser.new_context(
            viewport={"width": viewport.width, "height": viewport.height},
            user_agent=SETTINGS.user_agent, locale="en-IN", bypass_csp=True,
        )
        return Session(ctx, vision_deficiency)

    def close(self) -> None:
        self.browser.close()
        self._pw.stop()


class Session:
    def __init__(self, ctx: BrowserContext, vision_deficiency: str | None = None):
        self.ctx = ctx
        self.screenshot_error = ""  # why the last failed screenshot failed (empty if none has)
        ctx.add_init_script(HELPER_JS)
        self.page: Page = ctx.new_page()
        self.cdp = ctx.new_cdp_session(self.page)
        self.cdp.send("Accessibility.enable")
        self.cdp.send("DOM.enable")
        if vision_deficiency:
            self.cdp.send("Emulation.setEmulatedVisionDeficiency", {"type": vision_deficiency})

    # ------------------------------------------------------------ navigation

    def goto(self, url: str) -> None:
        # A refused or reset connection on the first load is the network or server, not the site's accessibility: try
        # again before giving up. A load that times out is retried too, after a longer pause.
        for attempt in range(3):
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                break
            except Exception as e:
                timed_out = "Timeout" in str(e) and "exceeded" in str(e)
                if attempt == 2 or not (timed_out or any(c in str(e) for c in (
                        "ERR_CONNECTION_REFUSED", "ERR_CONNECTION_RESET", "ERR_NETWORK_CHANGED", "ERR_INTERNET_DISCONNECTED"))):
                    raise
                self.page.wait_for_timeout((15000 if timed_out else 3000) * (attempt + 1))
        self.settle(1500)

    def settle(self, ms: int | None = None) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        self.page.wait_for_timeout(ms if ms is not None else SETTINGS.settle_ms)

    def close(self) -> None:
        self.ctx.close()

    # ------------------------------------------------------------ in-page helper

    def js(self, fn: str, *args):
        """Call a function exported by page_helper.js. A page that navigates mid-call (a redirect, a bot check reloading
        itself) destroys the context: wait for the new page and try again."""
        for attempt in range(3):
            try:
                return self.page.evaluate(f"(args) => window.__a11y.{fn}(...args)", list(args))
            except Exception as e:
                if "Execution context was destroyed" not in str(e) or attempt == 2:
                    raise
                self.settle(500)

    # ------------------------------------------------------------ accessibility tree

    def ax_nodes(self) -> list[dict]:
        self.cdp.send("DOM.getDocument", {"depth": -1})
        return self.cdp.send("Accessibility.getFullAXTree")["nodes"]

    def ax_tree(self, max_lines: int = 700) -> "AXTree":
        return AXTree(self.ax_nodes(), max_lines=max_lines)

    def _object_for(self, backend_id: int) -> str:
        return self.cdp.send("DOM.resolveNode", {"backendNodeId": backend_id})["object"]["objectId"]

    def element_for_ref(self, ref: str):
        """Return a Playwright ElementHandle for an ax:/el: ref (or None if gone)."""
        if ref.startswith("el:"):
            return self.page.query_selector(f'[data-aa-id="{ref[3:]}"]')
        if ref.startswith("ax:"):
            try:
                obj = self._object_for(int(ref[3:]))
            except Exception:
                return None
            # Mark it so Playwright can find it, then clear the mark.
            self.cdp.send("Runtime.callFunctionOn", {
                "objectId": obj,
                "functionDeclaration": "function(){ const e = this.nodeType === 1 ? this : this.parentElement; "
                                       "document.querySelectorAll('[data-aa-target]').forEach(x => x.removeAttribute('data-aa-target')); "
                                       "if (e) e.setAttribute('data-aa-target', '1'); }",
            })
            return self.page.query_selector('[data-aa-target="1"]')
        return None

    def ax_of(self, handle) -> dict | None:
        """The accessibility node Chrome exposes for a DOM element (what a screen reader gets for it)."""
        try:
            handle.evaluate("e => e.setAttribute('data-aa-probe', '1')")
            root = self.cdp.send("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
            nid = self.cdp.send("DOM.querySelector", {"nodeId": root, "selector": "[data-aa-probe='1']"})["nodeId"]
            handle.evaluate("e => e.removeAttribute('data-aa-probe')")
            if not nid:
                return None
            bid = self.cdp.send("DOM.describeNode", {"nodeId": nid})["node"]["backendNodeId"]
            nodes = self.cdp.send("Accessibility.getPartialAXTree", {"backendNodeId": bid, "fetchRelatives": False})["nodes"]
        except Exception:
            return None
        if not nodes:
            return None
        n = next((x for x in nodes if x.get("backendDOMNodeId") == bid), nodes[0])
        val = lambda k: (n.get(k) or {}).get("value") if isinstance(n.get(k), dict) else n.get(k)
        props = {p["name"]: p["value"].get("value") for p in n.get("properties", [])}
        return {"ref": f"ax:{bid}", "ignored": bool(n.get("ignored")), "role": val("role") or "",
                "name": (val("name") or "").strip(), "props": props}

    # ------------------------------------------------------------ observations

    def screenshot(self, path: Path | None = None, full_page: bool = False, timeout: int = 10000) -> bytes:
        """PNG bytes, or b"" if the browser could not take one. A slow page (Playwright's "waiting for fonts to load"
        timeout) must not end a run: one retry, then give up quietly. Callers treat b"" as "no image"."""
        png = b""
        for attempt in range(2):
            try:
                png = self.page.screenshot(full_page=full_page, timeout=timeout)
                break
            except Exception as e:
                self.screenshot_error = str(e).splitlines()[0][:160] if str(e) else type(e).__name__
                if attempt == 0:
                    try:
                        self.page.wait_for_timeout(500)
                    except Exception:
                        pass
        if png and path:
            path.write_bytes(png)
        return png

    def focus_info(self) -> dict | None:
        return self.js("focusInfo")

    def announcements(self, since: float = 0) -> list[dict]:
        return self.js("announcements", since)

    def now(self) -> float:
        return self.page.evaluate("() => performance.now()")

    def visible_text(self, viewport_only: bool = False, limit: int = 4000) -> str:
        return self.js("visibleText", viewport_only, limit)

    def interactive_elements(self, viewport_only: bool = False) -> list[dict]:
        """What a sighted pointer user can act on (incl. clickable divs), tagged with el: refs."""
        return self.js("interactiveElements", viewport_only)


# ---------------------------------------------------------------------- AX tree

INTERACTIVE_ROLES = {
    "button", "link", "checkbox", "radio", "tab", "option", "menuitem", "menuitemcheckbox", "menuitemradio",
    "combobox", "textbox", "searchbox", "slider", "spinbutton", "switch", "listbox", "gridcell", "treeitem",
    "ListBoxOption", "MenuListOption", "PopUpButton", "TextField",
}
STATE_PROPS = ("focused", "disabled", "checked", "pressed", "selected", "expanded", "invalid", "required",
               "readonly", "haspopup", "level", "valuetext", "focusable", "hidden")
SKIP_ROLES = {"generic", "none", "presentation", "LineBreak", "InlineTextBox", "StaticText", "ignored"}


class AXTree:
    """Chrome's accessibility tree, pruned and serialised for agents and checks."""

    def __init__(self, raw: list[dict], max_lines: int = 700):
        self.raw = raw
        self.by_id = {n["nodeId"]: n for n in raw}
        self.max_lines = max_lines
        self.nodes: list[dict] = []  # flattened, pruned, in reading order
        roots = [n for n in raw if not n.get("parentId")]
        for r in roots:
            self._walk(r, 0)

    @staticmethod
    def _val(n: dict, key: str):
        v = n.get(key)
        return v.get("value") if isinstance(v, dict) else v

    def _props(self, n: dict) -> dict:
        out = {}
        for p in n.get("properties", []):
            if p["name"] in STATE_PROPS:
                out[p["name"]] = p["value"].get("value")
        return out

    def _walk(self, n: dict, depth: int) -> None:
        if n.get("ignored"):
            for cid in n.get("childIds", []):
                if cid in self.by_id:
                    self._walk(self.by_id[cid], depth)
            return
        role = self._val(n, "role") or ""
        name = (self._val(n, "name") or "").strip()
        props = self._props(n)
        keep = role not in SKIP_ROLES or (role == "StaticText" and name and not self._parent_has_name(n, name))
        if role in ("RootWebArea", "WebArea"):
            keep = True
        if keep:
            self.nodes.append({
                "ref": f"ax:{n['backendDOMNodeId']}" if n.get("backendDOMNodeId") else None,
                "role": role, "name": name, "depth": depth,
                "value": (self._val(n, "value") or ""),
                "description": (self._val(n, "description") or ""),
                "props": props,
                "interactive": role in INTERACTIVE_ROLES or bool(props.get("focusable") and role not in ("RootWebArea", "WebArea")),
            })
            depth += 1
        for cid in n.get("childIds", []):
            if cid in self.by_id:
                self._walk(self.by_id[cid], depth)

    def _parent_has_name(self, n: dict, name: str) -> bool:
        pid = n.get("parentId")
        while pid and pid in self.by_id:
            p = self.by_id[pid]
            if not p.get("ignored") and (self._val(p, "role") or "") not in SKIP_ROLES:
                return (self._val(p, "name") or "").strip() == name
            pid = p.get("parentId")
        return False

    def interactive(self) -> list[dict]:
        return [n for n in self.nodes if n["interactive"] and n["ref"]]

    def find(self, ref: str) -> dict | None:
        return next((n for n in self.nodes if n["ref"] == ref), None)

    def serialise(self, focus_ref: str | None = None) -> str:
        """Indented text, one node per line: `[ax:12] button "Search" (focused, expanded=false)`."""
        lines = []
        for n in self.nodes:
            st = []
            for k, v in n["props"].items():
                if k in ("focusable",):
                    continue
                if v is True:
                    st.append(k)
                elif v not in (False, None, "", "false"):
                    st.append(f"{k}={v}")
            if n["value"] and n["role"] not in ("StaticText",):
                st.append(f'value="{str(n["value"])[:40]}"')
            ref = f'[{n["ref"]}] ' if n["interactive"] and n["ref"] else ""
            label = "text" if n["role"] == "StaticText" else n["role"]
            name = f' "{n["name"][:120]}"' if n["name"] else ""
            lines.append("  " * min(n["depth"], 12) + f"{ref}{label}{name}" + (f" ({', '.join(st)})" if st else ""))
        if len(lines) > self.max_lines:
            # Keep the region around focus plus the start: screen-reader users can always jump around.
            fi = next((i for i, l in enumerate(lines) if "(focused" in l or ", focused" in l), 0)
            head = lines[: self.max_lines // 3]
            lo = max(len(head), fi - self.max_lines // 3)
            mid = lines[lo: lo + 2 * self.max_lines // 3]
            lines = head + [f"... ({lo - len(head)} lines omitted) ..."] + mid + ["... (more below) ..."]
        return "\n".join(lines)
