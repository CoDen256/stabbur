(() => {
  "use strict";

  const progressEl = document.getElementById("progress");
  const emptyEl = document.getElementById("empty");
  const bodyEl = document.getElementById("body");
  const textEl = document.getElementById("text");
  const posEl = document.getElementById("pos");
  const audioRowEl = document.getElementById("audio-row");
  const playBtn = document.getElementById("play-btn");
  const translationsEl = document.getElementById("translations");
  const transcriptionField = document.getElementById("transcription-field");
  const transcriptionEl = document.getElementById("transcription");
  const inflectionsField = document.getElementById("inflections-field");
  const inflectionsEl = document.getElementById("inflections");
  const contextField = document.getElementById("context-field");
  const contextEl = document.getElementById("context");
  const evidenceRow = document.getElementById("evidence-row");
  const verdictPill = document.getElementById("verdict-pill");
  const evidenceDetail = document.getElementById("evidence-detail");
  const conflictsEl = document.getElementById("conflicts");
  const conflictsBody = document.getElementById("conflicts-body");
  const sourcesEl = document.getElementById("sources");
  const recentList = document.getElementById("recent-list");
  const helpOverlay = document.getElementById("help-overlay");
  const helpBtn = document.getElementById("help-btn");
  const player = document.getElementById("player");
  const preloadPlayer = document.getElementById("preload-player");

  let current = null; // the candidate payload currently on screen
  let gestureHappened = false; // browsers block autoplay before a user gesture (design D3)
  let busy = false; // true while a decision/undo/skip request is in flight

  function audioUrl(signatureKey) {
    return "/api/audio/" + encodeURIComponent(signatureKey);
  }

  function renderTranslations(translations) {
    translationsEl.innerHTML = "";
    if (!translations || !translations.length) {
      translationsEl.textContent = "—";
      return;
    }
    for (const t of translations) {
      const span = document.createElement("span");
      span.className = "translation-item";
      const lang = document.createElement("span");
      lang.className = "lang";
      lang.textContent = t.lang;
      span.appendChild(lang);
      span.appendChild(document.createTextNode(t.text));
      translationsEl.appendChild(span);
    }
  }

  function renderInflections(inflections) {
    inflectionsEl.innerHTML = "";
    const entries = Object.entries(inflections || {}).filter(([k]) => !k.startsWith("_"));
    if (!entries.length) {
      inflectionsField.hidden = true;
      return;
    }
    inflectionsField.hidden = false;
    for (const [key, value] of entries) {
      const span = document.createElement("span");
      span.className = "inflection-item";
      const k = document.createElement("span");
      k.className = "key";
      k.textContent = key;
      span.appendChild(k);
      span.appendChild(document.createTextNode(String(value)));
      inflectionsEl.appendChild(span);
    }
  }

  function renderConflicts(conflicts) {
    conflictsBody.innerHTML = "";
    const entries = Object.entries(conflicts || {});
    if (!entries.length) {
      conflictsEl.hidden = true;
      return;
    }
    conflictsEl.hidden = false;
    for (const [field, losers] of entries) {
      for (const loser of losers) {
        const div = document.createElement("div");
        div.textContent = `${field}: ${loser.source} also has ${JSON.stringify(loser.value)}`;
        conflictsBody.appendChild(div);
      }
    }
  }

  function renderSources(sources) {
    sourcesEl.innerHTML = "";
    for (const [field, source] of Object.entries(sources || {})) {
      const span = document.createElement("span");
      span.className = "source-chip";
      span.textContent = `${field}: ${source}`;
      sourcesEl.appendChild(span);
    }
  }

  function renderEvidence(verdict, evidence) {
    verdictPill.textContent = verdict + (evidence && evidence.rule ? ` · ${evidence.rule}` : "");
    const bits = [];
    if (evidence && evidence.cf_stock) bits.push(`cf. stock: ${JSON.stringify(evidence.cf_stock)}`);
    if (evidence && evidence.tokens) bits.push(`all tokens known, phrase isn't: ${evidence.tokens}`);
    evidenceDetail.textContent = bits.join(" — ");
    evidenceRow.hidden = false;
  }

  function renderRecent(recent) {
    recentList.innerHTML = "";
    for (const item of recent || []) {
      const li = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = item.text || item.signature_key;
      const decision = document.createElement("span");
      decision.className = "decision-" + item.decision;
      decision.textContent = item.decision === "accept" ? "new to me" : "already known";
      li.appendChild(label);
      li.appendChild(decision);
      recentList.appendChild(li);
    }
  }

  function renderCandidate(candidate) {
    const fields = candidate.fields || {};
    textEl.textContent = fields.text || "";
    posEl.textContent = fields.pos || "";
    renderTranslations(fields.translations);

    if (fields.transcription) {
      transcriptionField.hidden = false;
      transcriptionEl.textContent = fields.transcription;
    } else {
      transcriptionField.hidden = true;
    }

    renderInflections(fields.inflections);

    if (fields.context_text) {
      contextField.hidden = false;
      contextEl.textContent = fields.context_text;
    } else {
      contextField.hidden = true;
    }

    renderEvidence(candidate.verdict, candidate.evidence);
    renderConflicts(candidate.conflicts);
    renderSources(candidate.sources);

    audioRowEl.hidden = !candidate.has_audio;
  }

  function setupAudio(state) {
    if (!state.current || !state.current.has_audio) {
      player.removeAttribute("src");
      return;
    }
    const url = audioUrl(state.current.signature_key);
    if (player.getAttribute("src") !== url) {
      player.src = url;
    }
    if (gestureHappened) {
      player.currentTime = 0;
      player.play().catch(() => {
        /* still blocked somehow — the play button remains available */
      });
    }

    if (state.next_audio_signature) {
      preloadPlayer.src = audioUrl(state.next_audio_signature);
    } else {
      preloadPlayer.removeAttribute("src");
    }
  }

  function render(state) {
    current = state.current;
    progressEl.textContent = `${state.reviewed} reviewed · ${state.remaining} remaining`;

    if (!state.current) {
      emptyEl.hidden = false;
      bodyEl.hidden = true;
    } else {
      emptyEl.hidden = true;
      bodyEl.hidden = false;
      renderCandidate(state.current);
    }

    renderRecent(state.recent);
    setupAudio(state);
    busy = false;
  }

  async function fetchState() {
    const response = await fetch("/api/state");
    render(await response.json());
  }

  async function postJSON(url, body) {
    if (busy) return;
    busy = true;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    render(await response.json());
  }

  function decide(decision) {
    if (!current) return;
    postJSON("/api/decisions", { signature_key: current.signature_key, decision });
  }

  function skip() {
    if (!current) return;
    postJSON("/api/skip", { signature_key: current.signature_key });
  }

  function undo() {
    postJSON("/api/undo", {});
  }

  function replay() {
    if (!player.getAttribute("src")) return;
    player.currentTime = 0;
    player.play().catch(() => {});
  }

  function toggleHelp() {
    helpOverlay.hidden = !helpOverlay.hidden;
  }

  document.querySelectorAll(".actions .btn[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      gestureHappened = true;
      const action = btn.dataset.action;
      if (action === "accept" || action === "reject") decide(action);
      else if (action === "skip") skip();
      else if (action === "undo") undo();
    });
  });

  playBtn.addEventListener("click", () => {
    gestureHappened = true;
    replay();
  });

  helpBtn.addEventListener("click", toggleHelp);

  document.addEventListener("keydown", (event) => {
    if (event.key === "?" ) {
      event.preventDefault();
      toggleHelp();
      return;
    }
    if (event.key === "Escape" && !helpOverlay.hidden) {
      event.preventDefault();
      helpOverlay.hidden = true;
      return;
    }
    if (!helpOverlay.hidden) return; // keys other than ?/Esc do nothing while help is open

    gestureHappened = true;
    switch (event.key.toLowerCase()) {
      case "r":
        event.preventDefault();
        decide("accept");
        break;
      case "x":
        event.preventDefault();
        decide("reject");
        break;
      case "l":
        event.preventDefault();
        replay();
        break;
      case "v":
        event.preventDefault();
        undo();
        break;
      case "e":
        event.preventDefault();
        skip();
        break;
    }
  });

  fetchState();
})();
