// ui.js — the operator console's client logic (vanilla JS, no framework,
// no build step — matches smia's/mjolnir's UI convention, D46).
//
// Hash-based routing: #/notes, #/notes/:id, #/grammar, #/grammar/:id,
// #/new-note, #/new-grammar. One `<section class="page">` per route, shown/
// hidden via the `.active` class.

// Empty at the domain root (local dev); the mount prefix (e.g. "/stabbur")
// once reverse-proxied — set by app.py's ui_index() templating in
// index.html from the proxy's X-Forwarded-Prefix header. Every absolute
// API/blob request below goes through this so the same bundle works
// unmodified at either mount point.
const API_BASE = window.STABBUR_PREFIX || '';

const INFLECTION_SHAPES = {
  substantiv: ['article', 'sg_indef', 'sg_def', 'pl_indef', 'pl_def'],
  adjektiv: ['positiv', 'nøytrum', 'flertall', 'komparativ', 'superlativ'],
  verb: ['infinitiv', 'presens', 'preteritum', 'perfektum'],
  adverb: ['form'],
};

// Grammatically meaningful row grouping for the inflection fields —
// substantiv only (singular forms, then plural forms); every other PoS
// falls back to the default flat layout (inflection-rows-and-fill
// design.md D1 — no row-grouping was requested for adjektiv/verb/adverb,
// and an arbitrary N-per-row chunk there would carry no actual meaning).
const INFLECTION_ROW_GROUPS = {
  substantiv: [['article'], ['sg_indef', 'sg_def'], ['pl_indef', 'pl_def']],
};

const KNOWN_POS_VALUES = ['substantiv', 'adjektiv', 'verb', 'adverb', 'preposisjon', 'konjunksjon'];

// Only `word` notes carry a meaningful lemma/PoS; only `grammar` notes have
// no transcription (their E side is a Norwegian answer, not a sound clip).
const TYPE_VISIBLE_FIELDS = {
  word: { lemma: true, pos: true, transcription: true },
  expression: { lemma: false, pos: false, transcription: true },
  listening: { lemma: false, pos: false, transcription: true },
  pronunciation: { lemma: false, pos: false, transcription: true },
  grammar: { lemma: false, pos: false, transcription: false },
};

function setFieldVisible(fieldId, visible) {
  const field = document.getElementById(fieldId);
  if (!field) return;
  field.style.display = visible ? '' : 'none';
  const row = field.closest('.field-row');
  if (row) {
    const anyHidden = Array.from(row.children).some((c) => c.style.display === 'none');
    row.classList.toggle('single', anyHidden);
  }
}

function applyTypeFieldVisibility(prefix, type) {
  const vis = TYPE_VISIBLE_FIELDS[type] || { lemma: true, pos: true, transcription: true };
  setFieldVisible(`${prefix}_lemma_field`, vis.lemma);
  setFieldVisible(`${prefix}_pos_field`, vis.pos);
  setFieldVisible(`${prefix}_transcription_field`, vis.transcription);
}

// PoS select + "Custom…" text fallback, shared shape between the note
// editor (e_*) and the new-note form (c_*).
function setPosValue(selectId, customId, pos) {
  const select = document.getElementById(selectId);
  const custom = document.getElementById(customId);
  if (!pos) {
    select.value = '';
    custom.style.display = 'none';
    custom.value = '';
  } else if (KNOWN_POS_VALUES.includes(pos)) {
    select.value = pos;
    custom.style.display = 'none';
    custom.value = '';
  } else {
    select.value = '__custom__';
    custom.style.display = 'block';
    custom.value = pos;
  }
}

function getPosValue(selectId, customId) {
  const select = document.getElementById(selectId);
  if (select.value === '__custom__') return document.getElementById(customId).value || null;
  return select.value || null;
}

function wirePosCustomToggle(selectId, customId, onChange) {
  document.getElementById(selectId).addEventListener('change', () => {
    const select = document.getElementById(selectId);
    const custom = document.getElementById(customId);
    if (select.value === '__custom__') {
      custom.style.display = 'block';
      custom.focus();
    } else {
      custom.style.display = 'none';
      custom.value = '';
    }
    if (onChange) onChange();
  });
}

function authHeaders() {
  const token = document.getElementById('tokenInput').value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Remember the bearer token across page loads (same-origin localStorage —
// this is a single-operator internal tool, not a multi-user app, so there's
// no session-separation concern). The script runs at the end of <body>, so
// the DOM is already parsed by the time this executes.
const TOKEN_STORAGE_KEY = 'stabbur_token';
(function restoreToken() {
  const input = document.getElementById('tokenInput');
  const saved = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (saved) input.value = saved;
  input.addEventListener('input', () => {
    if (input.value) localStorage.setItem(TOKEN_STORAGE_KEY, input.value);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  });
})();

async function api(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...(options.headers || {}), ...authHeaders() },
  });
  const text = await resp.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  return { status: resp.status, body };
}

function qs(params) {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== '') usp.set(k, v);
  }
  const s = usp.toString();
  return s ? `?${s}` : '';
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function statusPill(status) {
  return `<span class="pill ${status === 'ready' ? 'pill-ok' : 'pill-warn'}">${status}</span>`;
}

function audioPill(audioBlob) {
  return audioBlob
    ? `<span class="pill pill-ok">✓ attached</span>`
    : `<span class="pill pill-err">— missing</span>`;
}

// design.md D9: origin is read-only in the editor (it's immutable once
// set, so offering it as a form input would be a lie). For origin=import,
// show the source name rather than the raw import_ref JSON.
function originLabel(note) {
  if (note.origin === 'import') {
    const source = note.import_ref && note.import_ref.source;
    return `imported from ${escapeHtml(source || '?')}`;
  }
  return escapeHtml(note.origin);
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// ------------------------------------------------- translation list field --

function addTranslationRow(containerId, lang, text, onChange) {
  const container = document.getElementById(containerId);
  const row = document.createElement('div');
  row.className = 'translation-row';
  row.innerHTML = `
    <input type="text" class="t-lang" placeholder="lang" value="${escapeHtml(lang || '')}">
    <input type="text" class="t-text" placeholder="translation">
    <button type="button" class="btn-ghost t-remove">✕</button>
  `;
  row.querySelector('.t-text').value = text || '';
  row.querySelector('.t-remove').addEventListener('click', () => { row.remove(); if (onChange) onChange(); });
  row.querySelectorAll('input').forEach((inp) => inp.addEventListener('input', () => { if (onChange) onChange(); }));
  container.appendChild(row);
}

function renderTranslationRows(containerId, translations, onChange) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  (translations || []).forEach((t) => addTranslationRow(containerId, t.lang, t.text, onChange));
}

function readTranslationRows(containerId) {
  return Array.from(document.querySelectorAll(`#${containerId} .translation-row`))
    .map((row) => ({ lang: row.querySelector('.t-lang').value, text: row.querySelector('.t-text').value }))
    .filter((t) => t.lang || t.text);
}

// -------------------------------------------------- inflection fields UI --

function inflectionFieldHtml(field, value) {
  return `
    <div class="inflection-field">
      <label>${escapeHtml(field.replace(/_/g, ' '))}</label>
      <input type="text" data-inflection-field="${field}" value="${escapeHtml(value || '')}">
    </div>
  `;
}

function renderInflectionFields(containerId, pos, values) {
  const container = document.getElementById(containerId);
  const shape = INFLECTION_SHAPES[pos];
  if (!shape) {
    container.innerHTML = '';
    return;
  }
  const groups = INFLECTION_ROW_GROUPS[pos];
  if (!groups) {
    container.innerHTML = shape.map((field) => inflectionFieldHtml(field, values && values[field])).join('');
    return;
  }
  container.innerHTML = groups
    .map((group) => `<div class="inflection-row">${group.map((field) => inflectionFieldHtml(field, values && values[field])).join('')}</div>`)
    .join('');
}

function readInflectionFields(containerId) {
  const out = {};
  document.querySelectorAll(`#${containerId} [data-inflection-field]`).forEach((input) => {
    out[input.dataset.inflectionField] = input.value;
  });
  return out;
}

// --------------------------------------------------- grammar rule select --

async function populateGrammarRuleSelect(selectEl, currentValue) {
  const { status, body } = await api('/api/grammar_rules?sort=title_asc');
  const options = ['<option value="">— none —</option>'];
  if (status === 200) {
    body.forEach((r) => options.push(`<option value="${r.id}">${escapeHtml(r.title)} (#${r.id})</option>`));
  }
  selectEl.innerHTML = options.join('');
  selectEl.value = currentValue != null ? String(currentValue) : '';
}

// ---------------------------------------------------------------- router --

const routes = {
  notes: renderNotesList,
  'notes-detail': renderNoteDetail,
  grammar: renderGrammarList,
  'grammar-detail': renderGrammarDetail,
  'new-note': renderNewNote,
  'new-grammar': renderNewGrammar,
  settings: renderSettings,
  triage: renderTriage,
};

function parseHash() {
  const hash = location.hash.replace(/^#\/?/, '');
  const parts = hash.split('/').filter(Boolean);
  if (parts.length === 0) return { route: 'notes', id: null };
  if (parts[0] === 'notes' && parts[1]) return { route: 'notes-detail', id: parts[1] };
  if (parts[0] === 'grammar' && parts[1]) return { route: 'grammar-detail', id: parts[1] };
  if (routes[parts[0]]) return { route: parts[0], id: null };
  return { route: 'notes', id: null };
}

function showPage(route) {
  document.querySelectorAll('.page').forEach((el) => el.classList.remove('active'));
  const pageId = {
    notes: 'page-notes',
    'notes-detail': 'page-note-detail',
    grammar: 'page-grammar',
    'grammar-detail': 'page-grammar-detail',
    'new-note': 'page-new-note',
    'new-grammar': 'page-new-grammar',
    settings: 'page-settings',
    triage: 'page-triage',
  }[route];
  document.getElementById(pageId).classList.add('active');

  const railRoute = route.startsWith('notes') ? 'notes' : route.startsWith('grammar') ? 'grammar' : route;
  document.querySelectorAll('.rail a').forEach((a) => {
    a.classList.toggle('active', a.dataset.route === railRoute);
  });
}

async function router() {
  const { route, id } = parseHash();
  showPage(route);
  await routes[route](id);
}

window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', router);

// ------------------------------------------------------------ notes list --

const notesListState = { status: '', type: '', origin: '', sortField: 'updated', sortDir: 'desc' };

function wireChipGroup(containerId, onChange) {
  const group = document.getElementById(containerId);
  group.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      group.querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      onChange(chip.dataset.value);
    });
  });
}

wireChipGroup('notesStatusChips', (value) => { notesListState.status = value; renderNotesList(); });
wireChipGroup('notesTypeChips', (value) => { notesListState.type = value; renderNotesList(); });
wireChipGroup('notesOriginChips', (value) => { notesListState.origin = value; renderNotesList(); });

function wireSortableHeaders(theadSelector, state, defaultDirs, onChange) {
  document.querySelectorAll(`${theadSelector} .sort-th`).forEach((th) => {
    th.addEventListener('click', () => {
      const field = th.dataset.sort;
      if (state.sortField === field) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortField = field;
        state.sortDir = defaultDirs[field] || 'asc';
      }
      document.querySelectorAll(`${theadSelector} .sort-th`).forEach((el) => {
        const active = el.dataset.sort === state.sortField;
        el.classList.toggle('sort-active', active);
        el.querySelector('.sort-caret').textContent = active ? (state.sortDir === 'asc' ? '▲' : '▼') : '';
      });
      onChange();
    });
  });
}

wireSortableHeaders('#page-notes thead', notesListState, { text: 'asc', updated: 'desc' }, renderNotesList);
document.querySelector('#page-notes thead .sort-th[data-sort="updated"]').classList.add('sort-active');
document.querySelector('#page-notes thead .sort-th[data-sort="updated"] .sort-caret').textContent = '▼';

async function renderNotesList() {
  const status = notesListState.status;
  const type = notesListState.type;
  const origin = notesListState.origin;
  const sort = `${notesListState.sortField}_${notesListState.sortDir}`;
  const q = document.getElementById('notesSearch').value.trim();

  const { status: httpStatus, body } = await api(`/api/notes/authoring${qs({ status, type, origin, sort, q })}`);
  const tbody = document.getElementById('notesTableBody');
  if (httpStatus !== 200) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">${escapeHtml(JSON.stringify(body))}</td></tr>`;
    return;
  }

  const total = body.length;
  const readyCount = body.filter((n) => n.status === 'ready').length;
  const draftCount = total - readyCount;
  const missingAudio = body.filter((n) => !n.audio_blob).length;
  document.getElementById('notesSummary').textContent =
    `${total} total · ${readyCount} ready · ${draftCount} draft · ${missingAudio} missing audio`;

  if (total === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">No notes match these filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = body.map((n) => `
    <tr data-id="${n.id}">
      <td><strong>${escapeHtml(n.text)}</strong></td>
      <td>${escapeHtml(n.type)}</td>
      <td>${escapeHtml(n.pos || '—')}</td>
      <td>${statusPill(n.status)}</td>
      <td>${audioPill(n.audio_blob)}</td>
      <td class="wrap">${escapeHtml((n.translations && n.translations[0] && n.translations[0].text) || '—')}</td>
      <td class="mono">${fmtDate(n.updated_at)}</td>
    </tr>
  `).join('');

  tbody.querySelectorAll('tr[data-id]').forEach((row) => {
    row.addEventListener('click', () => { location.hash = `#/notes/${row.dataset.id}`; });
  });
}

