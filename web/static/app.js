'use strict';

// ── State ────────────────────────────────────────────────────
const state = { baseline: null, new: null };

// ── DOM refs ─────────────────────────────────────────────────
const zoneBaseline   = document.getElementById('zone-baseline');
const zoneNew        = document.getElementById('zone-new');
const inputBaseline  = document.getElementById('input-baseline');
const inputNew       = document.getElementById('input-new');
const badgeBaseline  = document.getElementById('badge-baseline');
const badgeNew       = document.getElementById('badge-new');
const btnCompare     = document.getElementById('btn-compare');
const btnHint        = document.getElementById('btn-hint');
const spinner        = document.getElementById('spinner');
const results        = document.getElementById('results');
const resultHeader   = document.getElementById('result-header');
const resultBadge    = document.getElementById('result-badge');
const resultFilenames = document.getElementById('result-filenames');
const resultStats    = document.getElementById('result-stats');
const resultDetails  = document.getElementById('result-details');

// ── Drop zone wiring ─────────────────────────────────────────
function wireZone(zone, input, role) {
  zone.addEventListener('click', (e) => {
    if (e.target.tagName === 'LABEL') return; // let label handle its own click
    input.click();
  });

  input.addEventListener('change', () => {
    if (input.files[0]) setFile(role, input.files[0]);
  });

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) setFile(role, file);
  });
}

wireZone(zoneBaseline, inputBaseline, 'baseline');
wireZone(zoneNew,      inputNew,      'new');

function setFile(role, file) {
  state[role] = file;
  const zone  = role === 'baseline' ? zoneBaseline : zoneNew;
  const badge = role === 'baseline' ? badgeBaseline : badgeNew;

  zone.classList.add('has-file');
  badge.textContent = file.name;
  badge.hidden = false;

  updateButton();
}

function updateButton() {
  const ready = state.baseline && state.new;
  btnCompare.disabled = !ready;
  btnHint.textContent = ready ? '' : 'Drop both files to compare';
}

// ── Compare ──────────────────────────────────────────────────
btnCompare.addEventListener('click', runCompare);

async function runCompare() {
  results.hidden = true;
  spinner.hidden = false;
  btnCompare.disabled = true;

  const form = new FormData();
  form.append('baseline', state.baseline);
  form.append('new', state.new);
  form.append('tolerance',         parseFloat(document.getElementById('opt-tolerance').value)     || 0);
  form.append('tolerance_pct',     (parseFloat(document.getElementById('opt-tolerance-pct').value) || 0) / 100);
  form.append('ignore_order',      document.getElementById('opt-ignore-order').checked);
  form.append('ignore_numerics',   document.getElementById('opt-ignore-numerics').checked);
  form.append('ignore_timestamps', document.getElementById('opt-ignore-timestamps').checked);

  try {
    const res  = await fetch('/compare', { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Server error ${res.status}: ${text}`);
    }
    const data = await res.json();
    renderResults(data);
  } catch (err) {
    renderError(err.message);
  } finally {
    spinner.hidden = true;
    btnCompare.disabled = false;
  }
}

// ── Render results ───────────────────────────────────────────
function renderResults(data) {
  const passed = data.result === 'PASS';

  // Header
  resultHeader.className = `result-header ${passed ? 'pass' : 'fail'}`;
  resultBadge.textContent = data.result;
  resultBadge.className   = `result-badge ${passed ? 'pass' : 'fail'}`;
  resultFilenames.innerHTML =
    `<strong>${esc(data.baseline_filename)}</strong> vs <strong>${esc(data.new_filename)}</strong>`;

  // Stats
  const orderCount   = data.order_mismatches.length;
  const numericCount = data.numeric_mismatches.length;
  const warnCount    = data.warnings.length;

  resultStats.innerHTML = `
    <div class="stat-cell">
      <span class="stat-label">Baseline lines</span>
      <span class="stat-value neutral">${data.baseline_line_count}</span>
    </div>
    <div class="stat-cell">
      <span class="stat-label">New lines</span>
      <span class="stat-value neutral">${data.new_line_count}</span>
    </div>
    <div class="stat-cell">
      <span class="stat-label">Order issues</span>
      <span class="stat-value ${orderCount > 0 ? 'bad' : 'ok'}">${orderCount}</span>
    </div>
    <div class="stat-cell">
      <span class="stat-label">Numeric issues</span>
      <span class="stat-value ${numericCount > 0 ? 'bad' : 'ok'}">${numericCount}</span>
    </div>
    <div class="stat-cell">
      <span class="stat-label">Warnings</span>
      <span class="stat-value ${warnCount > 0 ? 'bad' : 'ok'}">${warnCount}</span>
    </div>
  `;

  // Details
  resultDetails.innerHTML = '';

  if (passed && orderCount === 0 && numericCount === 0 && warnCount === 0) {
    resultDetails.innerHTML =
      '<div class="all-pass-msg">&#10003; All checks passed — files match within tolerance</div>';
  } else {
    if (data.order_mismatches.length > 0) {
      resultDetails.appendChild(
        buildMismatchSection('Order mismatches', data.order_mismatches)
      );
    }
    if (data.numeric_mismatches.length > 0) {
      resultDetails.appendChild(
        buildMismatchSection('Numeric mismatches', data.numeric_mismatches)
      );
    }
    if (data.warnings.length > 0) {
      resultDetails.appendChild(buildWarningsSection(data.warnings));
    }
  }

  results.hidden = false;
  results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function buildMismatchSection(title, mismatches) {
  const wrap = document.createElement('div');
  wrap.innerHTML = `<div class="section-heading">${esc(title)} (${mismatches.length})</div>`;
  const list = document.createElement('div');
  list.className = 'mismatch-list';

  mismatches.forEach(m => {
    const card = document.createElement('div');
    card.className = `mismatch-card ${m.kind}`;

    const locs = [];
    if (m.baseline_lineno != null) locs.push(`baseline line ${m.baseline_lineno}`);
    if (m.new_lineno != null)      locs.push(`new line ${m.new_lineno}`);
    const locStr = locs.length ? locs.join(', ') : '';

    card.innerHTML = `
      <div><span class="mismatch-kind ${m.kind}">${esc(m.kind)}</span></div>
      ${locStr ? `<div class="mismatch-loc">${esc(locStr)}</div>` : ''}
      <pre class="mismatch-detail">${esc(m.detail)}</pre>
    `;
    list.appendChild(card);
  });

  wrap.appendChild(list);
  return wrap;
}

function buildWarningsSection(warnings) {
  const wrap = document.createElement('div');
  wrap.innerHTML = `<div class="section-heading">Warnings (${warnings.length})</div>`;
  const list = document.createElement('div');
  list.className = 'warning-list';
  warnings.forEach(w => {
    const item = document.createElement('div');
    item.className = 'warning-item';
    item.textContent = w;
    list.appendChild(item);
  });
  wrap.appendChild(list);
  return wrap;
}

function renderError(msg) {
  results.hidden = false;
  resultHeader.className = 'result-header fail';
  resultBadge.textContent = 'ERROR';
  resultBadge.className = 'result-badge fail';
  resultFilenames.textContent = '';
  resultStats.innerHTML = '';
  resultDetails.innerHTML = `<pre class="mismatch-detail" style="color:var(--fail)">${esc(msg)}</pre>`;
}

// ── Helpers ──────────────────────────────────────────────────
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
