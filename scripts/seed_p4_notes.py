"""
scripts/seed_p4_notes.py — one-off script for task 5.1: hand-author the 10
real notes P4's finish line calls for, with real audio sourced from
`phonexa/lang/no/audio` (per-clip durations measured with ffprobe), via the
real HTTP API (not direct DB writes) so it exercises the same path a human
using `/ui` would. Also seeds one `grammar_rule` and one `type=grammar` note
that references it, so the grammar-management UI has real data to show.

Not part of the service itself — run once, by hand:
  STABBUR_AUTH_TOKEN=... python scripts/seed_p4_notes.py [base_url]
"""

from __future__ import annotations

import sys

import requests

PHONEXA_AUDIO = "/home/coden/dev/phonexa/lang/no/audio"

GRAMMAR_RULE = dict(
    title="Perfektum of strong verbs",
    html=(
        "<p>Strong verbs change their stem vowel instead of taking "
        "<code>-et</code> in the perfektum, e.g. "
        "<em>skrive &rarr; har skrevet</em>.</p>"
    ),
)

# grammar_rule_id is filled in at runtime once the rule above is created.
GRAMMAR_NOTE = dict(
    type="grammar", text="Hva er perfektum av 'å skrive'?",
    translations=[{"lang": "en", "text": "What is the perfect tense of 'to write'?"}],
    context_text="har skrevet",
    audio_file=f"{PHONEXA_AUDIO}/mjolnir/er/skriver.mp3", audio_ms=1280,
)

NOTES = [
    dict(
        type="word", pos="substantiv", lemma="øye", text="øye",
        translations=[{"lang": "en", "text": "eye"}, {"lang": "de", "text": "Auge"}],
        inflections={"article": "et", "sg_indef": "øye", "sg_def": "øyet", "pl_indef": "øyne", "pl_def": "øynene"},
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/oey/oeye.mp3", audio_ms=862,
    ),
    dict(
        type="word", pos="substantiv", lemma="mening", text="mening",
        translations=[{"lang": "en", "text": "meaning / opinion"}, {"lang": "de", "text": "Meinung / Bedeutung"}],
        inflections={"article": "en", "sg_indef": "mening", "sg_def": "meningen", "pl_indef": "meninger", "pl_def": "meningene"},
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/mening.mp3", audio_ms=780,
    ),
    dict(
        type="word", pos="verb", lemma="skrive", text="skrive",
        translations=[{"lang": "en", "text": "to write"}, {"lang": "de", "text": "schreiben"}],
        inflections={"infinitiv": "skrive", "presens": "skriver", "preteritum": "skrev", "perfektum": "har skrevet"},
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/er/skriver.mp3", audio_ms=1280,
        context_text="Hun skriver et brev.",
    ),
    dict(
        type="word", pos="verb", lemma="kunne", text="kunne",
        translations=[{"lang": "en", "text": "can / could"}, {"lang": "de", "text": "können"}],
        inflections={"infinitiv": "kunne", "presens": "kan", "preteritum": "kunne", "perfektum": "har kunnet"},
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/ue/kunne.mp3", audio_ms=940,
    ),
    dict(
        type="word", pos="adjektiv", lemma="ledig", text="ledig",
        translations=[{"lang": "en", "text": "available / vacant"}, {"lang": "de", "text": "frei / verfügbar"}],
        inflections={"positiv": "ledig", "nøytrum": "ledig", "flertall": "ledige", "komparativ": "ledigere", "superlativ": "ledigst"},
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/ledig.mp3", audio_ms=500,
    ),
    dict(
        type="word", pos="adjektiv", lemma="enig", text="enig",
        translations=[{"lang": "en", "text": "in agreement"}, {"lang": "de", "text": "einig"}],
        inflections={"positiv": "enig", "nøytrum": "enig", "flertall": "enige", "komparativ": "mer enig", "superlativ": "mest enig"},
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/enig.mp3", audio_ms=500,
    ),
    dict(
        type="expression", text="god morgen",
        translations=[{"lang": "en", "text": "good morning"}, {"lang": "de", "text": "guten Morgen"}],
        context_text="Man sier 'god morgen' til noen man møter tidlig på dagen.",
        audio_file=f"{PHONEXA_AUDIO}/god_morgen.mp3", audio_ms=1080,
    ),
    dict(
        type="expression", text="unnskyld",
        translations=[{"lang": "en", "text": "sorry / excuse me"}, {"lang": "de", "text": "Entschuldigung"}],
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/ue/unnskyld.mp3", audio_ms=940,
    ),
    dict(
        type="listening", text="hvor",
        translations=[{"lang": "en", "text": "where"}, {"lang": "de", "text": "wo"}],
        context_text="Dictation drill: write down what you hear.",
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/u/hvor.mp3", audio_ms=601,
    ),
    dict(
        type="pronunciation", text="rom", transcription="ɹuːm",
        translations=[{"lang": "en", "text": "room"}, {"lang": "de", "text": "Zimmer"}],
        audio_file=f"{PHONEXA_AUDIO}/mjolnir/u/rom.mp3", audio_ms=679,
    ),
]


def _create_note(base_url: str, headers: dict, spec: dict) -> dict:
    spec = dict(spec)
    audio_file = spec.pop("audio_file")
    audio_ms = spec.pop("audio_ms")

    with open(audio_file, "rb") as f:
        upload = requests.post(f"{base_url}/blobs", headers=headers, files={"audio": f})
    upload.raise_for_status()
    sha256 = upload.json()["sha256"]

    payload = {"source_lang": "no", "status": "draft", **spec}
    create = requests.post(f"{base_url}/api/notes", headers=headers, json=payload)
    create.raise_for_status()
    note = create.json()

    patch = requests.patch(
        f"{base_url}/api/notes/{note['id']}",
        headers=headers,
        json={"audio_blob": sha256, "audio_sel_ms": [0, audio_ms], "status": "ready"},
    )
    patch.raise_for_status()
    result = patch.json()
    print(f"ready: {note['type']:<13} {spec['text']!r:<15} id={note['id']} audio={sha256[:12]}...")
    return result


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5056"
    import os

    token = os.environ["STABBUR_AUTH_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    rule_create = requests.post(f"{base_url}/api/grammar_rules", headers=headers, json=GRAMMAR_RULE)
    rule_create.raise_for_status()
    rule = rule_create.json()
    print(f"grammar_rule: {rule['title']!r} id={rule['id']}")

    created = [_create_note(base_url, headers, spec) for spec in NOTES]
    created.append(_create_note(base_url, headers, {**GRAMMAR_NOTE, "grammar_rule_id": rule["id"]}))

    print(f"\n{len(created)} notes created and marked ready, 1 grammar rule created.")


if __name__ == "__main__":
    main()