let notesSearchDebounce;
document.getElementById('notesSearch').addEventListener('input', () => {
  clearTimeout(notesSearchDebounce);
  notesSearchDebounce = setTimeout(renderNotesList, 250);
});

// ----------------------------------------------------------- note detail --

const EDIT_FIELD_IDS = [
  'type', 'source_lang', 'text', 'transcription', 'pos', 'lemma',
  'context_text', 'grammar_rule_id', 'status',
];

let currentNote = null;
let waveformState = null; // { durationMs, selStart, selEnd, dragging }

async function renderNoteDetail(id) {
  const { status, body: note } = await api(`/api/notes/${id}`);
  if (status !== 200) {
    document.getElementById('noteDetailTitle').textContent = 'Not found';
    document.getElementById('noteDetailSub').textContent = '';
    return;
  }
  currentNote = note;

  document.getElementById('noteDetailTitle').textContent = note.text;
  document.getElementById('noteDetailSub').innerHTML =
    `${escapeHtml(note.type)} · ${escapeHtml(note.pos || '—')} · ${statusPill(note.status)} · ` +
    `${originLabel(note)} · ` +
    `created ${fmtDate(note.created_at)} · updated ${fmtDate(note.updated_at)}`;

  document.getElementById('e_text').value = note.text || '';
  document.getElementById('e_lemma').value = note.lemma || '';
  document.getElementById('e_type').value = note.type;
  setPosValue('e_pos_select', 'e_pos_custom', note.pos);
  document.getElementById('e_source_lang').value = note.source_lang || '';
  document.getElementById('e_status').value = note.status;
  document.getElementById('e_transcription').value = note.transcription || '';
  renderTranslationRows('e_translations_list', note.translations, updateNoteJsonView);
  document.getElementById('e_context_text').value = note.context_text || '';
  await populateGrammarRuleSelect(document.getElementById('e_grammar_rule_id'), note.grammar_rule_id);
  document.getElementById('noteSaveResult').textContent = '';

  updateEditInflectionFields(note.pos, note.inflections);
  updateEditFieldVisibility();
  resetSuggestQueries('e');
  updateNoAudioWarning();
  updateNoteJsonView();
  renderAudioSection(note);
}

function currentInflectionShapeField() {
  const pos = getPosValue('e_pos_select', 'e_pos_custom');
  return INFLECTION_SHAPES[pos] ? pos : null;
}

function updateEditInflectionFields(pos, values) {
  const shapedPos = INFLECTION_SHAPES[pos] ? pos : null;
  document.getElementById('e_inflections_field').style.display = shapedPos ? 'block' : 'none';
  if (shapedPos) renderInflectionFields('e_inflections_fields', shapedPos, values);
  else document.getElementById('e_inflections_fields').innerHTML = '';
}

function updateEditFieldVisibility() {
  const type = document.getElementById('e_type').value;
  document.getElementById('e_grammar_rule_field').style.display = type === 'grammar' ? 'block' : 'none';
  applyTypeFieldVisibility('e', type);
}

document.getElementById('e_type').addEventListener('change', updateEditFieldVisibility);
wirePosCustomToggle('e_pos_select', 'e_pos_custom', () => {
  const pos = getPosValue('e_pos_select', 'e_pos_custom');
  // Carry forward whatever's currently typed into the inflection fields
  // (e.g. the operator just corrected the PoS spelling) rather than
  // resetting them — renderInflectionFields only picks out the keys the
  // new shape actually has, so stale keys from a different shape are
  // harmlessly dropped.
  const typedValues = readInflectionFields('e_inflections_fields');
  const hasTypedValues = Object.values(typedValues).some((v) => v);
  const values = hasTypedValues
    ? typedValues
    : (currentNote && currentNote.pos === pos ? currentNote.inflections : null);
  updateEditInflectionFields(pos, values);
  updateNoteJsonView();
});
document.getElementById('e_add_translation').addEventListener('click', () => {
  addTranslationRow('e_translations_list', '', '', updateNoteJsonView);
});

function readEditForm() {
  const shapedPos = currentInflectionShapeField();
  const inflections = shapedPos
    ? readInflectionFields('e_inflections_fields')
    : (currentNote?.inflections ?? {});

  return {
    text: document.getElementById('e_text').value,
    lemma: document.getElementById('e_lemma').value || null,
    type: document.getElementById('e_type').value,
    pos: getPosValue('e_pos_select', 'e_pos_custom'),
    source_lang: document.getElementById('e_source_lang').value,
    status: document.getElementById('e_status').value,
    transcription: document.getElementById('e_transcription').value || null,
    translations: readTranslationRows('e_translations_list'),
    inflections,
    context_text: document.getElementById('e_context_text').value || null,
    grammar_rule_id: document.getElementById('e_grammar_rule_id').value
      ? Number(document.getElementById('e_grammar_rule_id').value)
      : null,
  };
}

function updateNoteJsonView() {
  if (!currentNote) return;
  const merged = { ...currentNote, ...readEditForm() };
  document.getElementById('noteJsonView').textContent = JSON.stringify(merged, null, 2);
}

function updateNoAudioWarning() {
  if (!currentNote) return;
  const status = document.getElementById('e_status').value;
  const hasAudio = !!currentNote.audio_blob;
  document.getElementById('e_no_audio_warning').style.display =
    (status === 'ready' && !hasAudio) ? 'block' : 'none';
}

document.getElementById('noteEditForm').addEventListener('input', () => {
  updateNoteJsonView();
  updateNoAudioWarning();
  syncSuggestQueries('e');
});

document.getElementById('noteSaveBtn').addEventListener('click', async () => {
  if (!currentNote) return;
  const payload = readEditForm();
  const { status, body } = await api(`/api/notes/${currentNote.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = document.getElementById('noteSaveResult');
  if (status === 200) {
    currentNote = body;
    result.textContent = 'Saved.';
    document.getElementById('noteDetailSub').innerHTML =
      `${escapeHtml(body.type)} · ${escapeHtml(body.pos || '—')} · ${statusPill(body.status)} · ` +
      `${originLabel(body)} · ` +
      `created ${fmtDate(body.created_at)} · updated ${fmtDate(body.updated_at)}`;
    updateNoteJsonView();
    updateNoAudioWarning();
  } else {
    result.textContent = `Error: ${JSON.stringify(body)}`;
  }
});

document.getElementById('noteDeleteBtn').addEventListener('click', async () => {
  if (!currentNote) return;
  const willTombstone = currentNote.status === 'ready';
  const msg = willTombstone
    ? 'This note is ready, so it may already have been pulled by Mjølnir. Deleting it tombstones the id (not a hard delete) — continue?'
    : 'This draft note has never been eligible for pull — deleting it removes the row entirely (hard delete). Continue?';
  if (!confirm(msg)) return;

  const { status } = await api(`/api/notes/${currentNote.id}`, { method: 'DELETE' });
  if (status === 204 || status === 200) {
    location.hash = '#/notes';
  } else {
    document.getElementById('noteSaveResult').textContent = 'Delete failed.';
  }
});

document.getElementById('uploadAudioBtn').addEventListener('click', async () => {
  if (!currentNote) return;
  const fileInput = document.getElementById('e_audio_file');
  if (!fileInput.files[0]) return;

  const form = new FormData();
  form.append('audio', fileInput.files[0]);
  const uploadResp = await fetch(`${API_BASE}/blobs`, { method: 'POST', headers: authHeaders(), body: form });
  const uploadBody = await uploadResp.json();
  if (uploadResp.status !== 200) {
    document.getElementById('noteSaveResult').textContent = `Upload failed: ${JSON.stringify(uploadBody)}`;
    return;
  }

  const { status, body } = await api(`/api/notes/${currentNote.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_blob: uploadBody.sha256, audio_sel_ms: null }),
  });
  if (status === 200) {
    currentNote = body;
    fileInput.value = '';
    document.getElementById('noteSaveResult').textContent = 'Audio replaced.';
    updateNoAudioWarning();
    updateNoteJsonView();
    renderAudioSection(currentNote);
  } else {
    document.getElementById('noteSaveResult').textContent = `Attach failed: ${JSON.stringify(body)}`;
  }
});

// --------------------------------------------------------- audio + trim --

async function renderAudioSection(note) {
  const none = document.getElementById('noteAudioNone');
  const player = document.getElementById('noteAudioPlayer');
  // "Propose from audio" only makes sense once a note actually has audio to
  // transcribe — stt-text-suggest change.
  document.getElementById('e_stt_toggle').style.display = note.audio_blob ? 'inline-block' : 'none';
  if (!note.audio_blob) {
    none.style.display = 'block';
    player.style.display = 'none';
    waveformState = null;
    closeSuggestPanel(document.getElementById('e_stt_suggest'));
    return;
  }
  none.style.display = 'none';
  player.style.display = 'block';

  const audioEl = document.getElementById('audioElement');
  audioEl.src = `${API_BASE}/blob/${note.audio_blob}`;

  let durationMs = 0;
  try {
    const resp = await fetch(audioEl.src);
    const buf = await resp.arrayBuffer();
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtx();
    const decoded = await ctx.decodeAudioData(buf);
    durationMs = decoded.duration * 1000;
    drawWaveform(decoded);
    ctx.close && ctx.close();
  } catch (e) {
    // Decoding can fail on malformed/test fixtures — fall back to the
    // <audio> element's own metadata once it loads, trim still works.
    await new Promise((resolve) => {
      audioEl.addEventListener('loadedmetadata', resolve, { once: true });
      audioEl.load();
    });
    durationMs = (audioEl.duration || 0) * 1000;
  }

  const sel = note.audio_sel_ms && note.audio_sel_ms.length === 2 ? note.audio_sel_ms : [0, durationMs];
  waveformState = { durationMs, selStart: sel[0], selEnd: sel[1], dragging: null };
  updateTrimHandles();
}

function drawWaveform(audioBuffer) {
  const canvas = document.getElementById('audioWaveformCanvas');
  const ctx2d = canvas.getContext('2d');
  const width = canvas.width, height = canvas.height;
  ctx2d.clearRect(0, 0, width, height);
  const data = audioBuffer.getChannelData(0);
  const step = Math.ceil(data.length / width);
  ctx2d.strokeStyle = getComputedStyle(canvas).color;
  ctx2d.lineWidth = 1.4;
  ctx2d.globalAlpha = 0.6;
  ctx2d.beginPath();
  for (let i = 0; i < width; i++) {
    let max = 0;
    for (let j = 0; j < step; j++) {
      const v = Math.abs(data[i * step + j] || 0);
      if (v > max) max = v;
    }
    const y = height / 2 - max * (height / 2 - 2);
    const y2 = height / 2 + max * (height / 2 - 2);
    ctx2d.moveTo(i, y);
    ctx2d.lineTo(i, y2);
  }
  ctx2d.stroke();
}

function updateTrimHandles() {
  if (!waveformState) return;
  const { durationMs, selStart, selEnd } = waveformState;
  const startPct = durationMs ? (selStart / durationMs) * 100 : 0;
  const endPct = durationMs ? (selEnd / durationMs) * 100 : 100;
  document.getElementById('trimHandleStart').style.left = `${startPct}%`;
  document.getElementById('trimHandleEnd').style.left = `${endPct}%`;
  document.getElementById('trimShadeLeft').style.width = `${startPct}%`;
  document.getElementById('trimShadeRight').style.width = `${100 - endPct}%`;
  const fmt = (ms) => {
    const totalSec = Math.round(ms / 1000);
    return `${Math.floor(totalSec / 60)}:${String(totalSec % 60).padStart(2, '0')}`;
  };
  document.getElementById('audioTimeLabel').textContent = `${fmt(selStart)} – ${fmt(selEnd)}`;
}

