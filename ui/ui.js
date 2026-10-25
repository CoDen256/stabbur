// ui.js — the bare authoring form's client logic (design.md D-N3's
// "no inbox, no suggestions, no bulk actions": every note is addressed by
// id, typed or pasted in, not listed).

function authHeaders() {
  const token = document.getElementById('tokenInput').value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function parseJsonField(id, fallback) {
  const raw = document.getElementById(id).value.trim();
  if (!raw) return fallback;
  return JSON.parse(raw);
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

document.getElementById('createForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    type: document.getElementById('c_type').value,
    source_lang: document.getElementById('c_source_lang').value,
    text: document.getElementById('c_text').value,
    translations: parseJsonField('c_translations', []),
    transcription: document.getElementById('c_transcription').value || null,
    pos: document.getElementById('c_pos').value || null,
    lemma: document.getElementById('c_lemma').value || null,
    inflections: parseJsonField('c_inflections', {}),
    context_text: document.getElementById('c_context_text').value || null,
    grammar_rule_id: document.getElementById('c_grammar_rule_id').value
      ? Number(document.getElementById('c_grammar_rule_id').value)
      : null,
  };
  const { status, body } = await api('/api/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  document.getElementById('createResult').textContent = `${status}\n${JSON.stringify(body, null, 2)}`;
  if (status === 201) document.getElementById('e_id').value = body.id;
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
  document.getElementById('ruleResult').textContent = `${status}\n${JSON.stringify(body, null, 2)}`;
});

document.getElementById('listRulesBtn').addEventListener('click', async () => {
  const { status, body } = await api('/api/grammar_rules');
  document.getElementById('ruleList').textContent = `${status}\n${JSON.stringify(body, null, 2)}`;
});

function fillEditForm(note) {
  document.getElementById('e_type').value = note.type;
  document.getElementById('e_source_lang').value = note.source_lang;
  document.getElementById('e_text').value = note.text;
  document.getElementById('e_translations').value = JSON.stringify(note.translations ?? []);
  document.getElementById('e_transcription').value = note.transcription ?? '';
  document.getElementById('e_pos').value = note.pos ?? '';
  document.getElementById('e_lemma').value = note.lemma ?? '';
  document.getElementById('e_inflections').value = JSON.stringify(note.inflections ?? {});
  document.getElementById('e_context_text').value = note.context_text ?? '';
  document.getElementById('e_grammar_rule_id').value = note.grammar_rule_id ?? '';
  document.getElementById('e_status').value = note.status;
  document.getElementById('e_audio_blob').textContent = note.audio_blob ?? 'null';
  document.getElementById('e_audio_sel_ms').value = note.audio_sel_ms ? JSON.stringify(note.audio_sel_ms) : '';

  const preview = document.getElementById('e_audio_preview');
  if (note.audio_blob) {
    preview.src = `/blob/${note.audio_blob}`;
    preview.style.display = 'block';
  } else {
    preview.style.display = 'none';
  }

  document.getElementById('editForm').style.display = 'block';
  document.getElementById('audioSection').style.display = 'block';
  document.getElementById('deleteBtn').style.display = 'inline-block';
}

document.getElementById('loadBtn').addEventListener('click', async () => {
  const id = document.getElementById('e_id').value.trim();
  if (!id) return;
  const { status, body } = await api(`/api/notes/${id}`);
  document.getElementById('editResult').textContent = `${status}\n${JSON.stringify(body, null, 2)}`;
  if (status === 200) fillEditForm(body);
});

document.getElementById('editForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('e_id').value.trim();
  const payload = {
    type: document.getElementById('e_type').value,
    source_lang: document.getElementById('e_source_lang').value,
    text: document.getElementById('e_text').value,
    translations: parseJsonField('e_translations', []),
    transcription: document.getElementById('e_transcription').value || null,
    pos: document.getElementById('e_pos').value || null,
    lemma: document.getElementById('e_lemma').value || null,
    inflections: parseJsonField('e_inflections', {}),
    context_text: document.getElementById('e_context_text').value || null,
    grammar_rule_id: document.getElementById('e_grammar_rule_id').value
      ? Number(document.getElementById('e_grammar_rule_id').value)
      : null,
    status: document.getElementById('e_status').value,
    audio_sel_ms: parseJsonField('e_audio_sel_ms', null),
  };
  const { status, body } = await api(`/api/notes/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  document.getElementById('editResult').textContent = `${status}\n${JSON.stringify(body, null, 2)}`;
  if (status === 200) fillEditForm(body);
});

document.getElementById('uploadAudioBtn').addEventListener('click', async () => {
  const id = document.getElementById('e_id').value.trim();
  const fileInput = document.getElementById('e_audio_file');
  if (!id || !fileInput.files[0]) return;

  const form = new FormData();
  form.append('audio', fileInput.files[0]);
  const uploadResp = await fetch('/blobs', { method: 'POST', headers: authHeaders(), body: form });
  const { sha256 } = await uploadResp.json();

  const { status, body } = await api(`/api/notes/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_blob: sha256 }),
  });
  document.getElementById('editResult').textContent = `${status}\n${JSON.stringify(body, null, 2)}`;
  if (status === 200) fillEditForm(body);
});

document.getElementById('deleteBtn').addEventListener('click', async () => {
  const id = document.getElementById('e_id').value.trim();
  if (!id) return;
  const resp = await fetch(`/api/notes/${id}`, { method: 'DELETE', headers: authHeaders() });
  const text = await resp.text();
  document.getElementById('editResult').textContent = `${resp.status}\n${text}`;
});
