"""
scripts/seed_p4_notes.py — hand-authored seed notes for local/dev use, with
real audio sourced from `phonexa/lang/no/audio` (per-clip durations measured
with ffprobe), created via the real HTTP API (not direct DB writes) so it
exercises the same path a human using `/ui` would.

Notes are grouped into batches of 11, each batch covering every note type
(word: substantiv/adjektiv/adverb/verb/preposisjon, expression, listening,
pronunciation, grammar) plus one grammar_rule the batch's grammar note
references. Batches are independent — running batch 2 does not require
batch 1 to have been run first.

Not part of the service itself — run once per batch, by hand:
  STABBUR_AUTH_TOKEN=... python scripts/seed_p4_notes.py <batch> [base_url]
"""

from __future__ import annotations

import sys

import requests

PHONEXA_AUDIO = "/home/coden/dev/phonexa/lang/no/audio"

BATCHES = {
    1: dict(
        grammar_rule=dict(
            title="Perfektum of strong verbs",
            html=(
                "<p>Strong verbs change their stem vowel instead of taking "
                "<code>-et</code> in the perfektum, e.g. "
                "<em>skrive &rarr; har skrevet</em>.</p>"
            ),
        ),
        grammar_note=dict(
            type="grammar", text="Hva er perfektum av 'å skrive'?",
            translations=[{"lang": "en", "text": "What is the perfect tense of 'to write'?"}],
            context_text="har skrevet",
            audio_file=f"{PHONEXA_AUDIO}/mjolnir/er/skriver.mp3", audio_ms=1280,
        ),
        notes=[
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
        ],
    ),
    2: dict(
        grammar_rule=dict(
            title="Nøytrum of adjectives",
            html=(
                "<p>Adjectives take <code>-t</code> in the nøytrum (intetkjønn) "
                "form, e.g. <em>ny &rarr; nytt</em>.</p>"
            ),
        ),
        grammar_note=dict(
            type="grammar", text="Hva er nøytrumsformen av 'ny'?",
            translations=[{"lang": "en", "text": "What is the neuter form of 'new'?"}],
            context_text="et nytt hus",
            audio_file=f"{PHONEXA_AUDIO}/mjolnir/y/nytt.mp3", audio_ms=1071,
        ),
        notes=[
            dict(
                type="word", pos="substantiv", lemma="dag", text="dag",
                translations=[{"lang": "en", "text": "day"}, {"lang": "de", "text": "Tag"}],
                inflections={"article": "en", "sg_indef": "dag", "sg_def": "dagen", "pl_indef": "dager", "pl_def": "dagene"},
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/a/dag.mp3", audio_ms=653,
            ),
            dict(
                type="word", pos="substantiv", lemma="jobb", text="jobb",
                translations=[{"lang": "en", "text": "job"}, {"lang": "de", "text": "Job / Arbeit"}],
                inflections={"article": "en", "sg_indef": "jobb", "sg_def": "jobben", "pl_indef": "jobber", "pl_def": "jobbene"},
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/o/jobb.mp3", audio_ms=705,
            ),
            dict(
                type="word", pos="verb", lemma="skjønne", text="skjønne",
                translations=[{"lang": "en", "text": "to understand"}, {"lang": "de", "text": "verstehen"}],
                inflections={"infinitiv": "skjønne", "presens": "skjønner", "preteritum": "skjønte", "perfektum": "har skjønt"},
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/oe/skjoenner.mp3", audio_ms=1045,
            ),
            dict(
                type="word", pos="adjektiv", lemma="ny", text="ny",
                translations=[{"lang": "en", "text": "new"}, {"lang": "de", "text": "neu"}],
                inflections={"positiv": "ny", "nøytrum": "nytt", "flertall": "nye", "komparativ": "nyere", "superlativ": "nyest"},
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/y/nytt.mp3", audio_ms=1071,
            ),
            dict(
                type="word", pos="adverb", lemma="bare", text="bare",
                translations=[{"lang": "en", "text": "just / only"}, {"lang": "de", "text": "nur / einfach"}],
                inflections={"form": "bare"},
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/schwa/bare.mp3", audio_ms=914,
            ),
            dict(
                type="word", pos="preposisjon", lemma="for", text="for",
                translations=[{"lang": "en", "text": "for"}, {"lang": "de", "text": "für"}],
                inflections={},
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/o/for.mp3", audio_ms=549,
            ),
            dict(
                type="word", pos="preposisjon", lemma="etter", text="etter",
                translations=[{"lang": "en", "text": "after"}, {"lang": "de", "text": "nach"}],
                inflections={},
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/e/etter.mp3", audio_ms=836,
            ),
            dict(
                type="expression", text="god dag",
                translations=[{"lang": "en", "text": "good day"}, {"lang": "de", "text": "guten Tag"}],
                context_text="Man sier 'god dag' som en formell hilsen.",
                audio_file=f"{PHONEXA_AUDIO}/god_dag.mp3", audio_ms=750,
            ),
            dict(
                type="listening", text="ikke",
                translations=[{"lang": "en", "text": "not"}, {"lang": "de", "text": "nicht"}],
                context_text="Dictation drill: write down what you hear.",
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/i/ikke.mp3", audio_ms=967,
            ),
            dict(
                type="pronunciation", text="hei", transcription="hæi",
                translations=[{"lang": "en", "text": "hi"}, {"lang": "de", "text": "hallo"}],
                audio_file=f"{PHONEXA_AUDIO}/mjolnir/aei/hei.mp3", audio_ms=653,
            ),
        ],
    ),
}


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
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <batch:{'|'.join(str(k) for k in BATCHES)}> [base_url]")

    batch_num = int(sys.argv[1])
    if batch_num not in BATCHES:
        sys.exit(f"unknown batch {batch_num}; available: {sorted(BATCHES)}")
    batch = BATCHES[batch_num]

    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5056"
    import os

    token = os.environ["STABBUR_AUTH_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    rule_create = requests.post(f"{base_url}/api/grammar_rules", headers=headers, json=batch["grammar_rule"])
    rule_create.raise_for_status()
    rule = rule_create.json()
    print(f"grammar_rule: {rule['title']!r} id={rule['id']}")

    created = [_create_note(base_url, headers, spec) for spec in batch["notes"]]
    created.append(_create_note(base_url, headers, {**batch["grammar_note"], "grammar_rule_id": rule["id"]}))

    print(f"\nbatch {batch_num}: {len(created)} notes created and marked ready, 1 grammar rule created.")


if __name__ == "__main__":
    main()
