// Ma11y's 25 WCAG-failure mutation operators, ported to run inside the page (S3, D84).
//
// Source: Tafreshipour, Deshpande, Mehralian, Ahmed, Malek. "Ma11y: A Mutation Framework for Web Accessibility
// Testing", ISSTA 2024, doi:10.1145/3650212.3652113 (Table 1). Code: github.com/mahantaf/web-a11y-tool-analyzer at
// commit 4715847, src/mutant-generator/mutation-operators/F*.js, MIT licence (c) 2024 Mahan Tafreshipour.
//
// Each operator keeps the original's selection rule (applicable(): the first visible element in document order that
// meets its conditions) and its mutation (apply()). The originals run once on a static page through Puppeteer;
// BenchBook is a single-page app that re-renders, so here an operator is applied to the first applicable element of
// every page state the user reaches, and re-applied if a re-render removes the mutated element. Where the port can't
// follow the original exactly, the line says DEVIATION and why. We chose the operators' targets in no case: the
// selection rule does.
//
// Configure: window.__MUTANTS = [{op: 'ma11y', failure: 'F68'}]. Every mutated element gets data-ma11y="<failure>";
// window.__MA11Y_LOG lists each application (failure, route, tag, html), which the labelling script reads.
(() => {
  const cfg = (window.__MUTANTS || []).filter((m) => m.op === 'ma11y');
  if (!cfg.length) return;
  window.__MA11Y_LOG = window.__MA11Y_LOG || [];

  // handler.js isVisibleAndAccessible, verbatim except that it takes the element directly (the viewport test is
  // commented out in the original too).
  const vis = (element) => {
    const { display, visibility, opacity } = getComputedStyle(element);
    const ariaHidden = element.getAttribute('aria-hidden');
    const role = element.getAttribute('role');
    let parent = element.parentNode;
    let hasHiddenParent = false;
    while (parent && parent.nodeType === Node.ELEMENT_NODE) {
      const style = getComputedStyle(parent);
      const parentAriaHidden = parent.getAttribute('aria-hidden');
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0' || parentAriaHidden === 'true') {
        hasHiddenParent = true;
        break;
      }
      parent = parent.parentNode;
    }
    return display !== 'none' && visibility !== 'hidden' && opacity !== '0' &&
      (!role || (role !== 'presentation' && role !== 'none')) &&
      (!ariaHidden || ariaHidden.toLowerCase() === 'false') && !hasHiddenParent;
  };
  // Task-path placement (D85): with {placement: 'path', path: [css...]} an operator keeps its own conditions and
  // mutation but may only take an element that is one of the gold path's controls, inside one, or contains one.
  // Page-wide operators (F24, F25, F77) have no position and don't apply under this placement.
  const PATH = (cfg[0] && cfg[0].placement === 'path') ? (cfg[0].path || []) : null;
  const nearPath = (e) => !PATH || PATH.some((sel) => {
    try { return [...document.querySelectorAll(sel)].some((t) => t === e || t.contains(e) || e.contains(t)); } catch (err) { return false; }
  });
  const first = (sel, ok) => [...document.querySelectorAll(sel)].find((e) => !e.closest('[data-ma11y]') && vis(e) && nearPath(e) && (!ok || ok(e)));
  const styleTag = (id, text) => {
    if (document.querySelector(`style[data-ma11y-style="${id}"]`)) return;
    const s = document.createElement('style');
    s.dataset.ma11yStyle = id;
    s.textContent = text;
    (document.head || document.documentElement).appendChild(s);
  };
  // DEVIATION: utils.generateRandomString() returns a new random string per run. A fixed string of the same form
  // keeps every run of a unit identical (and the cache key stable).
  const RANDOM = 'k3j9x2q';
  const imgOk = (e) => e.hasAttribute('alt') && e.getAttribute('alt').trim() !== '' && e.closest('a') === null &&
    e.offsetWidth > 0 && e.offsetHeight > 0;
  const textInput = (e) => !['image', 'hidden', 'submit', 'reset', 'button'].includes(e.getAttribute('type'));
  // DEVIATION (F55, F78): the originals press Tab and take the first link that receives focus. Pressing Tab inside a
  // running test would move the agent's focus, so the first link in sequential focus order is computed instead
  // (positive tabindex first, then document order), skipping links that can't take focus.
  const firstTabbableLink = () => {
    const links = [...document.querySelectorAll('a[href]')].filter((a) => !a.closest('[data-ma11y]') && a.tabIndex >= 0 && vis(a) && nearPath(a));
    const pos = links.filter((a) => a.tabIndex > 0).sort((a, b) => a.tabIndex - b.tabIndex);
    return pos[0] || links.find((a) => a.tabIndex === 0);
  };

  // Each returns the element it mutated (to be marked), or undefined when the page has nothing it applies to.
  const OPS = {
    F2: () => { // Replace Header with Paragraph (1.3.1)
      const h = first('h2', (e) => e.children.length === 0 && e.childNodes.length === 1 && e.firstChild.nodeType === Node.TEXT_NODE);
      if (!h) return;
      styleTag('F2', '.p-class { font-size: 1.5em; font-weight: bold; margin-block-start: 0.67em; margin-block-end: 0.67em; }');
      const p = document.createElement('p');
      for (const { name, value } of h.attributes) p.setAttribute(name, value);
      p.innerHTML = h.innerHTML;
      p.classList.add('p-class');
      h.parentNode.replaceChild(p, h);
      return p;
    },
    F3: () => { // Replace Image with Div (1.1.1)
      const el = first('img', imgOk);
      if (!el) return;
      const style = `width: ${el.offsetWidth}px; height: ${el.offsetHeight}px; background-image: url(${el.getAttribute('src')});` +
        ' background-repeat: no-repeat; background-position: top left; background-color: transparent; background-size: contain;';
      const d = document.createElement('div');
      d.innerText = el.getAttribute('alt');
      d.style.cssText = 'display: inline-block; ' + style;
      el.replaceWith(d);
      return d;
    },
    F4: () => { // Make Text Blink (2.2.2)
      const s = first('span');
      if (!s) return;
      styleTag('F4', '.blink_me { animation: blinker 1s linear infinite; } @keyframes blinker { 50% { opacity: 0; } }');
      s.classList.add('blink_me');
      return s;
    },
    F9: () => { // Change Context on Blur (3.2.5)
      const i = first('form > input', (e) => textInput(e) && typeof e.onblur !== 'function');
      if (!i) return;
      i.setAttribute('onblur', "window.open('https://www.google.com')");
      return i;
    },
    F22: () => { // Change Context on Click (3.2.5)
      const s = first('span', (e) => e.textContent.trim() !== '' && typeof e.onclick !== 'function');
      if (!s) return;
      s.removeAttribute('class');
      s.removeAttribute('style');
      s.setAttribute('onclick', "window.open('https://google.com')");
      return s;
    },
    F24: () => { // Change Foreground Color (1.4.3): the target is the first visible paragraph; the style is page-wide
      if (PATH) return;
      const p = first('p');
      if (!p) return;
      styleTag('F24', 'body { color: white; !important }');   // the original's CSS, including its misplaced !important
      return p;
    },
    F25: () => { // Change Page Title (2.4.2); re-applied on every run because the app sets the title per route
      if (PATH) return;
      const t = document.querySelector('title');
      if (!t || !document.title.trim()) return;
      // Only when the app has put its own title back: setting it unconditionally changes the DOM, which re-runs the
      // operators, which sets it again (an endless loop that froze the page on 3 Nov).
      if (document.title !== RANDOM) document.title = RANDOM;
      return t;
    },
    F30: () => { // Change Image Alt Text (1.1.1)
      const el = first('img', imgOk);
      if (!el) return;
      el.setAttribute('alt', RANDOM);
      return el;
    },
    F32: () => { // Add Space Between Characters (1.3.2)
      const s = first('span', (e) => e.textContent.trim().length > 0 && e.textContent.trim().split(' ').length === 1);
      if (!s) return;
      s.textContent = s.textContent.trim().split('').join(' ');
      return s;
    },
    F36: () => { // Change Context on Input (3.2.2): the last input of the first visible form submits it on change
      const form = [...document.querySelectorAll('form')].find((f) => !f.closest('[data-ma11y]') && vis(f) && nearPath(f));
      if (!form) return;
      const inputs = form.querySelectorAll('input');
      const last = inputs[inputs.length - 1];
      if (!last || !['text', 'email', 'password', 'search', 'number', 'tel'].includes(last.getAttribute('type')) ||
          typeof last.onchange === 'function') return;
      form.setAttribute('id', 'form_12345');
      last.setAttribute('onchange', 'form_12345.submit();');
      return last;
    },
    F37: () => { // Change Context on Selection (3.2.2)
      const i = first('input', (e) => e.getAttribute('type') === 'radio' && typeof e.onclick !== 'function');
      if (!i) return;
      i.setAttribute('onclick', "window.open('https://google.com')");
      return i;
    },
    F42: () => { // Replace Anchor Text with Span (1.3.1, 2.1.1, 4.1.2)
      const a = first('a', (e) => e.textContent.trim() !== '');
      if (!a) return;
      styleTag('F42', '.a-decoration { text-decoration: underline; !important; cursor: pointer; !important; color: blue; !important; }');
      const s = document.createElement('span');
      for (const { name, value } of a.attributes) {
        if (name !== 'href') s.setAttribute(name, value);
        else s.setAttribute('onclick', `window.location.href='${value}';`);
      }
      s.textContent = a.textContent;
      s.classList.add('a-decoration');
      a.parentNode.replaceChild(s, a);
      return s;
    },
    F44: () => { // Change Tab Index Order (2.4.3): links in the first list reversed with positive tabindex
      const ul = first('ul', (e) => { const li = e.querySelectorAll('li'); return li.length >= 2 && [...li].every((x) => x.querySelector('a')); });
      if (!ul) return;
      const lis = ul.querySelectorAll('li');
      let t = lis.length;
      for (const li of lis) { li.querySelector('a').setAttribute('tabindex', t); t -= 1; }
      return ul;
    },
    F54: () => { // Change Device-Specific Pointer (2.1.1): onclick moved to onmousedown
      const e = first('[onclick]');
      if (!e) return;
      e.setAttribute('onmousedown', e.getAttribute('onclick'));
      e.removeAttribute('onclick');
      return e;
    },
    F55: () => { // Remove Focus from Anchor Text (2.1.1, 2.4.7, 3.2.1)
      const a = firstTabbableLink();
      if (!a) return;
      a.setAttribute('onfocus', 'this.blur();');
      return a;
    },
    F65: () => { // Remove Image Alt Text (1.1.1)
      const el = first('img', imgOk);
      if (!el) return;
      el.removeAttribute('alt');
      el.removeAttribute('aria-label');
      el.removeAttribute('title');
      return el;
    },
    F68: () => { // Remove Input Names (1.3.1, 4.1.2)
      const i = first('form > input', (e) => textInput(e) && e.labels && e.labels.length > 0);
      if (!i) return;
      i.removeAttribute('placeholder');
      Array.from(i.labels).forEach((l) => l.remove());
      return i;
    },
    F73: () => { // Remove Anchor Text Decorations (1.4.1)
      const a = first('p > a', (e) => { const cs = getComputedStyle(e); return cs.getPropertyValue('text-decoration') !== 'none' && cs.getPropertyValue('cursor') !== 'default'; });
      if (!a) return;
      a.setAttribute('style', 'text-decoration: none; cursor: default');
      a.setAttribute('onmouseover', "this.style.textDecoration='none'");
      a.setAttribute('onmouseout', "this.style.textDecoration='none'");
      a.setAttribute('onclick', "this.style.textDecoration='none'");
      return a;
    },
    F77: () => { // Make Duplicate Ids (4.1.1): the first two adjacent elements with different ids share one.
      // DEVIATION: the original's pair includes elements with no id ('' !== 'x'); the same rule is kept.
      if (PATH) return;
      const els = [...document.querySelectorAll('body *:not(script):not(style)')].filter((e) => !e.closest('[data-ma11y]'));
      for (let i = 0; i < els.length - 1; i += 1) {
        if (els[i].id !== els[i + 1].id) { els[i].id = 'common-id'; els[i + 1].id = 'common-id'; return els[i + 1]; }
      }
    },
    F78: () => { // Remove Outline from Anchor Text (2.4.7)
      // DEVIATION: the original also requires a non-'none' outline when focused, read after a real Tab press; the port
      // can't focus the link without moving the agent's focus, so it takes the first tabbable link (see above).
      const a = firstTabbableLink();
      if (!a) return;
      styleTag('F78', '.no_outline { outline: none !important; }');
      a.classList.add('no_outline');
      return a;
    },
    F80: () => { // Change Input Font Size (1.4.4)
      const i = first('form > input', (e) => e.type === 'text');
      if (!i) return;
      styleTag('F80', '.fix-size-input { font-size: 8pt; !important; }');   // DEVIATION: class renamed (F94 uses .fix-size too)
      i.classList.add('fix-size-input');
      return i;
    },
    F89: () => { // Remove Anchor Text Identifier (2.4.4, 4.1.2): an image-only link loses its name
      const a = first('a', (e) => {
        const img = e.querySelector('img');
        return e.childElementCount === 1 && e.firstElementChild.tagName.toLowerCase() === 'img' && e.textContent.trim() === '' &&
          (e.hasAttribute('aria-label') || e.hasAttribute('aria-labelledby') || (img && img.alt.trim() !== ''));
      });
      if (!a) return;
      a.removeAttribute('aria-label');
      a.removeAttribute('aria-labelledby');
      a.removeAttribute('title');
      a.querySelector('img').setAttribute('alt', '');
      return a;
    },
    F91: () => { // Replace Table Headers with Table Data (1.3.1)
      const t = first('table', (e) => e.querySelectorAll('th').length > 0);
      if (!t) return;
      t.querySelectorAll('th').forEach((th) => { const td = document.createElement('td'); td.innerHTML = th.innerHTML; th.parentNode.replaceChild(td, th); });
      return t;
    },
    F94: () => { // Change Paragraph Font Size (1.4.4)
      const p = first('p', (e) => e.textContent.trim() !== '');
      if (!p) return;
      styleTag('F94', '.fix-size { font-size: 2vh !important; }');
      p.classList.add('fix-size');
      return p;
    },
    F96: () => { // Change Button Label (2.5.3)
      // The original calls isVisibleAndAccessible without await, so its visibility test is always truthy; kept as is.
      const b = [...document.querySelectorAll('button')].find((e) => !e.closest('[data-ma11y]') && nearPath(e) &&
        e.childElementCount === 0 && e.textContent.trim() !== '' && e.hasAttribute('aria-label'));
      if (!b) return;
      b.setAttribute('aria-label', RANDOM);
      return b;
    },
  };

  const route = () => location.pathname + location.hash;
  let pending = false;
  // Circuit breaker: an operator whose own change keeps re-triggering it must not freeze the page.
  let runs = 0, windowStart = Date.now(), tripped = false;
  const run = () => {
    pending = false;
    if (tripped) return;
    if (Date.now() - windowStart > 1000) { windowStart = Date.now(); runs = 0; }
    if (++runs > 50) { tripped = true; console.warn('ma11y: more than 50 re-applications in 1 s, stopped'); return; }
    for (const m of cfg) {
      const op = OPS[m.failure];
      if (!op) continue;
      if (m.failure !== 'F25' && document.querySelector(`[data-ma11y="${m.failure}"]`)) continue;   // one live target per page state
      try {
        const el = op();
        if (!el) continue;
        if (el.dataset && el.dataset.ma11y !== m.failure) {
          el.dataset.ma11y = m.failure;
          el.dataset.mutated = '1';
          window.__MA11Y_LOG.push({ failure: m.failure, route: route(), tag: el.tagName.toLowerCase(),
            html: (el.outerHTML || '').slice(0, 240), t: Date.now() });
        }
      } catch (err) { console.warn('ma11y operator failed', m.failure, err); }
    }
  };
  const schedule = () => { if (!pending) { pending = true; queueMicrotask(run); } };
  const start = () => { run(); new MutationObserver(schedule).observe(document.documentElement, { subtree: true, childList: true }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
