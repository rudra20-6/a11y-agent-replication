// Injected into every page before it loads. Site-agnostic observation helpers.
(() => {
  if (window.__a11y) return;
  const log = [];          // announcements (what a screen reader would be told)
  const focusLog = [];     // focus movements
  let nextId = 1;
  let inField = null;      // v3.1 (D108): the text field whose change/input event is being handled
  const mark = (k, v) => { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (_) {} };
  try {
    const submit0 = HTMLFormElement.prototype.submit;
    HTMLFormElement.prototype.submit = function () {
      if (inField && performance.now() - inField.t < 200) mark('__aaChangeNav', { t: Date.now(), name: inField.name });
      return submit0.apply(this, arguments);
    };
  } catch (_) {}

  const visible = (e) => {
    if (!e || !e.getBoundingClientRect) return false;
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const s = getComputedStyle(e);
    return s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.01;
  };
  // v2.4 (D86, H03): text cut off by an ancestor with overflow other than visible (e.g. a fare clipped to its card)
  // is in the DOM and in the viewport, but a sighted user can't read it.
  const clippedOut = (textNode) => {
    const rg = document.createRange();
    rg.selectNodeContents(textNode);
    const t = rg.getBoundingClientRect();
    if (t.width <= 0 || t.height <= 0) return false;
    for (let a = textNode.parentElement; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
      const r = a.getBoundingClientRect();
      const ix = Math.min(t.right, r.right) - Math.max(t.left, r.left);
      const iy = Math.min(t.bottom, r.bottom) - Math.max(t.top, r.top);
      if (ix <= 1 || iy <= 1) return true;
    }
    return false;
  };
  const tag = (e) => {
    if (!e.dataset.aaId) e.dataset.aaId = String(nextId++);
    return 'el:' + e.dataset.aaId;
  };
  const clean = (t) => (t || '').replace(/\s+/g, ' ').trim();
  // A rough accessible-name approximation, used only for logs; real names come from the AX tree.
  const roughName = (e) => clean(e.getAttribute('aria-label') ||
      (e.labels && e.labels[0] && e.labels[0].innerText) || e.getAttribute('title') ||
      e.getAttribute('alt') || e.innerText || e.value || e.getAttribute('placeholder') || '').slice(0, 80);

  const liveSel = '[aria-live]:not([aria-live="off"]), [role="status"], [role="alert"], [role="log"]';
  const record = (region, kind) => {
    // v2.4 (D86, H08): a screen reader never announces a live region inside aria-hidden content.
    if (region.closest && region.closest('[aria-hidden="true"]')) return;
    const text = clean(region.innerText || region.textContent);
    if (!text) return;
    const last = log[log.length - 1];
    if (last && last.text === text && performance.now() - last.t < 300) return;
    log.push({ t: performance.now(), text: text.slice(0, 300), kind,
               politeness: region.getAttribute('aria-live') || (region.getAttribute('role') === 'alert' ? 'assertive' : 'polite') });
  };
  const observe = () => {
    const mo = new MutationObserver((muts) => {
      for (const m of muts) {
        const target = m.target.nodeType === 1 ? m.target : m.target.parentElement;
        if (!target) continue;
        const region = target.closest && target.closest(liveSel);
        if (region) record(region, 'live');
        for (const n of m.addedNodes || []) {
          if (n.nodeType === 1 && n.matches && n.matches('[role="alert"], [role="alertdialog"]')) record(n, 'alert');
        }
      }
    });
    mo.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: false });
    document.addEventListener('focusin', (ev) => {
      const e = ev.target;
      focusLog.push({ t: performance.now(), ref: e.dataset ? tag(e) : null, tag: e.tagName ? e.tagName.toLowerCase() : null, name: roughName(e) });
    }, true);
    // v3.1 (D108): a page that changes context on input (Ma11y F36: the field's onchange calls form.submit()). The page
    // helper wraps HTMLFormElement.submit (top of this file); a call made while a text field's change/input event is being handled
    // is recorded in sessionStorage, which survives the reload. A submit button, Enter's implicit submission and a
    // link are not recorded: they are requested by the user.
    const fieldEvent = (ev) => {
      const e = ev.target;
      if (e && e.tagName === 'INPUT' && !['checkbox', 'radio', 'submit', 'button', 'file', 'range'].includes(e.type))
        inField = { name: roughName(e), t: performance.now() };
    };
    for (const k of ['change', 'input']) {
      document.addEventListener(k, fieldEvent, true);
      window.addEventListener(k, () => { inField = null; }, false);
    }
  };
  if (document.documentElement) observe(); else document.addEventListener('DOMContentLoaded', observe);

  const styleSig = (e) => {
    const s = getComputedStyle(e);
    return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderColor, s.borderWidth,
            s.backgroundColor, s.color, s.textDecorationLine].join('|');
  };

  window.__a11y = {
    announcements: (since) => log.filter(x => x.t > since),
    focusLog: (since) => focusLog.filter(x => x.t > since),

    focusInfo: () => {
      const e = document.activeElement;
      if (!e || e === document.body || e === document.documentElement) return null;
      const r = e.getBoundingClientRect();
      return { ref: tag(e), tag: e.tagName.toLowerCase(), role: e.getAttribute('role'), name: roughName(e),
               rect: [r.left, r.top, r.width, r.height],
               inViewport: r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth,
               editable: e.isContentEditable || ['input', 'textarea', 'select'].includes(e.tagName.toLowerCase()) };
    },

    visibleText: (viewportOnly, limit) => {
      if (!viewportOnly) return clean(document.body ? document.body.innerText : '').slice(0, limit);
      const out = [];
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) {
        const p = n.parentElement;
        if (!p || !clean(n.textContent)) continue;
        const r = p.getBoundingClientRect();
        if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
        if (!visible(p)) continue;
        if (clippedOut(n)) continue;
        out.push(clean(n.textContent));
        if (out.join(' ').length > limit) break;
      }
      return out.join(' ').slice(0, limit);
    },

    interactiveElements: (viewportOnly) => {
      const sel = 'a[href], button, input, select, textarea, summary, [role=button], [role=link], [role=checkbox], [role=radio], ' +
                  '[role=tab], [role=option], [role=menuitem], [role=switch], [role=slider], [role=combobox], [role=gridcell], [onclick], ' +
                  // tabindex=-1 marks a focus target (a skip-link <main>, a heading the router focuses), not a control; as a
                  // candidate it hid every pointer-cursor control inside it from sighted agents (D67)
                  '[tabindex]:not([tabindex="-1"])';
      const cands = new Set(document.querySelectorAll(sel));
      // Things that *look* clickable to a sighted user, even if nothing tells the browser so.
      for (const e of document.querySelectorAll('div, span, li, img, svg, td, p, label')) {
        if (getComputedStyle(e).cursor === 'pointer') cands.add(e);
      }
      const out = [];
      for (const e of cands) {
        if (!visible(e)) continue;
        // Skip a pointer-cursor child if an ancestor is already a candidate (one target per control).
        let p = e.parentElement, nested = false;
        while (p) { if (cands.has(p) && getComputedStyle(e).cursor === 'pointer' && !e.matches(sel)) { nested = true; break; } p = p.parentElement; }
        if (nested) continue;
        const r = e.getBoundingClientRect();
        const inView = r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth;
        if (viewportOnly && !inView) continue;
        // v2.5 (D95): a styled radio/checkbox (GOV.UK, NHS) hides the real input and draws its state on the label, so the
        // label carries the drawn state; listing it without one sent REF clicking "Yes" until it gave up.
        const hiddenCtl = e.tagName === 'LABEL' && e.control && ['checkbox', 'radio'].includes(e.control.type) && !visible(e.control);
        out.push({ ref: tag(e), tag: e.tagName.toLowerCase(), role: e.getAttribute('role'), type: e.type || null,
                   text: roughName(e), checked: e.checked === true || (hiddenCtl && e.control.checked),   // v2.4 (D86, N3): visual personas get drawn state only; ARIA state is P1's (AX tree)
                   disabled: e.disabled === true || e.getAttribute('aria-disabled') === 'true',
                   value: (e.value !== undefined && e.tagName !== 'BUTTON') ? String(e.value).slice(0, 40) : null,
                   rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], inView });
        if (out.length >= 300) break;
      }
      return out;
    },

    // Focus visibility (WCAG 2.4.7): style of the focused element vs the same element blurred.
    focusStyleDiff: () => {
      const e = document.activeElement;
      if (!e || e === document.body) return null;
      const focused = styleSig(e);
      const s = getComputedStyle(e);
      const outlineNone = s.outlineStyle === 'none' || parseFloat(s.outlineWidth) === 0;
      e.blur();
      const blurred = styleSig(e);
      e.focus({ preventScroll: true });
      return { changed: focused !== blurred, outlineNone, ref: tag(e) };
    },

    // Focus not obscured (WCAG 2.4.11): is something else painted on top of the focused element?
    focusObscured: () => {
      const e = document.activeElement;
      if (!e || e === document.body) return null;
      const r = e.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return { obscured: false, offscreen: true };
      const pts = [[0.5, 0.5], [0.15, 0.5], [0.85, 0.5]];
      let covered = 0, inside = 0, by = null;
      for (const [fx, fy] of pts) {
        const x = r.left + r.width * fx, y = r.top + r.height * fy;
        if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) continue;
        inside++;
        const top = document.elementFromPoint(x, y);
        if (top && top !== e && !e.contains(top) && !top.contains(e) && !(e.labels && [...e.labels].some(l => l.contains(top)))) {
          // Ignore elements that are part of the same control (e.g. a label overlay inside the same wrapper).
          const fixed = (n) => { while (n && n !== document.body) { const p = getComputedStyle(n).position; if (p === 'fixed' || p === 'sticky') return true; n = n.parentElement; } return false; };
          if (fixed(top)) { covered++; by = roughName(top) || top.tagName.toLowerCase(); }
        }
      }
      return { obscured: inside > 0 && covered === inside, offscreen: inside === 0, by };
    },

    styleSigOf: (el) => styleSig(el),
    // v3.1 (D104): would a sighted keyboard user see where focus is? Any drawn indicator counts, not only an outline: a
    // box-shadow ring, a ring drawn on the label of a hidden radio/checkbox (GOV.UK), or a background, colour, border
    // or underline that differs from an unfocused neighbour of the same kind (a highlighted suggestion). Without a
    // neighbour to compare with, a missing outline and shadow counts as not shown. No blur/refocus (that would close
    // open suggestion lists while the persona is using them).
    focusShown: () => {
      const e = document.activeElement;
      if (!e || e === document.body || e === document.documentElement) return null;
      const ring = (c) => (c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0) || (c.boxShadow && c.boxShadow !== 'none');
      const s = getComputedStyle(e);
      if (ring(s)) return true;
      for (const l of (e.labels || [])) {
        if (ring(getComputedStyle(l))) return true;
        for (const ps of ['::before', '::after']) if (ring(getComputedStyle(l, ps))) return true;
      }
      const sib = e.parentElement && [...e.parentElement.children].find((x) => x !== e && x.tagName === e.tagName && visible(x));
      const host = !sib && e.parentElement && e.parentElement.parentElement &&
        [...e.parentElement.parentElement.children].map((x) => x.firstElementChild).find((x) => x && x !== e && x.tagName === e.tagName && visible(x));
      const other = sib || host;
      if (!other) return false;
      const t = getComputedStyle(other);
      return ['backgroundColor', 'color', 'borderTopColor', 'borderTopWidth', 'textDecorationLine', 'fontWeight'].some((k) => s[k] !== t[k]);
    },

    // v3.1 (D108): read and clear the unload record (see the listeners in observe()). 'leftField' is the name of the field
    // whose committed value reloaded the page, or null.
    unloadCause: (clear) => {
      let rec = null;
      try { rec = JSON.parse(sessionStorage.getItem('__aaChangeNav') || 'null'); } catch (_) {}
      if (clear) { try { sessionStorage.removeItem('__aaChangeNav'); } catch (_) {} }
      return { leftField: rec ? (rec.name || '') : null };
    },

    activeStyle: () => { const e = document.activeElement; if (!e || e === document.body) return null;
      const s = getComputedStyle(e); return { sig: styleSig(e), outlineNone: s.outlineStyle === 'none' || parseFloat(s.outlineWidth) === 0 }; },

    reflow: () => {
      const sw = document.documentElement.scrollWidth, vw = innerWidth;
      return { viewport: vw, scrollWidth: sw, needsSideScroll: sw > vw + 2 };
    },

    rectOf: (ref) => {
      const e = document.querySelector(`[data-aa-id="${ref.slice(3)}"]`);
      if (!e) return null;
      const r = e.getBoundingClientRect();
      return [r.left, r.top, r.width, r.height];
    },

    // Elements the task needs: is a sighted user's target inside the visible width?
    horizontallyReachable: (ref) => {
      const e = document.querySelector(`[data-aa-id="${ref.slice(3)}"]`);
      if (!e) return null;
      const r = e.getBoundingClientRect();
      return { left: r.left, right: r.right, viewport: innerWidth, reachable: r.left >= 0 && r.right <= innerWidth + 1 };
    },

    tagSelector: (sel) => { const e = document.querySelector(sel); return e ? tag(e) : null; },

    // ---------------------------------------------------------------- helpers for the step checks

    // Words a sighted user can actually see inside el (excludes visually-hidden/clipped text and aria-hidden icons stay in).
    visibleWords: (el) => {
      const out = [];
      const seen = (p) => {
        for (let n = p; n && n !== document.body; n = n.parentElement) {
          const s = getComputedStyle(n);
          if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) < 0.05) return false;
          const r = n.getBoundingClientRect();
          if (r.width <= 2 || r.height <= 2) return false;
          if (s.clip && s.clip !== 'auto' && /rect\(0(px)?,? 0(px)?/.test(s.clip)) return false;
          if (s.clipPath && s.clipPath.startsWith('inset(50%')) return false;
        }
        return true;
      };
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) {
        const lab = el.labels && [...el.labels].find((l) => seen(l));
        if (lab) out.push(clean(lab.innerText));
        else {
          // A visible caption right before the field (a "label" that isn't wired up) still counts for sighted users.
          const prev = el.previousElementSibling || (el.parentElement && el.parentElement.querySelector('.label, label, span'));
          if (prev && prev !== el && seen(prev) && clean(prev.innerText).length < 60) out.push(clean(prev.innerText));
          else if (el.placeholder) out.push(el.placeholder);
        }
        if (el.type === 'radio' || el.type === 'checkbox') return out.join(' ');
        return out.join(' ');
      }
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) { if (clean(n.textContent) && seen(n.parentElement)) out.push(clean(n.textContent)); }
      if (!out.length && el.tagName === 'IMG' && el.alt) out.push(el.alt);
      return clean(out.join(' '));
    },

    describeEl: (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return { ref: tag(el), tag: el.tagName.toLowerCase(), roleAttr: el.getAttribute('role'), type: el.type || null,
               tabIndex: el.tabIndex, disabled: !!el.disabled, rect: [r.left, r.top, r.width, r.height],
               style: { bg: s.backgroundColor, border: s.borderTopColor, color: s.color, outline: s.outlineStyle },
               widget: (() => { const c = el.closest('[role=grid],[role=listbox],[role=radiogroup],[role=tablist],[role=menu],[role=tree]');
                                 if (c && c.id) { const owner = document.querySelector(`[aria-controls="${c.id}"],[aria-owns="${c.id}"]`); if (owner) return tag(owner); }
                                 return c ? tag(c) : null; })() };
    },

    // Is the focused element el, inside el, or inside el's widget?
    focusMatches: (el, widgetRef) => {
      const a = document.activeElement;
      if (!a || a === document.body) return false;
      if (a === el || el.contains(a) || a.contains(el)) return true;
      if (el.type === 'radio' && a.type === 'radio' && a.name === el.name) return true;
      if (widgetRef) {
        const w = document.querySelector(`[data-aa-id="${widgetRef.slice(3)}"]`);
        if (w && (a === w || w.contains(a))) return true;
      }
      return false;
    },

    // Snapshot of what's on screen in main content, for change detection.
    mainSnapshot: () => {
      const root = document.querySelector('main, [role=main]') || document.body;
      const dialogs = [...document.querySelectorAll('[role=dialog],[role=alertdialog],dialog[open]')].filter(visible);
      return { text: clean(root.innerText).slice(0, 20000), dialogs: dialogs.map((d) => tag(d)), hash: location.hash, path: location.pathname,
               invalid: [...document.querySelectorAll('[aria-invalid=true]')].map((e) => tag(e)) };
    },

    focusInside: (ref) => {
      const w = document.querySelector(`[data-aa-id="${ref.slice(3)}"]`);
      const a = document.activeElement;
      return !!(w && a && (w === a || w.contains(a)));
    },

    // Visible error messages (any site). Error-like wording alone is not enough: "Enter your pincode" or "required"
    // are also ordinary instructions. The element (or a close ancestor) must also look like an error: role=alert,
    // an error/invalid class or id, or red text.
    visibleErrors: () => {
      const re = /\b(error|invalid|enter (a|an|the|your)|must|required|problem|rejected|not valid|incorrect|wrong|please (enter|choose|select)|choose (a|an|the|where))\b/i;
      const marked = (e) => {
        for (let n = e, d = 0; n && n.nodeType === 1 && d < 4; n = n.parentElement, d++) {
          if (n.getAttribute('role') === 'alert' || n.getAttribute('aria-live') === 'assertive') return true;
          const cls = typeof n.className === 'string' ? n.className : (n.className && n.className.baseVal) || '';
          if (/err|invalid|danger/i.test(cls + ' ' + (n.id || ''))) return true;
        }
        const c = (getComputedStyle(e).color.match(/[\d.]+/g) || []).map(Number);
        return c.length >= 3 && c[0] > 150 && c[1] < 110 && c[2] < 110;
      };
      const out = [];
      for (const e of document.querySelectorAll('p, span, div, li, a, label, strong')) {
        if (e.children.length > 2) continue;
        const t = clean(e.innerText);
        if (!t || t.length > 160 || !re.test(t)) continue;
        if (!visible(e) || e.getBoundingClientRect().width <= 2 || !marked(e)) continue;
        out.push({ ref: tag(e), text: t });
      }
      return out;
    },

    // Fields that changed only in colour after a submit (red border, no words): candidates for colour-only errors.
    fieldStyles: () => [...document.querySelectorAll('input, select, textarea')].filter(visible).map((e) => {
      const s = getComputedStyle(e);
      return { ref: tag(e), border: s.borderTopColor, bg: s.backgroundColor, invalid: e.getAttribute('aria-invalid') === 'true',
               words: window.__a11y.visibleWords(e.closest('.field, .form-group, div') || e.parentElement) };
    }),

    // Sibling controls next to el, grouped by colour; used to spot "told apart only by colour".
    siblingColours: (el) => {
      const parent = el.parentElement;
      if (!parent) return [];
      const sibs = [...parent.children].filter((x) => x.tagName === el.tagName && visible(x));
      return sibs.map((x) => { const s = getComputedStyle(x);
        return { ref: tag(x), colour: [s.borderTopColor, s.backgroundColor, s.color].join('|'),
                 words: window.__a11y.visibleWords(x), disabled: !!x.disabled }; });
    },
  };
})();