function wireTrimHandle(handleEl, which) {
  handleEl.addEventListener('pointerdown', (e) => {
    if (!waveformState) return;
    waveformState.dragging = which;
    handleEl.setPointerCapture(e.pointerId);
  });
  handleEl.addEventListener('pointermove', (e) => {
    if (!waveformState || waveformState.dragging !== which) return;
    const rect = document.getElementById('audioWaveform').getBoundingClientRect();
    const pct = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    const ms = Math.round(pct * waveformState.durationMs);
    if (which === 'start') waveformState.selStart = Math.min(ms, waveformState.selEnd);
    else waveformState.selEnd = Math.max(ms, waveformState.selStart);
    updateTrimHandles();
  });
  handleEl.addEventListener('pointerup', async () => {
    if (!waveformState || waveformState.dragging !== which) return;
    waveformState.dragging = null;
    if (!currentNote) return;
    const sel = [waveformState.selStart, waveformState.selEnd];
    const { status, body } = await api(`/api/notes/${currentNote.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audio_sel_ms: sel }),
    });
    if (status === 200) {
      currentNote = body;
      updateNoteJsonView();
    }
  });
}
wireTrimHandle(document.getElementById('trimHandleStart'), 'start');
wireTrimHandle(document.getElementById('trimHandleEnd'), 'end');

document.getElementById('audioPlayBtn').addEventListener('click', () => {
  const audioEl = document.getElementById('audioElement');
  if (audioEl.paused) audioEl.play(); else audioEl.pause();
});

document.getElementById('previewTrimBtn').addEventListener('click', () => {
  if (!waveformState) return;
  const audioEl = document.getElementById('audioElement');
  const startSec = waveformState.selStart / 1000;
  const endSec = waveformState.selEnd / 1000;
  audioEl.currentTime = startSec;
  audioEl.play();
  const onTimeUpdate = () => {
    if (audioEl.currentTime >= endSec) {
      audioEl.pause();
      audioEl.removeEventListener('timeupdate', onTimeUpdate);
    }
  };
  audioEl.addEventListener('timeupdate', onTimeUpdate);
});

// --------------------------------------------------------- grammar list --

const grammarListState = { sortField: 'usage', sortDir: 'desc' };

wireSortableHeaders('#page-grammar thead', grammarListState, { title: 'asc', usage: 'desc' }, renderGrammarList);
document.querySelector('#page-grammar thead .sort-th[data-sort="usage"]').classList.add('sort-active');
document.querySelector('#page-grammar thead .sort-th[data-sort="usage"] .sort-caret').textContent = '▼';

async function renderGrammarList() {
  const sort = `${grammarListState.sortField}_${grammarListState.sortDir}`;
  const q = document.getElementById('grammarSearch').value.trim();
  const { status, body } = await api(`/api/grammar_rules${qs({ sort, q })}`);
  const tbody = document.getElementById('grammarTableBody');
  if (status !== 200) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="2">${escapeHtml(JSON.stringify(body))}</td></tr>`;
    return;
  }

  const totalUsed = body.filter((r) => r.usage_count > 0).length;
  document.getElementById('grammarSummary').textContent =
    `${body.length} rules · ${totalUsed} used by at least one note`;

  if (body.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="2">No grammar rules yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = body.map((r) => `
    <tr data-id="${r.id}">
      <td><strong>${escapeHtml(r.title)}</strong></td>
      <td class="num">${r.usage_count} note${r.usage_count === 1 ? '' : 's'}</td>
    </tr>
  `).join('');
  tbody.querySelectorAll('tr[data-id]').forEach((row) => {
    row.addEventListener('click', () => { location.hash = `#/grammar/${row.dataset.id}`; });
  });
}

let grammarSearchDebounce;
document.getElementById('grammarSearch').addEventListener('input', () => {
  clearTimeout(grammarSearchDebounce);
  grammarSearchDebounce = setTimeout(renderGrammarList, 250);
});

// ------------------------------------------------------- grammar detail --

let currentRule = null;

async function renderGrammarDetail(id) {
  const { status, body: rule } = await api(`/api/grammar_rules/${id}`);
  if (status !== 200) {
    document.getElementById('grammarDetailTitle').textContent = 'Not found';
    return;
  }
  currentRule = rule;
  document.getElementById('grammarDetailTitle').textContent = rule.title;
  document.getElementById('gr_title').value = rule.title;
  document.getElementById('gr_html').value = rule.html;
  document.getElementById('gr_html_preview').innerHTML = rule.html;
  document.getElementById('grammarSaveResult').textContent = '';
  document.getElementById('grammarDeleteBlocked').textContent = '';
  document.getElementById('grammarUsageHeading').textContent = `Used by ${rule.usage_count} note${rule.usage_count === 1 ? '' : 's'}`;

  const deleteBtn = document.getElementById('grammarDeleteBtn');
  deleteBtn.disabled = rule.usage_count > 0;
  document.getElementById('grammarDeleteBlocked').textContent = rule.usage_count > 0
    ? `Delete blocked: ${rule.usage_count} note(s) still reference this rule.`
    : '';

  const { status: notesStatus, body: notes } = await api(`/api/notes/authoring${qs({ grammar_rule_id: id })}`);
  const list = document.getElementById('grammarUsageList');
  if (notesStatus === 200 && notes.length) {
    list.innerHTML = notes.map((n) => `
      <a class="usage-item" href="#/notes/${n.id}"><span>${escapeHtml(n.text)}</span>${statusPill(n.status)}</a>
    `).join('');
  } else {
    list.innerHTML = '<div class="inline-note">No notes reference this rule yet.</div>';
  }
}

document.getElementById('gr_html').addEventListener('input', (e) => {
  document.getElementById('gr_html_preview').innerHTML = e.target.value;
});

document.getElementById('grammarSaveBtn').addEventListener('click', async () => {
  if (!currentRule) return;
  const payload = {
    title: document.getElementById('gr_title').value,
    html: document.getElementById('gr_html').value,
  };
  const { status, body } = await api(`/api/grammar_rules/${currentRule.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = document.getElementById('grammarSaveResult');
  if (status === 200) {
    currentRule = body;
    document.getElementById('grammarDetailTitle').textContent = body.title;
    result.textContent = 'Saved.';
  } else {
    result.textContent = `Error: ${JSON.stringify(body)}`;
  }
});

document.getElementById('grammarDeleteBtn').addEventListener('click', async () => {
  if (!currentRule) return;
  if (!confirm(`Delete grammar rule "${currentRule.title}"?`)) return;
  const { status, body } = await api(`/api/grammar_rules/${currentRule.id}`, { method: 'DELETE' });
  if (status === 204) {
    location.hash = '#/grammar';
  } else if (status === 409) {
    document.getElementById('grammarDeleteBlocked').textContent =
      `Blocked: ${body.reference_count} note(s) still reference this rule.`;
  } else {
    document.getElementById('grammarDeleteBlocked').textContent = `Error: ${JSON.stringify(body)}`;
  }
});

// ------------------------------------------------------------- new note --

// Holds a TTS suggestion's stabbur sha256 until the note is created — a
// brand-new note has no id yet to PATCH against (unlike the existing-note
// editor's TTS "Use", which attaches immediately). Cleared whenever the
// dropzone file input is used instead, and vice versa (last action wins —
// new-note-audio-suggest design.md D2).
let newNoteAudioFromSuggest = null;

function setNewNoteAudioFromSuggest(sha256, providerName, meta) {
  newNoteAudioFromSuggest = { sha256, providerName };
  document.getElementById('c_audio_file').value = '';
  const chosen = document.getElementById('c_audio_suggest_chosen');
  chosen.style.cssText = 'display:flex; align-items:center; gap:8px;';
  chosen.innerHTML = '';
  chosen.appendChild(enrichEl(`<span>Will attach on save: ${escapeHtml(providerName)}${meta ? ` (${escapeHtml(meta)})` : ''}</span>`));
  // `sha256` here is already a real stabbur blob (tts/use or the manual
  // upload button both store it before returning), so the normal public
  // /blob/ route plays it directly — no need for the smia-side preview
  // route this change also adds for not-yet-stored candidates.
  chosen.appendChild(buildAudioPreviewButton(`${API_BASE}/blob/${sha256}`));
}

function clearNewNoteAudioFromSuggest() {
  newNoteAudioFromSuggest = null;
  const chosen = document.getElementById('c_audio_suggest_chosen');
  chosen.style.display = 'none';
  chosen.innerHTML = '';
}

document.getElementById('c_audio_file').addEventListener('change', (e) => {
  if (e.target.files[0]) clearNewNoteAudioFromSuggest();
});

// Mirrors the existing-note sidebar's "Manual upload" card (uploadAudioBtn):
// uploads eagerly on click rather than waiting for the whole note to be
// saved, so the operator gets the same immediate preview as every other
// provider's "Use" button, instead of only finding out what they picked
// after creating the note.
document.getElementById('c_upload_audio_btn').addEventListener('click', async () => {
  const fileInput = document.getElementById('c_audio_file');
  const file = fileInput.files[0];
  if (!file) return;
  const btn = document.getElementById('c_upload_audio_btn');
  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = '…';
  const form = new FormData();
  form.append('audio', file);
  const uploadResp = await fetch(`${API_BASE}/blobs`, { method: 'POST', headers: authHeaders(), body: form });
  const uploadBody = await uploadResp.json();
  btn.disabled = false;
  btn.textContent = originalLabel;
  if (uploadResp.status !== 200) {
    enrichToast('Upload failed');
    return;
  }
  setNewNoteAudioFromSuggest(uploadBody.sha256, 'manual upload', file.name);
});

function updateNewNoteFieldVisibility() {
  const type = document.getElementById('c_type').value;
  applyTypeFieldVisibility('c', type);
  document.getElementById('c_grammar_rule_field').style.display = type === 'grammar' ? 'block' : 'none';
  if (type !== 'word') {
    setPosValue('c_pos', 'c_pos_custom', '');
    document.getElementById('c_inflections_field').style.display = 'none';
    document.getElementById('c_inflections_fields').innerHTML = '';
  }
}

function updateNewNoteInflectionFields() {
  const pos = getPosValue('c_pos', 'c_pos_custom');
  const shaped = !!INFLECTION_SHAPES[pos];
  document.getElementById('c_inflections_field').style.display = shaped ? 'block' : 'none';
  renderInflectionFields('c_inflections_fields', pos);
}

wirePosCustomToggle('c_pos', 'c_pos_custom', updateNewNoteInflectionFields);

// Clears every c_-prefixed field, the translations list, the inflection
// fields, and the suggest controls' queries/dirty flags — so a note never
// outlives its own form (editor-session-hygiene). Run on a successful
// create and on every entry to the new-note route.
function resetCreateForm() {
  document.getElementById('createForm').reset();
  document.getElementById('c_source_lang').value = 'no';
  document.getElementById('createResult').textContent = '';
  clearNewNoteAudioFromSuggest();
  renderTranslationRows('c_translations_list', [], null);
  updateNewNoteFieldVisibility();
  updateNewNoteInflectionFields();
  resetSuggestQueries('c');
}

async function renderNewNote() {
  resetCreateForm();
  await populateGrammarRuleSelect(document.getElementById('c_grammar_rule_id'), null);
}

document.getElementById('c_type').addEventListener('change', updateNewNoteFieldVisibility);
document.getElementById('c_add_translation').addEventListener('click', () => {
  addTranslationRow('c_translations_list', '', '', null);
});

async function submitNewNote(status) {
  const translations = readTranslationRows('c_translations_list');
  const inflections = readInflectionFields('c_inflections_fields');

  const payload = {
    type: document.getElementById('c_type').value,
    source_lang: document.getElementById('c_source_lang').value,
    text: document.getElementById('c_text').value,
    status,
    pos: getPosValue('c_pos', 'c_pos_custom'),
    lemma: document.getElementById('c_lemma').value || null,
    transcription: document.getElementById('c_transcription').value || null,
    translations,
    inflections,
    context_text: document.getElementById('c_context_text').value || null,
    grammar_rule_id: document.getElementById('c_grammar_rule_id').value
      ? Number(document.getElementById('c_grammar_rule_id').value)
      : null,
    // A TTS suggestion already has its stabbur sha256 before the note
    // exists, so it goes straight into the create payload — no
    // create-then-PATCH round trip needed for this path (design.md D1).
    // A dropzone file, by contrast, needs the created note's id to call the
    // multipart /blobs upload, so it stays a separate step below.
    audio_blob: newNoteAudioFromSuggest ? newNoteAudioFromSuggest.sha256 : null,
  };

  const { status: httpStatus, body } = await api('/api/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (httpStatus !== 201) {
    document.getElementById('createResult').textContent = `Error: ${JSON.stringify(body)}`;
    return;
  }

  const fileInput = document.getElementById('c_audio_file');
  if (fileInput.files[0]) {
    const form = new FormData();
    form.append('audio', fileInput.files[0]);
    const uploadResp = await fetch(`${API_BASE}/blobs`, { method: 'POST', headers: authHeaders(), body: form });
    const uploadBody = await uploadResp.json();
    if (uploadResp.status === 200) {
      await api(`/api/notes/${body.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_blob: uploadBody.sha256 }),
      });
    }
  }

  resetCreateForm();
  location.hash = `#/notes/${body.id}`;
}

document.getElementById('createForm').addEventListener('input', () => {
  syncSuggestQueries('c');
});

document.getElementById('createForm').addEventListener('submit', (e) => {
  e.preventDefault();
  submitNewNote('draft');
});
document.getElementById('createReadyBtn').addEventListener('click', () => submitNewNote('ready'));

// --------------------------------------------------------- new grammar --

function renderNewGrammar() {
  document.getElementById('ruleForm').reset();
  document.getElementById('ruleResult').textContent = '';
  document.getElementById('r_html_preview').innerHTML = '';
}

document.getElementById('r_html').addEventListener('input', (e) => {
  document.getElementById('r_html_preview').innerHTML = e.target.value;
});

document.getElementById('ruleForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    title: document.getElementById('r_title').value,
    html: document.getElementById('r_html').value,
  };
  const { status, body } = await api('/api/grammar_rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (status === 201) {
    location.hash = `#/grammar/${body.id}`;
  } else {
    document.getElementById('ruleResult').textContent = `Error: ${JSON.stringify(body)}`;
  }
});

// ----------------------------------------------- smia enrichment panels --
// Per-field "Suggest" accordions (smia-enrichment-panel change). Works
// identically on the new-note form (c_*) and the note-detail form (e_*) —
// every lookup reads only the form's current field values, never the note's
// saved state, so it needs no note id. Manual-trigger only: nothing here
// ever fires from an `input` listener, only from an explicit click.

const ENRICH_LANG_NAMES = {
  en: 'English', de: 'German', fr: 'French', es: 'Spanish',
  nl: 'Dutch', sv: 'Swedish', pl: 'Polish', it: 'Italian',
};
function enrichLangLabel(code) { return ENRICH_LANG_NAMES[code] || code.toUpperCase(); }

// operator-settings's own fallback defaults (settings_store.py's), used
// only if a settings fetch fails outright — the editor must still be fully
// usable before the settings page has ever been opened (design D2).
const SUGGEST_DEFAULT_LANGS = ['en', 'de'];

