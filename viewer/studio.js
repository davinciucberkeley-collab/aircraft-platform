// Plane Studio: buttons and dialogs on top of the viewer. Loaded only when the page is served by
// `plane studio` (index.json has "studio": true); the GitHub Pages viewer never loads it.
// Every action calls the local API, which runs the same core library as the CLI and CI.

const V = window.planeViewer;
let ping = {};
let lastRev = -1;
let lastJobState = '';

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'value') el.value = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}
const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const r = await fetch('api/' + path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

function toast(text, kind = '') {
  const t = h('div', { class: 'toast ' + kind, role: 'status' }, text);
  $('toasts').append(t);
  setTimeout(() => t.remove(), kind === 'err' ? 9000 : 4000);
}

// ---------- dialogs ----------
function dialog(title, body, actions) {
  const err = h('div', { class: 'dlg-err', hidden: true });
  const dlg = h('dialog', { class: 'dlg' },
    h('form', { method: 'dialog' },
      h('header', {}, h('h2', {}, title), h('button', { class: 'icon', value: 'cancel', 'aria-label': 'Close', type: 'submit' }, '×')),
      h('div', { class: 'dlg-body' }, body), err,
      h('footer', {}, h('button', { value: 'cancel', type: 'submit', class: 'ghost' }, 'Cancel'), actions)));
  dlg.showError = (m) => { err.textContent = m; err.hidden = !m; };
  dlg.addEventListener('close', () => dlg.remove());
  document.body.append(dlg);
  dlg.showModal();
  return dlg;
}
function field(label, input, hint) {
  return h('label', { class: 'field' }, h('span', { class: 'lbl' }, label), input, hint ? h('span', { class: 'hint' }, hint) : null);
}
function primary(label, onclick) {
  return h('button', { type: 'button', class: 'primary', onclick: async (e) => {
    const b = e.currentTarget; const dlg = b.closest('dialog');
    b.disabled = true; dlg.showError('');
    try { await onclick(dlg); } catch (err) { dlg.showError(err.message); } finally { b.disabled = false; }
  } }, label);
}
const slug = (s) => s.toLowerCase().trim().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');

function newDesignDialog(fromId) {
  const designs = V.designs();
  const from = h('select', {}, designs.map((d) => h('option', { value: d.id, selected: d.id === (fromId || V.selected()) }, d.name ? `${d.name} (${d.id})` : d.id)));
  const name = h('input', { type: 'text', placeholder: 'e.g. concept-a-bigger-wing', autofocus: true });
  dialog('New design', [
    field('Start from', from, 'Copies its file and 3D parts; the original is not touched.'),
    field('Name', name, 'Lowercase letters, numbers and dashes.'),
  ], primary('Create', async (dlg) => {
    const id = slug(name.value);
    if (!id) throw new Error('Give the new design a name.');
    await api('new', { id, from: from.value });
    dlg.close(); toast(`Created ${id}. Checking it now.`);
    await V.reload(id);
  }));
}

function importDialog() {
  const root = h('input', { type: 'text', value: ping.dbf_root_guess || '', placeholder: 'C:\\Users\\you\\Documents\\dbf-combined' });
  const concept = h('input', { type: 'text', value: 'A', maxlength: 4, style: 'width:70px' });
  const id = h('input', { type: 'text', value: 'concept-a' });
  const warn = h('p', { class: 'hint warn' });
  const upd = () => { const v = slug(id.value); warn.textContent = V.designs().some((d) => d.id === v) ? `“${v}” already exists and will be replaced by the fresh import.` : ''; };
  id.addEventListener('input', upd); upd();
  dialog('Import from DBF-Combined', [
    h('p', { class: 'muted' }, 'Rebuilds a concept from Dillon’s CAD scripts as exact solids. It only reads that folder.'),
    field('DBF-Combined folder', root, 'Paste the folder path from File Explorer (right-click the folder › Copy as path).'),
    h('div', { class: 'row' }, field('Concept', concept), field('Save as', id)), warn,
  ], primary('Import', async (dlg) => {
    await api('import-dbf', { root: root.value, concept: concept.value, id: slug(id.value) });
    dlg.close(); toast('Import started. It shows up in the list when it is done.');
  }));
}

// ---------- editor: forms for the common edits, the raw file for everything else ----------
const num = (v) => (v === '' || v == null ? null : Number(v));
function input(value, attrs = {}) {
  const el = h('input', { type: attrs.type || 'number', step: 'any', class: 'cell', ...attrs, value: value ?? '' });
  el.dataset.orig = value ?? '';
  return el;
}
function select(value, options, attrs = {}) {
  const opts = [...new Set([...(value ? [value] : []), ...options])];
  const el = h('select', { class: 'cell', ...attrs }, (value ? [] : [h('option', { value: '' }, '—')]).concat(opts.map((o) => h('option', { value: o, selected: o === value }, o))));
  el.dataset.orig = value ?? '';
  return el;
}
const changed = (el) => String(el.value) !== String(el.dataset.orig);

async function editDialog(id) {
  const d = V.designs().find((x) => x.id === id);
  const [{ data, enums }, { text }, sc] = await Promise.all([
    api('design?id=' + encodeURIComponent(id)), api('yaml?id=' + encodeURIComponent(id)),
    d?.scorecard ? fetch('data/' + d.scorecard).then((r) => r.json()).catch(() => null) : null]);
  const failMsgs = (sc?.tiers || []).flatMap((t) => t.results).filter((r) => r.status === 'FAIL').map((r) => r.message);
  const failsFor = (jid) => failMsgs.filter((m) => m.includes(jid + ':') || m.includes(jid + ' '));
  const edits = []; // {el, path, kind}
  const track = (el, path, kind = 'num') => { edits.push({ el, path, kind }); el.addEventListener('input', () => el.classList.toggle('dirty', changed(el))); el.addEventListener('change', () => el.classList.toggle('dirty', changed(el))); return el; };

  // Overview
  const req = data.requirements || {};
  const overview = h('div', { class: 'tabpane' },
    h('div', { class: 'grid2' },
      field('Name', track(input(data.name, { type: 'text' }), ['name'], 'text')),
      field('Status', track(select(data.status, enums.status), ['status'], 'text'))),
    field('Description', track(Object.assign(h('textarea', { class: 'cell desc', rows: 3 }), { value: data.description || '' }), ['description'], 'text')),
    h('h3', {}, 'Requirements'),
    h('div', { class: 'grid3' }, enums.requirements.map((k) => field(k.replace(/_/g, ' '), track(input(req[k]), ['requirements', k])))));
  overview.querySelector('textarea').dataset.orig = data.description || '';

  // Parts
  const comps = data.components || [];
  const partRows = comps.map((c) => {
    const pos = Array.isArray(c.position) ? c.position : [null, null, null];
    const px = pos.map((v) => input(v, { class: 'cell xs' }));
    const posEdit = { el: px[0], path: ['components', { id: c.id }, 'position'], kind: 'pos', els: px };
    px.forEach((e) => e.addEventListener('input', () => e.classList.toggle('dirty', changed(e))));
    edits.push(posEdit);
    return h('tr', { 'data-q': `${c.id} ${c.type} ${c.description || ''}`.toLowerCase() },
      h('td', {}, h('code', {}, c.id), c.description ? h('div', { class: 'hint' }, c.description) : null),
      h('td', {}, c.type),
      h('td', {}, track(input(c.mass_g, { class: 'cell sm' }), ['components', { id: c.id }, 'mass_g'])),
      h('td', { class: 'xyz' }, px),
      h('td', {}, track(select(c.manufacturing?.method, enums.manufacturing), ['components', { id: c.id }, 'manufacturing', 'method'], 'text')));
  });
  const partFilter = h('input', { type: 'search', placeholder: `Filter ${comps.length} parts`, oninput: (e) => { const q = e.target.value.toLowerCase(); partRows.forEach((r) => (r.hidden = q && !r.dataset.q.includes(q))); } });
  const parts = h('div', { class: 'tabpane', hidden: true }, partFilter,
    h('table', { class: 'edit' }, h('thead', {}, h('tr', {}, ['Part', 'Type', 'Mass (g)', 'Position x, y, z (mm)', 'Made by'].map((t) => h('th', {}, t)))), h('tbody', {}, partRows)));

  // Joints
  const atts = data.attachments || [];
  const jointRows = atts.map((a) => {
    const f = failsFor(a.id);
    return h('tr', { class: f.length ? 'failing' : '', 'data-q': `${a.id} ${a.parent} ${a.child} ${a.method} ${f.length ? 'failing' : ''} ${a.rating_basis || ''}`.toLowerCase() },
      h('td', {}, h('code', {}, a.id), f.map((m) => h('div', { class: 'hint fail' }, m))),
      h('td', {}, h('span', { class: 'mono small' }, `${a.parent} → ${a.child}`)),
      h('td', {}, track(select(a.method, enums.joint_method), ['attachments', { id: a.id }, 'method'], 'text')),
      h('td', {}, track(input(a.rated_load_n, { class: 'cell sm' }), ['attachments', { id: a.id }, 'rated_load_n'])),
      h('td', {}, track(select(a.rating_basis, enums.rating_basis), ['attachments', { id: a.id }, 'rating_basis'], 'text')));
  });
  const nFail = jointRows.filter((r) => r.classList.contains('failing')).length;
  const jointFilter = h('input', { type: 'search', placeholder: `Filter ${atts.length} joints (try “failing” or “placeholder”)`, oninput: (e) => { const q = e.target.value.toLowerCase(); jointRows.forEach((r) => (r.hidden = q && !q.split(/\s+/).every((t) => r.dataset.q.includes(t)))); } });
  const joints = h('div', { class: 'tabpane', hidden: true }, jointFilter,
    h('table', { class: 'edit' }, h('thead', {}, h('tr', {}, ['Joint', 'Connects', 'Method', 'Strength (N)', 'Strength source'].map((t) => h('th', {}, t)))), h('tbody', {}, jointRows)));

  // File
  const ta = h('textarea', { class: 'yaml', spellcheck: 'false', wrap: 'off' }); ta.value = text;
  ta.addEventListener('keydown', (e) => { if (e.key === 'Tab') { e.preventDefault(); const s0 = ta.selectionStart; ta.setRangeText('  ', s0, ta.selectionEnd, 'end'); } });
  const file = h('div', { class: 'tabpane', hidden: true }, h('p', { class: 'muted' }, 'The whole design file, for anything the forms don’t cover. Units: mm, g, N, degrees.'), ta);

  const panes = { Overview: overview, Parts: parts, [`Joints${nFail ? ` (${nFail} failing)` : ''}`]: joints, 'File (advanced)': file };
  const tabs = h('div', { class: 'seg tabs' }, Object.entries(panes).map(([name, pane], i) => h('button', { type: 'button', class: i ? '' : 'active', onclick: (e) => {
    tabs.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === e.currentTarget));
    Object.values(panes).forEach((p) => (p.hidden = p !== pane));
    if (pane === file) { ta.setSelectionRange(0, 0); ta.scrollTop = 0; }
  } }, name)));

  const dlg = dialog(`Edit ${d?.name || id}`, [
    h('p', { class: 'muted' }, 'Change values, then Save. Every save keeps a backup and re-runs all the checks.'), tabs, overview, parts, joints, file,
  ], primary('Save and check', async (dd) => {
    const fileChanged = ta.value !== text;
    const changes = [];
    for (const e of edits) {
      if (e.kind === 'pos') {
        if (!e.els.some(changed)) continue;
        const v = e.els.map((x) => num(x.value));
        if (v.some((x) => x == null || Number.isNaN(x))) throw new Error(`${e.path[1].id}: fill in all three position numbers`);
        changes.push({ path: e.path, value: v });
      } else if (changed(e.el)) {
        const v = e.kind === 'num' ? num(e.el.value) : e.el.value;
        if (e.kind === 'num' && Number.isNaN(v)) throw new Error(`Not a number: ${e.el.value}`);
        changes.push({ path: e.path, value: v });
      }
    }
    if (fileChanged && changes.length) throw new Error('You changed both the forms and the file. Save one of them: undo the other first.');
    if (fileChanged) await api('yaml', { id, text: ta.value });
    else if (changes.length) await api('patch', { id, changes });
    else { dd.close(); return; }
    dd.close(); toast(`Saved ${id}${changes.length ? ` (${changes.length} change${changes.length > 1 ? 's' : ''})` : ''}. Checking it now.`);
    await V.reload(id);
  }));
  dlg.classList.add('wide');
}

