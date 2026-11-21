// BenchBook: a booking and shopping web application. Widgets follow the ARIA Authoring Practices patterns.
(() => {
  'use strict';
  const TODAY = new Date(2026, 9, 12); // fixed "today" (12 Oct 2026) so every run sees the same calendar
  const CITIES = [
    ['HYD', 'Hyderabad'], ['DEL', 'Delhi'], ['BOM', 'Mumbai'], ['BLR', 'Bengaluru'],
    ['MAA', 'Chennai'], ['CCU', 'Kolkata'], ['PNQ', 'Pune'], ['GOI', 'Goa'],
  ];
  const cityName = (c) => (CITIES.find(x => x[0] === c) || [c, c])[1];
  const inr = (n) => '₹' + Math.round(n).toLocaleString('en-IN');
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const longDate = (d) => `${DAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  const shortDate = (d) => `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)} ${d.getFullYear()}`;
  const fareFor = (d) => 3000 + ((d.getDate() * 37 + d.getMonth() * 11) % 23) * 100;

  const state = {
    search: { from: null, to: null, date: null, pax: 1 }, results: [], fare: null,
    passenger: null, review: false, payClicked: false,
    sip: { amount: 25000, rate: 12, years: 10 },
    cart: [], filters: { cats: [], price: 'all', sort: 'featured' }, pincode: null,
    seat: null, seatContinue: false,
  };
  window.__bench = { state, today: iso(TODAY) };

  const $ = (sel, root = document) => root.querySelector(sel);
  const h = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const main = $('main');
  const cartStatus = $('[data-bench=cart-status]');

  // ------------------------------------------------------------------ router
  const routes = {};
  function go(hash) { if (location.hash === hash) render(); else location.hash = hash; }
  function render() {
    const [path, query] = (location.hash.slice(1) || '/').split('?');
    const params = new URLSearchParams(query || '');
    const key = Object.keys(routes).find(k => new RegExp('^' + k.replace(/:\w+/g, '([^/]+)') + '$').test(path)) || '/';
    const m = path.match(new RegExp('^' + key.replace(/:\w+/g, '([^/]+)') + '$')) || [];
    main.innerHTML = '';
    routes[key](params, ...m.slice(1));
    const h1 = $('h1', main);
    document.title = (h1 ? h1.textContent + ' – ' : '') + 'BenchBook';
    if (h1) { h1.setAttribute('tabindex', '-1'); h1.focus(); }
  }
  window.addEventListener('hashchange', render);

  // ------------------------------------------------------------------ shared: error summary
  function showErrors(form, errors) {
    form.querySelectorAll('[aria-invalid]').forEach(e => { e.removeAttribute('aria-invalid'); });
    form.querySelectorAll('.error-text').forEach(e => e.remove());
    form.querySelectorAll('[data-err-for]').forEach(e => e.remove());
    const old = $('.error-summary', main); if (old) old.remove();
    for (const el of form.querySelectorAll('[aria-describedby]')) {
      el.setAttribute('aria-describedby', el.getAttribute('aria-describedby').split(' ').filter(id => !id.endsWith('-error')).join(' '));
      if (!el.getAttribute('aria-describedby')) el.removeAttribute('aria-describedby');
    }
    if (!errors.length) return true;
    const sum = h(`<div class="error-summary" role="alert" tabindex="-1" data-bench="error-summary">
      <h2>There is a problem</h2><ul>${errors.map(e => `<li><a href="#${e.id}" data-bench="error-link">${e.msg}</a></li>`).join('')}</ul></div>`);
    form.before(sum);
    for (const e of errors) {
      const field = document.getElementById(e.id);
      const msg = h(`<p class="error-text" id="${e.id}-error" data-err-for="${e.id}" data-bench="field-error">${e.msg}</p>`);
      (field.closest('.field') || field.parentElement).insertBefore(msg, field.closest('.field') ? field.closest('.field').querySelector('label, .label').nextSibling : field);
      field.setAttribute('aria-invalid', 'true');
      field.setAttribute('aria-describedby', ((field.getAttribute('aria-describedby') || '') + ' ' + e.id + '-error').trim());
    }
    sum.addEventListener('click', (ev) => {
      const a = ev.target.closest('a'); if (!a) return;
      ev.preventDefault(); document.getElementById(a.getAttribute('href').slice(1)).focus();
    });
    sum.focus();
    return false;
  }

  // ------------------------------------------------------------------ combobox (APG list autocomplete)
  function combobox(id, labelText, value) {
    const wrap = h(`<div class="field">
      <label for="${id}">${labelText}</label>
      <input id="${id}" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false"
             aria-controls="${id}-list" autocomplete="off" data-bench="${id}">
      <ul id="${id}-list" role="listbox" aria-label="${labelText} cities" class="listbox" hidden data-bench="${id}-list"></ul>
    </div>`);
    const input = $('input', wrap), list = $('ul', wrap);
    let active = -1, opts = [];
    if (value) input.value = `${cityName(value)} (${value})`;
    input.dataset.code = value || '';
    const open = (filter) => {
      const f = filter.toLowerCase();
      opts = CITIES.filter(([c, n]) => !f || n.toLowerCase().startsWith(f) || c.toLowerCase().startsWith(f));
      list.innerHTML = opts.map(([c, n], i) => `<li role="option" id="${id}-opt-${i}" aria-selected="false" data-code="${c}" data-bench="${id}-option">${n} (${c})</li>`).join('');
      list.hidden = !opts.length; input.setAttribute('aria-expanded', String(!!opts.length)); active = -1;
      input.removeAttribute('aria-activedescendant');
    };
    const close = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); active = -1; };
    const setActive = (i) => {
      const items = list.querySelectorAll('[role=option]');
      items.forEach(o => o.setAttribute('aria-selected', 'false'));
      active = (i + items.length) % items.length;
      items[active].setAttribute('aria-selected', 'true');
      input.setAttribute('aria-activedescendant', items[active].id);
      items[active].scrollIntoView({ block: 'nearest' });
    };
    const choose = (code) => { input.value = `${cityName(code)} (${code})`; input.dataset.code = code; close(); input.dispatchEvent(new Event('change')); };
    input.addEventListener('input', () => { input.dataset.code = ''; open(input.value); });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (list.hidden) open(input.value); if (opts.length) setActive(active + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); if (!list.hidden && opts.length) setActive(active - 1); }
      else if (e.key === 'Enter') { if (!list.hidden && active >= 0) { e.preventDefault(); choose(opts[active][0]); } }
      else if (e.key === 'Escape') { close(); }
    });
    list.addEventListener('mousedown', (e) => e.preventDefault());
    list.addEventListener('click', (e) => { const o = e.target.closest('[role=option]'); if (o) choose(o.dataset.code); });
    input.addEventListener('blur', () => {
      setTimeout(close, 150);
      if (!input.dataset.code) { // accept an exact typed name or code
        const t = input.value.trim().toLowerCase();
        const hit = CITIES.find(([c, n]) => n.toLowerCase() === t || c.toLowerCase() === t || `${n} (${c})`.toLowerCase() === t);
        if (hit) { input.value = `${hit[1]} (${hit[0]})`; input.dataset.code = hit[0]; }
      }
    });
    return wrap;
  }

  // ------------------------------------------------------------------ date picker dialog (APG pattern)
  function datePicker(onPick, current) {
    const opener = document.activeElement;
    let shown = new Date((current || TODAY).getFullYear(), (current || TODAY).getMonth(), 1);
    let focusDate = current || new Date(TODAY);
    const back = h(`<div class="dialog-backdrop" data-bench="date-backdrop">
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dp-title" data-bench="date-dialog">
        <div class="dialog-head">
          <button type="button" class="secondary" data-bench="date-prev" aria-label="Previous month">‹</button>
          <h2 id="dp-title" aria-live="polite"></h2>
          <button type="button" class="secondary" data-bench="date-next" aria-label="Next month">›</button>
        </div>
        <table class="grid" role="grid" aria-labelledby="dp-title" data-bench="date-grid">
          <thead><tr>${DAYS.map(d => `<th scope="col" abbr="${d}">${d.slice(0, 2)}</th>`).join('')}</tr></thead>
          <tbody></tbody>
        </table>
        <p class="hint">Use arrow keys to move, Enter to choose. Lowest fares are marked "lowest".</p>
        <button type="button" class="secondary" data-bench="date-cancel">Cancel</button>
      </div></div>`);
    const title = $('#dp-title', back), tbody = $('tbody', back);
    const disabled = (d) => d < new Date(TODAY.getFullYear(), TODAY.getMonth(), TODAY.getDate());
    const draw = () => {
      title.textContent = `${MONTHS[shown.getMonth()]} ${shown.getFullYear()}`;
      const first = new Date(shown.getFullYear(), shown.getMonth(), 1);
      const days = new Date(shown.getFullYear(), shown.getMonth() + 1, 0).getDate();
      const fares = []; for (let i = 1; i <= days; i++) { const d = new Date(shown.getFullYear(), shown.getMonth(), i); if (!disabled(d)) fares.push(fareFor(d)); }
      const low = Math.min(...fares);
      let html = '<tr role="row">' + '<td></td>'.repeat(first.getDay());
      for (let i = 1; i <= days; i++) {
        const d = new Date(shown.getFullYear(), shown.getMonth(), i);
        const dis = disabled(d), f = fareFor(d), isLow = !dis && f === low;
        const sel = !!(current && iso(current) === iso(d));
        html += `<td role="gridcell" tabindex="-1" data-date="${iso(d)}" data-bench="date-cell"
                   class="${isLow ? 'lowest' : ''}" aria-selected="${sel}" ${dis ? 'aria-disabled="true"' : ''}
                   aria-label="${longDate(d)}${dis ? ', unavailable' : `, fare ${inr(f)}${isLow ? ', lowest fare' : ''}`}">
                   <span class="day">${i}</span><span class="fare">${dis ? '–' : inr(f) + (isLow ? ' lowest' : '')}</span></td>`;
        if ((first.getDay() + i) % 7 === 0 && i < days) html += '</tr><tr role="row">';
      }
      tbody.innerHTML = html + '</tr>';
      const target = tbody.querySelector(`[data-date="${iso(focusDate)}"]`) || tbody.querySelector('[role=gridcell]:not([aria-disabled])');
      target.setAttribute('tabindex', '0');
    };
    const focusCell = () => { const c = tbody.querySelector('[tabindex="0"]'); if (c) c.focus(); };
    const move = (days) => {
      const nd = new Date(focusDate); nd.setDate(nd.getDate() + days);
      if (disabled(nd)) return;
      focusDate = nd;
      if (nd.getMonth() !== shown.getMonth() || nd.getFullYear() !== shown.getFullYear()) shown = new Date(nd.getFullYear(), nd.getMonth(), 1);
      draw(); focusCell();
    };
    const closeDlg = (picked) => { back.remove(); document.removeEventListener('keydown', trap, true); if (picked) onPick(picked); else if (opener) opener.focus(); };
    const pick = (cell) => { if (!cell || cell.getAttribute('aria-disabled') === 'true') return; const [y, m, d] = cell.dataset.date.split('-').map(Number); closeDlg(new Date(y, m - 1, d)); };
    tbody.addEventListener('click', (e) => pick(e.target.closest('[role=gridcell]')));
    tbody.addEventListener('keydown', (e) => {
      const map = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 7, ArrowUp: -7 };
      if (map[e.key]) { e.preventDefault(); move(map[e.key]); }
      else if (e.key === 'Home') { e.preventDefault(); move(-focusDate.getDay()); }
      else if (e.key === 'End') { e.preventDefault(); move(6 - focusDate.getDay()); }
      else if (e.key === 'PageDown') { e.preventDefault(); move(new Date(focusDate.getFullYear(), focusDate.getMonth() + 1, 0).getDate()); }
      else if (e.key === 'PageUp') { e.preventDefault(); move(-new Date(focusDate.getFullYear(), focusDate.getMonth(), 0).getDate()); }
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(e.target.closest('[role=gridcell]')); }
    });
    $('[data-bench=date-prev]', back).addEventListener('click', () => { shown = new Date(shown.getFullYear(), shown.getMonth() - 1, 1); draw(); });
    $('[data-bench=date-next]', back).addEventListener('click', () => { shown = new Date(shown.getFullYear(), shown.getMonth() + 1, 1); draw(); });
    $('[data-bench=date-cancel]', back).addEventListener('click', () => closeDlg(null));
    // Modal: keep Tab inside the dialog; Esc closes.
    const trap = (e) => {
      if (!document.body.contains(back)) return;
      if (e.key === 'Escape') { e.preventDefault(); closeDlg(null); return; }
      if (e.key !== 'Tab') return;
      const f = [...back.querySelectorAll('button, [tabindex="0"]')];
      const i = f.indexOf(document.activeElement);
      if (e.shiftKey && (i <= 0)) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
    };
    document.addEventListener('keydown', trap, true);
    document.body.appendChild(back);
    draw(); focusCell();
  }

  // ------------------------------------------------------------------ flights
  routes['/'] = () => {
    main.append(h(`<section><h1>Welcome to BenchBook</h1>
      <p>Book flights and bus seats, plan a SIP, or shop.</p>
      <ul><li><a href="#/flights">Search flights</a></li><li><a href="#/seats">Choose a bus seat</a></li>
      <li><a href="#/sip">SIP calculator</a></li><li><a href="#/shop">Shop</a></li></ul></section>`));
  };

  function searchFlights() {
    const { from, to, date } = state.search;
    const airlines = [['IndiGo', '6E'], ['Air India', 'AI'], ['Akasa Air', 'QP'], ['SpiceJet', 'SG']];
    const base = fareFor(date) + (from.charCodeAt(0) + to.charCodeAt(1)) % 7 * 150;
    const out = [];
    for (let i = 0; i < 6; i++) {
      const [al, code] = airlines[i % 4];
      const dep = 6 + i * 2, dur = 2 + (i % 2);
      const fare = base + ((i * 53) % 9) * 120;
      out.push({ id: `${code}${201 + i * 17}`, airline: al, num: `${code} ${201 + i * 17}`,
                 dep: `${String(dep).padStart(2, '0')}:10`, arr: `${String(dep + dur).padStart(2, '0')}:25`, fare });
    }
    const cheapest = Math.min(...out.map(r => r.fare));
    out.forEach(r => { r.cheapest = r.fare === cheapest; });
    return out;
  }

  routes['/flights'] = () => {
    const s = state.search;
    const sec = h(`<section><h1>Search flights</h1>
      <form novalidate data-bench="search-form"><div class="row"></div>
        <div class="row">
          <div class="field"><span class="label" id="date-label">Departure date</span>
            <button type="button" id="date" class="secondary" data-bench="date-button" aria-describedby="date-label">Departure date: ${s.date ? shortDate(s.date) : 'choose a date'}</button></div>
          <div class="field"><label for="pax">Passengers</label>
            <input id="pax" type="number" min="1" max="9" value="${s.pax}" data-bench="pax"></div>
        </div>
        <button type="submit" data-bench="search-submit">Search flights</button>
      </form>
      <p class="status" role="status" data-bench="results-status"></p>
      <div data-bench="results"></div></section>`);
    const row = $('.row', sec);
    row.append(combobox('from', 'From', s.from), combobox('to', 'To', s.to));
    main.append(sec);
    const form = $('form', sec), dateBtn = $('#date', sec);
    dateBtn.addEventListener('click', () => datePicker((d) => {
      s.date = d; dateBtn.textContent = `Departure date: ${shortDate(d)}`; dateBtn.focus();
    }, s.date));
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      s.from = $('#from', sec).dataset.code || null; s.to = $('#to', sec).dataset.code || null;
      s.pax = Math.max(1, parseInt($('#pax', sec).value || '1', 10));
      const errs = [];
      if (!s.from) errs.push({ id: 'from', msg: 'Choose where you are flying from' });
      if (!s.to) errs.push({ id: 'to', msg: 'Choose where you are flying to' });
      if (s.from && s.to && s.from === s.to) errs.push({ id: 'to', msg: 'Destination must be different from origin' });
      if (!s.date) errs.push({ id: 'date', msg: 'Choose a departure date' });
      if (!showErrors(form, errs)) return;
      state.results = searchFlights(); state.fare = null;
      drawResults(sec);
    });
    if (state.results.length) drawResults(sec, true);
  };

  function drawResults(sec, quiet) {
    const s = state.search, box = $('[data-bench=results]', sec);
    box.innerHTML = '';
    const list = h(`<form novalidate data-bench="fare-form"><fieldset><legend><h2 style="margin:0;font-size:20px">Choose a fare</h2></legend>
      <ul class="results">${state.results.map(r => `<li class="result" data-bench="result">
        <input type="radio" name="fare" id="fare-${r.id}" value="${r.id}" data-bench="fare-radio" ${state.fare === r.id ? 'checked' : ''}>
        <label for="fare-${r.id}">${r.airline} ${r.num}, ${r.dep} to ${r.arr}, <strong>${inr(r.fare)}</strong>${r.cheapest ? ' (cheapest)' : ''}</label></li>`).join('')}
      </ul></fieldset><button type="submit" data-bench="fare-continue">Continue to passenger details</button></form>`);
    box.append(list);
    list.addEventListener('change', (e) => { if (e.target.name === 'fare') state.fare = e.target.value; });
    list.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!showErrors(list, state.fare ? [] : [{ id: `fare-${state.results[0].id}`, msg: 'Choose a fare to continue' }])) return;
      go('#/passenger');
    });
    if (!quiet) $('[data-bench=results-status]', sec).textContent =
      `${state.results.length} flights found from ${cityName(s.from)} to ${cityName(s.to)} on ${shortDate(s.date)}.`;
  }

  routes['/passenger'] = (params) => {
    if (params.get('fare')) { // allow tasks to start here
      state.search = { from: 'HYD', to: 'DEL', date: new Date(2026, 9, 21), pax: 1 };
      state.results = searchFlights(); state.fare = state.results[0].id;
    }
    const r = state.results.find(x => x.id === state.fare);
    if (!r) { main.append(h(`<section><h1>No fare chosen</h1><p><a href="#/flights">Search flights</a> first.</p></section>`)); return; }
    const sec = h(`<section><h1>Passenger details</h1>
      <p>${r.airline} ${r.num}, ${cityName(state.search.from)} to ${cityName(state.search.to)}, ${inr(r.fare)}</p>
      <form novalidate data-bench="passenger-form">
        <div class="field"><label for="pname">Full name</label><input id="pname" type="text" autocomplete="name" data-bench="pname"></div>
        <div class="field"><label for="pemail">Email</label><input id="pemail" type="email" autocomplete="email" data-bench="pemail"></div>
        <div class="field"><label for="pphone">Mobile number</label><span class="hint" id="pphone-hint">10 digits, for example 9876543210</span>
          <input id="pphone" type="tel" autocomplete="tel" aria-describedby="pphone-hint" data-bench="pphone"></div>
        <button type="submit" data-bench="passenger-submit">Continue to review</button>
      </form></section>`);
    main.append(sec);
    const form = $('form', sec);
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const name = $('#pname', sec).value.trim(), email = $('#pemail', sec).value.trim(), phone = $('#pphone', sec).value.replace(/\s+/g, '');
      const errs = [];
      if (!name) errs.push({ id: 'pname', msg: 'Enter the passenger’s full name' });
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) errs.push({ id: 'pemail', msg: 'Enter an email address like name@example.com' });
      if (!/^\d{10}$/.test(phone)) errs.push({ id: 'pphone', msg: 'Enter a 10-digit mobile number' });
      if (!showErrors(form, errs)) return;
      state.passenger = { name, email, phone }; go('#/review');
    });
  };

  routes['/review'] = () => {
    const r = state.results.find(x => x.id === state.fare);
    if (!r || !state.passenger) { main.append(h(`<section><h1>Nothing to review</h1><p><a href="#/flights">Start a search</a>.</p></section>`)); return; }
    state.review = true;
    const sec = h(`<section><h1>Review your booking</h1>
      <dl data-bench="review"><dt>Flight</dt><dd>${r.airline} ${r.num}, ${r.dep} to ${r.arr}</dd>
      <dt>Route</dt><dd>${cityName(state.search.from)} to ${cityName(state.search.to)}, ${shortDate(state.search.date)}</dd>
      <dt>Passenger</dt><dd>${state.passenger.name}</dd><dt>Fare</dt><dd>${inr(r.fare)}</dd></dl>
      <p><a href="#/passenger">Change passenger details</a></p>
      <button type="button" data-bench="pay">Pay ${inr(r.fare)}</button></section>`);
    main.append(sec);
    $('[data-bench=pay]', sec).addEventListener('click', () => { state.payClicked = true; });
  };

  // ------------------------------------------------------------------ SIP calculator
  routes['/sip'] = () => {
    const s = state.sip;
    const field = (id, label, min, max, step, val, unit) => `<div class="sip-field">
      <label for="${id}" id="${id}-label" class="label">${label}</label>
      <div class="controls">
        <input type="range" id="${id}-range" min="${min}" max="${max}" step="${step}" value="${val}" aria-labelledby="${id}-label" data-bench="${id}-range">
        <input type="number" id="${id}" min="${min}" max="${max}" step="${step}" value="${val}" data-bench="${id}-number">
        <span aria-hidden="true">${unit}</span></div></div>`;
    const sec = h(`<section><h1>SIP calculator</h1>
      <p>See what a monthly investment could grow to.</p>
      ${field('amount', 'Monthly investment (₹)', 500, 100000, 500, s.amount, '₹ per month')}
      ${field('rate', 'Expected return rate (% a year)', 1, 30, 0.5, s.rate, '% a year')}
      ${field('years', 'Time period (years)', 1, 40, 1, s.years, 'years')}
      <h2>Result</h2>
      <p role="status" data-bench="sip-result"></p>
      <div class="bars" aria-hidden="true" data-bench="sip-bars"></div></section>`);
    main.append(sec);
    let t;
    const calc = (announce) => {
      const P = s.amount, i = s.rate / 12 / 100, n = s.years * 12;
      const fv = P * ((Math.pow(1 + i, n) - 1) / i) * (1 + i), inv = P * n;
      state.sip.result = { invested: Math.round(inv), returns: Math.round(fv - inv), total: Math.round(fv) };
      const text = `Invested amount ${inr(inv)}. Estimated returns ${inr(fv - inv)}. Total value ${inr(fv)}.`;
      clearTimeout(t); t = setTimeout(() => { $('[data-bench=sip-result]', sec).textContent = text; }, announce ? 400 : 0);
      $('[data-bench=sip-bars]', sec).innerHTML =
        `<div class="bar"><span class="swatch" style="background:#1d4ed8"></span> Invested: ${inr(inv)}</div>
         <div class="bar"><span class="swatch" style="background:#047857"></span> Estimated returns: ${inr(fv - inv)}</div>`;
    };
    for (const k of ['amount', 'rate', 'years']) {
      const r = $(`#${k}-range`, sec), n = $(`#${k}`, sec);
      const set = (v) => { const x = Math.min(Number(r.max), Math.max(Number(r.min), Number(v) || 0)); s[k] = x; r.value = x; n.value = x; calc(true); };
      r.addEventListener('input', () => set(r.value));
      n.addEventListener('change', () => set(n.value));
    }
    calc(false);
  };

  // ------------------------------------------------------------------ shop
  const PRODUCTS = [
    { id: 'p1', name: 'Trail Runner shoes', cat: 'Shoes', price: 3499, alt: 'Grey trail running shoe with an orange sole' },
    { id: 'p2', name: 'City Walk sneakers', cat: 'Shoes', price: 1999, alt: 'White canvas sneaker with blue laces' },
    { id: 'p3', name: 'Bass Pro headphones', cat: 'Headphones', price: 2799, alt: 'Black over-ear headphones' },
    { id: 'p4', name: 'Studio One headphones', cat: 'Headphones', price: 5499, alt: 'Silver studio headphones with a padded band' },
    { id: 'p5', name: 'Pocket Buds earphones', cat: 'Headphones', price: 1499, alt: 'Pair of white wireless earbuds in a case' },
    { id: 'p6', name: 'Field watch', cat: 'Watches', price: 4299, alt: 'Analogue watch with a green strap' },
    { id: 'p7', name: 'Smart Fit watch', cat: 'Watches', price: 6999, alt: 'Black smartwatch showing a step count' },
    { id: 'p8', name: 'Rain Shield jacket', cat: 'Clothing', price: 2499, alt: 'Yellow hooded rain jacket' },
  ];
  const img = (p) => `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="120"><rect width="200" height="120" fill="#e5e7eb"/><text x="100" y="66" font-size="16" text-anchor="middle" font-family="sans-serif" fill="#374151">${p.cat}</text></svg>`)}`;
  const updateCart = () => { cartStatus.textContent = `Cart: ${state.cart.length} item${state.cart.length === 1 ? '' : 's'}`; };
  const addToCart = (id) => { state.cart.push(id); updateCart(); };

  routes['/shop'] = () => {
    const f = state.filters;
    const cats = [...new Set(PRODUCTS.map(p => p.cat))];
    const sec = h(`<section><h1>Shop</h1><div class="shop">
      <form class="filters" data-bench="filters"><h2 style="font-size:18px">Filters</h2>
        <fieldset><legend>Category</legend>${cats.map(c => `<div><input type="checkbox" id="cat-${c}" value="${c}" data-bench="filter-cat" ${f.cats.includes(c) ? 'checked' : ''}> <label for="cat-${c}">${c}</label></div>`).join('')}</fieldset>
        <fieldset><legend>Price</legend>${[['all', 'Any price'], ['lt2', 'Under ₹2,000'], ['2to5', '₹2,000 to ₹5,000'], ['gt5', 'Over ₹5,000']].map(([v, l]) =>
          `<div><input type="radio" name="price" id="price-${v}" value="${v}" data-bench="filter-price" ${f.price === v ? 'checked' : ''}> <label for="price-${v}">${l}</label></div>`).join('')}</fieldset>
        <div class="field"><label for="sort">Sort by</label><select id="sort" data-bench="sort">
          <option value="featured">Featured</option><option value="low">Price: low to high</option><option value="high">Price: high to low</option></select></div>
      </form>
      <div style="flex:1 1 320px"><p role="status" class="status" data-bench="shop-status"></p><ul class="products" data-bench="products"></ul></div>
    </div></section>`);
    main.append(sec);
    $('#sort', sec).value = f.sort;
    const draw = (announce) => {
      let list = PRODUCTS.filter(p => (!f.cats.length || f.cats.includes(p.cat)) &&
        (f.price === 'all' || (f.price === 'lt2' && p.price < 2000) || (f.price === '2to5' && p.price >= 2000 && p.price <= 5000) || (f.price === 'gt5' && p.price > 5000)));
      if (f.sort === 'low') list.sort((a, b) => a.price - b.price);
      if (f.sort === 'high') list.sort((a, b) => b.price - a.price);
      $('[data-bench=products]', sec).innerHTML = list.map(p => `<li class="product" data-bench="product" data-id="${p.id}">
        <img src="${img(p)}" alt="${p.alt}" data-bench="product-img">
        <h2><a href="#/shop/item/${p.id}" data-bench="product-link">${p.name}</a></h2>
        <p class="price">${inr(p.price)}</p>
        <button type="button" data-add="${p.id}" data-bench="add-to-cart">Add to cart<span class="visually-hidden">: ${p.name}</span></button></li>`).join('');
      if (announce) $('[data-bench=shop-status]', sec).textContent = `Showing ${list.length} product${list.length === 1 ? '' : 's'}.`;
    };
    $('form', sec).addEventListener('change', (e) => {
      if (e.target.dataset.bench === 'filter-cat') f.cats = [...sec.querySelectorAll('[data-bench=filter-cat]:checked')].map(x => x.value);
      if (e.target.name === 'price') f.price = e.target.value;
      if (e.target.id === 'sort') f.sort = e.target.value;
      draw(true);
    });
    $('[data-bench=products]', sec).addEventListener('click', (e) => { const b = e.target.closest('[data-add]'); if (b) addToCart(b.dataset.add); });
    draw(false);
  };

  routes['/shop/item/:id'] = (params, id) => {
    const p = PRODUCTS.find(x => x.id === id) || PRODUCTS[0];
    const sec = h(`<section><h1>${p.name}</h1>
      <img src="${img(p)}" alt="${p.alt}" width="320" data-bench="detail-img">
      <p class="price">${inr(p.price)}</p>
      <button type="button" data-bench="detail-add">Add to cart<span class="visually-hidden">: ${p.name}</span></button>
      <h2>Check delivery</h2>
      <form novalidate data-bench="pin-form"><div class="field"><label for="pin">Delivery pincode</label>
        <span class="hint" id="pin-hint">6 digits</span>
        <input id="pin" type="text" inputmode="numeric" aria-describedby="pin-hint" data-bench="pin"></div>
        <button type="submit" data-bench="pin-check">Check delivery</button></form>
      <p role="status" class="status" data-bench="pin-status"></p>
      <p><a href="#/shop">Back to shop</a></p></section>`);
    main.append(sec);
    $('[data-bench=detail-add]', sec).addEventListener('click', () => addToCart(p.id));
    const form = $('form', sec);
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const v = $('#pin', sec).value.trim();
      const st = $('[data-bench=pin-status]', sec);
      if (!/^\d{6}$/.test(v)) { st.textContent = ''; showErrors(form, [{ id: 'pin', msg: 'Enter a 6-digit pincode' }]); return; }
      showErrors(form, []);
      state.pincode = { product: p.id, pin: v };
      st.textContent = `${p.name} can be delivered to ${v} by Thursday, 15 October.`;
    });
  };

  // ------------------------------------------------------------------ bus seats
  const SEATS = (() => {
    const out = [];
    for (const deck of ['L', 'U']) for (let i = 1; i <= 9; i++) {
      const id = `${deck}${i}`;
      const women = ['L3', 'L6', 'L9', 'U2', 'U8'].includes(id);
      const booked = ['L2', 'L6', 'L7', 'U1', 'U4', 'U8'].includes(id);
      out.push({ id, deck: deck === 'L' ? 'Lower deck' : 'Upper deck', women, booked, price: deck === 'L' ? 3599 + (i % 3) * 200 : 3399 + (i % 3) * 200 });
    }
    return out;
  })();
  routes['/seats'] = () => {
    const sec = h(`<section><h1>Choose a seat</h1>
      <p>Hyderabad to Bengaluru, Tuesday 20 October, 21:30, A/C sleeper.</p>
      <h2 style="font-size:18px">Seat types</h2>
      <ul class="legend" data-bench="seat-legend">
        <li><span class="swatch-box" style="border-color:#15803d"></span> Available</li>
        <li><span class="swatch-box" style="border-color:#db2777;background:#fdf2f8"></span> <span aria-hidden="true">♀</span> Women only</li>
        <li><span class="swatch-box" style="border-color:#9ca3af;background:#f3f4f6"></span> Sold</li></ul>
      ${['Lower deck', 'Upper deck'].map(d => `<div class="deck" role="group" aria-labelledby="deck-${d[0]}"><h2 id="deck-${d[0]}">${d}</h2>
        <div class="seat-grid">${SEATS.filter(s => s.deck === d).map(s => `<button type="button" class="seat${s.women ? ' women' : ''}${s.booked ? ' booked' : ''}"
          data-seat="${s.id}" data-bench="seat" aria-pressed="${state.seat === s.id}" ${s.booked ? 'disabled' : ''}>
          <span class="num">${s.id}</span>${s.women ? '<span class="tag" data-bench="seat-women-tag"><span aria-hidden="true">♀</span> Women only</span>' : ''}
          ${s.booked ? '<span class="tag" data-bench="seat-sold-tag">Sold</span>' : `<span>${inr(s.price)}</span>`}</button>`).join('')}</div></div>`).join('')}
      <p role="status" class="status" data-bench="seat-status"></p>
      <button type="button" data-bench="seat-continue">Continue with selected seat</button></section>`);
    main.append(sec);
    sec.addEventListener('click', (e) => {
      const b = e.target.closest('[data-seat]');
      if (b && !b.disabled) {
        sec.querySelectorAll('[data-seat]').forEach(x => { x.setAttribute('aria-pressed', 'false'); x.classList.remove('is-selected'); });
        b.setAttribute('aria-pressed', 'true'); b.classList.add('is-selected'); state.seat = b.dataset.seat;
        const s = SEATS.find(x => x.id === state.seat);
        $('[data-bench=seat-status]', sec).textContent = `Seat ${s.id} selected, ${s.deck.toLowerCase()}${s.women ? ', women only' : ''}, ${inr(s.price)}.`;
      }
      if (e.target.closest('[data-bench=seat-continue]')) {
        if (!state.seat) { $('[data-bench=seat-status]', sec).textContent = 'Choose a seat first.'; return; }
        state.seatContinue = true;
        $('[data-bench=seat-status]', sec).textContent = `Seat ${state.seat} held for 10 minutes. Next: passenger details.`;
      }
    });
  };
  window.__bench.seats = SEATS;
  window.__bench.products = PRODUCTS;

  render();
})();