let _settingsCache = null;
async function fetchSettings() {
  if (_settingsCache) return _settingsCache;
  const { status, body } = await api('/api/settings');
  if (status === 200) _settingsCache = body;
  return status === 200 ? body : {
    translation_merge_mode: 'append',
    override_prefill: true,
    default_target_langs: SUGGEST_DEFAULT_LANGS,
    providers: {},
  };
}

let _enrichProvidersCache = null;
async function fetchEnrichProviders() {
  if (_enrichProvidersCache) return _enrichProvidersCache;
  const { status, body } = await api('/api/enrich/providers');
  // Only a successful fetch is cached — a transient smia outage must not
  // permanently disable suggestions for the rest of the page's lifetime;
  // the next panel open retries instead of reusing a stale empty catalog.
  if (status === 200) _enrichProvidersCache = body;
  return status === 200 ? body : {};
}

// ── combined suggest controls: live query sync + Enter-to-fire + counts ──

function querySuggestControls(prefix) {
  return Array.from(document.querySelectorAll('.suggest-control')).filter((control) => {
    const btn = control.querySelector('[data-suggest-toggle]');
    const panel = btn && document.getElementById(btn.dataset.suggestToggle);
    return panel && panel.dataset.prefix === prefix;
  });
}

function suggestControlPanel(control) {
  const btn = control.querySelector('[data-suggest-toggle]');
  return btn && document.getElementById(btn.dataset.suggestToggle);
}

function panelsForPrefix(prefix) {
  return Array.from(document.querySelectorAll('.suggest-panel')).filter((p) => p.dataset.prefix === prefix);
}

// Syncs every suggest-control's query field to its own kind's source field
// (design D1: inflections reads lemma, everything else reads text — no
// shared default), skipping any control the operator has directly edited
// (`dirty`) so an unrelated field edit never clobbers a deliberate override.
function syncSuggestQueries(prefix) {
  querySuggestControls(prefix).forEach((control) => {
    const input = control.querySelector('.suggest-query');
    if (!input || input.dataset.dirty === '1') return;
    const panel = suggestControlPanel(control);
    input.value = defaultSuggestQuery(prefix, panel ? panel.dataset.kind : null);
  });
}

// Called when a note is (re)loaded into a form — clears any prior dirty
// state so the new note starts with every query and the lemma sync back in
// sync, and collapses+empties every panel so no panel outlives the note it
// was opened for (design D4).
function resetSuggestQueries(prefix) {
  querySuggestControls(prefix).forEach((control) => {
    const input = control.querySelector('.suggest-query');
    if (input) delete input.dataset.dirty;
  });
  const lemmaEl = document.getElementById(`${prefix}_lemma`);
  if (lemmaEl) delete lemmaEl.dataset.dirty;
  syncSuggestQueries(prefix);
  panelsForPrefix(prefix).forEach((panel) => {
    closeSuggestPanel(panel);
    panel.innerHTML = '';
  });
}

async function updateSuggestCounts() {
  const catalog = await fetchEnrichProviders();
  document.querySelectorAll('.suggest-control').forEach((control) => {
    const btn = control.querySelector('[data-suggest-toggle]');
    const panel = btn && document.getElementById(btn.dataset.suggestToggle);
    const countEl = control.querySelector('.count');
    if (!panel || !countEl) return;
    const count = (catalog[panel.dataset.kind] || []).length;
    countEl.textContent = String(count);
    countEl.style.display = count > 0 ? '' : 'none';
  });
}

document.querySelectorAll('.suggest-control').forEach((control) => {
  const btn = control.querySelector('[data-suggest-toggle]');
  const input = control.querySelector('.suggest-query');
  if (!btn || !input) return;
  input.addEventListener('input', () => { input.dataset.dirty = '1'; });
  // Enter fires the panel whether it's closed (opens it) or already open
  // (re-fires every provider with the edited value) — no fire-on-keystroke,
  // matching every other suggest input's manual-trigger convention. A
  // different query is a different cache key and will miss anyway, so this
  // does not force a cache bypass (design D5) — only the explicit ⟳ does.
  input.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const panel = document.getElementById(btn.dataset.suggestToggle);
    if (panel) openSuggestPanel(panel);
  });
});
updateSuggestCounts();

// Raising/lowering the requested count is a genuinely new lookup, not a
// forced re-fetch of the same one — `limit` is part of smia's cache
// identity (design D4) — so this rebuilds the panel the same way any other
// query change would, only if the panel is already open.
document.querySelectorAll('.examples-count-input').forEach((input) => {
  input.addEventListener('change', () => {
    const prefix = input.id.split('_')[0];
    const panel = document.getElementById(`${prefix}_examples_suggest`);
    if (panel && panel.classList.contains('open')) openSuggestPanel(panel);
  });
});

// Panel-level "re-run every provider" control — re-opens/re-fires the panel
// in place (it already stays marked `.open` throughout) with a forced cache
// bypass, making the existing Enter-to-fire behaviour discoverable
// (design D5).
document.querySelectorAll('[data-suggest-rerun]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const panel = document.getElementById(btn.dataset.suggestRerun);
    if (!panel) return;
    btn.classList.add('spinning');
    setTimeout(() => btn.classList.remove('spinning'), 650);
    openSuggestPanel(panel, { forceRefresh: true });
  });
});

// ── reactive lemma: follows `text`'s first token until edited directly ──

function syncLemmaFromText(prefix) {
  const lemmaEl = document.getElementById(`${prefix}_lemma`);
  if (!lemmaEl || lemmaEl.dataset.dirty === '1') return;
  const textEl = document.getElementById(`${prefix}_text`);
  lemmaEl.value = textEl ? (textEl.value.trim().split(/\s+/)[0] || '') : '';
}

function wireLemmaTextSync(prefix) {
  const lemmaEl = document.getElementById(`${prefix}_lemma`);
  const textEl = document.getElementById(`${prefix}_text`);
  if (!lemmaEl || !textEl) return;
  // A direct edit to lemma stops the sync for this note — same dirty-flag
  // idiom the suggest-control queries already use.
  lemmaEl.addEventListener('input', () => { lemmaEl.dataset.dirty = '1'; });
  textEl.addEventListener('input', () => syncLemmaFromText(prefix));
}
wireLemmaTextSync('e');
wireLemmaTextSync('c');

function enrichEl(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

// A small ▶/⏸ icon button standing in for a full native <audio controls>
// bar, which doesn't fit next to a candidate's text/meta/Use button in a
// narrow row or sidebar. Only one plays at a time — starting one pauses any
// other preview already playing.
function buildAudioPreviewButton(url) {
  const wrap = enrichEl(`
    <span class="audio-preview">
      <button type="button" class="icon-btn preview-play-btn" title="Preview">▶</button>
      <audio class="preview-audio" preload="none" src="${escapeHtml(url)}"></audio>
    </span>
  `);
  const btn = wrap.querySelector('.preview-play-btn');
  const audio = wrap.querySelector('.preview-audio');
  btn.addEventListener('click', () => {
    if (audio.paused) {
      document.querySelectorAll('audio.preview-audio').forEach((a) => { if (a !== audio) a.pause(); });
      audio.play();
    } else {
      audio.pause();
    }
  });
  audio.addEventListener('play', () => { btn.textContent = '⏸'; btn.classList.add('playing'); });
  audio.addEventListener('pause', () => { btn.textContent = '▶'; btn.classList.remove('playing'); });
  audio.addEventListener('ended', () => { btn.textContent = '▶'; btn.classList.remove('playing'); });
  return wrap;
}

function enrichToast(msg) {
  let stack = document.getElementById('enrichToastStack');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'enrichToastStack';
    stack.style.cssText = 'position:fixed;bottom:18px;left:18px;z-index:80;display:flex;flex-direction:column;gap:8px;';
    document.body.appendChild(stack);
  }
  const t = enrichEl(`<div style="background:var(--text);color:var(--bg);padding:8px 13px;border-radius:var(--radius);font-size:12.5px;box-shadow:0 6px 18px -6px rgba(0,0,0,.3);">${escapeHtml(msg)}</div>`);
  stack.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

function enrichCopy(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).catch(() => {});
  enrichToast(`Copied "${text}"`);
}

// Exclusive within a language group (translations — one chosen translation
// per target language) or the whole panel (ipa/tts — single-value field) —
// never global, so picking an EN translation doesn't un-mark a DE one.
function markSuggestUsed(btn) {
  const scope = btn.closest('.lang-group') || btn.closest('.suggest-panel') || document;
  scope.querySelectorAll('.use-btn.used').forEach((b) => { if (b !== btn) { b.classList.remove('used'); b.textContent = 'Use'; } });
  btn.classList.add('used');
  btn.textContent = '✓ Used';
}

function suggestFieldValue(prefix, field) {
  const el = document.getElementById(`${prefix}_${field}`);
  return el ? el.value.trim() : '';
}

// editor-session-hygiene design D1: each kind draws from exactly one named
// field, with no fallback between fields — inflections reads `lemma`,
// everything else reads `text`. TYPE_VISIBLE_FIELDS already guarantees
// `lemma` is only present for type=word, so this needs no separate type
// check: a non-word note's inflections panel isn't reachable with a stale
// lemma to begin with.
function defaultSuggestQuery(prefix, kind) {
  return suggestFieldValue(prefix, kind === 'inflections' ? 'lemma' : 'text');
}

// The combined suggest control (toggle + live query) sitting next to a
// panel's toggle button, if that kind has one (ipa/tts/translations do;
// inflections/stt don't). Reading the query from here — not recomputing a
// fresh default — means an edit made before the panel was even opened is
// respected when it fires (lemma-first-suggestions design D3).
function suggestControlInput(panelId) {
  const btn = document.querySelector(`[data-suggest-toggle="${panelId}"]`);
  const control = btn ? btn.closest('.suggest-control') : null;
  return control ? control.querySelector('.suggest-query') : null;
}

function suggestControlQueryValue(panelId, prefix) {
  const input = suggestControlInput(panelId);
  if (input) return input.value.trim();
  const panel = document.getElementById(panelId);
  return defaultSuggestQuery(prefix, panel ? panel.dataset.kind : null);
}

// stabbur's `source_lang` is deliberately language-agnostic (CLAUDE.md) and
// defaults to the macro-language code "no" for Norwegian notes; smia's
// providers expect the specific written-standard code "nb" (bokmål) — "no"
// isn't reliably recognized by them (confirmed live: dict.cc's /tts accepts
// "nb", not "no"). This maps at the request boundary only — the note's own
// stored source_lang is untouched.
function smiaLangCode(sourceLang) {
  if (sourceLang === 'no') return 'nb';
  return sourceLang || 'nb';
}

function enrichRequestFields(kind, prefix, queryValue, lang, limit) {
  const sourceLang = smiaLangCode(suggestFieldValue(prefix, 'source_lang'));
  if (kind === 'ipa') return { text: queryValue, lang: sourceLang };
  if (kind === 'inflections') return { word: queryValue, lang: sourceLang };
  if (kind === 'tts') return { text: queryValue, lang: sourceLang };
  if (kind === 'translations') return { text: queryValue, from: sourceLang, to: lang };
  if (kind === 'examples') return { text: queryValue, lang: sourceLang, limit };
  return {};
}

// smia's own default (design D4) — the count control starts here and is
// clamped to smia's accepted 1–10 range before ever being sent.
const EXAMPLES_DEFAULT_LIMIT = 3;
function examplesLimitValue(prefix) {
  const el = document.getElementById(`${prefix}_examples_count`);
  const n = el ? parseInt(el.value, 10) : NaN;
  if (!Number.isFinite(n)) return EXAMPLES_DEFAULT_LIMIT;
  return Math.min(10, Math.max(1, n));
}

