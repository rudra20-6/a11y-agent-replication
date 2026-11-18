// Accessibility mutation operators. Configure with window.__MUTANTS = [{op, sel, ...args}] before this runs.
// Each operator is idempotent and re-applied whenever the DOM changes (the app re-renders on route change).
(() => {
  const cfg = window.__MUTANTS || [];
  if (!cfg.length) return;
  const css = (text) => { const s = document.createElement('style'); s.dataset.mutant = '1'; s.textContent = text; (document.head || document.documentElement).appendChild(s); };
  const each = (sel, fn) => document.querySelectorAll(sel).forEach((e) => { if (!e.dataset.mutated) { e.dataset.mutated = '1'; fn(e); } });
  const vhide = 'position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;clip:rect(0 0 0 0)!important;white-space:nowrap!important;';
  const hist = [];
  document.addEventListener('focusin', (e) => { hist.push(e.target); if (hist.length > 20) hist.shift(); }, true);
  // The last focused element that isn't inside the thing that just stole focus (a dialog or an error summary).
  const backTo = (exclude) => [...hist].reverse().find((x) => document.contains(x) && !(x.closest && x.closest(exclude)));

  const OPS = {
    // --- scanner-detectable controls
    remove_alt: (m) => each(m.sel, (e) => e.removeAttribute('alt')),
    remove_label: (m) => each(m.sel, (input) => {
      document.querySelectorAll(`label[for="${input.id}"]`).forEach((l) => { const s = document.createElement('span'); s.className = 'label'; s.textContent = l.textContent; l.replaceWith(s); });
      input.removeAttribute('aria-labelledby');
    }),
    icon_no_name: (m) => each(m.sel, (b) => {
      b.removeAttribute('aria-label');
      b.innerHTML = '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24"><circle cx="10" cy="10" r="6" stroke="currentColor" stroke-width="2.5" fill="none"/><line x1="15" y1="15" x2="21" y2="21" stroke="currentColor" stroke-width="2.5"/></svg>';
    }),
    // --- Identify
    generic_alt: (m) => each(m.sel, (e) => e.setAttribute('alt', m.text || 'image')),
    identical_names: (m) => each(m.sel, (e) => e.setAttribute('aria-label', m.text)),
    generic_field_label: (m) => each(m.sel, (e) => e.setAttribute('aria-label', m.text)),
    label_mismatch: (m) => each(m.sel, (e) => e.setAttribute('aria-label', m.text)),
    // --- Reach
    div_button: (m) => each(m.sel, (b) => {
      const d = document.createElement('div');
      d.className = b.className; d.innerHTML = b.innerHTML; d.dataset.mutated = '1';
      d.style.cssText = 'display:inline-block;padding:9px 16px;border-radius:6px;border:2px solid #1d4ed8;background:#1d4ed8;color:#fff;cursor:pointer;';
      d.addEventListener('click', () => b.click());
      b.style.display = 'none'; b.after(d);
    }),
    tabindex_neg: (m) => each(m.sel, (e) => e.setAttribute('tabindex', '-1')),
    // --- Operate
    strip_keys: (m) => each(m.sel, (e) => e.addEventListener('keydown', (ev) => {
      if ((m.keys || ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Enter', ' ', 'Home', 'End', 'PageUp', 'PageDown']).includes(ev.key)) { ev.stopImmediatePropagation(); ev.preventDefault(); }
    }, true)),
    // --- Notice
    remove_live: (m) => each(m.sel, (e) => { e.removeAttribute('role'); e.removeAttribute('aria-live'); }),
    no_focus_move: (m) => each(m.sel, () => setTimeout(() => { const back = backTo('[role=dialog]'); if (back) back.focus(); }, 30)),
    strip_state: (m) => {
      const strip = (e) => (m.attrs || ['aria-pressed']).forEach((a) => e.removeAttribute(a));
      document.querySelectorAll(m.sel).forEach(strip);
      if (!OPS._stateObs) {
        OPS._stateObs = new MutationObserver((muts) => muts.forEach((x) => { if (x.target.matches && x.target.matches(m.sel) && x.target.hasAttribute(x.attributeName)) strip(x.target); }));
        OPS._stateObs.observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: m.attrs || ['aria-pressed'] });
      }
    },
    // --- Recover
    unlink_errors: (m) => {
      document.querySelectorAll(m.sel).forEach((form) => {
        form.querySelectorAll('[aria-invalid]').forEach((f) => f.removeAttribute('aria-invalid'));
        form.querySelectorAll('[aria-describedby]').forEach((f) => {
          const ids = f.getAttribute('aria-describedby').split(' ').filter((id) => !id.endsWith('-error'));
          if (ids.length) f.setAttribute('aria-describedby', ids.join(' ')); else f.removeAttribute('aria-describedby');
        });
      });
      each('[data-bench=error-summary]', (s) => { s.removeAttribute('role'); s.removeAttribute('tabindex'); setTimeout(() => { const back = backTo('[data-bench=error-summary]'); if (back) back.focus(); }, 30); });
    },
    // --- Keyboard-only (P2)
    no_outline: () => { if (!OPS._outline) { OPS._outline = 1; css('*:focus,*:focus-visible{outline:none!important;box-shadow:none!important}'); } },
    sticky_cover: (m) => {
      if (document.querySelector(m.sel) && !document.querySelector('[data-mutant-banner]')) {
        const b = document.createElement('div');
        b.dataset.mutantBanner = '1';
        b.textContent = 'We use cookies to improve your experience. By using BenchBook you agree to our cookie policy.';
        b.style.cssText = 'position:fixed;left:0;right:0;bottom:0;height:' + (m.height || 46) + 'vh;background:#111827;color:#fff;padding:16px;z-index:50;font-size:15px;';
        document.body.appendChild(b);
        // Room to scroll content above the banner (mouse users can); keyboard focus still lands underneath it.
        document.body.style.paddingBottom = (m.height || 46) + 'vh';
      } else if (!document.querySelector(m.sel)) { const b = document.querySelector('[data-mutant-banner]'); if (b) { b.remove(); document.body.style.paddingBottom = ''; } }
    },
    // --- Low vision zoom (P3)
    min_width: (m) => { if (!OPS._minw) { OPS._minw = 1; css(`${m.sel}{min-width:${m.px || 1200}px!important}`); } },
    // --- Colour (P4)
    red_border_only: (m) => { if (!OPS._redb) { OPS._redb = 1; css(`${m.sel} .error-text, ${m.sel} ~ .error-summary, .error-summary{${vhide}}`); } },
    colour_only: (m) => { if (!OPS._colonly) { OPS._colonly = 1; css(`${m.sel}{${vhide}}`); } },
    // --- Benign (should change nothing a user can notice)
    benign_wrap: (m) => each(m.sel, (e) => { const s = document.createElement('span'); while (e.firstChild) s.appendChild(e.firstChild); e.appendChild(s); }),
    benign_class: (m) => each(m.sel, (e) => e.classList.add('mutant-noop')),
  };

  let pending = false;
  const apply = () => { pending = false; for (const m of cfg) { if (!OPS[m.op]) continue; try { OPS[m.op](m); } catch (err) { console.warn('mutant failed', m.op, err); } } };
  const schedule = () => { if (!pending) { pending = true; queueMicrotask(apply); } };
  const start = () => { apply(); new MutationObserver(schedule).observe(document.documentElement, { subtree: true, childList: true }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
