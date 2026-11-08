"""
scripts/import/ingest.py — section 2: parse the five external sources
verbatim into `raw_note` (tasks 2.1-2.5).

`.apkg` archives are legacy plain SQLite (confirmed by magic bytes against
all four files on disk, task 2.1 — not assumed). Each is opened as a zip,
`collection.anki21` is extracted to a temp file and read with the stdlib
`sqlite3` module, `notes.flds` is split on `\x1f` using the field order from
`col.models`, and `[sound:...]` references in field values are resolved
against the archive's `media` JSON (numeric key -> original filename) into
`raw_note.media_json` (task 2.2), so a later stage can pull audio bytes
straight out of the right archive by member key without re-parsing notes.

Every value is stored as read — no field is reinterpreted, no notation is
parsed, no type is assigned. That is `normalize`'s job (section 3).
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

IMPORT_DIR = Path(__file__).resolve().parent.parent.parent / "import"

SOUND_REF_RE = re.compile(r"\[sound:([^\]]+)\]")

# Measured against the actual archives (design.md's Context table, corrected
# in section 2 for freq6k — see design.md's implementation-correction note).
APKG_SOURCES = {
    "ntnu": {
        "file": "NTNU_Norskkurs_Now_1_Complete_Vocabulary_Deck.apkg",
        "models": ("NoW",),
        "expected_count": 749,
    },
    "a1_31k": {
        "file": "Norwegian_A1_Words__Sentences_with_Native_Audio_31k.apkg",
        "models": ("Basic (Norwegian A1)",),
        "expected_count": 3097,
    },
    "core6k": {
        "file": "Norwegian_Bokml_Core_6k__Vocabulary_Sentences_Audio.apkg",
        # Grammar (225) is excluded here, not merely elsewhere (design D9).
        "models": ("Norwegian Core", "Country"),
        "expected_count": 6383,
    },
    "freq6k": {
        "file": "6000_Most_Frequent_Norwegian_Words_A1-B1_offline_audio.apkg",
        # "Read me" (1 note) is excluded here.
        "models": ("6000 Most Frequent Norwegian Words",),
        "expected_count": 3881,
    },
}

CSV_SOURCE = "herpaberget"
CSV_GLOB = "Her-på-berget-ordliste-original.xlsx - *.csv"
CSV_EXPECTED_COUNT = 1152
CSV_FIELDS = (
    "Kapittel",
    "Original word",
    "Explanation (no)",
    "Explanation (en)",
    "Example (no)",
    "Example (en)",
)


class IngestCountMismatch(AssertionError):
    pass


def _read_apkg(path: Path) -> tuple[list[sqlite3.Row], dict[int, str], dict[int, list[str]], dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        media_by_member = json.loads(archive.read("media").decode("utf-8"))
        filename_to_member = {filename: member for member, filename in media_by_member.items()}

        with tempfile.NamedTemporaryFile(suffix=".anki21") as tmp:
            tmp.write(archive.read("collection.anki21"))
            tmp.flush()
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
            magic = open(tmp.name, "rb").read(16)
            if not magic.startswith(b"SQLite format 3"):
                raise IngestCountMismatch(f"{path.name}: collection.anki21 is not plain SQLite (got {magic!r})")

            models = json.loads(conn.execute("SELECT models FROM col").fetchone()["models"])
            model_name_by_id = {int(mid): m["name"] for mid, m in models.items()}
            model_fields_by_id = {int(mid): [f["name"] for f in m["flds"]] for mid, m in models.items()}

            notes = conn.execute("SELECT id, mid, tags, flds FROM notes").fetchall()
            conn.close()

    return notes, model_name_by_id, model_fields_by_id, filename_to_member


def _resolve_media(fields: dict[str, str], filename_to_member: dict[str, str]) -> dict[str, str | None]:
    media: dict[str, str | None] = {}
    for value in fields.values():
        for filename in SOUND_REF_RE.findall(value):
            media[filename] = filename_to_member.get(filename)
    return media


def ingest_apkg_source(source: str) -> tuple[list[dict], int]:
    """Returns (raw rows for allowed models, total note count across every
    model in the archive — including excluded ones, for the discard count)."""
    spec = APKG_SOURCES[source]
    path = IMPORT_DIR / spec["file"]
    notes, model_name_by_id, model_fields_by_id, filename_to_member = _read_apkg(path)

    rows = []
    for note in notes:
        mid = note["mid"]
        model_name = model_name_by_id.get(mid, f"<unknown model {mid}>")
        if model_name not in spec["models"]:
            continue
        field_names = model_fields_by_id[mid]
        values = note["flds"].split("\x1f")
        fields = dict(zip(field_names, values))
        tags = [t for t in note["tags"].split(" ") if t]
        media = _resolve_media(fields, filename_to_member)
        rows.append(
            {
                "source": source,
                "source_note_id": str(note["id"]),
                "note_type": model_name,
                "fields": fields,
                "tags": tags,
                "media": media,
            }
        )
    return rows, len(notes)


def ingest_csv_source() -> list[dict]:
    rows = []
    for path in sorted(IMPORT_DIR.glob(CSV_GLOB)):
        current_section = None
        row_index = 0
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # header
            for raw_row in reader:
                cells = (raw_row + [""] * len(CSV_FIELDS))[: len(CSV_FIELDS)]
                cells = [c.strip() for c in cells]
                kapittel, word = cells[0], cells[1]
                if not word and not kapittel:
                    continue  # fully blank row
                if not word and kapittel:
                    current_section = kapittel  # section header, carried down
                    continue
                row_index += 1
                fields = dict(zip(CSV_FIELDS, cells))
                fields["Kapittel"] = kapittel or current_section or ""
                rows.append(
                    {
                        "source": CSV_SOURCE,
                        "source_note_id": f"{path.name}:{row_index}",
                        "note_type": "csv_row",
                        "fields": fields,
                        "tags": [],
                        "media": {},
                    }
                )
    return rows


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    import store

    all_rows: list[dict] = []
    count_in = 0

    for source, spec in APKG_SOURCES.items():
        rows, total_notes = ingest_apkg_source(source)
        count_in += total_notes
        if len(rows) != spec["expected_count"]:
            raise IngestCountMismatch(
                f"{source}: expected {spec['expected_count']} notes after model filtering, got {len(rows)}"
            )
        all_rows.extend(rows)

    csv_rows = ingest_csv_source()
    count_in += len(csv_rows)
    if len(csv_rows) != CSV_EXPECTED_COUNT:
        raise IngestCountMismatch(f"{CSV_SOURCE}: expected {CSV_EXPECTED_COUNT} rows, got {len(csv_rows)}")
    all_rows.extend(csv_rows)

    store.replace_stage_table(conn, "ingest")
    for row in all_rows:
        conn.execute(
            """
            INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json, tags_json, media_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row["source"],
                row["source_note_id"],
                row["note_type"],
                json.dumps(row["fields"], ensure_ascii=False),
                json.dumps(row["tags"], ensure_ascii=False),
                json.dumps(row["media"], ensure_ascii=False),
            ),
        )
    conn.commit()

    count_out = len(all_rows)
    count_discarded = count_in - count_out
    return count_in, count_out, count_discarded