// `forceRefresh` is only ever sent when true — an operator-initiated
// re-run (design D5) — never originated on an ordinary lookup, so the
// proxy (routes/enrich.py) stays a pass-through rather than acquiring a
// caching policy of its own.
async function enrichLookup(kind, provider, fields, forceRefresh) {
  return api(`/api/enrich/${kind}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...fields, provider, ...(forceRefresh ? { forceRefresh: true } : {}) }),
  });
}

// One provider row with its own editable query + retry (ipa/translations/
// tts — anything whose candidates are a flat list). `lang` is only used by
// translations, to know which target language this row belongs to.
// smia's forvo/filmot /tts adapters have no API — they always answer
// `{candidates: [], url}`, a link to check by hand (manual-link-audio-
// capture). This maps a provider name to the stabbur route that turns a
// pasted-back result into a real blob.
const MANUAL_LINK_CAPTURE_ROUTES = {
  forvo: '/api/enrich/manual-link/forvo',
  filmot: '/api/enrich/manual-link/filmot',
};

const MANUAL_LINK_PASTE_PLACEHOLDERS = {
  forvo: 'Paste the direct audio file URL you found there',
  filmot: 'Paste the YouTube URL + timecode you found there',
};

function renderManualLinkState(provider, url, prefix) {
  const captureRoute = MANUAL_LINK_CAPTURE_ROUTES[provider];
  const wrap = enrichEl(`
    <div class="manual-link-state">
      <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="btn-ghost">Open ${escapeHtml(provider)} ↗</a>
      <div class="manual-link-paste">
        <input type="text" class="manual-link-input" placeholder="${escapeHtml(MANUAL_LINK_PASTE_PLACEHOLDERS[provider] || 'Paste the link you found there')}">
        <button class="use-btn" type="button">Fetch &amp; attach</button>
      </div>
      <div class="manual-link-status inline-note"></div>
    </div>
  `);
  const input = wrap.querySelector('.manual-link-input');
  const btn = wrap.querySelector('.use-btn');
  const status = wrap.querySelector('.manual-link-status');

  btn.addEventListener('click', async () => {
    const pastedUrl = input.value.trim();
    if (!pastedUrl || (prefix === 'e' && !currentNote)) return;
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = '…';
    status.textContent = '';

    const fetched = await api(captureRoute, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: pastedUrl }),
    });
    if (fetched.status !== 200 || !fetched.body || !fetched.body.sha256) {
      btn.disabled = false;
      btn.textContent = originalLabel;
      status.textContent = (fetched.body && fetched.body.error) || 'Capture failed.';
      return;
    }

    const attached = await attachAudioToNote(prefix, fetched.body.sha256, provider, null);
    btn.disabled = false;
    btn.textContent = originalLabel;
    if (attached) {
      markSuggestUsed(btn);
      enrichToast(`Audio captured from ${provider} — trim it below if needed`);
    } else {
      status.textContent = 'Could not attach the captured audio.';
    }
  });

  return wrap;
}

// `defaultQuery` is the panel's shared query (the suggest-control's current
// value) — every row fires against it on open. A per-row override stays
// hidden until the ✎ button reveals it (progressive disclosure,
// lemma-first-suggestions design D5): revealed, it starts empty rather than
// copying `defaultQuery`, so it reads unambiguously as "something
// different," not a copy. Retrying uses the override's value if revealed
// and non-empty, otherwise falls back to `defaultQuery`.
function buildEnrichProviderRow(kind, provider, prefix, defaultQuery, renderCandidate, lang, initialForceRefresh, limit) {
  const row = enrichEl(`
    <div class="provider-row">
      <div class="provider-head">
        <span class="provider-name">${escapeHtml(provider)}</span>
        <span class="provider-spacer"></span>
        <button class="icon-btn provider-edit-btn" type="button" title="Override just this provider's query">✎</button>
        <button class="icon-btn retry-btn" type="button" title="Retry">↻</button>
      </div>
      <div class="provider-query">
        <input type="text" class="query-input" placeholder="override just for ${escapeHtml(provider)}">
      </div>
      <div class="provider-result"></div>
    </div>
  `);
  const resultBox = row.querySelector('.provider-result');
  const queryWrap = row.querySelector('.provider-query');
  const input = row.querySelector('.query-input');
  const editBtn = row.querySelector('.provider-edit-btn');
  const retryBtn = row.querySelector('.retry-btn');

  function currentQuery() {
    const override = input.value.trim();
    return (queryWrap.classList.contains('revealed') && override) ? override : defaultQuery;
  }

  async function fire(queryValue, forceRefresh) {
    resultBox.innerHTML = '<div class="suggest-skel"></div>';
    const fields = enrichRequestFields(kind, prefix, queryValue, lang, limit);
    const { status, body } = await enrichLookup(kind, provider, fields, forceRefresh);
    const isManualLink = status === 200 && body && Array.isArray(body.candidates)
      && body.candidates.length === 0 && body.url && MANUAL_LINK_CAPTURE_ROUTES[provider];
    if (isManualLink) {
      resultBox.innerHTML = '';
      resultBox.appendChild(renderManualLinkState(provider, body.url, prefix));
      return;
    }
    if (kind === 'ipa' && status === 200 && body && body.mode === 'per_word') {
      if (!Array.isArray(body.tokens) || body.tokens.length === 0) {
        resultBox.innerHTML = `<div class="suggest-error">No entry found for "${escapeHtml(queryValue)}".</div>`;
        return;
      }
      resultBox.innerHTML = '';
      resultBox.appendChild(renderIpaPerWord(body, provider, renderCandidate, prefix));
      return;
    }
    if (status !== 200 || !body || !Array.isArray(body.candidates) || body.candidates.length === 0) {
      resultBox.innerHTML = `<div class="suggest-error">No entry found for "${escapeHtml(queryValue)}".</div>`;
      return;
    }
    resultBox.innerHTML = '';
    body.candidates.forEach((c) => resultBox.appendChild(renderCandidate(c, provider)));
  }

  editBtn.addEventListener('click', async () => {
    const revealing = !queryWrap.classList.contains('revealed');
    queryWrap.classList.toggle('revealed');
    editBtn.classList.toggle('active', queryWrap.classList.contains('revealed'));
    if (!revealing) return;
    input.focus();
    // design D5 (operator-settings): prefilled with the shared query by
    // default, reversing lemma-first-suggestions' empty-by-default choice;
    // configurable back to empty. Collapsing without retrying still falls
    // back to `defaultQuery` regardless (currentQuery() above), so this
    // prefill is never mistaken for a value that was actually retried.
    if (!input.value) {
      const settings = await fetchSettings();
      if (settings.override_prefill !== false) input.value = defaultQuery;
    }
  });

  retryBtn.addEventListener('click', () => {
    retryBtn.classList.add('spinning');
    setTimeout(() => retryBtn.classList.remove('spinning'), 650);
    fire(currentQuery(), true);
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') retryBtn.click(); });

  fire(defaultQuery, initialForceRefresh);
  return row;
}

function renderIpaCandidate(prefix) {
  return (c, providerName) => {
    const value = c.ipa || c.phonemic || c.phonetic || '';
    const r = enrichEl(`
      <div class="candidate-row">
        <span class="candidate-text">${escapeHtml(value)}</span>
        <span class="candidate-meta">${escapeHtml(c.variety || '')}</span>
        <span class="candidate-spacer"></span>
        <button class="use-btn" type="button">Use</button>
      </div>
    `);
    r.querySelector('.use-btn').addEventListener('click', (e) => {
      const field = document.getElementById(`${prefix}_transcription`);
      field.value = value;
      field.dispatchEvent(new Event('input', { bubbles: true }));
      markSuggestUsed(e.target);
      enrichToast(`Transcription set from ${providerName}`);
    });
    return r;
  };
}

// Renders smia's `mode: "per_word"` /ipa answer: one group per token (in
// input order, a gap token shown unresolved rather than dropped), plus the
// `joined` assembled-fill row when smia supplies one (design D2/D3 — stabbur
// never synthesises a join itself when `joined` is absent).
function renderIpaPerWord(body, providerName, renderCandidate, prefix) {
  const wrap = document.createElement('div');
  wrap.className = 'ipa-per-word';
  body.tokens.forEach((token) => {
    const group = enrichEl(`
      <div class="ipa-token-group">
        <div class="ipa-token-label">${escapeHtml(token.text)}</div>
        <div class="ipa-token-candidates"></div>
      </div>
    `);
    const candidatesBox = group.querySelector('.ipa-token-candidates');
    if (Array.isArray(token.candidates) && token.candidates.length > 0) {
      token.candidates.forEach((c) => candidatesBox.appendChild(renderCandidate(c, providerName)));
    } else {
      candidatesBox.appendChild(enrichEl('<div class="ipa-token-missing">No entry</div>'));
    }
    wrap.appendChild(group);
  });
  if (body.joined) {
    const joinedRow = enrichEl(`
      <div class="ipa-joined-row">
        <span class="ipa-joined-label">Assembled from single words:</span>
        <span class="candidate-text">${escapeHtml(body.joined)}</span>
        <span class="candidate-spacer"></span>
        <button class="use-btn" type="button">Use</button>
      </div>
    `);
    joinedRow.querySelector('.use-btn').addEventListener('click', (e) => {
      const field = document.getElementById(`${prefix}_transcription`);
      field.value = body.joined;
      field.dispatchEvent(new Event('input', { bubbles: true }));
      markSuggestUsed(e.target);
      enrichToast(`Transcription assembled from ${providerName}`);
    });
    wrap.appendChild(joinedRow);
  }
  return wrap;
}

// design D6 (operator-settings): using a candidate for a language the note
// already has a translation for either appends to that row, separated by
// " / " (matching smia's own /ipa merged-varieties separator), or adds a
// separate row — whichever the operator's configured merge mode says.
// A language with no existing row always gets a new one regardless of mode
// (nothing to append to) — applies at point of use only, never rewrites
// anything already stored on save.
function useTranslationCandidate(containerId, lang, text, mergeMode, onChange) {
  const container = document.getElementById(containerId);
  const existingRow = Array.from(container.querySelectorAll('.translation-row'))
    .find((row) => row.querySelector('.t-lang').value.trim().toLowerCase() === lang.toLowerCase());
  if (existingRow && mergeMode === 'append') {
    const textInput = existingRow.querySelector('.t-text');
    const current = textInput.value.trim();
    textInput.value = current ? `${current} / ${text}` : text;
    textInput.dispatchEvent(new Event('input', { bubbles: true }));
    return;
  }
  addTranslationRow(containerId, lang, text, onChange);
}

function renderTranslationCandidate(prefix, lang) {
  return (c, providerName) => {
    const r = enrichEl(`
      <div class="candidate-row">
        <span class="candidate-text">${escapeHtml(c.text)}</span>
        ${c.context ? `<span class="candidate-meta">${escapeHtml(c.context)}</span>` : ''}
        <span class="candidate-spacer"></span>
        <button class="use-btn" type="button">Use</button>
      </div>
    `);
    r.querySelector('.use-btn').addEventListener('click', async (e) => {
      const onChange = prefix === 'e' ? updateNoteJsonView : null;
      const settings = await fetchSettings();
      useTranslationCandidate(`${prefix}_translations_list`, lang, c.text, settings.translation_merge_mode, onChange);
      if (onChange) onChange();
      markSuggestUsed(e.target);
      enrichToast(`Added ${lang.toUpperCase()} translation from ${providerName}`);
    });
    return r;
  };
}

// Shared by every path that ends with "a stabbur sha256 exists, attach it as
// this note's audio" — the TTS "Use" button and the manual-link
// forvo/filmot paste-back flow (manual-link-audio-capture) both land here.
// On the new-note form (no id yet) this stashes the hash for submitNewNote;
// on an existing note it PATCHes immediately. Returns true on success.
async function attachAudioToNote(prefix, sha256, providerName, meta) {
  if (prefix === 'c') {
    setNewNoteAudioFromSuggest(sha256, providerName, meta);
    return true;
  }
  if (prefix === 't') {
    if (!currentTriageNote) return false;
    triageStagedAudio = { sha256, providerName };
    renderTriageAudioSection({ ...currentTriageNote, audio_blob: sha256, audio_sel_ms: null });
    markTriageFieldProvenance('audio', providerName);
    return true;
  }
  if (prefix !== 'e' || !currentNote) return false;
  const patch = await api(`/api/notes/${currentNote.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_blob: sha256, audio_sel_ms: null }),
  });
  if (patch.status !== 200) return false;
  currentNote = patch.body;
  updateNoteJsonView();
  updateNoAudioWarning();
  renderAudioSection(currentNote);
  return true;
}

// ----------------------------------------- generic link-shaped capture ----
// manual-link-audio-capture design D7: one paste box, independent of any
// provider row — routes/enrich.py's /api/enrich/manual-link discriminates
// on the link itself. Shared by the editor's audio sidebar (e) and the
// triage belt's audio section (t).
document.querySelectorAll('.link-capture-btn').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const prefix = btn.dataset.linkPrefix;
    const input = document.getElementById(`${prefix}_link_url`);
    const status = document.getElementById(`${prefix}_link_status`);
    const url = input.value.trim();
    if (!url) return;
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = '…';
    if (status) status.textContent = '';

    const { status: httpStatus, body } = await api('/api/enrich/manual-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    btn.disabled = false;
    btn.textContent = originalLabel;
    if (httpStatus !== 200 || !body || !body.sha256) {
      if (status) status.textContent = (body && body.error) || 'Capture failed.';
      return;
    }
    const attached = await attachAudioToNote(prefix, body.sha256, 'pasted link', null);
    if (attached) {
      input.value = '';
      enrichToast('Audio captured from pasted link');
    } else if (status) {
      status.textContent = 'Could not attach the captured audio.';
    }
  });
});

function renderTtsCandidate(prefix) {
  return (c, providerName) => {
    const metaBits = [c.source, c.voice].filter(Boolean).join(' · ');
    const idBit = c.sha256 ? `${c.sha256.slice(0, 12)}…` : '';
    // Listening before committing: streams smia's cached bytes directly
    // (preview route, auth-exempt like /blob/) — never touches stabbur's
    // blob store, unlike clicking "Use".
    const previewSrc = c.sha256 ? `${API_BASE}/api/enrich/tts/preview/${c.sha256}` : '';
    const r = enrichEl(`
      <div class="candidate-row">
        <span class="candidate-text">${escapeHtml(idBit)}</span>
        <span class="candidate-meta">${escapeHtml(metaBits)}</span>
        <span class="candidate-spacer"></span>
        <button class="use-btn" type="button">Use</button>
      </div>
    `);
    if (previewSrc) r.querySelector('.candidate-spacer').after(buildAudioPreviewButton(previewSrc));
    r.querySelector('.use-btn').addEventListener('click', async (e) => {
      if (prefix !== 'e' && prefix !== 'c') return;
      if (prefix === 'e' && !currentNote) return;
      const btn = e.target;
      const originalLabel = btn.textContent;
      btn.disabled = true;
      btn.textContent = '…';
      const fetched = await api('/api/enrich/tts/use', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sha256: c.sha256 }),
      });
      if (fetched.status !== 200) {
        btn.disabled = false;
        btn.textContent = originalLabel;
        enrichToast('Could not fetch that candidate’s audio');
        return;
      }

      const attached = await attachAudioToNote(prefix, fetched.body.sha256, providerName, metaBits || idBit);
      btn.disabled = false;
      if (attached) {
        markSuggestUsed(btn);
        enrichToast(
          prefix === 'c'
            ? `Audio fetched from ${providerName} — will attach on save`
            : `Audio fetched from ${providerName} and stored as a blob`
        );
      } else {
        btn.textContent = originalLabel;
      }
    });
    return r;
  };
}

