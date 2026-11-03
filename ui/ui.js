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

const notesListState = { status: '', type: '', sortField: 'updated', sortDir: 'desc' };

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
  const sort = `${notesListState.sortField}_${notesListState.sortDir}`;
  const q = document.getElementById('notesSearch').value.trim();

  const { status: httpStatus, body } = await api(`/api/notes/authoring${qs({ status, type, sort, q })}`);
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
  updateLemmaSuggestVisibility('e', 'e_pos_select', 'e_pos_custom');
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
  updateLemmaSuggestVisibility('e', 'e_pos_select', 'e_pos_custom');
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
  updateLemmaSuggestVisibility('c', 'c_pos', 'c_pos_custom');
}

function updateNewNoteInflectionFields() {
  const pos = getPosValue('c_pos', 'c_pos_custom');
  const shaped = !!INFLECTION_SHAPES[pos];
  document.getElementById('c_inflections_field').style.display = shaped ? 'block' : 'none';
  renderInflectionFields('c_inflections_fields', pos);
  updateLemmaSuggestVisibility('c', 'c_pos', 'c_pos_custom');
}

wirePosCustomToggle('c_pos', 'c_pos_custom', updateNewNoteInflectionFields);

async function renderNewNote() {
  document.getElementById('createForm').reset();
  document.getElementById('c_source_lang').value = 'no';
  document.getElementById('createResult').textContent = '';
  clearNewNoteAudioFromSuggest();
  renderTranslationRows('c_translations_list', [], null);
  updateNewNoteFieldVisibility();
  updateNewNoteInflectionFields();
  resetSuggestQueries('c');
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

  newNoteAudioFromSuggest = null;
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

const SUGGEST_DEFAULT_LANGS = ['en', 'de'];

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

// Syncs every suggest-control's query field to the current lemma||text,
// skipping any control the operator has directly edited (`dirty`) so an
// unrelated field edit never clobbers a deliberate override.
function syncSuggestQueries(prefix) {
  const value = defaultSuggestQuery(prefix);
  querySuggestControls(prefix).forEach((control) => {
    const input = control.querySelector('.suggest-query');
    if (input && input.dataset.dirty !== '1') input.value = value;
  });
}

// Called when a note is (re)loaded into a form — clears any prior dirty
// state so the new note starts with every query back in sync.
function resetSuggestQueries(prefix) {
  querySuggestControls(prefix).forEach((control) => {
    const input = control.querySelector('.suggest-query');
    if (input) delete input.dataset.dirty;
  });
  syncSuggestQueries(prefix);
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
  // matching every other suggest input's manual-trigger convention.
  input.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const panel = document.getElementById(btn.dataset.suggestToggle);
    if (panel) openSuggestPanel(panel);
  });
});
updateSuggestCounts();

// ── verb-only "From text" lemma-suggest button ───────────────────────────

function deriveLemmaFromText(text) {
  return text.trim().replace(/^å\s+/i, '');
}

function updateLemmaSuggestVisibility(prefix, selectId, customId) {
  const pos = getPosValue(selectId, customId);
  const btn = document.getElementById(`${prefix}_lemma_suggest_btn`);
  if (btn) btn.style.display = pos === 'verb' ? '' : 'none';
}