// ---------- stress check (OpenCAE) ----------
function feaSetup(oc, after) {
  const py = h('input', { type: 'text', value: oc?.python || '', placeholder: 'C:\\Users\\you\\.conda\\envs\\qt_test\\python.exe' });
  const root = h('input', { type: 'text', value: oc?.root || '', placeholder: 'C:\\Users\\you\\Documents\\OpenCAE-Studio' });
  dialog('Connect OpenCAE', [
    h('p', { class: 'muted' }, 'The stress check runs in OpenCAE Studio. Point the app at it once.'),
    field('OpenCAE’s Python', py, 'python.exe of the environment that runs OpenCAE (the one with PySide6, gmsh and OCP). Tip: in that environment run  where python'),
    field('OpenCAE folder', root, 'The folder that contains the opencae folder and launch_opencae.bat.'),
  ], primary('Save', async (dlg) => {
    await api('fea-setup', { python: py.value, root: root.value });
    dlg.close(); toast('OpenCAE connected.'); after?.();
  }));
}

async function feaDialog(id) {
  const st = await api('fea?id=' + encodeURIComponent(id));
  if (!st.opencae.found) return feaSetup(st.opencae, () => feaDialog(id));
  const badge = (r) => !r.status ? h('span', { class: 'badge NONE' }, 'not run')
    : r.up_to_date === false ? h('span', { class: 'badge WARN' }, 'out of date')
    : r.status === 'NOT CHECKED' ? h('span', { class: 'badge WARN', title: (r.cases || []).map((c) => c.message).filter(Boolean).join('\n') }, 'not checked')
    : h('span', { class: 'badge ' + (r.status === 'ERROR' ? 'FAIL' : r.status) }, r.status === 'FAIL' && r.error ? 'error' : r.status);
  const boxes = [];
  const rows = st.parts.map((r) => {
    const cb = h('input', { type: 'checkbox', checked: !r.status || r.up_to_date === false || r.status === 'FAIL' });
    cb.dataset.part = r.part; boxes.push(cb);
    const worst = (r.cases || []).filter((c) => c.safety_factor_at_ultimate != null).sort((a, b) => a.safety_factor_at_ultimate - b.safety_factor_at_ultimate)[0];
    return h('tr', { class: r.status === 'FAIL' ? 'failing' : '' },
      h('td', {}, cb), h('td', {}, h('code', {}, r.part), h('div', { class: 'hint' }, r.description)),
      h('td', {}, badge(r)),
      h('td', { class: 'mono small' }, worst ? `${worst.max_von_mises_away_mpa} MPa · SF ${worst.safety_factor_at_ultimate} (${worst.name})` : (r.error ? r.error.slice(0, 80) : '—')),
      h('td', {}, (r.files || []).filter((f) => f.kind !== 'ocae').map((f) => h('a', { href: `api/fea-file?id=${encodeURIComponent(id)}&part=${encodeURIComponent(r.part)}&name=${encodeURIComponent(f.name)}`, target: f.kind === 'html' ? '_blank' : null, class: 'filelink' }, f.kind === 'html' ? 'report' : 'ParaView'))));
  });
  const allow = st.allowable_mpa, uf = st.ultimate_factor;
  const dlg = dialog(`Stress check: ${id}`, [
    h('p', { class: 'muted' }, `Each printed part is meshed and solved in OpenCAE (CalculiX) for two load cases: the joint loads from the landing drop test, and hover at full thrust, both ×${uf}. It passes when the stress away from the clamps stays under ${allow} MPa (printed PETG, interlayer strength). Expect a few seconds to a few minutes per part.`),
    h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn', onclick: () => boxes.forEach((b) => (b.checked = true)) }, 'All'),
      h('button', { type: 'button', class: 'btn', onclick: () => boxes.forEach((b) => (b.checked = false)) }, 'None'),
      h('button', { type: 'button', class: 'btn', onclick: () => { dlg.close(); feaSetup(st.opencae); } }, 'OpenCAE settings')),
    h('div', { class: 'tabpane' }, h('table', { class: 'edit' }, h('thead', {}, h('tr', {}, ['', 'Part', 'Result', 'Worst case', 'Files'].map((t) => h('th', {}, t)))), h('tbody', {}, rows))),
  ], primary('Run selected', async (d) => {
    const parts = boxes.filter((b) => b.checked).map((b) => b.dataset.part);
    if (!parts.length) throw new Error('Tick at least one part.');
    await api('fea', { id, parts });
    d.close(); toast(`Stress check started for ${parts.length} part${parts.length > 1 ? 's' : ''}. Progress shows on the left.`);
  }));
  dlg.classList.add('wide');
}