// A corpus provider (tatoeba/leipzig) names the dataset via `source`; a
// dictionary provider (ordbokene/kaikki) names the definition via `sense`.
// Both are optional and shown only when present — no placeholder for the
// absent one, since an absent field is a complete answer, not missing data
// (examples-context-suggestions design D3). smia strips translations from
// every example, so none is requested or rendered here.
function renderExamplesCandidate(prefix) {
  return (c, providerName) => {
    const metaBits = [];
    if (c.sense) metaBits.push(`sense: ${c.sense}`);
    if (c.source) metaBits.push(`source: ${c.source}`);
    const r = enrichEl(`
      <div class="candidate-sentence-row">
        <div class="candidate-text candidate-sentence-text">${escapeHtml(c.text || '')}</div>
        <div class="candidate-sentence-foot">
          ${metaBits.length ? `<span class="candidate-meta">${escapeHtml(metaBits.join(' · '))}</span>` : '<span class="candidate-spacer"></span>'}
          <button class="use-btn" type="button">Use</button>
        </div>
      </div>
    `);
    r.querySelector('.use-btn').addEventListener('click', (e) => {
      const field = document.getElementById(`${prefix}_context_text`);
      field.value = c.text || '';
      field.dispatchEvent(new Event('input', { bubbles: true }));
      markSuggestUsed(e.target);
      enrichToast(`Context set from ${providerName}`);
    });
    return r;
  };
}

// Inflections stays read-only/copy-only by design (D-smia-enrichment-panel
// fix #1) — providers disagree with each other and stabbur's own
// PoS-keyed fields often enough that auto-fill would silently hide real
// ambiguity. Each paradigm key/value is its own click-to-copy cell.
// Orders a paradigm's keys the same way the note form's own fields are
// ordered (INFLECTION_SHAPES) instead of whatever order the provider's JSON
// happened to use — a provider's own field order isn't guaranteed to match
// (confirmed live: a verb paradigm coming back as infinitiv/perfektum/
// presens/preteritum, not infinitiv/presens/preteritum/perfektum). Any key
// outside the known shape (unexpected/extra provider key) is appended
// after, never dropped.
function orderedParadigmEntries(pos, paradigm) {
  const shape = INFLECTION_SHAPES[pos] || [];
  const known = shape.filter((k) => k in paradigm).map((k) => [k, paradigm[k]]);
  const extra = Object.entries(paradigm).filter(([k]) => !shape.includes(k));
  return known.concat(extra);
}

// Same progressive-disclosure shape as buildEnrichProviderRow (lemma-first-
// suggestions): the shared query fires every provider on open, a per-
// provider override stays hidden behind ✎ until needed. Candidates stay
// read-only/copy-or-fill — never auto-filled (smia-enrichment-panel fix #1).
function buildInflectionsProviderBlock(provider, prefix, defaultQuery, initialForceRefresh) {
  const wrap = enrichEl(`
    <div class="provider-row">
      <div class="provider-head">
        <span class="provider-name">${escapeHtml(provider)}</span>
        <span class="provider-spacer"></span>
        <button class="icon-btn provider-edit-btn" type="button" title="Override just this provider's query">✎</button>
        <button class="icon-btn retry-btn" type="button" title="Retry">↻</button>
      </div>
      <div class="provider-query">
        <input type="text" class="query-input" placeholder="override just for ${escapeHtml(provider)}">
      </div>
      <div class="provider-result"></div>
    </div>
  `);
  const resultBox = wrap.querySelector('.provider-result');
  const queryWrap = wrap.querySelector('.provider-query');
  const input = wrap.querySelector('.query-input');
  const editBtn = wrap.querySelector('.provider-edit-btn');
  const retryBtn = wrap.querySelector('.retry-btn');

  function currentQuery() {
    const override = input.value.trim();
    return (queryWrap.classList.contains('revealed') && override) ? override : defaultQuery;
  }

  async function fire(queryValue, forceRefresh) {
    resultBox.innerHTML = '<div class="suggest-skel"></div>';
    const { status, body } = await enrichLookup('inflections', provider, enrichRequestFields('inflections', prefix, queryValue), forceRefresh);
    if (status !== 200 || !body || !Array.isArray(body.candidates) || body.candidates.length === 0) {
      resultBox.innerHTML = `<div class="suggest-error">No entry found for "${escapeHtml(queryValue)}".</div>`;
      return;
    }
    resultBox.innerHTML = '';
    body.candidates.forEach((c) => {
      const paradigm = c.paradigm || {};
      // Note-form field for this key, if the active note's current PoS has
      // one — a provider can report a key that doesn't apply (wrong PoS
      // guess), in which case only copy is offered (design.md D3).
      const fieldFor = (key) => document.querySelector(`#${prefix}_inflections_fields [data-inflection-field="${key}"]`);
      const paradigmRow = (key, value) => `
        <div class="paradigm-row">
          <span class="paradigm-key">${escapeHtml(key.replace(/_/g, ' '))}</span>
          <span class="paradigm-row-value">
            <span class="copy-cell" data-copy="${escapeHtml(value)}">${escapeHtml(value)}<span class="copy-ic">⧉</span></span>
            ${fieldFor(key) ? `<button class="fill-btn" type="button" data-fill-field="${escapeHtml(key)}" data-fill-value="${escapeHtml(value)}" title="Fill into the note's ${escapeHtml(key.replace(/_/g, ' '))} field">→ Fill</button>` : ''}
          </span>
        </div>
      `;

      // Substantiv candidates get the same singular/plural row grouping as
      // the note form itself (inflection-rows-and-fill); any key outside
      // the grouping (unexpected/extra provider key) still renders, just
      // appended after instead of silently dropped.
      const groups = INFLECTION_ROW_GROUPS[c.pos];
      let rowsHtml;
      if (groups) {
        const grouped = new Set(groups.flat());
        rowsHtml = groups
          .map((group) => `<div class="inflection-row">${group.filter((k) => k in paradigm).map((k) => paradigmRow(k, paradigm[k])).join('')}</div>`)
          .join('') + orderedParadigmEntries(c.pos, paradigm).filter(([k]) => !grouped.has(k)).map(([k, v]) => paradigmRow(k, v)).join('');
      } else {
        rowsHtml = orderedParadigmEntries(c.pos, paradigm).map(([k, v]) => paradigmRow(k, v)).join('');
      }

      const block = enrichEl(`
        <div class="paradigm-candidate">
          <div class="paradigm-candidate-head"><strong>${escapeHtml(c.lemma || '')}</strong> · ${escapeHtml(c.pos || '')}</div>
          ${rowsHtml}
        </div>
      `);
      block.querySelectorAll('.copy-cell').forEach((cell) => cell.addEventListener('click', () => enrichCopy(cell.dataset.copy)));
      block.querySelectorAll('.fill-btn').forEach((btn) => btn.addEventListener('click', () => {
        const field = fieldFor(btn.dataset.fillField);
        if (!field) return;
        field.value = btn.dataset.fillValue;
        field.dispatchEvent(new Event('input', { bubbles: true }));
        enrichToast(`${btn.dataset.fillField.replace(/_/g, ' ')} filled from ${provider}`);
      }));
      resultBox.appendChild(block);
    });
  }

  editBtn.addEventListener('click', async () => {
    const revealing = !queryWrap.classList.contains('revealed');
    queryWrap.classList.toggle('revealed');
    editBtn.classList.toggle('active', queryWrap.classList.contains('revealed'));
    if (!revealing) return;
    input.focus();
    if (!input.value) {
      const settings = await fetchSettings();
      if (settings.override_prefill !== false) input.value = defaultQuery;
    }
  });

  retryBtn.addEventListener('click', () => {
    retryBtn.classList.add('spinning');
    setTimeout(() => retryBtn.classList.remove('spinning'), 650);
    fire(currentQuery(), true);
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') retryBtn.click(); });

  fire(defaultQuery, initialForceRefresh);
  return wrap;
}

function buildTranslationsSuggestPanel(prefix, providers, defaultQuery, initialForceRefresh, defaultLangs) {
  const wrap = enrichEl(`
    <div>
      <div class="suggest-head"><span>${providers.length} provider(s) configured</span><span>editable per-provider</span></div>
      <div class="lang-add-row">
        <input type="text" class="new-lang-input" placeholder="add a language, e.g. fr" maxlength="8">
        <button class="btn-ghost" type="button">+ Add language</button>
      </div>
      <div class="lang-groups"></div>
    </div>
  `);
  const groupsEl = wrap.querySelector('.lang-groups');

  function addLangGroup(lang, forceRefresh) {
    lang = lang.trim().toLowerCase();
    if (!lang || groupsEl.querySelector(`[data-lang="${lang}"]`)) return;
    const group = enrichEl(`
      <div class="lang-group" data-lang="${lang}">
        <div class="lang-group-head"><span class="lang-pill">${escapeHtml(lang)}</span>${escapeHtml(enrichLangLabel(lang))}</div>
      </div>
    `);
    providers.forEach((p) => {
      group.appendChild(buildEnrichProviderRow('translations', p, prefix, defaultQuery, renderTranslationCandidate(prefix, lang), lang, forceRefresh));
    });
    groupsEl.appendChild(group);
  }

  // design D5.4 (operator-settings): the panel's language groups come from
  // the operator's configured default target languages, not a hardcoded
  // list — `defaultLangs` falls back to SUGGEST_DEFAULT_LANGS only if the
  // caller couldn't resolve settings at all.
  (defaultLangs && defaultLangs.length ? defaultLangs : SUGGEST_DEFAULT_LANGS).forEach((lang) => addLangGroup(lang, initialForceRefresh));

  const addBtn = wrap.querySelector('button');
  const input = wrap.querySelector('.new-lang-input');
  addBtn.addEventListener('click', () => { addLangGroup(input.value); input.value = ''; input.focus(); });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') addBtn.click(); });

  return wrap;
}

// /stt returns exactly one `{provider, text}` per request — no candidates
// array to pick among — so this renders a single block per provider rather
// than reusing buildEnrichProviderRow's candidates-array assumption
// (stt-text-suggest design.md D4... see D4 in that change's design.md).
function renderSttResult(prefix) {
  return (body, providerName) => {
    const r = enrichEl(`
      <div class="candidate-row">
        <span class="candidate-text">${escapeHtml(body.text || '(empty transcription)')}</span>
        <span class="candidate-spacer"></span>
        <button class="use-btn" type="button">Use</button>
      </div>
    `);
    r.querySelector('.use-btn').addEventListener('click', (e) => {
      const field = document.getElementById(`${prefix}_text`);
      // `text` is the note's primary content, unlike every other "Use"
      // target — confirm before clobbering anything already there
      // (stt-text-suggest design.md D5).
      if (field.value.trim() && !confirm('Replace the current text with this transcription?')) return;
      field.value = body.text || '';
      field.dispatchEvent(new Event('input', { bubbles: true }));
      markSuggestUsed(e.target);
      enrichToast(`Text set from ${providerName}`);
    });
    return r;
  };
}

function buildSttProviderBlock(provider, prefix) {
  const wrap = enrichEl(`
    <div class="provider-row">
      <div class="provider-head"><span class="provider-name">${escapeHtml(provider)}</span></div>
      <div class="provider-result"></div>
    </div>
  `);
  const resultBox = wrap.querySelector('.provider-result');

  resultBox.innerHTML = '<div class="suggest-skel"></div>';
  (async () => {
    const { status, body } = await api('/api/enrich/stt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider,
        audio_blob: currentNote ? currentNote.audio_blob : null,
        lang: smiaLangCode(suggestFieldValue(prefix, 'source_lang')),
      }),
    });
    if (status !== 200 || !body || typeof body.text !== 'string') {
      resultBox.innerHTML = `<div class="suggest-error">Transcription failed.</div>`;
      return;
    }
    resultBox.innerHTML = '';
    resultBox.appendChild(renderSttResult(prefix)(body, provider));
  })();

  return wrap;
}

