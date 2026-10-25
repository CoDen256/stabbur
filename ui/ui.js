// ui.js — the operator console's client logic (vanilla JS, no framework,
// no build step — matches smia's/mjolnir's UI convention, D46).
//
// Hash-based routing: #/notes, #/notes/:id, #/grammar, #/grammar/:id,
// #/new-note, #/new-grammar. One `<section class="page">` per route, shown/
// hidden via the `.active` class.

const INFLECTION_SHAPES = {
  substantiv: ['article', 'sg_indef', 'sg_def', 'pl_indef', 'pl_def'],
  adjektiv: ['positiv', 'nøytrum', 'flertall', 'komparativ', 'superlativ'],
  verb: ['infinitiv', 'presens', 'preteritum', 'perfektum'],
  adverb: ['form'],
};

function authHeaders() {
  const token = document.getElementById('tokenInput').value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
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

async function renderNotesList() {
  const status = document.getElementById('notesStatusFilter').value;
  const type = document.getElementById('notesTypeFilter').value;
  const sort = document.getElementById('notesSort').value;
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

['notesStatusFilter', 'notesTypeFilter', 'notesSort'].forEach((id) =>
  document.getElementById(id).addEventListener('change', renderNotesList)
);
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
  document.getElementById('e_pos').value = note.pos || '';
  document.getElementById('e_source_lang').value = note.source_lang || '';
  document.getElementById('e_status').value = note.status;
  document.getElementById('e_transcription').value = note.transcription || '';
  document.getElementById('e_translations').value = JSON.stringify(note.translations ?? [], null, 2);
  document.getElementById('e_inflections').value = JSON.stringify(note.inflections ?? {}, null, 2);
  document.getElementById('e_context_text').value = note.context_text || '';
  document.getElementById('e_grammar_rule_id').value = note.grammar_rule_id ?? '';
  document.getElementById('noteSaveResult').textContent = '';

  updateNoAudioWarning();
  updateNoteJsonView();
  renderAudioSection(note);
}

function readEditForm() {
  let translations, inflections;
  try { translations = JSON.parse(document.getElementById('e_translations').value || '[]'); }
  catch { translations = currentNote?.translations ?? []; }
  try { inflections = JSON.parse(document.getElementById('e_inflections').value || '{}'); }
  catch { inflections = currentNote?.inflections ?? {}; }

  return {
    text: document.getElementById('e_text').value,
    lemma: document.getElementById('e_lemma').value || null,
    type: document.getElementById('e_type').value,
    pos: document.getElementById('e_pos').value || null,
    source_lang: document.getElementById('e_source_lang').value,
    status: document.getElementById('e_status').value,
    transcription: document.getElementById('e_transcription').value || null,
    translations,
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
  const uploadResp = await fetch('/blobs', { method: 'POST', headers: authHeaders(), body: form });
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
  if (!note.audio_blob) {
    none.style.display = 'block';
    player.style.display = 'none';
    waveformState = null;
    return;
  }
  none.style.display = 'none';
  player.style.display = 'block';

  const audioEl = document.getElementById('audioElement');
  audioEl.src = `/blob/${note.audio_blob}`;

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

async function renderGrammarList() {
  const sort = document.getElementById('grammarSort').value;
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

['grammarSort'].forEach((id) => document.getElementById(id).addEventListener('change', renderGrammarList));
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

function renderInflectionFields(pos) {
  const container = document.getElementById('c_inflections_fields');
  const shape = INFLECTION_SHAPES[pos];
  if (!shape) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = `<label>Inflections (${escapeHtml(pos)})</label>` + shape.map((field) => `
    <div style="margin-top:6px;">
      <label style="font-weight:400; text-transform:capitalize;">${escapeHtml(field.replace(/_/g, ' '))}</label>
      <input type="text" data-inflection-field="${field}">
    </div>
  `).join('');
}

function updateNewNoteFieldVisibility() {
  const type = document.getElementById('c_type').value;
  document.getElementById('c_pos_field').style.display = type === 'word' ? 'block' : 'none';
  document.getElementById('c_grammar_rule_field').style.display = type === 'grammar' ? 'block' : 'none';
  if (type !== 'word') {
    document.getElementById('c_pos').value = '';
    renderInflectionFields('');
  }
}

function renderNewNote() {
  document.getElementById('createForm').reset();
  document.getElementById('c_source_lang').value = 'no';
  document.getElementById('c_translations').value = '[]';
  document.getElementById('createResult').textContent = '';
  updateNewNoteFieldVisibility();
  renderInflectionFields(document.getElementById('c_pos').value);
}

document.getElementById('c_type').addEventListener('change', updateNewNoteFieldVisibility);
document.getElementById('c_pos').addEventListener('change', (e) => renderInflectionFields(e.target.value));

async function submitNewNote(status) {
  let translations;
  try { translations = JSON.parse(document.getElementById('c_translations').value || '[]'); }
  catch { translations = []; }

  const inflections = {};
  document.querySelectorAll('#c_inflections_fields [data-inflection-field]').forEach((input) => {
    inflections[input.dataset.inflectionField] = input.value;
  });

  const payload = {
    type: document.getElementById('c_type').value,
    source_lang: document.getElementById('c_source_lang').value,
    text: document.getElementById('c_text').value,
    status,
    pos: document.getElementById('c_pos').value || null,
    lemma: document.getElementById('c_lemma').value || null,
    transcription: document.getElementById('c_transcription').value || null,
    translations,
    inflections,
    context_text: document.getElementById('c_context_text').value || null,
    grammar_rule_id: document.getElementById('c_grammar_rule_id').value
      ? Number(document.getElementById('c_grammar_rule_id').value)
      : null,
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
    const uploadResp = await fetch('/blobs', { method: 'POST', headers: authHeaders(), body: form });
    const uploadBody = await uploadResp.json();
    if (uploadResp.status === 200) {
      await api(`/api/notes/${body.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_blob: uploadBody.sha256 }),
      });
    }
  }

  location.hash = `#/notes/${body.id}`;
}

document.getElementById('createForm').addEventListener('submit', (e) => {
  e.preventDefault();
  submitNewNote('draft');
});
document.getElementById('createReadyBtn').addEventListener('click', () => submitNewNote('ready'));

// --------------------------------------------------------- new grammar --

function renderNewGrammar() {
  document.getElementById('ruleForm').reset();
  document.getElementById('ruleResult').textContent = '';
}

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