function wireLemmaSuggestButton(prefix, textId, lemmaId) {
  const btn = document.getElementById(`${prefix}_lemma_suggest_btn`);
  if (!btn) return;
  btn.addEventListener('click', () => {
    const lemmaEl = document.getElementById(lemmaId);
    lemmaEl.value = deriveLemmaFromText(document.getElementById(textId).value);
    lemmaEl.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
wireLemmaSuggestButton('e', 'e_text', 'e_lemma');
wireLemmaSuggestButton('c', 'c_text', 'c_lemma');

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

// lemma-first-suggestions: type=word notes default every suggestion query
// to `lemma`, falling back to `text` only when no lemma is set (non-`word`
// types never have a lemma field to begin with, so this needs no separate
// type check — an empty/hidden lemma already falls through).
function defaultSuggestQuery(prefix) {
  return suggestFieldValue(prefix, 'lemma') || suggestFieldValue(prefix, 'text');
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
  return input ? input.value.trim() : defaultSuggestQuery(prefix);
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

function enrichRequestFields(kind, prefix, queryValue, lang) {
  const sourceLang = smiaLangCode(suggestFieldValue(prefix, 'source_lang'));
  if (kind === 'ipa') return { text: queryValue, lang: sourceLang };
  if (kind === 'inflections') return { word: queryValue, lang: sourceLang };
  if (kind === 'tts') return { text: queryValue, lang: sourceLang };
  if (kind === 'translations') return { text: queryValue, from: sourceLang, to: lang };
  return {};
}

async function enrichLookup(kind, provider, fields) {
  return api(`/api/enrich/${kind}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...fields, provider }),
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
function buildEnrichProviderRow(kind, provider, prefix, defaultQuery, renderCandidate, lang) {
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

  async function fire(queryValue) {
    resultBox.innerHTML = '<div class="suggest-skel"></div>';
    const fields = enrichRequestFields(kind, prefix, queryValue, lang);
    const { status, body } = await enrichLookup(kind, provider, fields);
    const isManualLink = status === 200 && body && Array.isArray(body.candidates)
      && body.candidates.length === 0 && body.url && MANUAL_LINK_CAPTURE_ROUTES[provider];
    if (isManualLink) {
      resultBox.innerHTML = '';
      resultBox.appendChild(renderManualLinkState(provider, body.url, prefix));
      return;
    }
    if (status !== 200 || !body || !Array.isArray(body.candidates) || body.candidates.length === 0) {
      resultBox.innerHTML = `<div class="suggest-error">No entry found for "${escapeHtml(queryValue)}".</div>`;
      return;
    }
    resultBox.innerHTML = '';
    body.candidates.forEach((c) => resultBox.appendChild(renderCandidate(c, provider)));
  }

  editBtn.addEventListener('click', () => {
    queryWrap.classList.toggle('revealed');
    editBtn.classList.toggle('active', queryWrap.classList.contains('revealed'));
    if (queryWrap.classList.contains('revealed')) input.focus();
  });

  retryBtn.addEventListener('click', () => {
    retryBtn.classList.add('spinning');
    setTimeout(() => retryBtn.classList.remove('spinning'), 650);
    fire(currentQuery());
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') retryBtn.click(); });

  fire(defaultQuery);
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
    r.querySelector('.use-btn').addEventListener('click', (e) => {
      const onChange = prefix === 'e' ? updateNoteJsonView : null;
      addTranslationRow(`${prefix}_translations_list`, lang, c.text, onChange);
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
function buildInflectionsProviderBlock(provider, prefix, defaultQuery) {
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

  async function fire(queryValue) {
    resultBox.innerHTML = '<div class="suggest-skel"></div>';
    const { status, body } = await enrichLookup('inflections', provider, enrichRequestFields('inflections', prefix, queryValue));
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

  editBtn.addEventListener('click', () => {
    queryWrap.classList.toggle('revealed');
    editBtn.classList.toggle('active', queryWrap.classList.contains('revealed'));
    if (queryWrap.classList.contains('revealed')) input.focus();
  });

  retryBtn.addEventListener('click', () => {
    retryBtn.classList.add('spinning');
    setTimeout(() => retryBtn.classList.remove('spinning'), 650);
    fire(currentQuery());
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') retryBtn.click(); });

  fire(defaultQuery);
  return wrap;
}

function buildTranslationsSuggestPanel(prefix, providers, defaultQuery) {
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

  function addLangGroup(lang) {
    lang = lang.trim().toLowerCase();
    if (!lang || groupsEl.querySelector(`[data-lang="${lang}"]`)) return;
    const group = enrichEl(`
      <div class="lang-group" data-lang="${lang}">
        <div class="lang-group-head"><span class="lang-pill">${escapeHtml(lang)}</span>${escapeHtml(enrichLangLabel(lang))}</div>
      </div>
    `);
    providers.forEach((p) => {
      group.appendChild(buildEnrichProviderRow('translations', p, prefix, defaultQuery, renderTranslationCandidate(prefix, lang), lang));
    });
    groupsEl.appendChild(group);
  }

  SUGGEST_DEFAULT_LANGS.forEach(addLangGroup);

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

async function openSuggestPanel(panelEl) {
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
    panelEl.appendChild(buildTranslationsSuggestPanel(prefix, providers, defaultQuery));
    return;
  }
  if (kind === 'inflections') {
    panelEl.appendChild(enrichEl(`<div class="suggest-head"><span>${providers.length} provider(s) configured</span><span>copy or fill per field</span></div>`));
    const defaultQuery = suggestControlQueryValue(panelEl.id, prefix);
    providers.forEach((p) => panelEl.appendChild(buildInflectionsProviderBlock(p, prefix, defaultQuery)));
    return;
  }
  if (kind === 'stt') {
    panelEl.appendChild(enrichEl(`<div class="suggest-head"><span>${providers.length} provider(s) configured</span><span>transcribed from this note's audio</span></div>`));
    providers.forEach((p) => panelEl.appendChild(buildSttProviderBlock(p, prefix)));
    return;
  }

  panelEl.appendChild(enrichEl(`<div class="suggest-head"><span>${providers.length} provider(s) configured</span><span>editable per-provider</span></div>`));
  const defaultQuery = suggestControlQueryValue(panelEl.id, prefix);
  const renderCandidate = kind === 'ipa' ? renderIpaCandidate(prefix) : renderTtsCandidate(prefix);
  providers.forEach((p) => panelEl.appendChild(buildEnrichProviderRow(kind, p, prefix, defaultQuery, renderCandidate)));
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