// `forceRefresh` is only passed true from the panel-level ⟳ re-run control
// (design D5) — an ordinary open (toggle click or Enter in the shared
// query) leaves it false/undefined, so a first lookup is still free to
// answer from smia's cache. Rebuilding the panel from scratch here (rather
// than re-firing in place) keeps this the single path every provider's
// initial fire goes through, forced or not.
async function openSuggestPanel(panelEl, { forceRefresh = false } = {}) {
  const kind = panelEl.dataset.kind;
  const prefix = panelEl.dataset.prefix;
  const btn = document.querySelector(`[data-suggest-toggle="${panelEl.id}"]`);
  panelEl.classList.add('open');
  if (btn) btn.setAttribute('aria-expanded', 'true');
  panelEl.innerHTML = '<div class="suggest-head"><span>Loading providers…</span></div>';

  const catalog = await fetchEnrichProviders();
  const providers = catalog[kind] || [];
  panelEl.innerHTML = '';

  if (providers.length === 0) {
    panelEl.appendChild(enrichEl(`<div class="suggest-error">No providers currently configured for ${escapeHtml(kind)}.</div>`));
    return;
  }

  if (kind === 'translations') {
    const defaultQuery = suggestControlQueryValue(panelEl.id, prefix);
    const settings = await fetchSettings();
    panelEl.appendChild(buildTranslationsSuggestPanel(prefix, providers, defaultQuery, forceRefresh, settings.default_target_langs));
    return;
  }
  if (kind === 'inflections') {
    panelEl.appendChild(enrichEl(`<div class="suggest-head"><span>${providers.length} provider(s) configured</span><span>copy or fill per field</span></div>`));
    const defaultQuery = suggestControlQueryValue(panelEl.id, prefix);
    providers.forEach((p) => panelEl.appendChild(buildInflectionsProviderBlock(p, prefix, defaultQuery, forceRefresh)));
    return;
  }
  if (kind === 'stt') {
    panelEl.appendChild(enrichEl(`<div class="suggest-head"><span>${providers.length} provider(s) configured</span><span>transcribed from this note's audio</span></div>`));
    providers.forEach((p) => panelEl.appendChild(buildSttProviderBlock(p, prefix)));
    return;
  }

  panelEl.appendChild(enrichEl(`<div class="suggest-head"><span>${providers.length} provider(s) configured</span><span>editable per-provider</span></div>`));
  const defaultQuery = suggestControlQueryValue(panelEl.id, prefix);
  const renderCandidate = kind === 'ipa' ? renderIpaCandidate(prefix)
    : kind === 'examples' ? renderExamplesCandidate(prefix)
    : renderTtsCandidate(prefix);
  const limit = kind === 'examples' ? examplesLimitValue(prefix) : undefined;
  providers.forEach((p) => panelEl.appendChild(buildEnrichProviderRow(kind, p, prefix, defaultQuery, renderCandidate, undefined, forceRefresh, limit)));
}

function closeSuggestPanel(panelEl) {
  panelEl.classList.remove('open');
  const btn = document.querySelector(`[data-suggest-toggle="${panelEl.id}"]`);
  if (btn) btn.setAttribute('aria-expanded', 'false');
}

document.querySelectorAll('[data-suggest-toggle]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const panel = document.getElementById(btn.dataset.suggestToggle);
    if (!panel) return;
    if (panel.classList.contains('open')) closeSuggestPanel(panel);
    else openSuggestPanel(panel);
  });
});

// ------------------------------------------------------------- settings --

// Human labels/hints for the kinds stabbur proxies (routes/enrich.py's
// ENRICHABLE_KINDS) — "tts" reads as "Audio" everywhere else in this UI,
// so the settings page matches rather than exposing the wire name.
const SETTINGS_KIND_ORDER = ['ipa', 'translations', 'inflections', 'tts', 'examples'];
const SETTINGS_KIND_LABELS = { ipa: 'Transcription', translations: 'Translations', inflections: 'Inflections', tts: 'Audio', examples: 'Examples' };
const SETTINGS_KIND_HINTS = {
  ipa: 'Queried with text.',
  translations: 'Queried with text.',
  inflections: 'Queried with lemma — the only kind that is.',
  tts: 'Queried with text. Manual-link providers cannot answer automatically, so a prefill run skips past them.',
  examples: 'Queried with text. No translation is requested or shown.',
};

function renumberPlist(plist) {
  Array.from(plist.querySelectorAll('.pitem')).forEach((item, idx) => {
    item.querySelector('.ord').textContent = String(idx + 1);
  });
}

async function saveSettingsProviderOrder(kind, plist) {
  const items = Array.from(plist.querySelectorAll('.pitem'));
  const order = items.map((item) => item.dataset.provider);
  const disabled = items
    .filter((item) => item.querySelector('.switch').getAttribute('aria-pressed') !== 'true')
    .map((item) => item.dataset.provider);
  const { status, body } = await api('/api/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ providers: { [kind]: { order, disabled } } }),
  });
  if (status === 200) {
    _settingsCache = body;
    renderSettingsProviders(body.providers || {});
  }
}

// Reorderable per-kind provider list (4.3): drag to reorder, a switch per
// provider to enable/disable, the effective primary and manual-link
// providers (4.4 — forvo/filmot, same MANUAL_LINK_CAPTURE_ROUTES the
// editor's audio panel already keys off) called out on their row.
function renderSettingsProviders(providers) {
  const container = document.getElementById('settingsProvidersBody');
  container.innerHTML = '';
  SETTINGS_KIND_ORDER.forEach((kind) => {
    const info = providers[kind] || { order: [], disabled: [], primary: null };
    container.appendChild(enrichEl(`
      <div class="sitem">
        <div class="txt"><b>${escapeHtml(SETTINGS_KIND_LABELS[kind] || kind)}</b><p>${escapeHtml(SETTINGS_KIND_HINTS[kind] || '')}</p></div>
      </div>
    `));
    const sub = enrichEl(`<div class="sitem sub"><div class="plist" data-kind="${escapeHtml(kind)}"></div></div>`);
    container.appendChild(sub);
    const plist = sub.querySelector('.plist');

    if (info.order.length === 0) {
      plist.appendChild(enrichEl('<div class="inline-note">No providers currently configured for this kind.</div>'));
      return;
    }

    info.order.forEach((provider, idx) => {
      const disabled = info.disabled.includes(provider);
      const item = enrichEl(`
        <div class="pitem ${disabled ? 'off' : ''}" draggable="true" data-provider="${escapeHtml(provider)}">
          <span class="grip">⠿</span>
          <span class="ord">${idx + 1}</span>
          <span class="nm">${escapeHtml(provider)}</span>
          <span class="tail">
            ${provider === info.primary ? '<span class="pill pill-accent">primary</span>' : ''}
            ${MANUAL_LINK_CAPTURE_ROUTES[provider] ? '<span class="pill">manual link</span>' : ''}
            <button type="button" class="switch" aria-pressed="${disabled ? 'false' : 'true'}" aria-label="Enable ${escapeHtml(provider)}"></button>
          </span>
        </div>
      `);
      plist.appendChild(item);
    });

    plist.querySelectorAll('.switch').forEach((btn) => {
      btn.addEventListener('click', () => {
        const wasEnabled = btn.getAttribute('aria-pressed') === 'true';
        btn.setAttribute('aria-pressed', wasEnabled ? 'false' : 'true');
        btn.closest('.pitem').classList.toggle('off', wasEnabled);
        saveSettingsProviderOrder(kind, plist);
      });
    });

    let dragEl = null;
    plist.querySelectorAll('.pitem').forEach((item) => {
      item.addEventListener('dragstart', () => { dragEl = item; item.classList.add('dragging'); });
      item.addEventListener('dragend', () => {
        item.classList.remove('dragging');
        dragEl = null;
        saveSettingsProviderOrder(kind, plist);
      });
      item.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!dragEl || dragEl === item) return;
        const rect = item.getBoundingClientRect();
        const before = (e.clientY - rect.top) < rect.height / 2;
        plist.insertBefore(dragEl, before ? item : item.nextSibling);
        renumberPlist(plist);
      });
    });
  });
}

async function patchSettingsScalar(updates) {
  const resultEl = document.getElementById('settingsSaveResult');
  const { status, body } = await api('/api/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (status === 200) {
    _settingsCache = body;
    resultEl.textContent = 'Saved.';
    setTimeout(() => { if (resultEl.textContent === 'Saved.') resultEl.textContent = ''; }, 1500);
  } else {
    resultEl.textContent = (body && body.error) || 'Could not save.';
  }
}

// Wired once at script load (not inside renderSettings, which re-runs
// every time the page is visited) — same idiom as wireChipGroup above —
// so repeat visits never stack duplicate click listeners on these static
// controls. renderSettings only ever updates their visual state.
(function wireSettingsScalarControls() {
  const prefillSeg = document.getElementById('settingsPrefillTimingSeg');
  prefillSeg.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      prefillSeg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', 'false'));
      btn.setAttribute('aria-pressed', 'true');
      patchSettingsScalar({ prefill_timing: btn.dataset.value });
    });
  });

  const seg = document.getElementById('settingsMergeModeSeg');
  seg.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', 'false'));
      btn.setAttribute('aria-pressed', 'true');
      patchSettingsScalar({ translation_merge_mode: btn.dataset.value });
    });
  });

  document.getElementById('settingsDefaultLangsInput').addEventListener('change', (e) => {
    const langs = e.target.value.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    patchSettingsScalar({ default_target_langs: langs });
  });

  const prefillSwitch = document.getElementById('settingsOverridePrefillSwitch');
  prefillSwitch.addEventListener('click', () => {
    const next = prefillSwitch.getAttribute('aria-pressed') !== 'true';
    prefillSwitch.setAttribute('aria-pressed', next ? 'true' : 'false');
    patchSettingsScalar({ override_prefill: next });
  });
})();

// Guards against a stale load clobbering a fresher one — e.g. the page's
// very first render firing before the bearer token is in place (401),
// then resolving after a later, successful re-render of the same page.
let _settingsRenderToken = 0;

async function renderSettings() {
  const renderToken = ++_settingsRenderToken;
  const resultEl = document.getElementById('settingsSaveResult');
  resultEl.textContent = '';
  const { status, body } = await api('/api/settings');
  if (renderToken !== _settingsRenderToken) return;
  if (status !== 200) {
    resultEl.textContent = 'Could not load settings.';
    return;
  }
  _settingsCache = body;

  renderSettingsProviders(body.providers || {});

  const seg = document.getElementById('settingsMergeModeSeg');
  seg.querySelectorAll('button').forEach((btn) => {
    btn.setAttribute('aria-pressed', btn.dataset.value === body.translation_merge_mode ? 'true' : 'false');
  });
  document.getElementById('settingsDefaultLangsInput').value = (body.default_target_langs || []).join(', ');
  document.getElementById('settingsOverridePrefillSwitch').setAttribute('aria-pressed', body.override_prefill ? 'true' : 'false');

  document.querySelectorAll('#settingsPrefillTimingSeg button').forEach((btn) => {
    btn.setAttribute('aria-pressed', btn.dataset.value === body.prefill_timing ? 'true' : 'false');
  });
}

// ------------------------------------------------------------ note-triage --
// origin-scoped-triage-belt: a queue of drafted notes reviewed one at a
// time, scoped to exactly one origin (design D1/D2). Reuses the editor's
// field components under the `t_` prefix (translations/inflections/
// suggest-panel machinery are already generic over `prefix`) so the two
// surfaces can't drift (tasks 3.6).

const TRIAGE_ORIGIN_STORAGE_KEY = 'stabbur_triage_origin';
let currentTriageNote = null;
let triageQueue = [];
let triageIndex = 0;
let triageDeferredCount = 0;
// Audio (unlike every other field) normally attaches with an immediate
// PATCH (attachAudioToNote's 'e' path) — staged here instead, so "skip"
// genuinely saves nothing (design D8) and a verdict is what actually
// commits it, same as every other field's edits.
let triageStagedAudio = null;

function triageOrigin() {
  return document.getElementById('triageOriginSelect').value;
}

document.getElementById('triageOriginSelect').addEventListener('change', () => {
  localStorage.setItem(TRIAGE_ORIGIN_STORAGE_KEY, triageOrigin());
  loadTriageQueue();
});

async function refreshTriageRailBadge() {
  const { status, body } = await api('/api/notes/authoring/counts?status=draft');
  const badge = document.getElementById('triageRailBadge');
  if (status !== 200) { badge.style.display = 'none'; return; }
  const total = Object.values(body).reduce((a, b) => a + b, 0);
  badge.textContent = String(total);
  badge.style.display = total > 0 ? '' : 'none';
}
refreshTriageRailBadge();

async function renderTriage() {
  const saved = localStorage.getItem(TRIAGE_ORIGIN_STORAGE_KEY);
  if (saved) document.getElementById('triageOriginSelect').value = saved;
  await loadTriageQueue();
}

async function loadTriageQueue() {
  triageDeferredCount = 0;
  const origin = triageOrigin();
  const { status, body } = await api(`/api/notes/authoring${qs({ status: 'draft', origin, sort: 'updated_asc' })}`);
  triageQueue = status === 200 ? body : [];
  triageIndex = 0;
  refreshTriageRailBadge();
  updateTriageBelt();
  await showTriageNote();
}

function updateTriageBelt() {
  const total = triageQueue.length;
  const remaining = Math.max(0, total - triageIndex);
  document.getElementById('triageCount').innerHTML = `${remaining} <small>/ ${total}</small>`;
  const deferredPill = document.getElementById('triageDeferredPill');
  if (triageDeferredCount > 0) {
    deferredPill.style.display = '';
    deferredPill.textContent = `${triageDeferredCount} sent back`;
  } else {
    deferredPill.style.display = 'none';
  }
}

function triageProvenanceSrcId(fieldKey) {
  return { transcription: 't_transcription_src', translations: 't_translations_src', inflections: 't_inflections_src', context_text: 't_context_text_src', audio: 't_audio_src' }[fieldKey];
}

function markTriageFieldProvenance(fieldKey, provider) {
  const el = document.getElementById(triageProvenanceSrcId(fieldKey));
  if (!el) return;
  el.textContent = provider;
  el.style.display = '';
}

function clearTriageProvenanceBadges() {
  ['transcription', 'translations', 'inflections', 'context_text', 'audio'].forEach((key) => {
    const el = document.getElementById(triageProvenanceSrcId(key));
    if (el) { el.style.display = 'none'; el.textContent = ''; }
  });
}