// ---------- action bar on the scorecard ----------
const EXPORTS = [
  ['glb', '3D model (.glb)', 'Opens in Windows 3D Viewer, Blender, web viewers'],
  ['stl', 'Parts for printing (.stl, zipped)', 'One file per part, in mm'],
  ['report', 'Scorecard report (.md)', 'For a PR, a review or Douglas'],
  ['mjcf', 'Physics sim model (MuJoCo, zipped)', ''],
  ['json', 'Design data (.json)', ''],
];
function actionBar(box, d) {
  const exp = h('details', { class: 'menu' }, h('summary', { class: 'btn' }, 'Download ▾'),
    h('div', { class: 'menu-list' }, EXPORTS.map(([f, label, hint]) =>
      h('a', { href: `api/export?id=${encodeURIComponent(d.id)}&format=${f}`, download: '', onclick: () => toast('Preparing the download…') },
        h('b', {}, label), hint ? h('span', {}, hint) : null))));
  const bar = h('div', { class: 'studio-bar' },
    h('button', { class: 'btn', disabled: d.pending, onclick: async () => { await api('check', { id: d.id }); toast(`Checking ${d.id}…`); } }, d.pending ? 'Checking…' : 'Check again'),
    h('button', { class: 'btn', onclick: () => editDialog(d.id).catch((e) => toast(e.message, 'err')) }, 'Edit design'),
    h('button', { class: 'btn', onclick: () => newDesignDialog(d.id) }, 'Make a copy'),
    h('button', { class: 'btn', onclick: () => feaDialog(d.id).catch((e) => toast(e.message, 'err')) }, 'Stress check'),
    d.error || d.pending ? null : exp);
  box.querySelector('.sub')?.after(bar);
}

