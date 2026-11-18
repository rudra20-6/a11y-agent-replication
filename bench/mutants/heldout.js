// Held-out accessibility mutation operators, written blind to the detection tool (see bench/HELDOUT_GUIDE.md).
// Same contract as mutants.js: configure with window.__MUTANTS = [{op, sel, ...args}] before this runs; each operator is
// idempotent and re-applied whenever the DOM changes. This file is loaded in the same page as mutants.js, so it only
// applies ops it defines (all names start with h_) and ignores the rest.
(() => {
  const cfg = window.__MUTANTS || [];
  if (!cfg.length) return;
  const css = (text) => { const s = document.createElement('style'); s.dataset.mutant = '1'; s.textContent = text; (document.head || document.documentElement).appendChild(s); };
  const each = (sel, fn) => document.querySelectorAll(sel).forEach((e) => { if (!e.dataset.mutated) { e.dataset.mutated = '1'; fn(e); } });
  const vhide = 'position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;clip:rect(0 0 0 0)!important;white-space:nowrap!important;';
  const done = {};
  const once = (key, fn) => { if (!done[key]) { done[key] = 1; fn(); } };
  const TICK = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M3 8.5l3.2 3.2L13 5' stroke='white' stroke-width='2.2' fill='none'/%3E%3C/svg%3E\")";

  const OPS = {
    // --- Operate (keyboard): Tab and Shift+Tab are swallowed while this control has focus
    h_key_trap: (m) => each(m.sel, (e) => e.addEventListener('keydown', (ev) => {
      if (ev.key === 'Tab') { ev.preventDefault(); ev.stopPropagation(); }
    }, true)),

    // --- Reach (keyboard): positive tabindex values in a scrambled order. m.tabs lists selectors, first gets tabindex 1.
    h_tabindex_pos: (m) => each(m.sel, (root) => (m.tabs || []).forEach((s, i) => {
      const el = root.querySelector(s); if (el) el.setAttribute('tabindex', String(i + 1));
    })),

    // --- Notice (keyboard / screen reader): when the matched element leaves the DOM, focus is reset to the top of the page
    h_focus_reset_on_remove: (m) => {
      once('reset-css', () => css('body:focus,body:focus-visible{outline:none!important}'));
      each(m.sel, (e) => {
        const mo = new MutationObserver(() => {
          if (document.contains(e)) return;
          mo.disconnect();
          setTimeout(() => {
            const a = document.activeElement; if (a && a !== document.body) a.blur();
            document.body.setAttribute('tabindex', '-1'); document.body.focus(); document.body.removeAttribute('tabindex');
          }, 0);
        });
        mo.observe(document.body, { childList: true });
      });
    },

    // --- Reach (keyboard): a control that is only drawn while the mouse is over its card. m.card is the hover target.
    h_hover_reveal: (m) => once('hover-' + m.sel, () => css(`${m.sel}{opacity:0!important}${m.card}:hover ${m.sel}{opacity:1!important}`)),

    // --- Identify (screen reader): native checkbox swapped for a focusable, clickable box with no role and no state
    h_fake_checkbox: (m) => {
      once('toggle-css', () => css('.h-toggle{display:flex;align-items:center;gap:8px;cursor:pointer;padding:2px 0}'
        + '.h-toggle::before{content:"";flex:none;width:18px;height:18px;border:2px solid #6b7280;border-radius:4px;background:#fff}'
        + '.h-toggle[data-on]::before{background:#1d4ed8 ' + TICK + ' center/14px no-repeat;border-color:#1d4ed8}'));
      each(m.sel, (input) => {
        const label = document.querySelector(`label[for="${input.id}"]`);
        const t = document.createElement('div');
        t.className = 'h-toggle'; t.id = input.id; t.tabIndex = 0; t.textContent = label ? label.textContent : input.value;
        if (input.checked) t.setAttribute('data-on', '');
        const flip = () => { input.click(); t.toggleAttribute('data-on', input.checked); };
        t.addEventListener('click', flip);
        t.addEventListener('keydown', (e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); flip(); } });
        input.removeAttribute('id'); input.style.display = 'none';
        if (label) label.remove();
        input.after(t);
      });
    },

    // --- Identify (screen reader / voice): two fields keep their visible labels, but their accessible names are swapped
    h_swap_names: (m) => each(m.sel, (root) => {
      const [a, b] = (m.pair || []).map((id) => root.querySelector('#' + id));
      if (!a || !b) return;
      const la = root.querySelector(`label[for="${a.id}"]`), lb = root.querySelector(`label[for="${b.id}"]`);
      if (!la || !lb) return;
      la.id = la.id || a.id + '-lbl'; lb.id = lb.id || b.id + '-lbl';
      a.setAttribute('aria-labelledby', lb.id); b.setAttribute('aria-labelledby', la.id);
    }),

    // --- Notice (screen reader): the element is removed from the accessibility tree but stays on screen
    h_aria_hide: (m) => each(m.sel, (e) => e.setAttribute('aria-hidden', 'true')),

    // --- Identify (colour-vision deficiency): chart labels are dropped; the two series differ by red/green hue only,
    // explained by a text key that names the colours. The plain-text result is kept for assistive tech only.
    h_chart_colour: (m) => {
      once('chart-css', () => css(`${m.result}{${vhide}}`));
      each(`${m.sel} .bar`, (bar) => {
        const sw = bar.querySelector('.swatch'); if (!sw) return;
        const idx = [...bar.parentElement.children].indexOf(bar);
        sw.style.background = idx === 0 ? '#bf4c40' : '#15803d';
        const amount = (bar.textContent.match(/₹[\d,]+/) || [''])[0];
        bar.replaceChildren(sw, document.createTextNode(' ' + amount));
      });
      const chart = document.querySelector(m.sel);
      if (chart && !document.querySelector('[data-mutant-key]')) {
        const p = document.createElement('p');
        p.dataset.mutantKey = '1'; p.setAttribute('aria-hidden', 'true');
        p.textContent = 'Green bar: estimated returns. Red bar: amount you invest.';
        chart.after(p);
      }
    },

    // --- Notice (colour-vision deficiency): the selected state of a seat is a red/green (or pink/teal) border swap only
    h_selected_hue: (m) => once('hue-css', () => css(
      `${m.sel}.is-selected{background:#fff!important;color:#111827!important;border-color:#bf4c40!important}`
      + `${m.sel}.women.is-selected{background:#fdf2f8!important;color:#111827!important;border-color:#06796e!important}`)),

    // --- Identify (400% zoom): at narrow widths the label text is cut off with an ellipsis and cannot be read in full
    h_clip_narrow: (m) => once('clip-' + m.sel, () => css(
      `@media (max-width:480px){fieldset:has(${m.sel}){min-width:0}${m.sel} .result{overflow:hidden}`
      + `${m.sel} .result label{flex:1 1 0;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}`)),

    // --- Operate (keyboard): visual order is the reverse of DOM / tab order
    h_reverse_order: (m) => once('rev-' + m.sel, () => css(`${m.sel}{display:flex!important;flex-direction:column-reverse}`)),

    // --- Recover (screen reader / keyboard): error-summary links jump to a different field than the one in error
    h_error_link_wrong: (m) => each(m.sel, (a) => a.setAttribute('href', '#' + m.to)),

    // --- Reach (400% zoom): a chat-style panel pinned to the bottom at narrow widths, covering the page's own controls
    h_fixed_panel: (m) => {
      once('panel-css', () => css('.h-panel{display:none}@media (max-width:480px){.h-panel{display:block;position:fixed;left:0;right:0;bottom:0;'
        + `height:${m.height || 55}vh;background:#111827;color:#fff;padding:14px 40px 14px 14px;z-index:50;font-size:15px}`
        + '.h-panel button{position:absolute;top:4px;right:4px;width:28px;height:28px;padding:0;line-height:1;font-size:18px;'
        + 'background:transparent;border:1px solid #9ca3af}}'));
      const panel = document.querySelector('[data-mutant-panel]');
      if (document.querySelector(m.sel)) {
        if (!panel && !done.panelDismissed) {
          const p = document.createElement('div');
          p.className = 'h-panel'; p.dataset.mutantPanel = '1';
          p.innerHTML = '<strong>Chat with us</strong><p>Our delivery experts are online. Typical reply time: 2 minutes.</p>'
            + '<button type="button" aria-label="Close chat">×</button>';
          p.querySelector('button').addEventListener('click', () => { done.panelDismissed = 1; p.remove(); });
          document.body.appendChild(p);
        }
      } else { done.panelDismissed = 0; if (panel) panel.remove(); }
    },

    // --- Identify (voice control): the visible label becomes an image of text whose alt text says something else
    h_text_image: (m) => each(m.sel, (b) => {
      const text = b.textContent.trim().replace(/[&<>]/g, '');
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="124" height="20"><text x="0" y="15" font-size="16" font-family="sans-serif" fill="#fff">${text}</text></svg>`;
      const img = new Image();
      img.alt = m.alt || 'Go'; img.width = 124; img.height = 20; img.src = 'data:image/svg+xml,' + encodeURIComponent(svg);
      b.replaceChildren(img);
    }),

    // --- Benign (should change nothing a user can notice)
    h_benign_role: (m) => each(m.sel, (e) => e.setAttribute('role', m.role)),
    h_benign_same_label: (m) => each(m.sel, (e) => e.setAttribute('aria-label', e.textContent.trim())),
  };

  let pending = false;
  const apply = () => { pending = false; for (const m of cfg) { if (!OPS[m.op]) continue; try { OPS[m.op](m); } catch (err) { console.warn('heldout mutant failed', m.op, err); } } };
  const schedule = () => { if (!pending) { pending = true; queueMicrotask(apply); } };
  const start = () => { apply(); new MutationObserver(schedule).observe(document.documentElement, { subtree: true, childList: true }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