// Prefill fills gaps, never opinions (design D5) — but once the operator
// has typed into a field themselves, its provenance badge no longer
// describes what's actually there, so an edit clears it rather than
// leaving a stale attribution ("not attributed to any provider").
document.getElementById('triageForm').addEventListener('input', (e) => {
  syncSuggestQueries('t');
  const fieldKey = {
    t_transcription: 'transcription', t_context_text: 'context_text',
  }[e.target.id];
  if (fieldKey) {
    const el = document.getElementById(triageProvenanceSrcId(fieldKey));
    if (el) { el.style.display = 'none'; el.textContent = ''; }
  }
  if (e.target.closest('#t_translations_list')) {
    const el = document.getElementById('t_translations_src');
    if (el) { el.style.display = 'none'; el.textContent = ''; }
  }
  if (e.target.closest('#t_inflections_fields')) {
    const el = document.getElementById('t_inflections_src');
    if (el) { el.style.display = 'none'; el.textContent = ''; }
  }
});

function renderTriageAudioSection(note) {
  const none = document.getElementById('t_audio_none');
  const player = document.getElementById('t_audio_player');
  if (!note.audio_blob) {
    none.style.display = 'block';
    player.style.display = 'none';
    return;
  }
  none.style.display = 'none';
  player.style.display = 'block';
  document.getElementById('t_audioElement').src = `${API_BASE}/blob/${note.audio_blob}`;
  const sel = note.audio_sel_ms;
  document.getElementById('t_audio_sel_note').textContent =
    sel && sel.length === 2 ? `trim ${(sel[0] / 1000).toFixed(2)} – ${(sel[1] / 1000).toFixed(2)} s (adjust in the editor)` : '';
}

async function showTriageNote() {
  const empty = document.getElementById('triageEmpty');
  const cardWrap = document.getElementById('triageCardWrap');
  const verdictBar = document.getElementById('triageVerdictBar');

  if (triageIndex >= triageQueue.length) {
    currentTriageNote = null;
    empty.style.display = 'block';
    cardWrap.style.display = 'none';
    verdictBar.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  cardWrap.style.display = 'block';
  verdictBar.style.display = 'block';

  const note = triageQueue[triageIndex];
  currentTriageNote = note;
  triageStagedAudio = null;

  document.getElementById('triageHeadword').textContent = note.text;
  document.getElementById('triageMeta').innerHTML =
    `${escapeHtml(note.type)} · ${escapeHtml(note.pos || '—')} · ${originLabel(note)} · seq ${note.seq}`;

  document.getElementById('t_text').value = note.text || '';
  document.getElementById('t_lemma').value = note.lemma || '';
  document.getElementById('t_type').value = note.type;
  setPosValue('t_pos_select', 't_pos_custom', note.pos);
  document.getElementById('t_source_lang').value = note.source_lang || '';
  document.getElementById('t_transcription').value = note.transcription || '';
  renderTranslationRows('t_translations_list', note.translations, null);
  document.getElementById('t_context_text').value = note.context_text || '';
  await populateGrammarRuleSelect(document.getElementById('t_grammar_rule_id'), note.grammar_rule_id);

  updateTriageInflectionFields(note.pos, note.inflections);
  updateTriageFieldVisibility();
  resetSuggestQueries('t'); // closes and empties every suggest panel (tasks 3.5/5.7/7.10)
  clearTriageProvenanceBadges();
  renderTriageAudioSection(note);

  const settings = await fetchSettings();
  if ((settings.prefill_timing || 'on_open') === 'on_open') runTriagePrefill();
}

function updateTriageInflectionFields(pos, values) {
  const shapedPos = INFLECTION_SHAPES[pos] ? pos : null;
  document.getElementById('t_inflections_field').style.display = shapedPos ? 'block' : 'none';
  if (shapedPos) renderInflectionFields('t_inflections_fields', shapedPos, values);
  else document.getElementById('t_inflections_fields').innerHTML = '';
}

function updateTriageFieldVisibility() {
  const type = document.getElementById('t_type').value;
  document.getElementById('t_grammar_rule_field').style.display = type === 'grammar' ? 'block' : 'none';
  applyTypeFieldVisibility('t', type);
}

document.getElementById('t_type').addEventListener('change', updateTriageFieldVisibility);
wirePosCustomToggle('t_pos_select', 't_pos_custom', () => {
  const pos = getPosValue('t_pos_select', 't_pos_custom');
  updateTriageInflectionFields(pos, currentTriageNote && currentTriageNote.pos === pos ? currentTriageNote.inflections : null);
});
document.getElementById('t_add_translation').addEventListener('click', () => {
  addTranslationRow('t_translations_list', '', '', null);
});
wireLemmaTextSync('t');

function readTriageForm() {
  const pos = getPosValue('t_pos_select', 't_pos_custom');
  const shapedPos = INFLECTION_SHAPES[pos] ? pos : null;
  const inflections = shapedPos ? readInflectionFields('t_inflections_fields') : (currentTriageNote?.inflections ?? {});
  return {
    text: document.getElementById('t_text').value,
    lemma: document.getElementById('t_lemma').value || null,
    type: document.getElementById('t_type').value,
    pos,
    source_lang: document.getElementById('t_source_lang').value,
    transcription: document.getElementById('t_transcription').value || null,
    translations: readTranslationRows('t_translations_list'),
    inflections,
    context_text: document.getElementById('t_context_text').value || null,
    grammar_rule_id: document.getElementById('t_grammar_rule_id').value
      ? Number(document.getElementById('t_grammar_rule_id').value)
      : null,
    ...(triageStagedAudio ? { audio_blob: triageStagedAudio.sha256, audio_sel_ms: null } : {}),
  };
}

// ── verdicts (design D8: accept is the only path to `ready`) ─────────────

async function saveTriageEdits() {
  if (!currentTriageNote) return null;
  const { status, body } = await api(`/api/notes/${currentTriageNote.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(readTriageForm()),
  });
  return status === 200 ? body : null;
}

function advanceTriageIndex() {
  triageIndex += 1;
  updateTriageBelt();
  showTriageNote();
}

document.getElementById('triageAcceptBtn').addEventListener('click', async () => {
  if (!currentTriageNote) return;
  const payload = readTriageForm();
  payload.status = 'ready';
  const { status } = await api(`/api/notes/${currentTriageNote.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (status === 200) { advanceTriageIndex(); refreshTriageRailBadge(); }
});

document.getElementById('triageSendBackBtn').addEventListener('click', async () => {
  if (!currentTriageNote) return;
  const saved = await saveTriageEdits();
  if (!saved) return;
  triageDeferredCount += 1;
  // design D3: deferral is just a save, so the note sorts last under
  // `updated_asc` — moved to the end of the in-memory queue too, so it
  // reads as deferred within this pass, not only after a reload.
  triageQueue.splice(triageIndex, 1);
  triageQueue.push(saved);
  updateTriageBelt();
  await showTriageNote();
});

document.getElementById('triageSkipBtn').addEventListener('click', () => {
  if (!currentTriageNote) return;
  advanceTriageIndex();
});

document.getElementById('triageDeleteBtn').addEventListener('click', async () => {
  if (!currentTriageNote) return;
  if (!confirm(`Delete "${currentTriageNote.text}"? Every note in this queue is a draft, so this is a hard delete.`)) return;
  const { status } = await api(`/api/notes/${currentTriageNote.id}`, { method: 'DELETE' });
  if (status === 204 || status === 200) { advanceTriageIndex(); refreshTriageRailBadge(); }
});

document.getElementById('triagePrefillBtn').addEventListener('click', () => runTriagePrefill());

document.getElementById('t_upload_audio_btn').addEventListener('click', async () => {
  if (!currentTriageNote) return;
  const fileInput = document.getElementById('t_audio_file');
  const file = fileInput.files[0];
  if (!file) return;
  const btn = document.getElementById('t_upload_audio_btn');
  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = '…';
  const form = new FormData();
  form.append('audio', file);
  const uploadResp = await fetch(`${API_BASE}/blobs`, { method: 'POST', headers: authHeaders(), body: form });
  const uploadBody = await uploadResp.json();
  btn.disabled = false;
  btn.textContent = originalLabel;
  if (uploadResp.status !== 200) { enrichToast('Upload failed'); return; }
  fileInput.value = '';
  await attachAudioToNote('t', uploadBody.sha256, 'manual upload', file.name);
});

// Place delete away from accept in the key layout (design Risks/task 4.6):
// ⌫/Delete at one end, ⏎ accept at the other, with send-to-back/skip
// between them. Suppressed while focus is in any form control, so typing
// in a field never fires a verdict by accident.
document.addEventListener('keydown', (e) => {
  if (parseHash().route !== 'triage' || !currentTriageNote) return;
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  if (e.key === 'Enter') { e.preventDefault(); document.getElementById('triageAcceptBtn').click(); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); document.getElementById('triageSkipBtn').click(); }
  else if (e.key.toLowerCase() === 'l') { e.preventDefault(); document.getElementById('triageSendBackBtn').click(); }
  else if (e.key === 'Backspace' || e.key === 'Delete') { e.preventDefault(); document.getElementById('triageDeleteBtn').click(); }
});

// ── prefill: N ordinary pass-through lookups, walking the operator's
// configured provider order client-side (design D4 — routes/enrich.py
// gains no chain logic of its own) ────────────────────────────────────────

async function walkProviders(kind, prefix, queryValue, lang, limit) {
  const settings = await fetchSettings();
  const info = (settings.providers && settings.providers[kind]) || {};
  const disabled = new Set(info.disabled || []);
  const providers = (info.order || []).filter((p) => !disabled.has(p));
  for (const provider of providers) {
    const fields = enrichRequestFields(kind, prefix, queryValue, lang, limit);
    const { status, body } = await enrichLookup(kind, provider, fields, false);
    if (status !== 200 || !body) continue;
    if (kind === 'ipa' && body.mode === 'per_word') {
      if (body.joined) return { provider, value: body.joined };
      continue;
    }
    if (Array.isArray(body.candidates) && body.candidates.length > 0) {
      return { provider, candidate: body.candidates[0] };
    }
  }
  return null;
}

async function runTriagePrefill() {
  if (!currentTriageNote) return;
  const settings = await fetchSettings();
  const sourceLang = smiaLangCode(document.getElementById('t_source_lang').value);
  let filledCount = 0;

  const transcriptionEl = document.getElementById('t_transcription');
  if (!transcriptionEl.value.trim()) {
    const query = defaultSuggestQuery('t', 'ipa');
    if (query) {
      const result = await walkProviders('ipa', 't', query, sourceLang);
      const value = result && (result.value || (result.candidate && (result.candidate.ipa || result.candidate.phonemic || result.candidate.phonetic)));
      if (value) {
        transcriptionEl.value = value;
        markTriageFieldProvenance('transcription', result.provider);
        filledCount += 1;
      }
    }
  }

  const existingLangs = new Set(readTranslationRows('t_translations_list').map((t) => t.lang.toLowerCase()));
  const targetLangs = (settings.default_target_langs && settings.default_target_langs.length) ? settings.default_target_langs : SUGGEST_DEFAULT_LANGS;
  const translationsQuery = defaultSuggestQuery('t', 'translations');
  if (translationsQuery) {
    for (const lang of targetLangs) {
      if (existingLangs.has(lang.toLowerCase())) continue;
      const result = await walkProviders('translations', 't', translationsQuery, lang);
      if (result && result.candidate && result.candidate.text) {
        addTranslationRow('t_translations_list', lang, result.candidate.text, null);
        markTriageFieldProvenance('translations', result.provider);
        filledCount += 1;
      }
    }
  }

  const pos = getPosValue('t_pos_select', 't_pos_custom');
  if (INFLECTION_SHAPES[pos]) {
    const lemma = document.getElementById('t_lemma').value.trim();
    if (lemma) {
      const result = await walkProviders('inflections', 't', lemma);
      if (result && result.candidate && result.candidate.paradigm) {
        const current = readInflectionFields('t_inflections_fields');
        let any = false;
        INFLECTION_SHAPES[pos].forEach((field) => {
          if (!current[field] && result.candidate.paradigm[field]) {
            const input = document.querySelector(`#t_inflections_fields [data-inflection-field="${field}"]`);
            if (input) { input.value = result.candidate.paradigm[field]; any = true; }
          }
        });
        if (any) { markTriageFieldProvenance('inflections', result.provider); filledCount += 1; }
      }
    }
  }

  const ctxEl = document.getElementById('t_context_text');
  if (!ctxEl.value.trim()) {
    const exQuery = defaultSuggestQuery('t', 'examples');
    if (exQuery) {
      const result = await walkProviders('examples', 't', exQuery, undefined, examplesLimitValue('t'));
      if (result && result.candidate && result.candidate.text) {
        ctxEl.value = result.candidate.text;
        markTriageFieldProvenance('context_text', result.provider);
        filledCount += 1;
      }
    }
  }

  // Audio: only a real candidate (sha256 present) auto-attaches — a
  // manual-link provider's empty-candidates-plus-url answer is exactly the
  // "has no entry" case the walk is defined to fall through on, never
  // something to surface here (settings page's own note on this).
  if (currentTriageNote && !currentTriageNote.audio_blob) {
    const audioQuery = defaultSuggestQuery('t', 'tts');
    if (audioQuery) {
      const result = await walkProviders('tts', 't', audioQuery, sourceLang);
      if (result && result.candidate && result.candidate.sha256) {
        const fetched = await api('/api/enrich/tts/use', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sha256: result.candidate.sha256 }),
        });
        if (fetched.status === 200) {
          const attached = await attachAudioToNote('t', fetched.body.sha256, result.provider, null);
          if (attached) { markTriageFieldProvenance('audio', result.provider); filledCount += 1; }
        }
      }
    }
  }

  syncSuggestQueries('t');
  if (filledCount > 0) enrichToast(`Prefilled ${filledCount} field${filledCount === 1 ? '' : 's'}`);
}