// ---------- jobs ----------
function renderJobs(st) {
  const box = $('jobs');
  const running = st.jobs.filter((j) => j.state === 'running' || j.state === 'queued');
  const recent = st.jobs.filter((j) => j.state === 'done' || j.state === 'error').slice(0, 3);
  const rows = recent.map((j) => h('div', { class: 'job ' + j.state, title: j.message }, j.state === 'error' ? '✕ ' : '✓ ', `${j.label}: `, h('span', { class: 'muted' }, j.message)));
  if (running.length) {
    const cur = running.find((j) => j.state === 'running') || running[0];
    rows.unshift(h('div', { class: 'job running' }, h('span', { class: 'spin' }), cur.label + (cur.message ? `: ${cur.message}` : ''), running.length > 1 ? h('span', { class: 'muted' }, ` +${running.length - 1} waiting`) : null));
  }
  box.replaceChildren(...rows);
  box.hidden = !running.length && !recent.length;
}
async function poll() {
  try {
    const st = await api('state');
    renderJobs(st);
    const sig = st.jobs.map((j) => j.id + j.state).join();
    if (st.rev !== lastRev) {
      if (lastRev !== -1) await V.reload();
      lastRev = st.rev;
    }
    for (const j of st.jobs) {
      const key = j.id + j.state;
      if (j.state === 'error' && !lastJobState.includes(key) && lastJobState) toast(`${j.label} failed: ${j.message}`, 'err');
    }
    lastJobState = sig;
    setTimeout(poll, st.busy ? 1000 : 3000);
  } catch {
    $('jobs').hidden = false;
    $('jobs').replaceChildren(h('div', { class: 'job error' }, 'Lost contact with Plane Studio. Is its window still open?'));
    setTimeout(poll, 4000);
  }
}

// ---------- boot ----------
async function boot() {
  ping = await api('ping').catch(() => ({}));
  document.title = 'Plane Studio';
  document.body.classList.add('studio');
  document.querySelector('.brand h1').textContent = 'Plane Studio';
  document.querySelector('.filters').before(h('div', { class: 'studio-top' },
    h('button', { class: 'btn primary', onclick: () => newDesignDialog() }, '+ New design'),
    h('button', { class: 'btn', onclick: importDialog }, 'Import'),
    h('button', { class: 'btn', title: 'Re-run every check', onclick: async () => { await api('check-all', {}); toast('Checking every design…'); } }, 'Check all')));
  document.querySelector('#sidebar footer').before(h('div', { id: 'jobs', class: 'jobs', hidden: true, 'aria-live': 'polite' }));
  document.body.append(h('div', { id: 'toasts', class: 'toasts' }));
  V.onScorecard = actionBar;
  V.refresh();
  poll();
}
boot();
